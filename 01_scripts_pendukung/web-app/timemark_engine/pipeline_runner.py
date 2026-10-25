"""
pipeline_runner.py — Orchestrator for OCR Foto Timemark & Merge Pipeline (Steps 1 to 5)
Handles dynamic source, target, export, and merged directories.
Supports Single Folder Mode (1 folder sumber) & Dual Folder Mode (2 folder sumber).
Supports real-time logging, cancellation, and progress updates.
"""
import os
import sys
import time
import json
import shutil
import subprocess
import threading

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))

state = {
    "running": False,
    "cancelled": False,
    "current_step": 0,
    "step_name": "",
    "progress": 0,
    "sub_current": 0,
    "sub_total": 0,
    "logs": [],
    "step_statuses": {
        "step1": "pending",
        "step1_5": "pending",
        "step2": "pending",
        "step3": "pending",
        "step4": "pending",
        "step4_fast": "pending",
        "step5": "pending",
    },
    "error": None,
    "summary": {},
    "active_process": None
}

_state_lock = threading.RLock()

def add_log(log_type, msg):
    ts = time.strftime("%H:%M:%S")
    with _state_lock:
        state["logs"].append({"type": log_type, "msg": msg, "ts": ts})
        if len(state["logs"]) > 1000:
            state["logs"] = state["logs"][-800:]

def get_state():
    with _state_lock:
        return {
            "running": state["running"],
            "cancelled": state["cancelled"],
            "current_step": state["current_step"],
            "step_name": state["step_name"],
            "progress": state["progress"],
            "sub_current": state.get("sub_current", 0),
            "sub_total": state.get("sub_total", 0),
            "logs": list(state["logs"]),
            "step_statuses": dict(state["step_statuses"]),
            "error": state["error"],
            "summary": dict(state["summary"])
        }

def cancel_pipeline():
    with _state_lock:
        state["cancelled"] = True
        state["running"] = False
        proc = state.get("active_process")
    add_log("warn", "🛑 Menghentikan pipeline...")
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            add_log("info", "Proses aktif berhasil dihentikan.")
        except Exception as e:
            add_log("error", f"Gagal menghentikan proses: {e}")

def run_cmd(cmd_list, step_key, step_name, start_pct=0.0, end_pct=100.0):
    import re
    with _state_lock:
        if state["cancelled"]:
            return False
        state["step_statuses"][step_key] = "running"
        state["step_name"] = step_name
        state["sub_current"] = 0
        state["sub_total"] = 0
        state["progress"] = int(round(start_pct))
    add_log("info", f"🚀 Memulai {step_name}...")

    prog_re = re.compile(r'(?:\[PROGRESS\]\s*(\d+)\s*/\s*(\d+)|\[(\d+)\s*/\s*(\d+)\])')

    try:
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONWARNINGS"] = "ignore::FutureWarning,ignore::DeprecationWarning"
        proc = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        )
        with _state_lock:
            state["active_process"] = proc

        for line in proc.stdout:
            line_str = line.strip()
            if not line_str:
                continue
            # Abaikan pesan FutureWarning / DeprecationWarning internal library (seperti fitz/__init__.py)
            if "FutureWarning:" in line_str or "DeprecationWarning:" in line_str or "fitz\__init__.py" in line_str or "fitz/__init__.py" in line_str:
                continue
            # Abaikan baris JSON telemetri internal agar log tetap bersih
            if line_str.startswith('{"type": "stage"') or line_str.startswith("__SUMMARY__:"):
                continue

            # Tangkap progres [cur/tot] atau [PROGRESS] cur/tot untuk menggerakkan progress bar secara real-time
            m_prog = prog_re.search(line_str)
            if m_prog:
                c_str = m_prog.group(1) or m_prog.group(3)
                t_str = m_prog.group(2) or m_prog.group(4)
                try:
                    cur_v = int(c_str)
                    tot_v = int(t_str)
                    if tot_v > 0 and 0 <= cur_v <= tot_v:
                        ratio = cur_v / tot_v
                        calc_pct = int(round(start_pct + ratio * (end_pct - start_pct)))
                        with _state_lock:
                            state["sub_current"] = cur_v
                            state["sub_total"] = tot_v
                            if calc_pct > state["progress"]:
                                state["progress"] = min(int(round(end_pct)), calc_pct)
                except Exception:
                    pass

            if "error" in line_str.lower() or "traceback" in line_str.lower():
                add_log("error", line_str)
            elif "warn" in line_str.lower():
                add_log("warn", line_str)
            elif "success" in line_str.lower() or "selesai" in line_str.lower():
                add_log("success", line_str)
            else:
                add_log("info", line_str)

        proc.wait()
        with _state_lock:
            state["active_process"] = None

        if state["cancelled"]:
            add_log("warn", f"⚠️ {step_name} dibatalkan pengguna.")
            return False

        if proc.returncode == 0:
            with _state_lock:
                state["step_statuses"][step_key] = "done"
                state["progress"] = int(round(end_pct))
                state["sub_current"] = 0
                state["sub_total"] = 0
            add_log("success", f"✓ {step_name} selesai.")
            return True
        else:
            with _state_lock:
                state["step_statuses"][step_key] = "error"
                state["error"] = f"{step_name} gagal dengan exit code {proc.returncode}"
            add_log("error", f"✗ {step_name} gagal (exit code: {proc.returncode})")
            return False
    except Exception as e:
        with _state_lock:
            state["step_statuses"][step_key] = "error"
            state["error"] = str(e)
            state["active_process"] = None
        add_log("error", f"✗ Galat pada {step_name}: {e}")
        return False

