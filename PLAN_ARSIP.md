# Plan: Mode ke-2 "Timpa Tanggal" — PaddleOCR deteksi + renderer HSV

## Goal
Menambah mode detektor Timemark ke-3 (`timpa_tanggal`) yang memakai PaddleOCR untuk menemukan posisi tanggal lama lalu langsung menimpanya dengan tanggal baru memakai renderer pill/blur (blur pill + pill hitam + teks putih), dan membuang seluruh rantai deteksi HSV dari jalur tanggal — sehingga tersisa 3 mode: **1. LaMa AI**, **2. Timpa Tanggal**, **3. Google AI Vision** (fallback-nya PaddleOCR, bukan HSV).

## Current context / assumptions

Repo git root: `D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server`
Dir app: `01_scripts_pendukung/web-app`

Python runtime (punya PIL, numpy, cv2, paddleocr): `C:/Users/dikarm/AppData/Local/Programs/Python/Python311/python.exe`
Wajib set `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` dan `PYTHONPATH=` untuk Paddle.
Terminal = git-bash. Path native Windows pakai slash-maju: `D:/02. Sintelis/...`.

### Fakta kode terverifikasi (inventory, nomor baris bisa bergeser — selalu `grep -n` dulu)

**Dispatch detektor** — `timemark_engine/edit_timemark_ide1.py`:
| Baris | Isi |
|---|---|
| `:1644` | `process_image(..., detector: str = "paddle_ocr", ignore_manual: bool = False)` |
| `:1668` | `eff_detector = detector or CURRENT_DETECTOR` |
| `:1670-1671` | whitelist: `if eff_detector not in ("paddle_ocr","lama_ai","google_vision"): eff_detector = "paddle_ocr"` |
| `:1717` | `if eff_detector in ("paddle_ocr", "lama_ai"):` → jalur PaddleOCR |
| `:1725-1730` | OCR gagal → `initial_box, initial_stage = None, "stage_fallback"`; `ocr_failed = True` |
| `:1751` | cabang kuota Google Vision → `CURRENT_DETECTOR = "paddle_ocr"` |
| `:1805` | `if stage == "stage_fallback" and (ocr_failed or (not is_collage and actual_input_path == image_path)):` → jalur skip |
| `:1826` | `folder_meta[pname]["ocrFailed"] = bool(eff_detector in ("paddle_ocr", "lama_ai"))` |
| `:1827` | `folder_meta[pname]["detector"] = "paddle_ocr" if eff_detector in ("paddle_ocr","lama_ai") else "guide"` |
| `:1863` | `is_lama_mode = (eff_detector in ("paddle_ocr", "lama_ai") or detector in ("paddle_ocr", "lama_ai"))` |
| `:1897` | tulis `<stem>.clean.jpg` — **hanya** di dalam `if is_lama_mode:` |
| `:1914` | `img_out = img_erased` (LaMa: TIDAK menempel teks) |
| `:1916` | `else:` → cabang non-LaMa |
| `:1938` | `img_out = draw_textbox(img_erased, box, timemark_text, no_bg=False)` ← **renderer yang diminta** |
| `:1942` | `img_out.save(output_path, ...)` — file yang dilihat user di `04` |
| `:1963` | `folder_meta[pname]["detector"] = "paddle_ocr" if stage=="stage_paddle_ocr" else ("google_vision" if stage=="stage_google_vision" else "guide")` |
| `:1966-1969` | meta `xPos`/`yPos` ditulis **0-300 normalized** dari `box` |
| `:2038` | argparse `--detector choices=["paddle_ocr","lama_ai","google_vision"], default="paddle_ocr"` |
| `:986` | `draw_textbox(img, box, text, no_bg=False)` — Gaussian blur `:1022`, pill hitam alpha 140 `:1030`, teks putih `:1035-1036` |

**Alasan desain inti (penting):** `is_lama_mode` mengembalikan **False** untuk nilai detektor apa pun selain `paddle_ocr`/`lama_ai`. Jadi detektor baru `timpa_tanggal` **otomatis** masuk cabang `else` (`:1916`) → `draw_textbox(..., no_bg=False)` di `:1938`, dan **tidak** menulis `.clean.jpg` (`:1897`). Tidak perlu kode render baru — hanya perlu didaftarkan di jalur deteksi.

**Frontend & plumbing lain:**
| Lokasi | Isi |
|---|---|
| `TimemarkModule.jsx:23` | `useState('paddle_ocr')` + komentar `// 'google_vision' \| 'guide'` |
| `TimemarkModule.jsx:552` | tombol `setDetector('paddle_ocr')` label `LaMa AI (Hapus Teks)` (hijau) |
| `TimemarkModule.jsx:576` | tombol `setDetector('google_vision')` label `✨ Google AI Vision (Otomatis)` (ungu) |
| `TimemarkModule.jsx:600` | tombol `setDetector('guide')` label `🎨 Metode Biasa (HSV Panduan)` (biru) ← **target ganti** |
| `GalleryPanel.jsx:31-66` | `getDetectorInfo(det)` — map label/icon/warna; `paddle_ocr\|lama_ai`→LaMa, `google_vision`→Vision AI, else→`Metode Biasa (HSV)` (fallback) |
| `GalleryPanel.jsx:2276-2280` | array selector `[{paddle_ocr,'LaMa AI (Hapus Teks)'},{google_vision,'✨ Vision AI'},{guide,'🎯 HSV'}]` ← **target ganti** |
| `GalleryPanel.jsx:1051,1070` | 2 tombol modal (`paddle_ocr`, `google_vision`) |
| `GalleryPanel.jsx:1032` | label inline `'LaMa AI'/'Vision AI'/'HSV'` |
| `GalleryPanel.jsx:1327` | komentar `// 'google_vision' \| 'guide'` |
| `BatchDateEditorPanel.jsx:448-449` | `<option>` `paddle_ocr`, `google_vision` |
| `BatchDateEditorPanel.jsx:2107-2108` | `<option>` `paddle_ocr`, `google_vision` |
| `BatchDateEditorPanel.jsx:45,743` | default `paddle_ocr`; `:743` komentar menyebut `guide` |
| `pipeline_runner.py:371` | `if "4" in steps_to_run and detector != "fast_meta":` |
| `pipeline_runner.py:377` | `chosen_detector = detector if detector in ("paddle_ocr","lama_ai","google_vision") else "paddle_ocr"` |
| `pipeline_runner.py:378,389` | label log + `det_short` |
| `run_desktop_webview.py:77` | guard: rewrite `"guide"` setelah `--detector` → `"paddle_ocr"` (biarkan, untuk meta lama) |
| `run_desktop_webview.py:4244` | `det_title` = `LaMa AI (Hapus Teks)` / `Google AI Vision` / `Metode Biasa (HSV)` |
| `merge_pdf_foto.py:1613` | `for clean_p in photos_dir.rglob("*.clean.jpg")` → restamp `:1633` `draw_textbox(..., no_bg=True)` |
| `run_desktop_webview.py:195` | `_ensure_asset_photos_stamped` — restamp dari `.clean.jpg`, `no_bg=True` |

### Keputusan user (terkunci)
1. Tiga mode: **LaMa AI** (`paddle_ocr`), **Timpa Tanggal** (`timpa_tanggal`), **Google AI Vision** (`google_vision`).
2. Timpa Tanggal menempel **fisik langsung** di Step 4 (bukan deferred), tombolnya muncul setelah Step 4 dicentang, lalu Step 4 langsung scan + timpa.
3. OCR gagal → **skip + `ocrFailed: true`** (perilaku yang sudah ada).
4. Tampilan teks baru = renderer HSV lama: blur pill + pill hitam + teks putih (`no_bg=False`).

## Architecture / proposed approach

Mode baru didaftarkan sebagai nilai detektor ke-4 di jalur **deteksi** (sehingga PaddleOCR yang mencari posisi tanggal lama), tapi **tidak** didaftarkan di `is_lama_mode` — sehingga ia otomatis jatuh ke cabang render non-LaMa `draw_textbox(no_bg=False)` yang sudah ada dan tidak menulis `.clean.jpg`. Jadi perubahan kode baru hampir nol: hanya whitelist, label, dan 2 tombol UI. Satu guard ditambahkan supaya jalur restamp deferred (Merge PDF) tidak menimpa hasil mode ini bila `.clean.jpg` warisan ada di folder yang sama.

## Step-by-step tasks

Urutan wajib: Task 1 dulu (mode baru harus ada sebelum dirujuk Task 8).

