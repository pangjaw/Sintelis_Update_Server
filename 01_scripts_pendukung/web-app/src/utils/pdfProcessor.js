// =============================================================================
// pdfProcessor.js — PDF rendering with PDF.js + OCR with Tesseract.js
// =============================================================================

import * as pdfjs from 'pdfjs-dist';

// Lazy-load Tesseract.js — hanya saat fallback OCR dibutuhkan
let _Tesseract = null;
async function getTesseract() {
  if (!_Tesseract) {
    const mod = await import('tesseract.js');
    _Tesseract = mod.default;
  }
  return _Tesseract;
}

// Set worker path for pdfjs
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url
).toString();

const WORKER_LANG = 'ind+eng';
const API_OCR = 'http://localhost:18725/api/ocr';

/**
 * Render first page of PDF to an off-screen canvas at given DPI.
 * @param {ArrayBuffer} pdfBuffer
 * @param {number} dpi
 * @returns {Promise<HTMLCanvasElement>}
 */
export async function renderPage1(pdfBuffer, dpi = 200) {
  const pdf = await pdfjs.getDocument({ data: pdfBuffer.slice(0) }).promise;
  const page = await pdf.getPage(1);
  const viewport = page.getViewport({ scale: dpi / 72 });
  const canvas = document.createElement('canvas');
  canvas.width = viewport.width;
  canvas.height = viewport.height;
  const ctx = canvas.getContext('2d');
  await page.render({ canvasContext: ctx, viewport }).promise;
  return canvas;
}

/**
 * Run Tesseract OCR on a canvas, return uppercased text.
 * Only crops top 40% height (same as Python), with contrast boost.
 * @param {HTMLCanvasElement} canvas
 * @returns {Promise<string>}
 */
export async function ocrCanvas(canvas) {
  // Crop top 40%
  const w = canvas.width;
  const h = canvas.height;
  const cropH = Math.round(h * 0.40);

  // Apply contrast enhancement (simulate ImageOps.autocontrast)
  const enhanced = document.createElement('canvas');
  enhanced.width = w;
  enhanced.height = cropH;
  const ectx = enhanced.getContext('2d');

  // Draw cropped portion
  ectx.drawImage(canvas, 0, 0, w, cropH, 0, 0, w, cropH);

  // Grayscale + autocontrast via pixel manipulation
  const imageData = ectx.getImageData(0, 0, w, cropH);
  const pixels = imageData.data;
  let minVal = 255, maxVal = 0;
  // First pass: find min/max
  for (let i = 0; i < pixels.length; i += 4) {
    const gray = Math.round(pixels[i] * 0.299 + pixels[i + 1] * 0.587 + pixels[i + 2] * 0.114);
    if (gray < minVal) minVal = gray;
    if (gray > maxVal) maxVal = gray;
  }
  // Second pass: stretch contrast
  const range = maxVal - minVal || 1;
  for (let i = 0; i < pixels.length; i += 4) {
    const gray = Math.round(pixels[i] * 0.299 + pixels[i + 1] * 0.587 + pixels[i + 2] * 0.114);
    const stretched = Math.round(((gray - minVal) / range) * 255);
    pixels[i] = stretched;
    pixels[i + 1] = stretched;
    pixels[i + 2] = stretched;
  }
  ectx.putImageData(imageData, 0, 0);

  const T = await getTesseract();
  const { data } = await T.recognize(enhanced, WORKER_LANG, {
    logger: (m) => { /* silent */ },
  });
  return data.text.toUpperCase();
}

/**
 * Fallback OCR via Python backend (Tesseract desktop — lebih akurat).
 * @param {ArrayBuffer} pdfBuffer
 * @returns {Promise<string>}
 */
async function ocrViaPython(pdfBuffer) {
  try {
    const bytes = new Uint8Array(pdfBuffer);
    // Chunked encoding: ~50x lebih cepat dari byte-by-byte loop
    const chunkSize = 0x8000;
    let binary = '';
    for (let i = 0; i < bytes.length; i += chunkSize) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
    }
    const b64 = btoa(binary);
    const resp = await fetch(API_OCR, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data: b64 }),
    });
    const result = await resp.json();
    if (result.error) {
      console.warn('[OCR-Python] error:', result.error);
      return '';
    }
    return (result.text || '').toUpperCase();
  } catch (err) {
    console.warn('[OCR-Python] fetch failed:', err.message);
    return '';
  }
}

/**
 * Hitung SHA-256 hash dari ArrayBuffer menggunakan Web Crypto API,
 * dengan fallback FNV-1a 64-bit jika Web Crypto tidak tersedia.
 * @param {ArrayBuffer} arrayBuffer
 * @returns {Promise<string>}
 */
export async function computeSha256(arrayBuffer) {
  try {
    if (typeof window !== 'undefined' && window.crypto && window.crypto.subtle) {
      const hashBuf = await window.crypto.subtle.digest('SHA-256', arrayBuffer);
      return Array.from(new Uint8Array(hashBuf))
        .map(b => b.toString(16).padStart(2, '0'))
        .join('');
    }
  } catch (e) {
    // fallback jika Web Crypto subtle digest gagal
  }
  const bytes = new Uint8Array(arrayBuffer);
  let h1 = 0x811c9dc5;
  let h2 = 0x9e3779b9;
  for (let i = 0; i < bytes.length; i++) {
    h1 = Math.imul(h1 ^ bytes[i], 0x01000193);
    h2 = Math.imul(h2 ^ bytes[i], 0x27d4eb2d);
  }
  return (h1 >>> 0).toString(16) + (h2 >>> 0).toString(16) + '_' + bytes.length;
}

