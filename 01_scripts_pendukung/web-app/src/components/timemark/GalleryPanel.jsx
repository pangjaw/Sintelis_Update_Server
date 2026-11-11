import { useState, useEffect, useMemo, useRef } from 'react';
import { MASTER_CATEGORIES, CATEGORY_LABEL_MAP, normalizeCategory } from '../../utils/masterAssets';

// =============================================================================
// Helper Kalkulasi Tanggal Otomatis (0%, 50%, 100%)
// =============================================================================
function helperCalculateDate(baseDate, photoStem) {
  let cleanDate = (baseDate || '').trim();
  const m = cleanDate.match(/^(.*?\d{4})\s+(\d{2}):(\d{2})$/);
  if (!m) {
    if (cleanDate) {
      const defaultTime = photoStem === '50' ? '08:22' : (photoStem === '100' ? '08:45' : '08:00');
      return `${cleanDate} ${defaultTime}`;
    }
    return cleanDate;
  }

  const [_, datePart, hh, mm] = m;
  let totalMin = parseInt(hh, 10) * 60 + parseInt(mm, 10);
  let pct = 0;
  if (photoStem === '50') pct = 50;
  else if (photoStem === '100') pct = 100;
  const duration = 45;
  totalMin += Math.round((pct * duration) / 100);

  const newHH = String(Math.floor(totalMin / 60) % 24).padStart(2, '0');
  const newMM = String(totalMin % 60).padStart(2, '0');
  return `${datePart} ${newHH}:${newMM}`;
}

const getDetectorInfo = (det) => {
  if (det === 'paddle_ocr' || det === 'lama_ai') {
    return {
      label: 'LaMa AI (Hapus Teks)',
      shortLabel: 'LaMa AI',
      icon: '',
      gradient: 'linear-gradient(135deg, #059669 0%, #10b981 100%)',
      btnBg: 'rgba(16, 185, 129, 0.2)',
      btnColor: '#34d399',
      border: '1px solid #10b981',
      shadow: '0 2px 6px rgba(16, 185, 129, 0.4)'
    };
  }
  if (det === 'google_vision') {
    return {
      label: 'Google AI Vision',
      shortLabel: 'AI Vision',
      icon: '✨',
      gradient: 'linear-gradient(135deg, #7e22ce 0%, #9333ea 100%)',
      btnBg: 'rgba(168, 85, 247, 0.2)',
      btnColor: '#c084fc',
      border: '1px solid #a855f7',
      shadow: '0 2px 6px rgba(147, 51, 234, 0.4)'
    };
  }
  return {
    label: 'Metode Biasa (HSV)',
    shortLabel: 'HSV',
    icon: '⚡',
    gradient: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
    btnBg: 'rgba(2, 132, 199, 0.2)',
    btnColor: '#38bdf8',
    border: '1px solid #0284c7',
    shadow: '0 2px 6px rgba(2, 132, 199, 0.4)'
  };
};

// =============================================================================
// Komponen Kotak Timemark Interaktif yang Dapat Digeser (Inline Draggable Box)
// =============================================================================
function InlineTimemarkBox({
  asset,
  photo,
  photoName,
  targetKey,
  localCoord,
  exportDir,
  activeDetector = 'paddle_ocr',
  lastTimemarkPos,
  onPosChange,
  onSaved,
  onOpenModal
}) {
  const boxRef = useRef(null);
  const isValidCoord = (n) => typeof n === 'number' && !isNaN(n) && n >= 0 && n <= 295;
  const validMetaX = (photo?.meta?.xPos !== undefined && photo?.meta?.xPos !== null) ? Number(photo.meta.xPos) : null;
  const validMetaY = (photo?.meta?.yPos !== undefined && photo?.meta?.yPos !== null) ? Number(photo.meta.yPos) : null;

  // Prioritaskan koordinat lokal yang baru saja digeser user pada foto ini
  const initialX = isValidCoord(localCoord?.x) ? localCoord.x : (isValidCoord(validMetaX) ? validMetaX : 14);
  const initialY = isValidCoord(localCoord?.y) ? localCoord.y : (isValidCoord(validMetaY) ? validMetaY : 220);
  const [pos, setPos] = useState({
    x: initialX,
    y: initialY
  });
  const [dragging, setDragging] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);

  useEffect(() => {
    // Sinkronisasi posisi jika foto ini memiliki koordinat lokal tersimpan sendiri atau meta tersimpan
    if (isValidCoord(localCoord?.x) && isValidCoord(localCoord?.y)) {
      setPos({ x: localCoord.x, y: localCoord.y });
    } else {
      const curX = (photo?.meta?.xPos !== undefined && photo?.meta?.xPos !== null) ? Number(photo.meta.xPos) : null;
      const curY = (photo?.meta?.yPos !== undefined && photo?.meta?.yPos !== null) ? Number(photo.meta.yPos) : null;
      if (isValidCoord(curX) && isValidCoord(curY)) {
        setPos({ x: curX, y: curY });
      } else if (!isValidCoord(pos.x) || !isValidCoord(pos.y)) {
        setPos({ x: 14, y: 220 });
      }
    }
    if (boxRef.current) {
      const targetPos = isValidCoord(localCoord?.x) && isValidCoord(localCoord?.y)
        ? { x: localCoord.x, y: localCoord.y }
        : pos;
      boxRef.current.style.left = `${(targetPos.x / 300) * 100}%`;
      boxRef.current.style.top = `${(targetPos.y / 300) * 100}%`;
    }
  }, [localCoord?.x, localCoord?.y, localCoord?.ts, photo?.meta?.xPos, photo?.meta?.yPos, photo?.meta?.timestamp, photo?.meta?.updatedAt]);

  const handlePointerDown = (e) => {
    if (e.button !== 0 && e.pointerType === 'mouse') return;
    e.stopPropagation();
    e.preventDefault();

    const boxEl = e.currentTarget;
    const containerEl = boxEl.parentElement;
    if (!containerEl) return;

    const imgEl = containerEl.querySelector('img');
    const containerW = (imgEl && imgEl.clientWidth > 10) ? imgEl.clientWidth : containerEl.clientWidth;
    const containerH = (imgEl && imgEl.clientHeight > 10) ? imgEl.clientHeight : containerEl.clientHeight;

    const startPointerX = e.clientX;
    const startPointerY = e.clientY;
    const startLeft = boxEl.offsetLeft;
    const startTop = boxEl.offsetTop;
    let hasMoved = false;

    setDragging(true);

    let lastNormX = pos.x;
    let lastNormY = pos.y;

    const onPointerMove = (ev) => {
      ev.preventDefault();
      const dx = ev.clientX - startPointerX;
      const dy = ev.clientY - startPointerY;
      if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
        hasMoved = true;
      }
      const maxLeft = Math.max(0, containerW - boxEl.offsetWidth);
      const maxTop = Math.max(0, containerH - boxEl.offsetHeight);
      const newLeft = Math.max(0, Math.min(maxLeft, startLeft + dx));
      const newTop = Math.max(0, Math.min(maxTop, startTop + dy));

      lastNormX = Math.min(280, Math.max(0, Math.round((newLeft / (containerW || 1)) * 300)));
      lastNormY = Math.min(280, Math.max(0, Math.round((newTop / (containerH || 1)) * 300)));

      boxEl.style.left = `${(newLeft / (containerW || 1)) * 100}%`;
      boxEl.style.top = `${(newTop / (containerH || 1)) * 100}%`;
    };

    const onPointerUp = async (ev) => {
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
      window.removeEventListener('pointercancel', onPointerUp);
      setDragging(false);

      if (!hasMoved) {
        if (onOpenModal) onOpenModal();
        return;
      }

      // Kunci koordinat ternormalisasi (0 - 300) di memori foto ini secara permanen
      setPos({ x: lastNormX, y: lastNormY });
      if (boxRef.current) {
        boxRef.current.style.left = `${(lastNormX / 300) * 100}%`;
        boxRef.current.style.top = `${(lastNormY / 300) * 100}%`;
      }
      if (onPosChange) {
        onPosChange(targetKey, { x: lastNormX, y: lastNormY });
      }

      let dateText = photo?.meta?.dateText || asset.dateText || '';
      if (!photo?.meta?.dateText && asset.dateText) {
        if (photoName === '50.jpg') dateText = helperCalculateDate(asset.dateText, '50');
        else if (photoName === '100.jpg') dateText = helperCalculateDate(asset.dateText, '100');
      }

      setSaving(true);
      try {
        const rawRelPath = targetKey || `${asset.relDir}/${photoName}`;
        const res = await fetch('/api/timemark/manual-edit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            baseExportDir: exportDir,
            rawRelPath,
            dateText,
            yPos: lastNormY,
            xPos: lastNormX,
            applyToFolder: false, // HANYA FOTO INI
            saveOnly: true,       // INSTAN 0 ms: simpan koordinat murni tanpa komputasi gambar
            detector: activeDetector
          })
        });
        const data = await res.json();
        if (res.ok && data.ok) {
          setSavedFlash(true);
          setTimeout(() => setSavedFlash(false), 900);
          if (onSaved) onSaved({ targetKey: rawRelPath, xPos: lastNormX, yPos: lastNormY, dateText });
        }
      } catch (err) {
        console.error('Error saving inline box pos:', err);
      } finally {
        setSaving(false);
      }
    };

    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
    window.addEventListener('pointercancel', onPointerUp);
  };

  const displayText = photo?.meta?.dateText || (
    photoName === '50.jpg' ? helperCalculateDate(asset.dateText, '50') :
    photoName === '100.jpg' ? helperCalculateDate(asset.dateText, '100') :
    asset.dateText || ''
  );

  return (
    <div
      ref={boxRef}
      className="inline-timemark-box"
      draggable={false}
      onDragStart={(e) => { e.preventDefault(); e.stopPropagation(); }}
      onPointerDown={handlePointerDown}
      style={{
        position: 'absolute',
        top: `${(pos.y / 300) * 100}%`,
        left: `${(pos.x / 300) * 100}%`,
        minWidth: '32%',
        width: 'fit-content',
        maxWidth: '92%',
        height: 'auto',
        minHeight: '14px',
        border: dragging ? '1.5px solid #38bdf8' : savedFlash ? '1.5px solid #22c55e' : '1px dashed rgba(56, 189, 248, 0.4)',
        background: dragging ? 'rgba(15, 23, 42, 0.78)' : savedFlash ? 'rgba(34, 197, 94, 0.25)' : 'transparent',
        boxShadow: dragging ? '0 0 10px rgba(56, 189, 248, 0.75)' : savedFlash ? '0 0 8px rgba(34, 197, 94, 0.75)' : 'none',
        borderRadius: '3px',
        cursor: dragging ? 'grabbing' : 'grab',
        zIndex: 25,
        display: 'flex',
        alignItems: 'center',
        gap: '3px',
        padding: '1px 4px',
        userSelect: 'none',
        touchAction: 'none',
        boxSizing: 'border-box',
        transition: dragging ? 'none' : 'border 0.2s, background 0.2s'
      }}
      title="✥ Watermark Timemark: Geser bebas ke posisi yang diinginkan. Tanggal akan ditempel saat klik Merge PDF."
    >
      <span
        style={{
          fontFamily: '"Roboto", "Segoe UI", sans-serif',
          fontSize: 'calc(7px + 0.2vw)',
          fontWeight: 700,
          color: dragging ? '#38bdf8' : '#f8f8f8',
          textShadow: '0 1px 2px rgba(0,0,0,0.95), 0 0 1.5px #000',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          pointerEvents: 'none',
          lineHeight: 1.15,
          letterSpacing: '0.1px'
        }}
      >
        {displayText || 'Timemark'}
      </span>
      {savedFlash && (
        <span style={{ fontSize: '7px', background: '#22c55e', color: '#fff', padding: '0 3px', borderRadius: '2px', fontWeight: 800 }}>
          ✓
        </span>
      )}
    </div>
  );
}