| # | Task | File utama |
|---|---|---|
| 1 | Mode `timpa_tanggal` di whitelist + jalur deteksi + cabang render tanpa `diffuse_fill` | `edit_timemark_ide1.py` |
| 2 | Teruskan lewat pipeline runner | `pipeline_runner.py` |
| 3 | Label `det_title` | `run_desktop_webview.py` |
| 4 | Guard restamp deferred | `merge_pdf_foto.py`, `run_desktop_webview.py` |
| 5 | Tombol Step 4 → 3 mode | `TimemarkModule.jsx` |
| 6 | `getDetectorInfo` + selector galeri | `GalleryPanel.jsx` |
| 7 | Dropdown opsi | `BatchDateEditorPanel.jsx` |
| 8 | Fast-update ikuti mode (tanpa `diffuse_fill` untuk Timpa Tanggal) | `fast_update_timemark.py` |
| 9 | Buang rantai HSV dari deteksi tanggal; fallback Vision → PaddleOCR | `edit_timemark_ide1.py`, `run_desktop_webview.py` |
| 10 | Bersihkan sisa `guide` + verifikasi akhir | semua |
| **11** | **Perbaiki deteksi kolase: zona pindai full-width + klasifikasi rekursif + ambang seam** | `auto_crop_collages.py` |
| **12** | **Perbaiki fallback buta `TL` → panel pertama hasil rekursif** | `run_desktop_webview.py` |
| **13** | **Hapus 3 file dead code kolase** (disetujui user) | `timemark_engine/` |

Kerjakan berurutan. Setiap task: edit → jalankan verifikasi → commit.
Semua perintah dijalankan dari dalam `D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server/01_scripts_pendukung/web-app` kecuali yang ditandai lain.

---

### Task 1 — Backend: daftarkan `timpa_tanggal` di whitelist + jalur deteksi PaddleOCR

**File:** `timemark_engine/edit_timemark_ide1.py`

1a. Cari whitelist:
```bash
grep -n 'if eff_detector not in (' timemark_engine/edit_timemark_ide1.py
```
Ganti baris itu menjadi:
```python
    if eff_detector not in ("paddle_ocr", "lama_ai", "google_vision", "timpa_tanggal"):
        eff_detector = "paddle_ocr"
```

1b. Cari jalur deteksi PaddleOCR:
```bash
grep -n 'if eff_detector in ("paddle_ocr", "lama_ai"):' timemark_engine/edit_timemark_ide1.py
```
Ganti menjadi:
```python
            if eff_detector in ("paddle_ocr", "lama_ai", "timpa_tanggal"):
```

1c. `ocrFailed` harus true untuk mode ini saat OCR gagal:
```bash
grep -n 'folder_meta\[pname\]\["ocrFailed"\]' timemark_engine/edit_timemark_ide1.py
```
Ganti menjadi:
```python
            folder_meta[pname]["ocrFailed"] = bool(eff_detector in ("paddle_ocr", "lama_ai", "timpa_tanggal"))
```

1d. Label `detector` di meta, dua tempat. Cari:
```bash
grep -n 'folder_meta\[pname\]\["detector"\]' timemark_engine/edit_timemark_ide1.py
```
- Di blok fallback-skip, ganti:
```python
            folder_meta[pname]["detector"] = "paddle_ocr" if eff_detector in ("paddle_ocr", "lama_ai") else "guide"
```
menjadi:
```python
            folder_meta[pname]["detector"] = eff_detector if eff_detector in ("paddle_ocr", "lama_ai", "google_vision", "timpa_tanggal") else "paddle_ocr"
```
- Di blok sukses (yang memakai `stage`), ganti:
```python
        folder_meta[pname]["detector"] = "paddle_ocr" if stage == "stage_paddle_ocr" else ("google_vision" if stage == "stage_google_vision" else "guide")
```
menjadi:
```python
        folder_meta[pname]["detector"] = eff_detector if eff_detector in ("paddle_ocr", "lama_ai", "google_vision", "timpa_tanggal") else ("paddle_ocr" if stage == "stage_paddle_ocr" else "google_vision")
```

1e. Tambah pilihan argparse. Cari:
```bash
grep -n 'parser.add_argument("--detector"' timemark_engine/edit_timemark_ide1.py
```
Ganti menjadi:
```python
        parser.add_argument("--detector", choices=["paddle_ocr", "lama_ai", "google_vision", "timpa_tanggal"], default="paddle_ocr", help="Detection method: paddle_ocr/lama_ai (default), google_vision, or timpa_tanggal")
```

1f. **Mode Timpa Tanggal tidak pakai `diffuse_fill`.** `draw_textbox` sendiri sudah memberi blur + pill hitam yang menutup tanggal lama, jadi penghapusan di depan tidak perlu. Tambahkan cabang khusus **tepat sebelum** `else:` non-LaMa.

Cari:
```bash
grep -n 'Mode Non-LaMa (Google Vision / HSV): Pertahankan alur legacy' -B 3 timemark_engine/edit_timemark_ide1.py
```
Sisipkan tepat sebelum baris `else:` yang memuat komentar itu, sehingga blok itu menjadi:
```python
    elif eff_detector == "timpa_tanggal":
        # Timpa Tanggal: tanpa hapus/diffuse_fill — draw_textbox (blur + pill hitam + teks baru) yang menimpa.
        img_out = draw_textbox(Image.fromarray(arr_orig), box, timemark_text, no_bg=False)
    else:
        # Mode Non-LaMa (Google Vision / HSV): Pertahankan alur legacy
        arr_work = arr_orig.copy()
```
Jangan sentuh isi `else:` — jalur legacy Google Vision / HSV tetap memakai `diffuse_fill`.

**Verifikasi Task 1:**
```bash
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server/01_scripts_pendukung/web-app"
python -c "import ast;ast.parse(open('timemark_engine/edit_timemark_ide1.py',encoding='utf-8').read());print('syntax-ok')"
PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python PYTHONPATH= "C:/Users/dikarm/AppData/Local/Programs/Python/Python311/python.exe" timemark_engine/edit_timemark_ide1.py --detector timpa_tanggal --input x.jpg 2>&1 | tail -2
```
Harapan: `syntax-ok`, lalu error **bukan** `invalid choice` (harus gagal di tahap lain, mis. file tidak ada).

Probe end-to-end (foto berteks → harus `stage_paddle_ocr`, JPG **bertanggal fisik**, `.clean.jpg` **tidak ada**):
```bash
T=C:/Users/dikarm/AppData/Local/Temp/timpa1; rm -rf "$T"; mkdir -p "$T"
"C:/Users/dikarm/AppData/Local/Programs/Python/Python311/python.exe" -c "from PIL import Image,ImageDraw,ImageFont;im=Image.new('RGB',(1200,900),(240,240,240));d=ImageDraw.Draw(im);d.text((70,690),'Rabu, Nov 13 2026 08:00',fill=(20,20,20),font=ImageFont.truetype('arialbd.ttf',42));im.save(r'C:/Users/dikarm/AppData/Local/Temp/timpa1/probe.jpg')"
PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python PYTHONPATH= "C:/Users/dikarm/AppData/Local/Programs/Python/Python311/python.exe" timemark_engine/edit_timemark_ide1.py --input "$T/probe.jpg" --single-out "$T/out/probe.jpg" --detector timpa_tanggal --date "Sabtu, Nov 14 2026 09:30" 2>&1 | tail -3
ls "$T/out/"
grep -o '"detector": "[a-z_]*"\|"stage": "[a-z_0-9]*"' "$T/out/meta.json"
```
Harapan: `ls` = `probe.jpg` dan `meta.json` **saja** (tidak ada `probe.clean.jpg`); grep → `"stage": "stage_paddle_ocr"` dan `"detector": "timpa_tanggal"`.

Probe OCR gagal (foto kosong → skip + tandai):
```bash
T=C:/Users/dikarm/AppData/Local/Temp/timpa1
"C:/Users/dikarm/AppData/Local/Programs/Python/Python311/python.exe" -c "from PIL import Image;Image.new('RGB',(1200,900),(30,60,90)).save(r'C:/Users/dikarm/AppData/Local/Temp/timpa1/blank.jpg')"
PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python PYTHONPATH= "C:/Users/dikarm/AppData/Local/Programs/Python/Python311/python.exe" timemark_engine/edit_timemark_ide1.py --input "$T/blank.jpg" --single-out "$T/out2/blank.jpg" --detector timpa_tanggal --date "Sabtu, Nov 14 2026 09:30" 2>&1 | tail -3
ls "$T/out2/"; grep -o '"ocrFailed": [a-z]*\|"stage": "[a-z_0-9]*"\|"detector": "[a-z_]*"' "$T/out2/meta.json"
```
Harapan: ada `blank.jpg.unedited`; grep → `"ocrFailed": true`, `"stage": "stage_fallback_skipped"`, `"detector": "timpa_tanggal"`.

Commit:
```bash
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server"
git add 01_scripts_pendukung/web-app/timemark_engine/edit_timemark_ide1.py
git commit -m "timemark: detektor timpa_tanggal (PaddleOCR deteksi + render HSV)"
```

---

### Task 2 — Backend: teruskan `timpa_tanggal` lewat pipeline runner

**File:** `timemark_engine/pipeline_runner.py`

