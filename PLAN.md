# Plan: Bug badge "Gagal Ocr" (LaMa AI & Timpa Tanggal)

> Fase 1–2 (mode `timpa_tanggal` + kolase Step 1.5) sudah selesai/ditunda → dipindah ke `PLAN_ARSIP.md`. Dokumen ini = rencana aktif.

## Goal

Hilangkan badge merah `⚠️ Gagal Ocr` yang muncul padahal app tidak crash, dan perbaiki deteksi OCR agar foto bertanggal tidak ikut di-skip.

## Current context / assumptions

- GUI: `Sintelis Utility 2.0 v1.9.0`, tab `Galeri & Edit Foto`.
- Mode UI "LaMa AI (Hapus Teks)" = detector internal `paddle_ocr` (`GalleryPanel.jsx:2289`), bukan `lama_ai`. Timpa Tanggal = `timpa_tanggal`. Keduanya lewat `detect_timemark_via_paddle_ocr` (`edit_timemark_ide1.py:1667`).
- Nomor baris bisa bergeser — selalu `grep -n` dulu.

## Dua kasus (bukti)

| Kasus | Aset | Ukuran | Akar |
|---|---|---|---|
| A — BUG NYATA | `OTB 1 ER TELKOM MASENG` (BTP BD/SERAT OPTIK, `IMO\2026\FOTO\TES`), mode LaMa AI | 3048×3048 | Ambang piksel absolut |
| B — SALAH LABEL | `ZP 24A CLT` (BTP JAK/AXC, `IMO\2025\DONE NEW\FOTO\APRIL`), mode Timpa Tanggal | 300×300 | Foto tanpa tanggal → label merah |

**Kasus A:** meta ketiga foto = `stage_fallback_skipped` + `ocrFailed:true` + `.unedited`. Bongkar OCR mentah → OCR **menemukan** `'Kamis,Nov 12 2026'` conf **1.00**, **tinggi box 95–106px**. Sumber tak punya `0/50/100.txt` (hanya `date.txt`).
**Kasus B:** `0.jpg` `stage_fallback_skipped`+`ocrFailed:true`; `50/100.jpg` sukses `stage_paddle_ocr`. OCR mentah `0.jpg` = tak ada baris tanggal (hanya alamat/koordinat).

## Rantai sebab (terverifikasi)

1. `edit_timemark_ide1.py:1667–1680` — cabang OCR; `p_box is None` → `stage_fallback` + `ocr_failed=True`. **Tanpa sibling-consensus** (kontras `google_vision:1712–1745`).
2. `:1757` cabang skip → `:1783–1785` tulis `stage_fallback_skipped` + `ocrFailed=bool(eff_detector in ("paddle_ocr","lama_ai","timpa_tanggal"))` → selalu `True`.
3. `GalleryPanel.jsx:2750` render badge `:2755`. Tombol `:2518` → `handleProcessTimemark` `:1972` → `POST /api/timemark/process-single` `:1978` (server `run_desktop_webview.py:3072`). Badge kembar `BatchDateEditorPanel.jsx:1856`.
4. `refreshSinglePhotoCard` (`:1383`) tak baca ulang disk, tapi backend kembalikan `final_returned_meta` dari disk (`run_desktop_webview.py:4210–4221`) → `ocrFailed` lama selalu masuk lagi.

## Step-by-step tasks

### Task 14 — Ambang piksel proporsional (`paddle_worker.py`) — ROOT CAUSE Kasus A

File: `01_scripts_pendukung/web-app/timemark_engine/paddle_worker.py`

Ganti semua ambang px-absolut agar skala ke ukuran gambar:
1. `:78` cap tinggi `7 <= (y2-y1) <= 60` → proporsional (mis. `h*0.004 .. h*0.06`).
2. `:67` merge-tolerance `abs(other.y_mid - item.y_mid) <= 7.0` → proporsional (mis. `h*0.02`).
3. `:78` lebar minimum `(x2-x1) >= 20` → proporsional (mis. `w*0.006`).
4. Cek `:40` `scale` (4.0/2.0/1.0): foto 3048 → `scale=1.0` benar; pastikan tak ada ambang bawah lain terlewat.

Verifikasi (satu skrip sekali jalan, jangan `probe_v*.py`):
```bash
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server/01_scripts_pendukung/web-app/timemark_engine"
PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python PYTHONPATH= "C:/Users/dikarm/AppData/Local/Programs/Python/Python311/python.exe" paddle_worker.py "<foto>"
```
Harapan: foto 300px (`ZP 24A CLT/50.jpg`) **dan** 3048px (`OTB 1 ER TELKOM MASENG/0.jpg`) keduanya `{"ok": true, "box": [...]}`.

