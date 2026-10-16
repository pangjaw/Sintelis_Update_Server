// =============================================================================
// DateChangerPanel.jsx — Komponen Ganti Tanggal Dokumen PDF & Nama Berkas
// =============================================================================

import { useState, useMemo, useCallback } from 'react';
import PersonnelChangerSubTab from './PersonnelChangerSubTab';

const INDONESIAN_MONTHS = [
  "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
  "Juli", "Agustus", "September", "Oktober", "November", "Desember"
];

// Helper kalkulasi live preview nama berkas baru
function computePreviewFilename(origName, newDateStr) {
  if (!newDateStr || !origName) return origName;
  const parts = newDateStr.split('-');
  if (parts.length !== 3) return origName;
  const year = parseInt(parts[0], 10);
  const month = parseInt(parts[1], 10);
  const day = parseInt(parts[2], 10);

  const dmyDash = `${String(day).padStart(2, '0')}-${String(month).padStart(2, '0')}-${year}`;
  const indoStr = `${String(day).padStart(2, '0')} ${INDONESIAN_MONTHS[month] || ''} ${year}`;

  const lastDot = origName.lastIndexOf('.');
  const name = lastDot !== -1 ? origName.slice(0, lastDot) : origName;
  const ext = lastDot !== -1 ? origName.slice(lastDot) : '';

  // 1. Cek prefix DD-MM-YYYY_
  const preMatch = name.match(/^(\d{2}-\d{2}-\d{4})(_.*)$/i);
  if (preMatch) {
    return `${dmyDash}${preMatch[2]}${ext}`;
  }

  // 2. Cek teks bulan Indonesia
  const idnMatch = name.match(/\b\d{1,2}\s+(?:JANUARI|FEBRUARI|MARET|APRIL|MEI|JUNI|JULI|AGUSTUS|SEPTEMBER|OKTOBER|NOVEMBER|DESEMBER)\s+\d{4}\b/i);
  if (idnMatch) {
    const newName = name.slice(0, idnMatch.index) + indoStr + name.slice(idnMatch.index + idnMatch[0].length);
    return `${newName}${ext}`;
  }

  // 3. Cek suffix / embedded DD-MM-YYYY
  const stdMatch = name.match(/\b(\d{2})[-/.](\d{2})[-/.](\d{4})\b/);
  if (stdMatch) {
    const newName = name.slice(0, stdMatch.index) + dmyDash + name.slice(stdMatch.index + stdMatch[0].length);
    return `${newName}${ext}`;
  }

  return `${name}_${dmyDash}${ext}`;
}

