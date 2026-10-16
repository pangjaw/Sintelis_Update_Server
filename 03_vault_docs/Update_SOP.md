# 🛡️ SOP 6 ATURAN EMAS RILIS PEMBARUAN BINER

Patuhi keenam aturan ini sebelum merilis biner ke server:
1. **Wajib Bump Versi SemVer:** Naikkan versi di `updater_engine.py`, `App.jsx`, dan `BentoHeader.jsx` sebelum kompilasi.
2. **Validasi Ukuran Biner (180–195 MB):** Jika ukuran di bawah 170 MB (poppler/DLL tertinggal) atau di atas 250 MB (duplikasi rekursif), rilis DIBATALKAN.
3. **Pembersihan Cache Kompilasi:** Selalu gunakan opsi `--clean` pada PyInstaller dan pastikan `dist/` lama bersih.
4. **Verifikasi HTTP Header:** Pastikan endpoint mengembalikan `Content-Length` sesuai ukuran biner dan status `200 OK`.
5. **Manajemen Proses Update Server:** Pastikan proses `server_update.py` di `02_server_update` aktif pada port 8085.
6. **Lokasi Tunggal Terpusat:** Seluruh rilis biner dan manifest versi ditempatkan secara eksklusif di `C:\Users\SINTEL 1.21 BOO\Documents\Server\Sintelis_Update_Server\02_server_update`.