2a. Cari whitelist:
```bash
grep -n 'chosen_detector = detector if detector in' timemark_engine/pipeline_runner.py
```
Ganti:
```python
        chosen_detector = detector if detector in ("paddle_ocr", "lama_ai", "google_vision") else "paddle_ocr"
```
menjadi:
```python
        chosen_detector = detector if detector in ("paddle_ocr", "lama_ai", "google_vision", "timpa_tanggal") else "paddle_ocr"
```

2b. Label log + label pendek. Cari:
```bash
grep -n "det_label = \|det_short = " timemark_engine/pipeline_runner.py
```
Ganti `det_label` menjadi:
```python
        det_label = 'LaMa AI (Hapus Teks)' if chosen_detector in ('paddle_ocr', 'lama_ai') else ('Google Cloud Vision AI' if chosen_detector == 'google_vision' else 'Timpa Tanggal (OCR + Box)')
```
Dan `det_short` menjadi:
```python
        det_short = 'LaMa AI' if chosen_detector in ('paddle_ocr', 'lama_ai') else ('AI Vision' if chosen_detector == 'google_vision' else 'Timpa Tanggal')
```

**Verifikasi Task 2:**
```bash
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server/01_scripts_pendukung/web-app"
python -c "import ast;ast.parse(open('timemark_engine/pipeline_runner.py',encoding='utf-8').read());print('syntax-ok')"
grep -n 'timpa_tanggal' timemark_engine/pipeline_runner.py
```
Harapan: `syntax-ok` + 3 baris (whitelist, det_label, det_short).

Commit:
```bash
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server"
git add 01_scripts_pendukung/web-app/timemark_engine/pipeline_runner.py
git commit -m "timemark: teruskan detector timpa_tanggal di pipeline runner"
```

---

### Task 3 — Backend: label `det_title` di web server

**File:** `run_desktop_webview.py`

Cari:
```bash
grep -n 'det_title' run_desktop_webview.py | head
```
Pada ekspresi label (sekitar `:4244`), ubah cabang `else` (yang sekarang `"Metode Biasa (HSV)"`) menjadi `"Timpa Tanggal"`. Ekspresi jadi:
```python
            det_title = "LaMa AI (Hapus Teks)" if detector in ("paddle_ocr", "lama_ai") else ("Google AI Vision" if detector == "google_vision" else "Timpa Tanggal")
```
**Jangan** ubah guard di `:77` (rewrite `"guide"` → `"paddle_ocr"`); itu masih dipakai oleh `meta.json` lama.

**Verifikasi Task 3:**
```bash
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server/01_scripts_pendukung/web-app"
python -c "import ast;ast.parse(open('run_desktop_webview.py',encoding='utf-8').read());print('syntax-ok')"
grep -n 'Timpa Tanggal' run_desktop_webview.py
```
Harapan: `syntax-ok` + 1 baris.

Commit:
```bash
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server"
git add 01_scripts_pendukung/web-app/run_desktop_webview.py
git commit -m "timemark: label log detector timpa_tanggal"
```

---

### Task 4 — Guard: jalur restamp deferred tidak boleh menimpa hasil Timpa Tanggal

**Masalah:** bila ada `.clean.jpg` warisan di folder yang sama, `merge_pdf_foto.py` dan `_ensure_asset_photos_stamped` menulis ulang `<stem>.jpg` dari `.clean.jpg` memakai `no_bg=True` — menghapus pill hitam hasil mode Timpa Tanggal.

**File:** `timemark_engine/merge_pdf_foto.py`

Cari:
```bash
grep -n 'for clean_p in photos_dir.rglob' timemark_engine/merge_pdf_foto.py
```
Tepat di dalam loop itu, setelah baris `p_info = m_data.get(f"{stem}.jpg", {})`, sisipkan:
```python
                    # Timpa Tanggal menempel fisik di Step 4; .clean.jpg warisan tidak boleh menimpanya.
                    if p_info.get("detector") == "timpa_tanggal":
                        continue
```

**File:** `run_desktop_webview.py` (fungsi `_ensure_asset_photos_stamped`)
Cari:
```bash
grep -n 'def _ensure_asset_photos_stamped' -A 20 run_desktop_webview.py
```
Setelah baris `p_info = meta_data.get(p_name, {}) if isinstance(meta_data.get(p_name), dict) else {}`, sisipkan:
```python
            if p_info.get("detector") == "timpa_tanggal":
                continue
```

**Verifikasi Task 4:**
```bash
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server/01_scripts_pendukung/web-app"
python -c "import ast;[ast.parse(open(f,encoding='utf-8').read()) for f in ['timemark_engine/merge_pdf_foto.py','run_desktop_webview.py']];print('syntax-ok')"
grep -n 'timpa_tanggal' timemark_engine/merge_pdf_foto.py run_desktop_webview.py
```
Harapan: `syntax-ok` + 2 baris guard.

Commit:
```bash
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server"
git add 01_scripts_pendukung/web-app/timemark_engine/merge_pdf_foto.py 01_scripts_pendukung/web-app/run_desktop_webview.py
git commit -m "timemark: guard restamp deferred untuk mode timpa_tanggal"
```

---

### Task 5 — UI: tombol Step 4 jadi 3 mode (buang `guide`)

**File:** `src/components/TimemarkModule.jsx`

5a. Komentar state, cari:
```bash
grep -n "useState('paddle_ocr'); // " src/components/TimemarkModule.jsx
```
Ganti komentarnya menjadi `// 'timpa_tanggal' | 'google_vision'`.
Ganti default jadi `'timpa_tanggal'`:
```jsx
  const [detector, setDetector] = useState('timpa_tanggal'); // 'timpa_tanggal' | 'google_vision'
```
> ponytail: default digeser ke Timpa Tanggal karena itu mode yang dipakai untuk produksi; LaMa tetap tersedia di tombol pertama.

5b. Tombol ketiga (`setDetector('guide')`) — cari:
```bash
grep -n "setDetector('guide')" src/components/TimemarkModule.jsx
```
Ganti seluruh blok `<button>...</button>` yang memuatnya (dari `<button` diikuti `type="button"`+`disabled={pipelineState.running}`+`onClick={() => setDetector('guide')}` sampai `</button>` setelah teks `Metode Biasa (HSV Panduan)`) dengan:
```jsx
                  <button
                    type="button"
                    disabled={pipelineState.running}
                    onClick={() => setDetector('timpa_tanggal')}
                    style={{
                      padding: '0.6rem 0.75rem',
                      borderRadius: '8px',
                      border: detector === 'timpa_tanggal' ? '2px solid #0284c7' : '1px solid var(--border-color)',
                      background: detector === 'timpa_tanggal' ? 'rgba(2, 132, 199, 0.15)' : 'var(--bg-secondary)',
                      color: detector === 'timpa_tanggal' ? '#38bdf8' : 'var(--text-secondary)',
                      cursor: pipelineState.running ? 'not-allowed' : 'pointer',
                      textAlign: 'left',
                      transition: 'all 0.2s',
                      boxShadow: detector === 'timpa_tanggal' ? '0 0 12px rgba(2, 132, 199, 0.25)' : 'none'
                    }}
                  >
                    <div style={{ fontWeight: 800, fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <span>🎯</span> Timpa Tanggal
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '0.2rem', lineHeight: 1.3 }}>
                      PaddleOCR cari tanggal lama, lalu timpa box blur + teks baru langsung
                    </div>
                  </button>
```

**Verifikasi Task 5:**
```bash
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server/01_scripts_pendukung/web-app"
grep -n "setDetector('guide')" src/components/TimemarkModule.jsx; echo "exit=$?"
grep -c "timpa_tanggal" src/components/TimemarkModule.jsx
```
Harapan: `exit=1` (tidak ada `guide`), dan count = `3` (default, onClick, styling ×2 → minimal 3).

Commit:
```bash
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server"
git add 01_scripts_pendukung/web-app/src/components/TimemarkModule.jsx
git commit -m "ui: tombol step 4 jadi LaMa AI / Timpa Tanggal / Google AI Vision"
```

---

### Task 6 — UI: `getDetectorInfo` + selector galeri kenali `timpa_tanggal`

**File:** `src/components/timemark/GalleryPanel.jsx`

6a. Tambah cabang di `getDetectorInfo` (cari `const getDetectorInfo = (det) => {`). Sisipkan **sebelum** blok `if (det === 'google_vision')`:
```jsx
  if (det === 'timpa_tanggal') {
    return {
      label: 'Timpa Tanggal',
      shortLabel: 'Timpa',
      icon: '🎯',
      gradient: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
      btnBg: 'rgba(2, 132, 199, 0.2)',
      btnColor: '#38bdf8',
      border: '1px solid #0284c7',
      shadow: '0 2px 6px rgba(2, 132, 199, 0.4)'
    };
  }
```

6b. Array selector galeri — cari `{ id: 'guide', label: '🎯 HSV', color: '#0284c7' }` dan ganti dengan:
```jsx
                { id: 'timpa_tanggal', label: '🎯 Timpa Tanggal', color: '#0284c7' }
```
Juga ubah `title=` di tombol map (sekitar `:2296`) supaya tidak menyebut HSV untuk mode ini:
```jsx
                  title={d.id === 'google_vision' ? 'Deteksi Google Cloud Vision AI' : d.id === 'timpa_tanggal' ? 'Deteksi tanggal lama via PaddleOCR lalu timpa' : 'Deteksi garis warna HSV'}
```

