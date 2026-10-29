---
name: visual-regression-reviewer
description: >-
  Visual regression testing, canvas alignment audit, and UI layout QA based on Lost-Pixel / Percy methodologies.
  Use this skill when auditing React UI components, canvas bounding boxes, drag-and-drop coordinates, aspect ratio locking,
  sticky headers, and visual layout consistency across viewport sizes in Sintelis Desktop Suite.
---

# 📸 Visual Regression Reviewer Skill (Agen DIKA)

Keahlian inspeksi visual dan jaminan kualitas tata letak antarmuka (*UI Layout QA*) yang mengadaptasi prinsip dan metodologi dari [**Lost-Pixel**](https://github.com/lost-pixel/lost-pixel).
Dirancang khusus untuk memverifikasi akurasi visual kartu foto, canvas cropping, dan elemen interaktif pada **Sintelis Utility Desktop Suite**.

---

## 🎯 Fokus Utama Audit Visual

### 1. Kotak Preview Watermark & Koordinat Anti-Geser
* **Skalasi Relatif 300x300:** Kotak preview timemark wajib menggunakan persentase atau penskalaan proporsional:
  $$\text{top} = \frac{\text{pos.y}}{300} \times 100\%, \quad \text{left} = \frac{\text{pos.x}}{300} \times 100\%$$
* **Sidebar Collapse Test:** Memastikan saat sidebar desktop diciutkan (*collapse*) atau diperlebar, kotak preview timemark tidak melompat (*drift*) keluar dari area watermark foto.
* **Aspect Ratio 1:1 Kunci Persegi:** Pada pemotongan foto kolase (*Manual Crop*), pastikan kotak crop mempertahankan rasio aspek 1:1 saat ditarik dari keempat sudutnya.

### 2. Komparasi Berdampingan (*Dual Mode* 03 vs 04)
* **Alignment Kartu:** Kartu Foto Mentah (`03_export_foto`) dan Foto Editan (`04_photos_edited`) harus memiliki tinggi, padding, dan border yang simetris.
* **Ukuran Kartu (Standar vs Fokus Besar):**
  * Mode Standar: grid proporsional (`minmax(360px, 1fr)`).
  * Mode Besar: grid fokus (`minmax(420px, 1fr)`) agar teks stempel waktu di lapangan terbaca tajam tanpa pecah.

### 3. Sticky Toolbar & Navigasi Scroll
* **Toolbar Filter:** Memastikan toolbar pencarian, filter stasiun, dan tombol mode (`Jam: ON/OFF`, `Detektor`) tetap `sticky` di bagian atas (`position: sticky; top: 0; z-index: 20`) saat pengguna menggulir galeri ribuan aset.
* **Badge Interaktif:** Badge status seperti `✅ Lengkap (3 Foto)` dan `📅 Tanggal ✏️` harus memiliki kontras warna yang jelas (WCAG accessible), radius sudut membulat, dan indikator kursor pointer saat interaktif.

### 4. Responsivitas Modal Interaktif
* **ManualCropModal & TimemarkEditorModal:**
  * Modal harus berada pada lapisan tertinggi (`z-index: 9999`) dengan latar belakang semi-transparan (`backdrop-filter: blur`).
  * Kanvas preview harus berada di posisi tengah (*centered*), responsif terhadap drag pointer mouse, dan tidak menyebabkan *horizontal scroll overflow*.

---

## 📋 Prosedur Verifikasi Visual

1. **Static Analysis & CSS Audit:**
   * Periksa apakah terdapat nilai pixel absolut (`px`) pada container fleksibel yang seharusnya menggunakan persentase (`%`) atau unit fleksibel (`fr`, `rem`).
2. **Kompilasi Aset Frontend:**
   * Eksekusi `npm run build` di `01_scripts_pendukung/web-app/` untuk memastikan modul CSS dan JSX terkompilasi tanpa peringatan styling.
3. **Checklist Laporan Visual (Lost-Pixel Style):**
   * [ ] **Layout Drift:** Apakah ada elemen yang bergeser dari posisi aslinya?
   * [ ] **Color Contrast:** Apakah kontras teks tombol toggle (`Jam: ON/OFF`, badge tanggal) jelas dan konsisten?
   * [ ] **Canvas Bounding:** Apakah area seleksi drag tetap berada di dalam batas gambar (0 - 300px)?
