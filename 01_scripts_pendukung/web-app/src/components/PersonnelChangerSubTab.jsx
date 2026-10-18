// =============================================================================
// PersonnelChangerSubTab.jsx — Sub-menu Ubah Personil & No. SC pada Lembar PDF
// =============================================================================

import React, { useState, useEffect, useMemo, useCallback } from 'react';

export default function PersonnelChangerSubTab() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [feedback, setFeedback] = useState(null);
  const [manualPath, setManualPath] = useState('');

  // Master Pegawai Base Data (dari /api/timemark/pegawai)
  const [presets, setPresets] = useState([]);
  const [activePresetId, setActivePresetId] = useState('');
  const [pegawaiData, setPegawaiData] = useState({ resor: {}, kaur: [], pnc: [] });
  const [loadingPegawai, setLoadingPegawai] = useState(false);

  // Custom Input Pegawai Luar Profil
  const [customNama, setCustomNama] = useState('');
  const [customNoSc, setCustomNoSc] = useState('');

  // Target Personil yang akan dimasukkan ke PDF (Urutan menentukan Baris 1, 2, 3...)
  const [targetEmployees, setTargetEmployees] = useState([]);

  // 1. Ambil data profil pegawai saat komponen dimuat
  const fetchPegawaiProfiles = async () => {
    setLoadingPegawai(true);
    try {
      const res = await fetch('/api/timemark/pegawai');
      if (res.ok) {
        const d = await res.json();
        if (d) {
          if (d.presets) setPresets(d.presets);
          if (d.active_preset_id) setActivePresetId(d.active_preset_id);
          if (d.daftar_pegawai) {
            setPegawaiData({
              resor: d.daftar_pegawai.resor || {},
              kaur: d.daftar_pegawai.kaur || [],
              pnc: d.daftar_pegawai.pnc || []
            });
          }
        }
      }
    } catch (err) {
      console.warn('Gagal memuat profil pegawai:', err);
    } finally {
      setLoadingPegawai(false);
    }
  };

  useEffect(() => {
    fetchPegawaiProfiles();
  }, []);

  // 2. Ganti Preset Aktif jika user memilih preset lain
  const handlePresetChange = (presetId) => {
    setActivePresetId(presetId);
    const chosen = presets.find(p => p.id === presetId);
    if (chosen && chosen.data) {
      setPegawaiData({
        resor: chosen.data.resor || {},
        kaur: chosen.data.kaur || [],
        pnc: chosen.data.pnc || []
      });
    }
  };

  // 3. Tambah Personil dari Profil ke Target
  const handleAddFromProfile = (person, roleLabel) => {
    if (!person || !person.nama) return;
    const cleanName = person.nama.trim().toUpperCase();
    
    // Cek apakah sudah ada di target
    const already = targetEmployees.some(e => e.nama.toUpperCase() === cleanName);
    if (already) {
      setFeedback({ type: 'info', text: `ℹ️ ${cleanName} sudah ada dalam daftar Target Personil.` });
      return;
    }

    setTargetEmployees(prev => [
      ...prev,
      {
        nama: cleanName,
        no_sc: (person.no_sc || '').trim().toUpperCase(),
        nipp: (person.nipp || '').trim(),
        role: roleLabel || 'TEKNISI',
        source: 'profile'
      }
    ]);
  };

  // 4. Tambah Personil Kustom Manual
  const handleAddCustomEmployee = (e) => {
    if (e) e.preventDefault();
    if (!customNama.trim()) {
      alert('Silakan masukkan nama pegawai!');
      return;
    }
    const cleanName = customNama.trim().toUpperCase();
    const cleanSc = customNoSc.trim().toUpperCase();

    // Cek duplikasi
    if (targetEmployees.some(e => e.nama.toUpperCase() === cleanName)) {
      alert(`Pegawai dengan nama ${cleanName} sudah ada dalam target!`);
      return;
    }

    setTargetEmployees(prev => [
      ...prev,
      {
        nama: cleanName,
        no_sc: cleanSc,
        nipp: '-',
        role: 'KUSTOM',
        source: 'manual'
      }
    ]);

    setCustomNama('');
    setCustomNoSc('');
  };

  // 5. Reorder & Hapus Target Personil
  const handleMoveUp = (index) => {
    if (index <= 0) return;
    setTargetEmployees(prev => {
      const copy = [...prev];
      const temp = copy[index - 1];
      copy[index - 1] = copy[index];
      copy[index] = temp;
      return copy;
    });
  };

  const handleMoveDown = (index) => {
    if (index >= targetEmployees.length - 1) return;
    setTargetEmployees(prev => {
      const copy = [...prev];
      const temp = copy[index + 1];
      copy[index + 1] = copy[index];
      copy[index] = temp;
      return copy;
    });
  };

  const handleRemoveTarget = (index) => {
    setTargetEmployees(prev => prev.filter((_, i) => i !== index));
  };

  // Handler Pindai Input Path Manual (SSH/Web friendly)
  const handleManualScan = () => {
    const p = manualPath.trim().replace(/^["']|["']$/g, '');
    if (!p) {
      setFeedback({ type: 'error', text: 'Silakan masukkan path folder atau berkas PDF terlebih dahulu.' });
      return;
    }
    if (p.toLowerCase().endsWith('.pdf')) {
      handleScanPaths([p]);
    } else {
      handleScanPaths([], p);
    }
  };

  // 6. Handler Pemindaian Berkas PDF untuk Ubah Personil
  const handleScanPaths = async (paths, folder = null) => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch('/api/personnel-changer/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths, folder })
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        const scanned = (data.items || []).map(item => ({
          ...item,
          selected: true,
          execution_status: 'ready' // 'ready' | 'processing' | 'success' | 'error'
        }));

        setItems(prev => {
          const existingPaths = new Set(prev.map(i => i.path));
          const newUnique = scanned.filter(i => !existingPaths.has(i.path));
          return [...prev, ...newUnique];
        });

        setFeedback({
          type: 'info',
          text: `✓ Pemindaian selesai: Ditemukan ${scanned.length} berkas PDF siap diperbarui personilnya.`
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

  // 7. Pilih File PDF
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

  // 8. Pilih Folder
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

  // 9. Drag & Drop
  const handleDrop = useCallback(async (e) => {
    e.preventDefault();
    e.stopPropagation();
    const droppedFiles = Array.from(e.dataTransfer.files || []).filter(f => f.name.toLowerCase().endsWith('.pdf'));
    if (droppedFiles.length === 0) return;

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

  // 10. Seleksi Baris
  const allSelected = useMemo(() => items.length > 0 && items.every(i => i.selected), [items]);
  const handleToggleSelectAll = () => {
    const target = !allSelected;
    setItems(prev => prev.map(i => ({ ...i, selected: target })));
  };

  const handleToggleSelectItem = (idx) => {
    setItems(prev => {
      const copy = [...prev];
      copy[idx] = { ...copy[idx], selected: !copy[idx].selected };
      return copy;
    });
  };

  const handleRemoveItem = (idx) => {
    setItems(prev => prev.filter((_, i) => i !== idx));
  };

  const selectedCount = useMemo(() => items.filter(i => i.selected).length, [items]);

  // 11. Eksekusi Pengubahan Personil PDF
  const handleExecute = async () => {
    const selectedItems = items.filter(i => i.selected);
    if (selectedItems.length === 0) {
      alert('Silakan pilih minimal 1 berkas PDF yang akan diubah personilnya!');
      return;
    }
    if (targetEmployees.length === 0) {
      alert('Silakan tentukan minimal 1 personil target (pilih dari profil atau tambahkan pegawai kustom)!');
      return;
    }

    setProcessing(true);
    setProgress({ current: 0, total: selectedItems.length });
    setFeedback(null);

    setItems(prev => prev.map(i => i.selected ? { ...i, execution_status: 'processing' } : i));

    try {
      const payload = {
        items: selectedItems.map(i => ({ path: i.path })),
        employees: targetEmployees.map(e => ({ nama: e.nama, no_sc: e.no_sc, nipp: e.nipp }))
      };

      const res = await fetch('/api/personnel-changer/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (res.ok && data.ok) {
        const resultMap = {};
        (data.results || []).forEach(r => {
          resultMap[r.path] = r;
        });

        const newTargetStr = targetEmployees.map(e => e.nama).join(', ');

        setItems(prev => prev.map(i => {
          const r = resultMap[i.path];
          if (r) {
            return {
              ...i,
              personnel_str: r.ok ? newTargetStr : i.personnel_str,
              execution_status: r.ok ? 'success' : 'error',
              error_msg: r.error
            };
          }
          return i;
        }));

        setFeedback({
          type: 'success',
          text: `🎉 Selesai! Berhasil memperbarui personil & nomor SC pada ${data.success_count || 0} berkas PDF.` +
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

  return (
    <div
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '1rem',
        height: '100%',
        width: '100%',
        boxSizing: 'border-box',
        overflow: 'hidden'
      }}
    >
      {/* ── TOP ACTION BAR (PEMILIH BERKAS) ── */}
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
        <div>
          <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            📁 Pemilihan Berkas PDF Target Personil
          </h4>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            Pilih berkas checklist PDF yang ingin diubah personil dan nomor sertifikat kecakapannya (in-place overwrite).
          </span>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
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

        {/* ── Manual Path Input (SSH / Remote Web) ── */}
        <div style={{ width: '100%', display: 'flex', gap: '0.5rem', alignItems: 'center', paddingTop: '0.6rem', borderTop: '1px dashed var(--border-color)' }}>
          <input
            type="text"
            placeholder="Ketik atau tempel path folder / berkas PDF di PC (misal: C:\Dokumen\Checklist atau D:\berkas.pdf)..."
            value={manualPath}
            onChange={(e) => setManualPath(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleManualScan(); }}
            disabled={loading || processing}
            style={{
              flex: 1,
              padding: '0.45rem 0.75rem',
              borderRadius: '7px',
              border: '1px solid var(--border-color)',
              background: 'var(--bg-input, var(--bg-secondary))',
              color: 'var(--text-primary)',
              fontSize: '0.825rem',
              fontFamily: 'monospace'
            }}
          />
          <button
            onClick={handleManualScan}
            disabled={loading || processing || !manualPath.trim()}
            style={{
              padding: '0.45rem 0.9rem',
              background: 'var(--accent)',
              color: '#ffffff',
              border: 'none',
              borderRadius: '7px',
              cursor: (loading || processing || !manualPath.trim()) ? 'not-allowed' : 'pointer',
              fontSize: '0.825rem',
              fontWeight: 600,
              whiteSpace: 'nowrap',
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem'
            }}
          >
            🔍 Pindai Path
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

      {/* ── 2-COLUMN PERSONNEL WORKSPACE ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '1rem', minHeight: 0 }}>
        
        {/* KOLOM KIRI: BASE DATA PEGAWAI + INPUT KUSTOM */}
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            borderRadius: '10px',
            padding: '1rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.85rem',
            overflowY: 'auto',
            maxHeight: '360px'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              👥 Base Data Profil Pegawai
            </span>
            {presets.length > 0 && (
              <select
                value={activePresetId}
                onChange={(e) => handlePresetChange(e.target.value)}
                style={{
                  padding: '0.3rem 0.5rem',
                  fontSize: '0.8rem',
                  borderRadius: '6px',
                  background: 'var(--bg-secondary)',
                  border: '1px solid var(--border-color)',
                  color: 'var(--text-primary)'
                }}
              >
                {presets.map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            )}
          </div>

          {/* List Pegawai dari Base Data Profil */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            {/* KAUR */}
            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase' }}>
              Kepala Urusan (KAUR)
            </span>
            {(pegawaiData.kaur || []).map((k, idx) => (
              <div
                key={`kaur_${idx}`}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  background: 'var(--bg-secondary)',
                  padding: '0.4rem 0.65rem',
                  borderRadius: '6px',
                  border: '1px solid var(--border-color)'
                }}
              >
                <div>
                  <div style={{ fontSize: '0.825rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {k.nama}
                  </div>
                  <div style={{ fontSize: '0.725rem', color: 'var(--text-muted)' }}>
                    SC: <strong style={{ color: 'var(--text-secondary)' }}>{k.no_sc || '-'}</strong>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => handleAddFromProfile(k, 'KAUR')}
                  style={{
                    padding: '0.3rem 0.6rem',
                    background: 'var(--bg-card)',
                    border: '1px solid var(--accent)',
                    color: 'var(--accent)',
                    borderRadius: '5px',
                    cursor: 'pointer',
                    fontSize: '0.75rem',
                    fontWeight: 600
                  }}
                >
                  + Masukkan
                </button>
              </div>
            ))}

            {/* PNC */}
            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#38bdf8', textTransform: 'uppercase', marginTop: '0.25rem' }}>
              Pelaksana (PNC)
            </span>
            {(pegawaiData.pnc || []).map((p, idx) => (
              <div
                key={`pnc_${idx}`}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  background: 'var(--bg-secondary)',
                  padding: '0.4rem 0.65rem',
                  borderRadius: '6px',
                  border: '1px solid var(--border-color)'
                }}
              >
                <div>
                  <div style={{ fontSize: '0.825rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {p.nama}
                  </div>
                  <div style={{ fontSize: '0.725rem', color: 'var(--text-muted)' }}>
                    SC: <strong style={{ color: 'var(--text-secondary)' }}>{p.no_sc || '-'}</strong>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => handleAddFromProfile(p, 'PNC')}
                  style={{
                    padding: '0.3rem 0.6rem',
                    background: 'var(--bg-card)',
                    border: '1px solid #38bdf8',
                    color: '#38bdf8',
                    borderRadius: '5px',
                    cursor: 'pointer',
                    fontSize: '0.75rem',
                    fontWeight: 600
                  }}
                >
                  + Masukkan
                </button>
              </div>
            ))}

            {/* KUPT / Resor (Opsional) */}
            {pegawaiData.resor && pegawaiData.resor.nama && (
              <>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginTop: '0.25rem' }}>
                  Resor / Pengawas
                </span>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    background: 'var(--bg-secondary)',
                    padding: '0.4rem 0.65rem',
                    borderRadius: '6px',
                    border: '1px solid var(--border-color)'
                  }}
                >
                  <div>
                    <div style={{ fontSize: '0.825rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {pegawaiData.resor.nama}
                    </div>
                    <div style={{ fontSize: '0.725rem', color: 'var(--text-muted)' }}>
                      SC: <strong style={{ color: 'var(--text-secondary)' }}>{pegawaiData.resor.no_sc || '-'}</strong>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleAddFromProfile(pegawaiData.resor, 'RESOR')}
                    style={{
                      padding: '0.3rem 0.6rem',
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border-color)',
                      color: 'var(--text-primary)',
                      borderRadius: '5px',
                      cursor: 'pointer',
                      fontSize: '0.75rem',
                      fontWeight: 600
                    }}
                  >
                    + Masukkan
                  </button>
                </div>
              </>
            )}
          </div>

          {/* Form Input Pegawai Kustom Tambahan */}
          <div style={{ marginTop: '0.5rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-color)' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-secondary)', display: 'block', marginBottom: '0.4rem' }}>
              ✏️ Tambah Pegawai di Luar Profil (Kustom Manual):
            </span>
            <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr auto', gap: '0.4rem', alignItems: 'center' }}>
              <input
                type="text"
                placeholder="Nama Pegawai Baru..."
                value={customNama}
                onChange={e => setCustomNama(e.target.value)}
                style={{
                  padding: '0.4rem 0.6rem',
                  fontSize: '0.8rem',
                  borderRadius: '6px',
                  background: 'var(--bg-secondary)',
                  border: '1px solid var(--border-color)',
                  color: 'var(--text-primary)',
                  textTransform: 'uppercase'
                }}
              />
              <input
                type="text"
                placeholder="No. SC (PRP...)..."
                value={customNoSc}
                onChange={e => setCustomNoSc(e.target.value)}
                style={{
                  padding: '0.4rem 0.6rem',
                  fontSize: '0.8rem',
                  borderRadius: '6px',
                  background: 'var(--bg-secondary)',
                  border: '1px solid var(--border-color)',
                  color: 'var(--text-primary)',
                  fontFamily: 'monospace',
                  textTransform: 'uppercase'
                }}
              />
              <button
                type="button"
                onClick={handleAddCustomEmployee}
                style={{
                  padding: '0.4rem 0.75rem',
                  background: 'var(--accent)',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  whiteSpace: 'nowrap'
                }}
              >
                + Tambah
              </button>
            </div>
          </div>
        </div>

        {/* KOLOM KANAN: TARGET PERSONIL TERPILIH (DILAKSANAKAN OLEH) */}
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            borderRadius: '10px',
            padding: '1rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.75rem',
            overflowY: 'auto',
            maxHeight: '360px'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              🎯 Target Personil Formulir (Halaman 1)
            </span>
            <span style={{ fontSize: '0.75rem', color: 'var(--accent)', fontWeight: 600 }}>
              {targetEmployees.length} Personil Terpilih
            </span>
          </div>

          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Urutan daftar di bawah ini akan langsung menjadi <strong>Baris 1, Baris 2, Baris 3</strong> pada kolom <em>"DILAKSANAKAN OLEH"</em> lembar pemeriksaan.
          </span>

          {targetEmployees.length === 0 ? (
            <div
              style={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                alignItems: 'center',
                border: '1px dashed var(--border-color)',
                borderRadius: '8px',
                padding: '1.5rem',
                color: 'var(--text-muted)',
                textAlign: 'center',
                fontSize: '0.8rem'
              }}
            >
              Belum ada personil target yang dipilih.
              <span style={{ fontSize: '0.725rem', marginTop: '0.25rem' }}>
                Klik tombol <strong>"+ Masukkan"</strong> dari Base Data di sebelah kiri atau ketik nama pada form kustom.
              </span>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              {targetEmployees.map((emp, idx) => (
                <div
                  key={`target_${idx}`}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.45rem 0.75rem',
                    borderRadius: '7px',
                    background: 'var(--bg-secondary)',
                    border: '1px solid var(--border-color)'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                    <span
                      style={{
                        padding: '0.15rem 0.45rem',
                        borderRadius: '4px',
                        background: 'var(--accent)',
                        color: '#ffffff',
                        fontSize: '0.7rem',
                        fontWeight: 700
                      }}
                    >
                      Baris {idx + 1}
                    </span>
                    <div>
                      <div style={{ fontSize: '0.825rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                        {emp.nama}
                      </div>
                      <div style={{ fontSize: '0.725rem', color: 'var(--text-muted)' }}>
                        No. SC: <strong style={{ color: 'var(--text-secondary)' }}>{emp.no_sc || '-'}</strong>
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '0.25rem', alignItems: 'center' }}>
                    <button
                      type="button"
                      onClick={() => handleMoveUp(idx)}
                      disabled={idx === 0}
                      title="Pindahkan baris ke atas"
                      style={{
                        padding: '0.2rem 0.45rem',
                        background: 'transparent',
                        border: '1px solid var(--border-color)',
                        borderRadius: '4px',
                        cursor: idx === 0 ? 'not-allowed' : 'pointer',
                        color: idx === 0 ? 'var(--text-muted)' : 'var(--text-primary)',
                        fontSize: '0.75rem'
                      }}
                    >
                      ▲
                    </button>
                    <button
                      type="button"
                      onClick={() => handleMoveDown(idx)}
                      disabled={idx === targetEmployees.length - 1}
                      title="Pindahkan baris ke bawah"
                      style={{
                        padding: '0.2rem 0.45rem',
                        background: 'transparent',
                        border: '1px solid var(--border-color)',
                        borderRadius: '4px',
                        cursor: idx === targetEmployees.length - 1 ? 'not-allowed' : 'pointer',
                        color: idx === targetEmployees.length - 1 ? 'var(--text-muted)' : 'var(--text-primary)',
                        fontSize: '0.75rem'
                      }}
                    >
                      ▼
                    </button>
                    <button
                      type="button"
                      onClick={() => handleRemoveTarget(idx)}
                      title="Hapus dari target"
                      style={{
                        padding: '0.2rem 0.45rem',
                        background: 'rgba(239, 68, 68, 0.1)',
                        border: '1px solid rgba(239, 68, 68, 0.3)',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        color: '#ef4444',
                        fontSize: '0.75rem',
                        marginLeft: '0.25rem'
                      }}
                    >
                      ✕
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── BATCH CONTROLS & TOMBOL EKSEKUSI ── */}
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
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <span style={{ fontSize: '0.825rem', color: 'var(--text-muted)' }}>
              Berkas Terpilih: <strong>{selectedCount}</strong> dari <strong>{items.length}</strong> berkas PDF
            </span>
          </div>

          <button
            onClick={handleExecute}
            disabled={processing || selectedCount === 0 || targetEmployees.length === 0}
            style={{
              padding: '0.6rem 1.4rem',
              background: (processing || selectedCount === 0 || targetEmployees.length === 0) ? 'var(--bg-secondary)' : 'var(--accent)',
              color: (processing || selectedCount === 0 || targetEmployees.length === 0) ? 'var(--text-muted)' : '#ffffff',
              border: 'none',
              borderRadius: '7px',
              cursor: (processing || selectedCount === 0 || targetEmployees.length === 0) ? 'not-allowed' : 'pointer',
              fontSize: '0.875rem',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              boxShadow: '0 2px 6px rgba(255, 115, 0, 0.3)'
            }}
          >
            {processing ? `⏳ Memperbarui ${progress.current}/${progress.total}...` : `⚡ Terapkan Personil Baru ke ${selectedCount} Berkas`}
          </button>
        </div>
      )}

      {/* ── TABEL DAFTAR BERKAS PDF ── */}
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
        {items.length === 0 ? (
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              alignItems: 'center',
              padding: '2rem',
              color: 'var(--text-muted)',
              fontSize: '0.85rem',
              textAlign: 'center',
              gap: '0.5rem'
            }}
          >
            <span style={{ fontSize: '2rem' }}>📑</span>
            <span>Belum ada berkas PDF yang dimuat.</span>
            <span style={{ fontSize: '0.775rem' }}>
              Klik tombol <strong>"Pilih Berkas PDF..."</strong> atau drag & drop file PDF ke area ini.
            </span>
          </div>
        ) : (
          <div style={{ overflowY: 'auto', flex: 1 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.8rem' }}>
              <thead
                style={{
                  position: 'sticky',
                  top: 0,
                  background: 'var(--bg-secondary)',
                  borderBottom: '1px solid var(--border-color)',
                  color: 'var(--text-secondary)',
                  fontSize: '0.75rem'
                }}
              >
                <tr>
                  <th style={{ padding: '0.6rem 0.75rem', width: '40px' }}>
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={handleToggleSelectAll}
                      disabled={processing}
                      style={{ cursor: 'pointer' }}
                    />
                  </th>
                  <th style={{ padding: '0.6rem 0.75rem' }}>Nama Berkas PDF</th>
                  <th style={{ padding: '0.6rem 0.75rem', width: '110px' }}>Tanggal</th>
                  <th style={{ padding: '0.6rem 0.75rem' }}>Personil Terbaca Saat Ini</th>
                  <th style={{ padding: '0.6rem 0.75rem', width: '130px' }}>Status</th>
                  <th style={{ padding: '0.6rem 0.75rem', width: '40px', textAlign: 'center' }}>Aksi</th>
                </tr>
              </thead>
              <tbody style={{ divideY: '1px solid var(--border-color)' }}>
                {items.map((item, idx) => (
                  <tr
                    key={item.path || idx}
                    style={{
                      borderBottom: '1px solid var(--border-color)',
                      background: item.selected ? 'rgba(255, 115, 0, 0.03)' : 'transparent',
                      transition: 'background 0.15s'
                    }}
                  >
                    <td style={{ padding: '0.55rem 0.75rem' }}>
                      <input
                        type="checkbox"
                        checked={item.selected}
                        onChange={() => handleToggleSelectItem(idx)}
                        disabled={processing}
                        style={{ cursor: 'pointer' }}
                      />
                    </td>
                    <td style={{ padding: '0.55rem 0.75rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {item.filename}
                    </td>
                    <td style={{ padding: '0.55rem 0.75rem', color: 'var(--text-secondary)' }}>
                      {item.date}
                    </td>
                    <td style={{ padding: '0.55rem 0.75rem', color: 'var(--text-secondary)' }}>
                      {item.personnel_str || '-'}
                    </td>
                    <td style={{ padding: '0.55rem 0.75rem' }}>
                      {item.execution_status === 'processing' && (
                        <span style={{ color: 'var(--accent)', fontWeight: 600 }}>⏳ Memproses...</span>
                      )}
                      {item.execution_status === 'success' && (
                        <span style={{ color: '#22c55e', fontWeight: 600 }}>✓ Diperbarui</span>
                      )}
                      {item.execution_status === 'error' && (
                        <span style={{ color: '#ef4444', fontWeight: 600 }} title={item.error_msg || ''}>
                          ✗ Gagal
                        </span>
                      )}
                      {item.execution_status === 'ready' && (
                        <span style={{ color: 'var(--text-muted)' }}>Siap</span>
                      )}
                    </td>
                    <td style={{ padding: '0.55rem 0.75rem', textAlign: 'center' }}>
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
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
