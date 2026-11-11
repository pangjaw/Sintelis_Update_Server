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
    "active_process": None,
    "revision": 0,
    "last_schedule_path": ""
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
            if "FutureWarning:" in line_str or "DeprecationWarning:" in line_str or "fitz\\__init__.py" in line_str or "fitz/__init__.py" in line_str:
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
                state["revision"] = state.get("revision", 0) + 1
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

def _make_engine_cmd(script_name, script_args):
    py_exe = sys.executable
    if getattr(sys, 'frozen', False):
        return [py_exe, "--run-script", script_name] + script_args
    return [py_exe, os.path.join(ENGINE_DIR, script_name)] + script_args


def _merge_schedule_entries_into_target(unit_sched_file: str, target_sched_file: str, target_dir: str) -> None:
    """Gabungkan entri jadwal per periode ke schedule.json induk di DIR PDF Target."""
    import json
    try:
        with open(unit_sched_file, "r", encoding="utf-8") as uf:
            u_data = json.load(uf)
        new_items = u_data.get("schedules", []) if isinstance(u_data, dict) else []
    except Exception:
        return

    existing_items = []
    if os.path.isfile(target_sched_file):
        try:
            with open(target_sched_file, "r", encoding="utf-8") as tf:
                t_data = json.load(tf)
            existing_items = t_data.get("schedules", []) if isinstance(t_data, dict) else []
        except Exception:
            existing_items = []

    live_pdf_names = set()
    if target_dir and os.path.isdir(target_dir):
        for r, dirs, fns in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d.lower() not in ("backups", "backup", "_temp_merged", "03_export_foto", "03_photos_export", "04_photos_edited", "05_pdf_merged")]
            for fn in fns:
                if fn.lower().endswith(".pdf"):
                    live_pdf_names.add(fn)

    new_files = {it.get("file") for it in new_items if it.get("file")}
    merged = [
        it for it in existing_items
        if it.get("file") not in new_files and (not live_pdf_names or it.get("file") in live_pdf_names)
    ]
    merged.extend(new_items)
    os.makedirs(os.path.dirname(target_sched_file), exist_ok=True)
    with open(target_sched_file, "w", encoding="utf-8") as tf:
        json.dump({"version": 3, "schedules": merged}, tf, indent=2, ensure_ascii=False)