def _execute_pipeline_task(source_dir, target_dir, export_dir, merged_dir, selected_steps, mode="dual", overwrite_original=False, detector="google_vision"):
    with _state_lock:
        state["running"] = True
        state["cancelled"] = False
        state["error"] = None
        state["logs"].clear()
        state["progress"] = 0
        for k in state["step_statuses"]:
            state["step_statuses"][k] = "pending"

    py_exe = sys.executable

    # Tentukan root direktori dan pemisahan subfolder 03 (mentah) dan 04 (edited)
    export_norm = os.path.normpath(export_dir)
    bname = os.path.basename(export_norm).lower()
    if bname in ("03_export_foto", "03_photos_export"):
        raw_photos_dir = export_norm
        export_root = os.path.dirname(export_norm)
    elif bname in ("04_photos_edited", "04_foto_edited"):
        export_root = os.path.dirname(export_norm)
        raw_photos_dir = os.path.join(export_root, "03_export_foto")
    else:
        export_root = export_norm
        if os.path.isdir(os.path.join(export_root, "03_photos_export")) and not os.path.isdir(os.path.join(export_root, "03_export_foto")):
            raw_photos_dir = os.path.join(export_root, "03_photos_export")
        else:
            raw_photos_dir = os.path.join(export_root, "03_export_foto")

    edited_photos_dir = os.path.join(export_root, "04_photos_edited")
    os.makedirs(raw_photos_dir, exist_ok=True)
    os.makedirs(edited_photos_dir, exist_ok=True)
    os.makedirs(merged_dir, exist_ok=True)

    sap_mapping = os.path.join(ENGINE_DIR, "sap_station_mapping.json")
    time_mapping = os.path.join(ENGINE_DIR, "asset_waktu_mapping.json")
    data_acuan = os.path.join(ENGINE_DIR, "data_acuan_tenaga_gabungan.json")
    schedule_file = os.path.join(export_root, "schedule.json")

    steps_to_run = selected_steps if isinstance(selected_steps, list) else ["1", "1.5", "2", "3", "4", "5"]
    total_steps = len(steps_to_run)
    step_idx = 0

    mode_label = "Mode 1 Folder Sumber" if mode == "single" else "Mode 2 Folder Sumber (Klasik)"
    add_log("info", f"📌 Menjalankan pipeline dalam {mode_label}...")
    if mode == "single":
        add_log("info", f"📂 Folder Dokumen Tunggal: {source_dir}")
        if overwrite_original:
            add_log("warn", "⚠️ Mode Timpa Asli aktif: Berkas asli akan dicadangkan ke subfolder backups/ sebelum digabung.")
    else:
        add_log("info", f"📂 Folder Sumber (2026): {source_dir}")
        add_log("info", f"📂 Folder Target (2025): {target_dir}")
    add_log("info", f"📁 Foto Mentah (03): {raw_photos_dir}")
    add_log("info", f"📁 Foto Hasil Edit (04): {edited_photos_dir}")

    # Tentukan folder output akhir untuk step 5
    actual_step5_output = merged_dir
    temp_merge_dir = None
    if mode == "single" and overwrite_original:
        temp_merge_dir = os.path.join(export_root, "_temp_merged")
        os.makedirs(temp_merge_dir, exist_ok=True)
        actual_step5_output = temp_merge_dir

    is_frozen = getattr(sys, 'frozen', False)
    def make_cmd(script_name, script_args):
        if is_frozen:
            return [py_exe, "--run-script", script_name] + script_args
        else:
            return [py_exe, os.path.join(ENGINE_DIR, script_name)] + script_args

    try:
        # STEP 1: Ekstraksi Foto
        if "1" in steps_to_run:
            step_idx += 1
            with _state_lock:
                state["current_step"] = 1
                state["progress"] = int((step_idx - 1) / total_steps * 100)
            cmd = make_cmd("export_pdf_foto.py", [
                "--input", source_dir,
                "--target-dir", target_dir,
                "--output", raw_photos_dir,
                "--sap-mapping", sap_mapping
            ])
            s_pct = (step_idx - 1) / total_steps * 100.0
            e_pct = step_idx / total_steps * 100.0
            ok = run_cmd(cmd, "step1", f"Step 1: Ekstraksi Foto ({'PDF Sumber' if mode == 'single' else 'PDF 2026'})", s_pct, e_pct)
            if not ok:
                return

        # STEP 1.5: Auto-Crop Kolase
        if "1.5" in steps_to_run or "step1_5" in steps_to_run:
            step_idx += 1
            with _state_lock:
                state["current_step"] = 1.5
                state["progress"] = int((step_idx - 1) / total_steps * 100)
            temp_crops_dir = os.path.join(export_root, "03_photos_cropped_temp")
            manifest_file = os.path.join(export_root, "logs", "auto_crop_manifest.json")
            cropped_set_file = os.path.join(export_root, "logs", "cropped_collages.json")
            cmd = make_cmd("auto_crop_collages.py", [
                "--input", raw_photos_dir,
                "--output", temp_crops_dir,
                "--manifest", manifest_file,
                "--cropped-set", cropped_set_file
            ])
            s_pct = (step_idx - 1) / total_steps * 100.0
            e_pct = step_idx / total_steps * 100.0
            ok = run_cmd(cmd, "step1_5", "Step 1.5: Auto-Crop Kolase (White-Seam Isolation)", s_pct, e_pct)
            if not ok:
                return

        # STEP 2: Ekstraksi Tanggal
        if "2" in steps_to_run:
            step_idx += 1
            with _state_lock:
                state["current_step"] = 2
                state["progress"] = int((step_idx - 1) / total_steps * 100)
            cmd = make_cmd("extract_pdf_dates.py", [
                "--pdf-dir", target_dir,
                "--output-dir", raw_photos_dir
            ])
            s_pct = (step_idx - 1) / total_steps * 100.0
            e_pct = step_idx / total_steps * 100.0
            ok = run_cmd(cmd, "step2", f"Step 2: Ekstraksi Tanggal ({'PDF Sumber' if mode == 'single' else 'PDF Target 2025'})", s_pct, e_pct)
            if not ok:
                return

        # STEP 3: Penjadwalan Tim
        if "3" in steps_to_run:
            step_idx += 1
            with _state_lock:
                state["current_step"] = 3
                state["progress"] = int((step_idx - 1) / total_steps * 100)
            cmd = make_cmd("scheduler.py", [
                "--pdf-dir", target_dir,
                "--photos-dir", raw_photos_dir,
                "--mapping", time_mapping,
                "--data-acuan", data_acuan,
                "--output", schedule_file
            ])
            s_pct = (step_idx - 1) / total_steps * 100.0
            e_pct = step_idx / total_steps * 100.0
            ok = run_cmd(cmd, "step3", "Step 3: Penjadwalan Tim & Alokasi Waktu", s_pct, e_pct)
            if not ok:
                return

            # Sinkronisasi schedule.json ke folder target_dir dan raw_photos_dir
            if os.path.isfile(schedule_file):
                for dest_dir in [target_dir, raw_photos_dir]:
                    try:
                        if dest_dir and os.path.isdir(dest_dir):
                            shutil.copy2(schedule_file, os.path.join(dest_dir, "schedule.json"))
                    except Exception:
                        pass

        # STEP 4: Edit Timemark Watermark
        if "4" in steps_to_run and detector != "fast_meta":
            step_idx += 1
            with _state_lock:
                state["current_step"] = 4
                state["progress"] = int((step_idx - 1) / total_steps * 100)
            chosen_detector = detector if detector in ("google_vision", "guide") else "google_vision"
            add_log("info", f"🔍 Detektor Timemark: {'Google Cloud Vision AI' if chosen_detector == 'google_vision' else 'Metode Biasa (HSV Garis Panduan)'}")
            cmd = make_cmd("edit_timemark_ide1.py", [
                "--input", raw_photos_dir,
                "--output", edited_photos_dir,
                "--schedule", schedule_file,
                "--detector", chosen_detector
            ])
            s_pct = (step_idx - 1) / total_steps * 100.0
            e_pct = step_idx / total_steps * 100.0
            ok = run_cmd(cmd, "step4", f"Step 4: Edit Watermark Timemark Foto ({'AI Vision' if chosen_detector == 'google_vision' else 'HSV'})", s_pct, e_pct)
            if not ok:
                return

        # STEP 4 FAST: Fast Update Timemark (Membaca koordinat xPos/yPos dari meta.json tanpa OCR/Vision)
        if "4_fast" in steps_to_run or "step4_fast" in steps_to_run or ("4" in steps_to_run and detector == "fast_meta"):
            step_idx += 1
            with _state_lock:
                state["current_step"] = 4
                state["progress"] = int((step_idx - 1) / total_steps * 100)
            temp_crops_dir = os.path.join(export_root, "03_photos_cropped_temp")
            add_log("info", "⚡ Mode Fast Update Timemark: Mengikuti koordinat (xPos, yPos) dari meta.json tanpa deteksi ulang...")
            cmd = make_cmd("fast_update_timemark.py", [
                "--schedule", schedule_file,
                "--input", raw_photos_dir,
                "--temp", temp_crops_dir,
                "--output", edited_photos_dir,
                "--force"
            ])
            s_pct = (step_idx - 1) / total_steps * 100.0
            e_pct = step_idx / total_steps * 100.0
            step_key = "step4_fast" if ("4_fast" in steps_to_run or "step4_fast" in steps_to_run) else "step4"
            ok = run_cmd(cmd, step_key, "Step 4 (Fast): Fast Update Timemark (Ikuti meta.json)", s_pct, e_pct)
            if not ok:
                return

        # STEP 5: Penggabungan PDF
        if "5" in steps_to_run:
            step_idx += 1
            with _state_lock:
                state["current_step"] = 5
                state["progress"] = int((step_idx - 1) / total_steps * 100)

            # Jika mode timpa berkas aktif, lakukan backup otomatis terlebih dahulu (rekursif)
            if mode == "single" and overwrite_original:
                from pathlib import Path
                ts_str = time.strftime("%Y%m%d_%H%M%S")
                backup_folder = os.path.join(source_dir, "backups", f"backup_{ts_str}")
                os.makedirs(backup_folder, exist_ok=True)
                add_log("info", f"💾 Membuat salinan cadangan otomatis di: {backup_folder}...")
                src_path = Path(source_dir)
                all_pdfs = [
                    p for p in src_path.rglob("*.pdf")
                    if "backups" not in p.parts and "_temp_merged" not in p.parts
                ]
                for p in all_pdfs:
                    try:
                        rel = p.relative_to(src_path)
                        dst = Path(backup_folder) / rel
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(p, dst)
                    except Exception as be:
                        add_log("warn", f"Gagal mencadangkan {p.name}: {be}")
                add_log("success", f"✓ {len(all_pdfs)} berkas PDF berhasil dicadangkan dengan aman.")

            cmd = make_cmd("merge_pdf_foto.py", [
                "--input", target_dir,
                "--photos", edited_photos_dir,
                "--output", actual_step5_output,
                "--schedule", schedule_file
            ])
            s_pct = (step_idx - 1) / total_steps * 100.0
            e_pct = step_idx / total_steps * 100.0
            ok = run_cmd(cmd, "step5", "Step 5: Penggabungan PDF Final A4", s_pct, e_pct)
            if not ok:
                return

            # Jika overwrite aktif, timpa berkas tepat di posisi subfolder asalnya
            if mode == "single" and overwrite_original and temp_merge_dir:
                from pathlib import Path
                add_log("info", f"🔄 Memperbarui berkas di folder sumber: {source_dir}...")
                src_path = Path(source_dir)
                orig_file_map = {
                    p.name.lower(): p for p in src_path.rglob("*.pdf")
                    if "backups" not in p.parts and "_temp_merged" not in p.parts
                }
                merged_pdfs = list(Path(temp_merge_dir).rglob("*.pdf"))
                replaced_count = 0
                for mp in merged_pdfs:
                    dst = orig_file_map.get(mp.name.lower(), src_path / mp.name)
                    try:
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(mp, dst)
                        replaced_count += 1
                    except Exception as re:
                        add_log("warn", f"Gagal menimpa {mp.name}: {re}")
                add_log("success", f"✓ Berhasil menimpa {replaced_count} berkas PDF di posisi subfolder asalnya dengan hasil foto terbaru.")
                try:
                    shutil.rmtree(temp_merge_dir)
                except Exception:
                    pass

        with _state_lock:
            state["progress"] = 100
            state["running"] = False
        add_log("success", "🎉 Seluruh tahapan pipeline berhasil diselesaikan!")

    except Exception as e:
        with _state_lock:
            state["running"] = False
            state["error"] = str(e)
        add_log("error", f"Pipeline terhenti karena galat: {e}")
    finally:
        with _state_lock:
            state["running"] = False