### Task 15 — Sibling-consensus untuk cabang OCR

File: `01_scripts_pendukung/web-app/timemark_engine/edit_timemark_ide1.py:1667–1680`

Reuse blok `:1712–1745`: sebelum menyerah `stage_fallback`, coba box dari `0/50/100.txt` saudara, lalu `meta.json` saudara. Membuat `ZP 24A CLT/0.jpg` ter-stamp, bukan skip.
**Catatan:** Kasus A tak punya `.txt` saudara → murni Task 14.

Verifikasi: jalankan ulang `ZP 24A CLT` → `0.jpg` stage non-fallback.

### Task 16 — Pisahkan "tak ada tanggal" vs "engine gagal"

File: `edit_timemark_ide1.py:1757–1797` + UI (`GalleryPanel.jsx:2750`, `BatchDateEditorPanel.jsx:1856`)

`ocrFailed` untuk engine error (mis. `stage_paddle_not_found` `:1587`). State benign baru (`noDateFound`) → badge kuning/abu (usul `⏭️ Dilewati (tanpa tanggal)`), bukan merah.

### Task 17 — Bersihkan state basi saat run sukses

File: `edit_timemark_ide1.py:1785` + `run_desktop_webview.py:3072`

Run non-fallback sukses: **hapus** key `ocrFailed` dari entry meta foto itu, **dan hapus** `<nama>.jpg.unedited` bila ada.

### Task 18 — Guard `pdfplumber`

File: `01_scripts_pendukung/web-app/timemark_engine/export_pdf_foto.py:16`

`import pdfplumber` tak terpasang di interpreter yang dites (hanya `build_exe.spec:59`). Jalur CLI input-folder (`edit_timemark_ide1.py:2005`) crash. Jadikan import lazy, atau `try/except` dengan pesan jelas.

### Task 19 — Verifikasi E2E

(a) `OTB 1 ER TELKOM MASENG` (3048px, LaMa AI) → `stage_paddle_ocr`, badge merah hilang.
(b) `ZP 24A CLT` → `0.jpg` ter-stamp via konsensus (atau badge benign).

Wajib:
- **Restart daemon OCR** port **58253** (cache `_ocr` in-memory; patch `paddle_worker.py` tak berlaku sampai restart, ATAU uji subprocess langsung).
- **Paksa render ulang**: `fast_update_timemark.py:270–275` skip foto "sesuai" → `--force`.
- Cek `meta.json` + `ls *.unedited` bersih.

## Tests / validation

Repo tak punya infrastruktur test. Verifikasi = probe end-to-end + build.
- Task 14: `paddle_worker.py` pada 1 foto 300px + 1 foto 3048px → keduanya `ok:true`.
- Task 15–19: jalankan via CLI `--single-out` (hindari jalur folder sampai Task 18 beres), cek `meta.json`, lalu konfirmasi GUI.

## Risks, tradeoffs, open questions

1. **Proporsional bisa lolos-terima noise.** Ambang lebar saat proporsional → teks besar non-tanggal mungkin lolos. Mitigasi: `DATE_RE` + `SKIP_RE` (`paddle_worker.py:15–31`) sudah menyaring; uji regresi pada >20 foto non-kolase.
2. **`ocrFailed` basi dua lapis** (in-memory preserve `:1403` + disk re-read). Task 17 harus hapus di disk; frontend tak perlu diubah.
3. **Daemon 58253** cache model in-memory → verifikasi Task 19 bisa false-negative bila lupa restart.
4. **`fast_update` skip** → verifikasi tanpa `--force` bisa menipu.
5. **Keputusan user belum dikunci:**
   - Task 14: batas proporsional persis (usul `h*0.004..h*0.06`, `h*0.02`, `w*0.006`)? Harus kompatibel 300px.
   - Task 15: prioritas sumber box saudara — `.txt` dulu atau `meta.json` dulu? (google_vision: `.txt` dulu.)
   - Task 16: label/warna benign — usul kuning `⏭️ Dilewati (tanpa tanggal)`.
   - Konfirmasi: apakah mode LaMa AI memang **seharusnya** menimpa tanggal, atau alias ke `paddle_ocr` disengaja?

