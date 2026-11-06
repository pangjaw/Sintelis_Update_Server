import React, { useState } from 'react';

export default function BentoHeader({
  activePreset = 'Standar (Resor 1.21 Bogor)',
  currentVersion = 'v1.8.0',
  serverVersion = null,
  updateAvailable = false,
  onOpenUpdateModal = null,
  mainTab = 'ocr',
  title = '',
  subtitle = ''
}) {
  // Simpan status ciutkan di localStorage agar preferensi tersimpan
  const [isCollapsed, setIsCollapsed] = useState(() => {
    try {
      const saved = localStorage.getItem('sintelis_bento_collapsed');
      if (saved !== null) return JSON.parse(saved);
      return mainTab === 'timemark'; // Default ciutkan di tab timemark agar galeri luas
    } catch (_) {
      return mainTab === 'timemark';
    }
  });

  const handleToggleCollapse = (val) => {
    setIsCollapsed(val);
    try {
      localStorage.setItem('sintelis_bento_collapsed', JSON.stringify(val));
    } catch (_) {}
  };

  const getTabMeta = () => {
    switch (mainTab) {
      case 'ocr':
        return {
          title: 'Penamaan Ceklis PDF (Rename PDF)',
          sub: 'Standardisasi penamaan dokumen otomatis sesuai format BTP JAK & BTP BD'
        };
      case 'audit_aset':
        return {
          title: 'Audit Kelengkapan Berkas Aset',
          sub: 'Pemeriksaan kelengkapan dokumen checklist pemeliharaan per periode & stasiun'
        };
      case 'downloader':
        return {
          title: 'Downloader Dokumen Rekap P3-STE',
          sub: 'Otomatisasi pengunduhan checklist PDF bulanan dari portal P3-STE'
        };
      case 'timemark':
        return {
          title: 'Timemark & Manajemen Berkas Lapangan',
          sub: 'Otomasi watermark koordinat, jadwal dinasan, tablo checklist, dan penggabungan PDF'
        };
      case 'ubah_tanggal':
        return {
          title: 'Ubah Tanggal Dokumen & Berkas PDF',
          sub: 'Penggantian tanggal nama file, formulir Halaman 1, dan header Halaman Foto secara kustom'
        };
      default:
        return {
          title: 'Sintelis Utility 2.0',
          sub: 'Platform otomasi cerdas persinyalan dan telekomunikasi'
        };
    }
  };

  const meta = getTabMeta();
  const displayTitle = title || meta.title;
  const displaySubtitle = subtitle || meta.sub;

  // 🌟 MODE ULTRA-COMPACT: Header ramping 1 baris (menghemat ~85px vertikal)
  if (isCollapsed) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '0.4rem 0.85rem',
          background: 'rgba(15, 23, 42, 0.75)',
          border: '1px solid var(--border-color)',
          borderRadius: '8px',
          marginBottom: '0.55rem',
          backdropFilter: 'blur(8px)',
          gap: '0.75rem',
          flexWrap: 'wrap'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <h2 style={{ fontSize: '0.98rem', fontWeight: 800, letterSpacing: '-0.01em', color: '#FFFFFF', margin: 0 }}>
            {displayTitle}
          </h2>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
            • {displaySubtitle}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {/* Versi Mini Badge */}
          <div
            onClick={() => onOpenUpdateModal && onOpenUpdateModal()}
            style={{
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              background: updateAvailable ? 'rgba(255, 115, 0, 0.18)' : 'rgba(16, 185, 129, 0.12)',
              border: `1px solid ${updateAvailable ? '#FF7300' : 'rgba(16, 185, 129, 0.28)'}`,
              padding: '0.2rem 0.55rem',
              borderRadius: '6px',
              fontSize: '0.72rem',
              transition: 'all 0.2s'
            }}
            title={updateAvailable ? `Versi aktif: ${currentVersion}. Versi baru ${serverVersion || ''} tersedia! Klik untuk memperbarui.` : `Versi aktif: ${currentVersion} (Terkini). Klik untuk periksa update.`}
          >
            <span style={{ color: updateAvailable ? '#FF9433' : 'var(--text-secondary)', fontWeight: 600 }}>VERSI:</span>
            <strong style={{ color: updateAvailable ? '#FF9433' : '#10B981' }}>{currentVersion}</strong>
            {updateAvailable ? (
              <span style={{ background: '#FF7300', color: '#ffffff', fontSize: '0.62rem', padding: '1px 5px', borderRadius: '4px', fontWeight: 700 }}>
                UPDATE
              </span>
            ) : (
              <span style={{ color: '#10B981', fontSize: '0.65rem', fontWeight: 700 }}>
                TERBARU
              </span>
            )}
          </div>

          {/* Preset Mini Badge */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              background: 'rgba(59, 130, 246, 0.12)',
              border: '1px solid rgba(59, 130, 246, 0.28)',
              padding: '0.2rem 0.55rem',
              borderRadius: '6px',
              fontSize: '0.72rem',
              maxWidth: '260px'
            }}
            title={`Preset Aktif: ${activePreset}`}
          >
            <span style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>PRESET:</span>
            <strong style={{ color: '#60A5FA', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {activePreset}
            </strong>
          </div>

          {/* Tombol Tampilkan Detail Bento */}
          <button
            type="button"
            onClick={() => handleToggleCollapse(false)}
            style={{
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-color)',
              color: 'var(--text-secondary)',
              borderRadius: '6px',
              padding: '0.2rem 0.5rem',
              fontSize: '0.7rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.25rem',
              fontWeight: 600
            }}
            title="Tampilkan kartu Bento lengkap"
          >
            <span>▼</span> Detail
          </button>
        </div>
      </div>
    );
  }

  // MODE NORMAL: Kartu Bento Lengkap
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '0.75rem' }}>
      {/* Title Banner & Tombol Ciutkan */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#FFFFFF', margin: 0 }}>
            {displayTitle}
          </h2>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: '2px 0 0 0' }}>
            {displaySubtitle}
          </p>
        </div>
        <button
          type="button"
          onClick={() => handleToggleCollapse(true)}
          style={{
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-color)',
            color: 'var(--text-secondary)',
            borderRadius: '6px',
            padding: '0.25rem 0.6rem',
            fontSize: '0.72rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.25rem',
            fontWeight: 600
          }}
          title="Ciutkan header agar ruang kerja lebih luas"
        >
          <span>▲</span> Ciutkan Header
        </button>
      </div>

      {/* 2 Bento Cards */}
      <div
        className="bento-header-grid"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
          gap: '0.75rem',
          width: '100%'
        }}
      >
        {/* Card 1: Versi Aplikasi */}
        <div
          className="bento-card"
          onClick={() => {
            if (onOpenUpdateModal) {
              onOpenUpdateModal();
            }
          }}
          style={{
            cursor: 'pointer',
            borderColor: updateAvailable ? '#FF7300' : 'var(--border-color)',
            boxShadow: updateAvailable
              ? '0 0 20px rgba(255, 115, 0, 0.55), inset 0 0 12px rgba(255, 115, 0, 0.2)'
              : 'none',
            background: updateAvailable
              ? 'linear-gradient(135deg, rgba(255, 115, 0, 0.16) 0%, var(--bg-card) 75%)'
              : 'var(--bg-card)',
            transition: 'all 0.3s ease'
          }}
          title={updateAvailable ? `Versi aktif: ${currentVersion}. Versi baru ${serverVersion || ''} tersedia! Klik untuk memperbarui.` : `Versi aktif: ${currentVersion} (Terkini). Klik untuk periksa pembaruan.`}
        >
          <div className="bento-card-top">
            <span className="bento-card-label" style={{ color: updateAvailable ? '#FF9433' : 'var(--text-secondary)' }}>
              VERSI APLIKASI
            </span>
            {updateAvailable ? (
              <span
                style={{
                  fontSize: '0.7rem',
                  padding: '2px 8px',
                  borderRadius: '12px',
                  background: '#FF7300',
                  color: '#FFFFFF',
                  fontWeight: 700,
                  boxShadow: '0 0 10px #FF7300',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  animation: 'pulse 1.8s infinite ease-in-out'
                }}
              >
                <span style={{ fontSize: '0.6rem' }}>●</span> UPDATE {serverVersion ? `${serverVersion} ` : ''}TERSEDIA
              </span>
            ) : (
              <span
                style={{
                  fontSize: '0.7rem',
                  padding: '1px 6px',
                  borderRadius: '4px',
                  background: 'rgba(16, 185, 129, 0.15)',
                  color: '#10B981',
                  fontWeight: 600
                }}
              >
                TERBARU
              </span>
            )}
          </div>
          <div
            className="bento-card-value"
            style={{
              color: updateAvailable ? '#FF9433' : '#FFFFFF',
              textShadow: updateAvailable ? '0 0 12px rgba(255, 115, 0, 0.6)' : 'none'
            }}
          >
            {currentVersion}
          </div>
          <div className="bento-card-sub" style={{ color: updateAvailable ? '#FFAA5B' : 'var(--text-secondary)' }}>
            {updateAvailable ? `⚡ Update ${serverVersion || 'baru'} tersedia — Klik untuk perbarui!` : 'Sintelis Desktop Suite (Klik untuk periksa update)'}
          </div>
        </div>

        {/* Card 2: Profil Preset Pegawai Aktif */}
        <div className="bento-card">
          <div className="bento-card-top">
            <span className="bento-card-label">PROFIL PRESET AKTIF</span>
            <span
              style={{
                fontSize: '0.7rem',
                padding: '1px 6px',
                borderRadius: '4px',
                background: 'rgba(59, 130, 246, 0.15)',
                color: '#60A5FA',
                fontWeight: 600
              }}
            >
              TERPILIH
            </span>
          </div>
          <div
            className="bento-card-value"
            style={{
              color: '#FFFFFF',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis'
            }}
            title={activePreset}
          >
            {activePreset}
          </div>
          <div className="bento-card-sub">
            KUPT & Roster Personil Lapangan
          </div>
        </div>
      </div>
    </div>
  );
}