def start_pipeline(source_dir, target_dir=None, export_dir=None, merged_dir=None, selected_steps=None, mode="dual", overwrite_original=False, detector="google_vision"):
    steps_list = selected_steps if isinstance(selected_steps, list) else ["1", "1.5", "2", "3", "4", "5"]

    if mode == "single":
        if not source_dir and target_dir:
            source_dir = target_dir
        target_dir = source_dir
    else:
        # Jika Step 1 tidak dipilih (mis. memakai Stok Foto langsung ke file 2025), source_dir 2026 boleh kosong
        if "1" not in steps_list and (not source_dir or not os.path.isdir(source_dir)):
            source_dir = target_dir or export_dir
        if not any(s in steps_list for s in ("1", "2", "3", "5")) and (not target_dir or not os.path.isdir(target_dir)):
            target_dir = source_dir or export_dir

    if "1" in steps_list and (not source_dir or not os.path.isdir(source_dir)):
        return {"ok": False, "error": f"Folder PDF Sumber tidak valid: {source_dir}"}

    if any(s in steps_list for s in ("2", "3", "5")) and (not target_dir or not os.path.isdir(target_dir)):
        return {"ok": False, "error": f"Folder PDF Target tidak valid: {target_dir}"}

    default_base = os.path.join(os.path.expanduser("~"), "Documents", "Sintelis")
    if not export_dir:
        export_dir = os.path.join(default_base, "03_export_foto")
    if not merged_dir:
        merged_dir = os.path.join(default_base, "05_pdf_merged")

    t = threading.Thread(
        target=_execute_pipeline_task,
        args=(source_dir, target_dir, export_dir, merged_dir, selected_steps, mode, overwrite_original, detector),
        daemon=True
    )
    t.start()
    return {"ok": True, "message": "Pipeline started", "mode": mode, "detector": detector}
