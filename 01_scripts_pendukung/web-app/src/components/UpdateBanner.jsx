import { useState, useEffect } from 'react';

export default function UpdateBanner({ onOpenModal, onAutoOpen }) {
  const [updateInfo, setUpdateInfo] = useState(null);

  useEffect(() => {
    const check = async () => {
      try {
        const customUrl = localStorage.getItem('sintelis_update_server_url') || '';
        const query = customUrl ? `?url=${encodeURIComponent(customUrl)}` : '';
        const res = await fetch(`/api/update/check${query}`);
        if (res.ok) {
          const data = await res.json();
          if (data.updateAvailable) {
            setUpdateInfo(data);
            if (onAutoOpen) {
              onAutoOpen(data);
            }
          }
        }
      } catch (e) {
        // Silent fail on network error / offline
      }
    };
    check();
  }, []);

  if (!updateInfo) return null;

  return (
    <div
      onClick={onOpenModal}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.5rem',
        padding: '0.35rem 0.85rem',
        background: 'rgba(0, 212, 170, 0.15)',
        border: '1px solid var(--accent)',
        borderRadius: '20px',
        color: 'var(--accent)',
        fontSize: '0.82rem',
        fontWeight: 600,
        cursor: 'pointer',
        animation: 'pulse 2s infinite'
      }}
      title="Klik untuk membuka jendela pembaruan"
    >
      <span>🚀</span>
      <span>Versi Baru Tersedia: v{updateInfo.serverVersion}</span>
      <span style={{ textDecoration: 'underline' }}>Perbarui Sekarang &rarr;</span>
    </div>
  );
}