6c. Label inline di modal (cari `detector === 'google_vision' ? 'Vision AI' : 'HSV'`), ganti `'HSV'` pada rantai ternary menjadi `'Timpa'` dengan menambah cabang:
```jsx
{detector === 'paddle_ocr' ? 'LaMa AI' : (detector === 'google_vision' ? 'Vision AI' : 'Timpa')}
```
Ulangi untuk label serupa di `:727`, `:905-906`, `:1010`, `:1023-1024`, `:1241-1256` — setiap tempat yang menulis `'HSV'` atau `'Metode Biasa (HSV)'` sebagai cabang `else`/fallback.
Catatan: `getDetectorInfo` fallback `'Metode Biasa (HSV)'` di `:56-65` **biarkan** (dipakai meta lama), cukup ditambah cabang baru di 6a.

**Verifikasi Task 6:**
```bash
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server/01_scripts_pendukung/web-app"
grep -n "id: 'guide'" src/components/timemark/GalleryPanel.jsx; echo "exit=$?"
npm run build 2>&1 | grep -E "built in|error|Error"
```
Harapan: `exit=1`; build `✓ built in ...s` tanpa error.

Commit:
```bash
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server"
git add 01_scripts_pendukung/web-app/src/components/timemark/GalleryPanel.jsx
git commit -m "ui: galeri kenali mode Timpa Tanggal"
```

---

### Task 7 — UI: dropdown `BatchDateEditorPanel` tambah opsi

**File:** `src/components/timemark/BatchDateEditorPanel.jsx`

Cari kedua `<select>` (`grep -n 'option value="google_vision"' src/components/timemark/BatchDateEditorPanel.jsx` → 2 baris). Setelah **setiap** baris:
```jsx
                <option value="google_vision">Google Vision AI (Inpainting Bersih)</option>
```
sisipkan:
```jsx
                <option value="timpa_tanggal">Timpa Tanggal (OCR + Box)</option>
```
Perhatikan indentasi kedua lokasi berbeda — jangan asal replace-all tanpa cek.

Perbaiki juga komentar `:743`: `// 'google_vision' | 'guide'` → `// 'timpa_tanggal' | 'google_vision'`.

**Verifikasi Task 7:**
```bash
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server/01_scripts_pendukung/web-app"
grep -c 'option value="timpa_tanggal"' src/components/timemark/BatchDateEditorPanel.jsx
grep -n "guide" src/components/timemark/BatchDateEditorPanel.jsx; echo "exit=$?"
npm run build 2>&1 | grep -E "built in|error|Error"
```
Harapan: count = `2`; `exit=1` (komentar `guide` sudah dibersihkan); build sukses.

Commit:
```bash
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server"
git add 01_scripts_pendukung/web-app/src/components/timemark/BatchDateEditorPanel.jsx
git commit -m "ui: opsi Timpa Tanggal di panel ganti tanggal"
```

---

### Task 8 — Fast-update: ikuti mode terpilih (LaMa / Timpa Tanggal / Google AI)

**Konteks (sudah terverifikasi):** UI sudah mengirim mode terpilih — `GalleryPanel.jsx:1635` `detector: activeDetector`; server meneruskannya di `run_desktop_webview.py:3170` + `:3200`. Yang belum kenal mode baru adalah **routing di engine**.

**File:** `timemark_engine/fast_update_timemark.py`

8a. Routing mode. Cari:
```bash
grep -n 'req_det in ("paddle_ocr", "lama_ai")' timemark_engine/fast_update_timemark.py
```
Blok ini (sekitar `:281-286`) berisi:
```python
            if req_det in ("paddle_ocr", "lama_ai"):
                is_lama_mode = True
            elif req_det in ("guide", "hsv", "google_vision"):
                is_lama_mode = False
            else:
                is_lama_mode = (meta_det in ("paddle_ocr", "lama_ai")) or (found_clean is not None)
```
Ganti menjadi:
```python
            if req_det in ("paddle_ocr", "lama_ai"):
                is_lama_mode = True
            elif req_det in ("timpa_tanggal", "guide", "hsv", "google_vision"):
                # Mode legacy (Vision/HSV): render fisik lama; Timpa Tanggal punya cabang sendiri di bawah
                is_lama_mode = False
            else:
                is_lama_mode = (meta_det in ("paddle_ocr", "lama_ai")) or (found_clean is not None)
```
Catatan penting: `timpa_tanggal` **harus** masuk cabang `elif` eksplisit. Kalau tidak, ia jatuh ke `else` dan `found_clean is not None` akan membalikkannya ke mode LaMa hanya karena ada `.clean.jpg` warisan.

8b. Tulis `detector` ke meta. Cari:
```bash
grep -n 'meta_item\["detector"\] = req_det if req_det in' timemark_engine/fast_update_timemark.py
```
Ganti baris:
```python
                    meta_item["detector"] = req_det if req_det in ("guide", "google_vision") else cached_meta.get("detector", "cache")
```
menjadi:
```python
                    meta_item["detector"] = req_det if req_det in ("timpa_tanggal", "google_vision") else cached_meta.get("detector", "paddle_ocr")
```
Dan baris `stage` tepat di atasnya (`meta_item["stage"] = cached_meta.get("stage", "stage_fast_update")`) ganti menjadi:
```python
                    meta_item["stage"] = "stage_timpa_tanggal" if req_det == "timpa_tanggal" else cached_meta.get("stage", "stage_fast_update")
```

8c. Lebar box saat Timpa Tanggal. Cari:
```bash
grep -n 'x2 = min(w, x1 + fit_w)' timemark_engine/fast_update_timemark.py
```
Bloknya (sekitar `:345-353`) sekarang berbunyi:
```python
                    pad_x = max(4, int(w * 0.010))
                    fit_w = tw + (2 * pad_x)
                    x2 = min(w, x1 + fit_w)
                    box = (x1, y1, x2, y2)

                    arr = np.array(img)
                    crop = arr[y1:y2, x1:x2]
                    mask = np.ones((y2 - y1, x2 - x1), dtype=bool)
                    arr[y1:y2, x1:x2] = diffuse_fill(crop, mask, steps=25)
                    img_erased = Image.fromarray(arr)
                    img_out = draw_textbox(img_erased, box, target_text, no_bg=False)
```
Ganti seluruh blok itu menjadi:
```python
                    pad_x = max(4, int(w * 0.010))
                    fit_w = tw + (2 * pad_x)
                    if req_det == "timpa_tanggal":
                        # Timpa Tanggal: tanpa diffuse_fill — draw_textbox (blur + pill) yang menutupi tanggal lama.
                        # ponytail: lebar dari box standar (48%); pakai (x2-x1) hasil deteksi bila sisa teks masih terlihat.
                        x2 = min(w, x1 + max(fit_w, int(w * BOX_WIDTH_RATIO)))
                        box = (x1, y1, x2, y2)
                        img_out = draw_textbox(img, box, target_text, no_bg=False)
                    else:
                        # Mode Non-LaMa legacy (Google Vision / HSV): hapus dulu, lalu tempel
                        x2 = min(w, x1 + fit_w)
                        box = (x1, y1, x2, y2)
                        arr = np.array(img)
                        crop = arr[y1:y2, x1:x2]
                        mask = np.ones((y2 - y1, x2 - x1), dtype=bool)
                        arr[y1:y2, x1:x2] = diffuse_fill(crop, mask, steps=25)
                        img_erased = Image.fromarray(arr)
                        img_out = draw_textbox(img_erased, box, target_text, no_bg=False)
```
Catatan: `diffuse_fill` tetap dipakai jalur legacy — jangan dihapus dari import.

`BOX_WIDTH_RATIO` **belum** di-import di file ini (blok import `:33-41` hanya memuat `BOX_HEIGHT_RATIO`). Tambahkan, cari:
```bash
grep -n '    BOX_HEIGHT_RATIO,' timemark_engine/fast_update_timemark.py
```
Ganti:
```python
    BOX_HEIGHT_RATIO,
)
```
menjadi:
```python
    BOX_HEIGHT_RATIO,
    BOX_WIDTH_RATIO,
)
```
```bash
grep -n "BOX_WIDTH_RATIO\|from edit_timemark_ide1 import" timemark_engine/fast_update_timemark.py | head
```
Bila belum ada, tambahkan ke baris import yang sudah ada (`:33` `from edit_timemark_ide1 import (`). Jangan bikin baris import baru bila blok import itu sudah memuat nama lain.

8d. Label argparse. Cari:
```bash
grep -n 'help="Detector mode' timemark_engine/fast_update_timemark.py
```
Ganti menjadi:
```python
    parser.add_argument("--detector", type=str, default="auto", help="Detector mode (paddle_ocr, timpa_tanggal, google_vision, auto)")
```

