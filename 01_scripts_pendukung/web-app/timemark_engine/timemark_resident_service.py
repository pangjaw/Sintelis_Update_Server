import os
import sys
import json
import time
import shutil
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

# Pastikan OpenMP / MKL tidak spin-waiting menghabiskan CPU 100% pada idle
os.environ["OMP_WAIT_POLICY"] = "PASSIVE"
os.environ["KMP_BLOCKTIME"] = "0"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

# Pastikan implementasi protobuf aman untuk PaddleOCR
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
os.environ["PYTHONUNBUFFERED"] = "1"

# Setup sys.path agar timemark_engine dapat diakses
CURRENT_DIR = Path(__file__).resolve().parent
WEB_APP_DIR = CURRENT_DIR.parent
if str(WEB_APP_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_APP_DIR))

# Pastikan model di-cache ke Drive C: (SSD) untuk kecepatan baca instan
def ensure_ssd_model_cache():
    local_appdata = os.environ.get("LOCALAPPDATA")
    if not local_appdata:
        return None
    ssd_dir = Path(local_appdata) / "Sintelis" / "models"
    ssd_dir.mkdir(parents=True, exist_ok=True)
    ssd_model = ssd_dir / "lama_fp32.onnx"
    
    src_model = CURRENT_DIR / "models" / "lama_fp32.onnx"
    if src_model.exists():
        if not ssd_model.exists() or ssd_model.stat().st_size != src_model.stat().st_size:
            try:
                print(f"[Resident Service] Menyalin model LaMa ke SSD ({ssd_model})...", flush=True)
                shutil.copy2(str(src_model), str(ssd_model))
            except Exception as e:
                print(f"[Resident Service] Gagal menyalin model ke SSD: {e}", flush=True)
                return str(src_model)
        return str(ssd_model)
    return str(src_model) if src_model.exists() else None

print("[Resident Service] Memulai pre-warming worker...", flush=True)
ensure_ssd_model_cache()

from timemark_engine.paddle_worker import detect as paddle_detect, get_ocr
from timemark_engine.edit_timemark_ide1 import get_lama_session, process_image, register_in_process_ocr

# Daftarkan fungsi OCR langsung in-memory agar process_image tidak perlu query HTTP ke dirinya sendiri
register_in_process_ocr(paddle_detect)

# Serializer reentrant inference lock agar alokasi VRAM GPU NVIDIA GTX 1050 aman dan re-entrant
_INFERENCE_LOCK = threading.RLock()

# Warm-up LaMa Session di GPU VRAM
t0 = time.perf_counter()
lama_sess = get_lama_session()
t1 = time.perf_counter()
print(f"[Resident Service] LaMa AI Session siap di GPU VRAM ({t1 - t0:.2f} detik)", flush=True)

# Warm-up PaddleOCR di RAM
t0 = time.perf_counter()
ocr_engine = get_ocr()
t1 = time.perf_counter()
print(f"[Resident Service] PaddleOCR engine siap di RAM ({t1 - t0:.2f} detik)", flush=True)


class ResidentRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Hindari spam stdout untuk request reguler
        pass

    def _json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            providers = lama_sess.get_providers() if lama_sess else ["CPUExecutionProvider"]
            self._json({
                "ok": True,
                "status": "ready",
                "providers": providers,
                "pid": os.getpid()
            })
        else:
            self._json({"ok": False, "error": "not_found"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception:
            payload = {}

        if self.path == "/ocr":
            # Endpoint deteksi OCR kilat (in-memory ~0.14 detik)
            img_path = payload.get("image_path", "")
            if not img_path or not os.path.exists(img_path):
                self._json({"ok": False, "error": "file_not_found"}, 400)
                return
            t0 = time.perf_counter()
            with _INFERENCE_LOCK:
                res = paddle_detect(img_path)
            dt = time.perf_counter() - t0
            res["duration_sec"] = round(dt, 4)
            self._json(res)

        elif self.path == "/process_image":
            # Endpoint proses foto lengkap (LaMa GPU inpainting + in-memory OCR ~1.0 detik)
            img_path = payload.get("image_path", "")
            out_path = payload.get("output_path", "")
            date_text = payload.get("timemark_text", "") or payload.get("date", "")
            y_override = payload.get("y_override")
            x_override = payload.get("x_override")
            detector = payload.get("detector", "paddle_ocr")
            ignore_manual = payload.get("ignore_manual", False)

            if not img_path or not os.path.exists(img_path):
                self._json({"ok": False, "error": f"input file tidak ditemukan: {img_path}"}, 400)
                return
            if not out_path:
                self._json({"ok": False, "error": "output_path wajib diisi"}, 400)
                return

            try:
                t0 = time.perf_counter()
                with _INFERENCE_LOCK:
                    st = process_image(
                        image_path=Path(img_path),
                        output_path=Path(out_path),
                        timemark_text=date_text,
                        y_override=y_override,
                        x_override=x_override,
                        detector=detector,
                        ignore_manual=ignore_manual
                    )
                dt = time.perf_counter() - t0
                self._json({
                    "ok": True,
                    "stage": st,
                    "output_path": out_path,
                    "duration_sec": round(dt, 4)
                })
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)

        elif self.path == "/shutdown":
            self._json({"ok": True, "message": "shutting down"})
            def _stop():
                time.sleep(0.5)
                self.server.shutdown()
            import threading
            threading.Thread(target=_stop, daemon=True).start()

        else:
            self._json({"ok": False, "error": "not_found"}, 404)


def run_service(port=58253):
    # Menggunakan ThreadingHTTPServer agar permintaan paralel tidak saling memblokir
    server = ThreadingHTTPServer(("127.0.0.1", port), ResidentRequestHandler)
    print(f"[Resident Service] Server berjalan di http://127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("[Resident Service] Server dihentikan.", flush=True)


if __name__ == "__main__":
    port = 58253
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    run_service(port)
