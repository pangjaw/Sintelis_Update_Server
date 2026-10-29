import React, { useState, useEffect, useRef, useCallback } from 'react';

/**
 * ManualCropModal.jsx
 * Modal Pemotong Kolase Manual Interaktif (Visual Drag & Resize Cropper)
 * 
 * Diporting & disempurnakan dari project OCR-FOTO-P3STE untuk Sintelis Utility.
 * Memungkinkan user untuk:
 * - Menggeser (drag) kotak seleksi crop secara visual di atas foto asli
 * - Mengubah ukuran (resize) kotak via 4 handle sudut dengan rasio 1:1 terkunci
 * - Melihat live preview hasil potongan 300x300 px
 * - Memilih preset instan (TL, TR, BL, BR, Panel Atas, Tengah, Reset 100%)
 * - Mengatur posisi & ukuran lewat slider micro-adjust
 * - Menerapkan crop ke foto tunggal atau ke seluruh foto di folder aset (0.jpg, 50.jpg, 100.jpg)
 */
export default function ManualCropModal({
  isOpen,
  onClose,
  asset,
  photo,
  exportDir,
  activeDetector = 'google_vision',
  onCropApplied
}) {
  if (!isOpen || !photo) return null;

  const targetKey = photo.rel || (asset ? `${asset.relDir}/${photo.name}` : '');
  const rawUrl = photo.rawUrl || photo.url || '';

  // Inisialisasi crop box: jika pernah dicrop sebelumnya dan ada di meta, gunakan itu
  const initialBox = photo?.meta?.cropBox && Array.isArray(photo.meta.cropBox) && photo.meta.cropBox.length === 4
    ? {
        l: Math.max(0, Math.min(100, Number(photo.meta.cropBox[0]))),
        t: Math.max(0, Math.min(100, Number(photo.meta.cropBox[1]))),
        r: Math.max(0, Math.min(100, Number(photo.meta.cropBox[2]))),
        b: Math.max(0, Math.min(100, Number(photo.meta.cropBox[3])))
      }
    : { l: 0, t: 0, r: 50, b: 50 }; // Default Kiri-Atas 2x2

  const [cropBoxNorm, setCropBoxNorm] = useState(initialBox);
  const [applyToFolder, setApplyToFolder] = useState(false);
  const [lockSquare, setLockSquare] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [naturalSize, setNaturalSize] = useState({ w: 0, h: 0 });

  // Dragging refs & state
  const [isDragging, setIsDragging] = useState(false);
  const dragTargetRef = useRef(null); // 'box' | 'tl' | 'tr' | 'bl' | 'br'
  const dragStartRef = useRef({ x: 0, y: 0, box: initialBox });
  const containerRef = useRef(null);
  const imgRef = useRef(null);
  const canvasRef = useRef(null);

  // Helper untuk enforce rasio kotak 1:1 terhadap ukuran piksel asli gambar
  const enforceSquare = useCallback((box, handle = 'br') => {
    const nw = naturalSize.w || 300;
    const nh = naturalSize.h || 300;
    let { l, t, r, b } = box;

    let wPx = Math.max(15, ((r - l) / 100) * nw);
    let hPx = Math.max(15, ((b - t) / 100) * nh);
    let sidePx = Math.min(wPx, hPx);

    let wPct = (sidePx / nw) * 100;
    let hPct = (sidePx / nh) * 100;

    if (handle === 'box') {
      let newL = Math.max(0, Math.min(100 - wPct, l));
      let newT = Math.max(0, Math.min(100 - hPct, t));
      return { l: newL, t: newT, r: newL + wPct, b: newT + hPct };
    }

    if (handle === 'tl') {
      let newL = Math.max(0, r - wPct);
      let newT = Math.max(0, b - hPct);
      return { l: newL, t: newT, r, b };
    } else if (handle === 'tr') {
      let newR = Math.min(100, l + wPct);
      let newT = Math.max(0, b - hPct);
      return { l, t: newT, r: newR, b };
    } else if (handle === 'bl') {
      let newL = Math.max(0, r - wPct);
      let newB = Math.min(100, t + hPct);
      return { l: newL, t, r, b: newB };
    } else {
      // Default br
      let newR = Math.min(100, l + wPct);
      let newB = Math.min(100, t + hPct);
      return { l, t, r: newR, b: newB };
    }
  }, [naturalSize]);

  // Redraw canvas live preview 300x300
  const updatePreviewCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img || !img.naturalWidth || !img.naturalHeight) return;

    const ctx = canvas.getContext('2d');
    const nw = img.naturalWidth;
    const nh = img.naturalHeight;

    const sx = Math.max(0, (cropBoxNorm.l / 100) * nw);
    const sy = Math.max(0, (cropBoxNorm.t / 100) * nh);
    const sw = Math.max(1, Math.min(nw - sx, ((cropBoxNorm.r - cropBoxNorm.l) / 100) * nw));
    const sh = Math.max(1, Math.min(nh - sy, ((cropBoxNorm.b - cropBoxNorm.t) / 100) * nh));

    ctx.clearRect(0, 0, 300, 300);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(img, sx, sy, sw, sh, 0, 0, 300, 300);
  }, [cropBoxNorm]);

  useEffect(() => {
    updatePreviewCanvas();
  }, [cropBoxNorm, naturalSize, updatePreviewCanvas]);

  // Saat image dimuat
  const handleImageLoaded = (e) => {
    const nw = e.target.naturalWidth || 300;
    const nh = e.target.naturalHeight || 300;
    setNaturalSize({ w: nw, h: nh });

    // Enforce rasio awal
    if (lockSquare) {
      setCropBoxNorm(prev => enforceSquare(prev, 'br'));
    }
  };

  // Pointer Down untuk drag box atau resize handles
  const handlePointerDown = (e, target) => {
    e.preventDefault();
    e.stopPropagation();

    dragTargetRef.current = target;
    dragStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      box: { ...cropBoxNorm }
    };
    setIsDragging(true);

    const onPointerMove = (ev) => {
      const container = containerRef.current;
      if (!container) return;
      const rect = container.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return;

      const deltaXPct = ((ev.clientX - dragStartRef.current.x) / rect.width) * 100;
      const deltaYPct = ((ev.clientY - dragStartRef.current.y) / rect.height) * 100;
      const init = dragStartRef.current.box;
      const t = dragTargetRef.current;

      let nextBox = { ...init };

      if (t === 'box') {
        const w = init.r - init.l;
        const h = init.b - init.t;
        let newL = Math.max(0, Math.min(100 - w, init.l + deltaXPct));
        let newT = Math.max(0, Math.min(100 - h, init.t + deltaYPct));
        nextBox = { l: newL, t: newT, r: newL + w, b: newT + h };
      } else {
        if (t.includes('l')) nextBox.l = Math.max(0, Math.min(init.r - 5, init.l + deltaXPct));
        if (t.includes('r')) nextBox.r = Math.min(100, Math.max(init.l + 5, init.r + deltaXPct));
        if (t.includes('t')) nextBox.t = Math.max(0, Math.min(init.b - 5, init.t + deltaYPct));
        if (t.includes('b')) nextBox.b = Math.min(100, Math.max(init.t + 5, init.b + deltaYPct));

        if (lockSquare) {
          nextBox = enforceSquare(nextBox, t);
        }
      }

      setCropBoxNorm(nextBox);
    };

    const onPointerUp = () => {
      setIsDragging(false);
      dragTargetRef.current = null;
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
    };

    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
  };

  // Preset Handlers
  const handlePreset = (presetName) => {
    let newBox = { l: 0, t: 0, r: 50, b: 50 };
    if (presetName === 'top-left') newBox = { l: 0, t: 0, r: 50, b: 50 };
    else if (presetName === 'top-right') newBox = { l: 50, t: 0, r: 100, b: 50 };
    else if (presetName === 'bottom-left') newBox = { l: 0, t: 50, r: 50, b: 100 };
    else if (presetName === 'bottom-right') newBox = { l: 50, t: 50, r: 100, b: 100 };
    else if (presetName === 'top-half') {
      newBox = { l: 0, t: 0, r: 100, b: 50 };
      setLockSquare(false);
      setCropBoxNorm(newBox);
      return;
    } else if (presetName === 'center') {
      newBox = { l: 25, t: 25, r: 75, b: 75 };
    } else if (presetName === 'full') {
      newBox = { l: 0, t: 0, r: 100, b: 100 };
      setLockSquare(false);
      setCropBoxNorm(newBox);
      return;
    }

    if (lockSquare) {
      newBox = enforceSquare(newBox, 'br');
    }
    setCropBoxNorm(newBox);
  };

  // Slider controls
  const boxWidth = cropBoxNorm.r - cropBoxNorm.l;
  const boxHeight = cropBoxNorm.b - cropBoxNorm.t;

  const handleSliderX = (val) => {
    const newL = Math.max(0, Math.min(100 - boxWidth, Number(val)));
    setCropBoxNorm(prev => ({ ...prev, l: newL, r: newL + boxWidth }));
  };

  const handleSliderY = (val) => {
    const newT = Math.max(0, Math.min(100 - boxHeight, Number(val)));
    setCropBoxNorm(prev => ({ ...prev, t: newT, b: newT + boxHeight }));
  };

  const handleSliderSize = (val) => {
    const newW = Number(val);
    const nw = naturalSize.w || 300;
    const nh = naturalSize.h || 300;
    const sidePx = (newW / 100) * nw;
    const newH = (sidePx / nh) * 100;

    let newR = Math.min(100, cropBoxNorm.l + newW);
    let newL = newR - newW;
    if (newL < 0) {
      newL = 0;
      newR = Math.min(100, newW);
    }

    let newB = Math.min(100, cropBoxNorm.t + newH);
    let newT = newB - newH;
    if (newT < 0) {
      newT = 0;
      newB = Math.min(100, newH);
    }

    setCropBoxNorm({ l: newL, t: newT, r: newR, b: newB });
  };

  // Terapkan Crop & Timemark
  const handleApplyCrop = async () => {
    setIsSaving(true);
    try {
      const cropBoxArray = [
        Math.round(cropBoxNorm.l * 100) / 100,
        Math.round(cropBoxNorm.t * 100) / 100,
        Math.round(cropBoxNorm.r * 100) / 100,
        Math.round(cropBoxNorm.b * 100) / 100
      ];

      const res = await fetch('/api/timemark/crop-collage-single', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          baseExportDir: exportDir,
          rel: targetKey,
          cropBox: cropBoxArray,
          applyToFolder,
          detector: activeDetector
        })
      });

      const data = await res.json();
      if (res.ok && data.ok) {
        if (onCropApplied) {
          onCropApplied(data.message || 'Crop berhasil disimpan dan foto diperbarui!');
        }
        onClose();
      } else {
        alert('Gagal menyimpan crop: ' + (data.error || 'Terjadi kesalahan sistem'));
      }
    } catch (err) {
      alert('Galat potong kolase: ' + err.message);
    } finally {
      setIsSaving(false);
    }
  };

  // Batal Crop (Kembalikan ke Asli)
  const handleUncrop = async () => {
    if (!confirm('Kembalikan foto ini ke ukuran utuh (batal crop kolase)?')) return;
    setIsSaving(true);
    try {
      const res = await fetch('/api/timemark/crop-collage-single', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          baseExportDir: exportDir,
          rel: targetKey,
          quadrant: 'ORIGINAL',
          applyToFolder,
          detector: activeDetector
        })
      });

      const data = await res.json();
      if (res.ok && data.ok) {
        if (onCropApplied) {
          onCropApplied('Foto dikembalikan ke ukuran utuh tanpa crop.');
        }
        onClose();
      } else {
        alert('Gagal membatalkan crop: ' + (data.error || 'Terjadi kesalahan'));
      }
    } catch (err) {
      alert('Galat batal crop: ' + err.message);
    } finally {
      setIsSaving(false);
    }
  };

  // Hitung estimasi piksel crop
  const pxW = naturalSize.w ? Math.round(((cropBoxNorm.r - cropBoxNorm.l) / 100) * naturalSize.w) : 0;
  const pxH = naturalSize.h ? Math.round(((cropBoxNorm.b - cropBoxNorm.t) / 100) * naturalSize.h) : 0;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(5, 10, 20, 0.85)',
        backdropFilter: 'blur(8px)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1rem',
        animation: 'fadeIn 0.15s ease-out'
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSaving && !isDragging) onClose();
      }}
    >
      <div
        style={{
          width: '880px',
          maxWidth: '96vw',
          maxHeight: '92vh',
          backgroundColor: '#0f172a',
          border: '1px solid #334155',
          borderRadius: '12px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header Modal */}
        <div
          style={{
            padding: '1rem 1.25rem',
            borderBottom: '1px solid #1e293b',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            backgroundColor: '#1e293b'
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontSize: '1.25rem' }}>✂️</span>
              <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#f8fafc' }}>
                Pemotong Kolase Manual (Visual Drag & Resize)
              </h3>
            </div>
            <p style={{ margin: '0.2rem 0 0', fontSize: '0.75rem', color: '#94a3b8' }}>
              Target: <code style={{ color: '#38bdf8' }}>{targetKey}</code>
              {naturalSize.w > 0 && ` • Dimensi Asli: ${naturalSize.w} × ${naturalSize.h} px`}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSaving}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#94a3b8',
              fontSize: '1.35rem',
              cursor: isSaving ? 'not-allowed' : 'pointer',
              padding: '0.25rem 0.5rem',
              borderRadius: '6px',
              transition: 'all 0.15s'
            }}
            title="Tutup (Esc)"
          >
            ✕
          </button>
        </div>

        {/* Body Modal: Dua Kolom (Kiri: Kanvas Crop Interaktif, Kanan: Live Preview & Kontrol) */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(320px, 420px) 1fr',
            gap: '1.25rem',
            padding: '1.25rem',
            overflowY: 'auto'
          }}
        >
          {/* Kolom Kiri: Visual Crop Canvas Container */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', alignItems: 'center' }}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                width: '100%',
                fontSize: '0.75rem',
                color: '#94a3b8'
              }}
            >
              <span>🖼️ Geser/Tarik Kotak Hijau:</span>
              <span style={{ color: '#10b981', fontWeight: 600 }}>
                {pxW > 0 ? `${pxW}×${pxH} px ➔ 300×300` : 'Rasio 1:1'}
              </span>
            </div>

            <div
              ref={containerRef}
              style={{
                position: 'relative',
                width: '380px',
                height: '380px',
                maxWidth: '100%',
                backgroundColor: '#020617',
                border: '2px dashed #38bdf8',
                borderRadius: '8px',
                overflow: 'hidden',
                userSelect: 'none',
                touchAction: 'none',
                boxShadow: 'inset 0 2px 8px rgba(0,0,0,0.6)'
              }}
            >
              {/* Gambar Mentah Penuh */}
              <img
                ref={imgRef}
                src={`${rawUrl}${rawUrl.includes('?') ? '&' : '?'}t=${Date.now()}`}
                alt="Foto Kolase Mentah"
                onLoad={handleImageLoaded}
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'contain',
                  pointerEvents: 'none',
                  display: 'block'
                }}
              />

              {/* Kotak Seleksi Crop Interaktif */}
              <div
                style={{
                  position: 'absolute',
                  left: `${cropBoxNorm.l}%`,
                  top: `${cropBoxNorm.t}%`,
                  width: `${cropBoxNorm.r - cropBoxNorm.l}%`,
                  height: `${cropBoxNorm.b - cropBoxNorm.t}%`,
                  border: '2px solid #10b981',
                  backgroundColor: 'rgba(16, 185, 129, 0.18)',
                  boxShadow: '0 0 0 9999px rgba(0, 0, 0, 0.65)',
                  cursor: isDragging ? 'grabbing' : 'grab',
                  zIndex: 20
                }}
                onPointerDown={(e) => handlePointerDown(e, 'box')}
                title="Klik & seret untuk memindahkan kotak crop"
              >
                {/* Crosshair Center */}
                <div
                  style={{
                    position: 'absolute',
                    inset: 0,
                    pointerEvents: 'none',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    opacity: 0.4
                  }}
                >
                  <div style={{ width: '12px', height: '1px', background: '#fff' }} />
                  <div style={{ height: '12px', width: '1px', background: '#fff', position: 'absolute' }} />
                </div>

                {/* 4 Corner Handles untuk Resize */}
                <div
                  onPointerDown={(e) => handlePointerDown(e, 'tl')}
                  style={{
                    position: 'absolute',
                    top: '-6px',
                    left: '-6px',
                    width: '12px',
                    height: '12px',
                    backgroundColor: '#10b981',
                    border: '2px solid #ffffff',
                    borderRadius: '50%',
                    cursor: 'nwse-resize',
                    zIndex: 30,
                    boxShadow: '0 0 6px rgba(0,0,0,0.8)'
                  }}
                  title="Tarik sudut Kiri-Atas"
                />
                <div
                  onPointerDown={(e) => handlePointerDown(e, 'tr')}
                  style={{
                    position: 'absolute',
                    top: '-6px',
                    right: '-6px',
                    width: '12px',
                    height: '12px',
                    backgroundColor: '#10b981',
                    border: '2px solid #ffffff',
                    borderRadius: '50%',
                    cursor: 'nesw-resize',
                    zIndex: 30,
                    boxShadow: '0 0 6px rgba(0,0,0,0.8)'
                  }}
                  title="Tarik sudut Kanan-Atas"
                />
                <div
                  onPointerDown={(e) => handlePointerDown(e, 'bl')}
                  style={{
                    position: 'absolute',
                    bottom: '-6px',
                    left: '-6px',
                    width: '12px',
                    height: '12px',
                    backgroundColor: '#10b981',
                    border: '2px solid #ffffff',
                    borderRadius: '50%',
                    cursor: 'nesw-resize',
                    zIndex: 30,
                    boxShadow: '0 0 6px rgba(0,0,0,0.8)'
                  }}
                  title="Tarik sudut Kiri-Bawah"
                />
                <div
                  onPointerDown={(e) => handlePointerDown(e, 'br')}
                  style={{
                    position: 'absolute',
                    bottom: '-6px',
                    right: '-6px',
                    width: '12px',
                    height: '12px',
                    backgroundColor: '#10b981',
                    border: '2px solid #ffffff',
                    borderRadius: '50%',
                    cursor: 'nwse-resize',
                    zIndex: 30,
                    boxShadow: '0 0 6px rgba(0,0,0,0.8)'
                  }}
                  title="Tarik sudut Kanan-Bawah"
                />
              </div>
            </div>

            <span style={{ fontSize: '0.72rem', color: '#64748b', textAlign: 'center' }}>
              💡 Petunjuk: Seret bagian tengah kotak untuk menggeser posisi, seret 4 titik sudut hijau untuk memperbesar/memperkecil.
            </span>
          </div>

          {/* Kolom Kanan: Live Preview & Tombol Preset & Opsi */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            
            {/* Live Preview Card */}
            <div
              style={{
                backgroundColor: '#1e293b',
                border: '1px solid #334155',
                borderRadius: '8px',
                padding: '0.75rem',
                display: 'flex',
                alignItems: 'center',
                gap: '1rem'
              }}
            >
              <div
                style={{
                  width: '120px',
                  height: '120px',
                  backgroundColor: '#020617',
                  borderRadius: '6px',
                  border: '1px solid #475569',
                  overflow: 'hidden',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0
                }}
              >
                <canvas
                  ref={canvasRef}
                  width={300}
                  height={300}
                  style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#f8fafc' }}>
                  Live Preview Hasil Crop
                </span>
                <span style={{ fontSize: '0.75rem', color: '#38bdf8', fontWeight: 600 }}>
                  Ukuran Output: 300 × 300 px
                </span>
                <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>
                  Koordinat: L:{cropBoxNorm.l.toFixed(1)}%, T:{cropBoxNorm.t.toFixed(1)}%
                </span>
                <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>
                  Lebar: {boxWidth.toFixed(1)}% | Tinggi: {boxHeight.toFixed(1)}%
                </span>
              </div>
            </div>

            {/* Presets Kuadran Instan */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#cbd5e1' }}>
                ⚡ Preset Kuadran Instan:
              </span>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.4rem' }}>
                <button
                  type="button"
                  onClick={() => handlePreset('top-left')}
                  style={presetBtnStyle}
                  title="Kuadran Kiri-Atas (2x2)"
                >
                  ↖ Atas-Kiri (TL)
                </button>
                <button
                  type="button"
                  onClick={() => handlePreset('top-right')}
                  style={presetBtnStyle}
                  title="Kuadran Kanan-Atas (2x2)"
                >
                  ↗ Atas-Kanan (TR)
                </button>
                <button
                  type="button"
                  onClick={() => handlePreset('center')}
                  style={presetBtnStyle}
                  title="Fokus Tengah (Center)"
                >
                  🎯 Tengah
                </button>
                <button
                  type="button"
                  onClick={() => handlePreset('bottom-left')}
                  style={presetBtnStyle}
                  title="Kuadran Kiri-Bawah (2x2)"
                >
                  ↙ Bawah-Kiri (BL)
                </button>
                <button
                  type="button"
                  onClick={() => handlePreset('bottom-right')}
                  style={presetBtnStyle}
                  title="Kuadran Kanan-Bawah (2x2)"
                >
                  ↘ Bawah-Kanan (BR)
                </button>
                <button
                  type="button"
                  onClick={() => handlePreset('top-half')}
                  style={presetBtnStyle}
                  title="Panel Atas (3-in-1 layout)"
                >
                  🔝 Panel Atas
                </button>
              </div>
              <button
                type="button"
                onClick={() => handlePreset('full')}
                style={{
                  ...presetBtnStyle,
                  width: '100%',
                  marginTop: '0.1rem',
                  borderColor: 'rgba(148, 163, 184, 0.4)'
                }}
                title="Reset crop ke ukuran foto utuh (100%)"
              >
                🔄 Reset Area Penuh (100%)
              </button>
            </div>

            {/* Micro-Adjustment Sliders */}
            <div
              style={{
                backgroundColor: '#1e293b',
                borderRadius: '8px',
                padding: '0.75rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.6rem'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#cbd5e1' }}>
                  🎛️ Penyesuaian Halus (Micro-Adjust):
                </span>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.72rem', color: '#94a3b8', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={lockSquare}
                    onChange={(e) => {
                      setLockSquare(e.target.checked);
                      if (e.target.checked) setCropBoxNorm(prev => enforceSquare(prev, 'br'));
                    }}
                    style={{ accentColor: '#10b981' }}
                  />
                  Kunci 1:1 (Kotak)
                </label>
              </div>

              {/* Slider X */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.72rem', color: '#94a3b8' }}>
                <span style={{ width: '45px' }}>Posisi X:</span>
                <input
                  type="range"
                  min="0"
                  max={Math.max(0, 100 - boxWidth)}
                  step="0.5"
                  value={cropBoxNorm.l}
                  onChange={(e) => handleSliderX(e.target.value)}
                  style={{ flex: 1, accentColor: '#38bdf8' }}
                />
                <span style={{ width: '35px', textAlign: 'right', fontFamily: 'monospace' }}>
                  {cropBoxNorm.l.toFixed(0)}%
                </span>
              </div>

              {/* Slider Y */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.72rem', color: '#94a3b8' }}>
                <span style={{ width: '45px' }}>Posisi Y:</span>
                <input
                  type="range"
                  min="0"
                  max={Math.max(0, 100 - boxHeight)}
                  step="0.5"
                  value={cropBoxNorm.t}
                  onChange={(e) => handleSliderY(e.target.value)}
                  style={{ flex: 1, accentColor: '#38bdf8' }}
                />
                <span style={{ width: '35px', textAlign: 'right', fontFamily: 'monospace' }}>
                  {cropBoxNorm.t.toFixed(0)}%
                </span>
              </div>

              {/* Slider Zoom / Scale */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.72rem', color: '#94a3b8' }}>
                <span style={{ width: '45px' }}>Ukuran:</span>
                <input
                  type="range"
                  min="15"
                  max="100"
                  step="1"
                  value={boxWidth}
                  onChange={(e) => handleSliderSize(e.target.value)}
                  style={{ flex: 1, accentColor: '#10b981' }}
                />
                <span style={{ width: '35px', textAlign: 'right', fontFamily: 'monospace' }}>
                  {boxWidth.toFixed(0)}%
                </span>
              </div>
            </div>

            {/* Checkbox Apply to Folder */}
            <div
              style={{
                backgroundColor: 'rgba(56, 189, 248, 0.08)',
                border: '1px solid rgba(56, 189, 248, 0.25)',
                borderRadius: '6px',
                padding: '0.6rem 0.75rem',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.5rem'
              }}
            >
              <input
                type="checkbox"
                id="chkApplyToFolder"
                checked={applyToFolder}
                onChange={(e) => setApplyToFolder(e.target.checked)}
                style={{ accentColor: '#38bdf8', marginTop: '2px', cursor: 'pointer' }}
              />
              <label
                htmlFor="chkApplyToFolder"
                style={{ fontSize: '0.75rem', color: '#cbd5e1', cursor: 'pointer', lineHeight: 1.4 }}
              >
                <strong>Terapkan ke seluruh foto dalam aset ini</strong> (0.jpg, 50.jpg, 100.jpg menggunakan kotak crop yang sama).
              </label>
            </div>

          </div>
        </div>

        {/* Footer Action Buttons */}
        <div
          style={{
            padding: '0.85rem 1.25rem',
            borderTop: '1px solid #1e293b',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            backgroundColor: '#1e293b'
          }}
        >
          {photo?.hasTemp ? (
            <button
              type="button"
              onClick={handleUncrop}
              disabled={isSaving}
              style={{
                background: 'rgba(239, 68, 68, 0.15)',
                border: '1px solid #ef4444',
                color: '#f87171',
                padding: '0.5rem 0.85rem',
                borderRadius: '6px',
                fontSize: '0.8rem',
                fontWeight: 600,
                cursor: isSaving ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.35rem'
              }}
              title="Batalkan pemotongan kolase dan kembalikan foto asli utuh"
            >
              ↩️ Batal Crop (Kembalikan ke Foto Utuh)
            </button>
          ) : <div />}

          <div style={{ display: 'flex', gap: '0.6rem' }}>
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
              style={{
                background: 'transparent',
                border: '1px solid #475569',
                color: '#cbd5e1',
                padding: '0.5rem 1rem',
                borderRadius: '6px',
                fontSize: '0.82rem',
                cursor: isSaving ? 'not-allowed' : 'pointer'
              }}
            >
              Batal
            </button>

            <button
              type="button"
              onClick={handleApplyCrop}
              disabled={isSaving}
              style={{
                background: isSaving ? '#047857' : '#10b981',
                border: '1px solid #059669',
                color: '#ffffff',
                padding: '0.5rem 1.25rem',
                borderRadius: '6px',
                fontSize: '0.82rem',
                fontWeight: 700,
                cursor: isSaving ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                boxShadow: '0 4px 12px rgba(16, 185, 129, 0.35)'
              }}
            >
              <span>{isSaving ? '⏳' : '✂️'}</span>
              <span>{isSaving ? 'Memproses Crop & Timemark...' : 'Terapkan Crop'}</span>
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}

const presetBtnStyle = {
  background: 'rgba(30, 41, 59, 0.8)',
  border: '1px solid #475569',
  color: '#cbd5e1',
  padding: '0.35rem 0.5rem',
  borderRadius: '6px',
  fontSize: '0.72rem',
  fontWeight: 600,
  cursor: 'pointer',
  textAlign: 'center',
  transition: 'all 0.15s'
};