**Verifikasi Task 8:**
```bash
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server/01_scripts_pendukung/web-app"
python -c "import ast;ast.parse(open('timemark_engine/fast_update_timemark.py',encoding='utf-8').read());print('syntax-ok')"
grep -n 'timpa_tanggal' timemark_engine/fast_update_timemark.py
grep -n "BOX_WIDTH_RATIO" timemark_engine/fast_update_timemark.py
```
Harapan: `syntax-ok`; `timpa_tanggal` muncul di 4 tempat (routing, stage, detector, help); `BOX_WIDTH_RATIO` ada di import + pemakaian.

Uji routing tanpa menyentuh foto asli (fungsi murni):
```bash
python -c "
def route(req_det, meta_det, found_clean):
    if req_det in ('paddle_ocr','lama_ai'): return True
    elif req_det in ('timpa_tanggal','guide','hsv','google_vision'): return False
    else: return (meta_det in ('paddle_ocr','lama_ai')) or (found_clean is not None)
assert route('timpa_tanggal','paddle_ocr',True) is False, 'harus timpa walau ada clean base warisan'
assert route('timpa_tanggal','timpa_tanggal',True) is False
assert route('paddle_ocr','timpa_tanggal',False) is True
assert route('google_vision','paddle_ocr',True) is False
assert route('auto','timpa_tanggal',True) is True, 'auto + clean warisan tetap LaMa'
print('route-ok')"
```
Harapan: `route-ok`.

Commit:
```bash
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server"
git add 01_scripts_pendukung/web-app/timemark_engine/fast_update_timemark.py
git commit -m "timemark: fast-update ikuti mode terpilih (timpa_tanggal)"
```

---

### Task 9 — Buang rantai HSV dari jalur deteksi tanggal (fallback Vision → PaddleOCR)

**Konteks:** keputusan user — semua fungsi HSV untuk deteksi tanggal diganti PaddleOCR. Yang **dipakai:**

| Lokasi | Dipakai untuk |
|---|---|
| `edit_timemark_ide1.py:1711` | `locate_date_box` — cabang `detector` tak dikenal / mask_mode |
| `edit_timemark_ide1.py:1788,1790` | `locate_date_box` di fallback Vision + cabang else |
| `edit_timemark_ide1.py:1536-1541` | "Smart Guide Alignment" di `detect_timemark_via_google_vision` |
| `edit_timemark_ide1.py:2006` | `_collect_folder_consensus` → `find_red_guide` |
| `run_desktop_webview.py:2920` | `get_folder_consensus_coordinates` langkah 3 |
| `edit_timemark_ide1.py:1705` | Pixel Inspector (`mask_mode`) |

**JANGAN DISENTUH — di luar timemark:**
- `timemark_engine/crop_single_temp.py:46` — `find_red_guide`/`find_cyan_guide_inverted` di sini memilih **kuadran** foto kolase di Step 1.5. Menghapusnya merusak Step 1.5.
- Definisi fungsi `find_red_guide:232`, `find_cyan_guide_inverted:365`, `find_custom1_hsv_guide:465`, `find_collage_custom_guide:587` — tetap ada selama masih ada pemakai di atas.

9a. **Fallback Vision → PaddleOCR.** File `timemark_engine/edit_timemark_ide1.py`. Cari:
```bash
grep -n 'Beralih ke Metode Biasa' -B 12 timemark_engine/edit_timemark_ide1.py
```
Blok `elif gv_stage == "quota_exceeded":` sampai `else:` berikutnya (sekitar `:1763-1789`) diganti menjadi:
```python
                elif gv_stage == "quota_exceeded":
                    print(json.dumps({
                        "type": "quota_exceeded",
                        "message": "Kuota Google Cloud Vision telah habis atau penagihan dinonaktifkan."
                    }), flush=True)
                    action = "continue_ocr"
                    if sys.stdin.isatty():
                        ans = input("\n[PAUSE] Kuota Google Vision habis. Lanjutkan dengan PaddleOCR? [Y/n]: ").strip().lower()
                        action = "stop" if ans == "n" else "continue_ocr"
                    else:
                        line = sys.stdin.readline().strip()
                        if line:
                            action = line
                    if action == "continue_ocr":
                        print("  │   ├── ⚠️ [FALLBACK] Beralih ke PaddleOCR", flush=True)
                        CURRENT_DETECTOR = "paddle_ocr"
                        p_box, p_stage = detect_timemark_via_paddle_ocr(actual_input_path, w, h)
                        if p_box is not None:
                            initial_box, initial_stage = p_box, p_stage
                        else:
                            initial_box, initial_stage = None, "stage_fallback"
                            ocr_failed = True
                    else:
                        print("  │   ├── 🛑 [STOP] Proses dihentikan pengguna karena kuota Google Vision habis.", flush=True)
                        sys.exit(42)
                else:
                    # Vision gagal → fallback PaddleOCR (rantai HSV sudah dibuang)
                    p_box, p_stage = detect_timemark_via_paddle_ocr(actual_input_path, w, h)
                    if p_box is not None:
                        initial_box, initial_stage = p_box, p_stage
                    else:
                        initial_box, initial_stage = None, "stage_fallback"
                        ocr_failed = True
```

9b. **Hapus Smart Guide Alignment dari Vision.** Cari:
```bash
grep -n 'Smart Guide Alignment' -A 14 timemark_engine/edit_timemark_ide1.py
```
Blok dari komentar `# Smart Guide Alignment:` sampai sebelum pemakaian `found_guide` berikutnya dihapus, dan setiap pemakaian `found_guide` disederhanakan (block itu hanya menyelaraskan `y_center`; ganti dengan nilai `y_center` murni dari hasil Vision). **Baca dulu 30 baris setelahnya** untuk memastikan tidak ada cabang lain yang bergantung — kalau rumit, tunda task ini dan catat sebagai open question.

9c. **Consensus folder pakai PaddleOCR, bukan garis merah.** Cari:
```bash
grep -n 'guide = find_red_guide(arr)' -B 8 timemark_engine/edit_timemark_ide1.py
```
Dalam `_collect_folder_consensus`, ganti pengambilan `find_red_guide` menjadi deteksi PaddleOCR:
```python
            p_box, _ = detect_timemark_via_paddle_ocr(src, img.width, img.height)
            if p_box:
                folder_guides[fkey].append(p_box[1])
            continue
```
Hapus baris `guide = find_red_guide(arr)` + blok `if guide:` di bawahnya, dan buang `arr = np.array(img)` bila tak lagi dipakai. Perhatikan: fungsi ini dijalankan **untuk semua foto** di folder, jadi PaddleOCR di sini memperlambat; cache sudah ada di `_PADDLE_CACHE` (`:1585`) sehingga aman bila dipanggil berulang pada file yang sama.
> ponytail: pakai cache yang ada; kalau konsensus jadi bottleneck di batch besar, batasi ke 3 foto pertama per folder.

9d. **Endpoint konsensus web server.** `run_desktop_webview.py:2912-2927` — ganti langkah 3 (`find_red_guide`) menjadi PaddleOCR:
```python
    # 3. Cek deteksi tanggal via PaddleOCR dari foto-foto di src_folder
    try:
        from timemark_engine.edit_timemark_ide1 import detect_timemark_via_paddle_ocr
        from pathlib import Path
        for p_name in photo_names:
            p_path = os.path.join(src_folder, p_name)
            if os.path.isfile(p_path):
                with Image.open(p_path) as img:
                    img = img.convert('RGB')
                    p_box, _ = detect_timemark_via_paddle_ocr(Path(p_path), img.width, img.height)
                if p_box:
                    return 14, int(round((p_box[1] / img.height) * 300))
    except Exception:
        pass
```

9e. **Hapus Pixel Inspector mask (0 pemakai UI).** Cari:
```bash
grep -n '\-\-red-mask\|mask_mode is not None\|mask_mode = ' timemark_engine/edit_timemark_ide1.py
```
Hapus tiga `parser.add_argument("--red-mask"/"--cyan-mask"/"--custom-mask")` (`:2035-2037`), baris penentuan `mask_mode` (`:2336`), pemakaian `mask_mode=` di pemanggilan `process_image` (`:2337`), cabang `elif mask_mode is not None:` (`:1704-1708`), dan parameter `mask_mode` di signature `process_image` (`:1644`). Cek pemakai lain dulu:
```bash
grep -rn "mask_mode" --include="*.py" . | grep -v node_modules
```
`find_guide_by_mask_direct` dan `find_collage_custom_guide` **tetap** dipakai `locate_date_box` — jangan hapus definisinya.

9f. **Hapus `_detect_guideline_for_label` (0 caller).** Cari:
```bash
grep -rn "_detect_guideline_for_label" --include="*.py" .
```
Bila hanya definisi (`:1226`) yang tersisa, hapus seluruh fungsinya. Bila ada caller, batalkan langkah ini dan laporkan.

