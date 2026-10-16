import { useState, useEffect } from 'react';

export default function ExcelExportPanel({ targetDir, exportDir }) {
  const currentYear = new Date().getFullYear();
  const currentMonth = new Date().getMonth() + 1;

  const [selectedSourceDir, setSelectedSourceDir] = useState(targetDir || exportDir || '');
  const [selectedOutputDir, setSelectedOutputDir] = useState('');
  const [exportYear, setExportYear] = useState(currentYear);
  const [exportMonth, setExportMonth] = useState(currentMonth);
  const [exportDocType, setExportDocType] = useState('both'); // 'both' | 'tablo' | 'dinasan'
  const [withPersonnel, setWithPersonnel] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);

  const [presets, setPresets] = useState([]);
  const [selectedPresetId, setSelectedPresetId] = useState('');
  const [activePresetName, setActivePresetName] = useState('');

  const [historyFiles, setHistoryFiles] = useState([]);
  const [feedback, setFeedback] = useState(null);

  useEffect(() => {
    if (!selectedSourceDir && (targetDir || exportDir)) {
      setSelectedSourceDir(targetDir || exportDir || '');
    }
  }, [targetDir, exportDir]);

  // Load employee presets on mount
  useEffect(() => {
    fetch('/api/timemark/pegawai')
      .then(res => res.json())
      .then(data => {
        if (data.ok) {
          if (data.presets && data.presets.length > 0) {
            setPresets(data.presets);
          }
          if (data.active_preset_id) {
            setSelectedPresetId(data.active_preset_id);
          } else if (data.presets && data.presets.length > 0) {
            setSelectedPresetId(data.presets[0].id);
          }
          if (data.active_preset_name) {
            setActivePresetName(data.active_preset_name);
          }
        }
      })
      .catch(err => console.error('Gagal mengambil daftar preset pegawai:', err));
  }, []);

  const handlePresetChange = async (newId) => {
    setSelectedPresetId(newId);
    const found = presets.find(p => p.id === newId);
    if (found) setActivePresetName(found.name);
    try {
      await fetch('/api/timemark/set-active-preset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ presetId: newId })
      });
    } catch (err) {
      console.warn('Gagal sinkronisasi active preset:', err);
    }
  };

  const months = [
    { num: 1, name: 'Januari' }, { num: 2, name: 'Februari' }, { num: 3, name: 'Maret' },
    { num: 4, name: 'April' }, { num: 5, name: 'Mei' }, { num: 6, name: 'Juni' },
    { num: 7, name: 'Juli' }, { num: 8, name: 'Agustus' }, { num: 9, name: 'September' },
    { num: 10, name: 'Oktober' }, { num: 11, name: 'November' }, { num: 12, name: 'Desember' }
  ];

  // Pick folder native (Sumber)
  const handlePickFolder = async () => {
    try {
      const res = await fetch('/api/select-folder', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        if (data.path) {
          setSelectedSourceDir(data.path);
        }
      }
    } catch (err) {
      alert('Gagal membuka dialog pemilihan folder: ' + err.message);
    }
  };

  // Pick file native (Sumber)
  const handlePickFile = async () => {
    try {
      const res = await fetch('/api/select-file', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        if (data.path) {
          setSelectedSourceDir(data.path);
        }
      }
    } catch (err) {
      alert('Gagal membuka dialog pemilihan berkas: ' + err.message);
    }
  };

  // Pick folder native (Output / Penyimpanan)
  const handlePickOutputDir = async () => {
    try {
      const res = await fetch('/api/select-folder', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        if (data.path) {
          setSelectedOutputDir(data.path);
        }
      }
    } catch (err) {
      alert('Gagal membuka dialog pemilihan folder output: ' + err.message);
    }
  };

  // Ekspor Dokumen Tunggal / Keduanya
  const handleExport = async () => {
    const effectiveFolder = selectedSourceDir || targetDir || exportDir;
    if (!effectiveFolder) {
      alert('Silakan tentukan Folder atau Berkas Sumber terlebih dahulu!');
      return;
    }

    setIsGenerating(true);
    setFeedback(null);
    const newFiles = [];
    const successMessages = [];

    try {
      // 1. Ekspor Tablo jika dipilih 'both' atau 'tablo'
      if (exportDocType === 'both' || exportDocType === 'tablo') {
        const resTablo = await fetch('/api/timemark/export-tablo', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            folder: effectiveFolder,
            exportDir: exportDir || effectiveFolder,
            outputDir: selectedOutputDir || undefined,
            year: exportYear,
            month: exportMonth,
            presetId: selectedPresetId || undefined
          })
        });
        const dataTablo = await resTablo.json();
        if (resTablo.ok && dataTablo.ok) {
          successMessages.push(`✓ Tablo Checklist: ${dataTablo.filePath}`);
          if (dataTablo.filePath) newFiles.push(dataTablo.filePath);
        } else {
          throw new Error(`Gagal membuat Tablo: ${dataTablo.error || 'Terjadi kesalahan'}`);
        }
      }

      // 2. Ekspor Jadwal Dinasan jika dipilih 'both' atau 'dinasan'
      if (exportDocType === 'both' || exportDocType === 'dinasan') {
        const resDinasan = await fetch('/api/timemark/export-dinasan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            folder: effectiveFolder,
            exportDir: exportDir || effectiveFolder,
            outputDir: selectedOutputDir || undefined,
            year: exportYear,
            month: exportMonth,
            withPersonnel,
            presetId: selectedPresetId || undefined
          })
        });
        const dataDinasan = await resDinasan.json();
        if (resDinasan.ok && dataDinasan.ok) {
          successMessages.push(`✓ Jadwal Dinasan: ${dataDinasan.filePath}`);
          if (dataDinasan.filePath) newFiles.push(dataDinasan.filePath);
        } else {
          throw new Error(`Gagal membuat Jadwal Dinasan: ${dataDinasan.error || 'Terjadi kesalahan'}`);
        }
      }

      setFeedback({
        type: 'success',
        text: successMessages.join('\n')
      });

      if (newFiles.length > 0) {
        setHistoryFiles(prev => [...newFiles, ...prev.filter(f => !newFiles.includes(f))]);
      }
    } catch (err) {
      setFeedback({
        type: 'error',
        text: 'Galat pembuatan dokumen: ' + err.message
      });
    } finally {
      setIsGenerating(false);
    }
  };

  // Buka file di Windows Explorer
  const handleOpenFile = async (filePath) => {
    try {
      await fetch('/api/timemark/open-file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filePath })
      });
    } catch (err) {
      alert('Gagal membuka berkas: ' + err.message);
    }
  };

  // Label dinamis untuk tombol eksekusi
  const getButtonLabel = () => {
    if (isGenerating) return 'Memproses Dokumen Excel...';
    if (exportDocType === 'both') return '⚡ Buat Tablo & Jadwal Dinasan Excel';
    if (exportDocType === 'tablo') return '⚡ Buat Tablo Checklist Excel';
    return '⚡ Buat Jadwal Dinasan Excel';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', height: '100%', width: '100%', overflowY: 'auto', paddingRight: '0.5rem' }}>
      
      {/* Header Info */}
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem 1.25rem', width: '100%' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span>📊</span> Ekspor Dokumen Resmi Excel
        </h3>
        <p style={{ fontSize: '0.825rem', color: 'var(--text-secondary)', margin: '0.25rem 0 0 0' }}>
          Mencetak formulir KAI resmi Tablo Checklist (Form STE-RECORD-13.4.01) dan Jadwal Dinasan Pegawai yang otomatis sinkron dengan profil personil aktif.
        </p>
      </div>

      {/* Pemilihan Folder / Berkas Sumber Dokumen */}
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem 1.25rem', width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
          <label style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <span>📁</span> Sumber Berkas / Folder (PDF atau Jadwal):
          </label>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            Folder PDF target/sumber, atau file PDF / schedule.json spesifik
          </span>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <input
            type="text"
            value={selectedSourceDir}
            onChange={e => setSelectedSourceDir(e.target.value)}
            placeholder="Pilih folder sumber PDF atau berkas jadwal..."
            style={{
              flex: '1 1 300px',
              padding: '0.55rem 0.85rem',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-color)',
              borderRadius: '6px',
              color: 'var(--text-primary)',
              fontSize: '0.85rem',
              fontFamily: 'monospace'
            }}
          />
          <button
            onClick={handlePickFolder}
            title="Pilih folder sumber PDF target atau folder jadwal"
            style={{
              padding: '0.55rem 1rem',
              background: 'var(--bg-card-hover)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: '6px',
              cursor: 'pointer',
              fontWeight: 500,
              fontSize: '0.825rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem'
            }}
          >
            <span>📂</span> Pilih Folder...
          </button>
          <button
            onClick={handlePickFile}
            title="Pilih file PDF atau file schedule.json spesifik"
            style={{
              padding: '0.55rem 1rem',
              background: 'var(--bg-card-hover)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: '6px',
              cursor: 'pointer',
              fontWeight: 500,
              fontSize: '0.825rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem'
            }}
          >
            <span>📄</span> Pilih Berkas...
          </button>
        </div>
      </div>

      {/* Pemilihan Folder Output Penyimpanan */}
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem 1.25rem', width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
          <label style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <span>💾</span> Folder Simpan Output Excel:
          </label>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            {selectedOutputDir ? 'Folder penyimpanan kustom dipilih' : 'Kosong = otomatis disimpan ke folder logs/'}
          </span>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <input
            type="text"
            value={selectedOutputDir}
            onChange={e => setSelectedOutputDir(e.target.value)}
            placeholder="Default (otomatis disimpan ke folder logs)..."
            style={{
              flex: '1 1 300px',
              padding: '0.55rem 0.85rem',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-color)',
              borderRadius: '6px',
              color: 'var(--text-primary)',
              fontSize: '0.85rem',
              fontFamily: 'monospace'
            }}
          />
          <button
            onClick={handlePickOutputDir}
            title="Pilih folder tujuan untuk menyimpan berkas Tablo & Jadwal Dinasan"
            style={{
              padding: '0.55rem 1rem',
              background: 'var(--bg-card-hover)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: '6px',
              cursor: 'pointer',
              fontWeight: 500,
              fontSize: '0.825rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem'
            }}
          >
            <span>📂</span> Pilih Folder Simpan...
          </button>
        </div>
      </div>

      {feedback && (
        <div style={{
          padding: '0.85rem 1.15rem',
          borderRadius: '6px',
          fontSize: '0.85rem',
          background: feedback.type === 'success' ? '#14532d' : '#7f1d1d',
          color: feedback.type === 'success' ? '#86efac' : '#fca5a5',
          border: `1px solid ${feedback.type === 'success' ? '#22c55e' : '#ef4444'}`,
          whiteSpace: 'pre-line',
          lineHeight: 1.5,
          width: '100%'
        }}>
          {feedback.text}
        </div>
      )}

      {/* Unified Single Export Panel */}
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1.25rem', width: '100%' }}>
        
        {/* Pilihan Jenis Dokumen */}
        <div>
          <label style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', display: 'block', marginBottom: '0.65rem' }}>
            🎯 Dokumen yang Ingin Dibuat:
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '0.75rem', width: '100%' }}>
            
            {/* Opsi 1: Keduanya */}
            <div
              onClick={() => setExportDocType('both')}
              style={{
                border: exportDocType === 'both' ? '2px solid var(--accent)' : '1px solid var(--border-color)',
                background: exportDocType === 'both' ? 'var(--bg-card-hover)' : 'var(--bg-secondary)',
                borderRadius: '8px',
                padding: '0.85rem 1rem',
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                <input
                  type="radio"
                  name="docType"
                  checked={exportDocType === 'both'}
                  onChange={() => setExportDocType('both')}
                  style={{ accentColor: 'var(--accent)', cursor: 'pointer' }}
                />
                <span style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                  ✨ Keduanya (Tablo + Jadwal)
                </span>
              </div>
              <p style={{ fontSize: '0.775rem', color: 'var(--text-secondary)', margin: '0.25rem 0 0 1.5rem', lineHeight: 1.35 }}>
                Ekspor formulir Tablo Checklist sekaligus Jadwal Dinasan secara bersamaan.
              </p>
            </div>

            {/* Opsi 2: Tablo Saja */}
            <div
              onClick={() => setExportDocType('tablo')}
              style={{
                border: exportDocType === 'tablo' ? '2px solid var(--accent)' : '1px solid var(--border-color)',
                background: exportDocType === 'tablo' ? 'var(--bg-card-hover)' : 'var(--bg-secondary)',
                borderRadius: '8px',
                padding: '0.85rem 1rem',
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                <input
                  type="radio"
                  name="docType"
                  checked={exportDocType === 'tablo'}
                  onChange={() => setExportDocType('tablo')}
                  style={{ accentColor: 'var(--accent)', cursor: 'pointer' }}
                />
                <span style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                  📑 Tablo Checklist Saja
                </span>
              </div>
              <p style={{ fontSize: '0.775rem', color: 'var(--text-secondary)', margin: '0.25rem 0 0 1.5rem', lineHeight: 1.35 }}>
                Form No. STE-RECORD-13.4.01 A4 Landscape tepat 1 halaman resmi.
              </p>
            </div>

            {/* Opsi 3: Jadwal Dinasan Saja */}
            <div
              onClick={() => setExportDocType('dinasan')}
              style={{
                border: exportDocType === 'dinasan' ? '2px solid var(--accent)' : '1px solid var(--border-color)',
                background: exportDocType === 'dinasan' ? 'var(--bg-card-hover)' : 'var(--bg-secondary)',
                borderRadius: '8px',
                padding: '0.85rem 1rem',
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                <input
                  type="radio"
                  name="docType"
                  checked={exportDocType === 'dinasan'}
                  onChange={() => setExportDocType('dinasan')}
                  style={{ accentColor: 'var(--accent)', cursor: 'pointer' }}
                />
                <span style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                  📅 Jadwal Dinasan Saja
                </span>
              </div>
              <p style={{ fontSize: '0.775rem', color: 'var(--text-secondary)', margin: '0.25rem 0 0 1.5rem', lineHeight: 1.35 }}>
                Matriks dinasan harian personil dan rekapitulasi dinas (S, M, L, P, CT).
              </p>
            </div>

          </div>
        </div>

        {/* Pilihan Profil Preset Pegawai */}
        <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '0.85rem 1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span>👤</span> Profil Pegawai / Roster Tim (KUPT & Personil):
            </label>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              Menentukan KUPT dan roster personil di Tablo & Jadwal Dinasan
            </span>
          </div>
          <select
            value={selectedPresetId}
            onChange={e => handlePresetChange(e.target.value)}
            style={{
              width: '100%',
              padding: '0.55rem 0.75rem',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-color)',
              borderRadius: '6px',
              color: 'var(--text-primary)',
              fontSize: '0.85rem',
              fontWeight: 500
            }}
          >
            {presets.length > 0 ? (
              presets.map(p => (
                <option key={p.id} value={p.id}>
                  {p.name} {p.id === selectedPresetId ? '✓ (Aktif)' : ''}
                </option>
              ))
            ) : (
              <option value="">Standar (KUPT Resor Sintel 1.21 Bogor)</option>
            )}
          </select>
        </div>

        {/* Unified Periode Selector (Satu Pilihan Bulan & Tahun) */}
        <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
              🗓️ Periode Dokumen (Bulan & Tahun):
            </label>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              Menentukan kop laporan Tablo & rentang kalender dinasan
            </span>
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div>
              <label style={{ fontSize: '0.775rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.3rem' }}>
                Pilih Bulan
              </label>
              <select
                value={exportMonth}
                onChange={e => setExportMonth(Number(e.target.value))}
                style={{
                  width: '100%',
                  padding: '0.55rem 0.75rem',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '6px',
                  color: 'var(--text-primary)',
                  fontSize: '0.85rem'
                }}
              >
                {months.map(m => (
                  <option key={m.num} value={m.num}>{m.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={{ fontSize: '0.775rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.3rem' }}>
                Pilih Tahun
              </label>
              <input
                type="number"
                value={exportYear}
                onChange={e => setExportYear(Number(e.target.value))}
                style={{
                  width: '100%',
                  padding: '0.55rem 0.75rem',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '6px',
                  color: 'var(--text-primary)',
                  fontSize: '0.85rem'
                }}
              />
            </div>
          </div>
        </div>

        {/* Pengaturan Tambahan (Personil Lengkap) */}
        {(exportDocType === 'both' || exportDocType === 'dinasan') && (
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.825rem', color: 'var(--text-primary)', cursor: 'pointer', padding: '0.25rem 0' }}>
            <input
              type="checkbox"
              checked={withPersonnel}
              onChange={e => setWithPersonnel(e.target.checked)}
              style={{ accentColor: 'var(--accent)' }}
            />
            <span>Sertakan Kolom Personil Tim Dinasan Lengkap pada Jadwal Dinasan</span>
          </label>
        )}

        {/* Single Primary Action Button */}
        <button
          onClick={handleExport}
          disabled={isGenerating}
          style={{
            width: '100%',
            padding: '0.75rem',
            background: isGenerating ? 'var(--bg-card-hover)' : 'var(--accent)',
            color: '#ffffff',
            border: 'none',
            borderRadius: '6px',
            cursor: isGenerating ? 'not-allowed' : 'pointer',
            fontWeight: 600,
            fontSize: '0.9rem',
            transition: 'background 0.2s ease',
            boxShadow: isGenerating ? 'none' : '0 2px 4px rgba(0,0,0,0.1)'
          }}
        >
          {getButtonLabel()}
        </button>

      </div>

      {/* Riwayat Berkas yang Baru Dibuat */}
      {historyFiles.length > 0 && (
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.25rem', width: '100%' }}>
          <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 0.75rem 0' }}>
            📁 Berkas Excel yang Baru Dihasilkan:
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {historyFiles.map((file, idx) => (
              <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '0.6rem 0.85rem' }}>
                <span style={{ fontSize: '0.825rem', color: 'var(--text-primary)', fontFamily: 'monospace', wordBreak: 'break-all' }}>
                  {file}
                </span>
                <button
                  onClick={() => handleOpenFile(file)}
                  style={{
                    padding: '0.35rem 0.75rem',
                    background: 'var(--accent-dim)',
                    color: 'var(--accent)',
                    border: '1px solid var(--accent)',
                    borderRadius: '5px',
                    cursor: 'pointer',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    whiteSpace: 'nowrap',
                    marginLeft: '0.75rem'
                  }}
                >
                  Buka Berkas
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
}
