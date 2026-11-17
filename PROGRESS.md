# PROGRESS — urutan & status task

Rencana padat perbaikan ada di `PLAN.md` (Task 11–19). Saat eksekusi, baca `PROGRESS.md` ini dan **HANYA** bagian task aktif di `PLAN.md` — dilarang memuat seluruh `PLAN.md` (~144 baris). Riwayat Fase 1–2 lama: `PLAN_ARSIP.md` (1027 baris, jangan dibuka kecuali perlu konteks Task 11).

## FOLDER KERJA (absolut — pakai ini, jangan cari ulang)

- **Repo (workdir)**: `D:\02. Sintelis\UPT Resor Sintelis 1.21 Bogor\Server\Sintelis_Update_Server`
- **Web app root** (cd ke sini sebelum jalankan CLI): `…\Sintelis_Update_Server\01_scripts_pendukung\web-app`
- **Interpreter Python** (wajib, 3.11): `C:\Users\dikarm\AppData\Local\Programs\Python\Python311\python.exe`
- **Data uji A (300px)**: `…\Server\IMO\2025\DONE NEW\FOTO\APRIL` (aset `BTP JAK/AXC/ZP 24A CLT`)
- **Data uji B (3048px)**: `…\Server\IMO\2026\FOTO\TES` (aset `BTP BD/SERAT OPTIK/OTB 1 ER TELKOM MASENG`)
- **Docs**: `AGENTS.md` (pintu masuk repo, wajib patuh §1–3), `.hermes/plans/` (arsip plan sesi lama).

## ATURAN EKSEKUSI (hemat context — lihat AGENTS.md §1–3)

- Kerjakan **1 task per giliran**, urut dari bawah. Jangan semua sekaligus.
- Tiap giliran: baca HANYA task aktif di `PLAN.md` → edit 1 file → verifikasi (`python -m py_compile` / `npm run build`) → tampilkan `git diff --stat` → update status di sini → berhenti.
- Jangan baca file besar utuh (`grep`/`read_file` rentang sempit). Jangan bikin `probe_v*.py`.
- Dilarang auto-build (`build_and_deploy.bat`, `build_release.py`, `pyinstaller`) — AGENTS.md §3.

## CARA JALANKAN (terverifikasi)

- Wrapper WAJIB: `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python PYTHONPATH= "<PY311>" timemark_engine/edit_timemark_ide1.py ...`
- Detektor valid: `paddle_ocr` (= UI "LaMa AI"), `timpa_tanggal`, `google_vision`; `lama_ai` alias.
- `--input <FILE> --single-out <FILE>` → aman. `--input <FOLDER>` → crash `pdfplumber` (Task 18).
- Daemon OCR resident port **58253** (aktif saat app jalan; cache `_ocr` → restart app bila patch `paddle_worker.py`).
- `fast_update_timemark.py:270–275` skip foto "sesuai" → pakai `--force` untuk render ulang.

---

## FASE 1 — mode `timpa_tanggal` (Task 1–10) — SELESAI

- [x] Task 1–10 selesai (PLAN.md Fase 1). Semua `py_compile`/`npm run build` lulus.

## FASE 2 — kolase Step 1.5 (Task 11–13)

Detail ada di `PLAN.md` (Task 11 & 12).

- [~] **Task 11** — seam `auto_crop_collages.detect_white_seam_collage` (`:69–135`): **DITUNDA / R&D**. Prototipe rekursif over-split; belum production-ready. Jangan lanjut tanpa instruksi. Jangan buat `probe_v*.py`. `auto_crop_collages.py` tetap dipakai (`pipeline_runner.py:301`, `run_desktop_webview.py:4921`) — jangan dihapus.
- [ ] **Task 12** — fallback `TL` statis → panel pertama hasil rekursif (`run_desktop_webview.py:4933–4942`). Belum.
- [x] **Task 13** — hapus `crop_single_temp.py`, `scan_collages_helper.py`, `crop_collage_photos.py` + hiddenimports `build_exe.spec`. Selesai.

## FASE 3 — bug badge "Gagal Ocr" (temuan 2026-11-16) — Task 14 selesai

Detail ada di `PLAN.md` (Task 14–19).

- [ ] **Task 14** — ambang piksel proporsional di `paddle_worker.py` (`:67`, `:78`). **ROOT CAUSE Kasus A** (foto 3048px). Prioritas tertinggi.
- [ ] **Task 15** — sibling-consensus untuk cabang OCR (`edit_timemark_ide1.py:1667–1680`).
- [ ] **Task 16** — pisah "tak ada tanggal" (benign) vs "engine gagal" (`:1757–1797` + UI badge).
- [ ] **Task 17** — hapus key `ocrFailed` + file `.unedited` basi saat run sukses.
- [ ] **Task 18** — guard `import pdfplumber` (`export_pdf_foto.py:16`).
- [x] **Task 19** — verifikasi E2E (restart daemon 58253 + `--force`). **SELESAI.**

**Blocker cleared:** batas proporsional (`h*0.004..h*0.06`, `h*0.02`, `w*0.006`), prioritas `.txt` dulu lalu `meta.json` (Task 15), label benign `⏭️ Dilewati (tanpa tanggal)` (Task 16), `ocrFailed` dibersihkan saat sukses (Task 17), LaMa AI alias `paddle_ocr` disengaja.

**Fase 3 selesai.** Kasus A & B: `ok: true`, badge merah hilang, meta.json bersih, no `.unedited` sisa.

**Status sesi ini:** diagnosis + plan saja. **Tak ada kode diubah.** Nol `probe_v*.py`.
