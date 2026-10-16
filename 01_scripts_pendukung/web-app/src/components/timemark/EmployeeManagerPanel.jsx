import { useState, useEffect } from 'react';

export default function EmployeeManagerPanel() {
  const [presets, setPresets] = useState([]);
  const [activePresetId, setActivePresetId] = useState('');
  const [resor, setResor] = useState({ nama: '', nipp: '', no_sc: '' });
  const [kaurList, setKaurList] = useState([]);
  const [pncList, setPncList] = useState([]);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState(null);

  // Load employee data from backend
  const fetchEmployeeData = async () => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch('/api/timemark/pegawai');
      if (res.ok) {
        const data = await res.json();
        if (data.presets) {
          setPresets(data.presets);
          setActivePresetId(data.active_preset_id || (data.presets[0]?.id || ''));
        }
        if (data.daftar_pegawai) {
          setResor(data.daftar_pegawai.resor || { nama: '', nipp: '', no_sc: '' });
          setKaurList(data.daftar_pegawai.kaur || []);
          setPncList(data.daftar_pegawai.pnc || []);
        }
      } else {
        setFeedback({ type: 'error', text: 'Gagal memuat data profil pegawai dari server.' });
      }
    } catch (err) {
      setFeedback({ type: 'error', text: 'Koneksi gagal: ' + err.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEmployeeData();
  }, []);

  // Switch preset
  const handleSelectPreset = (presetId) => {
    setActivePresetId(presetId);
    const selected = presets.find(p => p.id === presetId);
    if (selected && selected.data) {
      setResor(selected.data.resor || { nama: '', nipp: '', no_sc: '' });
      setKaurList(selected.data.kaur || []);
      setPncList(selected.data.pnc || []);
      setFeedback({ type: 'info', text: `Preset "${selected.name}" dimuat. Klik "Simpan ke Profil Aktif" untuk mengaktifkan.` });
    }
  };

  // Add new PNC row
  const handleAddPnc = () => {
    setPncList(prev => [...prev, { nama: '', nipp: '', no_sc: '' }]);
  };

  // Remove PNC row
  const handleRemovePnc = (index) => {
    setPncList(prev => prev.filter((_, i) => i !== index));
  };

  // Update PNC row
  const handlePncChange = (index, field, value) => {
    setPncList(prev => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  };

  // Add new KAUR row
  const handleAddKaur = () => {
    setKaurList(prev => [...prev, { nama: '', nipp: '', no_sc: '' }]);
  };

  // Remove KAUR row
  const handleRemoveKaur = (index) => {
    setKaurList(prev => prev.filter((_, i) => i !== index));
  };

  // Update KAUR row
  const handleKaurChange = (index, field, value) => {
    setKaurList(prev => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  };

  // Save current changes to the active/opened preset
  const handleSaveCurrentPreset = async () => {
    if (!activePresetId) {
      alert('Pilih preset terlebih dahulu.');
      return;
    }
    const presetIndex = presets.findIndex(p => p.id === activePresetId);
    if (presetIndex === -1) {
      alert('Preset tidak ditemukan dalam daftar.');
      return;
    }

    setSaving(true);
    setFeedback(null);
    try {
      const updatedPresets = [...presets];
      const targetPreset = updatedPresets[presetIndex];
      updatedPresets[presetIndex] = {
        ...targetPreset,
        updated_at: new Date().toISOString(),
        data: {
          resor,
          kaur: kaurList,
          pnc: pncList
        }
      };

      const payload = {
        active_preset_id: activePresetId,
        presets: updatedPresets,
        daftar_pegawai: {
          resor,
          kaur: kaurList,
          pnc: pncList
        }
      };

      const res = await fetch('/api/timemark/pegawai', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const result = await res.json();
      if (res.ok && result.ok) {
        setPresets(updatedPresets);
        setFeedback({
          type: 'success',
          text: `✓ Perubahan berhasil disimpan ke preset "${targetPreset.name}" dan aktif sebagai profil utama!`
        });
      } else {
        setFeedback({
          type: 'error',
          text: 'Gagal menyimpan preset: ' + (result.error || 'Terjadi kesalahan')
        });
      }
    } catch (err) {
      setFeedback({ type: 'error', text: 'Galat penyimpanan: ' + err.message });
    } finally {
      setSaving(false);
    }
  };

  // Save current profile to backend
  const handleSaveActive = async () => {
    setSaving(true);
    setFeedback(null);
    try {
      let updatedPresets = presets;
      if (activePresetId) {
        const pIdx = presets.findIndex(p => p.id === activePresetId);
        if (pIdx !== -1) {
          updatedPresets = [...presets];
          updatedPresets[pIdx] = {
            ...updatedPresets[pIdx],
            updated_at: new Date().toISOString(),
            data: { resor, kaur: kaurList, pnc: pncList }
          };
          setPresets(updatedPresets);
        }
      }

      const payload = {
        active_preset_id: activePresetId,
        presets: updatedPresets,
        daftar_pegawai: {
          resor,
          kaur: kaurList,
          pnc: pncList
        }
      };

      const res = await fetch('/api/timemark/pegawai', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const result = await res.json();
      if (res.ok && result.ok) {
        setFeedback({ type: 'success', text: '✓ Profil pegawai berhasil disimpan dan otomatis aktif untuk seluruh fitur!' });
      } else {
        setFeedback({ type: 'error', text: 'Gagal menyimpan: ' + (result.error || 'Terjadi kesalahan') });
      }
    } catch (err) {
      setFeedback({ type: 'error', text: 'Galat penyimpanan: ' + err.message });
    } finally {
      setSaving(false);
    }
  };

  // Create new preset
  const handleSaveNewPreset = async () => {
    const name = prompt('Masukkan nama preset baru (contoh: Reguler Shift Pagi, Roster 2026):');
    if (!name || !name.trim()) return;

    setSaving(true);
    try {
      const newPreset = {
        id: 'preset_' + Date.now(),
        name: name.trim(),
        created_at: new Date().toISOString(),
        data: {
          resor,
          kaur: kaurList,
          pnc: pncList
        }
      };

      const updatedPresets = [...presets, newPreset];
      const res = await fetch('/api/timemark/pegawai', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          active_preset_id: newPreset.id,
          presets: updatedPresets,
          daftar_pegawai: {
            resor,
            kaur: kaurList,
            pnc: pncList
          }
        })
      });

      if (res.ok) {
        setPresets(updatedPresets);
        setActivePresetId(newPreset.id);
        setFeedback({ type: 'success', text: `✓ Preset "${name}" berhasil dibuat dan diaktifkan.` });
      }
    } catch (err) {
      setFeedback({ type: 'error', text: 'Gagal membuat preset: ' + err.message });
    } finally {
      setSaving(false);
    }
  };

  // Export / Backup all presets to JSON file
  const handleExportPresets = async () => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch('/api/timemark/export-presets', { method: 'POST' });
      const data = await res.json();
      if (res.ok && data.ok) {
        setFeedback({
          type: 'success',
          text: `✓ ${data.message || 'Cadangan preset berhasil disimpan!'}`
        });
      } else if (data.cancelled) {
        // User cancelled dialog
      } else {
        setFeedback({
          type: 'error',
          text: 'Gagal mengekspor cadangan: ' + (data.error || 'Terjadi kesalahan')
        });
      }
    } catch (err) {
      setFeedback({ type: 'error', text: 'Galat ekspor: ' + err.message });
    } finally {
      setLoading(false);
    }
  };

  // Import / Restore presets from JSON backup file
  const handleImportPresets = async () => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch('/api/timemark/import-presets', { method: 'POST' });
      const data = await res.json();
      if (res.ok && data.ok) {
        if (data.presets) {
          setPresets(data.presets);
          const actId = data.active_preset_id || data.presets[0]?.id;
          setActivePresetId(actId);
          const activeObj = data.presets.find(p => p.id === actId);
          if (activeObj && activeObj.data) {
            setResor(activeObj.data.resor || { nama: '', nipp: '', no_sc: '' });
            setKaurList(activeObj.data.kaur || []);
            setPncList(activeObj.data.pnc || []);
          }
        }
        setFeedback({
          type: 'success',
          text: `✓ ${data.message || 'Preset berhasil dipulihkan dari cadangan!'}`
        });
      } else if (data.cancelled) {
        // User cancelled dialog
      } else {
        setFeedback({
          type: 'error',
          text: 'Gagal memulihkan preset: ' + (data.error || 'Terjadi kesalahan')
        });
      }
    } catch (err) {
      setFeedback({ type: 'error', text: 'Galat pemulihan: ' + err.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', height: '100%', width: '100%', overflowY: 'auto', paddingRight: '0.5rem' }}>
      
      {/* Header Panel */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem 1.25rem', width: '100%' }}>
        <div>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span>👥</span> Manajemen Profil Pegawai & Roster Dinasan
          </h3>
          <p style={{ fontSize: '0.825rem', color: 'var(--text-secondary)', margin: '0.25rem 0 0 0' }}>
            Tersimpan aman & permanen di AppData pengguna. Data otomatis dipakai untuk Koreksi Personil PDF, Tablo, dan Jadwal Dinasan.
          </p>
        </div>

        {/* Preset Selector & Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
          <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Pilih Preset:</label>
          <select
            value={activePresetId}
            onChange={(e) => handleSelectPreset(e.target.value)}
            style={{ padding: '0.45rem 0.75rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.85rem', minWidth: '150px' }}
          >
            {presets.map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          <button
            onClick={handleSaveCurrentPreset}
            disabled={saving || !activePresetId}
            title="Simpan perubahan langsung ke preset yang sedang dibuka ini"
            style={{ padding: '0.45rem 0.85rem', background: 'var(--accent)', color: '#ffffff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '0.825rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.35rem' }}
          >
            <span>💾</span> Simpan Preset Ini
          </button>
          <button
            onClick={handleSaveNewPreset}
            disabled={saving}
            title="Simpan data saat ini sebagai preset baru dengan nama berbeda"
            style={{ padding: '0.45rem 0.85rem', background: 'var(--bg-card-hover)', color: 'var(--text-primary)', border: '1px solid var(--border-color)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.825rem', fontWeight: 500 }}
          >
            + Preset Baru
          </button>
          <button
            onClick={handleExportPresets}
            disabled={saving || loading}
            title="Ekspor seluruh preset ke berkas JSON untuk cadangan"
            style={{ padding: '0.45rem 0.85rem', background: 'rgba(59, 130, 246, 0.12)', color: '#60A5FA', border: '1px solid rgba(59, 130, 246, 0.35)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.825rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.35rem' }}
          >
            <span>📤</span> Cadangkan
          </button>
          <button
            onClick={handleImportPresets}
            disabled={saving || loading}
            title="Pulihkan preset dari berkas JSON cadangan"
            style={{ padding: '0.45rem 0.85rem', background: 'rgba(16, 185, 129, 0.12)', color: '#34D399', border: '1px solid rgba(16, 185, 129, 0.35)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.825rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.35rem' }}
          >
            <span>📥</span> Pulihkan
          </button>
        </div>
      </div>

      {feedback && (
        <div style={{
          padding: '0.75rem 1rem',
          borderRadius: '6px',
          fontSize: '0.85rem',
          background: feedback.type === 'success' ? '#14532d' : feedback.type === 'error' ? '#7f1d1d' : '#1e3a5f',
          color: feedback.type === 'success' ? '#86efac' : feedback.type === 'error' ? '#fca5a5' : '#93c5fd',
          border: `1px solid ${feedback.type === 'success' ? '#22c55e' : feedback.type === 'error' ? '#ef4444' : '#3b82f6'}`
        }}>
          {feedback.text}
        </div>
      )}

      {/* Grid: KUPT Resor & KAUR */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>
        
        {/* KUPT Resor */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.25rem' }}>
          <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.85rem' }}>
            🏢 KUPT Resor Sintel
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <div>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.25rem' }}>Nama Lengkap & Gelar</label>
              <input
                type="text"
                value={resor.nama || ''}
                onChange={e => setResor(prev => ({ ...prev, nama: e.target.value }))}
                placeholder="Contoh: S. SLAMET RIYADI"
                style={{ width: '100%', padding: '0.5rem 0.75rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.85rem' }}
              />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <div>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.25rem' }}>NIPP</label>
                <input
                  type="text"
                  value={resor.nipp || ''}
                  onChange={e => setResor(prev => ({ ...prev, nipp: e.target.value }))}
                  placeholder="Contoh: 54321"
                  style={{ width: '100%', padding: '0.5rem 0.75rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.85rem' }}
                />
              </div>
              <div>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.25rem' }}>Nomor SC (Kompetensi)</label>
                <input
                  type="text"
                  value={resor.no_sc || ''}
                  onChange={e => setResor(prev => ({ ...prev, no_sc: e.target.value }))}
                  placeholder="Contoh: PRP.12345.67890"
                  style={{ width: '100%', padding: '0.5rem 0.75rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.85rem' }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* KAUR Preventif & Perbaikan */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.85rem' }}>
            <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
              🛡️ Kepala Urusan (KAUR)
            </h4>
            <button
              onClick={handleAddKaur}
              style={{ padding: '0.3rem 0.65rem', background: 'var(--bg-secondary)', color: 'var(--accent)', border: '1px solid var(--accent)', borderRadius: '5px', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 500 }}
            >
              + Tambah KAUR
            </button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '180px', overflowY: 'auto' }}>
            {kaurList.map((k, idx) => (
              <div key={idx} style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <input
                  type="text"
                  placeholder="Nama KAUR (Preventif / Perbaikan)"
                  value={k.nama || ''}
                  onChange={e => handleKaurChange(idx, 'nama', e.target.value)}
                  style={{ flex: 2, padding: '0.45rem 0.65rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '5px', color: 'var(--text-primary)', fontSize: '0.825rem' }}
                />
                <input
                  type="text"
                  placeholder="NIPP"
                  value={k.nipp || ''}
                  onChange={e => handleKaurChange(idx, 'nipp', e.target.value)}
                  style={{ flex: 1, padding: '0.45rem 0.65rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '5px', color: 'var(--text-primary)', fontSize: '0.825rem' }}
                />
                <input
                  type="text"
                  placeholder="No. SC"
                  value={k.no_sc || ''}
                  onChange={e => handleKaurChange(idx, 'no_sc', e.target.value)}
                  style={{ flex: 1.5, padding: '0.45rem 0.65rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '5px', color: 'var(--text-primary)', fontSize: '0.825rem' }}
                />
                <button
                  onClick={() => handleRemoveKaur(idx)}
                  style={{ padding: '0.45rem 0.65rem', background: '#7f1d1d', color: '#fca5a5', border: 'none', borderRadius: '5px', cursor: 'pointer', fontSize: '0.8rem' }}
                  title="Hapus baris KAUR"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Tabel Teknisi PNC */}
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <div>
            <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
              🔧 Daftar Teknisi Pemeliharaan (PNC)
            </h4>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: '0.25rem 0 0 0' }}>
              Teknisi yang melaksanakan pekerjaan di lapangan (Tim 1 dan Tim 2).
            </p>
          </div>
          <button
            onClick={handleAddPnc}
            style={{ padding: '0.4rem 0.85rem', background: 'var(--accent)', color: '#ffffff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '0.825rem', fontWeight: 500 }}
          >
            + Tambah Teknisi PNC
          </button>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ background: 'var(--bg-secondary)', color: 'var(--text-secondary)', textAlign: 'left', borderBottom: '1px solid var(--border-color)' }}>
                <th style={{ padding: '0.6rem 0.75rem', width: '40px' }}>No</th>
                <th style={{ padding: '0.6rem 0.75rem' }}>Nama Lengkap Teknisi</th>
                <th style={{ padding: '0.6rem 0.75rem', width: '160px' }}>NIPP</th>
                <th style={{ padding: '0.6rem 0.75rem', width: '220px' }}>Nomor Sertifikat (SC)</th>
                <th style={{ padding: '0.6rem 0.75rem', width: '60px', textAlign: 'center' }}>Aksi</th>
              </tr>
            </thead>
            <tbody>
              {pncList.map((p, idx) => (
                <tr key={idx} style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '0.6rem 0.75rem', color: 'var(--text-secondary)' }}>{idx + 1}</td>
                  <td style={{ padding: '0.6rem 0.75rem' }}>
                    <input
                      type="text"
                      value={p.nama || ''}
                      onChange={e => handlePncChange(idx, 'nama', e.target.value)}
                      placeholder="Nama teknisi..."
                      style={{ width: '100%', padding: '0.4rem 0.65rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '5px', color: 'var(--text-primary)', fontSize: '0.825rem' }}
                    />
                  </td>
                  <td style={{ padding: '0.6rem 0.75rem' }}>
                    <input
                      type="text"
                      value={p.nipp || ''}
                      onChange={e => handlePncChange(idx, 'nipp', e.target.value)}
                      placeholder="NIPP..."
                      style={{ width: '100%', padding: '0.4rem 0.65rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '5px', color: 'var(--text-primary)', fontSize: '0.825rem' }}
                    />
                  </td>
                  <td style={{ padding: '0.6rem 0.75rem' }}>
                    <input
                      type="text"
                      value={p.no_sc || ''}
                      onChange={e => handlePncChange(idx, 'no_sc', e.target.value)}
                      placeholder="Nomor SC..."
                      style={{ width: '100%', padding: '0.4rem 0.65rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '5px', color: 'var(--text-primary)', fontSize: '0.825rem' }}
                    />
                  </td>
                  <td style={{ padding: '0.6rem 0.75rem', textAlign: 'center' }}>
                    <button
                      onClick={() => handleRemovePnc(idx)}
                      style={{ padding: '0.35rem 0.6rem', background: '#7f1d1d', color: '#fca5a5', border: 'none', borderRadius: '5px', cursor: 'pointer', fontSize: '0.75rem' }}
                      title="Hapus baris teknisi"
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              ))}
              {pncList.length === 0 && (
                <tr>
                  <td colSpan="5" style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                    Belum ada data teknisi PNC. Klik tombol "+ Tambah Teknisi PNC" di atas.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Tombol Simpan Utama */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: 'auto', paddingTop: '0.5rem', flexWrap: 'wrap' }}>
        <button
          onClick={fetchEmployeeData}
          disabled={saving}
          style={{ padding: '0.65rem 1.25rem', background: 'var(--bg-secondary)', color: 'var(--text-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.85rem' }}
        >
          Muat Ulang
        </button>
        <button
          onClick={handleSaveCurrentPreset}
          disabled={saving || !activePresetId}
          style={{ padding: '0.65rem 1.5rem', background: 'var(--bg-card-hover)', color: 'var(--text-primary)', border: '1px solid var(--border-color)', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, fontSize: '0.875rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}
        >
          <span>💾</span> {saving ? 'Menyimpan...' : `Simpan ke Preset "${presets.find(p => p.id === activePresetId)?.name || 'Aktif'}"`}
        </button>
        <button
          onClick={handleSaveActive}
          disabled={saving}
          style={{ padding: '0.65rem 1.75rem', background: 'var(--accent)', color: '#ffffff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, fontSize: '0.875rem' }}
        >
          {saving ? 'Menyimpan...' : '💾 Simpan & Terapkan Profil Aktif'}
        </button>
      </div>

    </div>
  );
}