def _run_pipeline_unit(
    steps_to_run,
    source_dir,
    target_dir,
    unit_export_root,
    unit_raw_dir,
    unit_edited_dir,
    unit_merged_out,
    mode,
    overwrite_original,
    detector,
    split_multi_asset,
    include_time,
    custom_schedule_file,
    sap_mapping,
    time_mapping,
    data_acuan,
    period_filter="",
    pct_offset=0.0,
    pct_span=100.0,
):
    """Jalankan rangkaian Step 1..5 untuk satu unit workspace (1 bulan penuh atau seluruh batch 1 bulan)."""
    os.makedirs(unit_raw_dir, exist_ok=True)
    os.makedirs(unit_edited_dir, exist_ok=True)
    os.makedirs(unit_merged_out, exist_ok=True)

    schedule_root_dir = target_dir if (target_dir and os.path.isdir(target_dir)) else unit_export_root
    schedule_file = os.path.join(schedule_root_dir, "schedule.json")
    if custom_schedule_file and os.path.isfile(custom_schedule_file):
        add_log("info", f"📄 Menggunakan berkas jadwal eksternal terpilih: {custom_schedule_file}")
        schedule_file = custom_schedule_file

    total_steps = max(1, len(steps_to_run))
    step_idx = 0
    period_args = ["--period-filter", period_filter] if period_filter else []
    label_prefix = f"[{period_filter}] " if period_filter else ""

    def _pct_range(idx_zero_based):
        s_p = pct_offset + (idx_zero_based / total_steps) * pct_span
        e_p = pct_offset + ((idx_zero_based + 1) / total_steps) * pct_span
        return s_p, e_p

    # STEP 1: Ekstraksi Foto
    if "1" in steps_to_run:
        s_pct, e_pct = _pct_range(step_idx)
        step_idx += 1
        with _state_lock:
            state["current_step"] = 1
            state["progress"] = int(round(s_pct))
        step1_args = [
            "--input", source_dir,
            "--target-dir", target_dir,
            "--output", unit_raw_dir,
            "--log-dir", os.path.join(unit_export_root, "logs"),
            "--sap-mapping", sap_mapping,
        ] + period_args
        if split_multi_asset:
            step1_args.append("--split-multi-asset")
        cmd = _make_engine_cmd("export_pdf_foto.py", step1_args)
        ok = run_cmd(cmd, "step1", f"{label_prefix}Step 1: Ekstraksi Foto ({'PDF Sumber' if mode == 'single' else 'PDF 2026'})", s_pct, e_pct)
        if not ok:
            return False

    # STEP 1.5: Auto-Crop Kolase
    if "1.5" in steps_to_run or "step1_5" in steps_to_run:
        s_pct, e_pct = _pct_range(step_idx)
        step_idx += 1
        with _state_lock:
            state["current_step"] = 1.5
            state["progress"] = int(round(s_pct))
        temp_crops_dir = os.path.join(unit_export_root, "03_photos_cropped_temp")
        manifest_file = os.path.join(unit_export_root, "logs", "auto_crop_manifest.json")
        cropped_set_file = os.path.join(unit_export_root, "logs", "cropped_collages.json")
        cmd = _make_engine_cmd("auto_crop_collages.py", [
            "--input", unit_raw_dir,
            "--output", temp_crops_dir,
            "--manifest", manifest_file,
            "--cropped-set", cropped_set_file,
        ])
        ok = run_cmd(cmd, "step1_5", f"{label_prefix}Step 1.5: Auto-Crop Kolase (White-Seam Isolation)", s_pct, e_pct)
        if not ok:
            return False

    # STEP 2: Ekstraksi Tanggal
    if "2" in steps_to_run:
        s_pct, e_pct = _pct_range(step_idx)
        step_idx += 1
        with _state_lock:
            state["current_step"] = 2
            state["progress"] = int(round(s_pct))
        step2_args = [
            "--pdf-dir", target_dir,
            "--output-dir", unit_raw_dir,
        ] + period_args
        if split_multi_asset:
            step2_args.append("--split-multi-asset")
        cmd = _make_engine_cmd("extract_pdf_dates.py", step2_args)
        ok = run_cmd(cmd, "step2", f"{label_prefix}Step 2: Ekstraksi Tanggal ({'PDF Sumber' if mode == 'single' else 'PDF Target 2025'})", s_pct, e_pct)
        if not ok:
            return False

    # STEP 3: Penjadwalan Tim
    if "3" in steps_to_run:
        s_pct, e_pct = _pct_range(step_idx)
        step_idx += 1
        if custom_schedule_file and os.path.isfile(custom_schedule_file):
            add_log("info", f"⚡ Step 3 dilewati karena menggunakan berkas jadwal eksternal: {os.path.basename(custom_schedule_file)}")
            with _state_lock:
                state["step_statuses"]["step3"] = "done"
                state["progress"] = int(round(e_pct))
        else:
            with _state_lock:
                state["current_step"] = 3
                state["progress"] = int(round(s_pct))
            tmp_sched_out = schedule_file
            if period_filter:
                os.makedirs(os.path.join(unit_export_root, "logs"), exist_ok=True)
                tmp_sched_out = os.path.join(unit_export_root, "logs", "_tmp_unit_schedule.json")
            step3_args = [
                "--pdf-dir", target_dir,
                "--photos-dir", unit_raw_dir,
                "--mapping", time_mapping,
                "--data-acuan", data_acuan,
                "--output", tmp_sched_out,
            ] + period_args
            if split_multi_asset:
                step3_args.append("--split-multi-asset")
            cmd = _make_engine_cmd("scheduler.py", step3_args)
            ok = run_cmd(cmd, "step3", f"{label_prefix}Step 3: Penjadwalan Tim & Alokasi Waktu", s_pct, e_pct)
            if not ok:
                return False
            if period_filter and os.path.isfile(tmp_sched_out):
                _merge_schedule_entries_into_target(tmp_sched_out, schedule_file, target_dir)
                try:
                    os.remove(tmp_sched_out)
                except Exception:
                    pass

        if os.path.isfile(schedule_file):
            with _state_lock:
                state["last_schedule_path"] = schedule_file

    # STEP 4: Edit Timemark Watermark
    if "4" in steps_to_run and detector != "fast_meta":
        s_pct, e_pct = _pct_range(step_idx)
        step_idx += 1
        with _state_lock:
            state["current_step"] = 4
            state["progress"] = int(round(s_pct))
        chosen_detector = detector if detector in ("paddle_ocr", "lama_ai", "google_vision", "guide") else "paddle_ocr"
        det_label = 'LaMa AI (Hapus Teks)' if chosen_detector in ('paddle_ocr', 'lama_ai') else ('Google Cloud Vision AI' if chosen_detector == 'google_vision' else 'Metode Biasa (HSV Garis Panduan)')
        add_log("info", f"🔍 Detektor Timemark: {det_label}")
        step4_args = [
            "--input", unit_raw_dir,
            "--output", unit_edited_dir,
            "--schedule", schedule_file,
            "--detector", chosen_detector,
        ]
        if not include_time:
            step4_args.append("--no-time")
        cmd = _make_engine_cmd("edit_timemark_ide1.py", step4_args)
        det_short = 'LaMa AI' if chosen_detector in ('paddle_ocr', 'lama_ai') else ('AI Vision' if chosen_detector == 'google_vision' else 'HSV')
        ok = run_cmd(cmd, "step4", f"{label_prefix}Step 4: Edit Watermark Timemark Foto ({det_short})", s_pct, e_pct)
        if not ok:
            return False

    # STEP 4 FAST: Fast Update Timemark
    if "4_fast" in steps_to_run or "step4_fast" in steps_to_run or ("4" in steps_to_run and detector == "fast_meta"):
        s_pct, e_pct = _pct_range(step_idx)
        step_idx += 1
        with _state_lock:
            state["current_step"] = 4
            state["progress"] = int(round(s_pct))
        temp_crops_dir = os.path.join(unit_export_root, "03_photos_cropped_temp")
        add_log("info", "⚡ Mode Fast Update Timemark: Mengikuti koordinat (xPos, yPos) dari meta.json tanpa deteksi ulang...")
        fast_args = [
            "--schedule", schedule_file,
            "--input", unit_raw_dir,
            "--temp", temp_crops_dir,
            "--output", unit_edited_dir,
            "--force",
        ]
        if not include_time:
            fast_args.append("--no-time")
        cmd = _make_engine_cmd("fast_update_timemark.py", fast_args)
        step_key = "step4_fast" if ("4_fast" in steps_to_run or "step4_fast" in steps_to_run) else "step4"
        ok = run_cmd(cmd, step_key, f"{label_prefix}Step 4 (Fast): Fast Update Timemark (Ikuti meta.json)", s_pct, e_pct)
        if not ok:
            return False

    # STEP 5: Penggabungan PDF
    if "5" in steps_to_run:
        s_pct, e_pct = _pct_range(step_idx)
        step_idx += 1
        with _state_lock:
            state["current_step"] = 5
            state["progress"] = int(round(s_pct))

        step5_args = [
            "--input", target_dir,
            "--photos", unit_edited_dir,
            "--output", unit_merged_out,
            "--schedule", schedule_file,
        ] + period_args
        if split_multi_asset:
            step5_args.append("--split-multi-asset")
        cmd = _make_engine_cmd("merge_pdf_foto.py", step5_args)
        ok = run_cmd(cmd, "step5", f"{label_prefix}Step 5: Penggabungan PDF Final A4", s_pct, e_pct)
        if not ok:
            return False

    return True