// =============================================================================
// Komponen Modal Edit Tanggal Baris Aset (Langsung 3 Foto: 0%, 50%, 100%)
// =============================================================================
function RowDateEditorModal({ isOpen, onClose, asset, exportDir, onSaved }) {
  if (!isOpen || !asset) return null;

  const [baseDate, setBaseDate] = useState(asset.dateText || '');
  const [autoInterval, setAutoInterval] = useState(true);
  const [customDates, setCustomDates] = useState({
    '0.jpg': asset.dateText || '',
    '50.jpg': helperCalculateDate(asset.dateText || '', '50'),
    '100.jpg': helperCalculateDate(asset.dateText || '', '100')
  });
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  const computed0 = baseDate.trim();
  const computed50 = autoInterval ? helperCalculateDate(baseDate.trim(), '50') : customDates['50.jpg'];
  const computed100 = autoInterval ? helperCalculateDate(baseDate.trim(), '100') : customDates['100.jpg'];

  const handleUseCurrentTime = () => {
    const now = new Date();
    const days = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu'];
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];
    const dayName = days[now.getDay()];
    const monName = months[now.getMonth()];
    const dd = String(now.getDate()).padStart(2, '0');
    const yyyy = now.getFullYear();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    const str = `${dayName}, ${monName} ${dd} ${yyyy} ${hh}:${mm}`;
    setBaseDate(str);
    if (!autoInterval) {
      setCustomDates({
        '0.jpg': str,
        '50.jpg': helperCalculateDate(str, '50'),
        '100.jpg': helperCalculateDate(str, '100')
      });
    }
  };

  const handleSave = async () => {
    if (!baseDate.trim()) {
      setErrorMsg('Tanggal acuan tidak boleh kosong.');
      return;
    }
    setSaving(true);
    setErrorMsg(null);
    try {
      const datesPayload = {
        '0.jpg': computed0,
        '50.jpg': computed50,
        '100.jpg': computed100
      };
      const res = await fetch('/api/timemark/manual-edit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          baseExportDir: exportDir,
          rawRelPath: asset.relDir,
          dateText: baseDate.trim(),
          datesPerPhoto: datesPayload,
          applyToFolder: true,
          saveOnly: true,
          timGroup: 'Tim_1'
        })
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        throw new Error(data.error || 'Gagal menyimpan tanggal');
      }
      if (onSaved) {
        onSaved({
          assetRel: asset.relDir,
          baseDate: baseDate.trim(),
          dates: datesPayload
        });
      }
      onClose();
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(4px)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1rem'
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'var(--bg-card, #1e293b)',
          border: '1px solid var(--border-color, #334155)',
          borderRadius: '12px',
          width: '100%',
          maxWidth: '540px',
          boxShadow: '0 20px 40px rgba(0,0,0,0.5)',
          color: 'var(--text-primary, #f8fafc)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column'
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--border-color, #334155)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>🗓️</span> Edit Tanggal 3 Foto Sekaligus
            </h3>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.2rem' }}>
              {asset.station} • {asset.category || asset.asset_type} • <strong style={{ color: '#f1f5f9' }}>{asset.detail}</strong>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: '#94a3b8', fontSize: '1.25rem', cursor: 'pointer', lineHeight: 1 }}
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {errorMsg && (
            <div style={{ padding: '0.6rem 0.8rem', borderRadius: '6px', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid #ef4444', color: '#f87171', fontSize: '0.8rem' }}>
              ⚠️ {errorMsg}
            </div>
          )}

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 700, color: '#f8fafc' }}>
                Tanggal & Jam Acuan (Foto 0%)
              </label>
              <button
                type="button"
                onClick={handleUseCurrentTime}
                style={{ fontSize: '0.72rem', color: '#38bdf8', background: 'rgba(56, 189, 248, 0.12)', border: '1px solid rgba(56, 189, 248, 0.3)', padding: '0.2rem 0.5rem', borderRadius: '4px', cursor: 'pointer' }}
              >
                ⚡ Waktu Sekarang
              </button>
            </div>
            <input
              type="text"
              value={baseDate}
              onChange={e => setBaseDate(e.target.value)}
              placeholder="Contoh: Senin, Apr 28 2025 08:00"
              style={{
                width: '100%',
                padding: '0.6rem 0.8rem',
                borderRadius: '6px',
                background: 'rgba(15, 23, 42, 0.6)',
                border: '1px solid rgba(56, 189, 248, 0.4)',
                color: '#ffffff',
                fontSize: '0.9rem',
                fontWeight: 600,
                outline: 'none',
                boxSizing: 'border-box'
              }}
            />
            <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '0.3rem' }}>
              Format standar: <code style={{ color: '#34d399' }}>Hari, Bulan Tgl Tahun JJ:MM</code>
            </div>
          </div>

          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', color: '#cbd5e1', cursor: 'pointer', userSelect: 'none' }}>
            <input
              type="checkbox"
              checked={autoInterval}
              onChange={e => setAutoInterval(e.target.checked)}
              style={{ cursor: 'pointer', accentColor: '#10b981' }}
            />
            <span>Otomatis beri jeda menit standar dinasan (+22 mnt Foto 50%, +45 mnt Foto 100%)</span>
          </label>

          {/* Realtime 3 Photo Previews / Inputs */}
          <div style={{ background: 'rgba(15, 23, 42, 0.4)', border: '1px solid rgba(100, 116, 139, 0.25)', borderRadius: '8px', padding: '0.8rem', display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Pratinjau Nilai Tanggal Pada 3 Foto:
            </div>

            {/* 0% */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem', fontSize: '0.8rem' }}>
              <span style={{ fontWeight: 700, color: '#38bdf8', minWidth: '70px' }}>Foto 0%:</span>
              <span style={{ flex: 1, color: '#f1f5f9', background: 'rgba(255,255,255,0.05)', padding: '0.3rem 0.6rem', borderRadius: '4px', fontFamily: 'monospace' }}>
                {computed0 || <em style={{ color: '#64748b' }}>Belum diisi</em>}
              </span>
            </div>

            {/* 50% */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem', fontSize: '0.8rem' }}>
              <span style={{ fontWeight: 700, color: '#34d399', minWidth: '70px' }}>Foto 50%:</span>
              {autoInterval ? (
                <span style={{ flex: 1, color: '#f1f5f9', background: 'rgba(255,255,255,0.05)', padding: '0.3rem 0.6rem', borderRadius: '4px', fontFamily: 'monospace', display: 'flex', justifyContent: 'space-between' }}>
                  <span>{computed50 || <em style={{ color: '#64748b' }}>-</em>}</span>
                  <span style={{ fontSize: '0.7rem', color: '#34d399', opacity: 0.8 }}>+22 mnt</span>
                </span>
              ) : (
                <input
                  type="text"
                  value={customDates['50.jpg'] || ''}
                  onChange={e => setCustomDates(prev => ({ ...prev, '50.jpg': e.target.value }))}
                  placeholder="Tanggal Foto 50%"
                  style={{ flex: 1, padding: '0.3rem 0.6rem', borderRadius: '4px', background: 'rgba(15, 23, 42, 0.8)', border: '1px solid #475569', color: '#fff', fontSize: '0.8rem' }}
                />
              )}
            </div>

            {/* 100% */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem', fontSize: '0.8rem' }}>
              <span style={{ fontWeight: 700, color: '#a78bfa', minWidth: '70px' }}>Foto 100%:</span>
              {autoInterval ? (
                <span style={{ flex: 1, color: '#f1f5f9', background: 'rgba(255,255,255,0.05)', padding: '0.3rem 0.6rem', borderRadius: '4px', fontFamily: 'monospace', display: 'flex', justifyContent: 'space-between' }}>
                  <span>{computed100 || <em style={{ color: '#64748b' }}>-</em>}</span>
                  <span style={{ fontSize: '0.7rem', color: '#a78bfa', opacity: 0.8 }}>+45 mnt</span>
                </span>
              ) : (
                <input
                  type="text"
                  value={customDates['100.jpg'] || ''}
                  onChange={e => setCustomDates(prev => ({ ...prev, '100.jpg': e.target.value }))}
                  placeholder="Tanggal Foto 100%"
                  style={{ flex: 1, padding: '0.3rem 0.6rem', borderRadius: '4px', background: 'rgba(15, 23, 42, 0.8)', border: '1px solid #475569', color: '#fff', fontSize: '0.8rem' }}
                />
              )}
            </div>
          </div>
          
          <div style={{ fontSize: '0.72rem', color: '#94a3b8', background: 'rgba(56, 189, 248, 0.08)', border: '1px solid rgba(56, 189, 248, 0.2)', borderRadius: '6px', padding: '0.5rem 0.75rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <span>💡</span>
            <span>Tanggal baru langsung aktif seketika di kartu foto & tersimpan di meta.json tanpa perlu deteksi ulang.</span>
          </div>
        </div>

        {/* Footer */}
        <div style={{ padding: '0.85rem 1.25rem', borderTop: '1px solid var(--border-color, #334155)', display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', background: 'rgba(15, 23, 42, 0.3)' }}>
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            style={{ padding: '0.45rem 1rem', borderRadius: '6px', border: '1px solid #475569', background: 'transparent', color: '#cbd5e1', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600 }}
          >
            Batal
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || !baseDate.trim()}
            style={{
              padding: '0.45rem 1.2rem',
              borderRadius: '6px',
              border: 'none',
              background: saving ? '#64748b' : 'linear-gradient(135deg, #059669 0%, #10b981 100%)',
              color: '#ffffff',
              cursor: saving ? 'not-allowed' : 'pointer',
              fontSize: '0.8rem',
              fontWeight: 800,
              boxShadow: saving ? 'none' : '0 2px 8px rgba(16, 185, 129, 0.4)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem'
            }}
          >
            <span>{saving ? '⏳' : '💾'}</span>
            <span>{saving ? 'Menyimpan...' : 'Simpan ke 3 Foto'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Modal Editor Timemark Interaktif & Komparasi Berdampingan
// =============================================================================
function TimemarkEditorModal({
  isOpen,
  onClose,
  asset,
  photo,
  exportDir,
  defaultDetector = 'paddle_ocr',
  lastTimemarkPos,
  onPosChange,
  onSaved
}) {
  if (!isOpen || !asset || !photo) return null;

  const isSecondOrThird = photo.name === '50.jpg' || photo.name === '100.jpg';
  let calculatedDefaultDate = photo.meta?.dateText || (
    photo.name === '50.jpg' ? helperCalculateDate(asset.dateText, '50') :
    photo.name === '100.jpg' ? helperCalculateDate(asset.dateText, '100') :
    asset.dateText
  ) || '';
  if (calculatedDefaultDate && !/:\d{2}$/.test(calculatedDefaultDate.trim())) {
    const defaultTime = photo.name === '50.jpg' ? '08:22' : (photo.name === '100.jpg' ? '08:45' : '08:00');
    calculatedDefaultDate = `${calculatedDefaultDate.trim()} ${defaultTime}`;
  }

  const rawRelPath = `${asset.relDir}/${photo.name}`;
  const [detector, setDetector] = useState(photo.meta?.detector || defaultDetector || 'paddle_ocr');
  const [yPos, setYPos] = useState(photo.meta?.yPos ?? lastTimemarkPos?.y ?? 220);
  const [xPos, setXPos] = useState(photo.meta?.xPos ?? lastTimemarkPos?.x ?? 14);
  const [dateText, setDateText] = useState(calculatedDefaultDate);
  const [previewUrl, setPreviewUrl] = useState(photo.cleanUrl || photo.editedUrl || photo.outputUrl || null);
  const [applyToFolder, setApplyToFolder] = useState(false);
  const [saving, setSaving] = useState(false);
  const [processingAuto, setProcessingAuto] = useState(false);
  const [remerging, setRemerging] = useState(false);
  const [msg, setMsg] = useState(null);
  const [isModalDragging, setIsModalDragging] = useState(false);

  // Drag Pointer Handler untuk Kotak Timemark di Modal Preview
  const handleModalPointerDown = (e) => {
    if (e.button !== 0 && e.pointerType === 'mouse') return;
    e.stopPropagation();
    e.preventDefault();

    const boxEl = e.currentTarget;
    const containerEl = boxEl.parentElement;
    if (!containerEl) return;

    const startPointerX = e.clientX;
    const startPointerY = e.clientY;
    const startLeft = boxEl.offsetLeft;
    const startTop = boxEl.offsetTop;

    setIsModalDragging(true);

    let curNormX = xPos;
    let curNormY = yPos;

    const onPointerMove = (ev) => {
      ev.preventDefault();
      const dx = ev.clientX - startPointerX;
      const dy = ev.clientY - startPointerY;
      const maxLeft = containerEl.clientWidth - boxEl.offsetWidth;
      const maxTop = containerEl.clientHeight - boxEl.offsetHeight;
      const newLeft = Math.max(0, Math.min(maxLeft, startLeft + dx));
      const newTop = Math.max(0, Math.min(maxTop, startTop + dy));

      curNormX = Math.min(280, Math.max(0, Math.round((newLeft / containerEl.clientWidth) * 300)));
      curNormY = Math.min(280, Math.max(0, Math.round((newTop / containerEl.clientHeight) * 300)));
      setXPos(curNormX);
      setYPos(curNormY);
    };

    const onPointerUp = () => {
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
      window.removeEventListener('pointercancel', onPointerUp);
      setIsModalDragging(false);
      if (onPosChange) {
        onPosChange({ x: curNormX, y: curNormY });
      }
    };

    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
    window.addEventListener('pointercancel', onPointerUp);
  };

  // Quick Time Adjuster Helper
  const adjustMinutes = (deltaMin) => {
    const m = (dateText || '').match(/^(.*?\d{4})\s+(\d{2}):(\d{2})$/);
    if (!m) return;
    const [_, datePart, hh, mm] = m;
    let totalMin = parseInt(hh, 10) * 60 + parseInt(mm, 10) + deltaMin;
    if (totalMin < 0) totalMin += 24 * 60;
    const newHH = String(Math.floor(totalMin / 60) % 24).padStart(2, '0');
    const newMM = String(totalMin % 60).padStart(2, '0');
    setDateText(`${datePart} ${newHH}:${newMM}`);
  };

  // Proses Otomatis Menggunakan Google Vision / HSV
  const handleQuickProcess = async () => {
    setProcessingAuto(true);
    setMsg(null);
    try {
      const res = await fetch('/api/timemark/process-single', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          baseExportDir: exportDir,
          rawRelPath,
          photoName: photo.name,
          detector: detector,
          dateText: dateText.trim() || undefined
        })
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        throw new Error(data.error || 'Gagal memproses timemark otomatis');
      }

      let updatedX = xPos;
      let updatedY = yPos;
      if (data.xPos != null) { setXPos(data.xPos); updatedX = data.xPos; }
      if (data.yPos != null) { setYPos(data.yPos); updatedY = data.yPos; }
      if (data.meta && photo?.name && data.meta[photo.name]) {
        const m = data.meta[photo.name];
        if (m.xPos != null) { setXPos(m.xPos); updatedX = m.xPos; }
        if (m.yPos != null) { setYPos(m.yPos); updatedY = m.yPos; }
      }
      if (onPosChange) {
        onPosChange({ x: Number(updatedX), y: Number(updatedY) });
      }

      // Perbarui preview URL dengan timestamp baru agar cache browser bypass
      const ts = Date.now();
      if (data.outputUrl) {
        setPreviewUrl(data.outputUrl);
      } else {
        const baseSrc = photo.editedUrl || photo.outputUrl || photo.rawUrl || '';
        const cleanSrc = baseSrc.replace(/03_export_foto/i, '04_photos_edited').replace(/03_photos_export/i, '04_photos_edited');
        const cleanNoT = cleanSrc.replace(/&t=\d+/i, '').replace(/\?t=\d+&?/i, '?');
        const sep = cleanNoT.includes('?') ? (cleanNoT.endsWith('?') ? '' : '&') : '?';
        setPreviewUrl(`${cleanNoT}${sep}t=${ts}`);
      }
      setMsg({
        type: 'success',
        text: `✓ Foto berhasil diproses menggunakan ${detector === 'google_vision' ? 'Google AI Vision' : 'Metode Biasa (HSV)'}!`
      });
      if (onSaved) onSaved({ targetKey: rawRelPath, xPos: Number(updatedX), yPos: Number(updatedY), dateText: dateText.trim(), applyToFolder, outputUrl: data.outputUrl });
    } catch (err) {
      setMsg({ type: 'error', text: err.message });
    } finally {
      setProcessingAuto(false);
    }
  };

  const handleSave = async (andRemerge = false) => {
    if (!dateText.trim()) {
      alert('Teks tanggal & waktu tidak boleh kosong!');
      return;
    }
    setSaving(true);
    setMsg(null);
    try {
      const res = await fetch('/api/timemark/manual-edit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          baseExportDir: exportDir,
          rawRelPath,
          dateText: dateText.trim(),
          yPos: Number(yPos),
          xPos: Number(xPos),
          detector: detector,
          applyToFolder,
          timGroup: 'Tim_1'
        })
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        throw new Error(data.error || 'Gagal menyimpan timemark');
      }

      const ts = Date.now();
      if (data.outputUrl) {
        setPreviewUrl(data.outputUrl);
      } else {
        const baseSrc = photo.editedUrl || photo.outputUrl || photo.rawUrl || '';
        const cleanSrc = baseSrc.replace(/03_export_foto/i, '04_photos_edited').replace(/03_photos_export/i, '04_photos_edited');
        const cleanNoT = cleanSrc.replace(/&t=\d+/i, '').replace(/\?t=\d+&?/i, '?');
        const sep = cleanNoT.includes('?') ? (cleanNoT.endsWith('?') ? '' : '&') : '?';
        setPreviewUrl(`${cleanNoT}${sep}t=${ts}`);
      }

      if (andRemerge) {
        setRemerging(true);
        const targetPdfs = (asset.targetFiles && asset.targetFiles.length > 0) ? asset.targetFiles : [];
        const mergeRes = await fetch('/api/timemark/remerge-single', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            rawRelPath,
            baseExportDir: exportDir,
            pdfName: targetPdfs[0] || undefined,
            pdfNames: targetPdfs
          })
        });
        const mergeData = await mergeRes.json();
        if (!mergeRes.ok || !mergeData.ok) {
          throw new Error(mergeData.error || 'Gagal re-merge PDF target');
        }
        setMsg({
          type: 'success',
          text: `✓ Timemark disimpan dan PDF ${mergeData.pdfName} berhasil digabung ulang!`
        });
      } else {
        setMsg({
          type: 'success',
          text: '✓ Timemark berhasil diperbarui dan disimpan!'
        });
      }

      if (onSaved) onSaved({ targetKey: rawRelPath, xPos: Number(xPos), yPos: Number(yPos), dateText: dateText.trim(), applyToFolder, outputUrl: data.outputUrl });
    } catch (err) {
      setMsg({ type: 'error', text: err.message });
    } finally {
      setSaving(false);
      setRemerging(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'rgba(0, 0, 0, 0.82)',
        backdropFilter: 'blur(6px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1.25rem'
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '960px',
          maxHeight: '92vh',
          background: 'var(--bg-card, #131b2e)',
          border: '1px solid var(--border-color, #22304d)',
          borderRadius: '14px',
          boxShadow: '0 25px 60px rgba(0,0,0,0.5)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header Modal */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '1rem 1.5rem',
            borderBottom: '1px solid var(--border-color, #22304d)',
            background: 'rgba(0,0,0,0.2)'
          }}
        >
          <div>
            <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>⚙️</span> Editor Timemark Manual: {asset.detail} ({photo.name})
            </h3>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
              {rawRelPath}
            </span>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-secondary)',
              fontSize: '1.25rem',
              cursor: 'pointer',
              padding: '0.25rem 0.5rem',
              borderRadius: '6px'
            }}
          >
            ✕
          </button>
        </div>

        {/* Body Modal */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem', padding: '1.25rem 1.5rem', overflowY: 'auto' }}>
          
          {/* Side-by-Side Comparison Box */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
            
            {/* Sisi Kiri: Foto Asli */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', background: '#090d16', padding: '0.75rem', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#94a3b8' }}>📷 Foto Asli / Sebelum Edit</span>
                <span style={{ fontSize: '0.7rem', color: '#64748b' }}>Ekspor Mentah</span>
              </div>
              <div style={{ width: '100%', height: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', borderRadius: '6px', background: '#000000' }}>
                <img
                  src={photo.rawUrl}
                  alt="Foto Asli"
                  style={{ maxWidth: '100%', maxHeight: '300px', width: 'auto', height: 'auto', objectFit: 'contain', display: 'block' }}
                />
              </div>
            </div>

            {/* Sisi Kanan: Foto Hasil Timemark */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', background: '#090d16', padding: '0.75rem', borderRadius: '10px', border: previewUrl ? '1px solid #10b981' : '1px dashed #f59e0b' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 800, color: previewUrl ? '#34d399' : '#f59e0b', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                  <span>{previewUrl ? '✨' : '⚠️'}</span> {previewUrl ? 'Foto Hasil Timemark (Aktif)' : 'Belum Ada Hasil Edit (04)'}
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <span style={{ fontSize: '0.68rem', background: detector === 'google_vision' ? 'rgba(168, 85, 247, 0.2)' : 'rgba(2, 132, 199, 0.2)', color: detector === 'google_vision' ? '#c084fc' : '#38bdf8', padding: '1px 6px', borderRadius: '4px', fontWeight: 700, border: `1px solid ${detector === 'google_vision' ? '#a855f7' : '#0284c7'}` }}>
                    {detector === 'google_vision' ? '✨ Vision AI' : '🎨 HSV'}
                  </span>
                  <span style={{ fontSize: '0.7rem', background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', padding: '1px 6px', borderRadius: '4px', fontWeight: 700 }}>
                    X:{xPos}px · Y:{yPos}px
                  </span>
                </div>
              </div>
              <div style={{ width: '100%', height: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', borderRadius: '6px', background: '#000000', position: 'relative' }}>
                {previewUrl || photo.rawUrl ? (
                  <div style={{ position: 'relative', display: 'inline-block', maxWidth: '100%', maxHeight: '100%', lineHeight: 0, textAlign: 'center' }}>
                    <img
                      src={(photo.hasClean && photo.cleanUrl) ? photo.cleanUrl : (previewUrl || photo.rawUrl)}
                      alt="Foto Preview Timemark"
                      draggable={false}
                      onError={() => {
                        // Jika URL hasil edit gagal me-load, fallback agar tidak muncul broken image icon
                        if (previewUrl && previewUrl !== photo.rawUrl) {
                          setPreviewUrl(null);
                        }
                      }}
                      style={{ maxWidth: '100%', maxHeight: '300px', width: 'auto', height: 'auto', objectFit: 'contain', userSelect: 'none', pointerEvents: 'none', display: 'block' }}
                    />

                    {/* Draggable Timemark Box di Modal Preview */}
                    <div
                      className="modal-timemark-box"
                      draggable={false}
                      onDragStart={(e) => { e.preventDefault(); e.stopPropagation(); }}
                      onPointerDown={handleModalPointerDown}
                      style={{
                        position: 'absolute',
                        top: `${(yPos / 300) * 100}%`,
                        left: `${(xPos / 300) * 100}%`,
                        minWidth: '135px',
                        maxWidth: '90%',
                        width: 'fit-content',
                        height: 'auto',
                        minHeight: '22px',
                        border: isModalDragging ? '2px solid #f0883e' : '2px solid #38bdf8',
                        background: isModalDragging ? 'rgba(240, 136, 62, 0.95)' : 'rgba(15, 23, 42, 0.95)',
                        boxShadow: isModalDragging ? '0 0 16px rgba(240, 136, 62, 0.95)' : '0 0 12px rgba(56, 189, 248, 0.85)',
                        borderRadius: '4px',
                        cursor: isModalDragging ? 'grabbing' : 'grab',
                        zIndex: 20,
                        display: 'flex',
                        alignItems: 'center',
                        padding: '3px 8px',
                        userSelect: 'none',
                        touchAction: 'none',
                        boxSizing: 'border-box',
                        lineHeight: 1.2
                      }}
                      title="✥ Klik & geser kotak ini langsung di foto untuk memindahkan posisi timemark (X & Y)"
                    >
                      {/* Floating Coordinate Tag */}
                      <div
                        style={{
                          position: 'absolute',
                          top: '-18px',
                          left: '0',
                          background: isModalDragging ? '#ea580c' : '#0284c7',
                          color: '#ffffff',
                          fontSize: '8px',
                          fontWeight: 800,
                          padding: '1px 5px',
                          borderRadius: '3px',
                          whiteSpace: 'nowrap',
                          boxShadow: '0 2px 4px rgba(0,0,0,0.5)',
                          pointerEvents: 'none',
                          lineHeight: '1.2'
                        }}
                      >
                        ✥ X:{xPos} · Y:{yPos}
                      </div>

                      <span
                        style={{
                          fontSize: '9.5px',
                          fontWeight: 800,
                          color: '#ffffff',
                          textShadow: '0 1px 3px rgba(0,0,0,0.9)',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          pointerEvents: 'none',
                          lineHeight: '1.2',
                          display: 'inline-block'
                        }}
                      >
                        {dateText || 'Pilih Tanggal'}
                      </span>
                    </div>

                    </div>
                  ) : (
                  <div style={{ textAlign: 'center', color: '#f59e0b', fontSize: '0.75rem', padding: '1rem', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
                    <div style={{ fontSize: '1.75rem' }}>⚠️</div>
                    <div>Foto hasil editan belum tersedia.</div>
                    <button
                      type="button"
                      onClick={handleQuickProcess}
                      disabled={processingAuto}
                      style={{
                        padding: '0.45rem 0.85rem',
                        background: detector === 'google_vision' ? 'linear-gradient(135deg, #7e22ce 0%, #9333ea 100%)' : 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
                        color: '#ffffff',
                        border: 'none',
                        borderRadius: '6px',
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        cursor: processingAuto ? 'not-allowed' : 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.4rem',
                        boxShadow: '0 2px 8px rgba(0,0,0,0.4)'
                      }}
                    >
                      <span>{processingAuto ? '⏳' : detector === 'google_vision' ? '✨' : '⚡'}</span>
                      <span>{processingAuto ? 'Memproses...' : `Jalankan Timemark Sekarang (${detector === 'google_vision' ? 'Google AI Vision' : 'HSV'})`}</span>
                    </button>
                  </div>
                )}

                {processingAuto && (
                  <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.75)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#4ade80', zIndex: 30, gap: '0.4rem' }}>
                    <span style={{ fontSize: '1.75rem', animation: 'spin 1s linear infinite' }}>⏳</span>
                    <strong style={{ fontSize: '0.8rem' }}>Memproses Timemark ({detector === 'paddle_ocr' ? 'LaMa AI' : (detector === 'google_vision' ? 'Vision AI' : 'HSV')})...</strong>
                  </div>
                )}
              </div>
            </div>

          </div>

          {/* Controls: Detektor, Tanggal, Slider Y-Offset & Options */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', background: 'var(--bg-secondary)', padding: '1rem', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
            
            {/* Pilihan Metode Detektor di Modal */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.6rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem' }}>
              <label style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                🔍 Metode Detektor Timemark:
              </label>
              <div style={{ display: 'flex', gap: '0.4rem' }}>
                <button
                  type="button"
                  onClick={() => setDetector('paddle_ocr')}
                  style={{
                    padding: '0.35rem 0.75rem',
                    borderRadius: '6px',
                    border: detector === 'paddle_ocr' ? '1px solid #10b981' : '1px solid var(--border-color)',
                    background: detector === 'paddle_ocr' ? 'rgba(16, 185, 129, 0.2)' : 'var(--bg-card)',
                    color: detector === 'paddle_ocr' ? '#34d399' : 'var(--text-secondary)',
                    fontWeight: detector === 'paddle_ocr' ? 800 : 500,
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.3rem'
                  }}
                >
                  LaMa AI (Hapus Teks)
                </button>
                <button
                  type="button"
                  onClick={() => setDetector('google_vision')}
                  style={{
                    padding: '0.35rem 0.75rem',
                    borderRadius: '6px',
                    border: detector === 'google_vision' ? '1px solid #a855f7' : '1px solid var(--border-color)',
                    background: detector === 'google_vision' ? 'rgba(168, 85, 247, 0.2)' : 'var(--bg-card)',
                    color: detector === 'google_vision' ? '#c084fc' : 'var(--text-secondary)',
                    fontWeight: detector === 'google_vision' ? 800 : 500,
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.3rem'
                  }}
                >
                  <span>✨</span> Google Vision AI
                </button>
                <button
                  type="button"
                  onClick={() => setDetector('guide')}
                  style={{
                    padding: '0.35rem 0.75rem',
                    borderRadius: '6px',
                    border: detector === 'guide' ? '1px solid #0284c7' : '1px solid var(--border-color)',
                    background: detector === 'guide' ? 'rgba(2, 132, 199, 0.2)' : 'var(--bg-card)',
                    color: detector === 'guide' ? '#38bdf8' : 'var(--text-secondary)',
                    fontWeight: detector === 'guide' ? 800 : 500,
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.3rem'
                  }}
                >
                  <span>🎨</span> Metode Biasa (HSV)
                </button>
              </div>
            </div>
            
            {/* Input Tanggal & Jam */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <label style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                📅 Teks Tanggal & Jam Watermark:
              </label>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <input
                  type="text"
                  value={dateText}
                  onChange={e => setDateText(e.target.value)}
                  placeholder="Contoh: Sabtu, 08 Februari 2025 08:30"
                  style={{
                    flex: 1,
                    minWidth: '240px',
                    padding: '0.55rem 0.85rem',
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '6px',
                    color: 'var(--text-primary)',
                    fontSize: '0.85rem',
                    fontWeight: 600
                  }}
                />
                <button
                  type="button"
                  onClick={() => adjustMinutes(-15)}
                  style={{ padding: '0.4rem 0.65rem', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600 }}
                  title="Kurangi 15 Menit"
                >
                  -15m
                </button>
                <button
                  type="button"
                  onClick={() => adjustMinutes(15)}
                  style={{ padding: '0.4rem 0.65rem', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600 }}
                  title="Tambah 15 Menit"
                >
                  +15m
                </button>
                <button
                  type="button"
                  onClick={() => adjustMinutes(30)}
                  style={{ padding: '0.4rem 0.65rem', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600 }}
                  title="Tambah 30 Menit"
                >
                  +30m
                </button>
              </div>
            </div>

            {/* Posisi Koordinat & Panduan Geser Timemark */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-card)', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1px solid var(--border-color)', flexWrap: 'wrap', gap: '0.6rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <span>✥</span> Posisi Watermark:
                </span>
                <span style={{ fontSize: '0.75rem', fontWeight: 800, color: '#38bdf8', background: 'rgba(56, 189, 248, 0.15)', padding: '2px 8px', borderRadius: '4px', border: '1px solid rgba(56, 189, 248, 0.3)' }}>
                  X: {xPos} px
                </span>
                <span style={{ fontSize: '0.75rem', fontWeight: 800, color: '#34d399', background: 'rgba(52, 211, 153, 0.15)', padding: '2px 8px', borderRadius: '4px', border: '1px solid rgba(52, 211, 153, 0.3)' }}>
                  Y: {yPos} px
                </span>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                  (Geser langsung kotak timemark pada foto preview di atas)
                </span>
              </div>
              <div style={{ display: 'flex', gap: '0.4rem' }}>
                <button
                  type="button"
                  onClick={() => { setXPos(14); setYPos(220); }}
                  style={{ padding: '0.3rem 0.65rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '5px', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '0.72rem', fontWeight: 600 }}
                  title="Kembalikan posisi timemark ke default (X: 14, Y: 220)"
                >
                  ↺ Reset Posisi Standar
                </button>
              </div>
            </div>

            {/* Checkbox Apply to Siblings */}
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.8rem', color: 'var(--text-primary)', cursor: 'pointer', userSelect: 'none' }}>
              <input
                type="checkbox"
                checked={applyToFolder}
                onChange={e => setApplyToFolder(e.target.checked)}
                style={{ width: '16px', height: '16px', accentColor: '#10b981', cursor: 'pointer' }}
              />
              <span>
                <strong>Terapkan ke seluruh foto aset ini (0%, 50%, 100%)</strong>
                <span style={{ display: 'block', fontSize: '0.72rem', color: applyToFolder ? 'var(--text-secondary)' : '#38bdf8' }}>
                  {applyToFolder
                    ? 'Otomatis menyinkronkan posisi dan menghitung jeda waktu: 0% waktu awal, 50% (+23m), 100% (+45m).'
                    : `HANYA terapkan posisi dan jam ini khusus untuk foto ${photo.name} saja (posisi foto lain tidak akan terpengaruh).`}
                </span>
              </span>
            </label>

          </div>

          {msg && (
            <div style={{
              padding: '0.65rem 0.95rem',
              borderRadius: '6px',
              fontSize: '0.8rem',
              background: msg.type === 'success' ? '#14532d' : '#7f1d1d',
              color: msg.type === 'success' ? '#86efac' : '#fca5a5',
              border: `1px solid ${msg.type === 'success' ? '#22c55e' : '#ef4444'}`
            }}>
              {msg.text}
            </div>
          )}

        </div>

        {/* Footer Modal Buttons */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '1rem 1.5rem',
            borderTop: '1px solid var(--border-color, #22304d)',
            background: 'rgba(0,0,0,0.2)',
            flexWrap: 'wrap',
            gap: '0.75rem'
          }}
        >
          <button
            type="button"
            onClick={onClose}
            disabled={saving || remerging}
            style={{
              padding: '0.55rem 1rem',
              background: 'var(--bg-secondary)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border-color)',
              borderRadius: '8px',
              cursor: 'pointer',
              fontSize: '0.8rem',
              fontWeight: 600
            }}
          >
            Tutup
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={handleQuickProcess}
              disabled={processingAuto || saving || remerging}
              style={{
                padding: '0.55rem 1.15rem',
                background: detector === 'google_vision' ? 'linear-gradient(135deg, #7e22ce 0%, #9333ea 100%)' : 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
                color: '#ffffff',
                border: 'none',
                borderRadius: '8px',
                cursor: processingAuto ? 'not-allowed' : 'pointer',
                fontSize: '0.8rem',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                boxShadow: detector === 'google_vision' ? '0 2px 10px rgba(147, 51, 234, 0.4)' : '0 2px 10px rgba(2, 132, 199, 0.4)'
              }}
              title={`Jalankan proses deteksi otomatis dengan ${detector === 'google_vision' ? 'Google AI Vision' : 'Metode Biasa (HSV)'}`}
            >
              <span>{processingAuto ? '⏳' : detector === 'google_vision' ? '✨' : '⚡'}</span>
              <span>{processingAuto ? 'Memproses...' : `⚡ Proses ${detector === 'google_vision' ? 'AI Vision' : 'HSV'}`}</span>
            </button>

            <button
              type="button"
              onClick={() => handleSave(false)}
              disabled={saving || remerging || processingAuto}
              style={{
                padding: '0.55rem 1.25rem',
                background: '#10b981',
                color: '#ffffff',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer',
                fontSize: '0.8rem',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                boxShadow: '0 2px 10px rgba(16, 185, 129, 0.4)'
              }}
            >
              {saving && !remerging ? '⏳ Menyimpan...' : '💾 Simpan Timemark'}
            </button>

            <button
              type="button"
              onClick={() => handleSave(true)}
              disabled={saving || remerging}
              style={{
                padding: '0.55rem 1.25rem',
                background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
                color: '#ffffff',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer',
                fontSize: '0.8rem',
                fontWeight: 800,
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                boxShadow: '0 2px 10px rgba(2, 132, 199, 0.4)'
              }}
              title="Simpan perubahan watermark dan langsung perbarui file PDF target terkait"
            >
              {remerging ? '⚡ Sedang Merge PDF...' : '⚡ Simpan & Merge PDF'}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}

// =============================================================================
// Komponen Utama GalleryPanel
// =============================================================================
export default function GalleryPanel({ exportDir, targetDir = '', onPickFolder, schedulePath = '', onPickSchedule, onScheduleChange, syncVersion = 0 }) {
  const [assets, setAssets] = useState([]);
  const [targetFiles, setTargetFiles] = useState([]);
  const [sourceFiles, setSourceFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState(null);

  // Mode States (Sama Persis dengan Web App)
  const [pipelineMode, setPipelineMode] = useState('standard'); // 'standard' | 'time' | 'coord'
  const [viewMode, setViewMode] = useState('edited'); // Default: 'edited' (04) | 'dual' | 'raw'
  const [cardSize, setCardSize] = useState('large'); // 'normal' | 'large'
  const [photoViewOverrides, setPhotoViewOverrides] = useState({}); // { [targetKey]: 'edited' | 'raw' }
  const [sourceTypeFilter, setSourceTypeFilter] = useState('all'); // 'timemark' | 'export' | 'all'
  const [activeDetector, setActiveDetector] = useState('paddle_ocr'); // 'google_vision' | 'guide'

  // Filter States
  const [selectedFile, setSelectedFile] = useState('');
  const [selectedStation, setSelectedStation] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedStatus, setSelectedStatus] = useState(''); // '' | 'complete' | 'incomplete'
  const [searchQuery, setSearchQuery] = useState('');

  // Status ciutkan/tampilkan bar filter pencarian (Default: tersembunyi agar galeri luas maksimal)
  const [showFilters, setShowFilters] = useState(() => {
    try {
      const s = localStorage.getItem('sintelis_gallery_show_filters');
      return s !== null ? JSON.parse(s) : false;
    } catch (_) {
      return false;
    }
  });

  const toggleFilters = () => {
    setShowFilters(prev => {
      const next = !prev;
      try { localStorage.setItem('sintelis_gallery_show_filters', JSON.stringify(next)); } catch (_) {}
      return next;
    });
  };

  const activeFilterCount = useMemo(() => {
    return [
      Boolean(selectedFile),
      Boolean(selectedStation),
      Boolean(selectedCategory),
      Boolean(selectedStatus),
      Boolean(searchQuery),
      sourceTypeFilter !== 'all'
    ].filter(Boolean).length;
  }, [selectedFile, selectedStation, selectedCategory, selectedStatus, searchQuery, sourceTypeFilter]);

  // Drag & Drop State
  const [dragOverRel, setDragOverRel] = useState(null);
  const [actionLoadingKeys, setActionLoadingKeys] = useState({}); // { [targetKey]: true }
  const [photoCardVersions, setPhotoCardVersions] = useState({}); // { [targetKey]: timestamp }

  // Fast targeted refresh: Memperbarui 1 foto lokal tanpa reload seluruh network drive
  const refreshSinglePhotoCard = (targetKey, newMeta = null) => {
    if (!targetKey) return;
    const now = Date.now();
    // Normalisasi slash agar tahan terhadap Windows (\) dan Unix (/)
    const normTarget = targetKey.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
    setPhotoCardVersions(prev => ({ ...prev, [targetKey]: now, [normTarget]: now }));
    setAssets(prevAssets => {
      const parts = normTarget.split('/');
      const pName = parts[parts.length - 1];
      const relDir = parts.slice(0, -1).join('/');
      return prevAssets.map(a => {
        const normAssetRel = (a.relDir || a.relPath || '').replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
        if (normAssetRel !== relDir) return a;
        const nextPhotos = (a.photos || []).map(p => {
          if (p.name !== pName && !newMeta?.applyToFolder) return p;
          const mergedMeta = {
            ...(p.meta || {}),
            ...(newMeta || {}),
            xPos: newMeta?.xPos !== undefined && newMeta?.xPos !== null ? Number(newMeta.xPos) : p.meta?.xPos,
            yPos: newMeta?.yPos !== undefined && newMeta?.yPos !== null ? Number(newMeta.yPos) : p.meta?.yPos,
            manualEdit: (newMeta && newMeta.manualEdit !== undefined) ? Boolean(newMeta.manualEdit) : Boolean(p.meta?.manualEdit),
            updatedAt: new Date().toISOString()
          };
          const bustUrl = (u) => {
            if (!u) return u;
            const clean = u.replace(/([?&])(_v|t)=\d+/g, '');
            const sep = clean.includes('?') ? '&' : '?';
            return `${clean}${sep}_v=${now}`;
          };
          const resolvedEditedUrl = (p.name === pName && newMeta?.outputUrl) ? newMeta.outputUrl : (
            p.editedUrl || p.outputUrl || (
              p.rawUrl ? p.rawUrl.replace(/03_export_foto/i, '04_photos_edited').replace(/03_photos_export/i, '04_photos_edited') : null
            )
          );
          const freshEditedUrl = bustUrl(resolvedEditedUrl);
          const freshCleanUrl = bustUrl(p.cleanUrl || (resolvedEditedUrl ? resolvedEditedUrl.replace(/\.jpg/i, '.clean.jpg') : null));
          return {
            ...p,
            hasEdited: true,
            hasClean: true,
            editedUrl: freshEditedUrl,
            outputUrl: freshEditedUrl,
            cleanUrl: freshCleanUrl,
            url: freshCleanUrl || freshEditedUrl || p.url,
            meta: mergedMeta
          };
        });
        return {
          ...a,
          hasEdited: true,
          photos: nextPhotos
        };
      });
    });
  };
  const [draggedPhotoInfo, setDraggedPhotoInfo] = useState(null); // { rel, photoName, assetRel }

  // Peta Koordinat Lokal Per-Foto Terkunci (Mencegah Foto 0 Terpengaruh Foto 50/100)
  const [photoCoordsMap, setPhotoCoordsMap] = useState({});

  const updatePhotoLocalPos = (tKey, coords) => {
    if (!tKey || !coords) return;
    const norm = tKey.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
    setPhotoCoordsMap(prev => ({
      ...prev,
      [tKey]: { ...coords, ts: Date.now() },
      [norm]: { ...coords, ts: Date.now() }
    }));
  };

  // Persistent Last Timemark Box Position (X, Y)
  const [lastTimemarkPos, setLastTimemarkPos] = useState(() => {
    try {
      const raw = localStorage.getItem('sintelis_last_timemark_pos');
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed.x === 'number' && typeof parsed.y === 'number' && parsed.x >= 0 && parsed.x <= 295 && parsed.y >= 0 && parsed.y <= 295) {
          return parsed;
        }
      }
      return { x: 14, y: 220 };
    } catch (_) {
      return { x: 14, y: 220 };
    }
  });

  const updateLastTimemarkPos = (newPos) => {
    if (!newPos || typeof newPos.x !== 'number' || typeof newPos.y !== 'number') return;
    setLastTimemarkPos(newPos);
    try {
      if (newPos.x >= 0 && newPos.x <= 295 && newPos.y >= 0 && newPos.y <= 295) {
        localStorage.setItem('sintelis_last_timemark_pos', JSON.stringify(newPos));
      }
    } catch (_) {}
  };

  // Zoom Preview Modal State
  const [zoomPhoto, setZoomPhoto] = useState(null); // { url, title }

  // Timemark Editor Modal State
  const [editingModal, setEditingModal] = useState(null); // { asset, photo }
  const [editingRowDateAsset, setEditingRowDateAsset] = useState(null); // { asset }

  const handleRowDateSaved = ({ assetRel, baseDate, dates }) => {
    const normRel = (assetRel || '').replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
    const now = Date.now();

    setAssets(prevAssets => {
      return prevAssets.map(a => {
        const aNorm = (a.relDir || a.relPath || '').replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
        if (aNorm !== normRel) return a;

        const nextPhotos = (a.photos || []).map(p => {
          const pDate = (dates && dates[p.name]) || (
            p.name === '50.jpg' ? helperCalculateDate(baseDate, '50') :
            p.name === '100.jpg' ? helperCalculateDate(baseDate, '100') :
            baseDate
          );
          return {
            ...p,
            hasEdited: true,
            meta: {
              ...(p.meta || {}),
              dateText: pDate,
              manualEdit: true,
              updatedAt: new Date().toISOString()
            }
          };
        });

        return {
          ...a,
          hasEdited: true,
          dateText: baseDate,
          photos: nextPhotos
        };
      });
    });

    setPhotoCardVersions(prev => ({
      ...prev,
      [`${normRel}/0.jpg`]: now,
      [`${normRel}/50.jpg`]: now,
      [`${normRel}/100.jpg`]: now
    }));

    setFeedback({
      type: 'success',
      text: `✓ Tanggal 3 foto berhasil diperbarui menjadi: ${baseDate}`
    });
  };

  // Single Merge State per Asset Row
  const [mergingRel, setMergingRel] = useState(null);
  const [bakingRel, setBakingRel] = useState(null);

  const handleBakeStamp = async (asset) => {
    if (!asset || !asset.relDir) return;
    setBakingRel(asset.relDir);
    try {
      const res = await fetch('/api/timemark/bake-stamp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          baseExportDir: exportDir,
          rawRelPath: asset.relDir
        })
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        fetchPhotos();
        alert(data.message || '✓ Berhasil menempelkan tanggal ke foto fisik JPG!');
      } else {
        alert(data.error || 'Gagal menempelkan tanggal.');
      }
    } catch (err) {
      alert('Error bake stamp: ' + err.message);
    } finally {
      setBakingRel(null);
    }
  };

  const [manualSchedulePath, setManualSchedulePath] = useState('');
  const [loadedScheduleInfo, setLoadedScheduleInfo] = useState('');

  // Reset pilihan jadwal manual saat ganti folder atau saat pipeline selesai Step 2/3
  useEffect(() => {
    setManualSchedulePath('');
  }, [exportDir, targetDir, syncVersion]);

  const handlePickScheduleFile = async () => {
    try {
      if (onPickSchedule) {
        onPickSchedule();
        return;
      }
      const res = await fetch('/api/select-file', { method: 'POST' });
      const data = await res.json();
      if (data && data.path) {
        setManualSchedulePath(data.path);
        if (onScheduleChange) onScheduleChange(data.path);
      }
    } catch (err) {
      alert('Gagal memilih berkas jadwal: ' + err.message);
    }
  };

  // Fetch photos and metadata from backend
  const fetchPhotos = async (isManualRefresh = false) => {
    if (!exportDir) return;
    setLoading(true);
    setFeedback(null);
    try {
      const curSched = (manualSchedulePath || schedulePath || '').trim();
      const targetQuery = targetDir ? `&targetDir=${encodeURIComponent(targetDir)}` : '';
      const schedQuery = curSched ? `&schedule=${encodeURIComponent(curSched)}` : '';
      const refreshQuery = isManualRefresh ? '&refresh=1' : '';
      const res = await fetch(`/api/timemark/photos?folder=${encodeURIComponent(exportDir)}${targetQuery}${schedQuery}${refreshQuery}`);
      if (res.ok) {
        const data = await res.json();
        const loadedAssets = data.assets || [];
        setAssets(loadedAssets);
        setTargetFiles(data.targetFiles || []);
        setSourceFiles(data.sourceFiles || []);
        setLoadedScheduleInfo(data.loadedSchedule || '');
      } else {
        setFeedback({ type: 'error', text: 'Gagal memuat galeri foto dari folder ekspor.' });
      }
    } catch (err) {
      setFeedback({ type: 'error', text: 'Koneksi gagal: ' + err.message });
    } finally {
      setLoading(false);
    }
  };

  const [isFastUpdating, setIsFastUpdating] = useState(false);

  const handleTriggerFastUpdate = async () => {
    const activeSched = (manualSchedulePath || schedulePath || loadedScheduleInfo || '').trim();
    if (!activeSched) {
      alert('Silakan pilih berkas schedule.json terlebih dahulu dengan menekan tombol "Pilih Jadwal" di sebelah kiri!');
      handlePickScheduleFile();
      return;
    }
    if (!exportDir) {
      alert('Folder foto belum dipilih!');
      return;
    }

    const schedFileName = activeSched.split(/[\\/]/).filter(Boolean).pop();
    const confirmMsg = `Jalankan Fast Update Timemark?\n\n• Jadwal Acuan: ${schedFileName}\n• Folder Foto: ${exportDir}\n\nSistem akan langsung menempelkan teks tanggal & jam dinas dari jadwal ke seluruh foto menggunakan koordinat (xPos, yPos) yang tersimpan di meta.json tanpa deteksi AI lagi (instan).\n\nLanjutkan?`;
    if (!confirm(confirmMsg)) return;

    setIsFastUpdating(true);
    setFeedback({ type: 'info', text: '⚡ Menjalankan Fast Update Timemark (membaca meta.json)... Mohon tunggu.' });
    try {
      const res = await fetch('/api/timemark/fast-update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          folder: exportDir,
          schedulePath: activeSched,
          includeTime: true,
          force: true,
          detector: activeDetector
        })
      });
      if (!res.ok) {
        const text = await res.text();
        let errMsg = `Error ${res.status}`;
        try {
          const j = JSON.parse(text);
          errMsg = j.error || errMsg;
        } catch (_) {
          if (res.status === 404) {
            errMsg = 'Endpoint Fast Update belum aktif pada proses backend. Mohon tutup aplikasi Sintelis Utility dan jalankan kembali via run_dev.bat.';
          }
        }
        throw new Error(errMsg);
      }
      const data = await res.json();
      if (data.ok) {
        setFeedback({ type: 'success', text: `✅ Fast Update Timemark Selesai! ${data.message || ''}` });
        alert(`⚡ Fast Update Timemark Selesai!\n\n${data.message || ''}`);
        await fetchPhotos(true);
      } else {
        setFeedback({ type: 'error', text: `❌ Gagal Fast Update: ${data.error || 'Terjadi kesalahan'}` });
        alert(`Gagal Fast Update: ${data.error || 'Terjadi kesalahan'}`);
      }
    } catch (err) {
      setFeedback({ type: 'error', text: `❌ Error: ${err.message}` });
      alert(`Gagal menghubungi server: ${err.message}`);
    } finally {
      setIsFastUpdating(false);
    }
  };

  useEffect(() => {
    fetchPhotos(syncVersion > 0);
  }, [exportDir, targetDir, manualSchedulePath, schedulePath, syncVersion]);

  // Counts
  const editedCount = useMemo(() => assets.filter(a => a.hasEdited).length, [assets]);
  const exportCount = useMemo(() => assets.length, [assets]);

  // Unique lists for dropdowns
  const uniqueStations = useMemo(() => {
    const set = new Set();
    assets.forEach(a => { if (a.station) set.add(a.station); });
    targetFiles.forEach(t => { if (t.btp) set.add(t.btp); });
    return Array.from(set).sort();
  }, [assets, targetFiles]);

  const uniqueCategories = useMemo(() => {
    const canonMap = new Map();

    // 1. Inisialisasi Kategori Master Sintelis Resor 1.21 BOO
    MASTER_CATEGORIES.forEach(cat => {
      const norm = normalizeCategory(cat);
      canonMap.set(norm, {
        key: cat,
        label: CATEGORY_LABEL_MAP[cat] || cat,
        count: 0
      });
    });

    // 2. Tambahkan kategori dari targetFiles / schedule jika ada
    targetFiles.forEach(t => {
      if (t.category) {
        const norm = normalizeCategory(t.category);
        if (!canonMap.has(norm)) {
          canonMap.set(norm, {
            key: t.category,
            label: CATEGORY_LABEL_MAP[t.category] || t.category,
            count: 0
          });
        }
      }
    });

    // 3. Tambahkan kategori riil dari folder assets
    assets.forEach(a => {
      const rawCat = a.category || a.asset_type;
      if (rawCat) {
        const norm = normalizeCategory(rawCat);
        if (!canonMap.has(norm)) {
          canonMap.set(norm, {
            key: rawCat,
            label: CATEGORY_LABEL_MAP[rawCat] || rawCat,
            count: 0
          });
        }
      }
    });

    // 4. Hitung jumlah aset riil untuk tiap kategori
    assets.forEach(a => {
      const norm = normalizeCategory(a.category || a.asset_type);
      if (canonMap.has(norm)) {
        canonMap.get(norm).count += 1;
      }
    });

    return Array.from(canonMap.values()).sort((a, b) => a.label.localeCompare(b.label));
  }, [assets, targetFiles]);

  // Combined File List
  const allFileOptions = useMemo(() => {
    const options = [];
    const seen = new Set();

    targetFiles.forEach(t => {
      if (t.file && !seen.has(t.file)) {
        seen.add(t.file);
        options.push({ value: t.file, label: `📄 ${t.file}`, category: t.category, btp: t.btp });
      }
    });

    sourceFiles.forEach(s => {
      if (s && !seen.has(s)) {
        seen.add(s);
        options.push({ value: s, label: `📥 ${s}` });
      }
    });

    return options.sort((a, b) => a.value.localeCompare(b.value));
  }, [targetFiles, sourceFiles]);

  // Filtered Assets
  const filteredAssets = useMemo(() => {
    return assets.filter(a => {
      // 0. Filter Tipe Sumber Foto (Hasil Timemark vs Ekspor Asli vs Kolase)
      if (sourceTypeFilter === 'timemark' && !a.hasEdited) return false;
      if (sourceTypeFilter === 'export' && !a.hasRaw) return false;
      if (sourceTypeFilter === 'collage' && !a.isCollage) return false;

      // 1. Filter File (Target PDF atau Source PDF)
      if (selectedFile) {
        const inTargets = (a.targetFiles || []).includes(selectedFile);
        const isSource = a.sourceFile === selectedFile;
        if (!inTargets && !isSource) return false;
      }

      // 2. Filter Stasiun / BTP
      if (selectedStation && a.station !== selectedStation) {
        return false;
      }

      // 3. Filter Kategori Aset (Normalisasi Alias agar AXC/AXLE COUNTER, SINYAL/PERAGA, dll cocok bolak-balik)
      const cat = a.category || a.asset_type || '';
      if (selectedCategory) {
        const normAssetCat = normalizeCategory(cat);
        const normSelectedCat = normalizeCategory(selectedCategory);
        if (normAssetCat !== normSelectedCat && cat !== selectedCategory) {
          return false;
        }
      }

      // 4. Filter Status Kelengkapan Foto
      const photoCount = (a.photos || []).length;
      if (selectedStatus === 'complete' && photoCount < 3) return false;
      if (selectedStatus === 'incomplete' && photoCount >= 3) return false;

      // 5. Search Query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const normCat = normalizeCategory(cat).toLowerCase();
        const labelCat = (CATEGORY_LABEL_MAP[normalizeCategory(cat)] || '').toLowerCase();
        const matchStation = a.station && a.station.toLowerCase().includes(q);
        const matchCat = (cat && cat.toLowerCase().includes(q)) || normCat.includes(q) || labelCat.includes(q);
        const matchDetail = a.detail && a.detail.toLowerCase().includes(q);
        if (!matchStation && !matchCat && !matchDetail) return false;
      }

      return true;
    });
  }, [assets, sourceTypeFilter, selectedFile, selectedStation, selectedCategory, selectedStatus, searchQuery]);

  const isFilterActive = Boolean(
    selectedFile || selectedStation || selectedCategory || selectedStatus || searchQuery ||
    sourceTypeFilter !== 'all'
  );

  const resetAllFilters = () => {
    setSelectedFile('');
    setSelectedStation('');
    setSelectedCategory('');
    setSelectedStatus('');
    setSearchQuery('');
    setSourceTypeFilter('all');
  };

  // Direct Drag & Drop Handler
  const handleDirectDrop = async (assetRel, photoName, file) => {
    if (!file.type.startsWith('image/') && !file.name.match(/\.(jpe?g|png|webp|bmp)$/i)) {
      alert('Harap masukkan berkas gambar (JPG, PNG, atau WEBP)!');
      return;
    }

    const targetKey = `${assetRel}/${photoName}`;
    setActionLoadingKeys(prev => ({ ...prev, [targetKey]: true }));
    try {
      const reader = new FileReader();
      reader.onload = async () => {
        const base64Data = reader.result.split(',')[1];
        const res = await fetch('/api/timemark/replace-photo', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            baseExportDir: exportDir,
            assetRelPath: assetRel,
            photoName,
            imageBase64: base64Data,
            xPos: lastTimemarkPos?.x,
            yPos: lastTimemarkPos?.y
          })
        });
        const data = await res.json();
        if (res.ok && data.ok) {
          setFeedback({ type: 'success', text: `✓ Foto ${photoName} untuk ${assetRel} berhasil diperbarui.` });
          refreshSinglePhotoCard(targetKey, { xPos: lastTimemarkPos?.x, yPos: lastTimemarkPos?.y, manualEdit: true });
        } else {
          alert('Gagal mengganti foto: ' + (data.error || 'Terjadi kesalahan'));
        }
        setActionLoadingKeys(prev => { const n = { ...prev }; delete n[targetKey]; return n; });
      };
      reader.readAsDataURL(file);
    } catch (err) {
      alert('Galat baca berkas: ' + err.message);
      setActionLoadingKeys(prev => { const n = { ...prev }; delete n[targetKey]; return n; });
    }
  };

  // Revert Foto Asli Handler
  const handleRevert = async (assetRel, photoName) => {
    if (!confirm(`Kembalikan foto ${photoName} untuk ${assetRel} ke versi aslinya?`)) return;
    const targetKey = `${assetRel}/${photoName}`;
    setActionLoadingKeys(prev => ({ ...prev, [targetKey]: true }));
    try {
      const res = await fetch('/api/timemark/revert-photo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          baseExportDir: exportDir,
          assetRelPath: assetRel,
          photoName
        })
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        setFeedback({ type: 'success', text: `✓ Foto ${photoName} berhasil dipulihkan ke versi asli.` });
        await fetchPhotos();
      } else {
        alert('Gagal memulihkan foto: ' + (data.error || 'Terjadi kesalahan'));
      }
    } catch (err) {
      alert('Galat: ' + err.message);
    } finally {
      setActionLoadingKeys(prev => { const n = { ...prev }; delete n[targetKey]; return n; });
    }
  };

  // Tukar Posisi Foto (Swap Photos) Handler
  const handleSwapPhotos = async (sourceRel, targetRel) => {
    if (!sourceRel || !targetRel || sourceRel === targetRel) return;
    setActionLoadingKeys(prev => ({ ...prev, [sourceRel]: true }));
    try {
      const res = await fetch('/api/timemark/swap-photo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          baseExportDir: exportDir,
          sourceRel,
          targetRel,
          detector: activeDetector
        })
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        setFeedback({
          type: 'success',
          text: `✓ ${data.message || 'Posisi foto berhasil ditukar!'}`
        });
        await fetchPhotos();
      } else {
        alert('Gagal menukar posisi foto: ' + (data.error || 'Terjadi kesalahan'));
      }
    } catch (err) {
      alert('Galat tukar foto: ' + err.message);
    } finally {
      setActionLoadingKeys(prev => { const n = { ...prev }; delete n[sourceRel]; return n; });
    }
  };

  // Potong Kolase Per Foto (Crop Single Collage) Handler
  const handleCropCollageSingle = async (targetKey, quadrant = null) => {
    if (!targetKey) return;
    setActionLoadingKeys(prev => ({ ...prev, [targetKey]: true }));
    try {
      const res = await fetch('/api/timemark/crop-collage-single', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          baseExportDir: exportDir,
          rel: targetKey,
          quadrant: quadrant || undefined,
          detector: activeDetector
        })
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        setFeedback({
          type: 'success',
          text: `✓ ${data.message || 'Kolase berhasil dipotong dan disimpan!'}`
        });
        await fetchPhotos();
      } else {
        alert('Gagal memotong kolase: ' + (data.error || 'Terjadi kesalahan'));
      }
    } catch (err) {
      alert('Galat potong kolase: ' + err.message);
    } finally {
      setActionLoadingKeys(prev => { const n = { ...prev }; delete n[targetKey]; return n; });
    }
  };

  // Proses Timemark Otomatis (Per Foto atau Per Folder Aset)
  const handleProcessTimemark = async (asset, photoName = null) => {
    const targetKey = photoName ? `${asset.relDir}/${photoName}` : asset.relDir;
    setActionLoadingKeys(prev => ({ ...prev, [targetKey]: true }));
    try {
      const res = await fetch('/api/timemark/process-single', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          baseExportDir: exportDir,
          targetDir: targetDir || undefined,
          schedulePath: (manualSchedulePath || schedulePath || loadedScheduleInfo || '').trim() || undefined,
          assetRelPath: asset.relDir,
          photoName: photoName || undefined,
          detector: activeDetector,
          dateText: asset.dateText || undefined
        })
      });
      const data = await res.json();
      if (res.ok && (data.ok || data.success)) {
        setFeedback({
          type: 'success',
          text: `✓ ${data.message}`
        });
        const metaObj = data.meta || {};
        if (photoName) {
          const tKey = `${asset.relDir}/${photoName}`;
          const normKey = tKey.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
          setPhotoCoordsMap(prev => {
            const next = { ...prev };
            delete next[tKey];
            delete next[normKey];
            return next;
          });
          const pMeta = metaObj[photoName] || { detector: activeDetector };
          refreshSinglePhotoCard(tKey, pMeta);
        } else {
          setPhotoCoordsMap(prev => {
            const next = { ...prev };
            (asset.photos || []).forEach(p => {
              const k = `${asset.relDir}/${p.name}`;
              delete next[k];
              delete next[k.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')];
            });
            return next;
          });
          const fnames = (asset.photos && asset.photos.length > 0)
            ? asset.photos.map(p => p.name)
            : ['0.jpg', '50.jpg', '100.jpg'];
          fnames.forEach(pName => {
            const pMeta = metaObj[pName] || { detector: activeDetector };
            refreshSinglePhotoCard(`${asset.relDir}/${pName}`, pMeta);
          });
        }
      } else {
        alert('Gagal memproses timemark: ' + (data.error || 'Terjadi kesalahan'));
      }
    } catch (err) {
      alert('Galat proses timemark: ' + err.message);
    } finally {
      setActionLoadingKeys(prev => {
        const next = { ...prev };
        delete next[targetKey];
        return next;
      });
    }
  };

  // Instant Merge PDF Per Row Handler
  const handleMergeRow = async (asset) => {
    setMergingRel(asset.relDir);
    try {
      const firstPhotoRel = `${asset.relDir}/0.jpg`;
      const targetPdfs = (asset.targetFiles && asset.targetFiles.length > 0) ? asset.targetFiles : [];
      const res = await fetch('/api/timemark/remerge-single', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rawRelPath: firstPhotoRel,
          baseExportDir: exportDir,
          targetDir: targetDir || undefined,
          pdfName: targetPdfs[0] || undefined,
          pdfNames: targetPdfs
        })
      });
      const data = await res.json();
      if (res.ok && (data.ok || data.success)) {
        if (data.fileUrl) {
          window.open(data.fileUrl, '_blank');
        }
        setFeedback({
          type: 'success',
          text: `✓ Berkas PDF target (${targetPdfs.length > 0 ? targetPdfs.join(', ') : data.pdfName}) berhasil digabung dengan foto Timemark!`
        });
      } else {
        alert('Gagal merge PDF: ' + (data.error || 'Terjadi kesalahan'));
      }
    } catch (err) {
      alert('Galat merge PDF: ' + err.message);
    } finally {
      setMergingRel(null);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', height: '100%', width: '100%', overflowY: 'auto', paddingRight: '0.5rem' }}>
      
      {/* 🌟 ULTRA-COMPACT STICKY CONTROL BAR 🌟 */}
      <div
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 35,
          background: 'rgba(9, 13, 22, 0.96)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.45rem',
          padding: '0.5rem 0.75rem',
          borderRadius: '10px',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          boxShadow: '0 8px 24px rgba(0, 0, 0, 0.65)'
        }}
      >
        {/* Baris 1: Kontrol Utama (Folder + Switchers + Filter Toggle) */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.6rem', flexWrap: 'wrap' }}>
          
          {/* Kiri: Folder + Ganti + Refresh + Counter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', flexWrap: 'wrap' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                background: 'var(--bg-secondary)',
                padding: '0.25rem 0.6rem',
                borderRadius: '6px',
                border: '1px solid var(--border-color)',
                maxWidth: '300px'
              }}
              title={`Folder Foto: ${exportDir || 'Belum dipilih'}`}
            >
              <span style={{ fontSize: '0.8rem' }}>📁</span>
              <span style={{ fontSize: '0.74rem', color: 'var(--text-primary)', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {exportDir ? exportDir.split(/[\\/]/).filter(Boolean).slice(-2).join('/') : 'Belum dipilih'}
              </span>
            </div>

            {onPickFolder && (
              <button
                onClick={onPickFolder}
                style={{ padding: '0.28rem 0.65rem', background: 'var(--accent)', color: '#ffffff', border: 'none', borderRadius: '5px', cursor: 'pointer', fontSize: '0.72rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.25rem' }}
                title="Ganti folder foto"
              >
                📂 Ganti
              </button>
            )}

            <button
              onClick={() => fetchPhotos(true)}
              disabled={loading}
              style={{ padding: '0.28rem 0.6rem', background: 'var(--bg-secondary)', color: 'var(--text-secondary)', border: '1px solid var(--border-color)', borderRadius: '5px', cursor: 'pointer', fontSize: '0.72rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.25rem' }}
              title="Refresh daftar foto"
            >
              🔄 Refresh
            </button>

            {/* Indikator & Selector Jadwal (schedule.json dari DIR PDF Target) */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.3rem',
                  background: (loadedScheduleInfo || manualSchedulePath || schedulePath) ? 'rgba(99, 102, 241, 0.12)' : 'rgba(245, 158, 11, 0.1)',
                  border: (loadedScheduleInfo || manualSchedulePath || schedulePath) ? '1px solid #6366f1' : '1px solid rgba(245, 158, 11, 0.35)',
                  borderRadius: '5px',
                  padding: '0.22rem 0.5rem',
                  maxWidth: '240px'
                }}
                title={
                  (loadedScheduleInfo || manualSchedulePath || schedulePath)
                    ? `Jadwal aktif: ${loadedScheduleInfo || manualSchedulePath || schedulePath}`
                    : `Menunggu Step 2 & 3 — belum ada schedule.json di DIR PDF Target${targetDir ? ` (${targetDir})` : ''}`
                }
              >
                <span style={{ fontSize: '0.8rem' }}>{(loadedScheduleInfo || manualSchedulePath || schedulePath) ? '📅' : '⏳'}</span>
                <span style={{
                  fontSize: '0.72rem',
                  color: (loadedScheduleInfo || manualSchedulePath || schedulePath) ? '#a5b4fc' : '#fbbf24',
                  fontWeight: 600,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis'
                }}>
                  {(loadedScheduleInfo || manualSchedulePath || schedulePath)
                    ? (loadedScheduleInfo || manualSchedulePath || schedulePath).split(/[\\/]/).filter(Boolean).slice(-2).join('/')
                    : 'Menunggu Step 2 & 3'}
                </span>
              </div>

              <button
                type="button"
                onClick={handlePickScheduleFile}
                style={{
                  padding: '0.25rem 0.55rem',
                  background: 'rgba(99, 102, 241, 0.18)',
                  color: '#c7d2fe',
                  border: '1px solid #6366f1',
                  borderRadius: '5px',
                  cursor: 'pointer',
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.25rem'
                }}
                title="Pilih berkas schedule.json manual untuk folder ini"
              >
                🗓️ {(loadedScheduleInfo || manualSchedulePath || schedulePath) ? 'Ganti Jadwal' : 'Pilih Jadwal'}
              </button>
            </div>

            {/* Tombol Fast Update Timemark */}
            <button
              type="button"
              disabled={isFastUpdating || loading}
              onClick={handleTriggerFastUpdate}
              style={{
                padding: '0.25rem 0.65rem',
                background: isFastUpdating ? '#4b5563' : '#8957e5',
                color: '#ffffff',
                border: 'none',
                borderRadius: '5px',
                cursor: (isFastUpdating || loading) ? 'not-allowed' : 'pointer',
                fontSize: '0.72rem',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                gap: '0.3rem',
                boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
                transition: 'all 0.2s',
                opacity: (isFastUpdating || loading) ? 0.7 : 1
              }}
              title="Stempel ulang seluruh foto menggunakan koordinat meta.json dan acuan schedule.json (Proses Instan)"
            >
              <span>⚡</span> {isFastUpdating ? 'Memproses Fast Update...' : 'Fast Update Timemark'}
            </button>

            {/* Counter Badge */}
            <span style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', background: 'rgba(15, 23, 42, 0.8)', padding: '0.28rem 0.6rem', borderRadius: '5px', border: '1px solid var(--border-color)', fontWeight: 600 }}>
              <strong style={{ color: '#10b981' }}>{filteredAssets.length}</strong> / <strong>{assets.length}</strong> aset ({editedCount} diedit)
            </span>
          </div>

          {/* Kanan: Switcher Tampilan + Ukuran + Detektor + Toggle Filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', flexWrap: 'wrap' }}>
            
            {/* View Mode Switcher */}
            <div style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-secondary)', padding: '2px', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
              {[
                { id: 'edited', label: '✓ Edited (04)' },
                { id: 'dual', label: '⚡ Dual' },
                { id: 'raw', label: '📄 Mentah (03)' }
              ].map(v => (
                <button
                  key={v.id}
                  type="button"
                  onClick={() => setViewMode(v.id)}
                  style={{
                    padding: '0.22rem 0.55rem',
                    borderRadius: '4px',
                    border: 'none',
                    background: viewMode === v.id ? 'var(--accent)' : 'transparent',
                    color: viewMode === v.id ? '#ffffff' : 'var(--text-secondary)',
                    fontWeight: viewMode === v.id ? 700 : 500,
                    fontSize: '0.72rem',
                    cursor: 'pointer',
                    transition: 'all 0.15s'
                  }}
                >
                  {v.label}
                </button>
              ))}
            </div>

            {/* Card Size Switcher */}
            <div style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-secondary)', padding: '2px', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
              {[
                { id: 'normal', label: 'Standar' },
                { id: 'large', label: '🔍 Fokus' }
              ].map(s => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setCardSize(s.id)}
                  style={{
                    padding: '0.22rem 0.55rem',
                    borderRadius: '4px',
                    border: 'none',
                    background: cardSize === s.id ? '#6366f1' : 'transparent',
                    color: cardSize === s.id ? '#ffffff' : 'var(--text-secondary)',
                    fontWeight: cardSize === s.id ? 700 : 500,
                    fontSize: '0.72rem',
                    cursor: 'pointer',
                    transition: 'all 0.15s'
                  }}
                  title={s.id === 'large' ? 'Perbesar tampilan foto agar detail terbaca jelas' : 'Tampilan proporsional'}
                >
                  {s.label}
                </button>
              ))}
            </div>

            {/* Detektor Selector */}
            <div style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-secondary)', padding: '2px', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
              {[
                { id: 'paddle_ocr', label: 'LaMa AI (Hapus Teks)', color: '#10b981' },
                { id: 'google_vision', label: '✨ Vision AI', color: '#a855f7' },
                { id: 'guide', label: '🎯 HSV', color: '#0284c7' }
              ].map(d => (
                <button
                  key={d.id}
                  type="button"
                  onClick={() => setActiveDetector(d.id)}
                  style={{
                    padding: '0.22rem 0.55rem',
                    borderRadius: '4px',
                    border: activeDetector === d.id ? `1px solid ${d.color}` : '1px solid transparent',
                    background: activeDetector === d.id ? `${d.color}25` : 'transparent',
                    color: activeDetector === d.id ? d.color : 'var(--text-secondary)',
                    fontWeight: activeDetector === d.id ? 800 : 500,
                    fontSize: '0.72rem',
                    cursor: 'pointer',
                    transition: 'all 0.15s'
                  }}
                  title={d.id === 'google_vision' ? 'Deteksi Google Cloud Vision AI' : 'Deteksi garis warna HSV'}
                >
                  {d.label}
                </button>
              ))}
            </div>

            {/* Toggle Filter Bar Button */}
            <button
              type="button"
              onClick={toggleFilters}
              style={{
                padding: '0.28rem 0.7rem',
                borderRadius: '6px',
                border: activeFilterCount > 0 ? '1px solid #f59e0b' : '1px solid var(--border-color)',
                background: showFilters ? 'rgba(245, 158, 11, 0.2)' : (activeFilterCount > 0 ? 'rgba(245, 158, 11, 0.12)' : 'var(--bg-secondary)'),
                color: activeFilterCount > 0 ? '#fbbf24' : 'var(--text-primary)',
                fontWeight: 700,
                fontSize: '0.72rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.35rem',
                transition: 'all 0.2s'
              }}
              title={showFilters ? "Ciutkan bar filter untuk meluaskan galeri" : "Buka bar filter pencarian"}
            >
              <span>⚡ Filter</span>
              {activeFilterCount > 0 && (
                <span style={{ background: '#f59e0b', color: '#000000', fontSize: '0.62rem', padding: '1px 5px', borderRadius: '10px', fontWeight: 800 }}>
                  {activeFilterCount}
                </span>
              )}
              <span>{showFilters ? '▲' : '▼'}</span>
            </button>

          </div>
        </div>

        {/* Baris 2: Collapsible Filter Strip (Hanya tampil saat showFilters = true) */}
        {showFilters && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
              gap: '0.45rem',
              width: '100%',
              alignItems: 'center',
              paddingTop: '0.45rem',
              borderTop: '1px solid rgba(255, 255, 255, 0.08)'
            }}
          >
            {/* 1. Berkas Target */}
            <select
              value={selectedFile}
              onChange={e => {
                const val = e.target.value;
                setSelectedFile(val);
                const match = targetFiles.find(t => t.file === val);
                if (match) {
                  if (match.category) setSelectedCategory(match.category);
                  if (match.btp) setSelectedStation(match.btp);
                }
              }}
              style={{ width: '100%', padding: '0.3rem 0.5rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '5px', color: 'var(--text-primary)', fontSize: '0.75rem', outline: 'none' }}
              title="Filter berkas PDF target"
            >
              <option value="">📄 Semua Target PDF</option>
              {allFileOptions.map((opt, idx) => (
                <option key={idx} value={opt.value} title={opt.value}>{opt.label}</option>
              ))}
            </select>

            {/* 2. Stasiun / Wilayah */}
            <select
              value={selectedStation}
              onChange={e => setSelectedStation(e.target.value)}
              style={{ width: '100%', padding: '0.3rem 0.5rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '5px', color: 'var(--text-primary)', fontSize: '0.75rem', outline: 'none' }}
            >
              <option value="">🏢 Semua Stasiun/Wilayah</option>
              {uniqueStations.map(stn => {
                const count = assets.filter(a => a.station === stn).length;
                return <option key={stn} value={stn}>{stn} ({count})</option>;
              })}
            </select>

            {/* 3. Kategori Aset */}
            <select
              value={selectedCategory}
              onChange={e => setSelectedCategory(e.target.value)}
              style={{ width: '100%', padding: '0.3rem 0.5rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '5px', color: 'var(--text-primary)', fontSize: '0.75rem', outline: 'none' }}
            >
              <option value="">🏷️ Semua Kategori ({assets.length})</option>
              {uniqueCategories.map(cat => (
                <option key={cat.key} value={cat.key}>{cat.label} ({cat.count})</option>
              ))}
            </select>

            {/* 4. Kelengkapan */}
            <select
              value={selectedStatus}
              onChange={e => setSelectedStatus(e.target.value)}
              style={{ width: '100%', padding: '0.3rem 0.5rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '5px', color: 'var(--text-primary)', fontSize: '0.75rem', outline: 'none' }}
            >
              <option value="">📊 Status Kelengkapan</option>
              <option value="complete">✓ Lengkap (3 Foto)</option>
              <option value="incomplete">⚠ Belum Lengkap (&lt; 3)</option>
            </select>

            {/* 5. Sumber */}
            <select
              value={sourceTypeFilter}
              onChange={e => setSourceTypeFilter(e.target.value)}
              style={{ width: '100%', padding: '0.3rem 0.5rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '5px', color: 'var(--text-primary)', fontSize: '0.75rem', outline: 'none' }}
            >
              <option value="all">📂 Semua Sumber</option>
              <option value="timemark">✓ Sudah Diedit (04)</option>
              <option value="export">📄 Punya Mentah (03)</option>
              <option value="collage">📑 Foto Kolase ({assets.filter(a => a.isCollage).length})</option>
            </select>

            {/* 6. Cari & Reset */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <input
                type="text"
                placeholder="🔍 Cari nama aset..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                style={{ flex: 1, minWidth: '100px', padding: '0.3rem 0.5rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '5px', color: 'var(--text-primary)', fontSize: '0.75rem', outline: 'none' }}
              />
              {isFilterActive && (
                <button
                  onClick={resetAllFilters}
                  style={{ padding: '0.3rem 0.6rem', background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '5px', cursor: 'pointer', fontSize: '0.72rem', fontWeight: 700, whiteSpace: 'nowrap' }}
                  title="Reset semua filter"
                >
                  ✕ Reset
                </button>
              )}
            </div>
          </div>
        )}
      </div>
{feedback && (
        <div style={{
          padding: '0.75rem 1rem',
          borderRadius: '6px',
          fontSize: '0.85rem',
          background: feedback.type === 'success' ? '#14532d' : '#7f1d1d',
          color: feedback.type === 'success' ? '#86efac' : '#fca5a5',
          border: `1px solid ${feedback.type === 'success' ? '#22c55e' : '#ef4444'}`
        }}>
          {feedback.text}
        </div>
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: '3.5rem', color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
          ⏳ Memuat daftar foto aset dari disk...
        </div>
      )}

      {!loading && filteredAssets.length === 0 && (
        <div style={{ textAlign: 'center', padding: '3.5rem', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '10px', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
          {assets.length === 0
            ? 'Belum ada foto yang diekstraksi di folder ini. Jalankan Step 1 pada Tab Pipeline terlebih dahulu.'
            : 'Tidak ada aset yang cocok dengan kriteria filter atau pencarian saat ini.'}
        </div>
      )}

      {/* ── Asset Card List (1 Baris = 1 Kartu Aset Full-Width, 3 Kolom Foto 0%, 50%, 100%) ── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', width: '100%' }}>
        {filteredAssets.map((asset, idx) => {
          const isComplete = (asset.photos || []).length === 3;
          const isRowMerging = mergingRel === asset.relDir;
          const isRowProcessing = Boolean(actionLoadingKeys[asset.relDir]);
          const isRowBaking = bakingRel === asset.relDir;

          return (
            <div
              key={asset.relDir || idx}
              style={{
                background: 'var(--bg-card)',
                border: '1px solid var(--border-color)',
                borderRadius: '12px',
                padding: '1.25rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '1rem',
                boxShadow: '0 4px 16px rgba(0,0,0,0.18)',
                width: '100%'
              }}
            >
              
              {/* Asset Card Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '0.2rem 0.55rem', borderRadius: '4px', background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.3)' }}>
                    {asset.station}
                  </span>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '0.2rem 0.55rem', borderRadius: '4px', background: 'rgba(52, 211, 153, 0.15)', color: '#34d399', border: '1px solid rgba(52, 211, 153, 0.3)' }}>
                    {asset.category || asset.asset_type}
                  </span>
                  <h4 style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
                    {asset.detail}
                  </h4>

                  {/* Tombol Proses Timemark Otomatis (3 Foto Sekaligus) */}
                  <button
                    onClick={() => handleProcessTimemark(asset)}
                    disabled={isRowProcessing || isRowMerging || (asset.photos || []).length === 0}
                    style={{
                      padding: '0.25rem 0.75rem',
                      borderRadius: '6px',
                      background: (asset.photos || []).length === 0
                        ? 'rgba(100, 116, 139, 0.25)'
                        : isRowProcessing
                        ? 'rgba(147, 51, 234, 0.4)'
                        : getDetectorInfo(activeDetector).gradient,
                      color: (asset.photos || []).length === 0 ? '#94a3b8' : '#ffffff',
                      border: 'none',
                      fontSize: '0.75rem',
                      fontWeight: 800,
                      cursor: isRowProcessing || isRowMerging || (asset.photos || []).length === 0 ? 'not-allowed' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                      boxShadow: (asset.photos || []).length === 0 ? 'none' : getDetectorInfo(activeDetector).shadow,
                      transition: 'all 0.2s'
                    }}
                    title={(asset.photos || []).length === 0 ? 'Belum ada foto mentah yang dapat diproses' : `Edit otomatis 3 foto aset ini menggunakan ${getDetectorInfo(activeDetector).label}`}
                  >
                    {isRowProcessing ? (
                      <>
                        <span style={{ animation: 'spin 1s linear infinite' }}>⏳</span>
                        <span>Memproses...</span>
                      </>
                    ) : (
                      <>
                        <span>{getDetectorInfo(activeDetector).icon}</span>
                        <span>Proses Timemark ({getDetectorInfo(activeDetector).shortLabel})</span>
                      </>
                    )}
                  </button>

                  {/* Tombol Instan ⚡ Merge PDF Per Baris Aset */}
                  <button
                    onClick={() => handleMergeRow(asset)}
                    disabled={isRowMerging || isRowProcessing || (asset.photos || []).length === 0}
                    style={{
                      padding: '0.25rem 0.75rem',
                      borderRadius: '6px',
                      background: (asset.photos || []).length === 0 ? 'rgba(100, 116, 139, 0.25)' : (isRowMerging ? 'rgba(2, 132, 199, 0.4)' : '#0284c7'),
                      color: (asset.photos || []).length === 0 ? '#94a3b8' : '#ffffff',
                      border: 'none',
                      fontSize: '0.75rem',
                      fontWeight: 800,
                      cursor: isRowMerging || isRowProcessing || (asset.photos || []).length === 0 ? 'not-allowed' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                      boxShadow: (asset.photos || []).length === 0 ? 'none' : '0 2px 6px rgba(2, 132, 199, 0.4)',
                      transition: 'all 0.2s'
                    }}
                    title={(asset.photos || []).length === 0 ? 'Foto belum tersedia untuk dimerge' : 'Gabungkan 1 baris aset ini langsung ke file PDF target terkait'}
                  >
                    {isRowMerging ? (
                      <>
                        <span>⏳</span>
                        <span>Merging...</span>
                      </>
                    ) : (
                      <>
                        <span>⚡</span>
                        <span>Merge PDF</span>
                      </>
                    )}
                  </button>

                  {/* Tombol Tempel Tanggal Fisik (Bake Virtual Overlay to Physical JPG) */}
                  <button
                    onClick={() => handleBakeStamp(asset)}
                    disabled={isRowBaking || isRowMerging || isRowProcessing || (asset.photos || []).length === 0}
                    style={{
                      padding: '0.25rem 0.65rem',
                      borderRadius: '6px',
                      background: (asset.photos || []).length === 0 ? 'rgba(100, 116, 139, 0.25)' : (isRowBaking ? 'rgba(234, 179, 8, 0.4)' : '#d97706'),
                      color: (asset.photos || []).length === 0 ? '#94a3b8' : '#ffffff',
                      border: 'none',
                      fontSize: '0.75rem',
                      fontWeight: 800,
                      cursor: isRowBaking || isRowMerging || isRowProcessing || (asset.photos || []).length === 0 ? 'not-allowed' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                      boxShadow: (asset.photos || []).length === 0 ? 'none' : '0 2px 6px rgba(217, 119, 6, 0.4)',
                      transition: 'all 0.2s'
                    }}
                    title="Tempelkan posisi watermark tanggal sekarang langsung ke file fisik JPG (04_photos_edited)"
                  >
                    {isRowBaking ? (
                      <>
                        <span className="spinner-border spinner-border-sm" style={{ width: '12px', height: '12px', borderWidth: '2px' }} />
                        <span>Menempel...</span>
                      </>
                    ) : (
                      <>
                        <span>💾</span>
                        <span>Tempel Tanggal</span>
                      </>
                    )}
                  </button>

                  {asset.targetFiles && asset.targetFiles.length > 0 && (
                    <span
                      style={{ fontSize: '0.72rem', color: '#93c5fd', background: 'rgba(59, 130, 246, 0.15)', padding: '0.2rem 0.5rem', borderRadius: '4px', border: '1px solid rgba(59, 130, 246, 0.25)', cursor: 'help' }}
                      title={`Digunakan pada ${asset.targetFiles.length} berkas target:\n${asset.targetFiles.join('\n')}`}
                    >
                      📄 {asset.targetFiles.length} Target PDF
                    </span>
                  )}
                  {asset.sourceFile && (
                    <span
                      style={{ fontSize: '0.72rem', color: '#cbd5e1', background: 'rgba(100, 116, 139, 0.2)', padding: '0.2rem 0.5rem', borderRadius: '4px', border: '1px solid rgba(100, 116, 139, 0.3)' }}
                      title={`Sumber: ${asset.sourceFile}`}
                    >
                      📥 {asset.sourceFile}
                    </span>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, padding: '0.25rem 0.6rem', borderRadius: '5px', background: isComplete ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)', color: isComplete ? '#4ade80' : '#f87171', border: `1px solid ${isComplete ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)'}` }}>
                    {isComplete ? '✅ Lengkap (3 Foto)' : `⚠️ ${(asset.photos || []).length}/3 Foto`}
                  </span>
                  <button
                    type="button"
                    onClick={() => setEditingRowDateAsset(asset)}
                    style={{
                      fontSize: '0.8rem',
                      color: asset.hasEdited ? '#4ade80' : '#38bdf8',
                      background: asset.hasEdited ? 'rgba(34, 197, 94, 0.12)' : 'rgba(56, 189, 248, 0.12)',
                      border: asset.hasEdited ? '1px solid rgba(34, 197, 94, 0.35)' : '1px solid rgba(56, 189, 248, 0.35)',
                      padding: '0.25rem 0.65rem',
                      borderRadius: '6px',
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                      transition: 'all 0.18s ease',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.2)'
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.transform = 'translateY(-1px)';
                      e.currentTarget.style.borderColor = '#10b981';
                      e.currentTarget.style.boxShadow = '0 3px 8px rgba(16, 185, 129, 0.35)';
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.transform = 'none';
                      e.currentTarget.style.borderColor = asset.hasEdited ? 'rgba(34, 197, 94, 0.35)' : 'rgba(56, 189, 248, 0.35)';
                      e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.2)';
                    }}
                    title="Klik untuk ubah tanggal & jam dinas langsung untuk 3 foto (0%, 50%, 100%)"
                  >
                    <span>📅</span>
                    <span>{asset.dateText || 'Belum ada tanggal'}</span>
                    <span style={{ fontSize: '0.75rem', opacity: 0.85 }}>✏️</span>
                  </button>
                </div>
              </div>

              {/* 3 Photos Grid (0% | 50% | 100%) Across 3 Large Columns */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: viewMode === 'dual'
                    ? (cardSize === 'large' ? 'repeat(auto-fit, minmax(420px, 1fr))' : 'repeat(auto-fit, minmax(360px, 1fr))')
                    : (cardSize === 'large' ? 'repeat(auto-fit, minmax(340px, 1fr))' : 'repeat(auto-fit, minmax(280px, 1fr))'),
                  gap: '1rem',
                  width: '100%'
                }}
              >
                {['0.jpg', '50.jpg', '100.jpg'].map((photoName) => {
                  const targetKey = `${asset.relDir}/${photoName}`;
                  const photoObj = (asset.photos || []).find(p => p.name === photoName);
                  const cardVer = photoCardVersions[targetKey];
                  const editedPhotoUrl = photoObj?.editedUrl ? (cardVer ? `${photoObj.editedUrl}${photoObj.editedUrl.includes('?') ? '&' : '?'}_v=${cardVer}` : photoObj.editedUrl) : null;
                  const targetCleanUrl = (photoObj?.hasClean && photoObj?.cleanUrl) ? (cardVer ? `${photoObj.cleanUrl}${photoObj.cleanUrl.includes('?') ? '&' : '?'}_v=${cardVer}` : photoObj.cleanUrl) : null;
                  const labelPercent = photoName.replace('.jpg', '') + '%';
                  const isDragOver = dragOverRel === targetKey;
                  const isActionLoading = Boolean(actionLoadingKeys[targetKey]);
                  const isManual = photoObj?.meta?.manualEdit;
                  const dualCardHeight = cardSize === 'large' ? 290 : 220;
                  const singleCardHeight = cardSize === 'large' ? 380 : 270;
                  const currentSingleView = photoViewOverrides[targetKey] || (viewMode === 'raw' ? 'raw' : (photoObj?.hasEdited ? 'edited' : 'raw'));

                  return (
                    <div
                      key={`${asset.relDir}_${photoName}`}
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.6rem',
                        background: 'var(--bg-secondary)',
                        borderRadius: '8px',
                        padding: '0.75rem',
                        border: '1px solid var(--border-color)',
                        boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.1)',
                        position: 'relative'
                      }}
                    >
                      {/* Photo Top Badge */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                        <strong style={{ color: 'var(--text-primary)', fontSize: '0.85rem' }}>Foto {labelPercent}</strong>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                          {photoObj ? (
                            <>
                              {photoObj.isCollage && (
                                <span
                                  style={{
                                    fontSize: '0.7rem',
                                    padding: '1px 6px',
                                    borderRadius: '4px',
                                    background: photoObj.hasTemp ? 'rgba(34, 197, 94, 0.2)' : 'rgba(234, 179, 8, 0.2)',
                                    color: photoObj.hasTemp ? '#4ade80' : '#facc15',
                                    border: photoObj.hasTemp ? '1px solid #22c55e' : '1px solid #eab308',
                                    fontWeight: 600
                                  }}
                                  title={photoObj.hasTemp ? "Foto ini adalah kolase dan telah dipotong" : "Foto ini adalah kolase dan belum dipotong"}
                                >
                                  🗂️ {photoObj.hasTemp ? 'Kolase Terpotong' : 'Kolase'}
                                </span>
                              )}

                              {isManual && (
                                <span style={{ fontSize: '0.7rem', padding: '1px 6px', borderRadius: '4px', background: 'rgba(245, 158, 11, 0.2)', color: '#fbbf24', border: '1px solid #f59e0b', fontWeight: 600 }}>
                                  Manual (Y:{photoObj.meta.yPos})
                                </span>
                              )}

                              {viewMode === 'dual' ? (
                                photoObj.hasRaw && photoObj.hasEdited ? (
                                  <span style={{ fontSize: '0.7rem', padding: '1px 6px', borderRadius: '4px', background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.3)', fontWeight: 600 }}>
                                    📷 03 & ✨ 04
                                  </span>
                                ) : photoObj.hasEdited ? (
                                  <span style={{ fontSize: '0.7rem', padding: '1px 6px', borderRadius: '4px', background: 'rgba(34, 197, 94, 0.2)', color: '#4ade80', border: '1px solid #22c55e', fontWeight: 600 }}>
                                    ✨ Editan (04)
                                  </span>
                                ) : (
                                  <span style={{ fontSize: '0.7rem', padding: '1px 6px', borderRadius: '4px', background: 'rgba(148, 163, 184, 0.2)', color: '#94a3b8', border: '1px solid rgba(148, 163, 184, 0.4)' }}>
                                    📷 Mentah (03)
                                  </span>
                                )
                              ) : (
                                /* Quick Flip Toggle di Single Mode */
                                photoObj.hasRaw && photoObj.hasEdited ? (
                                  <div style={{ display: 'flex', alignItems: 'center', background: 'rgba(0,0,0,0.3)', borderRadius: '5px', padding: '1px', border: '1px solid rgba(255,255,255,0.1)' }}>
                                    <button
                                      type="button"
                                      onClick={() => setPhotoViewOverrides(prev => ({ ...prev, [targetKey]: 'edited' }))}
                                      style={{
                                        border: 'none',
                                        padding: '1px 6px',
                                        borderRadius: '4px',
                                        fontSize: '0.68rem',
                                        fontWeight: 700,
                                        cursor: 'pointer',
                                        background: currentSingleView === 'edited' ? '#10b981' : 'transparent',
                                        color: currentSingleView === 'edited' ? '#ffffff' : '#94a3b8'
                                      }}
                                      title="Tampilkan Foto Editan Timemark (04)"
                                    >
                                      ✨ 04
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => setPhotoViewOverrides(prev => ({ ...prev, [targetKey]: 'raw' }))}
                                      style={{
                                        border: 'none',
                                        padding: '1px 6px',
                                        borderRadius: '4px',
                                        fontSize: '0.68rem',
                                        fontWeight: 700,
                                        cursor: 'pointer',
                                        background: currentSingleView === 'raw' ? '#38bdf8' : 'transparent',
                                        color: currentSingleView === 'raw' ? '#ffffff' : '#94a3b8'
                                      }}
                                      title="Tampilkan Foto Mentah Ekspor (03)"
                                    >
                                      📷 03
                                    </button>
                                  </div>
                                ) : currentSingleView === 'edited' ? (
                                  <span style={{ fontSize: '0.7rem', padding: '1px 6px', borderRadius: '4px', background: 'rgba(34, 197, 94, 0.2)', color: '#4ade80', border: '1px solid #22c55e', fontWeight: 600 }}>
                                    ✨ Editan (04)
                                  </span>
                                ) : (
                                  <span style={{ fontSize: '0.7rem', padding: '1px 6px', borderRadius: '4px', background: 'rgba(148, 163, 184, 0.2)', color: '#94a3b8', border: '1px solid rgba(148, 163, 184, 0.4)', fontWeight: 600 }}>
                                    📷 Mentah (03)
                                  </span>
                                )
                              )}

                              {photoObj.hasBackup && (
                                <span style={{ fontSize: '0.7rem', padding: '1px 6px', borderRadius: '4px', background: 'rgba(234, 179, 8, 0.2)', color: '#facc15', border: '1px solid #eab308' }} title="Foto ini pernah diganti dan memiliki salinan asli">
                                  ↩️ Diganti
                                </span>
                              )}
                            </>
                          ) : (
                            <span style={{ fontSize: '0.72rem', color: '#f87171', fontWeight: 600 }}>Kosong</span>
                          )}
                        </div>
                      </div>

                      {/* Photo Image Area: Dual Split vs Single */}
                      {viewMode === 'dual' ? (
                        /* Komparasi Berdampingan: Sisi Kiri (Mentah 03) vs Sisi Kanan (Editan 04) */
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', width: '100%' }}>
                          
                          {/* Sisi Kiri: Foto Mentah (03_export_foto) */}
                          <div
                            onDragOver={e => {
                              e.preventDefault();
                              e.stopPropagation();
                              if (dragOverRel !== targetKey) {
                                setDragOverRel(targetKey);
                              }
                            }}
                            onDragLeave={e => {
                              e.preventDefault();
                              e.stopPropagation();
                              if (e.currentTarget.contains(e.relatedTarget)) return;
                              setDragOverRel(null);
                            }}
                            onDrop={e => {
                              e.preventDefault();
                              e.stopPropagation();
                              setDragOverRel(null);

                              // 1. Cek swap foto internal
                              const swapData = e.dataTransfer.getData('application/x-sintelis-photo');
                              if (swapData) {
                                try {
                                  const parsed = JSON.parse(swapData);
                                  if (parsed.rel && parsed.rel !== targetKey) {
                                    handleSwapPhotos(parsed.rel, targetKey);
                                    return;
                                  }
                                } catch (_) {}
                              }

                              // 2. Drop file baru dari komputer
                              const f = e.dataTransfer.files?.[0];
                              if (f) handleDirectDrop(asset.relDir, photoName, f);
                            }}
                            style={{
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '0.35rem',
                              background: '#090d16',
                              borderRadius: '6px',
                              padding: '0.45rem',
                              border: isDragOver ? '2px dashed #f59e0b' : '1px solid rgba(148, 163, 184, 0.25)',
                              position: 'relative'
                            }}
                            title="Tarik & lepaskan file gambar ke sini untuk mengganti foto mentah, atau seret foto ini ke slot lain untuk menukar posisi"
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                                <span style={{ cursor: 'grab' }} title="Seret untuk tukar posisi">✥</span>
                                📷 {photoObj?.hasTemp ? 'Mentah (Terpotong)' : 'Mentah (03)'}
                              </span>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                {photoObj?.isCollage && (
                                  <>
                                    <button
                                      type="button"
                                      onClick={() => handleCropCollageSingle(targetKey)}
                                      disabled={isActionLoading}
                                      style={{
                                        background: photoObj.hasTemp ? 'rgba(34, 197, 94, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                                        border: photoObj.hasTemp ? '1px solid #22c55e' : '1px solid #f59e0b',
                                        color: photoObj.hasTemp ? '#4ade80' : '#fbbf24',
                                        cursor: isActionLoading ? 'not-allowed' : 'pointer',
                                        padding: '1px 5px',
                                        borderRadius: '4px',
                                        fontSize: '0.68rem',
                                        fontWeight: 600
                                      }}
                                      title={photoObj.hasTemp ? "Klik untuk ganti kuadran potong (Kiri-Atas ➔ Kanan-Atas ➔ Kiri-Bawah ➔ Kanan-Bawah ➔ Utuh)" : "Potong otomatis kolase ini (auto-crop 300x300)"}
                                    >
                                      ✂️ {isActionLoading ? '...' : (photoObj.hasTemp ? 'Potong Ulang' : 'Potong')}
                                    </button>
                                    {photoObj.hasTemp && (
                                      <button
                                        type="button"
                                        onClick={() => handleCropCollageSingle(targetKey, 'ORIGINAL')}
                                        disabled={isActionLoading}
                                        style={{
                                          background: 'rgba(239, 68, 68, 0.18)',
                                          border: '1px solid #ef4444',
                                          color: '#f87171',
                                          cursor: isActionLoading ? 'not-allowed' : 'pointer',
                                          padding: '1px 5px',
                                          borderRadius: '4px',
                                          fontSize: '0.68rem',
                                          fontWeight: 600
                                        }}
                                        title="Kembalikan ke foto utuh (batal potong kolase) dan perbarui timemark"
                                      >
                                        ↩️ Utuh
                                      </button>
                                    )}
                                  </>
                                )}
                                {photoObj?.rawUrl && (
                                  <button
                                    type="button"
                                    onClick={() => setZoomPhoto({ url: (photoObj.hasTemp && photoObj.tempUrl) ? photoObj.tempUrl : photoObj.rawUrl, title: `${asset.detail} - ${labelPercent} (${photoObj.hasTemp ? 'Mentah Terpotong' : 'Mentah 03'})` })}
                                    style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '0 2px', fontSize: '0.75rem' }}
                                    title={photoObj.hasTemp ? "Perbesar Foto Mentah Terpotong" : "Perbesar Foto Mentah (03)"}
                                  >
                                    🔍
                                  </button>
                                )}
                              </div>
                            </div>

                            <div style={{ width: '100%', height: `${dualCardHeight}px`, display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', borderRadius: '4px', background: '#000000', position: 'relative' }}>
                              {photoObj?.rawUrl ? (
                                <div style={{ position: 'relative', display: 'inline-block', maxWidth: '100%', maxHeight: '100%', lineHeight: 0, textAlign: 'center' }}>
                                  <img
                                    src={(photoObj.hasTemp && photoObj.tempUrl) ? photoObj.tempUrl : photoObj.rawUrl}
                                    alt={`${asset.detail} - ${labelPercent} (${photoObj.hasTemp ? 'Mentah Terpotong' : 'Mentah'})`}
                                    style={{ maxWidth: '100%', maxHeight: `${dualCardHeight}px`, width: 'auto', height: 'auto', objectFit: 'contain', cursor: 'grab', display: 'block' }}
                                    loading="lazy"
                                    draggable={true}
                                    onDragStart={e => {
                                      if (e.target.closest('.inline-timemark-box')) {
                                        e.preventDefault();
                                        return;
                                      }
                                      const payload = JSON.stringify({ rel: targetKey, assetRel: asset.relDir, photoName });
                                      e.dataTransfer.setData('application/x-sintelis-photo', payload);
                                      e.dataTransfer.setData('text/plain', targetKey);
                                      setDraggedPhotoInfo({ rel: targetKey, assetRel: asset.relDir, photoName });
                                    }}
                                    onDragEnd={() => setDraggedPhotoInfo(null)}
                                    title="Klik & tahan (drag) untuk menukar posisi dengan foto lain"
                                  />
                                </div>
                              ) : (
                                <div style={{ textAlign: 'center', color: '#64748b', fontSize: '0.72rem', padding: '0.5rem' }}>
                                  <div style={{ fontSize: '1.25rem', marginBottom: '0.2rem' }}>📷</div>
                                  Foto mentah (03) belum ada
                                </div>
                              )}
                            </div>

                            {/* Drag Over Overlay */}
                            {isDragOver && (
                              <div style={{ position: 'absolute', inset: 0, background: 'rgba(245, 158, 11, 0.9)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#ffffff', zIndex: 10, borderRadius: '6px', pointerEvents: 'none' }}>
                                <span style={{ fontSize: '1.5rem', pointerEvents: 'none' }}>📥</span>
                                <strong style={{ fontSize: '0.75rem', pointerEvents: 'none' }}>Lepaskan untuk Ganti / Tukar Posisi</strong>
                              </div>
                            )}

                            {/* Action Loading Spinner */}
                            {isActionLoading && (
                              <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#4ade80', zIndex: 10, borderRadius: '6px' }}>
                                <span style={{ fontSize: '1.25rem', animation: 'spin 1s linear infinite' }}>⏳</span>
                                <span style={{ fontSize: '0.7rem', fontWeight: 600 }}>Memproses...</span>
                              </div>
                            )}
                          </div>

                          {/* Sisi Kanan: Foto Editan (04_photos_edited) */}
                          <div
                            onDragOver={e => {
                              e.preventDefault();
                              e.stopPropagation();
                              if (dragOverRel !== targetKey) {
                                setDragOverRel(targetKey);
                              }
                            }}
                            onDragLeave={e => {
                              e.preventDefault();
                              e.stopPropagation();
                              if (e.currentTarget.contains(e.relatedTarget)) return;
                              setDragOverRel(null);
                            }}
                            onDrop={e => {
                              e.preventDefault();
                              e.stopPropagation();
                              setDragOverRel(null);

                              // Cek swap foto internal
                              const swapData = e.dataTransfer.getData('application/x-sintelis-photo');
                              if (swapData) {
                                try {
                                  const parsed = JSON.parse(swapData);
                                  if (parsed.rel && parsed.rel !== targetKey) {
                                    handleSwapPhotos(parsed.rel, targetKey);
                                    return;
                                  }
                                } catch (_) {}
                              }

                              const f = e.dataTransfer.files?.[0];
                              if (f) handleDirectDrop(asset.relDir, photoName, f);
                            }}
                            style={{
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '0.35rem',
                              background: '#090d16',
                              borderRadius: '6px',
                              padding: '0.45rem',
                              border: isDragOver ? '2px dashed #f59e0b' : '1px solid rgba(52, 211, 153, 0.35)',
                              position: 'relative'
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontSize: '0.7rem', fontWeight: 800, color: '#34d399', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                                <span style={{ cursor: 'grab' }} title="Seret untuk tukar posisi">✥</span>
                                ✨ Editan (04)
                              </span>
                              {photoObj?.editedUrl && (
                                <button
                                  type="button"
                                  onClick={() => {
                                    const coord = photoCoordsMap[targetKey] || photoCoordsMap[targetKey.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')] || {};
                                    const x = coord.x ?? photoObj?.meta?.xPos ?? 14;
                                    const y = coord.y ?? photoObj?.meta?.yPos ?? 220;
                                    const dt = photoObj?.meta?.dateText || (
                                      photoName === '50.jpg' ? helperCalculateDate(asset.dateText, '50') :
                                      photoName === '100.jpg' ? helperCalculateDate(asset.dateText, '100') :
                                      asset.dateText || ''
                                    );
                                    const cleanTarget = (photoObj?.hasClean && photoObj?.cleanUrl) ? photoObj.cleanUrl : null;
                                    setZoomPhoto({
                                      url: cleanTarget || editedPhotoUrl || photoObj.editedUrl,
                                      title: `${asset.detail} - ${labelPercent} (Hasil Timemark 04)`,
                                      dateText: cleanTarget ? dt : null,
                                      xPos: x,
                                      yPos: y
                                    });
                                  }}
                                  style={{ background: 'transparent', border: 'none', color: '#34d399', cursor: 'pointer', padding: '0 2px', fontSize: '0.75rem' }}
                                  title="Perbesar Foto Editan Timemark (04)"
                                >
                                  🔍
                                </button>
                              )}
                            </div>

                            <div style={{ width: '100%', height: `${dualCardHeight}px`, display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', borderRadius: '4px', background: '#000000', position: 'relative' }}>
                              {photoObj?.editedUrl ? (
                                <div style={{ position: 'relative', display: 'inline-block', maxWidth: '100%', maxHeight: '100%', lineHeight: 0, textAlign: 'center' }}>
                                  <img
                                    src={targetCleanUrl || editedPhotoUrl || photoObj.editedUrl}
                                    alt={`${asset.detail} - ${labelPercent} (Editan)`}
                                    style={{ maxWidth: '100%', maxHeight: `${dualCardHeight}px`, width: 'auto', height: 'auto', objectFit: 'contain', cursor: 'grab', display: 'block' }}
                                    loading="lazy"
                                    draggable={true}
                                    onDragStart={e => {
                                      if (e.target.closest('.inline-timemark-box')) {
                                        e.preventDefault();
                                        return;
                                      }
                                      const payload = JSON.stringify({ rel: targetKey, assetRel: asset.relDir, photoName });
                                      e.dataTransfer.setData('application/x-sintelis-photo', payload);
                                      e.dataTransfer.setData('text/plain', targetKey);
                                      setDraggedPhotoInfo({ rel: targetKey, assetRel: asset.relDir, photoName });
                                    }}
                                    onDragEnd={() => setDraggedPhotoInfo(null)}
                                    title="Seret foto ini untuk menukar posisi"
                                  />

                                  {/* Kotak Timemark Interaktif yang Dapat Digeser (Inline Draggable Box) */}
                                  <InlineTimemarkBox
                                    key={targetKey}
                                    asset={asset}
                                    photo={photoObj}
                                    photoName={photoName}
                                    targetKey={targetKey}
                                    localCoord={photoCoordsMap[targetKey] || photoCoordsMap[targetKey.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')]}
                                    exportDir={exportDir}
                                    activeDetector={activeDetector}
                                    lastTimemarkPos={lastTimemarkPos}
                                    onPosChange={(k, c) => {
                                      updatePhotoLocalPos(k, c);
                                      updateLastTimemarkPos(c);
                                    }}
                                    onSaved={(info) => info?.targetKey ? refreshSinglePhotoCard(info.targetKey, info) : fetchPhotos()}
                                    onOpenModal={() => setEditingModal({ asset, photo: photoObj })}
                                  />
                                </div>
                              ) : (
                                <div style={{ textAlign: 'center', color: '#f59e0b', fontSize: '0.72rem', padding: '0.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.35rem' }}>
                                  <div style={{ fontSize: '1.25rem' }}>⚠️</div>
                                  <div>Belum diedit (04)</div>
                                  <button
                                    type="button"
                                    onClick={() => handleProcessTimemark(asset, photoName)}
                                    disabled={isActionLoading}
                                    style={{
                                      marginTop: '0.2rem',
                                      padding: '0.35rem 0.65rem',
                                      background: getDetectorInfo(activeDetector).gradient,
                                      color: '#ffffff',
                                      border: 'none',
                                      borderRadius: '5px',
                                      fontSize: '0.7rem',
                                      fontWeight: 700,
                                      cursor: isActionLoading ? 'not-allowed' : 'pointer',
                                      display: 'flex',
                                      alignItems: 'center',
                                      gap: '0.3rem',
                                      boxShadow: '0 2px 5px rgba(0,0,0,0.3)'
                                    }}
                                    title={`Proses timemark foto ini sekarang menggunakan ${getDetectorInfo(activeDetector).label}`}
                                  >
                                    <span>{getDetectorInfo(activeDetector).icon}</span>
                                    <span>{isActionLoading ? 'Memproses...' : `Proses (${getDetectorInfo(activeDetector).shortLabel})`}</span>
                                  </button>
                                </div>
                              )}
                            </div>

                            {/* Drag Over Overlay */}
                            {isDragOver && (
                              <div style={{ position: 'absolute', inset: 0, background: 'rgba(245, 158, 11, 0.9)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#ffffff', zIndex: 10, borderRadius: '6px', pointerEvents: 'none' }}>
                                <span style={{ fontSize: '1.5rem', pointerEvents: 'none' }}>📥</span>
                                <strong style={{ fontSize: '0.75rem', pointerEvents: 'none' }}>Lepaskan untuk Ganti / Tukar Posisi</strong>
                              </div>
                            )}

                            {/* Action Loading Spinner */}
                            {isActionLoading && (
                              <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#4ade80', zIndex: 10, borderRadius: '6px' }}>
                                <span style={{ fontSize: '1.25rem', animation: 'spin 1s linear infinite' }}>⏳</span>
                                <span style={{ fontSize: '0.7rem', fontWeight: 600 }}>Memproses...</span>
                              </div>
                            )}
                          </div>

                        </div>
                      ) : (
                        /* Mode Tunggal: 'raw' (Hanya Mentah 03) atau 'edited' (Hanya Editan 04) dengan PiP Preview */
                        <div
                          onDragOver={e => {
                            e.preventDefault();
                            e.stopPropagation();
                            if (dragOverRel !== targetKey) {
                              setDragOverRel(targetKey);
                            }
                          }}
                          onDragLeave={e => {
                            e.preventDefault();
                            e.stopPropagation();
                            if (e.currentTarget.contains(e.relatedTarget)) return;
                            setDragOverRel(null);
                          }}
                          onDrop={e => {
                            e.preventDefault();
                            e.stopPropagation();
                            setDragOverRel(null);

                            // Swap foto internal
                            const swapData = e.dataTransfer.getData('application/x-sintelis-photo');
                            if (swapData) {
                              try {
                                const parsed = JSON.parse(swapData);
                                if (parsed.rel && parsed.rel !== targetKey) {
                                  handleSwapPhotos(parsed.rel, targetKey);
                                  return;
                                }
                              } catch (_) {}
                            }

                            const f = e.dataTransfer.files?.[0];
                            if (f) handleDirectDrop(asset.relDir, photoName, f);
                          }}
                          style={{
                            width: '100%',
                            height: `${singleCardHeight}px`,
                            background: '#090d16',
                            borderRadius: '6px',
                            overflow: 'hidden',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            border: isDragOver ? '3px dashed #f59e0b' : '1px solid rgba(255,255,255,0.06)',
                            position: 'relative'
                          }}
                          title="Tarik & lepaskan file gambar ke sini untuk mengganti foto mentah, atau seret foto ini ke slot lain untuk menukar posisi"
                        >
                          {currentSingleView === 'raw' ? (
                            photoObj?.rawUrl ? (
                              <div style={{ position: 'relative', display: 'inline-block', maxWidth: '100%', maxHeight: '100%', lineHeight: 0, textAlign: 'center' }}>
                                <img
                                  src={(photoObj.hasTemp && photoObj.tempUrl) ? photoObj.tempUrl : photoObj.rawUrl}
                                  alt={`${asset.detail} - ${labelPercent} (${photoObj.hasTemp ? 'Mentah Terpotong' : 'Mentah'})`}
                                  style={{ maxWidth: '100%', maxHeight: `${singleCardHeight}px`, width: 'auto', height: 'auto', objectFit: 'contain', cursor: 'grab', display: 'block' }}
                                  loading="lazy"
                                  draggable={true}
                                  onDragStart={e => {
                                    const payload = JSON.stringify({ rel: targetKey, assetRel: asset.relDir, photoName });
                                    e.dataTransfer.setData('application/x-sintelis-photo', payload);
                                    e.dataTransfer.setData('text/plain', targetKey);
                                    setDraggedPhotoInfo({ rel: targetKey, assetRel: asset.relDir, photoName });
                                  }}
                                  onDragEnd={() => setDraggedPhotoInfo(null)}
                                />
                              </div>
                            ) : (
                              <div style={{ textAlign: 'center', color: '#64748b', fontSize: '0.8rem', padding: '1rem' }}>
                                <div style={{ fontSize: '1.5rem', marginBottom: '0.25rem' }}>📷</div>
                                Foto mentah (03_export_foto) belum diekstrak
                              </div>
                            )
                          ) : (
                            photoObj?.editedUrl ? (
                              <div style={{ position: 'relative', display: 'inline-block', maxWidth: '100%', maxHeight: '100%', lineHeight: 0, textAlign: 'center' }}>
                                <img
                                  src={targetCleanUrl || editedPhotoUrl || photoObj.editedUrl}
                                  alt={`${asset.detail} - ${labelPercent} (Editan)`}
                                  style={{ maxWidth: '100%', maxHeight: `${singleCardHeight}px`, width: 'auto', height: 'auto', objectFit: 'contain', cursor: 'grab', display: 'block' }}
                                  loading="lazy"
                                  draggable={true}
                                  onDragStart={e => {
                                    if (e.target.closest('.inline-timemark-box')) {
                                      e.preventDefault();
                                      return;
                                    }
                                    const payload = JSON.stringify({ rel: targetKey, assetRel: asset.relDir, photoName });
                                    e.dataTransfer.setData('application/x-sintelis-photo', payload);
                                    e.dataTransfer.setData('text/plain', targetKey);
                                    setDraggedPhotoInfo({ rel: targetKey, assetRel: asset.relDir, photoName });
                                  }}
                                  onDragEnd={() => setDraggedPhotoInfo(null)}
                                />

                                {/* Kotak Timemark Interaktif yang Terkunci Tepat pada Foto */}
                                <InlineTimemarkBox
                                  key={targetKey}
                                  asset={asset}
                                  photo={photoObj}
                                  photoName={photoName}
                                  targetKey={targetKey}
                                  localCoord={photoCoordsMap[targetKey] || photoCoordsMap[targetKey.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')]}
                                  exportDir={exportDir}
                                  activeDetector={activeDetector}
                                  lastTimemarkPos={lastTimemarkPos}
                                  onPosChange={(k, c) => {
                                    updatePhotoLocalPos(k, c);
                                    updateLastTimemarkPos(c);
                                  }}
                                  onSaved={(info) => info?.targetKey ? refreshSinglePhotoCard(info.targetKey, info) : fetchPhotos()}
                                  onOpenModal={() => setEditingModal({ asset, photo: photoObj })}
                                />
                              </div>
                            ) : (
                              <div style={{ textAlign: 'center', color: '#f59e0b', fontSize: '0.8rem', padding: '1rem', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.4rem' }}>
                                <div style={{ fontSize: '1.75rem' }}>⚠️</div>
                                <div>Foto belum diedit (04_photos_edited)</div>
                                <button
                                  type="button"
                                  onClick={() => handleProcessTimemark(asset, photoName)}
                                  disabled={isActionLoading}
                                  style={{
                                    marginTop: '0.25rem',
                                    padding: '0.4rem 0.85rem',
                                    background: getDetectorInfo(activeDetector).gradient,
                                    color: '#ffffff',
                                    border: 'none',
                                    borderRadius: '6px',
                                    fontSize: '0.75rem',
                                    fontWeight: 700,
                                    cursor: isActionLoading ? 'not-allowed' : 'pointer',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.35rem',
                                    boxShadow: '0 2px 6px rgba(0,0,0,0.3)'
                                  }}
                                  title={`Proses timemark foto ini sekarang menggunakan ${getDetectorInfo(activeDetector).label}`}
                                >
                                  <span>{getDetectorInfo(activeDetector).icon}</span>
                                  <span>{isActionLoading ? 'Memproses...' : `Proses Timemark (${getDetectorInfo(activeDetector).shortLabel})`}</span>
                                </button>
                              </div>
                            )
                          )}

                          {/* Mini PiP Thumbnail untuk melihat foto pasangannya (03 vs 04) secara instan */}
                          {photoObj?.hasRaw && photoObj?.hasEdited && (
                            <div
                              onClick={(e) => {
                                e.stopPropagation();
                                setPhotoViewOverrides(prev => ({
                                  ...prev,
                                  [targetKey]: currentSingleView === 'edited' ? 'raw' : 'edited'
                                }));
                              }}
                              style={{
                                position: 'absolute',
                                bottom: '10px',
                                right: '10px',
                                width: '64px',
                                height: '48px',
                                borderRadius: '6px',
                                border: currentSingleView === 'edited' ? '2px solid #38bdf8' : '2px solid #10b981',
                                background: '#000000',
                                overflow: 'hidden',
                                cursor: 'pointer',
                                boxShadow: '0 4px 12px rgba(0,0,0,0.7)',
                                zIndex: 20,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                transition: 'transform 0.15s ease'
                              }}
                              title={`Klik untuk intip/beralih ke Foto ${currentSingleView === 'edited' ? 'Mentah (03)' : 'Editan Timemark (04)'}`}
                              onMouseEnter={e => e.currentTarget.style.transform = 'scale(1.1)'}
                              onMouseLeave={e => e.currentTarget.style.transform = 'scale(1)'}
                            >
                              <img
                                src={currentSingleView === 'edited' ? photoObj.rawUrl : (targetCleanUrl || editedPhotoUrl || photoObj.editedUrl)}
                                alt="Thumbnail sebaliknya"
                                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                              />
                              <span
                                style={{
                                  position: 'absolute',
                                  top: '2px',
                                  left: '2px',
                                  fontSize: '0.55rem',
                                  fontWeight: 800,
                                  padding: '1px 3px',
                                  borderRadius: '3px',
                                  background: currentSingleView === 'edited' ? 'rgba(56, 189, 248, 0.9)' : 'rgba(16, 185, 129, 0.9)',
                                  color: '#ffffff',
                                  lineHeight: 1
                                }}
                              >
                                {currentSingleView === 'edited' ? '03' : '04'}
                              </span>
                            </div>
                          )}

                          {/* Drag Over Overlay */}
                          {isDragOver && (
                            <div style={{ position: 'absolute', inset: 0, background: 'rgba(245, 158, 11, 0.9)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#ffffff', zIndex: 10, pointerEvents: 'none' }}>
                              <span style={{ fontSize: '2rem', pointerEvents: 'none' }}>📥</span>
                              <strong style={{ fontSize: '0.9rem', pointerEvents: 'none' }}>Lepaskan untuk ganti foto</strong>
                            </div>
                          )}

                          {/* Action Loading Spinner */}
                          {isActionLoading && (
                            <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#4ade80', zIndex: 10 }}>
                              <span style={{ fontSize: '1.5rem', animation: 'spin 1s linear infinite' }}>⏳</span>
                              <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Memproses foto...</span>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Photo Bottom Controls */}
                      {photoObj && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', justifyContent: 'space-between', paddingTop: '0.2rem' }}>
                          <button
                            type="button"
                            onClick={() => handleProcessTimemark(asset, photoName)}
                            disabled={isActionLoading}
                            style={{
                              padding: '0.4rem 0.65rem',
                              background: getDetectorInfo(activeDetector).btnBg,
                              color: getDetectorInfo(activeDetector).btnColor,
                              border: getDetectorInfo(activeDetector).border,
                              borderRadius: '6px',
                              cursor: isActionLoading ? 'not-allowed' : 'pointer',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              gap: '0.3rem',
                              transition: 'all 0.2s'
                            }}
                            title={`Proses timemark foto ini sekarang menggunakan ${getDetectorInfo(activeDetector).label}`}
                          >
                            <span>{isActionLoading ? '⏳' : getDetectorInfo(activeDetector).icon}</span>
                            <span>{isActionLoading ? 'Memproses...' : getDetectorInfo(activeDetector).shortLabel}</span>
                          </button>

                          <button
                            type="button"
                            onClick={() => setEditingModal({ asset, photo: photoObj })}
                            style={{
                              flex: 1,
                              padding: '0.4rem 0.6rem',
                              background: '#10b981',
                              color: '#ffffff',
                              border: 'none',
                              borderRadius: '6px',
                              cursor: 'pointer',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              gap: '0.35rem',
                              boxShadow: '0 2px 6px rgba(16, 185, 129, 0.3)'
                            }}
                          >
                            <span>⚙️</span>
                            <span>Edit Timemark</span>
                          </button>

                          {photoObj.hasBackup && (
                            <button
                              type="button"
                              onClick={() => handleRevert(asset.relDir, photoName)}
                              style={{
                                padding: '0.4rem 0.6rem',
                                background: 'rgba(234, 179, 8, 0.2)',
                                color: '#facc15',
                                border: '1px solid #eab308',
                                borderRadius: '6px',
                                cursor: 'pointer',
                                fontSize: '0.75rem',
                                fontWeight: 600
                              }}
                              title="Kembalikan foto ini ke versi sebelum diganti"
                            >
                              ↩️ Asli
                            </button>
                          )}

                          {viewMode !== 'dual' && photoObj.isCollage && (
                            <>
                              <button
                                type="button"
                                onClick={() => handleCropCollageSingle(targetKey)}
                                disabled={isActionLoading}
                                style={{
                                  padding: '0.4rem 0.6rem',
                                  background: photoObj.hasTemp ? 'rgba(34, 197, 94, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                                  color: photoObj.hasTemp ? '#4ade80' : '#fbbf24',
                                  border: photoObj.hasTemp ? '1px solid #22c55e' : '1px solid #f59e0b',
                                  borderRadius: '6px',
                                  cursor: isActionLoading ? 'not-allowed' : 'pointer',
                                  fontSize: '0.75rem',
                                  fontWeight: 600,
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '0.25rem'
                                }}
                                title={photoObj.hasTemp ? "Klik untuk ganti kuadran potong (Kiri-Atas ➔ Kanan-Atas ➔ Kiri-Bawah ➔ Kanan-Bawah ➔ Utuh)" : "Potong otomatis foto kolase ini (auto-crop 300x300)"}
                              >
                                <span>✂️</span>
                                <span>{isActionLoading ? '...' : (photoObj.hasTemp ? 'Potong Ulang' : 'Potong Kolase')}</span>
                              </button>
                              {photoObj.hasTemp && (
                                <button
                                  type="button"
                                  onClick={() => handleCropCollageSingle(targetKey, 'ORIGINAL')}
                                  disabled={isActionLoading}
                                  style={{
                                    padding: '0.4rem 0.6rem',
                                    background: 'rgba(239, 68, 68, 0.18)',
                                    color: '#f87171',
                                    border: '1px solid #ef4444',
                                    borderRadius: '6px',
                                    cursor: isActionLoading ? 'not-allowed' : 'pointer',
                                    fontSize: '0.75rem',
                                    fontWeight: 600,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.25rem'
                                  }}
                                  title="Kembalikan ke foto utuh (batal potong kolase) dan perbarui timemark"
                                >
                                  <span>↩️</span>
                                  <span>Utuh</span>
                                </button>
                              )}
                            </>
                          )}

                          {viewMode !== 'dual' && (
                            <button
                              type="button"
                              onClick={() => {
                                const isRaw = viewMode === 'raw';
                                const coord = photoCoordsMap[targetKey] || photoCoordsMap[targetKey.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')] || {};
                                const x = coord.x ?? photoObj?.meta?.xPos ?? 14;
                                const y = coord.y ?? photoObj?.meta?.yPos ?? 220;
                                const dt = photoObj?.meta?.dateText || (
                                  photoName === '50.jpg' ? helperCalculateDate(asset.dateText, '50') :
                                  photoName === '100.jpg' ? helperCalculateDate(asset.dateText, '100') :
                                  asset.dateText || ''
                                );
                                const cleanTarget = (photoObj?.hasClean && photoObj?.cleanUrl) ? photoObj.cleanUrl : null;
                                const targetZoom = isRaw
                                  ? ((photoObj.hasTemp && photoObj.tempUrl) || photoObj.rawUrl)
                                  : (cleanTarget || editedPhotoUrl || photoObj.editedUrl);
                                if (targetZoom) {
                                  setZoomPhoto({
                                    url: targetZoom,
                                    title: `${asset.detail} - Foto ${labelPercent} (${isRaw ? (photoObj.hasTemp ? 'Mentah Terpotong' : 'Mentah 03') : 'Editan 04'})`,
                                    dateText: (!isRaw && cleanTarget) ? dt : null,
                                    xPos: x,
                                    yPos: y
                                  });
                                }
                              }}
                              disabled={!(viewMode === 'raw' ? photoObj.rawUrl : photoObj.editedUrl)}
                              style={{
                                padding: '0.4rem 0.6rem',
                                background: 'var(--bg-card)',
                                color: 'var(--text-secondary)',
                                border: '1px solid var(--border-color)',
                                borderRadius: '6px',
                                cursor: !(viewMode === 'raw' ? photoObj.rawUrl : photoObj.editedUrl) ? 'not-allowed' : 'pointer',
                                fontSize: '0.75rem',
                                fontWeight: 600,
                                opacity: !(viewMode === 'raw' ? photoObj.rawUrl : photoObj.editedUrl) ? 0.4 : 1
                              }}
                              title="Perbesar Pratinjau Foto"
                            >
                              🔍
                            </button>
                          )}
                        </div>
                      )}

                    </div>
                  );
                })}
              </div>

            </div>
          );
        })}
      </div>

      {/* ── Zoom Preview Modal ── */}
      {zoomPhoto && (
        <div
          onClick={() => setZoomPhoto(null)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.85)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 99999,
            padding: '2rem'
          }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              position: 'relative',
              maxWidth: '90vw',
              maxHeight: '90vh',
              background: '#0a0f1d',
              border: '1px solid var(--border-color)',
              borderRadius: '12px',
              padding: '1rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem',
              boxShadow: '0 20px 50px rgba(0,0,0,0.6)'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong style={{ fontSize: '1rem', color: 'var(--text-primary)' }}>{zoomPhoto.title}</strong>
              <button
                onClick={() => setZoomPhoto(null)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', fontSize: '1.25rem', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>
            <div style={{ maxWidth: '85vw', maxHeight: '80vh', overflow: 'auto', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div style={{ position: 'relative', display: 'inline-block' }}>
                <img
                  src={zoomPhoto.url}
                  alt={zoomPhoto.title}
                  style={{ maxWidth: '100%', maxHeight: '78vh', objectFit: 'contain', borderRadius: '6px', display: 'block' }}
                />
                {zoomPhoto.dateText && (
                  <div
                    style={{
                      position: 'absolute',
                      top: `${((zoomPhoto.yPos ?? 220) / 300) * 100}%`,
                      left: `${((zoomPhoto.xPos ?? 14) / 300) * 100}%`,
                      fontFamily: '"Roboto", "Segoe UI", -apple-system, BlinkMacSystemFont, sans-serif',
                      fontWeight: 700,
                      color: '#f8f8f8',
                      fontSize: 'clamp(14px, 1.8vw, 24px)',
                      lineHeight: 1.15,
                      textShadow: '0 1px 2px rgba(0, 0, 0, 0.95), 0 0 1.5px #000, 0 0 1px #000',
                      pointerEvents: 'none',
                      whiteSpace: 'nowrap',
                      userSelect: 'none'
                    }}
                  >
                    {zoomPhoto.dateText}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Timemark Editor Modal Interaktif ── */}
      {editingModal && (
        <TimemarkEditorModal
          isOpen={Boolean(editingModal)}
          onClose={() => setEditingModal(null)}
          asset={editingModal.asset}
          photo={editingModal.photo}
          exportDir={exportDir}
          defaultDetector={activeDetector}
          lastTimemarkPos={lastTimemarkPos}
          onPosChange={updateLastTimemarkPos}
          onSaved={(info) => {
            if (info?.targetKey && !info.applyToFolder) {
              refreshSinglePhotoCard(info.targetKey, info);
            } else {
              fetchPhotos();
            }
          }}
        />
      )}

      {/* ── Modal Edit Tanggal Baris Aset (3 Foto Sekaligus: 0%, 50%, 100%) ── */}
      {editingRowDateAsset && (
        <RowDateEditorModal
          isOpen={Boolean(editingRowDateAsset)}
          onClose={() => setEditingRowDateAsset(null)}
          asset={editingRowDateAsset}
          exportDir={exportDir}
          onSaved={handleRowDateSaved}
        />
      )}

    </div>
  );
}
