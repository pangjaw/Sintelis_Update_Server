// =============================================================================
// ScheduleSheetPanel.jsx — Panel Tabel Interaktif Schedule Sheet & Ekspor Excel
// Diadopsi dari OCR-FOTO-P3STE untuk Sintelis Utility Desktop App
// =============================================================================

import React, { useState, useEffect, useMemo } from 'react';

export default function ScheduleSheetPanel({ targetDir, exportDir, onPickFolder, schedulePath = '', onScheduleChange, onTargetDirChange, syncVersion = 0, onScheduleGenerated }) {
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [scheduleData, setScheduleData] = useState(null);
  const [sourcePath, setSourcePath] = useState('');
  const [feedback, setFeedback] = useState(null);

  // Filters
  const [timFilter, setTimFilter] = useState('ALL'); // 'ALL' | '1' | '2' | '3'
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('ALL');

  const [compactBanner, setCompactBanner] = useState(false);

  // Folder & File Selection State (Default menggunakan folder yang di-set di pipeline)
  const [activeTargetDir, setActiveTargetDir] = useState(targetDir || '');
  const [activeExportDir, setActiveExportDir] = useState(exportDir || '');
  const [activeScheduleFile, setActiveScheduleFile] = useState(schedulePath || '');
  const [isCustomMode, setIsCustomMode] = useState(false);
  const [splitMultiAssetRows, setSplitMultiAssetRows] = useState(true);

  // Sinkronisasi otomatis dari props pipeline jika belum dalam mode kustom, dan reset saat folder target atau pipeline berubah
  useEffect(() => {
    setIsCustomMode(false);
    setActiveTargetDir(targetDir || '');
    setActiveExportDir(exportDir || '');
    setActiveScheduleFile(schedulePath || '');
  }, [targetDir, syncVersion]);

  useEffect(() => {
    if (!isCustomMode) {
      setActiveExportDir(exportDir || '');
      setActiveScheduleFile(schedulePath || '');
    }
  }, [exportDir, schedulePath, isCustomMode]);

  // Handler memilih folder target PDF secara mandiri
  const handlePickTargetFolder = async () => {
    try {
      const res = await fetch('/api/select-folder', { method: 'POST' });
      const data = await res.json();
      if (data && data.path) {
        setActiveTargetDir(data.path);
        setIsCustomMode(true);
        if (onTargetDirChange) onTargetDirChange(data.path);
        setFeedback({ type: 'info', text: `📁 Folder target PDF diatur ke: ${data.path}` });
      }
    } catch (err) {
      alert('Gagal memilih folder: ' + err.message);
    }
  };

  // Handler memilih berkas schedule.json spesifik
  const handlePickScheduleFile = async () => {
    try {
      const res = await fetch('/api/select-file', { method: 'POST' });
      const data = await res.json();
      if (data && data.path) {
        const filePath = data.path.trim();
        setActiveScheduleFile(filePath);
        setIsCustomMode(true);
        if (onScheduleChange) onScheduleChange(filePath);
        
        // Jika folder target masih kosong, otomatis isi dengan direktori induk file schedule
        let targetCandidate = activeTargetDir;
        if (!targetCandidate) {
          const parentDir = filePath.replace(/[\\/][^\\/]+$/, '');
          if (parentDir) {
            targetCandidate = parentDir;
            setActiveTargetDir(parentDir);
          }
        }
        
        setFeedback({ type: 'info', text: `📄 Berkas jadwal dipilih: ${filePath}` });
        // Langsung muat daftar jadwal dengan path yang baru dipilih
        fetchScheduleList(targetCandidate, undefined, filePath);
      }
    } catch (err) {
      alert('Gagal memilih berkas: ' + err.message);
    }
  };

  // Handler reset kembali ke folder bawaan Pipeline Runner
  const handleResetToPipeline = () => {
    setActiveTargetDir(targetDir || '');
    setActiveExportDir(exportDir || '');
    setActiveScheduleFile(schedulePath || '');
    setIsCustomMode(false);
    if (onScheduleChange) onScheduleChange(schedulePath || '');
    setFeedback({ type: 'info', text: '🔄 Lokasi dikembalikan ke pengaturan default Pipeline Runner.' });
    fetchScheduleList(targetDir || '', exportDir || '', schedulePath || '');
  };

  // 1. Ambil data schedule dari backend
  const fetchScheduleList = async (overrideTarget, overrideExport, overrideSched) => {
    const tDir = overrideTarget !== undefined ? overrideTarget : activeTargetDir;
    const eDir = overrideExport !== undefined ? overrideExport : activeExportDir;
    const sFile = overrideSched !== undefined ? overrideSched : activeScheduleFile;

    setLoading(true);
    setFeedback(null);
    try {
      const params = new URLSearchParams();
      if (tDir) params.append('folder', tDir);
      if (eDir) params.append('exportDir', eDir);
      if (sFile) params.append('schedule', sFile);
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

  // Generate Schedule On-demand menggunakan activeTargetDir
  const handleGenerateSchedule = async () => {
    if (!activeTargetDir) {
      alert('Silakan pilih Folder PDF Target terlebih dahulu!');
      return;
    }
    if (rows.length > 0) {
      const ok = window.confirm(`Jadwal saat ini sudah memuat ${rows.length} data aset.\nMenyusun ulang jadwal dari ratusan berkas PDF jaringan dapat memakan waktu 30-60 detik.\n\nApakah Anda yakin ingin menyusun ulang (re-generate) jadwal?`);
      if (!ok) return;
    }
    setGenerating(true);
    setFeedback(null);
    try {
      const res = await fetch('/api/timemark/generate-schedule', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pdfDir: activeTargetDir,
          exportDir: activeExportDir || activeTargetDir,
          splitMultiAssetRows: splitMultiAssetRows
        })
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        setScheduleData(data.data);
        setSourcePath(data.source || '');
        setFeedback({ type: 'success', text: `✓ ${data.message}` });
        if (onScheduleGenerated) onScheduleGenerated();
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
  }, [activeTargetDir, activeExportDir, activeScheduleFile, syncVersion]);

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
      if (timFilter === '3' && r.tim !== 3) return false;

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

  // Ekspor ke format JSON (schedule.json) untuk digunakan kembali di Pipeline atau folder parsial
  const handleExportScheduleJson = async () => {
    setExporting(true);
    setFeedback(null);
    try {
      const res = await fetch('/api/timemark/export-schedule-json', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          folder: activeTargetDir,
          exportDir: activeExportDir,
          customJson: scheduleData || undefined
        })
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        setFeedback({
          type: 'success',
          text: `🎉 Berkas schedule.json berhasil disimpan ke: ${data.path}`
        });
      } else if (!data.cancelled) {
        setFeedback({ type: 'error', text: data.error || 'Gagal mengekspor berkas schedule.json' });
      }
    } catch (err) {
      setFeedback({ type: 'error', text: 'Galat ekspor schedule.json: ' + err.message });
    } finally {
      setExporting(false);
    }
  };

  // 3. Ekspor ke Excel (.xlsx)
  const handleExportExcel = async () => {
    setExporting(true);
    setFeedback(null);
    try {
      const res = await fetch('/api/timemark/export-schedule-excel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder: activeTargetDir })
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
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, width: '100%', height: '100%', minHeight: 0, gap: '0.65rem', overflow: 'hidden' }}>
      
      {/* ── HEADER BANNER ── */}
      <div
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          borderRadius: '10px',
          padding: compactBanner ? '0.6rem 1rem' : '0.85rem 1.25rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '0.85rem',
          transition: 'all 0.2s ease'
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '1.2rem' }}>📅</span>
            <h3 style={{ margin: 0, fontSize: '1.02rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Schedule Sheet & Daftar Jadwal Perawatan
            </h3>
            {sourcePath && (
              <span style={{ fontSize: '0.72rem', padding: '0.15rem 0.5rem', borderRadius: '4px', background: 'rgba(34, 197, 94, 0.12)', color: '#22c55e', border: '1px solid rgba(34, 197, 94, 0.25)', fontWeight: 600 }}>
                {rows.length} Rekord
              </span>
            )}
            <button
              type="button"
              onClick={() => setCompactBanner(!compactBanner)}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                fontSize: '0.72rem',
                textDecoration: 'underline',
                padding: '0 0.3rem'
              }}
              title="Ciutkan / perluas deskripsi banner agar ruang tabel lebih maksimal"
            >
              {compactBanner ? '▾ Tampilkan Deskripsi' : '▴ Ciutkan Header'}
            </button>
          </div>
          {!compactBanner && (
            <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Matriks alokasi waktu kerja, pembagian Tim 1/Tim 2/Tim 3, dan rincian stempel foto (0%, 50%, 100%) hasil Step 3 Penjadwalan.
            </p>
          )}
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
            onClick={handleExportScheduleJson}
            disabled={exporting || (!scheduleData && rows.length === 0)}
            style={{
              padding: '0.45rem 0.95rem',
              background: (exporting || (!scheduleData && rows.length === 0)) ? 'var(--bg-secondary)' : '#6366f1',
              color: (exporting || (!scheduleData && rows.length === 0)) ? 'var(--text-muted)' : '#ffffff',
              border: 'none',
              borderRadius: '7px',
              cursor: (exporting || (!scheduleData && rows.length === 0)) ? 'not-allowed' : 'pointer',
              fontSize: '0.825rem',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              boxShadow: (exporting || (!scheduleData && rows.length === 0)) ? 'none' : '0 2px 6px rgba(99, 102, 241, 0.25)'
            }}
            title="Ekspor dan simpan struktur jadwal (schedule.json) ke berkas eksternal"
          >
            {exporting ? '⏳ Mengekspor...' : '💾 Ekspor schedule.json'}
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

      {/* ── PANEL KONTROL SUMBER FOLDER / FILE JADWAL ── */}
      <div
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          borderRadius: '10px',
          padding: '0.85rem 1.15rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.65rem',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.05)'
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              📂 Lokasi Sumber PDF & Jadwal
            </span>
            <span
              style={{
                fontSize: '0.7rem',
                fontWeight: 700,
                padding: '0.15rem 0.5rem',
                borderRadius: '4px',
                background: isCustomMode ? 'rgba(245, 158, 11, 0.15)' : 'rgba(59, 130, 246, 0.15)',
                color: isCustomMode ? '#f59e0b' : '#3b82f6',
                border: isCustomMode ? '1px solid rgba(245, 158, 11, 0.3)' : '1px solid rgba(59, 130, 246, 0.3)'
              }}
            >
              {isCustomMode ? '⚙️ Folder Kustom (Luar Pipeline)' : '🔗 Default Pipeline Runner'}
            </span>
          </div>

          {isCustomMode && (
            <button
              type="button"
              onClick={handleResetToPipeline}
              style={{
                background: 'transparent',
                border: '1px solid var(--border-color)',
                borderRadius: '5px',
                color: 'var(--text-secondary)',
                fontSize: '0.725rem',
                fontWeight: 600,
                cursor: 'pointer',
                padding: '0.25rem 0.6rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.3rem'
              }}
              title="Kembalikan lokasi ke folder target yang sedang aktif di Pipeline Runner"
            >
              🔄 Reset ke Default Pipeline
            </button>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '0.75rem' }}>
          {/* Kolom 1: Folder PDF Target */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            <label style={{ fontSize: '0.725rem', fontWeight: 600, color: 'var(--text-muted)' }}>
              Folder PDF Target (Checklist / Folder Lain):
            </label>
            <div style={{ display: 'flex', gap: '0.35rem' }}>
              <input
                type="text"
                readOnly
                value={activeTargetDir || ''}
                placeholder="Belum ada folder target..."
                style={{
                  flex: 1,
                  padding: '0.35rem 0.6rem',
                  fontSize: '0.775rem',
                  borderRadius: '5px',
                  background: 'var(--bg-secondary)',
                  border: '1px solid var(--border-color)',
                  color: activeTargetDir ? 'var(--text-primary)' : 'var(--text-muted)'
                }}
              />
              <button
                type="button"
                onClick={handlePickTargetFolder}
                style={{
                  padding: '0.35rem 0.65rem',
                  background: 'var(--accent)',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '5px',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.25rem'
                }}
                title="Pilih folder PDF target checklist (bisa dari folder mana saja di luar pipeline)"
              >
                📂 Pilih Folder
              </button>
            </div>
          </div>

          {/* Kolom 2: Berkas Jadwal Spesifik / schedule.json */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            <label style={{ fontSize: '0.725rem', fontWeight: 600, color: 'var(--text-muted)' }}>
              Berkas Jadwal (schedule.json) Spesifik:
            </label>
            <div style={{ display: 'flex', gap: '0.35rem' }}>
              <input
                type="text"
                readOnly
                value={activeScheduleFile || (sourcePath ? sourcePath : '')}
                placeholder="Otomatis dari folder target (atau pilih file json)..."
                style={{
                  flex: 1,
                  padding: '0.35rem 0.6rem',
                  fontSize: '0.775rem',
                  borderRadius: '5px',
                  background: 'var(--bg-secondary)',
                  border: '1px solid var(--border-color)',
                  color: (activeScheduleFile || sourcePath) ? 'var(--text-primary)' : 'var(--text-muted)'
                }}
              />
              <button
                type="button"
                onClick={handlePickScheduleFile}
                style={{
                  padding: '0.35rem 0.65rem',
                  background: 'rgba(99, 102, 241, 0.2)',
                  color: '#818cf8',
                  border: '1px solid rgba(99, 102, 241, 0.4)',
                  borderRadius: '5px',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.25rem'
                }}
                title="Pilih berkas schedule.json yang sudah ada dari direktori manapun"
              >
                📄 Pilih File .json
              </button>
            </div>
          </div>
        </div>

        {/* Opsi Alokasi Jam per OTB (Serat Optik) & Multi-Row (PDSE) */}
        <div
          style={{
            marginTop: '0.2rem',
            padding: '0.45rem 0.75rem',
            borderRadius: '6px',
            background: splitMultiAssetRows ? 'rgba(59, 130, 246, 0.1)' : 'var(--bg-secondary)',
            border: splitMultiAssetRows ? '1px solid rgba(59, 130, 246, 0.3)' : '1px solid var(--border-color)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '0.5rem',
            transition: 'all 0.15s ease'
          }}
        >
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={splitMultiAssetRows}
              onChange={e => setSplitMultiAssetRows(e.target.checked)}
              style={{ accentColor: '#3b82f6', cursor: 'pointer', width: '15px', height: '15px' }}
            />
            <div>
              <span style={{ fontSize: '0.785rem', fontWeight: 700, color: splitMultiAssetRows ? '#60a5fa' : 'var(--text-primary)' }}>
                📑 Bagi Jam per OTB (Serat Optik 6 mnt/core) & Multi-Row (PDSE 420 mnt)
              </span>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginLeft: '0.4rem' }}>
                — Membagi slot waktu mandiri untuk setiap OTB (0%, 50%, 100%) berdasarkan jumlah core, bukan 1 jam flat per PDF.
              </span>
            </div>
          </label>
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
          padding: '0.65rem 0.95rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '0.75rem',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)'
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
            <button
              type="button"
              onClick={() => setTimFilter('3')}
              style={{
                padding: '0.3rem 0.65rem',
                borderRadius: '5px',
                border: 'none',
                background: timFilter === '3' ? '#3b82f6' : 'transparent',
                color: timFilter === '3' ? '#ffffff' : 'var(--text-secondary)',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              Tim 3 ({rows.filter(r => r.tim === 3).length})
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
          background: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          borderRadius: '10px',
          display: 'flex',
          flexDirection: 'column',
          width: '100%',
          minHeight: '400px',
          boxShadow: '0 2px 10px rgba(0, 0, 0, 0.08)'
        }}
      >
        {filteredRows.length === 0 ? (
          <div
            style={{
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
          <div style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            overflowX: 'auto',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            background: 'var(--bg-card)',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)'
          }}>
            <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: 0, textAlign: 'left', fontSize: '0.785rem' }}>
              <thead
                style={{
                  position: 'sticky',
                  top: 0,
                  zIndex: 25,
                  background: 'var(--bg-secondary)',
                  boxShadow: '0 2px 6px rgba(0, 0, 0, 0.2)'
                }}
              >
                <tr>
                  <th style={{ position: 'sticky', top: 0, background: 'var(--bg-secondary)', zIndex: 26, padding: '0.55rem 0.65rem', width: '45px', textAlign: 'center', borderBottom: '2px solid var(--border-color)', color: 'var(--text-secondary)', fontSize: '0.735rem' }}>No</th>
                  <th style={{ position: 'sticky', top: 0, background: 'var(--bg-secondary)', zIndex: 26, padding: '0.55rem 0.75rem', width: '130px', borderBottom: '2px solid var(--border-color)', color: 'var(--text-secondary)', fontSize: '0.735rem' }}>Tanggal</th>
                  <th style={{ position: 'sticky', top: 0, background: 'var(--bg-secondary)', zIndex: 26, padding: '0.55rem 0.65rem', width: '65px', textAlign: 'center', borderBottom: '2px solid var(--border-color)', color: 'var(--text-secondary)', fontSize: '0.735rem' }}>Tim</th>
                  <th style={{ position: 'sticky', top: 0, background: 'var(--bg-secondary)', zIndex: 26, padding: '0.55rem 0.65rem', width: '130px', textAlign: 'center', borderBottom: '2px solid var(--border-color)', color: 'var(--text-secondary)', fontSize: '0.735rem' }}>Jam (0% - 50% - 100%)</th>
                  <th style={{ position: 'sticky', top: 0, background: 'var(--bg-secondary)', zIndex: 26, padding: '0.55rem 0.75rem', width: '90px', borderBottom: '2px solid var(--border-color)', color: 'var(--text-secondary)', fontSize: '0.735rem' }}>Wilayah</th>
                  <th style={{ position: 'sticky', top: 0, background: 'var(--bg-secondary)', zIndex: 26, padding: '0.55rem 0.75rem', width: '110px', borderBottom: '2px solid var(--border-color)', color: 'var(--text-secondary)', fontSize: '0.735rem' }}>Kategori</th>
                  <th style={{ position: 'sticky', top: 0, background: 'var(--bg-secondary)', zIndex: 26, padding: '0.55rem 0.75rem', borderBottom: '2px solid var(--border-color)', color: 'var(--text-secondary)', fontSize: '0.735rem' }}>Detail Aset / Identifier</th>
                  <th style={{ position: 'sticky', top: 0, background: 'var(--bg-secondary)', zIndex: 26, padding: '0.55rem 0.75rem', borderBottom: '2px solid var(--border-color)', color: 'var(--text-secondary)', fontSize: '0.735rem' }}>Berkas PDF</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((r, idx) => (
                  <tr
                    key={r.no || idx}
                    style={{
                      borderBottom: '1px solid var(--border-color)',
                      background: r.tim === 1 ? 'rgba(34, 197, 94, 0.02)' : (r.tim === 2 ? 'rgba(245, 158, 11, 0.02)' : 'rgba(59, 130, 246, 0.03)'),
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
                          background: r.tim === 1 ? 'rgba(34, 197, 94, 0.15)' : (r.tim === 2 ? 'rgba(245, 158, 11, 0.15)' : 'rgba(59, 130, 246, 0.15)'),
                          color: r.tim === 1 ? '#22c55e' : (r.tim === 2 ? '#f59e0b' : '#60a5fa')
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
