import sys, json, os, re
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
import cv2

# ponytail: minimal PaddleOCR 2.9.1 bridge
_ocr = None

def get_ocr():
    global _ocr
    if _ocr is None:
        from paddleocr import PaddleOCR
        _ocr = PaddleOCR(use_angle_cls=False, lang='id', show_log=False)
    return _ocr

MONTH_NAMES = r'(?:jan(?:uari)?|feb(?:ruari)?|mar(?:et)?|apr(?:il)?|mei|jun(?:i)?|jul(?:i)?|agu(?:stus)?|sep(?:tember)?|okt(?:ober)?|nov(?:ember)?|des(?:ember)?)'
DAY_NAMES = r'(?:senin|selasa|rabu|kamis|jumat|sabtu|minggu|sen|sel|rab|kam|jum|sab|min)'

YEAR_RE = re.compile(r'202[0-9]')
MONTH_RE = re.compile(rf'\b{MONTH_NAMES}\b', re.IGNORECASE)
DAY_RE = re.compile(rf'\b{DAY_NAMES}\b', re.IGNORECASE)
TIME_RE = re.compile(r'\b\d{1,2}[:.]\d{2}\b')

DATE_RE = re.compile(
    rf'(?:202[0-9]|\b{MONTH_NAMES}\b|\b{DAY_NAMES}\b|\b\d{{1,2}}[:.]\d{{2}}\b|\b\d{{1,2}}[-/]\d{{1,2}}[-/]\d{{2,4}}\b)',
    re.IGNORECASE
)

SKIP_RE = re.compile(
    r'(?:timemark|magicstudio|camera|timestamp|watermark|jln?\.?|stasiun|toko|kec\.?|kel\.?|kab\.?|prov\.?|kota|\bkode\b|\bkoordinat\b|\brt\b|\brw\b)',
    re.IGNORECASE
)

def detect(img_path):
    if not os.path.exists(img_path):
        return {"ok": False, "error": "file_not_found"}
    img = cv2.imread(img_path)
    if img is None:
        return {"ok": False, "error": "cannot_read_image"}
    h, w = img.shape[:2]
    scale = 4.0 if max(w, h) <= 400 else (2.0 if max(w, h) <= 800 else 1.0)
    proc_img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LANCZOS4) if scale > 1.0 else img

    ocr = get_ocr()
    res = ocr.ocr(proc_img, cls=False)
    if res and res[0]:
        parsed_lines = []
        for line in res[0]:
            pts, (text, conf) = line
            clean_txt = text.strip()
            xs = [p[0] / scale for p in pts]
            ys = [p[1] / scale for p in pts]
            parsed_lines.append({
                "x1": min(xs), "y1": min(ys),
                "x2": max(xs), "y2": max(ys),
                "y_mid": (min(ys) + max(ys)) / 2.0,
                "text": clean_txt,
                "conf": float(conf)
            })

        candidates = []
        for item in parsed_lines:
            clean_txt = item["text"]
            if DATE_RE.search(clean_txt) and not SKIP_RE.search(clean_txt) and '°' not in clean_txt and not re.search(r'^\s*[-+]?\d{1,3}\.\d+', clean_txt):
                # Cari segmen lain di baris horizontal yang sama (misal "senin:" di sebelah kiri tanggal)
                same_row = [
                    other for other in parsed_lines
                    if abs(other["y_mid"] - item["y_mid"]) <= 7.0 and not SKIP_RE.search(other["text"]) and not re.search(r'^\s*[-+]?\d{1,3}\.\d+', other["text"])
                ]
                min_x = min(other["x1"] for other in same_row)
                min_y = min(other["y1"] for other in same_row)
                max_x = max(other["x2"] for other in same_row)
                max_y = max(other["y2"] for other in same_row)

                x1 = max(0, int(min_x))
                y1 = max(0, int(min_y))
                x2 = min(w, int(max_x))
                y2 = min(h, int(max_y))
                if (x2 - x1) >= 20 and 7 <= (y2 - y1) <= 60:
                    merged_text = " ".join([other["text"] for other in sorted(same_row, key=lambda o: o["x1"])])
                    
                    # Hitung skor kualitas kecocokan tanggal Timemark
                    score = 0
                    if DAY_RE.search(merged_text): score += 6
                    if MONTH_RE.search(merged_text): score += 6
                    if YEAR_RE.search(merged_text): score += 6
                    if TIME_RE.search(merged_text): score += 1
                    # Posisi tipikal watermark Timemark: sisi kiri (x < 0.4*w) dan bagian bawah (y > 0.4*h)
                    if x1 < w * 0.4: score += 3
                    if y1 > h * 0.4: score += 3

                    candidates.append({
                        "ok": True,
                        "box": [x1, y1, x2, y2],
                        "text": merged_text,
                        "conf": item["conf"],
                        "score": score
                    })

        if candidates:
            # Prioritaskan kandidat dengan kelengkapan tanggal (hari/bulan/tahun) dan posisi watermark
            candidates.sort(key=lambda c: (c["score"], c["conf"]), reverse=True)
            best = candidates[0]
            return {
                "ok": True,
                "box": best["box"],
                "text": best["text"],
                "conf": best["conf"]
            }
    return {"ok": False, "box": None, "error": "date_not_found"}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "missing_path"}))
        sys.exit(1)
    print(json.dumps(detect(sys.argv[1])))