def _execute_pipeline_task(source_dir, target_dir, export_dir, merged_dir, selected_steps, mode="dual", overwrite_original=False, detector="paddle_ocr", split_multi_asset=False, include_time=True, custom_schedule_file=None):
    from pathlib import Path
    with _state_lock:
        state["running"] = True
        state["cancelled"] = False
        state["error"] = None
        state["last_schedule_path"] = ""
        state["logs"].clear()
        state["progress"] = 0
        for k in state["step_statuses"]:
            state["step_statuses"][k] = "pending"

    export_norm = os.path.normpath(export_dir)
    bname = os.path.basename(export_norm).lower()
    if bname in ("03_export_foto", "03_photos_export"):
        raw_subdir = os.path.basename(export_norm)
        export_root = os.path.dirname(export_norm)
    elif bname in ("04_photos_edited", "04_foto_edited"):
        export_root = os.path.dirname(export_norm)
        raw_subdir = "03_export_foto"
    else:
        export_root = export_norm
        if os.path.isdir(os.path.join(export_root, "03_photos_export")) and not os.path.isdir(os.path.join(export_root, "03_export_foto")):
            raw_subdir = "03_photos_export"
        else:
            raw_subdir = "03_export_foto"

    raw_photos_dir = os.path.join(export_root, raw_subdir)
    edited_photos_dir = os.path.join(export_root, "04_photos_edited")
    sap_mapping = os.path.join(ENGINE_DIR, "sap_station_mapping.json")
    time_mapping = os.path.join(ENGINE_DIR, "asset_waktu_mapping.json")
    data_acuan = os.path.join(ENGINE_DIR, "data_acuan_tenaga_gabungan.json")
    steps_to_run = selected_steps if isinstance(selected_steps, list) else ["1", "1.5", "2", "3", "4", "5"]

    mode_label = "Mode 1 Folder Sumber" if mode == "single" else "Mode 2 Folder Sumber (Klasik)"
    add_log("info", f"📌 Menjalankan pipeline dalam {mode_label}...")
    if mode == "single":
        add_log("info", f"📂 Folder Dokumen Tunggal: {source_dir}")
        if overwrite_original:
            add_log("warn", "⚠️ Mode Timpa Asli aktif: Berkas asli akan dicadangkan ke subfolder backups/ sebelum digabung.")
    else:
        add_log("info", f"📂 Folder Sumber (2026): {source_dir}")
        add_log("info", f"📂 Folder Target (2025): {target_dir}")
    add_log("info", f"📁 Root Foto (03/04): {export_root}")

    try:
        from export_pdf_foto import resolve_pdf_period_map, list_pdf_files, discover_period_workspaces
    except ImportError:
        from timemark_engine.export_pdf_foto import resolve_pdf_period_map, list_pdf_files, discover_period_workspaces

    # Deteksi apakah batch berasal dari banyak bulan / lintas tahun
    src_pdfs = list_pdf_files(Path(source_dir)) if (source_dir and os.path.isdir(source_dir) and "1" in steps_to_run) else []
    tgt_pdfs = list_pdf_files(Path(target_dir)) if (target_dir and os.path.isdir(target_dir) and any(s in steps_to_run for s in ("2", "3", "5"))) else []
    src_map, src_multi, src_cross = resolve_pdf_period_map(src_pdfs) if src_pdfs else ({}, False, False)
    tgt_map, tgt_multi, tgt_cross = resolve_pdf_period_map(tgt_pdfs) if tgt_pdfs else ({}, False, False)

    # Backup 1x di awal jika mode overwrite_original
    temp_merge_dir = None
    actual_step5_output = merged_dir
    if mode == "single" and overwrite_original and "5" in steps_to_run:
        temp_merge_dir = os.path.join(export_root, "_temp_merged")
        if os.path.exists(temp_merge_dir):
            try:
                shutil.rmtree(temp_merge_dir)
            except Exception:
                pass
        os.makedirs(temp_merge_dir, exist_ok=True)
        actual_step5_output = temp_merge_dir

        ts_str = time.strftime("%Y%m%d_%H%M%S")
        backup_folder = os.path.join(source_dir, "backups", f"backup_{ts_str}")
        os.makedirs(backup_folder, exist_ok=True)
        add_log("info", f"💾 Membuat salinan cadangan otomatis di: {backup_folder}...")
        src_path = Path(source_dir)
        all_pdfs = [
            p for p in src_path.rglob("*.pdf")
            if not any(part.lower() in ("backups", "backup", "_temp_merged") for part in p.relative_to(src_path).parts[:-1])
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
    elif "5" in steps_to_run:
        os.makedirs(merged_dir, exist_ok=True)

    try:
        has_custom_sched = bool(custom_schedule_file and os.path.isfile(custom_schedule_file))
        existing_workspaces = [] if has_custom_sched else discover_period_workspaces(Path(export_root), raw_subdir)
        has_direct_btp = os.path.isdir(raw_photos_dir) and any(
            os.path.isdir(os.path.join(raw_photos_dir, d)) and d.upper().startswith("BTP")
            for d in os.listdir(raw_photos_dir)
        )

        # Jika tidak ada Step PDF (misal Step 1.5 / 4 saja), gunakan workspace periode yang sudah ada jika terstruktur per bulan
        pdf_only_periods = sorted({pr for pr in (list(src_map.values()) + list(tgt_map.values())) if pr})
        use_multi_period = (not has_custom_sched) and (
            src_multi or tgt_multi or (not has_direct_btp and bool(existing_workspaces))
        )

        if use_multi_period and (pdf_only_periods or existing_workspaces):
            src_prefs = sorted({pr for pr in src_map.values() if pr})
            tgt_prefs = sorted({pr for pr in tgt_map.values() if pr})

            if not src_prefs and not tgt_prefs:
                unit_prefs = [pr for pr, _ in existing_workspaces]
                kind_msg = "Tahun/Bulan" if any("/" in pr for pr in unit_prefs) else "Per Bulan"
                add_log("info", f"📅 Menjalankan pemrosesan folder periode ({kind_msg}): {', '.join(unit_prefs)}")
                for idx_u, pref in enumerate(unit_prefs):
                    m_root = os.path.join(export_root, pref)
                    ok = _run_pipeline_unit(
                        steps_to_run, source_dir, target_dir,
                        m_root, os.path.join(m_root, raw_subdir), os.path.join(m_root, "04_photos_edited"),
                        os.path.join(actual_step5_output, pref),
                        mode, overwrite_original, detector, split_multi_asset, include_time, None,
                        sap_mapping, time_mapping, data_acuan,
                        period_filter=pref,
                        pct_offset=(idx_u / len(unit_prefs)) * 100.0,
                        pct_span=100.0 / len(unit_prefs),
                    )
                    if not ok:
                        return
            elif src_prefs and tgt_prefs and src_prefs != tgt_prefs:
                # Dual mode lintas periode berbeda antara Sumber (Step 1) dan Target (Step 1.5-5)
                add_log("info", f"📅 Mode Lintas Periode: Step 1 -> [{', '.join(src_prefs)}], Step 1.5-5 -> [{', '.join(tgt_prefs)}]")
                total_units = len(src_prefs) + len(tgt_prefs)
                other_steps = [s for s in steps_to_run if s != "1"]
                for idx_u, pref in enumerate(src_prefs):
                    m_root = os.path.join(export_root, pref)
                    ok = _run_pipeline_unit(
                        ["1"], source_dir, target_dir,
                        m_root, os.path.join(m_root, raw_subdir), os.path.join(m_root, "04_photos_edited"),
                        os.path.join(actual_step5_output, pref),
                        mode, overwrite_original, detector, split_multi_asset, include_time, None,
                        sap_mapping, time_mapping, data_acuan,
                        period_filter=pref,
                        pct_offset=(idx_u / total_units) * 100.0,
                        pct_span=100.0 / total_units,
                    )
                    if not ok:
                        return
                if other_steps:
                    for idx_t, pref in enumerate(tgt_prefs):
                        m_root = os.path.join(export_root, pref)
                        ok = _run_pipeline_unit(
                            other_steps, source_dir, target_dir,
                            m_root, os.path.join(m_root, raw_subdir), os.path.join(m_root, "04_photos_edited"),
                            os.path.join(actual_step5_output, pref),
                            mode, overwrite_original, detector, split_multi_asset, include_time, None,
                            sap_mapping, time_mapping, data_acuan,
                            period_filter=pref,
                            pct_offset=((len(src_prefs) + idx_t) / total_units) * 100.0,
                            pct_span=100.0 / total_units,
                        )
                        if not ok:
                            return
            else:
                unit_prefs = pdf_only_periods or [pr for pr, _ in existing_workspaces]
                is_cross = src_cross or tgt_cross or any("/" in pr for pr in unit_prefs)
                add_log("info", f"📅 Terdeteksi banyak tanggal ({'Tahun -> Bulan' if is_cross else 'Per Bulan'}): {', '.join(unit_prefs)}")
                for idx_u, pref in enumerate(unit_prefs):
                    m_root = os.path.join(export_root, pref)
                    ok = _run_pipeline_unit(
                        steps_to_run, source_dir, target_dir,
                        m_root, os.path.join(m_root, raw_subdir), os.path.join(m_root, "04_photos_edited"),
                        os.path.join(actual_step5_output, pref),
                        mode, overwrite_original, detector, split_multi_asset, include_time, None,
                        sap_mapping, time_mapping, data_acuan,
                        period_filter=pref,
                        pct_offset=(idx_u / len(unit_prefs)) * 100.0,
                        pct_span=100.0 / len(unit_prefs),
                    )
                    if not ok:
                        return
        else:
            ok = _run_pipeline_unit(
                steps_to_run, source_dir, target_dir,
                export_root, raw_photos_dir, edited_photos_dir,
                actual_step5_output,
                mode, overwrite_original, detector, split_multi_asset, include_time, custom_schedule_file,
                sap_mapping, time_mapping, data_acuan,
                period_filter="",
                pct_offset=0.0,
                pct_span=100.0,
            )
            if not ok:
                return

        if mode == "single" and overwrite_original and temp_merge_dir and "5" in steps_to_run:
            add_log("info", f"🔄 Memperbarui berkas di folder sumber: {source_dir}...")
            src_path = Path(source_dir)
            orig_file_map = {
                p.name.lower(): p for p in src_path.rglob("*.pdf")
                if "backups" not in p.parts and "_temp_merged" not in p.parts
            }
            merged_pdfs = list(Path(temp_merge_dir).rglob("*.pdf"))
            replaced_count = 0
            for mp in merged_pdfs:
                dst = orig_file_map.get(mp.name.lower())
                if not dst:
                    continue
                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(mp, dst)
                    replaced_count += 1
                except Exception as re_err:
                    add_log("warn", f"Gagal menimpa {mp.name}: {re_err}")
            add_log("success", f"✓ Berhasil menimpa {replaced_count} berkas PDF di posisi subfolder asalnya dengan hasil foto terbaru.")
            try:
                shutil.rmtree(temp_merge_dir)
            except Exception:
                pass

        with _state_lock:
            state["progress"] = 100
            state["running"] = False
            state["revision"] = state.get("revision", 0) + 1
        add_log("success", "🎉 Seluruh tahapan pipeline berhasil diselesaikan!")

    except Exception as e:
        with _state_lock:
            state["running"] = False
            state["error"] = str(e)
        add_log("error", f"Pipeline terhenti karena galat: {e}")
    finally:
        with _state_lock:
            state["running"] = False

def start_pipeline(source_dir, target_dir=None, export_dir=None, merged_dir=None, selected_steps=None, mode="dual", overwrite_original=False, detector="paddle_ocr", split_multi_asset=False, include_time=True, custom_schedule_file=None):
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
        args=(source_dir, target_dir, export_dir, merged_dir, selected_steps, mode, overwrite_original, detector, split_multi_asset, include_time, custom_schedule_file),
        daemon=True
    )
    t.start()
    return {"ok": True, "message": "Pipeline started", "mode": mode, "detector": detector}
