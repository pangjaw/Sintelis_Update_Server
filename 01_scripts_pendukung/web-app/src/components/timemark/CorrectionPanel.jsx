import { useState, useRef, useEffect } from 'react';

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

  // State Window Log Koreksi & Serat Optik
  const [corrLogs, setCorrLogs] = useState([]);
  const [copiedLog, setCopiedLog] = useState(false);
  const logEndRef = useRef(null);

  const addLog = (type, msg) => {
    const ts = new Date().toLocaleTimeString();
    setCorrLogs(prev => [...prev, { ts, type, msg }]);
  };

  const handleCopyLogs = () => {
    if (!corrLogs.length) return;
    const text = corrLogs.map(l => `[${l.ts}] ${l.msg}`).join('\n');
    navigator.clipboard.writeText(text);
    setCopiedLog(true);
    setTimeout(() => setCopiedLog(false), 2000);
  };

  const handleClearLogs = () => {
    setCorrLogs([]);
  };

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [corrLogs]);

  // 1. Serat Optik Handler
  const handleScanSeratOptik = async (apply = false) => {
    if (!targetDir) {
      alert('Silakan tentukan Folder Target PDF terlebih dahulu!');
      return;
    }
    setSoScanning(true);
    setSoFeedback(null);
    addLog('info', `[SERAT OPTIK] Memulai ${apply ? 'koreksi nilai core fisik' : 'pemindaian berkas'} pada: ${targetDir}`);
    try {
      const res = await fetch('/api/timemark/koreksi-serat-optik', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder: targetDir, apply })
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        const items = data.items || [];
        setSoItems(items);
        const needed = items.filter(i => i.needs_correction).length;
        const appliedCount = items.filter(i => i.applied).length;

        // Detailkan ke Window Log
        items.forEach(it => {
          if (it.applied) {
            addLog('success', `⚡ [TERKOREKSI] ${it.filename} (${it.tipe}): ${it.current_core} Core -> ${it.target_core} Core (${it.message || 'Sukses'})`);
          } else if (it.needs_correction) {
            addLog('warn', `⚠️ [PERLU KOREKSI] ${it.filename} (${it.tipe}): Terbaca ${it.current_core || '-'} Core, Target: ${it.target_core} Core`);
          } else {
            addLog('info', `✓ [SESUAI] ${it.filename} (${it.tipe}): Sudah ${it.target_core} Core (${it.message || 'Standar valid'})`);
          }
        });

        if (apply) {
          const txt = `✓ Koreksi nilai core Serat Optik selesai: ${appliedCount} berkas berhasil disesuaikan.`;
          setSoFeedback({ type: 'success', text: txt });
          addLog('success', `[SERAT OPTIK] ${txt}`);
        } else {
          const txt = `Pemindaian selesai: Ditemukan ${items.length} berkas Serat Optik (${needed} perlu koreksi).`;
          setSoFeedback({ type: 'info', text: txt });
          addLog('info', `[SERAT OPTIK] ${txt}`);
        }
      } else {
        const errTxt = data.error || 'Terjadi kesalahan';
        setSoFeedback({ type: 'error', text: 'Gagal memproses: ' + errTxt });
        addLog('error', `[SERAT OPTIK] Gagal memproses: ${errTxt}`);
      }
    } catch (err) {
      setSoFeedback({ type: 'error', text: 'Galat: ' + err.message });
      addLog('error', `[SERAT OPTIK] Galat: ${err.message}`);
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
    const actionLabel = action === 'auto-correct-batch' 
      ? 'Koreksi Personil Sesuai Tim' 
      : action === 'auto-correct-no-sc' 
      ? 'Pelengkapan Nomor SC' 
      : (refresh ? 'Scan Ulang Fisik Disk & Audit' : 'Audit Dokumen');
    addLog('info', `[PERSONIL] Memulai ${actionLabel} pada: ${targetDir}...`);

    try {
      const res = await fetch('/api/timemark/audit-personil', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder: targetDir, action, refresh })
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        setPersReport(data.result);
        if (data.from_cache) {
          addLog('info', `[PERSONIL] ⚡ Memuat hasil audit dari cache lokal.`);
        }

        const summary = data.result?.summary;
        if (summary) {
          addLog('info', `[PERSONIL] Ringkasan: Total ${summary.total_files} berkas | Sesuai: ${summary.compliant} | Beda Tim: ${summary.team_mismatch_count || 0} | Perlu Koreksi: ${summary.needs_correction} | SC Kurang: ${summary.needs_sc_correction || 0}`);
        }

        if (action === 'auto-correct-batch') {
          const tot = data.result?.total_corrected || 0;
          const txt = `✓ Koreksi & sinkronisasi personil berhasil! ${tot} berkas disesuaikan dengan tim jadwalnya.`;
          setPersFeedback({ type: 'success', text: txt });
          addLog('success', `[PERSONIL] ${txt}`);
          if (Array.isArray(data.result?.corrected)) {
            data.result.corrected.forEach(c => {
              addLog('success', `⚡ [TERKOREKSI TIM] ${c.file}: KAUR=${c.kaur}, PNC=${(c.pnc || []).join(', ')}`);
            });
          }
        } else if (action === 'auto-correct-no-sc') {
          const totSc = data.result?.total_sc_corrected || 0;
          const txt = `✓ Nomor SC pada ${totSc} berkas berhasil dilengkapi.`;
          setPersFeedback({ type: 'success', text: txt });
          addLog('success', `[PERSONIL] ${txt}`);
        } else {
          const needsCorrCount = summary?.needs_correction ?? data.result?.critical_count ?? 0;
          const mismatchCount = summary?.team_mismatch_count ?? 0;
          const cachePrefix = data.from_cache ? '⚡ Hasil dimuat instan dari cache: ' : 'Audit selesai: ';
          const mismatchDesc = mismatchCount > 0 ? ` (${mismatchCount} berkas beda personil tim)` : '';
          const txt = `${cachePrefix}${data.result?.total_files || 0} berkas dipindai (${needsCorrCount} berkas perlu penyesuaian${mismatchDesc}).`;
          setPersFeedback({ type: 'info', text: txt });
          addLog('info', `[PERSONIL] ${txt}`);

          // Rincian berkas beda tim ke log
          if (Array.isArray(data.result?.files)) {
            const mismatches = data.result.files.filter(f => f.team_mismatch);
            if (mismatches.length > 0) {
              mismatches.forEach(m => {
                const readNames = (m.kaur || []).concat(m.pnc || []).join(', ') || 'Kosong';
                const expNames = (m.expected_kaur || []).concat(m.expected_pnc || []).join(', ') || '-';
                addLog('warn', `⚠️ [BEDA TIM] ${m.file} (${m.team_label || 'Tim ?'}): Terbaca [${readNames}] -> Seharusnya [${expNames}]`);
              });
            }
          }
        }
      } else {
        const errTxt = data.error || 'Terjadi kesalahan';
        setPersFeedback({ type: 'error', text: 'Gagal audit personil: ' + errTxt });
        addLog('error', `[PERSONIL] Gagal audit personil: ${errTxt}`);
      }
    } catch (err) {
      setPersFeedback({ type: 'error', text: 'Galat: ' + err.message });
      addLog('error', `[PERSONIL] Galat: ${err.message}`);
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

      {/* SECTION 3: WINDOW LOG KOREKSI & AUDIT (REAL-TIME TERMINAL CONSOLE) */}
      <div style={{
        marginTop: '0.5rem',
        background: '#090d16',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        padding: '0.85rem 1rem',
        fontFamily: 'monospace',
        fontSize: '0.8rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.35rem',
        minHeight: '175px',
        maxHeight: '260px',
        userSelect: 'text'
      }}>
        <div style={{
          color: '#64748b',
          borderBottom: '1px solid #1e293b',
          paddingBottom: '0.45rem',
          marginBottom: '0.35rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>
              🖥️ Window Log Koreksi & Audit ({corrLogs.length})
            </span>
            <span style={{ fontSize: '0.72rem', background: 'var(--bg-secondary)', padding: '0.15rem 0.45rem', borderRadius: '4px', color: 'var(--text-muted)' }}>
              {activeSubSection === 'serat_optik' ? 'Core Serat Optik' : 'Audit & Koreksi Personil'}
            </span>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            {corrLogs.length > 0 && (
              <>
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
                    gap: '0.3rem',
                    transition: 'all 0.2s'
                  }}
                  title="Salin seluruh isi log terminal koreksi ke clipboard"
                >
                  <span>{copiedLog ? '✓' : '📋'}</span>
                  <span>{copiedLog ? 'Tersalin!' : 'Salin Log'}</span>
                </button>
                <button
                  type="button"
                  onClick={handleClearLogs}
                  style={{
                    padding: '0.2rem 0.5rem',
                    background: 'transparent',
                    color: 'var(--text-muted)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '4px',
                    fontSize: '0.75rem',
                    cursor: 'pointer'
                  }}
                  title="Bersihkan catatan log"
                >
                  🗑️ Bersihkan
                </button>
              </>
            )}
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.25rem', paddingRight: '0.3rem', userSelect: 'text' }}>
          {corrLogs.map((lg, idx) => (
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
          {corrLogs.length === 0 && (
            <div style={{ color: '#475569', fontStyle: 'italic', margin: 'auto', textAlign: 'center', padding: '1rem' }}>
              Log aktivitas koreksi akan ditampilkan di sini saat proses Audit Personil atau Pindai Core Serat Optik dijalankan.
            </div>
          )}
          <div ref={logEndRef} />
        </div>
      </div>

    </div>
  );
}

