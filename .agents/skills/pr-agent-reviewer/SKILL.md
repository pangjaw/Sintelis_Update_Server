---
name: pr-agent-reviewer
description: >-
  Automated AI code review, architecture inspection, zero-regression audit, and PR quality assurance based on Codium-ai/pr-agent methodology.
  Use this skill when reviewing code changes, auditing diffs, analyzing pull requests, checking for breaking changes,
  and verifying consistency between Python backend engines and React frontend components.
---

# 🤖 PR-Agent Reviewer Skill (Agen DIKA)

Keahlian review kode dan arsitektur tingkat lanjut yang mengadaptasi prinsip dan metodologi dari [**Codium-ai/pr-agent**](https://github.com/Codium-ai/pr-agent).
Dirancang khusus untuk menjaga integritas arsitektur aplikasi **Sintelis Desktop Suite** (Python Engine + React WebView).

---

## 🎯 Fokus Utama Review

Setiap kali melakukan audit terhadap perubahan kode (*git diff* atau PR), jalankan evaluasi pada 5 pilar berikut:

### 1. Zero Regression Check (Kontrak Mutlak)
* Pastikan tidak ada fungsi, argumen CLI, atau alur kerja yang terdaftar di `03_vault_docs/Feature_Specs_and_Rules.md` yang hilang, terhapus, atau diubah tanpa persetujuan.
* Periksa kesesuaian mapping stasiun/BTP, format folder output `03_export_foto` dan `04_photos_edited`.
* Pastikan seluruh mode (Mode Single Folder & Mode Dual Folder) tetap kompatibel.

### 2. File Locking & Concurrency Prevention
* **Windows File Locking:** Verifikasi bahwa berkas biner, PDF, atau gambar yang dibuka selalu menggunakan context manager (`with ...`) atau ditutup dengan benar (`doc.close()`, `pdf.close()`).
* Hindari race condition pada shared log/manifest (`logs/auto_crop_manifest.json`, `logs/cropped_collages.json`).
* Pastikan aturan larangan build biner otomatis (`build_and_deploy.bat`, `pyinstaller`) selalu ditaati.

### 3. Logika Backend Python (PyMuPDF, PIL, Regex)
* **Regex Resiliency:** Periksa apakah regex menangani variasi spasi, format nama stasiun (misal `COS` vs `CS`, `RADIO_COS` vs `COS`), serta nama senyawa (`BOO-CLT`).
* **Inpainting & Koordinat:** Periksa penanganan scaling rasio (300x300 canvas ke resolusi gambar asli) agar posisi watermark tidak meleset saat resolusi gambar berbeda.
* **Error Handling:** Pastikan setiap pemrosesan file individu dibungkus `try...except` agar satu berkas rusak tidak menghentikan seluruh pipeline.

### 4. Frontend React / Vite Integrity
* **State Synchronization:** Pastikan state lokal (seperti `includeTime`, `activeDetector`, `viewMode`) tersinkronisasi dengan baik ke payload API.
* **No Syntax / JSX Broken Tags:** Pastikan tidak ada tag unclosed atau typo pada handler event pointer/mouse.
* **Responsive & Non-blocking:** Pastikan operasi asinkron (`fetch`) memiliki indikator loading dan penanganan error responsif.

---

## 📋 Template Output Review (Gaya PR-Agent)

Saat Agen DIKA memberikan laporan review, gunakan format terstruktur berikut:

```markdown
### 🔍 PR / Code Review Report (PR-Agent Style)

#### 1. Ringkasan Perubahan
* **Tujuan:** [Ringkasan singkat apa yang diubah]
* **Komponen Terdampak:** [Daftar file Python & JSX]

#### 2. Skor Kualitas & Risiko
* **Tingkat Risiko:** 🟢 Rendah / 🟡 Sedang / 🔴 Tinggi
* **Potensi Regresi:** [Ada / Tidak Ada]

#### 3. Temuan Kritis (Critical Findings)
* [ ] **Bug / Race Condition:** [Temuan jika ada]
* [ ] **File Locking / Resource Leak:** [Temuan jika ada]
* [ ] **Breaking Contract:** [Pemeriksaan terhadap Feature_Specs_and_Rules.md]

#### 4. Rekomendasi Peningkatan (Actionable Improvements)
* [Saran konkret atau baris kode alternatif jika ada efisiensi yang bisa ditingkatkan]
```
