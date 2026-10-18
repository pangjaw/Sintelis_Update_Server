import { useState, useEffect, useMemo, useRef } from 'react';
import { MASTER_CATEGORIES, CATEGORY_LABEL_MAP, normalizeCategory } from '../../utils/masterAssets';

// =============================================================================
// Helper Kalkulasi Tanggal Otomatis (0%, 50%, 100%)
// =============================================================================
function helperCalculateDate(baseDate, photoStem) {
  let cleanDate = (baseDate || '').trim();
  const m = cleanDate.match(/^(.*?\d{4})\s+(\d{2}):(\d{2})$/);
  if (!m) return cleanDate;

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

// =============================================================================
// Komponen Kotak Timemark Interaktif yang Dapat Digeser (Inline Draggable Box)
// =============================================================================
function InlineTimemarkBox({
  asset,
  photo,
  photoName,
  exportDir,
  activeDetector = 'google_vision',
  onSaved,
  onOpenModal
}) {
  const [pos, setPos] = useState({
    x: photo?.meta?.xPos ?? 14,
    y: photo?.meta?.yPos ?? 220
  });
  const [dragging, setDragging] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);

  useEffect(() => {
    setPos({
      x: photo?.meta?.xPos ?? 14,
      y: photo?.meta?.yPos ?? 220
    });
  }, [photo?.meta?.xPos, photo?.meta?.yPos]);

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
    let hasMoved = false;

    setDragging(true);

    const onPointerMove = (ev) => {
      ev.preventDefault();
      const dx = ev.clientX - startPointerX;
      const dy = ev.clientY - startPointerY;
      if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
        hasMoved = true;
      }
      const maxLeft = containerEl.clientWidth - boxEl.offsetWidth;
      const maxTop = containerEl.clientHeight - boxEl.offsetHeight;
      const newLeft = Math.max(0, Math.min(maxLeft, startLeft + dx));
      const newTop = Math.max(0, Math.min(maxTop, startTop + dy));

      boxEl.style.left = `${(newLeft / containerEl.clientWidth) * 100}%`;
      boxEl.style.top = `${(newTop / containerEl.clientHeight) * 100}%`;
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

      // Hitung koordinat ternormalisasi (0 - 300)
      const normX = Math.min(280, Math.max(0, Math.round((boxEl.offsetLeft / containerEl.clientWidth) * 300)));
      const normY = Math.min(280, Math.max(0, Math.round((boxEl.offsetTop / containerEl.clientHeight) * 300)));
      setPos({ x: normX, y: normY });

      let dateText = photo?.meta?.dateText || asset.dateText || '';
      if (!photo?.meta?.dateText && asset.dateText) {
        if (photoName === '50.jpg') dateText = helperCalculateDate(asset.dateText, '50');
        else if (photoName === '100.jpg') dateText = helperCalculateDate(asset.dateText, '100');
      }

      setSaving(true);
      try {
        const rawRelPath = `${asset.relDir}/${photoName}`;
        const res = await fetch('/api/timemark/manual-edit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            baseExportDir: exportDir,
            rawRelPath,
            dateText,
            yPos: normY,
            xPos: normX,
            applyToFolder: false, // HANYA FOTO INI (misal khusus foto kedua)
            detector: activeDetector
          })
        });
        const data = await res.json();
        if (res.ok && data.ok) {
          setSavedFlash(true);
          setTimeout(() => setSavedFlash(false), 1200);
          if (onSaved) onSaved();
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
    asset.dateText || 'Timemark'
  );

  return (
    <div
      className="inline-timemark-box"
      draggable={false}
      onDragStart={(e) => { e.preventDefault(); e.stopPropagation(); }}
      onPointerDown={handlePointerDown}
      style={{
        position: 'absolute',
        top: `${(pos.y / 300) * 100}%`,
        left: `${(pos.x / 300) * 100}%`,
        width: '36%',
        height: '5.2%',
        minHeight: '12px',
        maxHeight: '18px',
        border: dragging ? '1.5px solid #f0883e' : saving ? '1.5px solid #eab308' : savedFlash ? '1.5px solid #22c55e' : '1px solid #38bdf8',
        background: dragging ? 'rgba(240, 136, 62, 0.65)' : saving ? 'rgba(234, 179, 8, 0.65)' : savedFlash ? 'rgba(34, 197, 94, 0.75)' : 'rgba(56, 189, 248, 0.45)',
        boxShadow: dragging ? '0 0 10px rgba(240, 136, 62, 0.95)' : savedFlash ? '0 0 10px rgba(34, 197, 94, 0.95)' : '0 0 6px rgba(56, 189, 248, 0.6)',
        borderRadius: '3px',
        cursor: dragging ? 'grabbing' : 'grab',
        zIndex: 25,
        display: 'flex',
        alignItems: 'center',
        padding: '0 4px',
        userSelect: 'none',
        touchAction: 'none',
        boxSizing: 'border-box'
      }}
      title="✥ Geser (drag) langsung kotak timemark ini untuk memindahkan posisinya di foto. Klik untuk buka editor modal."
    >
      <span
        style={{
          fontSize: '7.5px',
          fontWeight: 700,
          color: '#ffffff',
          textShadow: '0 1px 2px #000',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          pointerEvents: 'none',
          lineHeight: 1,
          letterSpacing: '-0.2px'
        }}
      >
        {saving ? '⏳...' : savedFlash ? '✓ Disimpan' : displayText}
      </span>
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
  defaultDetector = 'google_vision',
  onSaved
}) {
  if (!isOpen || !asset || !photo) return null;

  const isSecondOrThird = photo.name === '50.jpg' || photo.name === '100.jpg';
  const calculatedDefaultDate = photo.meta?.dateText || (
    photo.name === '50.jpg' ? helperCalculateDate(asset.dateText, '50') :
    photo.name === '100.jpg' ? helperCalculateDate(asset.dateText, '100') :
    asset.dateText
  ) || '';

  const rawRelPath = `${asset.relDir}/${photo.name}`;
  const [detector, setDetector] = useState(photo.meta?.detector || defaultDetector || 'google_vision');
  const [yPos, setYPos] = useState(photo.meta?.yPos || 220);
  const [xPos, setXPos] = useState(photo.meta?.xPos || 14);
  const [dateText, setDateText] = useState(calculatedDefaultDate);
  const [previewUrl, setPreviewUrl] = useState(photo.editedUrl || null);
  const [applyToFolder, setApplyToFolder] = useState(!isSecondOrThird);
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
      setIsModalDragging(false);
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

      // Perbarui preview URL dengan timestamp baru agar cache browser bypass
      const ts = Date.now();
      setPreviewUrl(`${photo.rawUrl.split('?')[0]}?t=${ts}&mode=edited`);
      setMsg({
        type: 'success',
        text: `✓ Foto berhasil diproses menggunakan ${detector === 'google_vision' ? 'Google AI Vision' : 'Metode Biasa (HSV)'}!`
      });
      if (onSaved) onSaved();
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
      setPreviewUrl(`${photo.rawUrl.split('?')[0]}?t=${ts}&mode=manual`);

      if (andRemerge) {
        setRemerging(true);
        const mergeRes = await fetch('/api/timemark/remerge-single', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            rawRelPath,
            baseExportDir: exportDir,
            pdfName: (asset.targetFiles && asset.targetFiles[0]) || undefined
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

      if (onSaved) onSaved();
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
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', padding: '1.25rem 1.5rem', overflowY: 'auto' }}>
          
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
                  <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', maxWidth: '100%', maxHeight: '100%', lineHeight: 0 }}>
                    <img
                      src={previewUrl || photo.rawUrl}
                      alt="Foto Preview Timemark"
                      draggable={false}
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
                        width: '38%',
                        height: '6%',
                        minHeight: '16px',
                        maxHeight: '24px',
                        border: isModalDragging ? '2px solid #f0883e' : '2px solid #38bdf8',
                        background: isModalDragging ? 'rgba(240, 136, 62, 0.65)' : 'rgba(56, 189, 248, 0.45)',
                        boxShadow: isModalDragging ? '0 0 14px rgba(240, 136, 62, 0.95)' : '0 0 10px rgba(56, 189, 248, 0.75)',
                        borderRadius: '4px',
                        cursor: isModalDragging ? 'grabbing' : 'grab',
                        zIndex: 20,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '0 6px',
                        userSelect: 'none',
                        touchAction: 'none',
                        boxSizing: 'border-box'
                      }}
                      title="✥ Klik & geser kotak ini langsung di foto untuk memindahkan posisi timemark (X & Y)"
                    >
                      <span
                        style={{
                          fontSize: '8px',
                          fontWeight: 700,
                          color: '#ffffff',
                          textShadow: '0 1px 2px #000',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          pointerEvents: 'none'
                        }}
                      >
                        {dateText || 'Timemark'}
                      </span>
                      <span
                        style={{
                          fontSize: '7.5px',
                          color: '#ffffff',
                          opacity: 0.9,
                          fontWeight: 700,
                          pointerEvents: 'none',
                          marginLeft: '4px'
                        }}
                      >
                        ✥ {xPos},{yPos}
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
                    <strong style={{ fontSize: '0.8rem' }}>Memproses Timemark ({detector === 'google_vision' ? 'Vision AI' : 'HSV'})...</strong>
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
export default function GalleryPanel({ exportDir, onPickFolder }) {
  const [assets, setAssets] = useState([]);
  const [targetFiles, setTargetFiles] = useState([]);
  const [sourceFiles, setSourceFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState(null);

  // Mode States (Sama Persis dengan Web App)
  const [pipelineMode, setPipelineMode] = useState('standard'); // 'standard' | 'time' | 'coord'
  const [viewMode, setViewMode] = useState('dual'); // 'dual' | 'edited' | 'raw'
  const [cardSize, setCardSize] = useState('large'); // 'normal' | 'large'
  const [photoViewOverrides, setPhotoViewOverrides] = useState({}); // { [targetKey]: 'edited' | 'raw' }
  const [sourceTypeFilter, setSourceTypeFilter] = useState('all'); // 'timemark' | 'export' | 'all'
  const [activeDetector, setActiveDetector] = useState('google_vision'); // 'google_vision' | 'guide'

  // Filter States
  const [selectedFile, setSelectedFile] = useState('');
  const [selectedStation, setSelectedStation] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedStatus, setSelectedStatus] = useState(''); // '' | 'complete' | 'incomplete'
  const [searchQuery, setSearchQuery] = useState('');

  // Drag & Drop State
  const [dragOverRel, setDragOverRel] = useState(null);
  const [actionLoadingRel, setActionLoadingRel] = useState(null);
  const [draggedPhotoInfo, setDraggedPhotoInfo] = useState(null); // { rel, photoName, assetRel }

  // Zoom Preview Modal State
  const [zoomPhoto, setZoomPhoto] = useState(null); // { url, title }

  // Timemark Editor Modal State
  const [editingModal, setEditingModal] = useState(null); // { asset, photo }

  // Single Merge State per Asset Row
  const [mergingRel, setMergingRel] = useState(null);

  // Fetch photos and metadata from backend
  const fetchPhotos = async () => {
    if (!exportDir) return;
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch(`/api/timemark/photos?folder=${encodeURIComponent(exportDir)}`);
      if (res.ok) {
        const data = await res.json();
        const loadedAssets = data.assets || [];
        setAssets(loadedAssets);
        setTargetFiles(data.targetFiles || []);
        setSourceFiles(data.sourceFiles || []);
      } else {
        setFeedback({ type: 'error', text: 'Gagal memuat galeri foto dari folder ekspor.' });
      }
    } catch (err) {
      setFeedback({ type: 'error', text: 'Koneksi gagal: ' + err.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPhotos();
  }, [exportDir]);

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
    setActionLoadingRel(targetKey);
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
            imageBase64: base64Data
          })
        });
        const data = await res.json();
        if (res.ok && data.ok) {
          setFeedback({ type: 'success', text: `✓ Foto ${photoName} untuk ${assetRel} berhasil diperbarui.` });
          await fetchPhotos();
        } else {
          alert('Gagal mengganti foto: ' + (data.error || 'Terjadi kesalahan'));
        }
        setActionLoadingRel(null);
      };
      reader.readAsDataURL(file);
    } catch (err) {
      alert('Galat baca berkas: ' + err.message);
      setActionLoadingRel(null);
    }
  };

  // Revert Foto Asli Handler
  const handleRevert = async (assetRel, photoName) => {
    if (!confirm(`Kembalikan foto ${photoName} untuk ${assetRel} ke versi aslinya?`)) return;
    const targetKey = `${assetRel}/${photoName}`;
    setActionLoadingRel(targetKey);
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
      setActionLoadingRel(null);
    }
  };

  // Tukar Posisi Foto (Swap Photos) Handler
  const handleSwapPhotos = async (sourceRel, targetRel) => {
    if (!sourceRel || !targetRel || sourceRel === targetRel) return;
    setActionLoadingRel(sourceRel);
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
      setActionLoadingRel(null);
    }
  };

  // Potong Kolase Per Foto (Crop Single Collage) Handler
  const handleCropCollageSingle = async (targetKey) => {
    if (!targetKey) return;
    setActionLoadingRel(targetKey);
    try {
      const res = await fetch('/api/timemark/crop-collage-single', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          baseExportDir: exportDir,
          rel: targetKey
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
      setActionLoadingRel(null);
    }
  };

  // Proses Timemark Otomatis (Per Foto atau Per Folder Aset)
  const handleProcessTimemark = async (asset, photoName = null) => {
    const targetKey = photoName ? `${asset.relDir}/${photoName}` : asset.relDir;
    setActionLoadingRel(targetKey);
    try {
      const res = await fetch('/api/timemark/process-single', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          baseExportDir: exportDir,
          assetRelPath: asset.relDir,
          photoName: photoName || undefined,
          detector: activeDetector,
          dateText: asset.dateText || undefined
        })
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        setFeedback({
          type: 'success',
          text: `✓ ${data.message}`
        });
        await fetchPhotos();
      } else {
        alert('Gagal memproses timemark: ' + (data.error || 'Terjadi kesalahan'));
      }
    } catch (err) {
      alert('Galat proses timemark: ' + err.message);
    } finally {
      setActionLoadingRel(null);
    }
  };

  // Instant Merge PDF Per Row Handler
  const handleMergeRow = async (asset) => {
    setMergingRel(asset.relDir);
    try {
      const firstPhotoRel = `${asset.relDir}/0.jpg`;
      const res = await fetch('/api/timemark/remerge-single', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rawRelPath: firstPhotoRel,
          baseExportDir: exportDir,
          pdfName: (asset.targetFiles && asset.targetFiles[0]) || undefined
        })
      });
      const data = await res.json();
      if (res.ok && (data.ok || data.success)) {
        if (data.fileUrl) {
          window.open(data.fileUrl, '_blank');
        }
        setFeedback({
          type: 'success',
          text: `✓ Berkas PDF target ${data.pdfName} berhasil digabung dengan foto Timemark!`
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
      
      {/* ── STICKY FREEZE HEADER: Folder Bar & Mode Toolbar & Filter Box ── */}
      <div
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 35,
          background: 'rgba(10, 15, 29, 0.96)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.65rem',
          paddingTop: '0.25rem',
          paddingBottom: '0.75rem',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: '0 8px 24px rgba(0, 0, 0, 0.55)'
        }}
      >
        {/* ── Top Bar: Folder & Status Bar ── */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '0.75rem 1.25rem', width: '100%', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            <div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'block' }}>Folder Foto Ekspor / Timemark:</span>
              <strong style={{ fontSize: '0.875rem', color: 'var(--text-primary)', wordBreak: 'break-all' }}>{exportDir || 'Belum dipilih'}</strong>
            </div>
            {onPickFolder && (
              <button
                onClick={onPickFolder}
                style={{ padding: '0.4rem 0.85rem', background: 'var(--accent)', color: '#ffffff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.35rem' }}
              >
                📁 Ganti Folder...
              </button>
            )}
            <button
              onClick={fetchPhotos}
              disabled={loading}
              style={{ padding: '0.4rem 0.75rem', background: 'var(--bg-secondary)', color: 'var(--text-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.35rem' }}
            >
              🔄 Refresh
            </button>
          </div>

          {/* Counter Badge */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', background: 'var(--bg-secondary)', padding: '0.35rem 0.75rem', borderRadius: '6px', border: '1px solid var(--border-color)', fontWeight: 500 }}>
              Menampilkan <strong style={{ color: '#10b981' }}>{filteredAssets.length}</strong> dari <strong>{assets.length}</strong> aset ({editedCount} telah diedit)
            </span>
          </div>
        </div>

        {/* ── Mode Toolbar (Diadopsi Persis dari Web App) ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '1rem 1.25rem', width: '100%' }}>
          
          {/* Row 1: Pipeline Mode & View Mode Switchers */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem' }}>
            
            {/* Pipeline Mode Switcher */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', background: 'var(--bg-secondary)', padding: '0.3rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', paddingLeft: '0.4rem', fontWeight: 600 }}>Mode:</span>
              {[
                { id: 'standard', label: '📅 Edit Tanggal' },
                { id: 'time', label: '⏰ Edit Jam' },
                { id: 'coord', label: '📍 Edit Koordinat' }
              ].map(m => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => setPipelineMode(m.id)}
                  style={{
                    padding: '0.35rem 0.8rem',
                    borderRadius: '6px',
                    border: 'none',
                    background: pipelineMode === m.id ? '#10b981' : 'transparent',
                    color: pipelineMode === m.id ? '#ffffff' : 'var(--text-secondary)',
                    fontWeight: pipelineMode === m.id ? 700 : 500,
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                    transition: 'all 0.2s'
                  }}
                >
                  {m.label}
                </button>
              ))}
            </div>

            {/* View Mode Switcher (Dual vs Edited vs Raw) */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', background: 'var(--bg-secondary)', padding: '0.3rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', paddingLeft: '0.4rem', fontWeight: 600 }}>Tampilan:</span>
              {[
                { id: 'dual', label: '⚖️ Komparasi / Dual' },
                { id: 'edited', label: '✨ Edited (04)' },
                { id: 'raw', label: '📷 Mentah (03)' }
              ].map(v => (
                <button
                  key={v.id}
                  type="button"
                  onClick={() => setViewMode(v.id)}
                  style={{
                    padding: '0.35rem 0.8rem',
                    borderRadius: '6px',
                    border: 'none',
                    background: viewMode === v.id ? 'var(--accent)' : 'transparent',
                    color: viewMode === v.id ? '#ffffff' : 'var(--text-secondary)',
                    fontWeight: viewMode === v.id ? 700 : 500,
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                    transition: 'all 0.2s'
                  }}
                >
                  {v.label}
                </button>
              ))}
            </div>

            {/* Card Size Switcher */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', background: 'var(--bg-secondary)', padding: '0.3rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', paddingLeft: '0.4rem', fontWeight: 600 }}>Ukuran:</span>
              {[
                { id: 'normal', label: 'Standar' },
                { id: 'large', label: '🔍 Besar (Fokus)' }
              ].map(s => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setCardSize(s.id)}
                  style={{
                    padding: '0.35rem 0.8rem',
                    borderRadius: '6px',
                    border: 'none',
                    background: cardSize === s.id ? '#6366f1' : 'transparent',
                    color: cardSize === s.id ? '#ffffff' : 'var(--text-secondary)',
                    fontWeight: cardSize === s.id ? 700 : 500,
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                    transition: 'all 0.2s'
                  }}
                  title={s.id === 'large' ? 'Perbesar tampilan foto agar detail lapangan terbaca jelas' : 'Tampilan kartu proporsional standar'}
                >
                  {s.label}
                </button>
              ))}
            </div>

            {/* Detector Selector Switcher (Google AI Vision vs Metode Biasa HSV) */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', background: 'var(--bg-secondary)', padding: '0.3rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', paddingLeft: '0.4rem', fontWeight: 600 }}>Detektor:</span>
              {[
                { id: 'google_vision', label: '✨ Google Vision AI', color: '#a855f7', bg: 'rgba(168, 85, 247, 0.2)' },
                { id: 'guide', label: '🎨 Metode Biasa (HSV)', color: '#0284c7', bg: 'rgba(2, 132, 199, 0.2)' }
              ].map(d => (
                <button
                  key={d.id}
                  type="button"
                  onClick={() => setActiveDetector(d.id)}
                  style={{
                    padding: '0.35rem 0.8rem',
                    borderRadius: '6px',
                    border: activeDetector === d.id ? `1px solid ${d.color}` : '1px solid transparent',
                    background: activeDetector === d.id ? d.bg : 'transparent',
                    color: activeDetector === d.id ? d.color : 'var(--text-secondary)',
                    fontWeight: activeDetector === d.id ? 800 : 500,
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    boxShadow: activeDetector === d.id ? `0 0 8px ${d.color}40` : 'none'
                  }}
                  title={d.id === 'google_vision' ? 'Deteksi kotak tulisan waktu otomatis via Google Cloud Vision AI' : 'Deteksi garis panduan warna merah/oranye klasik'}
                >
                  {d.label}
                </button>
              ))}
            </div>

          </div>

          {/* Row 2: Search & Dropdown Filters */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem', width: '100%', alignItems: 'center' }}>
            
            {/* Filter Berkas PDF Target */}
            <div>
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
                style={{ width: '100%', padding: '0.55rem 0.75rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.8rem', outline: 'none' }}
                title="Filter aset berdasarkan berkas PDF target"
              >
                <option value="">📄 Semua Berkas Target PDF</option>
                {allFileOptions.map((opt, idx) => (
                  <option key={idx} value={opt.value} title={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Filter Stasiun / Wilayah (BTP) */}
            <div>
              <select
                value={selectedStation}
                onChange={e => setSelectedStation(e.target.value)}
                style={{ width: '100%', padding: '0.55rem 0.75rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.8rem', outline: 'none' }}
              >
                <option value="">🏢 Semua Stasiun / Wilayah (BTP)</option>
                {uniqueStations.map(stn => {
                  const count = assets.filter(a => a.station === stn).length;
                  return (
                    <option key={stn} value={stn}>
                      {stn} ({count} Aset)
                    </option>
                  );
                })}
              </select>
            </div>

            {/* Filter Kategori Aset */}
            <div>
              <select
                value={selectedCategory}
                onChange={e => setSelectedCategory(e.target.value)}
                style={{ width: '100%', padding: '0.55rem 0.75rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.8rem', outline: 'none' }}
              >
                <option value="">⚙️ Semua Kategori Aset ({assets.length} Aset)</option>
                {uniqueCategories.map(cat => (
                  <option key={cat.key} value={cat.key}>
                    {cat.label} ({cat.count})
                  </option>
                ))}
              </select>
            </div>

            {/* Filter Status Kelengkapan Foto */}
            <div>
              <select
                value={selectedStatus}
                onChange={e => setSelectedStatus(e.target.value)}
                style={{ width: '100%', padding: '0.55rem 0.75rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.8rem', outline: 'none' }}
              >
                <option value="">📸 Semua Status Kelengkapan</option>
                <option value="complete">✅ Lengkap (3 Foto: 0, 50, 100%) ({assets.filter(a => (a.photos || []).length >= 3).length})</option>
                <option value="incomplete">⚠️ Belum Lengkap (&lt; 3 Foto) ({assets.filter(a => (a.photos || []).length < 3).length})</option>
              </select>
            </div>

            {/* Filter Status Sumber Foto */}
            <div>
              <select
                value={sourceTypeFilter}
                onChange={e => setSourceTypeFilter(e.target.value)}
                style={{ width: '100%', padding: '0.55rem 0.75rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.8rem', outline: 'none' }}
              >
                <option value="all">🖼️ Semua Sumber Foto</option>
                <option value="timemark">✨ Hanya Yang Sudah Diedit (04)</option>
                <option value="export">📷 Hanya Yang Punya Mentah (03)</option>
                <option value="collage">🗂️ Hanya Foto Kolase ({assets.filter(a => a.isCollage).length})</option>
              </select>
            </div>

            {/* Pencarian Teks Cepat */}
            <div>
              <input
                type="text"
                placeholder="🔍 Cari nama aset (ZP 101, W11A, J10)..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                style={{ width: '100%', padding: '0.55rem 0.85rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.8rem', outline: 'none' }}
              />
            </div>

          </div>

          {/* Reset Filter Button row */}
          {isFilterActive && (
            <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '0.5rem', borderTop: '1px solid var(--border-color)' }}>
              <button
                onClick={resetAllFilters}
                style={{ padding: '0.35rem 0.85rem', background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600 }}
              >
                ✕ Reset Semua Filter
              </button>
            </div>
          )}
        </div>
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
          const isRowProcessing = actionLoadingRel === asset.relDir;

          return (
            <div
              key={idx}
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
                        : activeDetector === 'google_vision'
                        ? 'linear-gradient(135deg, #7e22ce 0%, #9333ea 100%)'
                        : 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
                      color: (asset.photos || []).length === 0 ? '#94a3b8' : '#ffffff',
                      border: 'none',
                      fontSize: '0.75rem',
                      fontWeight: 800,
                      cursor: isRowProcessing || isRowMerging || (asset.photos || []).length === 0 ? 'not-allowed' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                      boxShadow: (asset.photos || []).length === 0 ? 'none' : (activeDetector === 'google_vision' ? '0 2px 6px rgba(147, 51, 234, 0.4)' : '0 2px 6px rgba(2, 132, 199, 0.4)'),
                      transition: 'all 0.2s'
                    }}
                    title={(asset.photos || []).length === 0 ? 'Belum ada foto mentah yang dapat diproses' : `Edit otomatis 3 foto aset ini menggunakan ${activeDetector === 'google_vision' ? 'Google AI Vision' : 'Metode Biasa (HSV)'}`}
                  >
                    {isRowProcessing ? (
                      <>
                        <span style={{ animation: 'spin 1s linear infinite' }}>⏳</span>
                        <span>Memproses...</span>
                      </>
                    ) : (
                      <>
                        <span>{activeDetector === 'google_vision' ? '✨' : '⚡'}</span>
                        <span>Proses Timemark ({activeDetector === 'google_vision' ? 'AI Vision' : 'HSV'})</span>
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
                  <span style={{ fontSize: '0.8rem', color: asset.hasEdited ? '#4ade80' : 'var(--text-secondary)', background: asset.hasEdited ? 'rgba(34, 197, 94, 0.1)' : 'var(--bg-secondary)', border: asset.hasEdited ? '1px solid rgba(34, 197, 94, 0.25)' : 'none', padding: '0.25rem 0.65rem', borderRadius: '5px', fontWeight: asset.hasEdited ? 700 : 500 }}>
                    📅 {asset.dateText || 'Belum ada tanggal'}
                  </span>
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
                  const photoObj = (asset.photos || []).find(p => p.name === photoName);
                  const labelPercent = photoName.replace('.jpg', '') + '%';
                  const targetKey = `${asset.relDir}/${photoName}`;
                  const isDragOver = dragOverRel === targetKey;
                  const isActionLoading = actionLoadingRel === targetKey;
                  const isManual = photoObj?.meta?.manualEdit;
                  const dualCardHeight = cardSize === 'large' ? 290 : 220;
                  const singleCardHeight = cardSize === 'large' ? 380 : 270;
                  const currentSingleView = photoViewOverrides[targetKey] || (viewMode === 'raw' ? 'raw' : (photoObj?.hasEdited ? 'edited' : 'raw'));

                  return (
                    <div
                      key={photoName}
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
                              setDragOverRel(targetKey);
                            }}
                            onDragLeave={e => {
                              e.preventDefault();
                              e.stopPropagation();
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
                                  <button
                                    type="button"
                                    onClick={() => handleCropCollageSingle(targetKey)}
                                    disabled={actionLoadingRel === targetKey}
                                    style={{
                                      background: photoObj.hasTemp ? 'rgba(34, 197, 94, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                                      border: photoObj.hasTemp ? '1px solid #22c55e' : '1px solid #f59e0b',
                                      color: photoObj.hasTemp ? '#4ade80' : '#fbbf24',
                                      cursor: actionLoadingRel === targetKey ? 'not-allowed' : 'pointer',
                                      padding: '1px 5px',
                                      borderRadius: '4px',
                                      fontSize: '0.68rem',
                                      fontWeight: 600
                                    }}
                                    title={photoObj.hasTemp ? "Kolase sudah dipotong. Klik untuk potong ulang (auto-crop)" : "Potong otomatis kolase ini (auto-crop 300x300)"}
                                  >
                                    ✂️ {actionLoadingRel === targetKey ? '...' : (photoObj.hasTemp ? 'Potong Ulang' : 'Potong')}
                                  </button>
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
                                <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', maxWidth: '100%', maxHeight: '100%', lineHeight: 0 }}>
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
                              <div style={{ position: 'absolute', inset: 0, background: 'rgba(245, 158, 11, 0.9)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#ffffff', zIndex: 10, borderRadius: '6px' }}>
                                <span style={{ fontSize: '1.5rem' }}>📥</span>
                                <strong style={{ fontSize: '0.75rem' }}>Lepaskan untuk Ganti / Tukar Posisi</strong>
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
                              setDragOverRel(targetKey);
                            }}
                            onDragLeave={e => {
                              e.preventDefault();
                              e.stopPropagation();
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
                                  onClick={() => setZoomPhoto({ url: photoObj.editedUrl, title: `${asset.detail} - ${labelPercent} (Hasil Timemark 04)` })}
                                  style={{ background: 'transparent', border: 'none', color: '#34d399', cursor: 'pointer', padding: '0 2px', fontSize: '0.75rem' }}
                                  title="Perbesar Foto Editan Timemark (04)"
                                >
                                  🔍
                                </button>
                              )}
                            </div>

                            <div style={{ width: '100%', height: `${dualCardHeight}px`, display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', borderRadius: '4px', background: '#000000', position: 'relative' }}>
                              {photoObj?.editedUrl ? (
                                <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', maxWidth: '100%', maxHeight: '100%', lineHeight: 0 }}>
                                  <img
                                    src={photoObj.editedUrl}
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
                                    asset={asset}
                                    photo={photoObj}
                                    photoName={photoName}
                                    exportDir={exportDir}
                                    activeDetector={activeDetector}
                                    onSaved={fetchPhotos}
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
                                    disabled={actionLoadingRel === targetKey}
                                    style={{
                                      marginTop: '0.2rem',
                                      padding: '0.35rem 0.65rem',
                                      background: activeDetector === 'google_vision' ? 'linear-gradient(135deg, #7e22ce 0%, #9333ea 100%)' : 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
                                      color: '#ffffff',
                                      border: 'none',
                                      borderRadius: '5px',
                                      fontSize: '0.7rem',
                                      fontWeight: 700,
                                      cursor: actionLoadingRel === targetKey ? 'not-allowed' : 'pointer',
                                      display: 'flex',
                                      alignItems: 'center',
                                      gap: '0.3rem',
                                      boxShadow: '0 2px 5px rgba(0,0,0,0.3)'
                                    }}
                                    title={`Proses timemark foto ini sekarang menggunakan ${activeDetector === 'google_vision' ? 'Google AI Vision' : 'Metode Biasa'}`}
                                  >
                                    <span>{activeDetector === 'google_vision' ? '✨' : '⚡'}</span>
                                    <span>{actionLoadingRel === targetKey ? 'Memproses...' : `Proses (${activeDetector === 'google_vision' ? 'AI Vision' : 'HSV'})`}</span>
                                  </button>
                                </div>
                              )}
                            </div>

                            {/* Drag Over Overlay */}
                            {isDragOver && (
                              <div style={{ position: 'absolute', inset: 0, background: 'rgba(245, 158, 11, 0.9)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#ffffff', zIndex: 10, borderRadius: '6px' }}>
                                <span style={{ fontSize: '1.5rem' }}>📥</span>
                                <strong style={{ fontSize: '0.75rem' }}>Lepaskan untuk Ganti / Tukar Posisi</strong>
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
                            setDragOverRel(targetKey);
                          }}
                          onDragLeave={e => {
                            e.preventDefault();
                            e.stopPropagation();
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
                              <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', maxWidth: '100%', maxHeight: '100%', lineHeight: 0 }}>
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
                              <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', maxWidth: '100%', maxHeight: '100%', lineHeight: 0 }}>
                                <img
                                  src={photoObj.editedUrl}
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
                                  asset={asset}
                                  photo={photoObj}
                                  photoName={photoName}
                                  exportDir={exportDir}
                                  activeDetector={activeDetector}
                                  onSaved={fetchPhotos}
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
                                  disabled={actionLoadingRel === targetKey}
                                  style={{
                                    marginTop: '0.25rem',
                                    padding: '0.4rem 0.85rem',
                                    background: activeDetector === 'google_vision' ? 'linear-gradient(135deg, #7e22ce 0%, #9333ea 100%)' : 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
                                    color: '#ffffff',
                                    border: 'none',
                                    borderRadius: '6px',
                                    fontSize: '0.75rem',
                                    fontWeight: 700,
                                    cursor: actionLoadingRel === targetKey ? 'not-allowed' : 'pointer',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.35rem',
                                    boxShadow: '0 2px 6px rgba(0,0,0,0.3)'
                                  }}
                                  title={`Proses timemark foto ini sekarang menggunakan ${activeDetector === 'google_vision' ? 'Google AI Vision' : 'Metode Biasa'}`}
                                >
                                  <span>{activeDetector === 'google_vision' ? '✨' : '⚡'}</span>
                                  <span>{actionLoadingRel === targetKey ? 'Memproses...' : `Proses Timemark (${activeDetector === 'google_vision' ? 'AI Vision' : 'HSV'})`}</span>
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
                                src={currentSingleView === 'edited' ? photoObj.rawUrl : photoObj.editedUrl}
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
                            <div style={{ position: 'absolute', inset: 0, background: 'rgba(245, 158, 11, 0.9)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#ffffff', zIndex: 10 }}>
                              <span style={{ fontSize: '2rem' }}>📥</span>
                              <strong style={{ fontSize: '0.9rem' }}>Lepaskan untuk ganti foto</strong>
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
                            disabled={actionLoadingRel === targetKey}
                            style={{
                              padding: '0.4rem 0.65rem',
                              background: activeDetector === 'google_vision' ? 'rgba(168, 85, 247, 0.2)' : 'rgba(2, 132, 199, 0.2)',
                              color: activeDetector === 'google_vision' ? '#c084fc' : '#38bdf8',
                              border: `1px solid ${activeDetector === 'google_vision' ? '#a855f7' : '#0284c7'}`,
                              borderRadius: '6px',
                              cursor: actionLoadingRel === targetKey ? 'not-allowed' : 'pointer',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              gap: '0.3rem',
                              transition: 'all 0.2s'
                            }}
                            title={`Proses timemark foto ini sekarang menggunakan ${activeDetector === 'google_vision' ? 'Google AI Vision' : 'Metode Biasa (HSV)'}`}
                          >
                            <span>{actionLoadingRel === targetKey ? '⏳' : activeDetector === 'google_vision' ? '✨' : '⚡'}</span>
                            <span>{actionLoadingRel === targetKey ? 'Memproses...' : activeDetector === 'google_vision' ? 'AI Vision' : 'HSV'}</span>
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
                            <button
                              type="button"
                              onClick={() => handleCropCollageSingle(targetKey)}
                              disabled={actionLoadingRel === targetKey}
                              style={{
                                padding: '0.4rem 0.6rem',
                                background: photoObj.hasTemp ? 'rgba(34, 197, 94, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                                color: photoObj.hasTemp ? '#4ade80' : '#fbbf24',
                                border: photoObj.hasTemp ? '1px solid #22c55e' : '1px solid #f59e0b',
                                borderRadius: '6px',
                                cursor: actionLoadingRel === targetKey ? 'not-allowed' : 'pointer',
                                fontSize: '0.75rem',
                                fontWeight: 600,
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.25rem'
                              }}
                              title={photoObj.hasTemp ? "Kolase sudah dipotong. Klik untuk potong ulang" : "Potong otomatis foto kolase ini (auto-crop 300x300)"}
                            >
                              <span>✂️</span>
                              <span>{actionLoadingRel === targetKey ? '...' : (photoObj.hasTemp ? 'Potong Ulang' : 'Potong Kolase')}</span>
                            </button>
                          )}

                          {viewMode !== 'dual' && (
                            <button
                              type="button"
                              onClick={() => {
                                const targetZoom = viewMode === 'raw' ? ((photoObj.hasTemp && photoObj.tempUrl) || photoObj.rawUrl) : photoObj.editedUrl;
                                if (targetZoom) {
                                  setZoomPhoto({
                                    url: targetZoom,
                                    title: `${asset.detail} - Foto ${labelPercent} (${viewMode === 'raw' ? (photoObj.hasTemp ? 'Mentah Terpotong' : 'Mentah 03') : 'Editan 04'})`
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
              <img
                src={zoomPhoto.url}
                alt={zoomPhoto.title}
                style={{ maxWidth: '100%', maxHeight: '78vh', objectFit: 'contain', borderRadius: '6px' }}
              />
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
          onSaved={() => {
            fetchPhotos();
          }}
        />
      )}

    </div>
  );
}