**Verifikasi Task 9:**
```bash
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server/01_scripts_pendukung/web-app"
python -c "import ast
for f in ['timemark_engine/edit_timemark_ide1.py','run_desktop_webview.py','timemark_engine/crop_single_temp.py']:
    ast.parse(open(f,encoding='utf-8').read()); print('ok',f)"
echo "=== sisa guide di jalur tanggal (harus 0) ==="
grep -n "locate_date_box(" timemark_engine/edit_timemark_ide1.py
grep -rn "find_red_guide\|find_cyan_guide_inverted\|find_custom1_hsv_guide" --include="*.py" . | grep -v node_modules
echo "=== crop_single_temp HARUS tetap pakai (Step 1.5) ==="
grep -n "find_red_guide\|find_cyan_guide_inverted" timemark_engine/crop_single_temp.py
```
Harapan:
- 3× `ok`.
- `locate_date_box(` muncul **hanya** di definisinya (`:1070`) — atau tetap ada di `:1711` bila kamu memilih mempertahankan Pixel Inspector.
- `find_red_guide`/`find_cyan_guide_inverted`/`find_custom1_hsv_guide`: tersisa di definisi + `find_guide_by_mask_direct` + `crop_single_temp.py:46` saja.
- `crop_single_temp.py:46` **masih utuh**.

Uji regresi Step 1.5 tidak rusak (fungsi murni, tanpa GPU):
```bash
python -c "import ast,pathlib;p=pathlib.Path('timemark_engine/crop_single_temp.py').read_text(encoding='utf-8');assert 'find_cyan_guide_inverted' in p;print('step1.5-ok')"
```

Commit:
```bash
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server"
git add -A 01_scripts_pendukung/web-app/timemark_engine 01_scripts_pendukung/web-app/run_desktop_webview.py
git commit -m "timemark: buang rantai HSV dari deteksi tanggal, fallback Vision ke PaddleOCR"
```

---

### Task 10 — Bersihkan sisa referensi `guide` dan verifikasi akhir

Cari semua sisa:
```bash
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server"
grep -rn "guide" --include="*.jsx" 01_scripts_pendukung/web-app/src/
```
Bersihkan setiap komentar yang menyebut `'guide'` sebagai nilai detektor (ganti jadi `'timpa_tanggal'` atau hapus). **Jangan** sentuh:
- `run_desktop_webview.py:77` (guard meta lama)
- `edit_timemark_ide1.py` fungsi `find_red_guide` / `find_cyan_guide_inverted` / `find_custom1_hsv_guide` / `locate_date_box` / `_detect_guideline_for_label` (mesin HSV, masih dipakai fallback Google Vision + Pixel Inspector + konsensus folder)
- `fast_update_timemark.py` cabang `("guide", "hsv")` di routing (Task 8a) — itu alias legacy, biarkan
- `fast_update_timemark.py:_try_resident_lama` payload `"detector": "paddle_ocr"` — hardcoded by design (daemon LaMa)

Verifikasi akhir:
```bash
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server/01_scripts_pendukung/web-app"
python -c "import ast
for f in ['timemark_engine/edit_timemark_ide1.py','timemark_engine/pipeline_runner.py','run_desktop_webview.py','timemark_engine/merge_pdf_foto.py']:
    ast.parse(open(f,encoding='utf-8').read()); print('ok',f)"
npm run build 2>&1 | grep -E "built in|error"
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server"
git status --porcelain
git log --oneline -8
```
Harapan: 4× `ok`; build `✓ built in ...`; `git status` bersih.

---

## Fase 2 — Perbaikan deteksi kolase Step 1.5 (temuan 2026-11-14)

### Latar: bukti kegagalan nyata

Diuji pada 3 foto WhatsApp nyata (`C:\Users\dikarm\Downloads\WhatsApp Image 2026-11-14 at 12.23.{26,27,272}.jpeg`), dibandingkan dengan pembacaan visual:

| Foto | Isi nyata | Garis putih nyata | Hasil kode |
|---|---|---|---|
| `12.23.26` | 8 panel, baris 2+2+4 | X=799 (**49,9%**), Y=543 (**33,9%**), Y=1055 (65,9%) | `single_photo` |
| `12.23.27` | 6 panel, kiri-besar + 2 tumpuk kanan + 3 bawah | X=1054, Y=1054 (keduanya 65,9%) | `single_photo` |
| `12.23.272` | 9 panel, kisi **3×3 sama besar** | X=426 (33,3%), X=853 (66,6%), Y=426, Y=853 | `single_photo` |

Ketiganya kolase. Ketiganya dinyatakan **"bukan kolase"** oleh `detect_white_seam_collage`.

### Tiga akar masalah (terverifikasi `grep -n`)

1. **Zona pindai 45–55% terlalu sempit** — `auto_crop_collages.py:79`, `:92`, `:104`. Deteksi hanya melihat jendela 10% tengah. Pada `12.23.272` (kisi sempurna 3×3) garis ada di 33,3% dan 66,6% — keduanya di luar jendela. Ukur ulang dengan ambang longgar: kolom `x=852,853,854,855,856,859` = **100% putih**. Garisnya sempurna, kode hanya buta.
2. **Aturan klasifikasi kaku** — `:128-131`. `is_2x2` menuntut `max_v_pct >= 0.80` **dan** `max_h_pct >= 0.80`. Pada `12.23.26`, X = 100% (sempurna) tapi Y = 34,8% → gagal, meski garis vertikalnya utuh.
3. **Asumsi pembelah di tengah** — `:110-111` (`w // 2`, `h // 2` dengan toleransi 12px). Kenyataan: 33,9% / 65,9% / 33,3%+66,6%.

Tambahan: **ambang seam terlalu ketat.** `:69-70` memakai `min_c >= 195` (keras) / `>= 175` (lembut). Seam foto WhatsApp terukur `min_c` 173–194, `sat` 7–16 → banyak yang jatuh di antara dua ambang. Kalibrasi ke `min_c >= 160`, `sat < 25`.

### Keputusan: perbaiki mesinnya, jangan ganti dengan tool GitHub

Kode mask di `:63-70` **sudah benar** — yang salah hanya *di mana ia mencari* dan *seberapa kaku klasifikasinya*. Tool pihak ketiga yang disurvei (`reidenong/ComicPanelSegmentation`, `pakkio/comics-panel`, `ragavsachdeva/magi`) menargetkan **panel komik**: border hitam tebal, 2–6 panel. Domain berbeda dari foto kolase lapangan (garis putih tipis, 6–9 panel, tata letak tak beraturan). `ragavsachdeva/magi` juga berlisensi non-komersial/akademik saja — tidak layak untuk pekerjaan PT KAI. Mengganti mesin = membuang kode yang benar sambil mewarisi bug yang sama (bug ada di pemanggil, bukan mesin).

### Status prototipe (penting — belum production-ready)

Prototipe pembelahan rekursif sudah dibuat di `C:/Users/dikarm/AppData/Local/hermes/cache/scratch/collage_recursive.py` (scratch, bukan bagian repo). Hasil uji:

- Pendekatan: buang jendela 45–55%, pindai profil penuh, belah pada seam terkuat, ulangi rekursif pada tiap bagian.
- Bug pertama yang ditemukan dan diperbaiki: kandidat seam di dekat tepi (bingkai putih `y=12`) mengalahkan seam asli, lalu pembelahan ditolak → seluruh gambar jadi satu panel. Perbaikan: saring kandidat `c >= MIN_SPLIT` **sebelum** memilih pemenang, bukan sesudah.
- **Belum beres:** masih *over-split* — area nyaris-putih **di dalam** foto ikut terdeteksi sebagai seam (mis. `12.23.272` menghasilkan 11 panel, bukan 9; `12.23.27` 9 panel, bukan 6). Perbaikan yang belum dicoba: tolak run yang **lebar fisiknya** > ±30px (seam asli selalu tipis) sebelum memakai skornya.
- **Kesimpulan status:** arah terbukti benar (kisi 3×3 mulai terbelah pada posisi yang tepat), tapi prototipe **belum layak masuk produksi**. Jangan salin apa adanya.

### Task 11 — Perbaiki `detect_white_seam_collage` (zona pindai + klasifikasi + ambang)

File: `01_scripts_pendukung/web-app/timemark_engine/auto_crop_collages.py`

Tiga perubahan minimal, di `:69-135`:

1. **Ambang seam** (`:69-70`): turunkan ke nilai terukur.
   ```python
   is_white_seam = (sat < 25.0) & (min_c >= 160.0)
   is_soft_white_seam = (sat < 20.0) & (min_c >= 150.0)
   ```
   Alasan: seam foto WhatsApp terukur `sat` 7–16, `min_c` 173–194. Ambang lama (`195`/`175`) melewatkannya.
