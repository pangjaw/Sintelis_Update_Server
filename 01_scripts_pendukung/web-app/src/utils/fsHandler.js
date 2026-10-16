// =============================================================================
// fsHandler.js — File System Access API + JSZip fallback + HTTP API (desktop)
// Desktop (pywebview): POST /api/select-folder + /api/save-file
// Browser: File System Access API + ZIP download
// =============================================================================

import JSZip from 'jszip';

const API = '/api';

async function apiPost(endpoint, body, maxRetries = 3) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const res = await fetch(`${API}/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        if (res.status >= 500 && attempt < maxRetries) {
          await new Promise(r => setTimeout(r, 200 * attempt));
          continue;
        }
        return { ok: false, error: errJson?.error || `HTTP ${res.status}` };
      }
      return await res.json();
    } catch (err) {
      if (attempt < maxRetries) {
        await new Promise(r => setTimeout(r, 200 * attempt));
        continue;
      }
      return { ok: false, error: err.message };
    }
  }
}

/**
 * Ask user to pick a directory for saving renamed files.
 * Desktop: POST /api/select-folder. Browser: File System Access API.
 * @returns {Promise<{name:string, isDesktop: boolean}|null>}
 */
export async function pickDirectory() {
  // Try desktop API first
  const data = await apiPost('select-folder');
  if (data && data.path) {
    return { name: data.name, isDesktop: true, path: data.path };
  }

  // Browser: File System Access API
  if (!window.showDirectoryPicker) {
    return null; // will use ZIP
  }
  try {
    const handle = await window.showDirectoryPicker({ mode: 'readwrite' });
    return { name: handle.name, isDesktop: false, handle };
  } catch (err) {
    if (err.name === 'AbortError') return null;
    return null;
  }
}

function uint8ToBase64(bytes) {
  let binary = '';
  const len = bytes.byteLength;
  const chunkSize = 0x8000; // 32KB chunking for high performance without call stack overflow
  for (let i = 0; i < len; i += chunkSize) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, Math.min(i + chunkSize, len)));
  }
  return btoa(binary);
}

/**
 * Write a file to selected directory.
 * Desktop: POST /api/save-file. Browser: FileSystemDirectoryHandle.
 * @param {{name:string, isDesktop:boolean, handle?:FileSystemDirectoryHandle, path?:string}} dir
 * @param {string} filename
 * @param {ArrayBuffer|Uint8Array} data
 */
export async function writeFileToDir(dir, filename, data, relativePath = filename, conflictMode = 'rename') {
  if (dir.isDesktop) {
    const bytes = new Uint8Array(data);
    const b64 = uint8ToBase64(bytes);
    const result = await apiPost('save-file', { filename, relativePath, conflictMode, data: b64, folder: dir.path });
    if (!result || !result.ok) throw new Error(result?.error || 'Gagal menyimpan file');
    return result;
  }

  // Browser: File System Access API
  if (!dir.handle) throw new Error('No directory handle');
  const fileHandle = await dir.handle.getFileHandle(filename, { create: true });
  const writable = await fileHandle.createWritable({ keepExistingData: false });
  await writable.write(data);
  await writable.close();
}

/**
 * Save all processed files as ZIP (fallback when no folder selected).
 * @param {Array<{name: string, data: ArrayBuffer}>} files
 * @returns {Promise<Blob>}
 */
export async function createZipBlob(files) {
  const zip = new JSZip();
  for (const f of files) {
    zip.file(f.name, f.data);
  }
  return await zip.generateAsync({ type: 'blob', compression: 'DEFLATE' });
}

/**
 * Save a single file with native Windows Save As dialog.
 * @param {string} filename
 * @param {string} base64Data
 * @returns {Promise<{ok: boolean, path?: string, cancelled?: boolean}>}
 */
export async function saveFileWithDialog(filename, base64Data) {
  const result = await apiPost('save-dialog-file', { filename, data: base64Data });
  return result;
}

/**
 * Trigger browser download of a blob as a file.
 * @param {Blob} blob
 * @param {string} filename
 */
export function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * List all PDF files inside a directory handle (browser) or directory path (desktop).
 * @param {{name:string, isDesktop:boolean, handle?:FileSystemDirectoryHandle, path?:string}} dir
 * @returns {Promise<string[]>} List of PDF filenames
 */
export async function listPdfsInFolder(dir) {
  if (!dir) return [];
  if (dir.isDesktop && dir.path) {
    try {
      const res = await fetch(`${API}/list-folder-pdfs?folder=${encodeURIComponent(dir.path)}`);
      if (res.ok) {
        const data = await res.json();
        return (data.files || []).map(f => (typeof f === 'string' ? f : f.name || ''));
      }
    } catch (e) {
      console.error('Error fetching folder pdfs:', e);
    }
  } else if (dir.handle) {
    try {
      const names = [];
      async function scanDirectory(handle) {
        for await (const entry of handle.values()) {
          if (entry.kind === 'file' && entry.name.toLowerCase().endsWith('.pdf')) {
            names.push(entry.name);
          } else if (entry.kind === 'directory' && entry.name.toLowerCase() !== 'backups' && entry.name.toLowerCase() !== '_temp_merged') {
            await scanDirectory(entry);
          }
        }
      }
      await scanDirectory(dir.handle);
      return names;
    } catch (e) {
      console.error('Error reading directory handle:', e);
    }
  }
  return [];
}
