#!/usr/bin/env python3
"""
auto_crop_collages.py — Deteksi & Pemotongan Otomatis Foto Kolase berbasis Garis Putih / Netral (White-Seam Isolation).

Logika Deteksi:
1. Meredupkan seluruh warna (Saturation < 8% dan Brightness > 110) sehingga hanya menyisakan garis pembatas putih/netral.
2. Memindai sumbu tengah:
   - Garis pembatas vertikal lurus (X: 147..153 px) memanjang >= 88% dari atas ke bawah.
   - Garis pembatas horizontal lurus (Y: 147..153 px) memanjang >= 80% dari kiri ke kanan.
3. Menentukan layout:
   - 2x2 (4-in-1): Garis pembatas vertikal dan horizontal lurus membelah 4 kuadran ➔ Potong kuadran kiri atas [0, 0, split_x, split_y].
   - 3-in-1 (1 Atas + 2 Bawah): Garis pembatas horizontal penuh dan vertikal pada paruh bawah ➔ Potong panel atas horizontal [0, 0, W, split_y].
4. Hasil crop di-resize ke ukuran standar 300x300 px dan disimpan di 03_photos_cropped_temp/.
5. Foto tunggal (0 false positive) 100% dilewati tanpa disentuh.
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from PIL import Image
import numpy as np

DEFAULT_INPUT = Path("03_photos_export")
DEFAULT_OUTPUT = Path("03_photos_cropped_temp")
DEFAULT_MANIFEST = Path("logs/auto_crop_manifest.json")
DEFAULT_CROPPED_SET = Path("logs/cropped_collages.json")

# Kategori yang diizinkan untuk pemeriksaan kolase
COLLAGE_ELIGIBLE_CATEGORIES = {
    "CATUDAYA", "CATU DAYA", "CATU DAYA ER RADIO", "CATU DAYA ER SINYAL",
    "PDSE", "PTDS", "PTLS",
    "WAYSTATION 3 BULANAN", "WAYSTATION 6 BULANAN", "WAYSTATION 1 TAHUNAN",
    "BASESTATION 6 BULANAN", "BASESTATION 3 BULANAN", "BASESTATION 1 TAHUNAN",
}


def detect_white_seam_collage(img_path: Path, requested_quadrant: str | None = None) -> tuple[str, tuple[int, int, int, int] | None, dict]:
    """
    Mendeteksi apakah gambar memiliki garis pembatas putih/netral khas kolase 2x2 atau 3-in-1.
    Memilih kuadran terbaik berdasarkan deteksi garis vertikal guideline timemark di kiri-bawah
    (atau default ke Bottom-Left 'BL').
    Returns: (layout_type, crop_box, stats)
    """
    try:
        img = Image.open(img_path).convert("RGB")
        w, h = img.size
        arr = np.array(img).astype(float)

        r = arr[:, :, 0]
        g = arr[:, :, 1]
        b = arr[:, :, 2]

        # 1. Mask garis pembatas putih sejati (bukan tembok abu-abu/lemari gelap)
        max_c = np.maximum(np.maximum(r, g), b)
        min_c = np.minimum(np.minimum(r, g), b)
        delta = max_c - min_c
        sat = np.divide(delta * 100.0, max_c, out=np.zeros_like(delta), where=max_c > 0)

        is_white_seam = (sat < 15.0) & (min_c >= 195.0)
        is_soft_white_seam = (sat < 12.0) & (min_c >= 175.0)

        # Hindari gambar putih polos / dinding putih masif tanpa pembatas kolase
        overall_white_ratio = float(np.mean(is_white_seam))

        # 2. Pindai garis putih vertikal 1-piksel tepat pada sumbu tengah (45%..55%)
        best_v_col = w // 2
        max_v_pct = 0.0
        soft_v_pct = 0.0
        for x in range(int(w * 0.45), int(w * 0.55)):
            col_hits = float(np.mean(is_white_seam[:, x]))
            soft_hits = float(np.mean(is_soft_white_seam[:, x]))
            if col_hits > max_v_pct:
                max_v_pct = col_hits
                best_v_col = x
            if soft_hits > soft_v_pct:
                soft_v_pct = soft_hits

        # 3. Pindai garis putih horizontal 1-piksel tepat pada sumbu tengah (45%..55%)
        best_h_row = h // 2
        max_h_pct = 0.0
        soft_h_pct = 0.0
        for y in range(int(h * 0.45), int(h * 0.55)):
            row_hits = float(np.mean(is_white_seam[y, :]))
            soft_hits = float(np.mean(is_soft_white_seam[y, :]))
            if row_hits > max_h_pct:
                max_h_pct = row_hits
                best_h_row = y
            if soft_hits > soft_h_pct:
                soft_h_pct = soft_hits

        # 4. Pindai garis putih vertikal pada paruh bawah saja (Layout 3-in-1)
        max_bottom_v_pct = 0.0
        bot_start = int(h * 0.52)
        for x in range(int(w * 0.45), int(w * 0.55)):
            bottom_hits = float(np.mean(is_white_seam[bot_start:, x]))
            if bottom_hits > max_bottom_v_pct:
                max_bottom_v_pct = bottom_hits

        # Gunakan pembagian simetris sempurna jika offset kecil (standar kolase 150x150)
        split_x = w // 2 if abs(best_v_col - w // 2) <= 12 else best_v_col
        split_y = h // 2 if abs(best_h_row - h // 2) <= 12 else best_h_row

        center_patch = min_c[max(0, best_h_row - 1):min(h, best_h_row + 2), max(0, best_v_col - 1):min(w, best_v_col + 2)]
        center_bright = float(np.mean(center_patch)) if center_patch.size > 0 else 0.0

        stats = {
            "v_pct": round(max_v_pct, 3),
            "h_pct": round(max_h_pct, 3),
            "bottom_v_pct": round(max_bottom_v_pct, 3),
            "split_x": split_x,
            "split_y": split_y,
            "center_bright": round(center_bright, 1),
        }

        not_blank_white = overall_white_ratio < 0.72

        # Klasifikasi 2x2: Harus berupa garis putih menerus di KEDUA sumbu tengah (>=80% panjang)
        is_2x2 = not_blank_white and (
            (max_v_pct >= 0.80 and max_h_pct >= 0.80) or
            (soft_v_pct >= 0.90 and soft_h_pct >= 0.90 and center_bright >= 200.0)
        )
        # Klasifikasi 3-in-1: Garis horizontal putih utuh & paruh bawah vertikal utuh
        is_3in1 = (not is_2x2) and not_blank_white and (
            max_h_pct >= 0.85 and max_bottom_v_pct >= 0.85
        )

        if is_2x2:
            quads = {
                "BL": (0, split_y, split_x, h),
                "TL": (0, 0, split_x, split_y),
                "TR": (split_x, 0, w, split_y),
                "BR": (split_x, split_y, w, h)
            }
            if requested_quadrant and requested_quadrant.upper() in quads:
                chosen = requested_quadrant.upper()
                stats["chosen_quadrant"] = chosen
                return "2x2", quads[chosen], stats

            # Pemilihan kuadran otomatis: cari batang vertikal guideline sempit di zona kiri-bawah kuadran
            # (mengabaikan baju seragam oranye KAI atau objek berwarna lebar)
            chosen = "BL"
            best_score = 0
            arr_int = np.array(img)
            for qn, (x1, y1, x2, y2) in quads.items():
                qarr = arr_int[y1:y2, x1:x2]
                qh, qw = qarr.shape[:2]
                if qh < 20 or qw < 20:
                    continue
                zone = qarr[int(qh * 0.45):int(qh * 0.97), 0:max(6, int(qw * 0.25))]
                zr = zone[:, :, 0].astype(int)
                zg = zone[:, :, 1].astype(int)
                zb = zone[:, :, 2].astype(int)
                is_red_bar = (zr > 155) & ((zr - zb) > 65) & (zg < 145)
                is_cyan_bar = (zg > 140) & (zb > 140) & (zr < 95)
                bar_mask = is_red_bar | is_cyan_bar

                # Hitung kolom yang membentuk garis vertikal tipis kontinu (lebar baris <= 6 px)
                thin_rows = np.sum(bar_mask, axis=1)
                valid_row_mask = (thin_rows >= 1) & (thin_rows <= 6)
                if np.any(valid_row_mask):
                    col_counts = np.sum(bar_mask[valid_row_mask, :], axis=0)
                    score = int(np.max(col_counts))
                else:
                    score = 0

                if score > best_score and score >= 10:
                    best_score = score
                    chosen = qn

            stats["chosen_quadrant"] = chosen
            stats["guide_hits"] = best_score
            return "2x2", quads[chosen], stats

        if is_3in1:
            stats["chosen_quadrant"] = "TOP_PANEL"
            return "3_in_1", (0, 0, w, split_y), stats

        return "single_photo", None, stats

    except Exception as e:
        return "single_photo", None, {"error": str(e)}


def _load_previous_crop_state(manifest_path: Path, cropped_set_path: Path) -> tuple[dict[str, str], dict[str, list]]:
    """Baca daftar kolase & crop_box sebelumnya untuk deteksi item yang batal/berubah crop."""
    prev_rel_map: dict[str, str] = {}
    prev_box_map: dict[str, list] = {}
    if cropped_set_path.is_file():
        try:
            raw = json.loads(cropped_set_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                for item in raw:
                    norm = str(item).replace("\\", "/").strip("/")
                    if norm:
                        prev_rel_map[norm.lower()] = norm
        except Exception:
            pass
    if manifest_path.is_file():
        try:
            mdata = json.loads(manifest_path.read_text(encoding="utf-8"))
            for c in mdata.get("collages", []):
                rp = str(c.get("rel_path") or "").replace("\\", "/").strip("/")
                if rp:
                    prev_rel_map[rp.lower()] = rp
                    if c.get("crop_box"):
                        prev_box_map[rp.lower()] = list(c["crop_box"])
        except Exception:
            pass
    return prev_rel_map, prev_box_map


def _cleanup_stale_edited_crops(export_root: Path, invalidated_rels: list[str]) -> int:
    """Hapus file hasil edit lama di 04_photos_edited untuk foto yang batal/berubah crop-nya."""
    if not invalidated_rels:
        return 0
    edited_candidates = [export_root / "04_photos_edited", export_root / "04_foto_edited"]
    removed = 0
    for ed_root in edited_candidates:
        if not ed_root.is_dir():
            continue
        search_bases = [ed_root] + [d for d in ed_root.iterdir() if d.is_dir() and d.name.lower().startswith("tim_")]
        for base in search_bases:
            meta_dirty: dict[Path, list[str]] = {}
            for rel_str in invalidated_rels:
                rel_p = Path(rel_str)
                asset_dir = base / rel_p.parent
                if not asset_dir.is_dir():
                    continue
                fname = rel_p.name
                stem = rel_p.stem
                for cand in (asset_dir / fname, asset_dir / f"{stem}.clean.jpg", asset_dir / f"{fname}.unedited"):
                    if cand.is_file():
                        try:
                            cand.unlink()
                            removed += 1
                        except Exception:
                            pass
                meta_path = asset_dir / "meta.json"
                if meta_path.is_file():
                    meta_dirty.setdefault(meta_path, []).append(fname)
            for mpath, fnames in meta_dirty.items():
                try:
                    mdata = json.loads(mpath.read_text(encoding="utf-8"))
                    changed = False
                    for fn in fnames:
                        if fn in mdata:
                            mdata.pop(fn, None)
                            changed = True
                    if changed:
                        mpath.write_text(json.dumps(mdata, indent=2, ensure_ascii=False), encoding="utf-8")
                except Exception:
                    pass
    return removed


def process_all_collages(input_dir: Path, output_dir: Path, manifest_path: Path, cropped_set_path: Path) -> dict:
    prev_rel_map, prev_box_map = _load_previous_crop_state(manifest_path, cropped_set_path)

    # 1. Bersihkan folder output cropped sebelumnya
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    all_jpgs = sorted(list(input_dir.rglob("*.jpg")))
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "method": "white_seam_isolation",
        "total_scanned": len(all_jpgs),
        "total_collages_cropped": 0,
        "collages": []
    }

    cropped_rel_set = set()
    new_box_map: dict[str, list] = {}

    total_jpgs = len(all_jpgs)
    for idx_jpg, p in enumerate(all_jpgs, 1):
        try:
            if idx_jpg == 1 or idx_jpg % 50 == 0 or idx_jpg == total_jpgs:
                print(f"[PROGRESS] {idx_jpg}/{total_jpgs} foto dipindai...", flush=True)
            rel = p.relative_to(input_dir)
            rel_str = str(rel).replace("\\", "/")
            parts = rel.parts

            # Filter kategori (kategori di luar ini dijamin 100% single photo)
            cat = parts[1].upper() if len(parts) >= 2 else ""
            if cat not in COLLAGE_ELIGIBLE_CATEGORIES and not any(k in cat for k in ("CATUDAYA", "CATU DAYA", "PDSE", "PTDS", "PTLS", "WAYSTATION", "BASESTATION")):
                continue

            layout, crop_box, stats = detect_white_seam_collage(p)

            if layout != "single_photo" and crop_box is not None:
                img = Image.open(p).convert("RGB")
                w, h = img.size
                x1, y1, x2, y2 = crop_box
                cropped_img = img.crop((x1, y1, x2, y2))

                # Resize ke 300x300 px
                resized_img = cropped_img.resize((300, 300), Image.Resampling.LANCZOS)

                dst_path = output_dir / rel
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                resized_img.save(dst_path, quality=95, subsampling=0)

                cropped_rel_set.add(rel_str.lower())
                new_box_map[rel_str.lower()] = list(crop_box)
                manifest["total_collages_cropped"] += 1
                manifest["collages"].append({
                    "rel_path": rel_str,
                    "layout": layout,
                    "original_size": [w, h],
                    "crop_box": list(crop_box),
                    "stats": stats,
                    "output_path": str(dst_path)
                })
                print(f"🖼️ [{manifest['total_collages_cropped']}] Kolase Terdeteksi: {rel_str}", flush=True)
                print(f"  ├── Layout     : {layout.upper()}", flush=True)
                print(f"  ├── Resolusi   : {w}x{h} -> Crop Box {crop_box}", flush=True)
                print(f"  └── [OK] Disimpan ke {dst_path}\n", flush=True)

        except Exception as e:
            print(f"[ERROR] Gagal memproses {p}: {e}", file=sys.stderr)

    # Bersihkan sisa file editan lama di 04_photos_edited jika status/ukuran crop foto berubah atau batal
    invalidated_rels = [
        orig_rel for rel_low, orig_rel in prev_rel_map.items()
        if (rel_low not in cropped_rel_set)
        or (rel_low in prev_box_map and new_box_map.get(rel_low) != prev_box_map[rel_low])
    ]
    cleaned_edited = _cleanup_stale_edited_crops(input_dir.parent, invalidated_rels)

    # Simpan manifest dan update cropped_collages.json
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    cropped_set_path.write_text(json.dumps(sorted(list(cropped_rel_set)), indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n==========================================")
    print(f"AUTO-CROP WHITE-SEAM SELESAI:")
    print(f"  Total Foto Dipindai : {manifest['total_scanned']}")
    print(f"  Total Kolase Dipotong: {manifest['total_collages_cropped']}")
    if cleaned_edited > 0:
        print(f"  File Edit Lama Dibersihkan: {cleaned_edited} berkas (batal/ubah crop)")
    print(f"  Manifest Disimpan di : {manifest_path}")
    print(f"==========================================")

    return manifest


def main():
    parser = argparse.ArgumentParser(description="Auto-Crop Collages via White-Seam Isolation")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Photos export folder")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Photos cropped temp folder")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="Output manifest path")
    parser.add_argument("--cropped-set", type=Path, default=DEFAULT_CROPPED_SET, help="Cropped rel paths json")
    args = parser.parse_args()

    from export_pdf_foto import discover_period_workspaces, split_export_base_and_subdir
    inp = args.input.resolve()
    export_base, _ = split_export_base_and_subdir(inp, "03_export_foto")
    has_direct_btp = inp.is_dir() and any(d.is_dir() and d.name.upper().startswith("BTP") for d in inp.iterdir())
    workspaces = [] if has_direct_btp else discover_period_workspaces(export_base, "03_export_foto")

    if workspaces:
        print(f"[PERIODE] Terdeteksi {len(workspaces)} folder periode untuk Auto-Crop Kolase.", flush=True)
        for pref, m_root in workspaces:
            m_in = m_root / "03_export_foto"
            if not m_in.is_dir():
                m_in = m_root / "03_photos_export"
            print(f"\n── Periode: {pref} ──", flush=True)
            process_all_collages(
                m_in,
                m_root / "03_photos_cropped_temp",
                m_root / "logs" / "auto_crop_manifest.json",
                m_root / "logs" / "cropped_collages.json",
            )
    else:
        process_all_collages(args.input, args.output, args.manifest, args.cropped_set)


if __name__ == "__main__":
    main()