2. **Zona pindai** (`:79`, `:92`, `:104`): ganti `range(int(w*0.45), int(w*0.55))` jadi seluruh rentang dengan margin tepi, mis. `range(max(3, int(w*0.05)), int(w*0.95))`. Setelah itu buang asumsi simetri di `:110-111` — pakai kolom/baris pemenang apa adanya, karena pembelah nyata ada di 33,3% dan 66,6%.
3. **Klasifikasi** (`:128-135`): ganti `is_2x2`/`is_3in1` dengan pembelahan rekursif (potongan dari prototipe di atas), **setelah** menambahkan filter ketipisan run.

Verifikasi: jalankan pada 3 foto uji, harapan —
```bash
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server/01_scripts_pendukung/web-app/timemark_engine"
PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python PYTHONPATH= "C:/Users/dikarm/AppData/Local/Programs/Python/Python311/python.exe" -c "
import sys; sys.path.insert(0,'.')
from pathlib import Path
from auto_crop_collages import detect_white_seam_collage
for n in ('12.23.26','12.23.27','12.23.272'):
    p = Path(f'C:/Users/dikarm/Downloads/WhatsApp Image 2026-11-14 at {n}.jpeg')
    print(n, detect_white_seam_collage(p)[0])
"
```
Harapan: ketiganya **bukan** `single_photo`. Jumlah panel: 8 / 6 / 9.

**Catatan penting — perubahan perilaku.** Setelah zona pindai dibuka, foto yang sebelumnya `single_photo` bisa ikut terbelah. Wajib uji regresi pada folder non-kolase: minimal 20 foto dari kategori yang ada di `COLLAGE_ELIGIBLE_CATEGORIES` (`:39`) + 20 foto di luar daftar, pastikan jumlah `total_collages_cropped` tidak melonjak palsu. Filter kategori di `:297-299` tetap dipertahankan sebagai jaring pengaman.

### Task 12 — Perbaiki fallback buta

File: `01_scripts_pendukung/web-app/run_desktop_webview.py:4933-4942`

Bila deteksi gagal tapi user meminta potong, kode memakai kuadran **`TL`** statis dari pembelahan `w//2, h//2`:
```python
chosen = req_quad if req_quad in quads else "TL"
```
Ini menghasilkan potongan yang salah untuk setiap kolase tak simetris. Ganti: pakai **kuadran kiri-atas dari pembelahan hasil rekursif** (panel pertama), bukan `w//2`.
Sesudah Task 11, fallback ini seharusnya jarang terpakai — tapi tetap harus benar saat terpakai. Ini jalur penurunan mutu terakhir, bukan jalur utama.

### Task 13 — Hapus dead code (disetujui user)

Tiga file **pulau mati** — hanya saling impor, nol referensi dari pipeline, UI, atau shell:
- `timemark_engine/crop_single_temp.py` — 0 referensi eksternal; `find_red_guide` di dalamnya tidak dipakai siapa pun.
- `timemark_engine/scan_collages_helper.py` — 0 referensi eksternal.
- `timemark_engine/crop_collage_photos.py` — hanya diimpor `scan_collages_helper.py` (yang juga mati).

Diverifikasi: `grep -rn "<nama>" --include=*.py --include=*.jsx --include=*.js .` di luar file def-nya = kosong.
```bash
git rm "01_scripts_pendukung/web-app/timemark_engine/crop_single_temp.py" \
       "01_scripts_pendukung/web-app/timemark_engine/scan_collages_helper.py" \
       "01_scripts_pendukung/web-app/timemark_engine/crop_collage_photos.py"
```
Harapan: `git status` bersih setelah commit; `npm run build` dan pipeline Step 1.5 tetap lulus.

**Catatan koreksi:** pada turn sebelumnya aku menyebut `crop_collage_photos`/`detect_collage_by_crosshair` "nol pemanggil" — itu **salah**. Keduanya dipanggil di dalam `crop_collage_photos.py:81,99` dan `scan_collages_helper.py:26`. Yang benar: ketiga file itu membentuk pulau tertutup tanpa pintu masuk dari luar. Kesimpulan "aman dihapus" tetap sama, alasannya berbeda.

## Tests / validation

Repo tidak punya infrastruktur test (`pytest.ini`/`conftest.py`/`test_*.py`/`*.test.jsx` tidak ada). Jadi verifikasi = probe end-to-end + build.

**Regression check mode baru (jalankan setelah Task 1, ulangi di Task 8):**

Kasus A — foto berteks, `--detector timpa_tanggal`:
- `04` output JPG **bertanggal fisik** (teks baru terlihat di gambar).
- `stage = stage_paddle_ocr`, `detector = timpa_tanggal`.
- **Tidak ada** `<stem>.clean.jpg`.

Kasus B — foto kosong (tanpa teks), `--detector timpa_tanggal`:
- `<stem>.jpg` = salinan asli + `<stem>.jpg.unedited` ada.
- `ocrFailed = true`, `stage = stage_fallback_skipped`.

Kasus C — regresi mode 1 & 3 tidak berubah:
```bash
T=C:/Users/dikarm/AppData/Local/Temp/timpa1
for D in paddle_ocr google_vision; do echo "== $D"; PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python PYTHONPATH= "C:/Users/dikarm/AppData/Local/Programs/Python/Python311/python.exe" timemark_engine/edit_timemark_ide1.py --input "$T/blank.jpg" --single-out "$T/reg_$D/x.jpg" --detector "$D" --date "Sabtu, Nov 14 2026 09:30" >/dev/null 2>&1; grep -o '"stage": "[a-z_0-9]*"\|"detector": "[a-z_]*"' "$T/reg_$D/meta.json"; ls "$T/reg_$D/" | tr '\n' ' '; echo; done
```
Harapan:
- `paddle_ocr` → `"stage": "stage_fallback_skipped"` (OCR gagal pada foto kosong), ada `x.jpg.unedited`. **Tidak** ada `x.clean.jpg` (foto kosong: LaMa tidak pernah jalan).
- `google_vision` → `"detector": "google_vision"` (atau `guide` bila stage non-paddle/non-vision), ada `x.jpg`, **tidak** ada `x.clean.jpg`.
- Bentuk output kedua mode harus **identik** dengan sebelum plan ini. Kalau ada yang berubah, Task 1 salah sasaran.

**Manual UI (setelah `npm run dev` — tidak perlu untuk commit, tapi konfirmasi user):**
1. Centang Step 4 → tiga tombol muncul: **LaMa AI (Hapus Teks)**, **Google AI Vision (Otomatis)**, **🎯 Timpa Tanggal**.
2. Pilih Timpa Tanggal → Jalankan → foto di `04_photos_edited` bertanggal fisik dengan pill.
3. Galeri → selector detektor menampilkan **🎯 Timpa Tanggal** (bukan HSV).

## Risks, tradeoffs, open questions

1. **Cakupan pill (risiko visual utama).** `draw_textbox:1004` memakai `max(fit_w, x2-x1)` hanya bila lebar box ≤ `0.40 * w`. Bila box PaddleOCR lebih lebar dari 40% lebar gambar, ia jatuh ke `fit_w` (lebar teks baru) sehingga **sisa tanggal lama bisa terlihat** — tanpa `diffuse_fill` tidak ada lapisan penghapus cadangan. Cek visual wajib pada foto asli; bila terjadi, perbaikannya satu baris di `:1004` (pakai `(x2-x1)` tanpa batas 0.40w untuk mode `timpa_tanggal`).
2. **Mode 2 tidak menulis `.clean.jpg`.** Konsekuensi: tidak bisa di-restamp/repair lewat 'Tempel Tanggal' maupun jalur fast-update yang mengandalkan clean base. Menjalankan ulang Step 4 dengan mode 1 (LaMa) setelah mode 2 akan menggandakan penghapusan pada foto yang sudah bertanggal (LaMa akan mencoba meng-inpaint teks baru). Pastikan mode dipilih sekali per folder.
3. **Deferred stamp warisan** sudah dijaga di Task 4, tapi guard itu bergantung pada `meta.json` yang benar. Folder dengan `meta.json` lama (`detector: "guide"`) tanpa `.clean.jpg` tidak terpengaruh. Folder yang punya `.clean.jpg` dari run LaMa sebelumnya + meta baru `timpa_tanggal` → aman karena guard membaca meta.
4. **`TimemarkModule.jsx:23` default diubah ke `timpa_tanggal`.** Ini mengubah perilaku default Step 4 batch. Bila tidak diinginkan, kembalikan ke `'paddle_ocr'` — tidak ada bagian plan lain yang bergantung padanya.
5. **Fast-update (Step 4-fast) — dikerjakan di Task 8.** UI→engine sudah tersambung penuh: `GalleryPanel.jsx:1635` kirim `activeDetector`, `run_desktop_webview.py:3170`+`:3200` teruskan, `fast_update_timemark.py:281-286` memilih mode. Mode `timpa_tanggal` memakai cabang sendiri **tanpa `diffuse_fill`** — langsung `draw_textbox` (`no_bg=False`), sama seperti Step 4. Jalur legacy Vision/HSV tetap memakai `diffuse_fill`.
6. **`replace_export_photo.py:245`** `choices=["paddle_ocr","google_vision"]` tidak ditambah `timpa_tanggal`; endpoint replace/revert/swap foto tetap 2 pilihan. Di luar cakupan permintaan (yang minta 3 mode di Step 4 + fast-update), dicatat sebagai celah konsistensi.
7. **`detector_meta["textboxBox"]`** di `:1797-1802` mengirim box absolut; untuk mode 2 ini box tanggal **lama**, bukan teks baru. Frontend yang menggambar overlay dari nilai ini akan menggambar di posisi lama — perlu dicek bila overlay galeri dipakai pada mode 2.
8. **Fast-update mode LaMa memakai `.clean.jpg`; mode Timpa Tanggal tidak punya base itu.** Kalau user menjalankan Step 4 dengan mode 2 lalu Step 4-fast dengan mode 1, `found_clean` kosong → `_try_resident_lama` akan meng-inpaint ulang foto yang **sudah** bertanggal. Jalur ini hanya menyelamatkan bila foto sumber masih ada di `03`, tapi hasilnya menghapus tanggal baru. Peringatan: jangan campur mode 1 dan mode 2 pada folder yang sama tanpa rerun bersih dari `03`.

