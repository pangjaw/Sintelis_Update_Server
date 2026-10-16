// =============================================================================
// ScheduleSheetPanel.jsx — Panel Tabel Interaktif Schedule Sheet & Ekspor Excel
// Diadopsi dari OCR-FOTO-P3STE untuk Sintelis Utility Desktop App
// =============================================================================

import React, { useState, useEffect, useMemo } from 'react';

export default function ScheduleSheetPanel({ targetDir, exportDir, onPickFolder }) {
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [scheduleData, setScheduleData] = useState(null);
  const [sourcePath, setSourcePath] = useState('');
  const [feedback, setFeedback] = useState(null);

  // Filters
  const [timFilter, setTimFilter] = useState('ALL'); // 'ALL' | '1' | '2'
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('ALL');

  // 1. Ambil data schedule dari backend
  const fetchScheduleList = async () => {
    setLoading(true);
    setFeedback(null);
    try {
      const params = new URLSearchParams();
      if (targetDir) params.append('folder', targetDir);
      if (exportDir) params.append('exportDir', exportDir);
      const q = params.toString() ? `?${params.toString()}` : '';
      const res = await fetch(`/api/timemark/schedule-list${q}`);
      const data = await res.json();
      if (res.ok && data.ok) {
        setScheduleData(data.data);
        setSourcePath(data.source || '');
      } else {
        setScheduleData(null);
        setFeedback({
          type: 'info',
          text: data.error || 'Berkas jadwal (schedule.json) belum ditemukan. Anda dapat membuat jadwal secara otomatis dengan mengklik tombol "⚡ Buat Schedule Otomatis".'
        });
      }
    } catch (err) {
      setFeedback({ type: 'error', text: 'Galat memuat jadwal: ' + err.message });
    } finally {
      setLoading(false);
    }
  };

  // Generate Schedule On-demand
  const handleGenerateSchedule = async () => {
    setGenerating(true);
    setFeedback(null);
    try {
      const res = await fetch('/api/timemark/generate-schedule', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pdfDir: targetDir,
          exportDir: exportDir
        })
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        setScheduleData(data.data);
        setSourcePath(data.source || '');
        setFeedback({ type: 'success', text: `✓ ${data.message}` });
      } else {
        setFeedback({ type: 'error', text: data.error || 'Gagal membuat jadwal.' });
      }
    } catch (err) {
      setFeedback({ type: 'error', text: 'Galat generate jadwal: ' + err.message });
    } finally {
      setGenerating(false);
    }
  };

  useEffect(() => {
    fetchScheduleList();
  }, [targetDir, exportDir]);

  // 2. Parse rekord jadwal ke daftar baris tabel yang seragam
  const rows = useMemo(() => {
    if (!scheduleData) return [];

    const result = [];
    let counter = 1;

    // A. Format standar schedule.json (ada array 'schedules')
    if (scheduleData.schedules && Array.isArray(scheduleData.schedules)) {
      scheduleData.schedules.forEach(item => {
        const file = item.file || '';
        const date = item.date || '';
        const tim = item.tim || 1;
        const btp = item.btp || 'BTP JAK';
        const category = item.category || '-';
        const duration = item.waktu_menit || 45;

        // Cek assets anak atau single item
        if (item.assets && Array.isArray(item.assets) && item.assets.length > 0) {
          item.assets.forEach(asset => {
            const photos = asset.photos || {};
            const t0 = photos['0.jpg'] ? photos['0.jpg'].split('T')[1]?.slice(0, 5) : '';
            const t50 = photos['50.jpg'] ? photos['50.jpg'].split('T')[1]?.slice(0, 5) : '';
            const t100 = photos['100.jpg'] ? photos['100.jpg'].split('T')[1]?.slice(0, 5) : '';

            result.push({
              no: counter++,
              file,
              date,
              tim,
              btp,
              category: asset.type || category,
              detail_aset: asset.detail || asset.code || '-',
              code: asset.code || '-',
              duration: asset.waktu_menit || duration,
              jam0: t0 || '-',
              jam50: t50 || '-',
              jam100: t100 || '-',
              rentang: (t0 && t100) ? `${t0} - ${t100}` : '-',
              personnel: item.personnel || []
            });
          });
        } else {
          // Format single flat schedule record
          const photos = item.photos || {};
          const t0 = photos['0.jpg'] ? photos['0.jpg'].split('T')[1]?.slice(0, 5) : '';
          const t50 = photos['50.jpg'] ? photos['50.jpg'].split('T')[1]?.slice(0, 5) : '';
          const t100 = photos['100.jpg'] ? photos['100.jpg'].split('T')[1]?.slice(0, 5) : '';

          result.push({
            no: counter++,
            file,
            date,
            tim,
            btp,
            category,
            detail_aset: item.identifier || item.detail || '-',
            code: item.code || '-',
            duration,
            jam0: t0 || '-',
            jam50: t50 || '-',
            jam100: t100 || '-',
            rentang: (t0 && t100) ? `${t0} - ${t100}` : '-',
            personnel: item.personnel || []
          });
        }
      });
    } else if (scheduleData.files && Array.isArray(scheduleData.files)) {
      // B. Format fallback dari file_personnel_cache.json
      scheduleData.files.forEach(item => {
        result.push({
          no: item.no || counter++,
          file: item.file || '',
          date: item.date || item.iso_date || '-',
          tim: item.tim || 1,
          btp: item.btp || 'BTP JAK',
          category: item.category || '-',
          detail_aset: item.detail_aset || item.detail || '-',
          code: item.code || '-',
          duration: 45,
          jam0: '-',
          jam50: '-',
          jam100: '-',
          rentang: '-',
          personnel: item.personnel || []
        });
      });
    }

    return result;
  }, [scheduleData]);

  // Kategori unik untuk dropdown filter
  const availableCategories = useMemo(() => {
    const set = new Set();
    rows.forEach(r => {
      if (r.category && r.category !== '-') set.add(r.category);
    });
    return Array.from(set).sort();
  }, [rows]);

  // Filtered rows
  const filteredRows = useMemo(() => {
    return rows.filter(r => {
      // Filter Tim
      if (timFilter === '1' && r.tim !== 1) return false;
      if (timFilter === '2' && r.tim !== 2) return false;

      // Filter Kategori
      if (categoryFilter !== 'ALL' && r.category !== categoryFilter) return false;

      // Filter Pencarian Teks Bebas
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const str = `${r.file} ${r.date} ${r.category} ${r.detail_aset} ${r.btp} ${Array.isArray(r.personnel) ? r.personnel.join(' ') : ''}`.toLowerCase();
        if (!str.includes(q)) return false;
      }

      return true;
    });
  }, [rows, timFilter, categoryFilter, searchQuery]);

  // 3. Ekspor ke Excel (.xlsx)
  const handleExportExcel = async () => {
    setExporting(true);
    setFeedback(null);
    try {
      const res = await fetch('/api/timemark/export-schedule-excel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder: targetDir })
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        setFeedback({
          type: 'success',
          text: `🎉 Laporan Jadwal Perawatan Excel berhasil disimpan ke: ${data.path}`
        });
      } else if (!data.cancelled) {
        setFeedback({ type: 'error', text: data.error || 'Gagal mengekspor berkas Excel' });
      }
    } catch (err) {
      setFeedback({ type: 'error', text: 'Galat ekspor Excel: ' + err.message });
    } finally {
      setExporting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', height: '100%', width: '100%', overflow: 'hidden' }}>
      
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
            <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Schedule Sheet & Daftar Jadwal Perawatan
            </h3>
            {sourcePath && (
              <span style={{ fontSize: '0.725rem', padding: '0.15rem 0.5rem', borderRadius: '4px', background: 'rgba(34, 197, 94, 0.1)', color: '#22c55e', border: '1px solid rgba(34, 197, 94, 0.2)' }}>
                {rows.length} Rekord Aset
              </span>
            )}
          </div>
          <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.825rem', color: 'var(--text-secondary)' }}>
            Matriks alokasi waktu kerja, pembagian Tim 1/Tim 2, dan rincian stempel foto (0%, 50%, 100%) hasil Step 3 Penjadwalan.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            onClick={fetchScheduleList}
            disabled={loading}
            style={{
              padding: '0.45rem 0.8rem',
              background: 'var(--bg-secondary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: '7px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: '0.8rem',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem'
            }}
          >
            {loading ? 'Memuat...' : '🔄 Segarkan'}
          </button>

          <button
            onClick={handleGenerateSchedule}
            disabled={generating}
            style={{
              padding: '0.45rem 0.85rem',
              background: generating ? 'var(--bg-secondary)' : 'rgba(59, 130, 246, 0.15)',
              color: generating ? 'var(--text-muted)' : '#3b82f6',
              border: '1px solid rgba(59, 130, 246, 0.35)',
              borderRadius: '7px',
              cursor: generating ? 'not-allowed' : 'pointer',
              fontSize: '0.8rem',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem'
            }}
            title="Bangun schedule.json secara otomatis dari berkas PDF target tanpa harus mengulang pipeline dari awal"
          >
            {generating ? '⏳ Menyusun Jadwal...' : '⚡ Buat Schedule Otomatis'}
          </button>
          
          <button
            onClick={handleExportExcel}
            disabled={exporting || rows.length === 0}
            style={{
              padding: '0.45rem 0.95rem',
              background: (exporting || rows.length === 0) ? 'var(--bg-secondary)' : '#059669',
              color: (exporting || rows.length === 0) ? 'var(--text-muted)' : '#ffffff',
              border: 'none',
              borderRadius: '7px',
              cursor: (exporting || rows.length === 0) ? 'not-allowed' : 'pointer',
              fontSize: '0.825rem',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              boxShadow: (exporting || rows.length === 0) ? 'none' : '0 2px 6px rgba(5, 150, 105, 0.25)'
            }}
          >
            {exporting ? '⏳ Mengekspor...' : '📊 Ekspor Schedule Sheet (.xlsx)'}
          </button>
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

      {/* ── FILTER TOOLBAR ── */}
      <div
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          borderRadius: '10px',
          padding: '0.75rem 1rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '0.75rem'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          {/* Filter Tim Pills */}
          <div style={{ display: 'flex', background: 'var(--bg-secondary)', borderRadius: '6px', padding: '2px', border: '1px solid var(--border-color)' }}>
            <button
              type="button"
              onClick={() => setTimFilter('ALL')}
              style={{
                padding: '0.3rem 0.65rem',
                borderRadius: '5px',
                border: 'none',
                background: timFilter === 'ALL' ? 'var(--accent)' : 'transparent',
                color: timFilter === 'ALL' ? '#ffffff' : 'var(--text-secondary)',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              Semua Tim ({rows.length})
            </button>
            <button
              type="button"
              onClick={() => setTimFilter('1')}
              style={{
                padding: '0.3rem 0.65rem',
                borderRadius: '5px',
                border: 'none',
                background: timFilter === '1' ? '#22c55e' : 'transparent',
                color: timFilter === '1' ? '#ffffff' : 'var(--text-secondary)',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              Tim 1 ({rows.filter(r => r.tim === 1).length})
            </button>
            <button
              type="button"
              onClick={() => setTimFilter('2')}
              style={{
                padding: '0.3rem 0.65rem',
                borderRadius: '5px',
                border: 'none',
                background: timFilter === '2' ? '#f59e0b' : 'transparent',
                color: timFilter === '2' ? '#ffffff' : 'var(--text-secondary)',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              Tim 2 ({rows.filter(r => r.tim === 2).length})
            </button>
          </div>

          {/* Filter Kategori */}
          {availableCategories.length > 0 && (
            <select
              value={categoryFilter}
              onChange={e => setCategoryFilter(e.target.value)}
              style={{
                padding: '0.35rem 0.6rem',
                fontSize: '0.785rem',
                borderRadius: '6px',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)'
              }}
            >
              <option value="ALL">Semua Kategori</option>
              {availableCategories.map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          )}
        </div>

        {/* Input Pencarian */}
        <div style={{ flex: '0 0 260px' }}>
          <input
            type="text"
            placeholder="Cari aset, file, tanggal..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              padding: '0.4rem 0.75rem',
              fontSize: '0.8rem',
              borderRadius: '6px',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-color)',
              color: 'var(--text-primary)',
              boxSizing: 'border-box'
            }}
          />
        </div>
      </div>

      {/* ── TABEL SCHEDULE SPREADSHEET ── */}
      <div
        style={{
          flex: 1,
          background: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          borderRadius: '10px',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0
        }}
      >
        {filteredRows.length === 0 ? (
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              alignItems: 'center',
              padding: '3rem 2rem',
              color: 'var(--text-muted)',
              fontSize: '0.85rem',
              textAlign: 'center',
              gap: '0.75rem'
            }}
          >
            {rows.length === 0 ? (
              <>
                <span style={{ fontSize: '2.5rem' }}>📅</span>
                <span style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                  Berkas Jadwal (schedule.json) Belum Ditemukan
                </span>
                <p style={{ maxWidth: '500px', margin: '0 0 0.5rem 0', color: 'var(--text-secondary)', fontSize: '0.825rem', lineHeight: '1.4' }}>
                  Jadwal pemeliharaan belum dibuat untuk folder target ini atau pipeline Step 3 belum dijalankan.
                  Anda dapat membuat berkas <code>schedule.json</code> secara otomatis sekarang tanpa harus mengulang pipeline dari Step 1.
                </p>
                <button
                  type="button"
                  onClick={handleGenerateSchedule}
                  disabled={generating}
                  style={{
                    padding: '0.6rem 1.25rem',
                    background: generating ? 'var(--bg-secondary)' : '#3b82f6',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: generating ? 'not-allowed' : 'pointer',
                    fontSize: '0.875rem',
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    boxShadow: '0 2px 8px rgba(59, 130, 246, 0.35)'
                  }}
                >
                  {generating ? '⏳ Sedang Menyusun Jadwal...' : '⚡ Buat Schedule Otomatis Sekarang'}
                </button>
              </>
            ) : (
              <>
                <span style={{ fontSize: '2rem' }}>🔍</span>
                <span>Tidak ada data jadwal yang cocok dengan kata kunci atau filter yang dipilih.</span>
              </>
            )}
          </div>
        ) : (
          <div style={{ overflowY: 'auto', flex: 1 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.785rem' }}>
              <thead
                style={{
                  position: 'sticky',
                  top: 0,
                  background: 'var(--bg-secondary)',
                  borderBottom: '1px solid var(--border-color)',
                  color: 'var(--text-secondary)',
                  fontSize: '0.735rem'
                }}
              >
                <tr>
                  <th style={{ padding: '0.55rem 0.65rem', width: '45px', textAlign: 'center' }}>No</th>
                  <th style={{ padding: '0.55rem 0.75rem', width: '130px' }}>Tanggal</th>
                  <th style={{ padding: '0.55rem 0.65rem', width: '65px', textAlign: 'center' }}>Tim</th>
                  <th style={{ padding: '0.55rem 0.65rem', width: '130px', textAlign: 'center' }}>Jam (0% - 50% - 100%)</th>
                  <th style={{ padding: '0.55rem 0.75rem', width: '90px' }}>Wilayah</th>
                  <th style={{ padding: '0.55rem 0.75rem', width: '110px' }}>Kategori</th>
                  <th style={{ padding: '0.55rem 0.75rem' }}>Detail Aset / Identifier</th>
                  <th style={{ padding: '0.55rem 0.75rem' }}>Berkas PDF</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((r, idx) => (
                  <tr
                    key={r.no || idx}
                    style={{
                      borderBottom: '1px solid var(--border-color)',
                      background: r.tim === 1 ? 'rgba(34, 197, 94, 0.02)' : 'rgba(245, 158, 11, 0.02)',
                      transition: 'background 0.15s'
                    }}
                  >
                    <td style={{ padding: '0.5rem 0.65rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                      {r.no}
                    </td>
                    <td style={{ padding: '0.5rem 0.75rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {r.date}
                    </td>
                    <td style={{ padding: '0.5rem 0.65rem', textAlign: 'center' }}>
                      <span
                        style={{
                          padding: '0.15rem 0.45rem',
                          borderRadius: '4px',
                          fontSize: '0.7rem',
                          fontWeight: 700,
                          background: r.tim === 1 ? 'rgba(34, 197, 94, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                          color: r.tim === 1 ? '#22c55e' : '#f59e0b'
                        }}
                      >
                        Tim {r.tim}
                      </span>
                    </td>
                    <td style={{ padding: '0.5rem 0.65rem', textAlign: 'center', fontFamily: 'monospace', color: 'var(--text-secondary)' }}>
                      {r.jam0 !== '-' ? (
                        <span>
                          <strong style={{ color: 'var(--text-primary)' }}>{r.jam0}</strong> &rarr; {r.jam50} &rarr; <strong style={{ color: 'var(--text-primary)' }}>{r.jam100}</strong>
                        </span>
                      ) : '-'}
                    </td>
                    <td style={{ padding: '0.5rem 0.75rem', color: 'var(--text-secondary)' }}>
                      {r.btp}
                    </td>
                    <td style={{ padding: '0.5rem 0.75rem', fontWeight: 600, color: 'var(--accent)' }}>
                      {r.category}
                    </td>
                    <td style={{ padding: '0.5rem 0.75rem', color: 'var(--text-primary)' }}>
                      {r.detail_aset}
                    </td>
                    <td style={{ padding: '0.5rem 0.75rem', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                      {r.file}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
