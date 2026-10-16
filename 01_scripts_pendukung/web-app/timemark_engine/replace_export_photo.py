"""scripts/replace_export_photo.py — Ganti foto hasil export (Folder 3) dan auto-reprocess timemark.

Mendukung 2 mode aksi:
1. --replace: Mengganti file foto di 03_photos_export dengan gambar baru.
             Menyimpan backup {stem}.original_backup.jpg jika belum ada.
             Mengonversi format ke RGB JPEG standar.
             Menjalankan auto Step 4 pada folder aset tersebut.
2. --revert:  Memulihkan foto di 03_photos_export dari {stem}.original_backup.jpg,
             menghapus file backup, dan menjalankan auto Step 4 ulang.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from PIL import Image

APP_DIR = Path(__file__).resolve().parent.parent
PHOTOS_EXPORT = APP_DIR / "03_photos_export"
PHOTOS_CROPPED = APP_DIR / "03_photos_cropped_temp"
SCHEDULE_PATH = APP_DIR / "schedule.json"


def get_backup_path(target_path: Path) -> Path:
    """Return path for the original backup of the photo."""
    return target_path.parent / f"{target_path.stem}.original_backup.jpg"


def run_step4_auto(rel_path: str, mode: str, detector: str = "google_vision"):
    """Run the appropriate Step 4 script for the specific photo / folder."""
    norm_rel = rel_path.replace("\\", "/")
    folder_rel = str(Path(norm_rel).parent).replace("\\", "/")
    folder_abs = PHOTOS_EXPORT / folder_rel
    file_abs = PHOTOS_EXPORT / norm_rel

    engine_dir = Path(__file__).resolve().parent
    if mode == "jam":
        script = engine_dir / "edit_photo_time_only.py"
        if not script.exists():
            script = APP_DIR / "scripts" / "edit_photo_time_only.py"
        cmd = [sys.executable, "--run-script", str(script), "--input", norm_rel]
    elif mode == "koordinat":
        script = engine_dir / "edit_photo_coordinate_only.py"
        if not script.exists():
            script = APP_DIR / "scripts" / "edit_photo_coordinate_only.py"
        cmd = [sys.executable, "--run-script", str(script), "--input", norm_rel]
    else:
        # Default: mode tanggal (edit_timemark_ide1.py)
        script = engine_dir / "edit_timemark_ide1.py"
        if not script.exists():
            script = APP_DIR / "scripts" / "edit_timemark_ide1.py"
        cmd = [sys.executable, "--run-script", str(script), "--input", str(folder_abs)]
        if detector == "google_vision":
            cmd.extend(["--detector", "google_vision"])
        elif detector == "guide":
            cmd.extend(["--detector", "guide"])
        if SCHEDULE_PATH.exists():
            cmd.extend(["--schedule", str(SCHEDULE_PATH)])

    res = subprocess.run(
        cmd, cwd=str(APP_DIR), capture_output=True, text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    )
    return res.returncode == 0, res.stdout, res.stderr


def replace_photo(rel_path: str, new_image_path: str, mode: str, detector: str = "google_vision") -> dict:
    norm_rel = rel_path.replace("\\", "/")
    target_path = PHOTOS_EXPORT / norm_rel

    if not target_path.exists():
        return {"success": False, "error": f"Target photo not found: {target_path}"}

    backup_path = get_backup_path(target_path)
    backup_created = False
    # Only create backup if not already present, so we always keep the FIRST original
    if not backup_path.exists():
        shutil.copy2(target_path, backup_path)
        backup_created = True

    # Convert and write new image as RGB JPEG
    try:
        with Image.open(new_image_path) as img:
            rgb_img = img.convert("RGB")
            rgb_img.save(target_path, "JPEG", quality=95)
    except Exception as exc:
        return {"success": False, "error": f"Failed to process image: {exc}"}

    # Clear cropped cache if exists so it doesn't override the new photo
    cropped_target = PHOTOS_CROPPED / norm_rel
    if cropped_target.exists():
        try:
            cropped_target.unlink()
        except Exception:
            pass

    # Auto Step 4
    reprocessed, stdout, stderr = run_step4_auto(norm_rel, mode, detector)

    return {
        "success": True,
        "backupCreated": backup_created,
        "backupPath": str(backup_path),
        "reprocessed": reprocessed,
        "stdout": stdout[-400:] if stdout else "",
        "stderr": stderr[-200:] if stderr else "",
    }


def revert_photo(rel_path: str, mode: str, detector: str = "google_vision") -> dict:
    norm_rel = rel_path.replace("\\", "/")
    target_path = PHOTOS_EXPORT / norm_rel
    backup_path = get_backup_path(target_path)

    if not backup_path.exists():
        return {"success": False, "error": f"Original backup not found: {backup_path}"}

    # Restore original photo
    shutil.copy2(backup_path, target_path)
    try:
        backup_path.unlink()
    except Exception:
        pass

    # Clear cropped cache if any
    cropped_target = PHOTOS_CROPPED / norm_rel
    if cropped_target.exists():
        try:
            cropped_target.unlink()
        except Exception:
            pass

    # Auto Step 4 reprocess
    reprocessed, stdout, stderr = run_step4_auto(norm_rel, mode, detector)

    return {
        "success": True,
        "reverted": True,
        "reprocessed": reprocessed,
        "stdout": stdout[-400:] if stdout else "",
        "stderr": stderr[-200:] if stderr else "",
    }


def swap_photos(source_rel: str, target_rel: str, mode: str, detector: str = "google_vision") -> dict:
    norm_source = source_rel.replace("\\", "/")
    norm_target = target_rel.replace("\\", "/")

    source_path = PHOTOS_EXPORT / norm_source
    target_path = PHOTOS_EXPORT / norm_target

    if not source_path.exists():
        return {"success": False, "error": f"Source photo not found: {source_path}"}
    if not target_path.exists():
        return {"success": False, "error": f"Target photo not found: {target_path}"}

    # Backup both before swapping if not already present
    for p in [source_path, target_path]:
        b = get_backup_path(p)
        if not b.exists():
            try:
                shutil.copy2(p, b)
            except Exception:
                pass

    # Swap files safely using temp name in target directory
    temp_swap = target_path.parent / f"{target_path.stem}.swap_tmp_{os.getpid()}.jpg"
    try:
        shutil.move(source_path, temp_swap)
        shutil.move(target_path, source_path)
        shutil.move(temp_swap, target_path)
    except Exception as exc:
        if temp_swap.exists():
            try:
                shutil.move(temp_swap, source_path)
            except Exception:
                pass
        return {"success": False, "error": f"Failed to swap files: {exc}"}

    # Clear cropped cache for both photos
    for rel in [norm_source, norm_target]:
        c = PHOTOS_CROPPED / rel
        if c.exists():
            try:
                c.unlink()
            except Exception:
                pass

    # Clean meta.json in 04_photos_edited for swapped items so Step 4 evaluates fresh timemarks
    for tim_dir in (APP_DIR / "04_photos_edited").glob("Tim_*"):
        for rel in [norm_source, norm_target]:
            meta_file = tim_dir / Path(rel).parent / "meta.json"
            if meta_file.exists():
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        meta_data = json.load(f)
                    fname = Path(rel).name
                    if fname in meta_data:
                        del meta_data[fname]
                        with open(meta_file, "w", encoding="utf-8") as f:
                            json.dump(meta_data, f, indent=2)
                except Exception:
                    pass

    # Run Step 4 auto
    source_folder = str(Path(norm_source).parent).replace("\\", "/")
    target_folder = str(Path(norm_target).parent).replace("\\", "/")

    reprocessed = []
    if mode in ["jam", "koordinat"]:
        r1, out1, err1 = run_step4_auto(norm_source, mode, detector)
        r2, out2, err2 = run_step4_auto(norm_target, mode, detector)
        reprocessed.append({"target": norm_source, "success": r1})
        reprocessed.append({"target": norm_target, "success": r2})
        stdout_combined = (out1 or "") + "\n" + (out2 or "")
        stderr_combined = (err1 or "") + "\n" + (err2 or "")
    else:
        r1, out1, err1 = run_step4_auto(norm_source, mode, detector)
        reprocessed.append({"folder": source_folder, "success": r1})
        stdout_combined = out1 or ""
        stderr_combined = err1 or ""
        if target_folder != source_folder:
            r2, out2, err2 = run_step4_auto(norm_target, mode, detector)
            reprocessed.append({"folder": target_folder, "success": r2})
            stdout_combined += "\n" + (out2 or "")
            stderr_combined += "\n" + (err2 or "")

    return {
        "success": True,
        "swapped": [norm_source, norm_target],
        "reprocessed": reprocessed,
        "stdout": stdout_combined[-400:] if stdout_combined else "",
        "stderr": stderr_combined[-200:] if stderr_combined else "",
    }


def main():
    parser = argparse.ArgumentParser(description="Replace, revert, or swap export photos in 03_photos_export")
    parser.add_argument("--action", choices=["replace", "revert", "swap"], required=True, help="Action to perform")
    parser.add_argument("--target", required=True, help="Target relative path in 03_photos_export (e.g. BTP JAK/PTLS/BOO/0.jpg)")
    parser.add_argument("--source", help="Source relative path in 03_photos_export (required for swap)")
    parser.add_argument("--image", help="Path to new image file (required for replace)")
    parser.add_argument("--mode", default="tanggal", choices=["tanggal", "jam", "koordinat"], help="Active pipeline mode")
    parser.add_argument("--detector", default="google_vision", choices=["guide", "google_vision"], help="Timemark detector to use")

    args = parser.parse_args()

    if args.action == "replace":
        if not args.image:
            print(json.dumps({"success": False, "error": "--image is required for replace action"}))
            sys.exit(1)
        res = replace_photo(args.target, args.image, args.mode, args.detector)
    elif args.action == "swap":
        if not args.source:
            print(json.dumps({"success": False, "error": "--source is required for swap action"}))
            sys.exit(1)
        res = swap_photos(args.source, args.target, args.mode, args.detector)
    else:
        res = revert_photo(args.target, args.mode, args.detector)

    print(json.dumps(res))
    sys.exit(0 if res.get("success") else 1)


if __name__ == "__main__":
    main()