---

## Fase 3 — Bug badge "Gagal Ocr" (temuan 2026-11-16)

### Latar & bukti

Dua kasus beda, keduanya memunculkan badge merah `⚠️ Gagal Ocr` di GUI padahal app tidak crash:

| Kasus | Aset | Ukuran | Akar |
|---|---|---|---|
| A (BUG NYATA) | `OTB 1 ER TELKOM MASENG` — BTP BD/SERAT OPTIK, workspace `IMO\2026\FOTO\TES`, mode **LaMa AI** | 3048×3048 | Ambang piksel absolut |
| B (SALAH LABEL) | `ZP 24A CLT` — BTP JAK/AXC, workspace `IMO\2025\DONE NEW\FOTO\APRIL`, mode **Timpa Tanggal** | 300×300 | Foto tanpa tanggal → label merah menyala |

Bukti Kasus A: `04_photos_edited/.../OTB 1 ER TELKOM MASENG/meta.json` → ketiga foto `stage_fallback_skipped` + `ocrFailed:true` + `.unedited`. Bongkar layer OCR mentah: OCR **menemukan** `'Kamis,Nov 12 2026'` conf **1.00**, y≈2540, **tinggi box 95–106px**. Tak ada `0/50/100.txt` di folder sumber (hanya `date.txt`).

Bukti Kasus B: `meta.json` → `0.jpg` `stage_fallback_skipped`+`ocrFailed:true`; `50/100.jpg` `stage_paddle_ocr` (sukses). OCR mentah `0.jpg` = **tak ada baris tanggal** sama sekali (hanya alamat/koordinat/`Timemark`).

### Rantai sebab (terverifikasi)

1. `edit_timemark_ide1.py:1667–1680` — cabang OCR langsung `detect_timemark_via_paddle_ocr`; `p_box is None` → `stage_fallback` + `ocr_failed=True`. **Tak ada sibling-consensus** (kontras `google_vision` `:1712–1745`).
2. `:1757` cabang skip → `:1783–1785` tulis `stage_fallback_skipped` + `ocrFailed=bool(eff_detector in ("paddle_ocr","lama_ai","timpa_tanggal"))` → selalu `True`.
3. `GalleryPanel.jsx:2750` render badge `:2755`. Tombol `:2518` → `handleProcessTimemark` `:1972` → `POST /api/timemark/process-single` `:1978` (server `run_desktop_webview.py:3072`); refresh `refreshSinglePhotoCard` `:1383`. Badge kembar `BatchDateEditorPanel.jsx:1856`.
4. UI "LaMa AI (Hapus Teks)" = detector internal **`paddle_ocr`** (`GalleryPanel.jsx:2289`), bukan `lama_ai` (alias tampilan `:32`). `is_lama_mode` mencakup `paddle_ocr` (`edit_timemark_ide1.py:1822`).

### Task 14 — Ambang piksel proporsional (`paddle_worker.py`) — ROOT CAUSE Kasus A

File: `01_scripts_pendukung/web-app/timemark_engine/paddle_worker.py`

Semua ambang px-absolut harus skala ke ukuran gambar:
1. `:78` cap tinggi `7 <= (y2-y1) <= 60` → proporsional (mis. `h*0.004 .. h*0.06`).
2. `:67` merge-tolerance `abs(y_mid - y_mid) <= 7.0` → proporsional (mis. `h*0.02`).
3. `:78` lebar minimum `(x2-x1) >= 20` → proporsional (mis. `w*0.006`).
4. Cek `:40` `scale` (4.0/2.0/1.0): foto 3048 → `scale=1.0` benar; pastikan tak ada ambang bawah lain terlewat.

Verifikasi (satu skrip sekali jalan, jangan `probe_v*.py`):
```
cd "D:/02. Sintelis/UPT Resor Sintelis 1.21 Bogor/Server/Sintelis_Update_Server/01_scripts_pendukung/web-app/timemark_engine"
PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python PYTHONPATH= "C:/Users/dikarm/AppData/Local/Programs/Python/Python311/python.exe" paddle_worker.py "<foto 300px>"
```
Harapan: foto 300px (mis. `ZP 24A CLT/50.jpg`) **dan** foto 3048px (`OTB 1 ER TELKOM MASENG/0.jpg`) keduanya `{"ok": true, "box": [...]}`.

### Task 15 — Sibling-consensus untuk cabang OCR (`edit_timemark_ide1.py`)

File: `01_scripts_pendukung/web-app/timemark_engine/edit_timemark_ide1.py:1667–1680`

Reuse blok `:1712–1745`: sebelum menyerah `stage_fallback`, coba box dari `0/50/100.txt` saudara di folder sama, lalu `meta.json` saudara. Membuat `ZP 24A CLT/0.jpg` ikut ter-stamp, bukan skip.
**Catatan:** Kasus A tak punya `.txt` saudara → murni tugas Task 14, bukan ini.

Verifikasi: jalankan ulang `ZP 24A CLT` → `0.jpg` `stage` non-fallback (mis. `stage_consensus_sibling`).

### Task 16 — Pisahkan "tak ada tanggal" vs "engine gagal" (`edit_timemark_ide1.py:1757–1797`)

Bedakan `ocrFailed` (engine error, mis. `stage_paddle_not_found` `:1587`) dari state benign baru (`noDateFound`). Badge merah "Gagal Ocr" hanya engine error; benign → badge kuning/abu (usul `⏭️ Dilewati (tanpa tanggal)`).
UI: `GalleryPanel.jsx:2750`, `BatchDateEditorPanel.jsx:1856`.

### Task 17 — Bersihkan state basi saat run sukses (`:1785` + `run_desktop_webview.py:3072`)

Saat run non-fallback sukses: **hapus** key `ocrFailed` dari entry meta foto itu, **dan hapus** `<nama>.jpg.unedited` bila ada (sisa marker skip lama, saat ini tak pernah dihapus). Frontend tak perlu diubah (re-evaluate dari `data.meta`).

### Task 18 — Guard `pdfplumber` (`export_pdf_foto.py:16`)

File: `01_scripts_pendukung/web-app/timemark_engine/export_pdf_foto.py`

`import pdfplumber` tak terpasang di interpreter yang dites (hanya tercatat `build_exe.spec:59`). Jalur CLI input-**folder** (`edit_timemark_ide1.py:2005`) crash `ModuleNotFoundError`. Jadikan import lazy di dalam fungsi yang perlu, atau `try/except` dengan pesan jelas.

### Task 19 — Verifikasi ulang end-to-end

(a) `OTB 1 ER TELKOM MASENG` (3 foto 3048px, LaMa AI) → `stage_paddle_ocr`, badge merah hilang.
(b) `ZP 24A CLT` → `0.jpg` ter-stamp via konsensus (atau badge benign, bukan merah).

Wajib:
- **Restart daemon OCR** port **58253** (aktif, cache `_ocr` in-memory; patch `paddle_worker.py` tak berlaku sampai app/daemon restart, ATAU uji lewat subprocess langsung).
- **Paksa render ulang**: `fast_update_timemark.py:270–275` skip foto yang tanggalnya "sesuai" → jalankan `--force`, jika tidak verifikasi menipu.
- Cek `meta.json` + `ls *.unedited` bersih.

### Keputusan desain perlu disetujui user

1. Task 14: batas proporsional persis (usul `h*0.004..h*0.06`, `h*0.02`, `w*0.006`)? Harus tetap kompatibel 300px.
2. Task 15: prioritas sumber box saudara — `.txt` dulu atau `meta.json` dulu? (google_vision: `.txt` dulu.)
3. Task 16: label/warna benign — usul kuning `⏭️ Dilewati (tanpa tanggal)`.
4. Konfirmasi: apakah mode LaMa AI memang **seharusnya** menimpa tanggal (seperti Timpa), atau alias ke `paddle_ocr` itu disengaja?
