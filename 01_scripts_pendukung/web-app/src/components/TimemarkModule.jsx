import { useState, useEffect, useRef } from 'react';
import GalleryPanel from './timemark/GalleryPanel';
import EmployeeManagerPanel from './timemark/EmployeeManagerPanel';
import CorrectionPanel from './timemark/CorrectionPanel';
import ExcelExportPanel from './timemark/ExcelExportPanel';
import ScheduleSheetPanel from './timemark/ScheduleSheetPanel';

export default function TimemarkModule() {
  const [activeSubTab, setActiveSubTab] = useState('pipeline'); // 'pipeline' | 'gallery' | 'employee' | 'correction' | 'export'

  // Folder state
  const [folderMode, setFolderMode] = useState('single'); // 'single' | 'dual'
  const [singleDir, setSingleDir] = useState('');
  const [overwriteOriginal, setOverwriteOriginal] = useState(false);

  const [sourceDir, setSourceDir] = useState('');
  const [targetDir, setTargetDir] = useState('');
  const [exportDir, setExportDir] = useState('');
  const [mergedDir, setMergedDir] = useState('');

  const [selectedSteps, setSelectedSteps] = useState(['1', '1.5', '2', '3', '4', '5']);
  const [detector, setDetector] = useState('google_vision'); // 'google_vision' | 'guide'
  const [pipelineState, setPipelineState] = useState({
    running: false,
    cancelled: false,
    current_step: 0,
    step_name: '',
    progress: 0,
    logs: [],
    step_statuses: {
      step1: 'pending',
      step1_5: 'pending',
      step2: 'pending',
      step3: 'pending',
      step4: 'pending',
      step5: 'pending'
    },
    error: null
  });

  const [pdfCounts, setPdfCounts] = useState({ single: null, source: null, target: null });
  const [copiedLog, setCopiedLog] = useState(false);
  const logEndRef = useRef(null);

  const handleCopyLogs = () => {
    if (!pipelineState.logs || !pipelineState.logs.length) return;
    const text = pipelineState.logs.map(l => `[${l.ts}] ${l.msg}`).join('\n');
    navigator.clipboard.writeText(text);
    setCopiedLog(true);
    setTimeout(() => setCopiedLog(false), 2000);
  };


  // Poll status when running
  useEffect(() => {
    let interval = null;
    const checkStatus = async () => {
      try {
        const res = await fetch('/api/timemark/status');
        if (res.ok) {
          const data = await res.json();
          setPipelineState(data);
        }
      } catch (err) {
        console.error('Error polling timemark status:', err);
      }
    };

    if (pipelineState.running) {
      interval = setInterval(checkStatus, 500);
    } else {
      checkStatus();
    }
    return () => { if (interval) clearInterval(interval); };
  }, [pipelineState.running]);

  // Auto-scroll log
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [pipelineState.logs]);

  // Folder picking helper
  const handlePickFolder = async (setter, type) => {
    try {
      const res = await fetch('/api/select-folder', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        if (data.path) {
          setter(data.path);
          if (type === 'single' || type === 'source' || type === 'target') {
            const listRes = await fetch(`/api/list-folder-pdfs?folder=${encodeURIComponent(data.path)}`);
            if (listRes.ok) {
              const listData = await listRes.json();
              setPdfCounts(prev => ({
                ...prev,
                [type]: listData.files ? listData.files.length : 0
              }));
            }
          }
        }
      }
    } catch (err) {
      alert('Gagal membuka dialog folder: ' + err.message);
    }
  };

  const handleToggleStep = (stepId) => {
    setSelectedSteps(prev =>
      prev.includes(stepId)
        ? prev.filter(s => s !== stepId)
        : [...prev, stepId].sort((a, b) => parseFloat(a) - parseFloat(b))
    );
  };

  const handleStartPipeline = async () => {
    const isSingle = folderMode === 'single';
    const effectiveSource = isSingle ? singleDir : sourceDir;
    const effectiveTarget = isSingle ? singleDir : targetDir;

    if (selectedSteps.includes('1') && !effectiveSource) {
      alert(isSingle ? 'Silakan pilih Folder Dokumen PDF terlebih dahulu!' : 'Silakan pilih Folder PDF Sumber 2026 terlebih dahulu!');
      return;
    }
    if (!isSingle && selectedSteps.some(s => ['2', '3', '5'].includes(s)) && !effectiveTarget) {
      alert('Silakan pilih Folder PDF Target 2025 terlebih dahulu!');
      return;
    }
    if (!effectiveSource && !effectiveTarget && !exportDir) {
      alert('Silakan pilih minimal Folder PDF Target atau Folder Ekstraksi Foto terlebih dahulu!');
      return;
    }
    if (selectedSteps.length === 0) {
      alert('Pilih minimal satu tahap untuk dijalankan!');
      return;
    }

    try {
      const res = await fetch('/api/timemark/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: folderMode,
          sourceDir: effectiveSource || effectiveTarget || exportDir,
          targetDir: effectiveTarget || effectiveSource || exportDir,
          exportDir: exportDir || undefined,
          mergedDir: mergedDir || undefined,
          overwriteOriginal: isSingle && overwriteOriginal,
          steps: selectedSteps,
          detector: detector
        })
      });
      const data = await res.json();
      if (!data.ok) {
        alert('Gagal memulai pipeline: ' + (data.error || 'Terjadi kesalahan'));
      } else {
        setPipelineState(prev => ({ ...prev, running: true, error: null, logs: [] }));
      }
    } catch (err) {
      alert('Gagal menghubungi server: ' + err.message);
    }
  };

  const handleFastUpdateTimemark = async () => {
    const isSingle = folderMode === 'single';
    const effectiveSource = isSingle ? singleDir : sourceDir;
    const effectiveTarget = isSingle ? singleDir : targetDir;

    if (!exportDir && !effectiveTarget && !effectiveSource) {
      alert('Silakan pilih Folder Ekstraksi Foto (03/04) atau Folder PDF Target terlebih dahulu!');
      return;
    }

    try {
      const res = await fetch('/api/timemark/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: folderMode,
          sourceDir: effectiveSource || effectiveTarget || exportDir,
          targetDir: effectiveTarget || effectiveSource || exportDir,
          exportDir: exportDir || undefined,
          mergedDir: mergedDir || undefined,
          overwriteOriginal: isSingle && overwriteOriginal,
          steps: ['4_fast'],
          detector: 'fast_meta'
        })
      });
      const data = await res.json();
      if (!data.ok) {
        alert('Gagal memulai Fast Update Timemark: ' + (data.error || 'Terjadi kesalahan'));
      } else {
        setPipelineState(prev => ({ ...prev, running: true, error: null, logs: [] }));
      }
    } catch (err) {
      alert('Gagal menghubungi server: ' + err.message);
    }
  };

  const handleCancelPipeline = async () => {
    if (!confirm('Apakah Anda yakin ingin membatalkan proses pipeline?')) return;
    try {
      await fetch('/api/timemark/cancel', { method: 'POST' });
    } catch (err) {
      console.error('Cancel error:', err);
    }
  };

  const stepLabels = [
    { id: '1', key: 'step1', name: 'Step 1: Ekstraksi Foto PDF' },
    { id: '1.5', key: 'step1_5', name: 'Step 1.5: Auto-Crop Kolase (White-Seam)' },
    { id: '2', key: 'step2', name: 'Step 2: Ekstraksi Tanggal Checklist' },
    { id: '3', key: 'step3', name: 'Step 3: Penjadwalan Tim & Alokasi Waktu' },
    { id: '4', key: 'step4', name: 'Step 4: Edit Watermark Timemark Foto' },
    { id: '5', key: 'step5', name: 'Step 5: Penggabungan PDF Final A4' }
  ];

  // Active target folder for other tabs
  const currentActiveTarget = folderMode === 'single' ? singleDir : targetDir;
  const currentActiveExport = folderMode === 'single' ? (exportDir || singleDir || '') : (exportDir || '');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', gap: '1rem', overflow: 'hidden' }}>
      
      {/* 5 Floating Pill Sub-Tabs Navigation Bar */}
      <div className="floating-pill-container" style={{ width: '100%' }}>
        {[
          { id: 'pipeline', label: '🚀 Pipeline Proses' },
          { id: 'schedule', label: '📅 Schedule Sheet' },
          { id: 'gallery', label: '🖼️ Galeri & Edit Foto' },
          { id: 'employee', label: '👥 Profil Pegawai' },
          { id: 'correction', label: '📑 Koreksi Dokumen' },
          { id: 'export', label: '📊 Ekspor Dokumen Excel' }
        ].map(tab => (
          <button
            key={tab.id}
            type="button"
            className={`floating-pill-btn ${activeSubTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveSubTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* SUB-TAB 1: PIPELINE PROSES */}
      <div style={{ display: activeSubTab === 'pipeline' ? 'flex' : 'none', gap: '1.25rem', flex: 1, width: '100%', minHeight: 0, overflow: 'hidden' }}>
        
        {/* Kolom Kiri: Form Konfigurasi Folder & Step */}
        <div style={{ flex: '0 0 490px', display: 'flex', flexDirection: 'column', gap: '1rem', overflowY: 'auto', paddingRight: '0.5rem' }}>
          
          {/* Card Pemilihan Mode Sumber Folder */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.25rem' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>📁</span> Mode Pemilihan Folder Sumber
            </h3>

            {/* Toggle Mode: 1 Folder vs 2 Folder */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', marginBottom: '1.25rem' }}>
              <button
                type="button"
                onClick={() => setFolderMode('single')}
                style={{
                  padding: '0.6rem 0.5rem',
                  background: folderMode === 'single' ? 'var(--accent)' : 'var(--bg-secondary)',
                  color: folderMode === 'single' ? '#ffffff' : 'var(--text-secondary)',
                  border: folderMode === 'single' ? '1px solid var(--accent)' : '1px solid var(--border-color)',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  textAlign: 'center'
                }}
              >
                1 Folder Sumber (Tunggal)
              </button>
              <button
                type="button"
                onClick={() => setFolderMode('dual')}
                style={{
                  padding: '0.6rem 0.5rem',
                  background: folderMode === 'dual' ? 'var(--accent)' : 'var(--bg-secondary)',
                  color: folderMode === 'dual' ? '#ffffff' : 'var(--text-secondary)',
                  border: folderMode === 'dual' ? '1px solid var(--accent)' : '1px solid var(--border-color)',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  textAlign: 'center'
                }}
              >
                2 Folder (2026 + 2025 Klasik)
              </button>
            </div>

            {/* MODE 1 FOLDER (TUNGGAL) */}
            {folderMode === 'single' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div>
                  <label style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                    <span>Folder Dokumen PDF (Ceklis & Foto)*</span>
                    {pdfCounts.single !== null && (
                      <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{pdfCounts.single} PDF terdeteksi</span>
                    )}
                  </label>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <input
                      type="text"
                      placeholder="Pilih folder berkas PDF tunggal..."
                      value={singleDir}
                      onChange={e => setSingleDir(e.target.value)}
                      style={{ flex: 1, padding: '0.5rem 0.75rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.85rem' }}
                    />
                    <button
                      onClick={() => handlePickFolder(setSingleDir, 'single')}
                      style={{ padding: '0.5rem 0.85rem', background: 'var(--accent)', color: '#ffffff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, whiteSpace: 'nowrap' }}
                    >
                      Pilih...
                    </button>
                  </div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.25rem', display: 'block' }}>
                    Ekstraksi foto, pembacaan tanggal, penjadwalan, dan merge akan mengacu pada folder yang sama.
                  </span>
                </div>

                {/* Saklar Penanganan Hasil Merge */}
                <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '0.75rem' }}>
                  <label style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={overwriteOriginal}
                      onChange={e => setOverwriteOriginal(e.target.checked)}
                      style={{ marginTop: '0.2rem' }}
                    />
                    <div>
                      <strong style={{ fontSize: '0.825rem', color: 'var(--text-primary)', display: 'block' }}>
                        Timpa Langsung Berkas PDF di Folder Sumber
                      </strong>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'block', marginTop: '0.15rem' }}>
                        {overwriteOriginal
                          ? '⚠️ Aktif: Berkas asli akan dicadangkan otomatis ke subfolder backups/ sebelum digabungkan.'
                          : 'Tidak aktif: Hasil merge disimpan ke folder output terpisah tanpa menyentuh file asli.'}
                      </span>
                    </div>
                  </label>
                </div>
              </div>
            )}

            {/* MODE 2 FOLDER (DUAL KLASIK) */}
            {folderMode === 'dual' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {/* 1. Sumber PDF 2026 */}
                <div>
                  <label style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                    <span>Folder PDF Sumber 2026 (Foto Asli)*</span>
                    {pdfCounts.source !== null && (
                      <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{pdfCounts.source} PDF terdeteksi</span>
                    )}
                  </label>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <input
                      type="text"
                      placeholder="Pilih folder sumber PDF 2026..."
                      value={sourceDir}
                      onChange={e => setSourceDir(e.target.value)}
                      style={{ flex: 1, padding: '0.5rem 0.75rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.85rem' }}
                    />
                    <button
                      onClick={() => handlePickFolder(setSourceDir, 'source')}
                      style={{ padding: '0.5rem 0.85rem', background: 'var(--accent)', color: '#ffffff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, whiteSpace: 'nowrap' }}
                    >
                      Pilih...
                    </button>
                  </div>
                </div>

                {/* 2. Target PDF 2025 */}
                <div>
                  <label style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                    <span>Folder PDF Target 2025 (Template Ceklis)*</span>
                    {pdfCounts.target !== null && (
                      <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{pdfCounts.target} PDF terdeteksi</span>
                    )}
                  </label>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <input
                      type="text"
                      placeholder="Pilih folder target PDF 2025..."
                      value={targetDir}
                      onChange={e => setTargetDir(e.target.value)}
                      style={{ flex: 1, padding: '0.5rem 0.75rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.85rem' }}
                    />
                    <button
                      onClick={() => handlePickFolder(setTargetDir, 'target')}
                      style={{ padding: '0.5rem 0.85rem', background: 'var(--accent)', color: '#ffffff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, whiteSpace: 'nowrap' }}
                    >
                      Pilih...
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Folder Output Opsional */}
            <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
                  Folder Ekstraksi Foto (Opsional / Bawaan: otomatis membuat 03_export_foto & 04_photos_edited)
                </label>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <input
                    type="text"
                    placeholder="Bawaan: [Folder]/03_export_foto & 04_photos_edited"
                    value={exportDir}
                    onChange={e => setExportDir(e.target.value)}
                    style={{ flex: 1, padding: '0.45rem 0.65rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.825rem' }}
                  />
                  <button
                    onClick={() => handlePickFolder(setExportDir, 'export')}
                    style={{ padding: '0.45rem 0.75rem', background: 'var(--bg-card-hover)', color: 'var(--text-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.8rem' }}
                  >
                    Pilih...
                  </button>
                </div>
              </div>

              {(!overwriteOriginal || folderMode === 'dual') && (
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
                    Folder PDF Gabungan Akhir (Opsional / Bawaan: Dokumen/Sintelis/05_pdf_merged)
                  </label>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <input
                      type="text"
                      placeholder="Bawaan: Dokumen/Sintelis/05_pdf_merged"
                      value={mergedDir}
                      onChange={e => setMergedDir(e.target.value)}
                      style={{ flex: 1, padding: '0.45rem 0.65rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.825rem' }}
                    />
                    <button
                      onClick={() => handlePickFolder(setMergedDir, 'merged')}
                      style={{ padding: '0.45rem 0.75rem', background: 'var(--bg-card-hover)', color: 'var(--text-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.8rem' }}
                    >
                      Pilih...
                    </button>
                  </div>
                </div>
              )}
            </div>

          </div>

          {/* Card Pilihan Tahap Pipeline */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.25rem' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.75rem' }}>
              ⚙️ Tahapan Pipeline yang Dijalankan
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {stepLabels.map(st => {
                const checked = selectedSteps.includes(st.id);
                const status = pipelineState.step_statuses?.[st.key] || 'pending';
                return (
                  <label
                    key={st.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '0.5rem 0.75rem',
                      background: checked ? 'var(--bg-secondary)' : 'transparent',
                      border: '1px solid var(--border-color)',
                      borderRadius: '6px',
                      cursor: pipelineState.running ? 'not-allowed' : 'pointer'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={pipelineState.running}
                        onChange={() => handleToggleStep(st.id)}
                      />
                      <span style={{ fontSize: '0.825rem', color: checked ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                        {st.name}
                      </span>
                    </div>
                    <span style={{
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      padding: '0.15rem 0.5rem',
                      borderRadius: '4px',
                      background: status === 'done' ? '#14532d' : status === 'running' ? '#1e3a5f' : status === 'error' ? '#7f1d1d' : 'transparent',
                      color: status === 'done' ? '#86efac' : status === 'running' ? '#93c5fd' : status === 'error' ? '#fca5a5' : 'var(--text-secondary)'
                    }}>
                      {status === 'done' ? '✓ Selesai' : status === 'running' ? '⏳ Berjalan' : status === 'error' ? '✗ Galat' : 'Menunggu'}
                    </span>
                  </label>
                );
              })}
            </div>

            {/* Pilihan Metode Deteksi Timemark (Jika Step 4 Aktif) */}
            {selectedSteps.includes('4') && (
              <div style={{ marginTop: '0.85rem', paddingTop: '0.85rem', borderTop: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <span>🔍</span> Detektor Timemark (Step 4):
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.6rem' }}>
                  <button
                    type="button"
                    disabled={pipelineState.running}
                    onClick={() => setDetector('google_vision')}
                    style={{
                      padding: '0.6rem 0.75rem',
                      borderRadius: '8px',
                      border: detector === 'google_vision' ? '2px solid #a855f7' : '1px solid var(--border-color)',
                      background: detector === 'google_vision' ? 'rgba(168, 85, 247, 0.15)' : 'var(--bg-secondary)',
                      color: detector === 'google_vision' ? '#c084fc' : 'var(--text-secondary)',
                      cursor: pipelineState.running ? 'not-allowed' : 'pointer',
                      textAlign: 'left',
                      transition: 'all 0.2s',
                      boxShadow: detector === 'google_vision' ? '0 0 12px rgba(168, 85, 247, 0.25)' : 'none'
                    }}
                  >
                    <div style={{ fontWeight: 800, fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <span>✨</span> Google AI Vision (Otomatis)
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '0.2rem', lineHeight: 1.3 }}>
                      Deteksi bounding-box tulisan waktu via AI Cloud Vision
                    </div>
                  </button>

                  <button
                    type="button"
                    disabled={pipelineState.running}
                    onClick={() => setDetector('guide')}
                    style={{
                      padding: '0.6rem 0.75rem',
                      borderRadius: '8px',
                      border: detector === 'guide' ? '2px solid #0284c7' : '1px solid var(--border-color)',
                      background: detector === 'guide' ? 'rgba(2, 132, 199, 0.15)' : 'var(--bg-secondary)',
                      color: detector === 'guide' ? '#38bdf8' : 'var(--text-secondary)',
                      cursor: pipelineState.running ? 'not-allowed' : 'pointer',
                      textAlign: 'left',
                      transition: 'all 0.2s',
                      boxShadow: detector === 'guide' ? '0 0 12px rgba(2, 132, 199, 0.25)' : 'none'
                    }}
                  >
                    <div style={{ fontWeight: 800, fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <span>🎨</span> Metode Biasa (HSV Panduan)
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '0.2rem', lineHeight: 1.3 }}>
                      Deteksi garis panduan warna merah/oranye klasik
                    </div>
                  </button>

                  <button
                    type="button"
                    disabled={pipelineState.running}
                    onClick={() => setDetector('fast_meta')}
                    style={{
                      padding: '0.6rem 0.75rem',
                      borderRadius: '8px',
                      border: detector === 'fast_meta' ? '2px solid #10b981' : '1px solid var(--border-color)',
                      background: detector === 'fast_meta' ? 'rgba(16, 185, 129, 0.15)' : 'var(--bg-secondary)',
                      color: detector === 'fast_meta' ? '#34d399' : 'var(--text-secondary)',
                      cursor: pipelineState.running ? 'not-allowed' : 'pointer',
                      textAlign: 'left',
                      transition: 'all 0.2s',
                      boxShadow: detector === 'fast_meta' ? '0 0 12px rgba(16, 185, 129, 0.25)' : 'none'
                    }}
                  >
                    <div style={{ fontWeight: 800, fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <span>⚡</span> Fast Update (Ikuti meta.json)
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '0.2rem', lineHeight: 1.3 }}>
                      Langsung pakai koordinat xPos/yPos tersimpan di meta.json tanpa deteksi ulang
                    </div>
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Action Buttons */}
          <div style={{ display: 'flex', gap: '0.6rem', marginTop: 'auto', paddingBottom: '0.5rem' }}>
            {!pipelineState.running ? (
              <>
                <button
                  onClick={handleStartPipeline}
                  style={{
                    flex: 1.2,
                    padding: '0.75rem',
                    background: 'var(--accent)',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '6px',
                    fontWeight: 600,
                    fontSize: '0.88rem',
                    cursor: 'pointer'
                  }}
                >
                  🚀 Mulai Pipeline
                </button>
                <button
                  type="button"
                  onClick={handleFastUpdateTimemark}
                  title="Hanya perbarui tanggal dan jam di textbox memakai koordinat tersimpan di meta.json tanpa OCR/deteksi ulang"
                  style={{
                    flex: 1,
                    padding: '0.75rem 0.65rem',
                    background: '#8957e5',
                    color: '#ffffff',
                    border: '1px solid #a371f7',
                    borderRadius: '6px',
                    fontWeight: 700,
                    fontSize: '0.82rem',
                    cursor: 'pointer',
                    whiteSpace: 'nowrap'
                  }}
                >
                  ⚡ Fast Update Timemark
                </button>
              </>
            ) : (
              <button
                onClick={handleCancelPipeline}
                style={{
                  flex: 1,
                  padding: '0.75rem',
                  background: '#dc2626',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '6px',
                  fontWeight: 600,
                  fontSize: '0.9rem',
                  cursor: 'pointer'
                }}
              >
                🛑 Batalkan Proses
              </button>
            )}
          </div>

        </div>

        {/* Kolom Kanan: Progres & Terminal Log */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1rem', minHeight: 0, overflow: 'hidden' }}>
          
          {/* Progress Bar Card */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem 1.25rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                {pipelineState.running
                  ? `Sedang Berjalan: ${pipelineState.step_name}${pipelineState.sub_total > 0 ? ` (${pipelineState.sub_current}/${pipelineState.sub_total})` : ''}`
                  : 'Siap menjalankan proses'}
              </span>
              <strong style={{ fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                {pipelineState.progress}%
              </strong>
            </div>
            <div style={{ width: '100%', height: '8px', background: 'var(--bg-secondary)', borderRadius: '4px', overflow: 'hidden' }}>
              <div
                style={{
                  width: `${pipelineState.progress}%`,
                  height: '100%',
                  background: pipelineState.error ? '#dc2626' : 'var(--accent)',
                  transition: 'width 0.3s ease'
                }}
              />
            </div>
          </div>

          {/* Terminal Console Log */}
          <div style={{
            flex: 1,
            background: '#090d16',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            padding: '1rem',
            fontFamily: 'monospace',
            fontSize: '0.8rem',
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.25rem',
            userSelect: 'text'
          }}>
            <div style={{
              color: '#64748b',
              borderBottom: '1px solid #1e293b',
              paddingBottom: '0.4rem',
              marginBottom: '0.4rem',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <span style={{ fontWeight: 600 }}>
                Console Log Pipeline — Output Real-Time {pipelineState.logs.length > 0 ? `(${pipelineState.logs.length})` : ''}
              </span>
              {pipelineState.logs.length > 0 && (
                <button
                  type="button"
                  onClick={handleCopyLogs}
                  style={{
                    padding: '0.2rem 0.6rem',
                    background: copiedLog ? '#14532d' : 'var(--bg-secondary)',
                    color: copiedLog ? '#86efac' : 'var(--accent)',
                    border: `1px solid ${copiedLog ? '#22c55e' : 'var(--border-color)'}`,
                    borderRadius: '4px',
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.35rem',
                    transition: 'all 0.2s'
                  }}
                  title="Salin seluruh isi log terminal ke clipboard"
                >
                  <span>{copiedLog ? '✓' : '📋'}</span>
                  <span>{copiedLog ? 'Tersalin!' : 'Salin Log'}</span>
                </button>
              )}
            </div>
            {pipelineState.logs.map((lg, idx) => (
              <div key={idx} style={{
                color: lg.type === 'error' ? '#f87171' : lg.type === 'warn' ? '#fbbf24' : lg.type === 'success' ? '#4ade80' : '#e2e8f0',
                lineHeight: 1.45,
                wordBreak: 'break-all',
                userSelect: 'text'
              }}>
                <span style={{ color: '#64748b', marginRight: '0.5rem' }}>[{lg.ts}]</span>
                {lg.msg}
              </div>
            ))}
            {pipelineState.logs.length === 0 && (
              <div style={{ color: '#475569', fontStyle: 'italic', margin: 'auto' }}>
                Log aktivitas akan ditampilkan di sini saat proses dijalankan.
              </div>
            )}
            <div ref={logEndRef} />
          </div>


        </div>

      </div>

      {/* SUB-TAB: SCHEDULE SHEET & DAFTAR JADWAL */}
      <div style={{ display: activeSubTab === 'schedule' ? 'flex' : 'none', flexDirection: 'column', flex: 1, width: '100%', minHeight: 0, overflow: 'hidden' }}>
        <ScheduleSheetPanel
          targetDir={currentActiveTarget}
          exportDir={currentActiveExport}
          onPickFolder={() => handlePickFolder(folderMode === 'single' ? setSingleDir : setTargetDir, folderMode === 'single' ? 'single' : 'target')}
        />
      </div>

      {/* SUB-TAB 2: GALERI & EDIT FOTO */}
      <div style={{ display: activeSubTab === 'gallery' ? 'flex' : 'none', flexDirection: 'column', flex: 1, width: '100%', minHeight: 0, overflow: 'hidden' }}>
        <GalleryPanel exportDir={currentActiveExport} onPickFolder={() => handlePickFolder(setExportDir, 'export')} />
      </div>

      {/* SUB-TAB 3: PROFIL PEGAWAI */}
      <div style={{ display: activeSubTab === 'employee' ? 'flex' : 'none', flexDirection: 'column', flex: 1, width: '100%', minHeight: 0, overflow: 'hidden' }}>
        <EmployeeManagerPanel />
      </div>

      {/* SUB-TAB 4: KOREKSI DOKUMEN */}
      <div style={{ display: activeSubTab === 'correction' ? 'flex' : 'none', flexDirection: 'column', flex: 1, width: '100%', minHeight: 0, overflow: 'hidden' }}>
        <CorrectionPanel
          targetDir={currentActiveTarget}
          onPickFolder={() => handlePickFolder(folderMode === 'single' ? setSingleDir : setTargetDir, folderMode === 'single' ? 'single' : 'target')}
        />
      </div>

      {/* SUB-TAB 5: EKSPOR EXCEL */}
      <div style={{ display: activeSubTab === 'export' ? 'flex' : 'none', flexDirection: 'column', flex: 1, width: '100%', minHeight: 0, overflow: 'hidden' }}>
        <ExcelExportPanel targetDir={currentActiveTarget} exportDir={currentActiveExport} />
      </div>

    </div>
  );
}
