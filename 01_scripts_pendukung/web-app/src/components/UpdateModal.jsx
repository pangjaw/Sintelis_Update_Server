import { useState, useEffect } from 'react';

export default function UpdateModal({ isOpen, onClose }) {
  const [serverUrl, setServerUrl] = useState(() => {
    return localStorage.getItem('sintelis_update_server_url') || 'https://update.sintelboo.my.id/version.json';
  });
  const [showSettings, setShowSettings] = useState(false);

  const [updateData, setUpdateData] = useState(null);
  const [loadingCheck, setLoadingCheck] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState({ percent: 0, downloaded: 0, status: 'idle' });
  const [isApplying, setIsApplying] = useState(false);

  useEffect(() => {
    if (isOpen) {
      checkUpdate();
    }
  }, [isOpen]);

  const checkUpdate = async () => {
    setLoadingCheck(true);
    try {
      const query = serverUrl ? `?url=${encodeURIComponent(serverUrl)}` : '';
      const res = await fetch(`/api/update/check${query}`);
      if (res.ok) {
        const data = await res.json();
        setUpdateData(data);
      }
    } catch (e) {
      setUpdateData({ error: e.message, offline: true });
    } finally {
      setLoadingCheck(false);
    }
  };

  const handleSaveUrl = (newUrl) => {
    setServerUrl(newUrl);
    localStorage.setItem('sintelis_update_server_url', newUrl);
  };

  const handleStartDownload = async () => {
    if (!updateData || !updateData.downloadUrl) return;
    try {
      setDownloadProgress({ percent: 1, downloaded: 0, status: 'downloading' });
      await fetch('/api/update/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ downloadUrl: updateData.downloadUrl })
      });

      const timer = setInterval(async () => {
        try {
          const res = await fetch('/api/update/progress');
          if (res.ok) {
            const data = await res.json();
            setDownloadProgress({
              percent: data.percent || 0,
              downloaded: data.downloaded_bytes || 0,
              status: data.status
            });
            if (data.status === 'ready' || data.status === 'error') {
              clearInterval(timer);
            }
          }
        } catch {
          clearInterval(timer);
        }
      }, 500);
    } catch (err) {
      alert('Gagal memulai unduhan: ' + err.message);
    }
  };

  const handleApplyUpdate = async () => {
    setIsApplying(true);
    try {
      await fetch('/api/update/apply', { method: 'POST' });
    } catch (err) {
      alert('Gagal memasang pembaruan: ' + err.message);
      setIsApplying(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }}>
      <div style={{ width: '520px', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '1.5rem', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.5)' }}>
        
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span>🚀</span> Pembaruan Aplikasi Sintelis Utility
          </h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', fontSize: '1.25rem', cursor: 'pointer' }}>
            ✕
          </button>
        </div>

        {/* Content */}
        {loadingCheck ? (
          <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
            Memeriksa pembaruan ke server Cloudflare...
          </div>
        ) : updateData?.error ? (
          <div style={{ padding: '1rem', background: 'rgba(255, 94, 125, 0.1)', border: '1px solid var(--danger)', borderRadius: '8px', color: 'var(--danger)', fontSize: '0.9rem', marginBottom: '1rem' }}>
            Tidak dapat terhubung ke server pembaruan: {updateData.error}
          </div>
        ) : updateData?.updateAvailable ? (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.75rem', background: 'var(--bg-secondary)', borderRadius: '8px', marginBottom: '1rem', fontSize: '0.88rem' }}>
              <div>Versi Saat Ini: <strong style={{ color: 'var(--text-secondary)' }}>v{updateData.currentVersion}</strong></div>
              <div>Versi Terbaru: <strong style={{ color: 'var(--accent)' }}>v{updateData.serverVersion}</strong></div>
            </div>

            {updateData.changelog && updateData.changelog.length > 0 && (
              <div style={{ marginBottom: '1rem' }}>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                  Catatan Pembaruan (Changelog):
                </div>
                <ul style={{ paddingLeft: '1.25rem', color: 'var(--text-primary)', fontSize: '0.85rem', lineHeight: 1.6 }}>
                  {updateData.changelog.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Download Progress Bar */}
            {downloadProgress.status === 'downloading' && (
              <div style={{ marginBottom: '1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '0.35rem' }}>
                  <span>Mengunduh biner baru...</span>
                  <span style={{ fontWeight: 600, color: 'var(--accent)' }}>{downloadProgress.percent}%</span>
                </div>
                <div style={{ width: '100%', height: '8px', background: 'var(--bg-secondary)', borderRadius: '4px', overflow: 'hidden' }}>
                  <div style={{ width: `${downloadProgress.percent}%`, height: '100%', background: 'var(--accent)' }} />
                </div>
              </div>
            )}

            {/* Actions */}
            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.25rem' }}>
              {downloadProgress.status === 'ready' ? (
                <button
                  onClick={handleApplyUpdate}
                  disabled={isApplying}
                  style={{ flex: 1, padding: '0.75rem', background: 'var(--accent)', color: '#0b0d15', border: 'none', borderRadius: '8px', fontWeight: 700, cursor: 'pointer' }}
                >
                  {isApplying ? 'Memasang & Membuka Ulang...' : '🔄 Pasang & Restart Sekarang'}
                </button>
              ) : downloadProgress.status === 'downloading' ? (
                <button disabled style={{ flex: 1, padding: '0.75rem', background: 'var(--bg-card-hover)', color: 'var(--text-secondary)', border: 'none', borderRadius: '8px' }}>
                  Mengunduh ({downloadProgress.percent}%)...
                </button>
              ) : (
                <button
                  onClick={handleStartDownload}
                  style={{ flex: 1, padding: '0.75rem', background: 'var(--accent)', color: '#0b0d15', border: 'none', borderRadius: '8px', fontWeight: 700, cursor: 'pointer' }}
                >
                  ⬇️ Unduh & Perbarui
                </button>
              )}
            </div>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-secondary)' }}>
            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>✓</div>
            <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
              Aplikasi Anda Sudah Terkini!
            </div>
            <div style={{ fontSize: '0.85rem' }}>Versi yang terpasang saat ini adalah v{updateData?.currentVersion || '1.4.0'}</div>
          </div>
        )}

        {/* Setting URL Collapse */}
        <div style={{ marginTop: '1.25rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-color)' }}>
          <button
            onClick={() => setShowSettings(!showSettings)}
            style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', fontSize: '0.8rem', cursor: 'pointer', textDecoration: 'underline' }}
          >
            {showSettings ? '▲ Sembunyikan Pengaturan URL Server' : '⚙️ Pengaturan Alamat URL Server Update'}
          </button>
          {showSettings && (
            <div style={{ marginTop: '0.5rem' }}>
              <input
                type="text"
                value={serverUrl}
                onChange={e => handleSaveUrl(e.target.value)}
                style={{ width: '100%', padding: '0.4rem 0.65rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.82rem' }}
                placeholder="https://update.sintelboo.my.id/version.json"
              />
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