export default function DateChangerPanel() {
  const [activeSubTab, setActiveSubTab] = useState('date'); // 'date' | 'personnel'
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [feedback, setFeedback] = useState(null);
  const [createBackup, setCreateBackup] = useState(false);

  // Master datepicker state (default: hari ini)
  const [masterDate, setMasterDate] = useState(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  });

  // 1. Handler Pemindaian Berkas dari Backend
  const handleScanPaths = async (paths, folder = null) => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch('/api/date-changer/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths, folder })
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        const scanned = (data.items || []).map(item => ({
          ...item,
          selected: true,
          // Gunakan detected_date atau masterDate sebagai default new_date
          new_date: item.detected_date || masterDate,
          execution_status: 'ready' // 'ready' | 'processing' | 'success' | 'error'
        }));

        setItems(prev => {
          // Gabungkan berkas baru tanpa duplikasi path
          const existingPaths = new Set(prev.map(i => i.path));
          const newUnique = scanned.filter(i => !existingPaths.has(i.path));
          return [...prev, ...newUnique];
        });

        setFeedback({
          type: 'info',
          text: `✓ Pemindaian selesai: Ditemukan ${scanned.length} berkas PDF siap diubah tanggalnya.`
        });
      } else {
        setFeedback({ type: 'error', text: 'Gagal memindai berkas: ' + (data.error || 'Terjadi kesalahan') });
      }
    } catch (err) {
      setFeedback({ type: 'error', text: 'Galat pemindaian: ' + err.message });
    } finally {
      setLoading(false);
    }
  };

  // 2. Pilih Banyak File PDF Sekaligus
  const handleSelectFiles = async () => {
    try {
      const res = await fetch('/api/select-files', { method: 'POST' });
      const data = await res.json();
      if (data && data.paths && data.paths.length > 0) {
        await handleScanPaths(data.paths);
      }
    } catch (err) {
      setFeedback({ type: 'error', text: 'Gagal membuka pemilih berkas: ' + err.message });
    }
  };

  // 3. Pilih Folder Penuh
  const handleSelectFolder = async () => {
    try {
      const res = await fetch('/api/select-folder', { method: 'POST' });
      const data = await res.json();
      if (data && data.path) {
        await handleScanPaths([], data.path);
      }
    } catch (err) {
      setFeedback({ type: 'error', text: 'Gagal membuka pemilih folder: ' + err.message });
    }
  };

  // 4. Drag and Drop Handler
  const handleDrop = useCallback(async (e) => {
    e.preventDefault();
    e.stopPropagation();
    const droppedFiles = Array.from(e.dataTransfer.files || []).filter(f => f.name.toLowerCase().endsWith('.pdf'));
    if (droppedFiles.length === 0) return;

    // Ambil path jika tersedia (desktop webview)
    const paths = droppedFiles.map(f => f.path).filter(Boolean);
    if (paths.length > 0) {
      await handleScanPaths(paths);
    } else {
      setFeedback({
        type: 'warn',
        text: 'Pilih file menggunakan tombol "Pilih Berkas PDF" untuk akses path langsung di aplikasi desktop.'
      });
    }
  }, []);

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  // 5. Terapkan Master Date ke Semua Berkas Terpilih
  const handleApplyMasterDate = () => {
    if (!masterDate) return;
    setItems(prev => prev.map(item => item.selected ? { ...item, new_date: masterDate } : item));
    setFeedback({
      type: 'info',
      text: `✓ Tanggal target ${masterDate} diterapkan ke semua berkas yang dicentang.`
    });
  };

  // 6. Toggle Select All
  const allSelected = useMemo(() => items.length > 0 && items.every(i => i.selected), [items]);
  const handleToggleSelectAll = () => {
    const target = !allSelected;
    setItems(prev => prev.map(i => ({ ...i, selected: target })));
  };

  // 7. Update Tanggal Baru per Baris
  const handleUpdateItemDate = (idx, newDate) => {
    setItems(prev => {
      const copy = [...prev];
      copy[idx] = { ...copy[idx], new_date: newDate };
      return copy;
    });
  };

  // 8. Toggle Select per Baris
  const handleToggleSelectItem = (idx) => {
    setItems(prev => {
      const copy = [...prev];
      copy[idx] = { ...copy[idx], selected: !copy[idx].selected };
      return copy;
    });
  };

  // 9. Hapus Berkas dari Daftar
  const handleRemoveItem = (idx) => {
    setItems(prev => prev.filter((_, i) => i !== idx));
  };

  // 10. Eksekusi Pengubahan Tanggal
  const handleExecute = async () => {
    const selectedItems = items.filter(i => i.selected && i.new_date);
    if (selectedItems.length === 0) {
      alert('Silakan pilih minimal 1 berkas yang memiliki tanggal baru!');
      return;
    }

    setProcessing(true);
    setProgress({ current: 0, total: selectedItems.length });
    setFeedback(null);

    // Tandai status baris
    setItems(prev => prev.map(i => i.selected ? { ...i, execution_status: 'processing' } : i));

    try {
      const payload = {
        items: selectedItems.map(i => ({ path: i.path, new_date: i.new_date })),
        create_backup: createBackup
      };

      const res = await fetch('/api/date-changer/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (res.ok && data.ok) {
        const resultMap = {};
        (data.results || []).forEach(r => {
          resultMap[r.old_path] = r;
        });

        setItems(prev => prev.map(i => {
          const r = resultMap[i.path];
          if (r) {
            return {
              ...i,
              path: r.new_path || i.path,
              filename: r.new_name || i.filename,
              detected_date: i.new_date,
              execution_status: r.ok ? 'success' : 'error',
              error_msg: r.error
            };
          }
          return i;
        }));

        setFeedback({
          type: 'success',
          text: `🎉 Selesai! Berhasil memperbarui ${data.success_count || 0} berkas PDF.` +
                (data.error_count > 0 ? ` (${data.error_count} berkas gagal)` : '')
        });
      } else {
        setFeedback({ type: 'error', text: 'Gagal menjalankan pembaruan: ' + (data.error || 'Terjadi galat') });
        setItems(prev => prev.map(i => i.selected ? { ...i, execution_status: 'error' } : i));
      }
    } catch (err) {
      setFeedback({ type: 'error', text: 'Galat eksekusi: ' + err.message });
      setItems(prev => prev.map(i => i.selected ? { ...i, execution_status: 'error' } : i));
    } finally {
      setProcessing(false);
    }
  };

  const selectedCount = useMemo(() => items.filter(i => i.selected).length, [items]);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem',
        height: '100%',
        width: '100%',
        padding: '0.25rem 0.5rem 1rem 0.25rem',
        boxSizing: 'border-box',
        overflow: 'hidden'
      }}
    >
      {/* ── Sub-Tabs Navigation Bar ── */}
      <div className="floating-pill-container" style={{ width: '100%' }}>
        <button
          type="button"
          className={`floating-pill-btn ${activeSubTab === 'date' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('date')}
        >
          📅 Ubah Tanggal Dokumen
        </button>
        <button
          type="button"
          className={`floating-pill-btn ${activeSubTab === 'personnel' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('personnel')}
        >
          👥 Ubah Personil & No. SC
        </button>
      </div>

      {activeSubTab === 'personnel' ? (
        <PersonnelChangerSubTab />
      ) : (
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '1rem',
            height: '100%',
            width: '100%',
            overflow: 'hidden'
          }}
        >
          {/* ── HEADER BANNER ── */}
      <div
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          borderRadius: '10px',
          padding: '1rem 1.25rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem'
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '1.25rem' }}>📅</span>
            <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Ubah Tanggal Dokumen & File PDF
            </h3>
          </div>
          <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.825rem', color: 'var(--text-secondary)' }}>
            Mengganti nama berkas PDF (format DD-MM-YYYY), formulir Halaman 1 (sel Tanggal: YYYY-MM-DD), dan header Halaman Foto (DD Bulan YYYY rata tengah). Watermark foto tetap asli.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center' }}>
          <button
            onClick={handleSelectFiles}
            disabled={loading || processing}
            style={{
              padding: '0.5rem 0.9rem',
              background: 'var(--accent)',
              color: '#ffffff',
              border: 'none',
              borderRadius: '7px',
              cursor: (loading || processing) ? 'not-allowed' : 'pointer',
              fontSize: '0.825rem',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              boxShadow: '0 2px 4px rgba(255, 115, 0, 0.2)'
            }}
          >
            📄 Pilih Berkas PDF...
          </button>
          <button
            onClick={handleSelectFolder}
            disabled={loading || processing}
            style={{
              padding: '0.5rem 0.9rem',
              background: 'var(--bg-secondary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: '7px',
              cursor: (loading || processing) ? 'not-allowed' : 'pointer',
              fontSize: '0.825rem',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem'
            }}
          >
            📁 Pilih Folder...
          </button>
          {items.length > 0 && (
            <button
              onClick={() => setItems([])}
              disabled={loading || processing}
              style={{
                padding: '0.5rem 0.75rem',
                background: 'transparent',
                color: 'var(--text-muted)',
                border: '1px solid var(--border-color)',
                borderRadius: '7px',
                cursor: 'pointer',
                fontSize: '0.825rem'
              }}
              title="Bersihkan daftar berkas"
            >
              Bersihkan
            </button>
          )}
        </div>
      </div>

      {/* ── FEEDBACK ALERT ── */}
      {feedback && (
        <div
          style={{
            padding: '0.75rem 1rem',
            borderRadius: '8px',
            fontSize: '0.85rem',
            fontWeight: 500,
            background: feedback.type === 'success' ? 'rgba(34, 197, 94, 0.15)' :
                        feedback.type === 'error' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(59, 130, 246, 0.15)',
            color: feedback.type === 'success' ? '#22c55e' :
                   feedback.type === 'error' ? '#ef4444' : '#3b82f6',
            border: `1px solid ${feedback.type === 'success' ? '#22c55e' : feedback.type === 'error' ? '#ef4444' : '#3b82f6'}`
          }}
        >
          {feedback.text}
        </div>
      )}

      {/* ── BATCH CONTROLS & MASTER DATE PICKER ── */}
      {items.length > 0 && (
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            borderRadius: '10px',
            padding: '0.85rem 1.25rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '1rem'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
              Set Tanggal Target Bersama:
            </span>
            <input
              type="date"
              value={masterDate}
              onChange={(e) => setMasterDate(e.target.value)}
              style={{
                padding: '0.4rem 0.6rem',
                borderRadius: '6px',
                border: '1px solid var(--border-color)',
                background: 'var(--bg-input, var(--bg-secondary))',
                color: 'var(--text-primary)',
                fontSize: '0.85rem',
                outline: 'none'
              }}
            />
            <button
              onClick={handleApplyMasterDate}
              disabled={processing}
              style={{
                padding: '0.4rem 0.75rem',
                background: 'var(--bg-secondary)',
                color: 'var(--accent)',
                border: '1px solid var(--accent)',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '0.825rem',
                fontWeight: 600
              }}
            >
              Terapkan ke Semua ({selectedCount})
            </button>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', fontSize: '0.825rem', color: 'var(--text-secondary)' }}>
              <input
                type="checkbox"
                checked={createBackup}
                onChange={(e) => setCreateBackup(e.target.checked)}
                disabled={processing}
                style={{ cursor: 'pointer' }}
              />
              Buat salinan cadangan (.bak)
            </label>

            <span style={{ fontSize: '0.825rem', color: 'var(--text-muted)' }}>
              Terpilih: <strong>{selectedCount}</strong> dari <strong>{items.length}</strong> berkas
            </span>
          </div>
        </div>
      )}

      {/* ── TABEL BERKAS / DROPZONE CONTAINER ── */}
      <div
        style={{
          flex: 1,
          minHeight: 0,
          background: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          borderRadius: '10px',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}
      >
        {items.length === 0 ? (
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '3rem',
              color: 'var(--text-muted)',
              textAlign: 'center'
            }}
          >
            <div style={{ fontSize: '3rem', marginBottom: '1rem', opacity: 0.6 }}>📑</div>
            <h4 style={{ margin: 0, color: 'var(--text-primary)', fontSize: '1.1rem' }}>
              Belum ada berkas PDF yang dipilih
            </h4>
            <p style={{ margin: '0.5rem 0 1.5rem 0', fontSize: '0.85rem', maxWidth: '420px', lineHeight: 1.5 }}>
              Klik tombol <strong>Pilih Berkas PDF</strong> untuk memilih berkas satuan/banyak, atau <strong>Pilih Folder</strong> untuk memindai seluruh direktori.
            </p>
            <button
              onClick={handleSelectFiles}
              style={{
                padding: '0.6rem 1.25rem',
                background: 'var(--accent)',
                color: '#ffffff',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer',
                fontSize: '0.875rem',
                fontWeight: 600
              }}
            >
              Pilih Berkas PDF...
            </button>
          </div>
        ) : (
          <div style={{ flex: 1, overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.825rem' }}>
              <thead
                style={{
                  position: 'sticky',
                  top: 0,
                  background: 'var(--bg-card)',
                  borderBottom: '2px solid var(--border-color)',
                  zIndex: 10,
                  color: 'var(--text-secondary)'
                }}
              >
                <tr>
                  <th style={{ padding: '0.65rem 0.75rem', width: '40px', textAlign: 'center' }}>
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={handleToggleSelectAll}
                      disabled={processing}
                      style={{ cursor: 'pointer' }}
                    />
                  </th>
                  <th style={{ padding: '0.65rem 0.75rem' }}>Nama Berkas Asli</th>
                  <th style={{ padding: '0.65rem 0.75rem', width: '130px' }}>Tanggal Asli</th>
                  <th style={{ padding: '0.65rem 0.75rem', width: '160px' }}>Tanggal Baru</th>
                  <th style={{ padding: '0.65rem 0.75rem' }}>Pratinjau Nama Berkas Baru</th>
                  <th style={{ padding: '0.65rem 0.75rem', width: '110px', textAlign: 'center' }}>Status</th>
                  <th style={{ padding: '0.65rem 0.75rem', width: '50px', textAlign: 'center' }}>Aksi</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, idx) => {
                  const previewName = computePreviewFilename(item.filename, item.new_date);
                  const isModified = previewName !== item.filename;

                  return (
                    <tr
                      key={item.path || idx}
                      style={{
                        borderBottom: '1px solid var(--border-color)',
                        background: item.selected ? 'transparent' : 'rgba(0, 0, 0, 0.05)',
                        opacity: item.selected ? 1 : 0.65
                      }}
                    >
                      {/* Checkbox */}
                      <td style={{ padding: '0.65rem 0.75rem', textAlign: 'center' }}>
                        <input
                          type="checkbox"
                          checked={item.selected}
                          onChange={() => handleToggleSelectItem(idx)}
                          disabled={processing}
                          style={{ cursor: 'pointer' }}
                        />
                      </td>

                      {/* Nama Asli */}
                      <td style={{ padding: '0.65rem 0.75rem', color: 'var(--text-primary)', fontWeight: 500, wordBreak: 'break-all' }}>
                        {item.filename}
                      </td>

                      {/* Tanggal Terdeteksi */}
                      <td style={{ padding: '0.65rem 0.75rem' }}>
                        {item.detected_date ? (
                          <span
                            style={{
                              display: 'inline-block',
                              padding: '0.2rem 0.45rem',
                              borderRadius: '4px',
                              background: 'rgba(59, 130, 246, 0.12)',
                              color: '#3b82f6',
                              fontWeight: 600,
                              fontSize: '0.775rem'
                            }}
                          >
                            {item.detected_date}
                          </span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>-</span>
                        )}
                      </td>

                      {/* Input Tanggal Baru */}
                      <td style={{ padding: '0.65rem 0.75rem' }}>
                        <input
                          type="date"
                          value={item.new_date || ''}
                          onChange={(e) => handleUpdateItemDate(idx, e.target.value)}
                          disabled={processing || !item.selected}
                          style={{
                            padding: '0.25rem 0.45rem',
                            borderRadius: '5px',
                            border: '1px solid var(--border-color)',
                            background: 'var(--bg-input, var(--bg-secondary))',
                            color: 'var(--text-primary)',
                            fontSize: '0.8rem',
                            outline: 'none',
                            width: '100%',
                            boxSizing: 'border-box'
                          }}
                        />
                      </td>

                      {/* Pratinjau Nama Baru */}
                      <td
                        style={{
                          padding: '0.65rem 0.75rem',
                          color: isModified ? 'var(--accent)' : 'var(--text-secondary)',
                          fontWeight: isModified ? 600 : 400,
                          wordBreak: 'break-all'
                        }}
                      >
                        {previewName}
                      </td>

                      {/* Status */}
                      <td style={{ padding: '0.65rem 0.75rem', textAlign: 'center' }}>
                        {item.execution_status === 'processing' && (
                          <span style={{ color: '#eab308', fontWeight: 600, fontSize: '0.75rem' }}>⏳ Memproses...</span>
                        )}
                        {item.execution_status === 'success' && (
                          <span style={{ color: '#22c55e', fontWeight: 600, fontSize: '0.75rem' }}>✓ Berhasil</span>
                        )}
                        {item.execution_status === 'error' && (
                          <span style={{ color: '#ef4444', fontWeight: 600, fontSize: '0.75rem' }} title={item.error_msg || 'Gagal'}>
                            ✗ Gagal
                          </span>
                        )}
                        {item.execution_status === 'ready' && (
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Siap</span>
                        )}
                      </td>

                      {/* Aksi Hapus */}
                      <td style={{ padding: '0.65rem 0.75rem', textAlign: 'center' }}>
                        <button
                          onClick={() => handleRemoveItem(idx)}
                          disabled={processing}
                          style={{
                            background: 'transparent',
                            border: 'none',
                            color: 'var(--text-muted)',
                            cursor: 'pointer',
                            fontSize: '0.9rem'
                          }}
                          title="Hapus dari daftar"
                        >
                          ✕
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── BOTTOM ACTION BAR ── */}
      {items.length > 0 && (
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            borderRadius: '10px',
            padding: '0.85rem 1.25rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '1rem',
            flexWrap: 'wrap'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Total <strong>{selectedCount}</strong> berkas siap diproses.
            </span>
            {createBackup && (
              <span style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', borderRadius: '4px', background: 'rgba(234, 179, 8, 0.15)', color: '#ca8a04', fontWeight: 500 }}>
                Mode Cadangan (.bak) Aktif
              </span>
            )}
          </div>

          <button
            onClick={handleExecute}
            disabled={processing || selectedCount === 0}
            style={{
              padding: '0.65rem 1.5rem',
              background: (processing || selectedCount === 0) ? 'var(--bg-secondary)' : 'linear-gradient(135deg, #FF7300 0%, #E05300 100%)',
              color: (processing || selectedCount === 0) ? 'var(--text-muted)' : '#ffffff',
              border: 'none',
              borderRadius: '8px',
              cursor: (processing || selectedCount === 0) ? 'not-allowed' : 'pointer',
              fontSize: '0.875rem',
              fontWeight: 700,
              boxShadow: (processing || selectedCount === 0) ? 'none' : '0 3px 8px rgba(255, 115, 0, 0.3)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}
          >
            {processing ? '⏳ Sedang Memproses...' : `🚀 Mulai Ubah Tanggal (${selectedCount} Berkas)`}
          </button>
        </div>
      )}
        </div>
      )}
    </div>
  );
}