/**
 * Ekstrak layer teks digital langsung dari PDF (halaman 1) via PDF.js.
 * @param {ArrayBuffer} arrayBuffer
 * @returns {Promise<string>}
 */
export async function extractDigitalText(arrayBuffer) {
  try {
    const pdf = await pdfjs.getDocument({ data: arrayBuffer.slice(0) }).promise;
    const page = await pdf.getPage(1);
    const content = await page.getTextContent();
    if (!content || !content.items || content.items.length === 0) {
      return '';
    }
    let lines = [];
    let currentLine = '';
    let lastY = null;
    for (const item of content.items) {
      const y = item.transform ? Math.round(item.transform[5]) : null;
      if (lastY !== null && y !== null && Math.abs(y - lastY) > 3) {
        if (currentLine.trim()) lines.push(currentLine.trim());
        currentLine = '';
      }
      currentLine += (currentLine ? ' ' : '') + item.str;
      lastY = y;
      if (item.hasEOL) {
        if (currentLine.trim()) lines.push(currentLine.trim());
        currentLine = '';
        lastY = null;
      }
    }
    if (currentLine.trim()) lines.push(currentLine.trim());
    return lines.join('\n').toUpperCase();
  } catch (e) {
    return '';
  }
}

/**
 * Process a single PDF file: render → OCR (JS, fallback Python) → detect → build new name.
 * @param {File} file
 * @param {Function} detectFn
 * @returns {Promise<object>}
 */
export async function processSingleFile(file, detectFn) {
  const fname = file.name;
  if (!fname.toLowerCase().endsWith('.pdf')) {
    return { status: 'skip', filename: fname };
  }

  try {
    const arrayBuffer = file._arrayBuffer || await file.arrayBuffer();

    // 1. Prioritaskan ekstraksi digital text layer langsung (jauh lebih cepat & 100% akurat)
    let textCrop = '';
    const digText = await extractDigitalText(arrayBuffer);
    if (digText && digText.length >= 40 && (
      digText.includes('PERAWATAN') || digText.includes('PEMERIKSAAN') || digText.includes('STE') || digText.includes('RESOR')
    )) {
      textCrop = digText;
    }

    // 2. Fallback ke OCR jika digital text tidak tersedia (file PDF hasil scan gambar)
    if (!textCrop.trim()) {
      textCrop = await ocrViaPython(arrayBuffer);
      if (!textCrop.trim()) {
        const canvas = await renderPage1(arrayBuffer);
        textCrop = await ocrCanvas(canvas);
        if (!textCrop.trim()) {
          console.log(`[OCR] Both OCR failed for "${fname}"`);
        }
      }
    }
    let textFlat = textCrop.replace(/\s+/g, ' ');

    const nameOnly = fname.toUpperCase();

    // Parse date from filename
    const dateResult = parseDate(nameOnly);
    if (!dateResult) {
      return { status: 'error', filename: fname, error: 'Format tanggal tidak ditemukan.' };
    }
    const { tglFull, blnAngka, thnAngka } = dateResult;
    const prefixPeriode = `${thnAngka}-${blnAngka}`;

    const { kode, kategori, assets } = detectFn(textFlat, textCrop, nameOnly);

    return {
      status: 'success',
      filename: fname,
      fileBytes: arrayBuffer,
      kode,
      kategori,
      assets,
      tglFull,
      prefixPeriode,
      textFlat,
    };
  } catch (err) {
    return { status: 'exception', filename: fname, error: err.message };
  }
}

/**
 * Parse DD-MM-YYYY or Indonesian date from uppercase filename string.
 */
function parseDate(nameOnly) {
  const BULAN_MAP = {
    'JANUARI':'1','FEBRUARI':'2','MARET':'3','APRIL':'4',
    'MEI':'5','JUNI':'6','JULI':'7','AGUSTUS':'8',
    'SEPTEMBER':'9','OKTOBER':'10','NOVEMBER':'11','DESEMBER':'12'
  };

  // Standard DD-MM-YYYY
  const stdMatch = nameOnly.match(/(\d{2})-(\d{2})-(\d{4})/);
  if (stdMatch) {
    return {
      tglFull: stdMatch[0],
      blnAngka: String(parseInt(stdMatch[2])),
      thnAngka: stdMatch[3],
    };
  }

  // Indonesian format: "07 Januari 2025"
  const idnMatch = nameOnly.match(/(?:^|\D)(\d{1,2})\s+(JANUARI|FEBRUARI|MARET|APRIL|MEI|JUNI|JULI|AGUSTUS|SEPTEMBER|OKTOBER|NOVEMBER|DESEMBER)\s+(\d{4})\b/);
  if (idnMatch) {
    const day = idnMatch[1];
    const blnAngka = BULAN_MAP[idnMatch[2]];
    const thnAngka = idnMatch[3];
    const tglFull = `${String(parseInt(day)).padStart(2, '0')}-${String(parseInt(blnAngka)).padStart(2, '0')}-${thnAngka}`;
    return { tglFull, blnAngka, thnAngka };
  }

  return null;
}

