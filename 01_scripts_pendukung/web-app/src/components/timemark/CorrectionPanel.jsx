import { useState } from 'react';

export default function CorrectionPanel({ targetDir, onPickFolder }) {
  const [activeSubSection, setActiveSubSection] = useState('personnel'); // 'personnel' | 'serat_optik'
  
  // State Serat Optik
  const [soScanning, setSoScanning] = useState(false);
  const [soItems, setSoItems] = useState([]);
  const [soFeedback, setSoFeedback] = useState(null);

  // State Personil
  const [persScanning, setPersScanning] = useState(false);
  const [persReport, setPersReport] = useState(null);
  const [persFeedback, setPersFeedback] = useState(null);
  const [filterStatus, setFilterStatus] = useState('all'); // 'all' | 'mismatch' | 'needs_sc' | 'compliant'

  // 1. Serat Optik Handler
  const handleScanSeratOptik = async (apply = false) => {
    if (!targetDir) {
      alert('Silakan tentukan Folder Target PDF terlebih dahulu!');
      return;
    }
    setSoScanning(true);
    setSoFeedback(null);
    try {
      const res = await fetch('/api/timemark/koreksi-serat-optik', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder: targetDir, apply })
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        setSoItems(data.items || []);
        const needed = (data.items || []).filter(i => i.needs_correction).length;
        if (apply) {
          setSoFeedback({ type: 'success', text: `✓ Koreksi nilai core Serat Optik berhasil diterapkan pada berkas yang membutuhkan.` });
        } else {
          setSoFeedback({ type: 'info', text: `Pemindaian selesai: Ditemukan ${data.items.length} berkas Serat Optik (${needed} perlu koreksi).` });
        }
      } else {
        setSoFeedback({ type: 'error', text: 'Gagal memproses: ' + (data.error || 'Terjadi kesalahan') });
      }
    } catch (err) {
      setSoFeedback({ type: 'error', text: 'Galat: ' + err.message });
    } finally {
      setSoScanning(false);
    }
  };

  // 2. Audit & Koreksi Personil Handler
  const handleAuditPersonil = async (action = 'audit', refresh = false) => {
    if (!targetDir) {
      alert('Silakan tentukan Folder Target PDF terlebih dahulu!');
      return;
    }
    setPersScanning(true);
    setPersFeedback(null);
    try {
      const res = await fetch('/api/timemark/audit-personil', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder: targetDir, action, refresh })
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        setPersReport(data.result);
        if (action === 'auto-correct-batch') {
          setPersFeedback({ type: 'success', text: `✓ Koreksi & sinkronisasi personil berhasil! ${data.result?.total_corrected || 0} berkas disesuaikan dengan tim jadwalnya.` });
        } else if (action === 'auto-correct-no-sc') {
          setPersFeedback({ type: 'success', text: `✓ Nomor SC pada ${data.result?.total_sc_corrected || 0} berkas berhasil dilengkapi.` });
        } else {
          const needsCorrCount = data.result?.summary?.needs_correction ?? data.result?.critical_count ?? 0;
          const mismatchCount = data.result?.summary?.team_mismatch_count ?? 0;
          const cachePrefix = data.from_cache ? '⚡ Hasil dimuat instan dari cache: ' : 'Audit selesai: ';
          const mismatchDesc = mismatchCount > 0 ? ` (${mismatchCount} berkas beda personil tim)` : '';
          setPersFeedback({ type: 'info', text: `${cachePrefix}${data.result?.total_files || 0} berkas dipindai (${needsCorrCount} berkas perlu penyesuaian${mismatchDesc}).` });
        }
      } else {
        setPersFeedback({ type: 'error', text: 'Gagal audit personil: ' + (data.error || 'Terjadi kesalahan') });
      }
    } catch (err) {
      setPersFeedback({ type: 'error', text: 'Galat: ' + err.message });
    } finally {
      setPersScanning(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', height: '100%', width: '100%', overflowY: 'auto', paddingRight: '0.5rem' }}>
      
      {/* Folder Indicator Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem 1.25rem', width: '100%' }}>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block' }}>Folder Target Berkas PDF:</span>
          <strong style={{ fontSize: '0.9rem', color: 'var(--text-primary)' }}>{targetDir || 'Belum dipilih (Pilih folder di Tab Pipeline atau klik tombol di kanan)'}</strong>
        </div>
        <button
          onClick={onPickFolder}
          style={{ padding: '0.45rem 0.85rem', background: 'var(--bg-secondary)', color: 'var(--accent)', border: '1px solid var(--accent)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.825rem', fontWeight: 500 }}
        >
          Ganti Folder...
        </button>
      </div>

      {/* Sub-Section Toggle Buttons */}
      <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
        <button
          onClick={() => setActiveSubSection('personnel')}
          style={{
            padding: '0.5rem 1rem',
            background: activeSubSection === 'personnel' ? 'var(--accent)' : 'var(--bg-secondary)',
            color: activeSubSection === 'personnel' ? '#ffffff' : 'var(--text-secondary)',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '0.85rem',
            fontWeight: 500
          }}
        >
          👤 Audit & Koreksi Personil (1 KAUR, 2 PNC)
        </button>
        <button
          onClick={() => setActiveSubSection('serat_optik')}
          style={{
            padding: '0.5rem 1rem',
            background: activeSubSection === 'serat_optik' ? 'var(--accent)' : 'var(--bg-secondary)',
            color: activeSubSection === 'serat_optik' ? '#ffffff' : 'var(--text-secondary)',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '0.85rem',
            fontWeight: 500
          }}
        >
          🌐 Koreksi Core Serat Optik / OTB
        </button>
      </div>

      {/* SECTION 1: AUDIT & KOREKSI PERSONIL */}
      {activeSubSection === 'personnel' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', width: '100%' }}>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.25rem', width: '100%' }}>
            <div>
              <h4 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                Kepatuhan Personil & Penugasan Tim Formulir Checklist PDF
              </h4>
              <p style={{ fontSize: '0.825rem', color: 'var(--text-secondary)', margin: '0.25rem 0 0 0' }}>
                Memeriksa halaman 1 berkas checklist agar terisi 1 KAUR dan 2 PNC resmi, serta sinkron dengan jadwal Tim (Tim 1, Tim 2, Tim 3).
              </p>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <button
                onClick={() => handleAuditPersonil('audit', false)}
                disabled={persScanning}
                style={{ padding: '0.5rem 0.95rem', background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-color)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.825rem', fontWeight: 500 }}
              >
                {persScanning ? 'Memindai...' : '🔍 Audit Dokumen'}
              </button>
              <button
                onClick={() => handleAuditPersonil('audit', true)}
                disabled={persScanning}
                title="Pindai ulang seluruh berkas fisik dari disk dan cocokkan jadwal tim tanpa cache"
                style={{ padding: '0.5rem 0.85rem', background: 'var(--bg-secondary)', color: 'var(--accent)', border: '1px solid var(--border-color)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.825rem', fontWeight: 500 }}
              >
                🔄 Scan Ulang & Audit Tim
              </button>
              <button
                onClick={() => handleAuditPersonil('auto-correct-no-sc')}
                disabled={persScanning}
                style={{ padding: '0.5rem 0.95rem', background: 'var(--bg-card-hover)', color: 'var(--accent)', border: '1px solid var(--accent)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.825rem', fontWeight: 500 }}
              >
                🧾 Lengkapi No. SC
              </button>
              <button
                onClick={() => handleAuditPersonil('auto-correct-batch')}
                disabled={persScanning}
                title="Koreksi personil berkas PDF agar sesuai dengan personil tim jadwalnya"
                style={{ padding: '0.5rem 1.15rem', background: 'var(--accent)', color: '#ffffff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '0.825rem', fontWeight: 600 }}
              >
                ⚡ Koreksi Sesuai Tim
              </button>
            </div>
          </div>

          {persFeedback && (
            <div style={{
              padding: '0.75rem 1rem',
              borderRadius: '6px',
              fontSize: '0.85rem',
              background: persFeedback.type === 'success' ? '#14532d' : persFeedback.type === 'error' ? '#7f1d1d' : '#1e3a5f',
              color: persFeedback.type === 'success' ? '#86efac' : persFeedback.type === 'error' ? '#fca5a5' : '#93c5fd',
              border: `1px solid ${persFeedback.type === 'success' ? '#22c55e' : persFeedback.type === 'error' ? '#ef4444' : '#3b82f6'}`
            }}>
              {persFeedback.text}
            </div>
          )}

          {/* Ringkasan Metrik Audit */}
          {(persReport?.summary || persReport?.total_files !== undefined) && (
            <div style={{ display: 'grid', gridTemplateColumns: persReport.summary?.team_mismatch_count > 0 ? 'repeat(5, minmax(0, 1fr))' : 'repeat(4, minmax(0, 1fr))', gap: '0.75rem', width: '100%' }}>
              <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '0.85rem 1rem' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'block' }}>Total Dokumen</span>
                <strong style={{ fontSize: '1.25rem', color: 'var(--text-primary)' }}>{persReport.summary?.total_files ?? persReport.total_files ?? 0}</strong>
              </div>
              <div style={{ background: 'var(--bg-card)', border: '1px solid #16a34a', borderRadius: '6px', padding: '0.85rem 1rem' }}>
                <span style={{ fontSize: '0.75rem', color: '#86efac', display: 'block' }}>Sesuai Aturan & Tim</span>
                <strong style={{ fontSize: '1.25rem', color: '#86efac' }}>{persReport.summary?.compliant ?? persReport.ok_count ?? 0}</strong>
              </div>
              {persReport.summary?.team_mismatch_count > 0 && (
                <div style={{ background: 'var(--bg-card)', border: '1px solid #d97706', borderRadius: '6px', padding: '0.85rem 1rem' }}>
                  <span style={{ fontSize: '0.75rem', color: '#fde68a', display: 'block' }}>⚠️ Beda Personil Tim</span>
                  <strong style={{ fontSize: '1.25rem', color: '#fde68a' }}>{persReport.summary?.team_mismatch_count || 0}</strong>
                </div>
              )}
              <div style={{ background: 'var(--bg-card)', border: '1px solid #ef4444', borderRadius: '6px', padding: '0.85rem 1rem' }}>
                <span style={{ fontSize: '0.75rem', color: '#fca5a5', display: 'block' }}>Perlu Koreksi Personil</span>
                <strong style={{ fontSize: '1.25rem', color: '#fca5a5' }}>{persReport.summary?.needs_correction ?? persReport.critical_count ?? 0}</strong>
              </div>
              <div style={{ background: 'var(--bg-card)', border: '1px solid #3b82f6', borderRadius: '6px', padding: '0.85rem 1rem' }}>
                <span style={{ fontSize: '0.75rem', color: '#93c5fd', display: 'block' }}>Nomor SC Kurang</span>
                <strong style={{ fontSize: '1.25rem', color: '#93c5fd' }}>{persReport.summary?.needs_sc_correction ?? 0}</strong>
              </div>
            </div>
          )}

          {/* Filter Pills */}
          {persReport?.files && (
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Filter Tampilan:</span>
              <button
                onClick={() => setFilterStatus('all')}
                style={{
                  padding: '0.25rem 0.65rem',
                  borderRadius: '12px',
                  fontSize: '0.75rem',
                  border: 'none',
                  cursor: 'pointer',
                  background: filterStatus === 'all' ? 'var(--accent)' : 'var(--bg-secondary)',
                  color: filterStatus === 'all' ? '#ffffff' : 'var(--text-secondary)'
                }}
              >
                Semua ({persReport.files.length})
              </button>
              {persReport.summary?.team_mismatch_count > 0 && (
                <button
                  onClick={() => setFilterStatus('mismatch')}
                  style={{
                    padding: '0.25rem 0.65rem',
                    borderRadius: '12px',
                    fontSize: '0.75rem',
                    border: 'none',
                    cursor: 'pointer',
                    background: filterStatus === 'mismatch' ? '#d97706' : 'var(--bg-secondary)',
                    color: filterStatus === 'mismatch' ? '#ffffff' : '#fde68a'
                  }}
                >
                  ⚠️ Beda Tim ({persReport.summary.team_mismatch_count})
                </button>
              )}
              <button
                onClick={() => setFilterStatus('needs_sc')}
                style={{
                  padding: '0.25rem 0.65rem',
                  borderRadius: '12px',
                  fontSize: '0.75rem',
                  border: 'none',
                  cursor: 'pointer',
                  background: filterStatus === 'needs_sc' ? '#2563eb' : 'var(--bg-secondary)',
                  color: filterStatus === 'needs_sc' ? '#ffffff' : '#93c5fd'
                }}
              >
                🧾 SC Kurang ({persReport.summary?.needs_sc_correction ?? 0})
              </button>
              <button
                onClick={() => setFilterStatus('compliant')}
                style={{
                  padding: '0.25rem 0.65rem',
                  borderRadius: '12px',
                  fontSize: '0.75rem',
                  border: 'none',
                  cursor: 'pointer',
                  background: filterStatus === 'compliant' ? '#16a34a' : 'var(--bg-secondary)',
                  color: filterStatus === 'compliant' ? '#ffffff' : '#86efac'
                }}
              >
                ✅ Sesuai ({persReport.summary?.compliant ?? 0})
              </button>
            </div>
          )}

          {/* Tabel Hasil Audit Personil */}
          {persReport?.files && (
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', overflow: 'hidden', width: '100%' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.825rem' }}>
                <thead>
                  <tr style={{ background: 'var(--bg-secondary)', color: 'var(--text-secondary)', textAlign: 'left', borderBottom: '1px solid var(--border-color)' }}>
                    <th style={{ padding: '0.6rem 0.75rem' }}>Nama Berkas Checklist</th>
                    <th style={{ padding: '0.6rem 0.75rem', width: '70px' }}>Tim</th>
                    <th style={{ padding: '0.6rem 0.75rem', width: '130px' }}>Status</th>
                    <th style={{ padding: '0.6rem 0.75rem', width: '160px' }}>KAUR Terbaca</th>
                    <th style={{ padding: '0.6rem 0.75rem' }}>Teknisi PNC Terbaca</th>
                    <th style={{ padding: '0.6rem 0.75rem', width: '220px' }}>Personil Tim Seharusnya</th>
                  </tr>
                </thead>
                <tbody>
                  {persReport.files
                    .filter(f => {
                      if (filterStatus === 'mismatch') return f.team_mismatch;
                      if (filterStatus === 'needs_sc') return f.needs_sc_correction;
                      if (filterStatus === 'compliant') return (f.status === 'compliant' || f.status === 'OK') && !f.team_mismatch && !f.needs_sc_correction;
                      return true;
                    })
                    .map((f, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid var(--border-color)' }}>
                      <td style={{ padding: '0.6rem 0.75rem', color: 'var(--text-primary)', wordBreak: 'break-all' }}>{f.file}</td>
                      <td style={{ padding: '0.6rem 0.75rem' }}>
                        <span style={{
                          padding: '0.2rem 0.5rem',
                          borderRadius: '4px',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          background: f.tim === 2 ? '#1e3a5f' : f.tim >= 3 ? '#581c87' : '#064e3b',
                          color: f.tim === 2 ? '#93c5fd' : f.tim >= 3 ? '#d8b4fe' : '#6ee7b7'
                        }}>
                          {f.team_label || (f.tim ? `Tim ${f.tim}` : 'Tim 1')}
                        </span>
                      </td>
                      <td style={{ padding: '0.6rem 0.75rem' }}>
                        {f.team_mismatch ? (
                          <span style={{ padding: '0.2rem 0.5rem', background: '#78350f', color: '#fde68a', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 500 }} title={f.status_label}>⚠️ Beda Tim</span>
                        ) : (f.status === 'compliant' || f.status === 'OK' || (!f.needs_correction && !f.needs_sc_correction)) ? (
                          <span style={{ padding: '0.2rem 0.5rem', background: '#14532d', color: '#86efac', borderRadius: '4px', fontSize: '0.75rem' }}>✅ Sesuai</span>
                        ) : f.needs_sc_correction && !f.needs_correction ? (
                          <span style={{ padding: '0.2rem 0.5rem', background: '#1e3a5f', color: '#93c5fd', borderRadius: '4px', fontSize: '0.75rem' }}>🧾 SC Kurang</span>
                        ) : (
                          <span style={{ padding: '0.2rem 0.5rem', background: '#7f1d1d', color: '#fca5a5', borderRadius: '4px', fontSize: '0.75rem' }} title={f.status_label}>🚨 Kurang Personil</span>
                        )}
                      </td>
                      <td style={{ padding: '0.6rem 0.75rem', color: 'var(--text-secondary)' }}>
                        {f.kaur?.length ? f.kaur.join(', ') : <span style={{ color: '#ef4444' }}>Tidak ada</span>}
                      </td>
                      <td style={{ padding: '0.6rem 0.75rem', color: 'var(--text-secondary)' }}>
                        {f.pnc?.length ? f.pnc.join(', ') : <span style={{ color: '#ef4444' }}>Tidak ada</span>}
                      </td>
                      <td style={{ padding: '0.6rem 0.75rem', color: f.team_mismatch ? '#fde68a' : 'var(--text-muted)', fontSize: '0.775rem' }}>
                        {f.expected_kaur?.length || f.expected_pnc?.length ? (
                          <span>
                            <strong>{f.expected_kaur?.join(', ')}</strong> + {f.expected_pnc?.join(', ')}
                          </span>
                        ) : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

        </div>
      )}

      {/* SECTION 2: KOREKSI SERAT OPTIK */}
      {activeSubSection === 'serat_optik' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', width: '100%' }}>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.25rem', width: '100%' }}>
            <div>
              <h4 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                Koreksi Nilai Core Serat Optik & OTB
              </h4>
              <p style={{ fontSize: '0.825rem', color: 'var(--text-secondary)', margin: '0.25rem 0 0 0' }}>
                Aturan standar: Khusus JPL = 12 Core, Serat Optik OTB = Total Aset * 24 Core (Redaksi presisi menjaga outline tabel).
              </p>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                onClick={() => handleScanSeratOptik(false)}
                disabled={soScanning}
                style={{ padding: '0.5rem 0.95rem', background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-color)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.825rem', fontWeight: 500 }}
              >
                {soScanning ? 'Memindai...' : '🔍 Pindai Berkas'}
              </button>
              <button
                onClick={() => handleScanSeratOptik(true)}
                disabled={soScanning}
                style={{ padding: '0.5rem 1.15rem', background: 'var(--accent)', color: '#ffffff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '0.825rem', fontWeight: 600 }}
              >
                ⚡ Terapkan Koreksi Core
              </button>
            </div>
          </div>

          {soFeedback && (
            <div style={{
              padding: '0.75rem 1rem',
              borderRadius: '6px',
              fontSize: '0.85rem',
              background: soFeedback.type === 'success' ? '#14532d' : soFeedback.type === 'error' ? '#7f1d1d' : '#1e3a5f',
              color: soFeedback.type === 'success' ? '#86efac' : soFeedback.type === 'error' ? '#fca5a5' : '#93c5fd',
              border: `1px solid ${soFeedback.type === 'success' ? '#22c55e' : soFeedback.type === 'error' ? '#ef4444' : '#3b82f6'}`
            }}>
              {soFeedback.text}
            </div>
          )}

          {/* Tabel Serat Optik */}
          {soItems.length > 0 && (
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', overflow: 'hidden', width: '100%' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.825rem' }}>
                <thead>
                  <tr style={{ background: 'var(--bg-secondary)', color: 'var(--text-secondary)', textAlign: 'left', borderBottom: '1px solid var(--border-color)' }}>
                    <th style={{ padding: '0.6rem 0.75rem' }}>Nama Berkas Serat Optik / OTB</th>
                    <th style={{ padding: '0.6rem 0.75rem', width: '100px' }}>Tipe</th>
                    <th style={{ padding: '0.6rem 0.75rem', width: '140px' }}>Core Saat Ini</th>
                    <th style={{ padding: '0.6rem 0.75rem', width: '140px' }}>Target Standar</th>
                    <th style={{ padding: '0.6rem 0.75rem', width: '130px' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {soItems.map((it, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid var(--border-color)' }}>
                      <td style={{ padding: '0.6rem 0.75rem', color: 'var(--text-primary)' }}>{it.filename}</td>
                      <td style={{ padding: '0.6rem 0.75rem', color: 'var(--text-secondary)' }}>{it.tipe}</td>
                      <td style={{ padding: '0.6rem 0.75rem', color: it.needs_correction ? '#ef4444' : '#10b981', fontWeight: 600 }}>{it.current_core || '-'}</td>
                      <td style={{ padding: '0.6rem 0.75rem', color: 'var(--accent)', fontWeight: 600 }}>{it.target_core} Core</td>
                      <td style={{ padding: '0.6rem 0.75rem' }}>
                        {it.applied ? (
                          <span style={{ padding: '0.2rem 0.5rem', background: '#14532d', color: '#86efac', borderRadius: '4px', fontSize: '0.75rem' }}>⚡ Terkoreksi</span>
                        ) : it.needs_correction ? (
                          <span style={{ padding: '0.2rem 0.5rem', background: '#78350f', color: '#fde68a', borderRadius: '4px', fontSize: '0.75rem' }}>⚠️ Perlu Koreksi</span>
                        ) : (
                          <span style={{ padding: '0.2rem 0.5rem', background: '#14532d', color: '#86efac', borderRadius: '4px', fontSize: '0.75rem' }}>✅ Sudah Sesuai</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {soItems.length === 0 && !soScanning && (
            <div style={{ textAlign: 'center', padding: '2.5rem', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
              Klik tombol "Pindai Berkas" untuk memeriksa nilai core berkas Serat Optik pada folder target.
            </div>
          )}

        </div>
      )}

    </div>
  );
}