## Task 11 — Perbaiki `detect_white_seam_collage` (kolase Step 1.5) — DITUNDA / R&D

File: `01_scripts_pendukung/web-app/timemark_engine/auto_crop_collages.py`

**Status: ditunda.** Prototipe pembelahan rekursif sudah dibuat tapi **over-split** (kisi 3×3 → 11 panel, bukan 9). Belum production-ready. Jangan lanjut tanpa instruksi; jangan bikin `probe_v*.py`.

Bukti (3 foto WhatsApp `C:\Users\dikarm\Downloads\WhatsApp Image 2026-11-14 at 12.23.{26,27,272}.jpeg`) — ketiganya kolase, ketiganya dinyatakan `single_photo`:

| Foto | Isi | Garis putih nyata | Hasil kode |
|---|---|---|---|
| `12.23.26` | 8 panel, 2+2+4 | X=799 (49,9%), Y=543 (33,9%), Y=1055 | `single_photo` |
| `12.23.27` | 6 panel | X=1054, Y=1054 (keduanya 65,9%) | `single_photo` |
| `12.23.272` | 9 panel, kisi 3×3 | X=426 (33,3%), X=853 (66,6%), Y=426, Y=853 | `single_photo` |

Tiga akar masalah (terverifikasi `grep -n`):
1. **Zona pindai 45–55% terlalu sempit** — `:79`, `:92`, `:104`. Hanya jendela 10% tengah; garis nyata di 33,3%/66,6% di luar jendela.
2. **Klasifikasi kaku** — `:128-131`. `is_2x2` menuntut `max_v_pct >= 0.80` **dan** `max_h_pct >= 0.80`; `12.23.26` X=100% tapi Y=34,8% → gagal.
3. **Asumsi pembelah di tengah** — `:110-111` (`w//2`, `h//2`, toleransi 12px). Kenyataan: 33,9%/65,9%/33,3%+66,6%.
4. Tambahan: **ambang seam terlalu ketat** — `:69-70` `min_c >= 195`/`>= 175`. Seam terukur `min_c` 173–194, `sat` 7–16 → jatuh di antara dua ambang.

Tiga perubahan minimal (`:69-135`):
1. **Ambang seam** (`:69-70`): `is_white_seam = (sat < 25.0) & (min_c >= 160.0)`; `is_soft_white_seam = (sat < 20.0) & (min_c >= 150.0)`.
2. **Zona pindai** (`:79`,`:92`,`:104`): `range(int(w*0.45), int(w*0.55))` → `range(max(3, int(w*0.05)), int(w*0.95))`. Buang asumsi simetri `:110-111`.
3. **Klasifikasi** (`:128-135`): ganti `is_2x2`/`is_3in1` dengan pembelahan rekursif **setelah** menambah filter ketipisan run (tolak run lebar > ±30px, seam asli selalu tipis — perbaikan yang belum dicoba di prototipe).

Prototipe (arsip, tak disalin ke produksi): `C:\Users\dikarm\AppData\Local\hermes\cache\scratch\collage_recursive.py` — pendekatan: buang jendela 45–55%, pindai profil penuh, belah pada seam terkuat, ulangi rekursif. Bug yang sudah diperbaiki: kandidat seam dekat tepi (bingkai `y=12`) mengalahkan seam asli → saring `c >= MIN_SPLIT` **sebelum** memilih pemenang.

Verifikasi: jalankan pada 3 foto uji, harapan ketiganya **bukan** `single_photo` (panel 8/6/9).
**Regresi wajib:** setelah zona pindai dibuka, foto non-kolase bisa ikut terbelah — uji ≥20 foto dalam `COLLAGE_ELIGIBLE_CATEGORIES` (`:39`) + ≥20 di luar daftar; pastikan `total_collages_cropped` tidak melonjak palsu.

## Task 12 — Perbaiki fallback buta (kolase Step 1.5)

File: `01_scripts_pendukung/web-app/run_desktop_webview.py:4933-4942`

Bila deteksi gagal tapi user minta potong, kode pakai kuadran **`TL`** statis dari pembelahan `w//2, h//2`:
```python
chosen = req_quad if req_quad in quads else "TL"
```
Salah untuk setiap kolase tak simetris. Ganti: pakai **kuadran kiri-atas dari pembelahan hasil rekursif** (panel pertama), bukan `w//2`. Setelah Task 20 jalur ini jarang terpakai, tapi tetap harus benar saat terpakai.
