import React from 'react';

export default function Sidebar({
  mainTab,
  setMainTab,
  isCollapsed,
  setIsCollapsed
}) {
  const menuItems = [
    {
      id: 'ocr',
      title: 'Rename PDF',
      sub: 'Penamaan & Format Ceklis',
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
          <line x1="16" y1="13" x2="8" y2="13"></line>
          <line x1="16" y1="17" x2="8" y2="17"></line>
          <polyline points="10 9 9 9 8 9"></polyline>
        </svg>
      )
    },
    {
      id: 'audit_aset',
      title: 'Audit Aset',
      sub: 'Audit Kelengkapan Aset',
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 11l3 3L22 4"></path>
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
        </svg>
      )
    },
    {
      id: 'downloader',
      title: 'Downloader P3-STE',
      sub: 'Unduh Rekap Otomatis',
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
          <polyline points="7 10 12 15 17 10"></polyline>
          <line x1="12" y1="15" x2="12" y2="3"></line>
        </svg>
      )
    },
    {
      id: 'timemark',
      title: 'Timemark & Berkas',
      sub: 'Watermark & Dokumen Excel',
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <polyline points="12 6 12 12 16 14"></polyline>
        </svg>
      )
    },
    {
      id: 'ubah_tanggal',
      title: 'Ubah Tanggal',
      sub: 'Ganti Tanggal Dokumen & File',
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
          <line x1="16" y1="2" x2="16" y2="6"></line>
          <line x1="8" y1="2" x2="8" y2="6"></line>
          <line x1="3" y1="10" x2="21" y2="10"></line>
          <path d="M12 14l2 2 4-4"></path>
        </svg>
      )
    }
  ];

  return (
    <aside
      className={`app-sidebar ${isCollapsed ? 'collapsed' : ''}`}
      style={{
        width: isCollapsed ? '72px' : '250px',
        minWidth: isCollapsed ? '72px' : '250px',
        transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        background: 'var(--bg-glass)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        borderRight: '1px solid var(--border-glass)',
        zIndex: 50,
        userSelect: 'none'
      }}
    >
      {/* ── Brand Header ── */}
      <div
        style={{
          padding: isCollapsed ? '1.25rem 0.5rem' : '1.25rem 1.25rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.75rem',
          borderBottom: '1px solid var(--border-glass)',
          justifyContent: isCollapsed ? 'center' : 'flex-start'
        }}
      >
        <div
          style={{
            width: '38px',
            height: '38px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, #FF7300 0%, #E05300 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#FFFFFF',
            fontWeight: 800,
            fontSize: '1.15rem',
            boxShadow: '0 0 15px rgba(255, 115, 0, 0.35)',
            flexShrink: 0
          }}
        >
          S
        </div>
        {!isCollapsed && (
          <div style={{ overflow: 'hidden' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
              <span style={{ fontWeight: 800, fontSize: '0.98rem', letterSpacing: '-0.02em', color: '#FFFFFF' }}>
                SINTELIS 2.0
              </span>
              <span
                style={{
                  width: '7px',
                  height: '7px',
                  borderRadius: '50%',
                  background: '#10B981',
                  boxShadow: '0 0 8px #10B981'
                }}
                title="Sistem Online & Siap"
              />
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
              KAI Resor 1.21 Bogor
            </div>
          </div>
        )}
      </div>

      {/* ── Main Navigation List ── */}
      <nav style={{ flex: 1, padding: '1rem 0.6rem', display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
        {menuItems.map(item => {
          const isActive = mainTab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setMainTab(item.id)}
              title={isCollapsed ? item.title : undefined}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.85rem',
                width: '100%',
                padding: isCollapsed ? '0.75rem 0' : '0.75rem 0.9rem',
                justifyContent: isCollapsed ? 'center' : 'flex-start',
                borderRadius: '8px',
                border: 'none',
                borderLeft: isActive ? '3px solid var(--accent-orange)' : '3px solid transparent',
                background: isActive
                  ? 'linear-gradient(90deg, rgba(255, 115, 0, 0.16) 0%, rgba(255, 115, 0, 0.03) 100%)'
                  : 'transparent',
                color: isActive ? '#FFFFFF' : 'var(--text-secondary)',
                cursor: 'pointer',
                transition: 'all 0.18s ease',
                textAlign: 'left'
              }}
              className="sidebar-nav-btn"
            >
              <div
                style={{
                  color: isActive ? 'var(--accent-orange)' : 'var(--text-secondary)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  filter: isActive ? 'drop-shadow(0 0 6px rgba(255, 115, 0, 0.5))' : 'none',
                  flexShrink: 0
                }}
              >
                {item.icon}
              </div>
              {!isCollapsed && (
                <div style={{ overflow: 'hidden' }}>
                  <div style={{ fontSize: '0.86rem', fontWeight: isActive ? 600 : 500, color: isActive ? '#FFFFFF' : 'var(--text-secondary)' }}>
                    {item.title}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: isActive ? 'rgba(255,255,255,0.6)' : 'rgba(148, 163, 184, 0.6)', marginTop: '1px' }}>
                    {item.sub}
                  </div>
                </div>
              )}
            </button>
          );
        })}
      </nav>

      {/* ── Bottom Section: Version, Updates, Collapse Toggle ── */}
      <div
        style={{
          padding: isCollapsed ? '1rem 0.5rem' : '1rem 0.9rem',
          borderTop: '1px solid var(--border-glass)',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.6rem'
        }}
      >

        {/* Collapse / Expand Toggle Button */}
        <button
          type="button"
          onClick={() => setIsCollapsed(!isCollapsed)}
          title={isCollapsed ? 'Perlebar Menu' : 'Perkecil Menu'}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem',
            width: '100%',
            padding: '0.45rem',
            background: 'transparent',
            border: 'none',
            color: 'var(--text-secondary)',
            fontSize: '0.76rem',
            cursor: 'pointer',
            borderRadius: '6px',
            transition: 'color 0.15s ease'
          }}
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{
              transform: isCollapsed ? 'rotate(180deg)' : 'none',
              transition: 'transform 0.2s ease'
            }}
          >
            <polyline points="11 19 4 12 11 5"></polyline>
            <polyline points="18 19 11 12 18 5"></polyline>
          </svg>
          {!isCollapsed && <span>Ciutkan Sidebar</span>}
        </button>
      </div>
    </aside>
  );
}
