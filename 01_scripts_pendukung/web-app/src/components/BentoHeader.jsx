import React from 'react';

export default function BentoHeader({
  activePreset = 'Standar (Resor 1.21 Bogor)',
  currentVersion = 'v1.7.1',
  serverVersion = null,
  updateAvailable = false,
  onOpenUpdateModal = null,
  mainTab = 'ocr',
  title = '',
  subtitle = ''
}) {
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', marginBottom: '0.85rem' }}>
      {/* ── Title Banner ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#FFFFFF', margin: 0 }}>
            {displayTitle}
          </h2>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: '2px 0 0 0' }}>
            {displaySubtitle}
          </p>
        </div>
      </div>

      {/* ── 2 Bento Cards: Versi Aplikasi (Glow Orange jika ada update) & Profil Preset ── */}
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
