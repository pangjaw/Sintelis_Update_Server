import { useState, useEffect, useMemo, useRef } from 'react';
import { MASTER_CATEGORIES, CATEGORY_LABEL_MAP, normalizeCategory } from '../../utils/masterAssets';

const DAYS_ID = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu'];
const MONTHS_ID = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];

function formatDateIndo(dateStr) {
  if (!dateStr) return '';
  const parts = dateStr.split('-');
  if (parts.length !== 3) return dateStr;
  const [year, month, day] = parts.map(Number);
  if (!year || !month || !day) return dateStr;
  const dt = new Date(year, month - 1, day);
  const dayName = DAYS_ID[dt.getDay()] || 'Senin';
  const monthName = MONTHS_ID[month - 1] || 'Jan';
  const padDay = String(day).padStart(2, '0');
  return `${dayName}, ${monthName} ${padDay} ${year}`;
}

// =============================================================================
// Modal Editor Timemark Interaktif (Draggable Box & Presisi Slider)
// =============================================================================
function BatchTimemarkEditorModal({
  isOpen,
  onClose,
  asset,
  photo,
  sourceDir,
  targetDir,
  batchDateText,
  defaultDetector = 'paddle_ocr',
  onSaved
}) {
  if (!isOpen || !asset || !photo) return null;

  const metaX = photo.outputMeta?.xPos ?? photo.meta?.xPos;
  const metaY = photo.outputMeta?.yPos ?? photo.meta?.yPos;
  const initialX = (metaX !== undefined && metaX !== null && !isNaN(Number(metaX))) ? Number(metaX) : 14;
  const initialY = (metaY !== undefined && metaY !== null && !isNaN(Number(metaY))) ? Number(metaY) : 220;
  const initialDate = photo.outputMeta?.dateText || photo.meta?.dateText || batchDateText || asset.targetDateText || asset.dateText || '';

  const [xPos, setXPos] = useState(initialX);
  const [yPos, setYPos] = useState(initialY);
  const [dateText, setDateText] = useState(initialDate);
  const [detector, setDetector] = useState(photo.outputMeta?.detector || defaultDetector || 'google_vision');
  const [applyToFolder, setApplyToFolder] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // Pratinjau gambar: prioritaskan foto output jika ada, atau foto sumber asli
  const photoUrl = photo.outputUrl || photo.url || photo.rawUrl;

  // Handler Pointer Dragging untuk Kotak Watermark Interaktif pada Canvas
  const handlePointerDown = (e) => {
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

    setIsDragging(true);

    const onPointerMove = (ev) => {
      ev.preventDefault();
      const dx = ev.clientX - startPointerX;
      const dy = ev.clientY - startPointerY;
      const maxLeft = containerEl.clientWidth - boxEl.offsetWidth;
      const maxTop = containerEl.clientHeight - boxEl.offsetHeight;
      const newLeft = Math.max(0, Math.min(maxLeft, startLeft + dx));
      const newTop = Math.max(0, Math.min(maxTop, startTop + dy));

      const normX = Math.min(280, Math.max(0, Math.round((newLeft / containerEl.clientWidth) * 300)));
      const normY = Math.min(280, Math.max(0, Math.round((newTop / containerEl.clientHeight) * 300)));
      setXPos(normX);
      setYPos(normY);
    };

    const onPointerUp = () => {
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
      window.removeEventListener('pointercancel', onPointerUp);
      setIsDragging(false);
    };

    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
    window.addEventListener('pointercancel', onPointerUp);
  };

  const handleSave = async () => {
    if (!dateText.trim()) {
      setErrorMsg('Teks tanggal watermark tidak boleh kosong!');
      return;
    }
    if (!targetDir) {
      setErrorMsg('Folder tujuan penyimpanan belum ditentukan!');
      return;
    }

    setSaving(true);
    setErrorMsg('');
    setSuccessMsg('');

    try {
      const payload = {
        sourceDir,
        targetDir,
        rawRelPath: `${asset.relDir}/${photo.name}`,
        cleanRel: asset.cleanRel || asset.relDir,
        dateText: dateText.trim(),
        xPos: Number(xPos),
        yPos: Number(yPos),
        detector,
        applyToFolder
      };

      const res = await fetch('/api/timemark/manual-edit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      if (!res.ok || !data.ok) {
        throw new Error(data.error || 'Gagal menyimpan perubahan timemark');
      }

      setSuccessMsg('✓ Timemark berhasil disimpan dan diekspor ke folder tujuan!');
      if (onSaved) {
        onSaved();
      }
      setTimeout(() => {
        onClose();
      }, 700);
    } catch (err) {
      setErrorMsg(err.message || 'Terjadi kesalahan sistem saat menyimpan');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'rgba(0, 0, 0, 0.85)',
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
          maxWidth: '920px',
          maxHeight: '92vh',
          background: 'var(--bg-card, #131b2e)',
          border: '1px solid var(--border-color, #22304d)',
          borderRadius: '12px',
          boxShadow: '0 25px 60px rgba(0,0,0,0.5)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header Modal */}
        <div style={{
          padding: '0.85rem 1.25rem',
          background: 'var(--bg-secondary)',
          borderBottom: '1px solid var(--border-color)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 800, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>✏️</span> Edit Posisi Timemark: {asset.station} / {asset.category} / {asset.detail || asset.identifier}
            </h3>
            <span style={{ fontSize: '0.725rem', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
              Foto Aktif: {photo.name} · Subfolder: {asset.relDir}
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-secondary)',
              fontSize: '1.3rem',
              cursor: 'pointer',
              padding: '0.2rem 0.5rem'
            }}
          >
            ✕
          </button>
        </div>

        {/* Body Modal (Grid: Preview Canvas Kiri vs Kontrol Kanan) */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 340px',
          gap: '1rem',
          padding: '1.25rem',
          overflowY: 'auto',
          flex: 1
        }}>
          {/* Kolom Kiri: Canvas Interaktif dengan Kotak Timemark */}
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '0.65rem',
            background: '#090d16',
            padding: '0.85rem',
            borderRadius: '8px',
            border: '1px solid var(--border-color)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <span>✥</span> Geser Kotak Timemark Menggunakan Mouse:
              </span>
              <span style={{ fontSize: '0.72rem', background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', padding: '1px 8px', borderRadius: '4px', fontWeight: 700, fontFamily: 'monospace' }}>
                X: {xPos}px · Y: {yPos}px
              </span>
            </div>

            {/* Container Foto + Overlay Draggable Watermark */}
            <div style={{
              width: '100%',
              height: '380px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: '#000000',
              borderRadius: '6px',
              overflow: 'hidden',
              position: 'relative'
            }}>
              {photoUrl ? (
                <div style={{
                  position: 'relative',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  maxWidth: '100%',
                  maxHeight: '100%'
                }}>
                  <img
                    src={photoUrl}
                    alt="Pratinjau Foto"
                    draggable={false}
                    style={{
                      maxWidth: '100%',
                      maxHeight: '380px',
                      width: 'auto',
                      height: 'auto',
                      objectFit: 'contain',
                      userSelect: 'none',
                      pointerEvents: 'none',
                      display: 'block'
                    }}
                  />

                  {/* Kotak Watermark Draggable */}
                  <div
                    draggable={false}
                    onPointerDown={handlePointerDown}
                    style={{
                      position: 'absolute',
                      top: `${(yPos / 300) * 100}%`,
                      left: `${(xPos / 300) * 100}%`,
                      width: '42%',
                      height: '7%',
                      minHeight: '20px',
                      maxHeight: '30px',
                      border: isDragging ? '2px solid #f59e0b' : '2px solid #38bdf8',
                      background: isDragging ? 'rgba(245, 158, 11, 0.65)' : 'rgba(56, 189, 248, 0.45)',
                      boxShadow: isDragging ? '0 0 16px rgba(245, 158, 11, 0.95)' : '0 0 10px rgba(56, 189, 248, 0.75)',
                      borderRadius: '4px',
                      cursor: isDragging ? 'grabbing' : 'grab',
                      zIndex: 20,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '0 8px',
                      userSelect: 'none',
                      touchAction: 'none',
                      boxSizing: 'border-box'
                    }}
                    title="✥ Klik & seret kotak ini untuk mengubah letak watermark"
                  >
                    <span style={{
                      fontSize: '9px',
                      fontWeight: 700,
                      color: '#ffffff',
                      textShadow: '0 1px 2px #000',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      pointerEvents: 'none'
                    }}>
                      {dateText || 'Watermark Baru'}
                    </span>
                    <span style={{
                      fontSize: '8px',
                      color: '#ffffff',
                      opacity: 0.9,
                      fontWeight: 700,
                      pointerEvents: 'none',
                      marginLeft: '4px'
                    }}>
                      ✥ {xPos},{yPos}
                    </span>
                  </div>
                </div>
              ) : (
                <div style={{ color: '#64748b', fontSize: '0.8rem' }}>Foto tidak tersedia</div>
              )}
            </div>

            <span style={{ fontSize: '0.7rem', color: '#94a3b8', textAlign: 'center' }}>
              💡 Petunjuk: Tarik kotak biru di atas ke posisi tulisan tanggal pada foto, atau gunakan slider koordinat di sebelah kanan.
            </span>
          </div>

          {/* Kolom Kanan: Pengaturan Presisi Koordinat, Tanggal, & Eksekusi */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            
            {/* Status Pesan */}
            {errorMsg && (
              <div style={{ padding: '0.5rem 0.75rem', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid #ef4444', borderRadius: '6px', color: '#ef4444', fontSize: '0.75rem' }}>
                {errorMsg}
              </div>
            )}
            {successMsg && (
              <div style={{ padding: '0.5rem 0.75rem', background: 'rgba(34, 197, 94, 0.15)', border: '1px solid #22c55e', borderRadius: '6px', color: '#22c55e', fontSize: '0.75rem' }}>
                {successMsg}
              </div>
            )}

            {/* Slider Koordinat Y (Vertikal) */}
            <div style={{ background: 'var(--bg-secondary)', padding: '0.65rem 0.85rem', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
                <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>
                  Posisi Vertikal (Y):
                </label>
                <span style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--accent)', fontFamily: 'monospace' }}>
                  {yPos} px
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="280"
                value={yPos}
                onChange={e => setYPos(Number(e.target.value))}
                style={{ width: '100%', cursor: 'pointer' }}
              />
              <div style={{ display: 'flex', gap: '0.3rem', marginTop: '0.35rem' }}>
                <button type="button" onClick={() => setYPos(p => Math.max(0, p - 10))} style={stepperBtnStyle}>-10</button>
                <button type="button" onClick={() => setYPos(p => Math.max(0, p - 1))} style={stepperBtnStyle}>-1</button>
                <button type="button" onClick={() => setYPos(p => Math.min(280, p + 1))} style={stepperBtnStyle}>+1</button>
                <button type="button" onClick={() => setYPos(p => Math.min(280, p + 10))} style={stepperBtnStyle}>+10</button>
              </div>
            </div>

            {/* Slider Koordinat X (Horizontal) */}
            <div style={{ background: 'var(--bg-secondary)', padding: '0.65rem 0.85rem', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
                <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>
                  Posisi Horizontal (X):
                </label>
                <span style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--accent)', fontFamily: 'monospace' }}>
                  {xPos} px
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="280"
                value={xPos}
                onChange={e => setXPos(Number(e.target.value))}
                style={{ width: '100%', cursor: 'pointer' }}
              />
              <div style={{ display: 'flex', gap: '0.3rem', marginTop: '0.35rem' }}>
                <button type="button" onClick={() => setXPos(p => Math.max(0, p - 10))} style={stepperBtnStyle}>-10</button>
                <button type="button" onClick={() => setXPos(p => Math.max(0, p - 1))} style={stepperBtnStyle}>-1</button>
                <button type="button" onClick={() => setXPos(p => Math.min(280, p + 1))} style={stepperBtnStyle}>+1</button>
                <button type="button" onClick={() => setXPos(p => Math.min(280, p + 10))} style={stepperBtnStyle}>+10</button>
              </div>
            </div>

            {/* Input Tanggal Watermark */}
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
                Teks Watermark:
              </label>
              <input
                type="text"
                value={dateText}
                onChange={e => setDateText(e.target.value)}
                placeholder="Misal: Selasa, Okt 20 2026"
                style={{
                  width: '100%',
                  padding: '0.45rem 0.65rem',
                  fontSize: '0.8rem',
                  background: 'var(--bg-secondary)',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '4px'
                }}
              />
            </div>

            {/* Mesin Detektor Watermark */}
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
                Metode Mesin Detektor:
              </label>
              <select
                value={detector}
                onChange={e => setDetector(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.4rem 0.6rem',
                  fontSize: '0.775rem',
                  background: 'var(--bg-secondary)',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '4px'
                }}
              >
                <option value="paddle_ocr">LaMa AI (Hapus Teks)</option>
                <option value="google_vision">Google Vision AI (Inpainting Bersih)</option>
                <option value="guide">Metode Garis Panduan (Guide HSV)</option>
              </select>
            </div>

            {/* Opsi Terapkan ke Seluruh Foto dalam Aset */}
            <div style={{
              background: 'rgba(59, 130, 246, 0.08)',
              padding: '0.65rem 0.85rem',
              borderRadius: '6px',
              border: '1px solid rgba(59, 130, 246, 0.25)'
            }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.775rem', color: 'var(--text-primary)', fontWeight: 600 }}>
                <input
                  type="checkbox"
                  checked={applyToFolder}
                  onChange={e => setApplyToFolder(e.target.checked)}
                  style={{ width: '15px', height: '15px', cursor: 'pointer' }}
                />
                Terapkan ke semua foto aset (0%, 50%, 100%)
              </label>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', display: 'block', marginTop: '0.2rem' }}>
                Semua foto dalam folder aset ini akan menggunakan koordinat Y yang seragam.
              </span>
            </div>

            {/* Tombol Simpan & Terapkan */}
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              style={{
                marginTop: 'auto',
                padding: '0.75rem',
                background: saving ? 'var(--bg-secondary)' : '#059669',
                color: '#ffffff',
                border: 'none',
                borderRadius: '6px',
                fontWeight: 700,
                fontSize: '0.85rem',
                cursor: saving ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem',
                boxShadow: '0 2px 8px rgba(5, 150, 105, 0.35)'
              }}
            >
              <span>{saving ? '⏳' : '💾'}</span>
              <span>{saving ? 'Menyimpan...' : 'Simpan & Ekspor Foto Baru'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

const stepperBtnStyle = {
  flex: 1,
  padding: '0.2rem 0.3rem',
  fontSize: '0.7rem',
  background: 'var(--bg-primary)',
  color: 'var(--text-primary)',
  border: '1px solid var(--border-color)',
  borderRadius: '3px',
  cursor: 'pointer'
};


// =============================================================================
// Komponen Geser Posisi Timemark Langsung pada Thumbnail Kartu Foto (Draggable Box)
// =============================================================================
function InlineTimemarkBox({
  asset,
  photo,
  photoName,
  targetKey,
  localCoord,
  sourceDir,
  targetDir,
  activeDetector = 'paddle_ocr',
  lastTimemarkPos,
  onPosChange,
  onSaved,
  onOpenModal
}) {
  const boxRef = useRef(null);
  const meta = photo?.outputMeta || photo?.meta || {};
  const isValidCoord = (n) => typeof n === 'number' && !isNaN(n) && n >= 0 && n <= 295;

  const validMetaX = (meta.xPos !== undefined && meta.xPos !== null) ? Number(meta.xPos) : null;
  const validMetaY = (meta.yPos !== undefined && meta.yPos !== null) ? Number(meta.yPos) : null;

  const initialX = isValidCoord(localCoord?.x) ? localCoord.x : (isValidCoord(validMetaX) ? validMetaX : 14);
  const initialY = isValidCoord(localCoord?.y) ? localCoord.y : (isValidCoord(validMetaY) ? validMetaY : 220);

  const [pos, setPos] = useState({ x: initialX, y: initialY });
  const [dragging, setDragging] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);

  useEffect(() => {
    if (isValidCoord(localCoord?.x) && isValidCoord(localCoord?.y)) {
      setPos({ x: localCoord.x, y: localCoord.y });
    } else {
      const curMeta = photo?.outputMeta || photo?.meta || {};
      const curX = (curMeta.xPos !== undefined && curMeta.xPos !== null) ? Number(curMeta.xPos) : null;
      const curY = (curMeta.yPos !== undefined && curMeta.yPos !== null) ? Number(curMeta.yPos) : null;
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
  }, [localCoord?.x, localCoord?.y, localCoord?.ts, photo?.outputMeta?.xPos, photo?.outputMeta?.yPos, photo?.meta?.xPos, photo?.meta?.yPos]);

  const handlePointerDown = (e) => {
    if (e.button !== 0 && e.pointerType === 'mouse') return;
    e.stopPropagation();
    e.preventDefault();

    const boxEl = boxRef.current || e.currentTarget;
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
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
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

      setPos({ x: lastNormX, y: lastNormY });
      if (boxRef.current) {
        boxRef.current.style.left = `${(lastNormX / 300) * 100}%`;
        boxRef.current.style.top = `${(lastNormY / 300) * 100}%`;
      }
      if (onPosChange) {
        onPosChange(targetKey, { x: lastNormX, y: lastNormY });
      }

      const dateText = meta.dateText || asset.targetDateText || '';
      setSaving(true);
      try {
        const rawRelPath = targetKey || `${asset.relDir}/${photoName}`;
        const res = await fetch('/api/timemark/manual-edit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            sourceDir,
            targetDir,
            rawRelPath,
            cleanRel: asset.cleanRel || asset.relDir,
            dateText,
            yPos: lastNormY,
            xPos: lastNormX,
            applyToFolder: false,
            detector: activeDetector
          })
        });
        const data = await res.json();
        if (res.ok && data.ok) {
          setSavedFlash(true);
          setTimeout(() => setSavedFlash(false), 1200);
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

  const displayText = meta.dateText || asset.targetDateText || 'Terupdate';

  return (
    <div
      ref={boxRef}
      className="inline-timemark-box"
      draggable={false}
      onDragStart={(e) => { e.preventDefault(); e.stopPropagation(); }}
      onPointerDown={handlePointerDown}
      title="Tahan dan geser untuk memindahkan posisi timemark di foto, atau klik untuk edit presisi"
      style={{
        position: 'absolute',
        top: `${(pos.y / 300) * 100}%`,
        left: `${(pos.x / 300) * 100}%`,
        width: '42%',
        height: '5.3%',
        minHeight: '13px',
        maxHeight: '22px',
        border: dragging ? '1.5px solid #f0883e' : saving ? '1.5px solid #eab308' : savedFlash ? '1.5px solid #22c55e' : '1.5px solid #10b981',
        background: dragging ? 'rgba(240, 136, 62, 0.65)' : saving ? 'rgba(234, 179, 8, 0.65)' : savedFlash ? 'rgba(34, 197, 94, 0.75)' : 'rgba(16, 185, 129, 0.45)',
        boxShadow: dragging ? '0 0 10px rgba(240, 136, 62, 0.95)' : savedFlash ? '0 0 10px rgba(34, 197, 94, 0.95)' : '0 0 6px rgba(16, 185, 129, 0.6)',
        color: '#ffffff',
        padding: '0 6px',
        borderRadius: '3px',
        cursor: dragging ? 'grabbing' : 'grab',
        zIndex: 25,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'flex-start',
        userSelect: 'none',
        touchAction: 'none',
        boxSizing: 'border-box',
        overflow: 'hidden'
      }}
    >
      <span style={{
        fontSize: '7.5px',
        fontWeight: 800,
        color: '#ffffff',
        textShadow: '0 1px 2px #000',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        pointerEvents: 'none',
        lineHeight: 1
      }}>
        {saving ? '⏳ Menyimpan...' : displayText}
      </span>
    </div>
  );
}

// Komponen Utama: BatchDateEditorPanel (Format Kartu 3x2)
// =============================================================================
export default function BatchDateEditorPanel({ defaultSourceDir = '' }) {
  // Folder states
  const [sourceDir, setSourceDir] = useState(defaultSourceDir || '');
  const [targetDir, setTargetDir] = useState('');

  // Assets and gallery data
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState(null);

  // Selection state
  const [selectedFolderRels, setSelectedFolderRels] = useState(new Set());

  // Date input state (Without Time)
  const todayStr = new Date().toISOString().split('T')[0];
  const [inputDate, setInputDate] = useState(todayStr);
  const [dateText, setDateText] = useState(() => formatDateIndo(todayStr));
  const [detector, setDetector] = useState('paddle_ocr'); // 'google_vision' | 'guide'

  // Filter states
  const [selectedStation, setSelectedStation] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  // UI View Size & Fullscreen Preview & Interactive Modal
  const [cardSize, setCardSize] = useState('besar'); // 'standar' (220px) | 'besar' (300px) | 'ekstra' (380px)
  const [previewPhoto, setPreviewPhoto] = useState(null); // { url, name, title }
  const [editingModal, setEditingModal] = useState(null); // { asset, photo }

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

  // Sticky Preserved Coordinates across cards (Hanya simpan jika koordinat valid di pojok kiri bawah)
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
    } catch {
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
    } catch {}
  };

  // Processing state
  const [processing, setProcessing] = useState(false);
  const [progressMsg, setProgressMsg] = useState('');

  // Update dateText when inputDate changes
  const handleDateInputChange = (e) => {
    const val = e.target.value;
    setInputDate(val);
    setDateText(formatDateIndo(val));
  };

  // Sync default target folder when sourceDir changes (Sesuai struktur Folder 3, tanpa folder Tim)
  useEffect(() => {
    if (sourceDir && !targetDir) {
      const baseRoot = sourceDir.replace(/[\\/](03_export_foto|03_photos_export|04_photos_edited|04_foto_edited).*$/i, '');
      setTargetDir(baseRoot + '\\03_export_foto_updated');
    }
  }, [sourceDir]);

  // Pick folder dialog helper
  const handlePickFolder = async (setter, isSource = false) => {
    try {
      const res = await fetch('/api/select-folder', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        const chosen = data.path || data.folder;
        if (chosen) {
          setter(chosen);
          if (isSource) {
            fetchPhotos(chosen, targetDir);
          } else {
            fetchPhotos(sourceDir, chosen);
          }
        }
      }
    } catch (err) {
      setFeedback({ type: 'error', text: 'Gagal membuka dialog folder: ' + err.message });
    }
  };

  // Fetch photos from sourceDir with deep=1 and targetFolder parameter
  const fetchPhotos = async (dirToFetch, targetDirToFetch) => {
    const dir = dirToFetch !== undefined ? dirToFetch : sourceDir;
    const tDir = targetDirToFetch !== undefined ? targetDirToFetch : targetDir;

    if (!dir || !dir.trim()) {
      setFeedback({ type: 'error', text: 'Harap masukkan jalur folder sumber foto.' });
      return;
    }
    setLoading(true);
    setFeedback(null);
    try {
      const targetParam = tDir ? `&targetFolder=${encodeURIComponent(tDir.trim())}` : '';
      const res = await fetch(`/api/timemark/photos?folder=${encodeURIComponent(dir.trim())}&deep=1${targetParam}`);
      if (res.ok) {
        const data = await res.json();
        if (data.resolvedPath && data.resolvedPath !== dir) {
          setSourceDir(data.resolvedPath);
        }
        const assetList = data.assets || [];
        setAssets(assetList);
        setCurrentPage(1);
        if (assetList.length === 0) {
          setFeedback({
            type: 'error',
            text: data.message || `Tidak ditemukan folder aset foto di dalam: ${data.resolvedPath || dir}`
          });
        } else {
          setFeedback({
            type: 'success',
            text: data.message || `Berhasil memindai ${assetList.length} folder aset foto.`
          });
        }
      } else {
        setFeedback({ type: 'error', text: 'Gagal membaca berkas foto dari folder sumber.' });
      }
    } catch (err) {
      setFeedback({ type: 'error', text: 'Koneksi gagal: ' + err.message });
    } finally {
      setLoading(false);
    }
  };

  // Pindai awal saat inisialisasi jika defaultSourceDir tersedia
  useEffect(() => {
    if (defaultSourceDir) {
      fetchPhotos(defaultSourceDir, targetDir);
    }
  }, []);

  // Unique lists for filters
  const uniqueStations = useMemo(() => {
    const s = new Set();
    assets.forEach(a => { if (a.station) s.add(a.station); });
    return Array.from(s).sort();
  }, [assets]);

  const uniqueCategories = useMemo(() => {
    const cMap = new Map();
    MASTER_CATEGORIES.forEach(c => {
      cMap.set(normalizeCategory(c), CATEGORY_LABEL_MAP[c] || c);
    });
    assets.forEach(a => {
      const rawCat = a.category;
      if (rawCat && !cMap.has(normalizeCategory(rawCat))) {
        cMap.set(normalizeCategory(rawCat), rawCat);
      }
    });
    return Array.from(cMap.entries()).map(([k, label]) => ({ key: k, label }));
  }, [assets]);

  // Filtered assets
  const filteredAssets = useMemo(() => {
    return assets.filter(a => {
      if (selectedStation && a.station !== selectedStation) return false;
      if (selectedCategory && normalizeCategory(a.category) !== selectedCategory) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase().trim();
        const hay = `${a.station} ${a.category} ${a.detail || a.identifier} ${a.relDir} ${a.tim || ''}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [assets, selectedStation, selectedCategory, searchQuery]);

  // Pagination states for high-performance gallery rendering
  const [pageSize, setPageSize] = useState(15);
  const [currentPage, setCurrentPage] = useState(1);

  useEffect(() => {
    setCurrentPage(1);
  }, [selectedStation, selectedCategory, searchQuery]);

  const totalPages = Math.ceil(filteredAssets.length / (pageSize || 1)) || 1;
  const paginatedAssets = useMemo(() => {
    if (pageSize === 0) return filteredAssets;
    const start = (currentPage - 1) * pageSize;
    return filteredAssets.slice(start, start + pageSize);
  }, [filteredAssets, currentPage, pageSize]);

  // Unique identifier for selection: prefer relDir or absPath
  const getAssetKey = (a) => a.absPath || a.relDir;

  // Toggle selection for a single folder asset
  const toggleFolderSelection = (key) => {
    setSelectedFolderRels(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  // Select all currently filtered folders
  const handleSelectAllFiltered = () => {
    setSelectedFolderRels(prev => {
      const next = new Set(prev);
      filteredAssets.forEach(a => next.add(getAssetKey(a)));
      return next;
    });
  };

  // Deselect all
  const handleDeselectAll = () => {
    setSelectedFolderRels(new Set());
  };

  // Map of selected folder objects
  const selectedFoldersList = useMemo(() => {
    return assets.filter(a => selectedFolderRels.has(getAssetKey(a)));
  }, [assets, selectedFolderRels]);

  // Total count of photos across selected folders
  const totalSelectedPhotos = useMemo(() => {
    return selectedFoldersList.reduce((sum, a) => sum + (a.photos?.length || 0), 0);
  }, [selectedFoldersList]);

  // Execute Batch Update Date
  const handleExecuteBatchUpdate = async () => {
    if (!sourceDir) {
      setFeedback({ type: 'error', text: 'Harap pilih folder sumber foto terlebih dahulu.' });
      return;
    }
    if (!targetDir) {
      setFeedback({ type: 'error', text: 'Harap tentukan folder tujuan penyimpanan hasil.' });
      return;
    }
    if (!dateText) {
      setFeedback({ type: 'error', text: 'Harap tentukan tanggal baru untuk watermark.' });
      return;
    }
    if (selectedFoldersList.length === 0) {
      setFeedback({ type: 'error', text: 'Belum ada folder aset yang dicentang.' });
      return;
    }

    setProcessing(true);
    setProgressMsg(`Memproses ${selectedFoldersList.length} folder (${totalSelectedPhotos} foto)...`);
    setFeedback(null);

    try {
      const payload = {
        sourceDir,
        targetDir,
        dateText,
        detector,
        folders: selectedFoldersList.map(a => ({
          relDir: a.relDir,
          cleanRel: a.cleanRel || a.relDir,
          absPath: a.absPath,
          station: a.station,
          category: a.category,
          identifier: a.detail || a.identifier,
          tim: a.tim,
          photos: (a.photos || []).map(p => p.name)
        }))
      };

      const res = await fetch('/api/timemark/batch-update-date', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      if (res.ok && data.ok) {
        setFeedback({
          type: 'success',
          text: data.message || `Berhasil memperbarui tanggal pada ${data.processedFolders} folder!`
        });
        // Refresh foto dari source & target agar baris hasil otomatis terupdate
        fetchPhotos();
      } else {
        setFeedback({
          type: 'error',
          text: data.error || 'Gagal memproses pembaruan tanggal pada beberapa foto.'
        });
      }
    } catch (err) {
      setFeedback({ type: 'error', text: 'Terjadi kesalahan sistem: ' + err.message });
    } finally {
      setProcessing(false);
      setProgressMsg('');
    }
  };

  const sizeConfig = {
    standar: { imgHeight: '200px' },
    besar: { imgHeight: '260px' },
    ekstra: { imgHeight: '340px' }
  }[cardSize] || { imgHeight: '260px' };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', gap: '0.75rem', overflow: 'hidden' }}>
      
      {/* 1. Bar Konfigurasi Folder (Sumber & Tujuan) */}
      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        padding: '0.85rem 1rem',
        display: 'grid',
        gridTemplateColumns: '1fr 1fr auto',
        gap: '1rem',
        alignItems: 'end'
      }}>
        {/* Folder Sumber */}
        <div>
          <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
            📁 Folder Sumber Foto (Mendukung Folder 3, Folder 4 & Subfolder Bebas)*
          </label>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <input
              type="text"
              placeholder="Pilih folder sumber (misal 03_export_foto atau 04_photos_edited)..."
              value={sourceDir}
              onChange={e => setSourceDir(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') fetchPhotos(); }}
              style={{
                flex: 1,
                padding: '0.45rem 0.65rem',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-color)',
                borderRadius: '6px',
                color: 'var(--text-primary)',
                fontSize: '0.825rem'
              }}
            />
            <button
              type="button"
              onClick={() => handlePickFolder(setSourceDir, true)}
              style={{
                padding: '0.45rem 0.85rem',
                background: 'var(--accent)',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '0.8rem',
                whiteSpace: 'nowrap'
              }}
            >
              Pilih...
            </button>
          </div>
        </div>

        {/* Folder Tujuan */}
        <div>
          <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
            💾 Folder Tujuan (Format Folder 3: [BTP]/[Kategori]/[Aset]/, tanpa folder Tim)*
          </label>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <input
              type="text"
              placeholder="Pilih folder tujuan penyimpanan..."
              value={targetDir}
              onChange={e => setTargetDir(e.target.value)}
              style={{
                flex: 1,
                padding: '0.45rem 0.65rem',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-color)',
                borderRadius: '6px',
                color: 'var(--text-primary)',
                fontSize: '0.825rem'
              }}
            />
            <button
              type="button"
              onClick={() => handlePickFolder(setTargetDir, false)}
              style={{
                padding: '0.45rem 0.85rem',
                background: 'var(--accent)',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '0.8rem',
                whiteSpace: 'nowrap'
              }}
            >
              Pilih...
            </button>
          </div>
        </div>

        {/* Tombol Reload / Scan */}
        <div>
          <button
            type="button"
            onClick={() => fetchPhotos()}
            disabled={loading || !sourceDir}
            style={{
              padding: '0.5rem 1rem',
              background: loading ? 'var(--bg-secondary)' : 'var(--accent)',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              cursor: loading || !sourceDir ? 'not-allowed' : 'pointer',
              fontWeight: 600,
              fontSize: '0.825rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              height: '34px'
            }}
          >
            <span>{loading ? '⏳' : '🔄'}</span> {loading ? 'Memindai...' : 'Scan Subfolder'}
          </button>
        </div>
      </div>

      {/* Feedback Alert */}
      {feedback && (
        <div style={{
          padding: '0.65rem 1rem',
          borderRadius: '6px',
          fontSize: '0.85rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: feedback.type === 'error' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(34, 197, 94, 0.15)',
          color: feedback.type === 'error' ? '#ef4444' : '#22c55e',
          border: `1px solid ${feedback.type === 'error' ? '#ef4444' : '#22c55e'}`
        }}>
          <span>{feedback.text}</span>
          <button
            type="button"
            onClick={() => setFeedback(null)}
            style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontWeight: 'bold' }}
          >
            ✕
          </button>
        </div>
      )}

      {/* 2. Main Content Split: Left (Gallery with 3x2 Folder Cards) vs Right (Execution Side Panel) */}
      <div style={{ display: 'flex', gap: '1rem', flex: 1, minHeight: 0, overflow: 'hidden' }}>
        
        {/* KOLOM KIRI: Galeri Folder Aset 3x2 (72% - 75%) */}
        <div style={{
          flex: '1 1 70%',
          display: 'flex',
          flexDirection: 'column',
          background: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          borderRadius: '8px',
          overflow: 'hidden'
        }}>
          
          {/* Toolbar Filter & Batch Select */}
          <div style={{
            padding: '0.65rem 0.85rem',
            background: 'var(--bg-secondary)',
            borderBottom: '1px solid var(--border-color)',
            display: 'flex',
            flexWrap: 'wrap',
            gap: '0.5rem',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Filter:</span>
              
              {/* Stasiun Dropdown */}
              <select
                value={selectedStation}
                onChange={e => setSelectedStation(e.target.value)}
                style={{
                  padding: '0.35rem 0.6rem',
                  fontSize: '0.8rem',
                  background: 'var(--bg-primary)',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '4px'
                }}
              >
                <option value="">Semua Stasiun</option>
                {uniqueStations.map(stn => (
                  <option key={stn} value={stn}>{stn}</option>
                ))}
              </select>

              {/* Kategori Dropdown */}
              <select
                value={selectedCategory}
                onChange={e => setSelectedCategory(e.target.value)}
                style={{
                  padding: '0.35rem 0.6rem',
                  fontSize: '0.8rem',
                  background: 'var(--bg-primary)',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '4px'
                }}
              >
                <option value="">Semua Kategori</option>
                {uniqueCategories.map(cat => (
                  <option key={cat.key} value={cat.key}>{cat.label}</option>
                ))}
              </select>

              {/* Search Query */}
              <input
                type="text"
                placeholder="Cari aset / subfolder..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                style={{
                  padding: '0.35rem 0.6rem',
                  fontSize: '0.8rem',
                  background: 'var(--bg-primary)',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '4px',
                  width: '160px'
                }}
              />

              {/* Ukuran Tampilan Kartu Foto */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.2rem', background: 'var(--bg-primary)', padding: '0.15rem 0.35rem', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginRight: '0.15rem' }}>Ukuran:</span>
                <button
                  type="button"
                  onClick={() => setCardSize('standar')}
                  style={{
                    padding: '0.18rem 0.45rem',
                    fontSize: '0.72rem',
                    fontWeight: cardSize === 'standar' ? 600 : 400,
                    borderRadius: '3px',
                    border: 'none',
                    background: cardSize === 'standar' ? 'var(--accent)' : 'transparent',
                    color: cardSize === 'standar' ? '#fff' : 'var(--text-secondary)',
                    cursor: 'pointer'
                  }}
                >
                  Standar
                </button>
                <button
                  type="button"
                  onClick={() => setCardSize('besar')}
                  style={{
                    padding: '0.18rem 0.45rem',
                    fontSize: '0.72rem',
                    fontWeight: cardSize === 'besar' ? 600 : 400,
                    borderRadius: '3px',
                    border: 'none',
                    background: cardSize === 'besar' ? 'var(--accent)' : 'transparent',
                    color: cardSize === 'besar' ? '#fff' : 'var(--text-secondary)',
                    cursor: 'pointer'
                  }}
                >
                  Besar
                </button>
                <button
                  type="button"
                  onClick={() => setCardSize('ekstra')}
                  style={{
                    padding: '0.18rem 0.45rem',
                    fontSize: '0.72rem',
                    fontWeight: cardSize === 'ekstra' ? 600 : 400,
                    borderRadius: '3px',
                    border: 'none',
                    background: cardSize === 'ekstra' ? 'var(--accent)' : 'transparent',
                    color: cardSize === 'ekstra' ? '#fff' : 'var(--text-secondary)',
                    cursor: 'pointer'
                  }}
                >
                  Ekstra
                </button>
              </div>
            </div>

            {/* Tombol Centang Semua & Batal */}
            <div style={{ display: 'flex', gap: '0.4rem' }}>
              <button
                type="button"
                onClick={handleSelectAllFiltered}
                style={{
                  padding: '0.35rem 0.65rem',
                  fontSize: '0.775rem',
                  fontWeight: 600,
                  background: 'var(--accent)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer'
                }}
              >
                ☑️ Centang Semua ({filteredAssets.length})
              </button>
              <button
                type="button"
                onClick={handleDeselectAll}
                disabled={selectedFolderRels.size === 0}
                style={{
                  padding: '0.35rem 0.65rem',
                  fontSize: '0.775rem',
                  background: 'var(--bg-primary)',
                  color: 'var(--text-secondary)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '4px',
                  cursor: selectedFolderRels.size === 0 ? 'not-allowed' : 'pointer'
                }}
              >
                Batal Pilihan
              </button>
            </div>
          </div>

          {/* List Scrollable Folder Aset (Layout 3x2) */}
          <div style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            padding: '0.85rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '1.25rem'
          }}>
            {loading && (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                <span>Memindai seluruh subfolder foto secara mendalam (Folder 3 & Folder 4)...</span>
              </div>
            )}

            {!loading && filteredAssets.length === 0 && (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                {assets.length === 0
                  ? 'Belum ada foto yang terdeteksi. Silakan pilih folder sumber yang memuat folder 03_export_foto, 04_photos_edited, atau subfolder foto lainnya.'
                  : 'Tidak ada folder aset yang cocok dengan filter pencarian.'}
              </div>
            )}

            {/* Pagination & Summary Bar */}
            {!loading && filteredAssets.length > 0 && (
              <div style={{
                flexShrink: 0,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '0.5rem 0.75rem',
                background: 'rgba(0,0,0,0.2)',
                borderRadius: '6px',
                fontSize: '0.8rem',
                color: 'var(--text-secondary)',
                border: '1px solid var(--border-color)'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <span>
                    Menampilkan <strong style={{ color: 'var(--text-primary)' }}>{paginatedAssets.length}</strong> dari <strong style={{ color: 'var(--text-primary)' }}>{filteredAssets.length}</strong> folder aset
                  </span>
                  <select
                    value={pageSize}
                    onChange={e => { setPageSize(Number(e.target.value)); setCurrentPage(1); }}
                    style={{
                      padding: '0.2rem 0.4rem',
                      fontSize: '0.75rem',
                      background: 'var(--bg-primary)',
                      color: 'var(--text-primary)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '4px'
                    }}
                  >
                    <option value={15}>15 per hal</option>
                    <option value={30}>30 per hal</option>
                    <option value={50}>50 per hal</option>
                    <option value={100}>100 per hal</option>
                  </select>
                </div>
                {totalPages > 1 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <button
                      type="button"
                      onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                      disabled={currentPage === 1}
                      style={{
                        padding: '0.25rem 0.6rem',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        background: 'var(--bg-secondary)',
                        color: 'var(--text-primary)',
                        border: '1px solid var(--border-color)',
                        borderRadius: '4px',
                        cursor: currentPage === 1 ? 'not-allowed' : 'pointer'
                      }}
                    >
                      ◀ Sebelumnya
                    </button>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)', padding: '0 0.3rem' }}>
                      Hal {currentPage} / {totalPages}
                    </span>
                    <button
                      type="button"
                      onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                      disabled={currentPage === totalPages}
                      style={{
                        padding: '0.25rem 0.6rem',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        background: 'var(--bg-secondary)',
                        color: 'var(--text-primary)',
                        border: '1px solid var(--border-color)',
                        borderRadius: '4px',
                        cursor: currentPage === totalPages ? 'not-allowed' : 'pointer'
                      }}
                    >
                      Selanjutnya ▶
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* List Kartu Aset Berformat 3x2 (Baris 1 Input, Baris 2 Output) */}
            {!loading && paginatedAssets.map(asset => {
              const aKey = getAssetKey(asset);
              const isChecked = selectedFolderRels.has(aKey);
              const photos = asset.photos || [];
              const outputCount = photos.filter(p => p.hasOutput).length;
              const hasAllOutput = photos.length > 0 && outputCount === photos.length;

              return (
                <div
                  key={aKey}
                  style={{
                    flexShrink: 0,
                    width: '100%',
                    background: isChecked ? 'rgba(59, 130, 246, 0.08)' : 'var(--bg-secondary)',
                    border: `1.5px solid ${isChecked ? 'var(--accent)' : 'var(--border-color)'}`,
                    borderRadius: '10px',
                    overflow: 'hidden',
                    transition: 'all 0.15s ease',
                    boxShadow: '0 3px 12px rgba(0,0,0,0.18)'
                  }}
                >
                  {/* Header Kartu Aset dengan Checkbox & Tombol Edit Timemark */}
                  <div
                    style={{
                      padding: '0.75rem 1rem',
                      background: isChecked ? 'rgba(59, 130, 246, 0.18)' : 'rgba(0, 0, 0, 0.22)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      borderBottom: '1px solid var(--border-color)',
                      gap: '0.75rem'
                    }}
                  >
                    <div
                      onClick={() => toggleFolderSelection(aKey)}
                      style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', cursor: 'pointer', flex: 1 }}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => {}} // handled by parent onClick
                        style={{ width: '18px', height: '18px', cursor: 'pointer' }}
                      />
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                          <span style={{ fontWeight: 800, fontSize: '0.9rem', color: isChecked ? 'var(--accent)' : 'var(--text-primary)' }}>
                            FOLDER ASET: {asset.station} / {asset.category} / {asset.detail || asset.identifier}
                          </span>
                          {asset.tim && (
                            <span style={{ fontSize: '0.7rem', fontWeight: 600, color: '#f59e0b', background: 'rgba(245, 158, 11, 0.15)', padding: '0.1rem 0.4rem', borderRadius: '4px' }}>
                              ⏱️ {asset.tim}
                            </span>
                          )}
                          <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', background: 'var(--bg-primary)', padding: '0.1rem 0.4rem', borderRadius: '4px' }}>
                            {photos.length} Foto Input
                          </span>
                          <span style={{
                            fontSize: '0.72rem',
                            fontWeight: 600,
                            color: hasAllOutput ? '#22c55e' : (outputCount > 0 ? '#f59e0b' : '#94a3b8'),
                            background: hasAllOutput ? 'rgba(34, 197, 94, 0.15)' : 'rgba(0,0,0,0.2)',
                            padding: '0.1rem 0.45rem',
                            borderRadius: '4px'
                          }}>
                            {outputCount} / {photos.length} Foto Output
                          </span>
                          {asset.targetDateText && (
                            <span style={{ fontSize: '0.72rem', color: '#10b981', background: 'rgba(16, 185, 129, 0.15)', padding: '0.1rem 0.45rem', borderRadius: '4px', fontWeight: 600 }}>
                              📅 {asset.targetDateText}
                            </span>
                          )}
                          {asset.hasMeta && (
                            <span style={{ fontSize: '0.72rem', color: '#38bdf8', background: 'rgba(56, 189, 248, 0.15)', border: '1px solid rgba(56, 189, 248, 0.35)', padding: '0.1rem 0.45rem', borderRadius: '4px', fontWeight: 600 }}>
                              📍 meta.json Presisi
                            </span>
                          )}
                        </div>
                        <span style={{ fontSize: '0.72rem', color: '#94a3b8', fontFamily: 'monospace' }}>
                          📁 Subfolder: {asset.relDir}
                        </span>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                      {/* Tombol Buka Modal Editor Timemark Interaktif */}
                      <button
                        type="button"
                        onClick={() => {
                          const firstPhoto = photos.find(p => p.name === '0.jpg') || photos[0];
                          if (firstPhoto) {
                            setEditingModal({ asset, photo: firstPhoto });
                          }
                        }}
                        style={{
                          padding: '0.35rem 0.75rem',
                          fontSize: '0.75rem',
                          fontWeight: 700,
                          background: 'rgba(56, 189, 248, 0.15)',
                          color: '#38bdf8',
                          border: '1px solid #38bdf8',
                          borderRadius: '6px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.35rem',
                          whiteSpace: 'nowrap'
                        }}
                        title="Buka kanvas interaktif untuk menggeser posisi watermark semua foto dalam folder aset ini"
                      >
                        <span>✏️</span> Edit Timemark Semua Foto
                      </button>

                      <span style={{
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        color: isChecked ? '#60a5fa' : 'var(--text-secondary)',
                        flexShrink: 0
                      }}>
                        {isChecked ? '✓ Tercentang' : 'Pilih'}
                      </span>
                    </div>
                  </div>

                  {/* Body Kartu 3x2: Baris 1 (Input) & Baris 2 (Output) */}
                  <div style={{ padding: '0.85rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    
                    {/* ========================================================= */}
                    {/* BARIS 1: FOTO SUMBER (INPUT / MENTAH) — SKEMA BIRU COBALT */}
                    {/* ========================================================= */}
                    <div style={{
                      background: 'linear-gradient(135deg, rgba(30, 58, 138, 0.22) 0%, rgba(15, 23, 42, 0.8) 100%)',
                      borderRadius: '8px',
                      padding: '0.75rem',
                      border: '1.5px solid rgba(59, 130, 246, 0.4)',
                      borderLeft: '5px solid #3b82f6',
                      boxShadow: 'inset 0 1px 1px rgba(255, 255, 255, 0.05)'
                    }}>
                      <div style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginBottom: '0.65rem',
                        paddingBottom: '0.45rem',
                        borderBottom: '1px solid rgba(59, 130, 246, 0.25)'
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem' }}>
                          <span style={{
                            fontSize: '0.725rem',
                            fontWeight: 800,
                            color: '#ffffff',
                            background: '#1d4ed8',
                            padding: '0.2rem 0.65rem',
                            borderRadius: '4px',
                            letterSpacing: '0.5px',
                            boxShadow: '0 2px 8px rgba(29, 78, 216, 0.4)'
                          }}>
                            📁 BARIS 1: FOTO SUMBER (INPUT / MENTAH)
                          </span>
                          <span style={{ fontSize: '0.72rem', color: '#93c5fd', fontFamily: 'monospace' }}>
                            {sourceDir}\{asset.relDir}
                          </span>
                        </div>
                        <span style={{
                          fontSize: '0.7rem',
                          color: '#60a5fa',
                          fontWeight: 700,
                          background: 'rgba(37, 99, 235, 0.15)',
                          padding: '0.15rem 0.5rem',
                          borderRadius: '4px',
                          border: '1px solid rgba(59, 130, 246, 0.3)'
                        }}>
                          {photos.length} Foto Mentah
                        </span>
                      </div>

                      {/* 3 Kolom Foto Input */}
                      <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
                        gap: '0.75rem'
                      }}>
                        {photos.map(p => {
                          const stem = p.name ? p.name.replace(/\.[^/.]+$/, '') : '';
                          const stepLabel = stem === '0' ? '0% (Mulai)' : stem === '50' ? '50% (Tengah)' : stem === '100' ? '100% (Selesai)' : p.name;
                          const rawUrl = p.url || p.rawUrl;

                          return (
                            <div
                              key={'input_' + p.name}
                              style={{
                                background: 'rgba(15, 23, 42, 0.9)',
                                border: '1px solid rgba(59, 130, 246, 0.35)',
                                borderRadius: '6px',
                                padding: '0.55rem',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '0.45rem',
                                transition: 'all 0.15s ease'
                              }}
                            >
                              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', fontWeight: 600 }}>
                                <span style={{ color: '#60a5fa', fontWeight: 700 }}>{stepLabel}</span>
                                <span style={{ fontFamily: 'monospace', color: '#93c5fd', fontSize: '0.72rem' }}>{p.name}</span>
                              </div>

                              {/* Thumbnail Box Input */}
                              <div
                                style={{
                                  width: '100%',
                                  height: sizeConfig.imgHeight,
                                  background: '#090d16',
                                  borderRadius: '4px',
                                  overflow: 'hidden',
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  position: 'relative',
                                  border: '1px solid rgba(59, 130, 246, 0.2)'
                                }}
                              >
                                {rawUrl ? (
                                  <img
                                    src={rawUrl}
                                    alt={p.name}
                                    style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                                    loading="lazy"
                                  />
                                ) : (
                                  <span style={{ fontSize: '0.75rem', color: '#64748b' }}>[ Foto {p.name} ]</span>
                                )}

                                <div style={{
                                  position: 'absolute',
                                  bottom: '6px',
                                  left: '6px',
                                  background: 'rgba(30, 58, 138, 0.85)',
                                  color: '#bfdbfe',
                                  border: '1px solid rgba(59, 130, 246, 0.4)',
                                  padding: '1px 6px',
                                  borderRadius: '3px',
                                  fontSize: '0.65rem',
                                  fontWeight: 600,
                                  boxShadow: '0 2px 4px rgba(0,0,0,0.4)'
                                }}>
                                  📷 Foto Mentah
                                </div>
                              </div>

                              {/* Action Footer Input (Murni Mentah Tanpa Geser Posisi) */}
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.7rem' }}>
                                <span
                                  onClick={() => rawUrl && setPreviewPhoto({
                                    url: rawUrl,
                                    name: p.name,
                                    title: `Foto Sumber: ${asset.station} / ${asset.category} / ${asset.detail || asset.identifier} — ${p.name} (${stepLabel})`
                                  })}
                                  style={{ color: '#60a5fa', cursor: 'pointer', fontWeight: 600 }}
                                >
                                  🔍 Perbesar Foto Mentah
                                </span>
                                <span style={{ fontSize: '0.65rem', color: '#93c5fd', opacity: 0.8 }}>
                                  [Referensi Asli]
                                </span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* ========================================================= */}
                    {/* BARIS 2: FOTO HASIL EKSPOR (OUTPUT) — SKEMA HIJAU ZAMRUD  */}
                    {/* ========================================================= */}
                    <div style={{
                      background: hasAllOutput
                        ? 'linear-gradient(135deg, rgba(6, 78, 59, 0.28) 0%, rgba(15, 23, 42, 0.8) 100%)'
                        : (outputCount > 0
                          ? 'linear-gradient(135deg, rgba(13, 148, 136, 0.22) 0%, rgba(15, 23, 42, 0.8) 100%)'
                          : 'linear-gradient(135deg, rgba(120, 53, 15, 0.2) 0%, rgba(15, 23, 42, 0.8) 100%)'),
                      borderRadius: '8px',
                      padding: '0.75rem',
                      border: hasAllOutput
                        ? '1.5px solid rgba(16, 185, 129, 0.55)'
                        : (outputCount > 0
                          ? '1.5px solid rgba(20, 184, 166, 0.5)'
                          : '1.5px dashed rgba(245, 158, 11, 0.5)'),
                      borderLeft: hasAllOutput
                        ? '5px solid #10b981'
                        : (outputCount > 0
                          ? '5px solid #14b8a6'
                          : '5px solid #f59e0b'),
                      boxShadow: 'inset 0 1px 1px rgba(255, 255, 255, 0.05)'
                    }}>
                      <div style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginBottom: '0.65rem',
                        paddingBottom: '0.45rem',
                        borderBottom: `1px solid ${hasAllOutput ? 'rgba(16, 185, 129, 0.25)' : 'rgba(245, 158, 11, 0.25)'}`
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem' }}>
                          <span style={{
                            fontSize: '0.725rem',
                            fontWeight: 800,
                            color: '#ffffff',
                            background: hasAllOutput ? '#059669' : (outputCount > 0 ? '#0d9488' : '#d97706'),
                            padding: '0.2rem 0.65rem',
                            borderRadius: '4px',
                            letterSpacing: '0.5px',
                            boxShadow: hasAllOutput
                              ? '0 2px 8px rgba(5, 150, 105, 0.4)'
                              : '0 2px 8px rgba(217, 119, 6, 0.4)'
                          }}>
                            💾 BARIS 2: FOTO HASIL EKSPOR (OUTPUT)
                          </span>
                          <span style={{
                            fontSize: '0.72rem',
                            color: hasAllOutput ? '#a7f3d0' : '#fde68a',
                            fontFamily: 'monospace'
                          }}>
                            {targetDir}\{asset.cleanRel || asset.relDir}
                          </span>
                        </div>
                        <span style={{
                          fontSize: '0.7rem',
                          fontWeight: 700,
                          color: hasAllOutput ? '#34d399' : '#fbbf24',
                          background: hasAllOutput ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                          padding: '0.15rem 0.5rem',
                          borderRadius: '4px',
                          border: `1px solid ${hasAllOutput ? 'rgba(16, 185, 129, 0.35)' : 'rgba(245, 158, 11, 0.35)'}`
                        }}>
                          {hasAllOutput ? '✅ Lengkap (3 Foto Selesai)' : `${outputCount} / ${photos.length} Foto Selesai`}
                        </span>
                      </div>

                      {/* 3 Kolom Foto Output */}
                      <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
                        gap: '0.75rem'
                      }}>
                        {photos.map(p => {
                          const stem = p.name ? p.name.replace(/\.[^/.]+$/, '') : '';
                          const stepLabel = stem === '0' ? '0% (Mulai)' : stem === '50' ? '50% (Tengah)' : stem === '100' ? '100% (Selesai)' : p.name;
                          const hasOut = p.hasOutput && p.outputUrl;

                          if (hasOut) {
                            return (
                              <div
                                key={'output_' + p.name}
                                style={{
                                  background: 'rgba(6, 44, 34, 0.55)',
                                  border: '1.5px solid rgba(16, 185, 129, 0.45)',
                                  borderRadius: '6px',
                                  padding: '0.55rem',
                                  display: 'flex',
                                  flexDirection: 'column',
                                  gap: '0.45rem',
                                  transition: 'all 0.15s ease'
                                }}
                              >
                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', fontWeight: 600 }}>
                                  <span style={{ color: '#34d399', fontWeight: 800 }}>{stepLabel}</span>
                                  <span style={{ color: '#10b981', fontSize: '0.68rem', fontWeight: 800, background: 'rgba(16, 185, 129, 0.15)', padding: '1px 6px', borderRadius: '3px' }}>
                                    ✓ Hasil Ekspor
                                  </span>
                                </div>

                                {/* Thumbnail Box Output dengan Kotak Geser Posisi Langsung */}
                                <div
                                  style={{
                                    width: '100%',
                                    height: sizeConfig.imgHeight,
                                    background: '#090d16',
                                    borderRadius: '4px',
                                    overflow: 'hidden',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    position: 'relative',
                                    border: '1px solid rgba(16, 185, 129, 0.3)'
                                  }}
                                >
                                  <div style={{
                                    position: 'relative',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    maxWidth: '100%',
                                    maxHeight: '100%',
                                    lineHeight: 0
                                  }}>
                                    <img
                                      src={`${p.outputUrl}${p.outputUrl.includes("?") ? "&" : "?"}_v=${p.outputMeta?.updatedAt ? new Date(p.outputMeta.updatedAt).getTime() : Date.now()}`}
                                      alt={'Output ' + p.name}
                                      style={{
                                        maxWidth: '100%',
                                        maxHeight: `${sizeConfig.imgHeight}px`,
                                        width: 'auto',
                                        height: 'auto',
                                        objectFit: 'contain',
                                        display: 'block'
                                      }}
                                      loading="lazy"
                                    />

                                    
                                    {/* Kotak Geser Posisi Timemark Langsung pada Foto Hasil (Baris 2 / Kartu 4) */}
                                    <InlineTimemarkBox
                                      key={`${asset.cleanRel || asset.relDir}/${p.name}`}
                                      asset={asset}
                                      photo={p}
                                      photoName={p.name}
                                      targetKey={`${asset.cleanRel || asset.relDir}/${p.name}`}
                                      localCoord={photoCoordsMap[`${asset.cleanRel || asset.relDir}/${p.name}`]}
                                      sourceDir={sourceDir}
                                      targetDir={targetDir}
                                      activeDetector={detector}
                                      lastTimemarkPos={lastTimemarkPos}
                                      onPosChange={(k, c) => {
                                        updatePhotoLocalPos(k, c);
                                        updateLastTimemarkPos(c);
                                      }}
                                      onSaved={() => fetchPhotos(sourceDir, targetDir)}
                                      onOpenModal={() => setEditingModal({ asset, photo: p })}
                                    />
                                  </div>

                                  
                                </div>

                                {/* Action Footer Output */}
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.7rem' }}>
                                  <span
                                    onClick={() => setPreviewPhoto({
                                      url: p.outputUrl,
                                      name: p.name,
                                      title: `Hasil Ekspor: ${asset.station} / ${asset.category} / ${asset.detail || asset.identifier} — ${p.name} (${stepLabel})`
                                    })}
                                    style={{ color: '#34d399', cursor: 'pointer', fontWeight: 700 }}
                                  >
                                    🔍 Perbesar
                                  </span>
                                  <button
                                    type="button"
                                    onClick={() => setEditingModal({ asset, photo: p })}
                                    style={{
                                      padding: '0.2rem 0.5rem',
                                      fontSize: '0.68rem',
                                      fontWeight: 700,
                                      background: 'rgba(34, 197, 94, 0.12)',
                                      color: '#34d399',
                                      border: '1px solid rgba(34, 197, 94, 0.4)',
                                      borderRadius: '4px',
                                      cursor: 'pointer'
                                    }}
                                    title="Edit ulang posisi timemark foto hasil"
                                  >
                                    ✏️ Edit Ulang
                                  </button>
                                </div>
                              </div>
                            );
                          }

                          // Placeholder jika foto belum diekspor ke folder tujuan
                          return (
                            <div
                              key={'output_placeholder_' + p.name}
                              style={{
                                height: '100%',
                                minHeight: sizeConfig.imgHeight,
                                background: 'rgba(245, 158, 11, 0.04)',
                                border: '1.5px dashed rgba(245, 158, 11, 0.45)',
                                borderRadius: '6px',
                                padding: '0.75rem',
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center',
                                justifyContent: 'center',
                                textAlign: 'center',
                                gap: '0.5rem'
                              }}
                            >
                              <span style={{ fontSize: '1.6rem', opacity: 0.85 }}>⏳</span>
                              <div>
                                <strong style={{ display: 'block', fontSize: '0.75rem', color: '#fbbf24' }}>
                                  {stepLabel} ({p.name})
                                </strong>
                                <span style={{ fontSize: '0.7rem', color: '#cbd5e1', display: 'block', marginTop: '0.2rem' }}>
                                  Belum diekspor ke folder tujuan
                                </span>
                              </div>
                              <button
                                type="button"
                                onClick={() => setEditingModal({ asset, photo: p })}
                                style={{
                                  marginTop: '0.35rem',
                                  padding: '0.35rem 0.75rem',
                                  fontSize: '0.72rem',
                                  fontWeight: 700,
                                  background: 'rgba(245, 158, 11, 0.15)',
                                  color: '#fbbf24',
                                  border: '1px solid rgba(245, 158, 11, 0.45)',
                                  borderRadius: '4px',
                                  cursor: 'pointer'
                                }}
                              >
                                ⚡ Edit & Ekspor Sekarang
                              </button>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* KOLOM KANAN: Panel Eksekusi & Folder Terpilih (28% - 30%) */}
        <div style={{
          flex: '0 0 320px',
          background: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          borderRadius: '8px',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}>
          {/* Header Panel */}
          <div style={{
            padding: '0.75rem 1rem',
            background: 'var(--bg-secondary)',
            borderBottom: '1px solid var(--border-color)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <h4 style={{ margin: 0, fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Panel Ubah Tanggal
            </h4>
            <span style={{
              background: 'var(--accent)',
              color: '#fff',
              fontSize: '0.75rem',
              fontWeight: 700,
              padding: '0.2rem 0.5rem',
              borderRadius: '12px'
            }}>
              {selectedFoldersList.length} Folder ({totalSelectedPhotos} Foto)
            </span>
          </div>

          {/* Form Pengaturan Tanggal & Tombol Eksekusi */}
          <div style={{ padding: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.75rem', borderBottom: '1px solid var(--border-color)' }}>
            
            {/* Box Input Tanggal */}
            <div>
              <label style={{ display: 'block', fontSize: '0.775rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                📅 TANGGAL WATERMARK BARU:
              </label>
              <input
                type="date"
                value={inputDate}
                onChange={handleDateInputChange}
                style={{
                  width: '100%',
                  padding: '0.5rem 0.65rem',
                  background: 'var(--bg-secondary)',
                  border: '1px solid var(--accent)',
                  borderRadius: '6px',
                  color: 'var(--text-primary)',
                  fontSize: '0.85rem',
                  fontWeight: 600
                }}
              />
            </div>

            {/* Preview Teks Tanggal Baku */}
            <div style={{
              background: 'rgba(59, 130, 246, 0.1)',
              border: '1px dashed var(--accent)',
              borderRadius: '6px',
              padding: '0.5rem 0.65rem'
            }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', display: 'block' }}>Format Watermark (Tanpa Jam):</span>
              <strong style={{ fontSize: '0.85rem', color: 'var(--accent)', display: 'block', marginTop: '0.15rem' }}>
                {dateText || '(Pilih tanggal)'}
              </strong>
            </div>

            {/* Pilihan Mesin Watermark */}
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
                Mesin Detektor Watermark:
              </label>
              <select
                value={detector}
                onChange={e => setDetector(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.4rem 0.6rem',
                  fontSize: '0.8rem',
                  background: 'var(--bg-secondary)',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '4px'
                }}
              >
                <option value="paddle_ocr">LaMa AI (Hapus Teks)</option>
                <option value="google_vision">Google Vision AI (Inpainting Bersih)</option>
                <option value="guide">Garis Panduan Oranye / HSV Fallback</option>
              </select>
            </div>

            {/* Big Action Button */}
            <button
              type="button"
              onClick={handleExecuteBatchUpdate}
              disabled={processing || selectedFoldersList.length === 0 || !dateText}
              style={{
                marginTop: '0.25rem',
                padding: '0.75rem 1rem',
                background: processing || selectedFoldersList.length === 0 ? 'var(--bg-secondary)' : '#059669',
                color: processing || selectedFoldersList.length === 0 ? 'var(--text-secondary)' : '#ffffff',
                border: 'none',
                borderRadius: '6px',
                cursor: processing || selectedFoldersList.length === 0 ? 'not-allowed' : 'pointer',
                fontWeight: 700,
                fontSize: '0.85rem',
                textAlign: 'center',
                boxShadow: selectedFoldersList.length > 0 ? '0 2px 8px rgba(5, 150, 105, 0.3)' : 'none',
                transition: 'all 0.15s ease'
              }}
            >
              {processing ? '⏳ Sedang Memproses...' : `⚡ TERAPKAN KE ${selectedFoldersList.length} FOLDER (${totalSelectedPhotos} FOTO)`}
            </button>

            <span style={{ fontSize: '0.72rem', color: '#10b981', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
              ✓ Output disimpan langsung mengikuti format Folder 3 (tanpa folder Tim)
            </span>
            {progressMsg && (
              <span style={{ fontSize: '0.75rem', color: 'var(--accent)', textAlign: 'center' }}>
                {progressMsg}
              </span>
            )}
          </div>

          {/* List Scrollable Folder yang Dicentang */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
              Daftar Folder yang Dicentang:
            </span>

            {selectedFoldersList.length === 0 && (
              <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                Belum ada folder yang dicentang. Centang folder aset di kolom kiri untuk memasukkannya ke daftar ini.
              </div>
            )}

            {selectedFoldersList.map(item => {
              const aKey = getAssetKey(item);
              return (
                <div
                  key={aKey}
                  style={{
                    background: 'var(--bg-secondary)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '6px',
                    padding: '0.5rem 0.65rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '0.5rem'
                  }}
                >
                  <div style={{ overflow: 'hidden' }}>
                    <strong style={{ fontSize: '0.8rem', color: 'var(--text-primary)', display: 'block', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                      {item.station} / {item.category} / {item.detail || item.identifier}
                      {item.tim ? ` (${item.tim})` : ''}
                    </strong>
                    <span style={{ fontSize: '0.7rem', color: 'var(--accent)', display: 'block' }}>
                      {item.photos?.length || 0} Foto
                    </span>
                    <span style={{ fontSize: '0.68rem', color: '#64748b', display: 'block', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                      📁 {item.relDir}
                    </span>
                  </div>

                  <button
                    type="button"
                    title="Hapus dari pilihan"
                    onClick={() => toggleFolderSelection(aKey)}
                    style={{
                      background: '#ef4444',
                      color: '#fff',
                      border: 'none',
                      borderRadius: '4px',
                      width: '22px',
                      height: '22px',
                      cursor: 'pointer',
                      fontWeight: 'bold',
                      fontSize: '0.75rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0
                    }}
                  >
                    ✕
                  </button>
                </div>
              );
            })}
          </div>

          {/* Footer of Right Panel: Clear All Selection */}
          {selectedFoldersList.length > 0 && (
            <div style={{ padding: '0.5rem 0.85rem', background: 'var(--bg-secondary)', borderTop: '1px solid var(--border-color)' }}>
              <button
                type="button"
                onClick={handleDeselectAll}
                style={{
                  width: '100%',
                  padding: '0.4rem',
                  fontSize: '0.75rem',
                  background: 'transparent',
                  color: 'var(--text-secondary)',
                  border: '1px dashed var(--border-color)',
                  borderRadius: '4px',
                  cursor: 'pointer'
                }}
              >
                Kosongkan Pilihan
              </button>
            </div>
          )}

        </div>

      </div>

      {/* Fullscreen Photo Preview Modal */}
      {previewPhoto && (
        <div
          onClick={() => setPreviewPhoto(null)}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.85)',
            backdropFilter: 'blur(4px)',
            zIndex: 9999,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1.5rem'
          }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              maxWidth: '92vw',
              maxHeight: '92vh',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-color)',
              borderRadius: '8px',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 8px 32px rgba(0,0,0,0.5)'
            }}
          >
            <div style={{ padding: '0.65rem 1rem', background: 'var(--bg-secondary)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-color)' }}>
              <strong style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>{previewPhoto.title}</strong>
              <button
                type="button"
                onClick={() => setPreviewPhoto(null)}
                style={{ background: 'none', border: 'none', color: 'var(--text-primary)', fontSize: '1.2rem', cursor: 'pointer', fontWeight: 'bold' }}
              >
                ✕
              </button>
            </div>
            <div style={{ flex: 1, overflow: 'auto', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#090d16', padding: '1rem' }}>
              <img
                src={previewPhoto.url}
                alt={previewPhoto.name}
                style={{ maxWidth: '100%', maxHeight: '80vh', objectFit: 'contain', borderRadius: '4px' }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Interactive Timemark Editor Modal */}
      {editingModal && (
        <BatchTimemarkEditorModal
          isOpen={Boolean(editingModal)}
          onClose={() => setEditingModal(null)}
          asset={editingModal.asset}
          photo={editingModal.photo}
          sourceDir={sourceDir}
          targetDir={targetDir}
          batchDateText={dateText}
          defaultDetector={detector}
          onSaved={() => {
            fetchPhotos();
          }}
        />
      )}

    </div>
  );
}
