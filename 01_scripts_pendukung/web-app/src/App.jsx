// =============================================================================
// App.jsx — Main React Component for Sintelis Utility Client-Side App
// =============================================================================

import { useState, useRef, useCallback, useEffect } from 'react';
import { detectDoc, buildFilename } from './utils/detector';
import { processSingleFile, computeSha256 } from './utils/pdfProcessor';
import { buildAssetDestination } from './utils/assetFolderMapper';
import { pickDirectory, writeFileToDir, createZipBlob, triggerDownload, saveFileWithDialog } from './utils/fsHandler';
import P3STEDownloader from './components/P3STEDownloader';
import AssetAuditPanel from './components/AssetAuditPanel';
import TimemarkModule from './components/TimemarkModule';
import DateChangerPanel from './components/DateChangerPanel';
import UpdateBanner from './components/UpdateBanner';
import UpdateModal from './components/UpdateModal';
import Sidebar from './components/Sidebar';
import BentoHeader from './components/BentoHeader';
import * as XLSX from 'xlsx';

export default function App() {
  const [mainTab, setMainTab] = useState('ocr'); // 'ocr' | 'downloader' | 'timemark'
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [showUpdateModal, setShowUpdateModal] = useState(false);
  const [files, setFiles] = useState([]);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [message, setMessage] = useState(null);

  const [jenisKegiatan, setJenisKegiatan] = useState('Perawatan');
  const [instansi, setInstansi] = useState('BTP JAK');
  const [outputMode, setOutputMode] = useState('root');
  const [conflictMode, setConflictMode] = useState('rename');
  const [dirHandle, setDirHandle] = useState(null);
  const [results, setResults] = useState([]);
  const [errors, setErrors] = useState([]);
  const [logs, setLogs] = useState([]);
  const [activeTab, setActiveTab] = useState('hasil');
  const [paused, setPaused] = useState(false);
  const [errorFileNames, setErrorFileNames] = useState([]);
  const [failedSaveItems, setFailedSaveItems] = useState([]);
  const [currentVersion, setCurrentVersion] = useState('v1.8.0');
  const [serverVersion, setServerVersion] = useState(null);
  const [updateAvailable, setUpdateAvailable] = useState(false);
  const [activePresetName, setActivePresetName] = useState('');
  const logEndRef = useRef();
  const inputRef = useRef();
  const cancelledRef = useRef(false);
  const pausedRef = useRef(false);
  const resumeRef = useRef(null);
  const processRef = useRef(null); // ref ke handleProcess agar handleRetryErrors tidak stale

  // Sinkronisasi update status, versi biner aktif, & preset aktif
  useEffect(() => {
    // 1. Ambil versi biner aplikasi yang sedang berjalan secara instan dari backend
    fetch('/api/version')
      .then(r => r.json())
      .then(d => {
        if (d && d.version) {
          const v = d.version.startsWith('v') ? d.version : `v${d.version}`;
          setCurrentVersion(v);
        }
      })
      .catch(() => {});

    // 2. Cek status update dari server Cloudflare
    fetch('/api/update/check')
      .then(r => r.json())
      .then(d => {
        if (d) {
          if (d.currentVersion) {
            const v = d.currentVersion.startsWith('v') ? d.currentVersion : `v${d.currentVersion}`;
            setCurrentVersion(v);
          }
          if (d.serverVersion) {
            const sv = d.serverVersion.startsWith('v') ? d.serverVersion : `v${d.serverVersion}`;
            setServerVersion(sv);
          }
          if (d.updateAvailable) setUpdateAvailable(true);
        }
      })
      .catch(() => {});

    fetch('/api/timemark/pegawai')
      .then(r => r.json())
      .then(d => {
        if (d && d.active_preset_name) {
          setActivePresetName(d.active_preset_name);
        }
      })
      .catch(() => {});
  }, []);

  // Force re-render key — digunakan saat window jadi visible lagi setelah minimize
  // Bug WebView2: React state changes saat window hidden tidak di-paint.
  // Increment key ini memaksa React mount ulang komponen hasil/error.
  const [visibilityKey, setVisibilityKey] = useState(0);

  const formatBd = instansi === 'BTP BD';

  // Visibility listener: force re-render saat window restore dari minimize
  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        // Force re-render dengan increment key
        // Delay sedikit agar compositor WebView2 siap
        setTimeout(() => {
          setVisibilityKey(k => k + 1);
        }, 150);
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, []);

  // Auto-scroll log
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const addLog = useCallback((type, msg) => {
    setLogs(prev => [...prev, { type, msg, ts: Date.now() }]);
  }, []);

  const handleFileSelect = useCallback((e) => {
    const selected = Array.from(e.target.files || []);
    setFiles(prev => {
      const existingNames = new Set(prev.map(f => f.name));
      const newFiles = selected.filter(f => !existingNames.has(f.name));
      return [...prev, ...newFiles];
    });
    setMessage(null); setResults([]); setErrors([]); setLogs([]); setFailedSaveItems([]);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    const dropped = Array.from(e.dataTransfer.files).filter(f => f.name.toLowerCase().endsWith('.pdf'));
    setFiles(prev => {
      const existingNames = new Set(prev.map(f => f.name));
      const newFiles = dropped.filter(f => !existingNames.has(f.name));
      return [...prev, ...newFiles];
    });
    setMessage(null); setResults([]); setErrors([]); setLogs([]); setFailedSaveItems([]);
  }, []);

  const removeFile = useCallback((name) => {
    setFiles(prev => prev.filter(f => f.name !== name));
  }, []);

  const handlePickDir = useCallback(async () => {
    const handle = await pickDirectory();
    setDirHandle(handle);
    if (handle) addLog('success', `Folder dipilih: ${handle.name}`);
    else addLog('info', 'Mode ZIP (folder tidak dipilih).');
  }, [addLog]);

  const handleCancel = useCallback(() => {
    cancelledRef.current = true;
    // Jika sedang pause, resume dulu agar loop bisa keluar
    pausedRef.current = false;
    if (resumeRef.current) { resumeRef.current(); resumeRef.current = null; }
    setPaused(false);
    addLog('error', 'Proses dibatalkan pengguna.');
  }, [addLog]);

  const handlePause = useCallback(() => {
    pausedRef.current = true;
    setPaused(true);
    addLog('info', 'Proses dijeda. Klik Lanjutkan untuk melanjutkan.');
  }, [addLog]);

  const handleResume = useCallback(() => {
    pausedRef.current = false;
    setPaused(false);
    if (resumeRef.current) { resumeRef.current(); resumeRef.current = null; }
    addLog('info', 'Proses dilanjutkan.');
  }, [addLog]);

  // handleProcess: opsional terima fileList untuk retry-error-only
  const handleProcess = useCallback(async (fileList) => {
    const isRetry = Array.isArray(fileList);
    const targetFiles = isRetry ? fileList : files;
    if (!targetFiles.length) return;

    cancelledRef.current = false;
    pausedRef.current = false;
    setPaused(false);
    setErrorFileNames([]);
    setProcessing(true);
    setLogs([]);
    setProgress({ current: 0, total: targetFiles.length });
    setMessage(null);
    // Saat retry: JANGAN reset results — snapshot dulu untuk di-merge nanti
    // Saat proses normal: reset semua
    if (!isRetry) { setResults([]); setErrors([]); setFailedSaveItems([]); }

    const TIMEOUT_MS = 30000; // 30 detik per file
    addLog('info', `Mulai analisis duplikasi & proses ${targetFiles.length} file...`);
    const allResultItems = [];
    const soErAssets = [];
    const soBulananAssets = [];
    const errorList = [];
    const erroredFiles = []; // track File objects yang error untuk retry

    // -------------------------------------------------------------
    // Tahap 1: Pre-OCR Fast Binary Deduplication (Level 1)
    // Lewati file yang memiliki hash SHA-256 byte biner yang 100% identik
    // HANYA jika nama filenya terindikasi duplikat unduhan (akhiran (1), (2), - Copy, _1).
    // Jika nama filenya berbeda secara substantif (misal menargetkan aset berbeda seperti JPL 07 vs JPL BNR),
    // berikan kesempatan untuk diproses; Level 2 (Post-OCR Signature Check) akan menyaring jika ternyata hasilnya duplikat.
    // -------------------------------------------------------------
    const isCopyOrDownloadDuplicate = (nameA, nameB) => {
      const stripExt = (n) => n.replace(/\.[^/.]+$/, '');
      const cleanSuffixes = (n) => stripExt(n)
        .replace(/\s*\(\d+\)$/, '')
        .replace(/\s*-\s*Copy(?:\s*\(\d+\))?$/i, '')
        .replace(/_\d+$/, '')
        .trim()
        .toLowerCase();
      return cleanSuffixes(nameA) === cleanSuffixes(nameB);
    };

    const seenBinaryHashes = new Map(); // hash -> originalFilename
    const filesToProcess = [];
    let binaryDupCount = 0;

    for (let idx = 0; idx < targetFiles.length; idx++) {
      if (cancelledRef.current) {
        setProcessing(false);
        setProgress({ current: 0, total: 0 });
        return;
      }
      const file = targetFiles[idx];
      try {
        const arrayBuffer = await file.arrayBuffer();
        file._arrayBuffer = arrayBuffer;
        const binHash = await computeSha256(arrayBuffer);
        if (seenBinaryHashes.has(binHash)) {
          const original = seenBinaryHashes.get(binHash);
          if (isCopyOrDownloadDuplicate(file.name, original)) {
            binaryDupCount++;
            addLog('warn', `[DUPLIKAT DILEWATI] "${file.name}" dilewati (duplikat unduhan dari "${original}")`);
            continue;
          }
        } else {
          seenBinaryHashes.set(binHash, file.name);
        }
        filesToProcess.push(file);
      } catch (e) {
        // Jika pembacaan awal buffer gagal, serahkan ke filesToProcess agar dilaporkan di errorList
        filesToProcess.push(file);
      }
    }

    if (binaryDupCount > 0) {
      addLog('info', `Eliminasi awal: ${binaryDupCount} file duplikat biner identik dilewati. Memproses ${filesToProcess.length} file unik...`);
    }

    // Set initial progress counter sesuai binary duplicates yang langsung dilewati
    let globalIdx = binaryDupCount;
    setProgress({ current: globalIdx, total: targetFiles.length });

    // -------------------------------------------------------------
    // Tahap 2: Parallel OCR & Post-OCR Content Signature Deduplication (Level 2)
    // -------------------------------------------------------------
    const CONCURRENCY = 4;
    const seenContentSignatures = new Map(); // contentSig -> originalFilename
    let contentDupCount = 0;

    for (let ci = 0; ci < filesToProcess.length; ci += CONCURRENCY) {
      // --- Cek cancel ---
      if (cancelledRef.current) {
        setProcessing(false);
        setProgress({ current: 0, total: 0 });
        return;
      }

      // --- Cek pause: tunggu sampai resume dipanggil ---
      while (pausedRef.current && !cancelledRef.current) {
        await new Promise(resolve => { resumeRef.current = resolve; });
      }
      if (cancelledRef.current) {
        setProcessing(false);
        setProgress({ current: 0, total: 0 });
        return;
      }

      const chunk = filesToProcess.slice(ci, ci + CONCURRENCY);
      const chunkStartIdx = ci;

      // Log semua file di chunk ini
      for (let j = 0; j < chunk.length; j++) {
        const currentNum = binaryDupCount + chunkStartIdx + j + 1;
        addLog('processing', `[${currentNum}/${targetFiles.length}] OCR ${chunk[j].name}`);
      }

      // Wrap setiap file dengan timeout
      const batchResults = await Promise.allSettled(
        chunk.map(f => Promise.race([
          processSingleFile(f, (flat, crop, upper) => detectDoc(flat, crop, upper, formatBd)),
          new Promise((_, reject) =>
            setTimeout(() => reject(new Error(`TIMEOUT: proses file >30 detik`)), TIMEOUT_MS)
          )
        ]))
      );

      // Proses hasil batch berurutan (agar log & progress urut)
      for (let j = 0; j < batchResults.length; j++) {
        if (cancelledRef.current) {
          setProcessing(false);
          setProgress({ current: 0, total: 0 });
          return;
        }

        const counter = binaryDupCount + chunkStartIdx + j + 1;
        const file = chunk[j];
        const settled = batchResults[j];

        if (settled.status === 'rejected') {
          const errMsg = settled.reason?.message || 'Unknown error';
          errorList.push(`ERROR|${file.name}|${errMsg}`);
          erroredFiles.push(file);
          addLog('error', `[${counter}/${targetFiles.length}] ${file.name}: ${errMsg}`);
          globalIdx++;
          setProgress({ current: globalIdx, total: targetFiles.length });
          continue;
        }

        const res = settled.value;
        globalIdx++;
        setProgress({ current: globalIdx, total: targetFiles.length });

        if (res.status === 'skip') { continue; }
        if (res.status === 'error' || res.status === 'exception') {
          errorList.push(`ERROR|${res.filename}|${res.error}`);
          erroredFiles.push(file);
          addLog('error', `[${counter}/${targetFiles.length}] ${res.filename}: ${res.error}`);
          continue;
        }

        const { filename, fileBytes, kode, kategori, assets, tglFull, prefixPeriode, textFlat } = res;
        addLog('info', `[OCR TEXT] ${filename}: "${textFlat ? textFlat.substring(0, 120) : '(KOSONG)'}"`);
        if (assets && assets.length > 0) {
          addLog('info', `[ASSETS] ${filename}: ${assets.map(a => `${a.id || '(TANPA ID)'} (${a.loc || '(TANPA LOKASI)'})`).join(', ')}`);
        }
        if (!assets || !assets.length) {
          errorList.push(`ERROR|${filename}|Jenis dokumen tidak terdeteksi.`);
          erroredFiles.push(file);
          addLog('error', `[${counter}/${targetFiles.length}] ${filename}: tidak terdeteksi`);
          continue;
        }

        // --- Level 2 Content Signature Check ---
        // Jika tanggal, kategori, daftar aset, dan teks checklist alfanumerik sama persis
        const normText = (textFlat || '').toLowerCase().replace(/[^a-z0-9]/g, '');
        if (normText.length >= 30) {
          const assetFingerprint = assets.map(a => `${a.id || ''}_${a.loc || ''}`).sort().join(';');
          const contentSig = `${tglFull}|${kategori}|${assetFingerprint}|${normText}`;
          if (seenContentSignatures.has(contentSig)) {
            const originalFile = seenContentSignatures.get(contentSig);
            contentDupCount++;
            addLog('warn', `[DUPLIKAT DILEWATI] "${filename}" dilewati (isi checklist identik dengan "${originalFile}")`);
            continue; // Jangan masukkan ke allResultItems
          }
          seenContentSignatures.set(contentSig, filename);
        }

        addLog('success', `[${counter}/${targetFiles.length}] ${filename} → ${kategori} (${assets.length} aset)`);

        for (const asset of assets) {
          const aid = asset.id || '';
          const loc = asset.loc || '';
          let identitas = aid ? `${kategori} ${aid} ${loc}` : `${kategori} ${loc}`;
          identitas = identitas.replace(/\s+/g, ' ').trim();

          if (asset.firstOtb !== undefined && asset.erType !== undefined) {
            soErAssets.push({ fileBytes, fname: filename, firstOtb: asset.firstOtb, erType: asset.erType, loc, kode, kategori, tglFull, prefixPeriode, jenisKegiatan, formatBd, otbMin: asset.otbMin ?? asset.firstOtb, otbMax: asset.otbMax ?? asset.firstOtb, hasOtbNumbers: asset.hasOtbNumbers });
          } else if (asset.isBulanan) {
            soBulananAssets.push({ fileBytes, fname: filename, seqNum: asset.seqNum ?? 1, loc, kode, kategori, tglFull, prefixPeriode, jenisKegiatan, formatBd });
          } else {
            allResultItems.push({ fileBytes, identitas, kode, kategori, jenisKegiatan, tglFull, prefixPeriode, formatBd });
          }
        }
      }
    }

    // Bersihkan buffer cache file
    for (const f of filesToProcess) {
      delete f._arrayBuffer;
    }

    if (cancelledRef.current) {
      setProcessing(false);
      setProgress({ current: 0, total: 0 });
      return;
    }

    // Simpan daftar file error untuk fitur retry
    setErrorFileNames(erroredFiles);

    // SO ER grouping
    const erGroups = {};
    for (const item of soErAssets) {
      const key = `${item.erType}|${item.loc}`;
      if (!erGroups[key]) erGroups[key] = [];
      erGroups[key].push(item);
    }
    for (const items of Object.values(erGroups)) {
      items.sort((a, b) => a.firstOtb - b.firstOtb);
      for (const item of items) {
        let identitas;
        if (item.hasOtbNumbers) {
          const rangeStr = item.otbMin !== item.otbMax ? `${item.otbMin}-${item.otbMax}` : String(item.otbMin);
          identitas = `${item.kategori} OTB ${rangeStr} ${item.erType} ${item.loc}`.replace(/\s+/g, ' ').trim();
        } else {
          identitas = `${item.kategori} OTB ${item.erType} ${item.loc}`.replace(/\s+/g, ' ').trim();
        }
        allResultItems.push({ fileBytes: item.fileBytes, identitas, kode: item.kode, kategori: item.kategori, jenisKegiatan: item.jenisKegiatan, tglFull: item.tglFull, prefixPeriode: item.prefixPeriode, formatBd: item.formatBd });
      }
    }

    // SO Bulanan grouping
    const bulananGroups = {};
    for (const item of soBulananAssets) {
      if (!bulananGroups[item.loc]) bulananGroups[item.loc] = [];
      bulananGroups[item.loc].push(item);
    }
    for (const items of Object.values(bulananGroups)) {
      items.sort((a, b) => a.seqNum - b.seqNum);
      items.forEach((item, idx) => {
        const suffix = idx > 0 ? ` (${idx + 1})` : '';
        const identitas = `${item.kategori} ${item.loc}${suffix}`.replace(/\s+/g, ' ').trim();
         allResultItems.push({ fileBytes: item.fileBytes, identitas, kode: item.kode, kategori: item.kategori, jenisKegiatan: item.jenisKegiatan, tglFull: item.tglFull, prefixPeriode: item.prefixPeriode, formatBd: item.formatBd });
      });
    }

    // Build filenames + dedup
    // Build filenames + penanganan duplikat otomatis dengan (2), (3), dst.
    const uniqueNames = new Set();
    const finalNames = [];
    for (const item of allResultItems) {
       let newName = buildFilename(item.prefixPeriode, item.kode, item.jenisKegiatan, item.identitas, item.tglFull, item.formatBd);
       newName = newName.replace(/[<>:"\\/\\|?*]/g, '_');
       const mapped = outputMode === 'asset' ? buildAssetDestination({ kategori: item.kategori || item.kode, asset: { id: item.identitas, loc: '' }, filename: newName }) : null;
       let relativePath = mapped?.ok ? mapped.relativePath : newName;
       
       let finalName = newName;
      if (uniqueNames.has(finalName)) {
        let counter = 2;
        const baseName = newName.replace(/\.pdf$/i, '');
        while (uniqueNames.has(`${baseName} (${counter}).pdf`)) {
          counter++;
        }
        finalName = `${baseName} (${counter}).pdf`;
        addLog('info', `Dokumen sejenis dengan isi berbeda terdeteksi, diberi penomoran: ${finalName}`);
      }
       uniqueNames.add(finalName);
       if (outputMode === 'asset' && !mapped?.ok) addLog('warn', `${newName}: mapping folder aset gagal, disimpan di root.`);
       finalNames.push({ data: item.fileBytes, name: finalName, relativePath: outputMode === 'asset' && mapped?.ok ? relativePath : finalName });
    }

    setProgress({ current: targetFiles.length, total: targetFiles.length });

    const totalSkippedDups = binaryDupCount + contentDupCount;
    const dupSummary = totalSkippedDups > 0 ? `, ${totalSkippedDups} duplikat dieliminasi otomatis` : '';

    if (isRetry) {
      // Merge hasil retry dengan hasil lama — dedup by name
      setResults(prev => {
        const existingNames = new Set(prev.map(r => r.name));
        const newUnique = finalNames.filter(r => !existingNames.has(r.name));
        return [...prev, ...newUnique];
      });
      // Ganti errors lama dengan errors dari retry (file yg masih gagal)
      setErrors(errorList);
      if (erroredFiles.length > 0) {
        addLog('info', `Retry selesai: ${finalNames.length} berhasil, ${erroredFiles.length} masih error${dupSummary}.`);
      } else {
        addLog('info', `Retry selesai: semua file berhasil diproses${dupSummary}.`);
      }
    } else {
      setResults(finalNames);
      setErrors(errorList);
      if (erroredFiles.length > 0) {
        addLog('info', `Selesai: ${finalNames.length} berhasil, ${erroredFiles.length} error${dupSummary}.`);
      } else {
        const dupNote = totalSkippedDups > 0 ? ` (${totalSkippedDups} duplikat dieliminasi otomatis)` : '';
        addLog('info', `Selesai deteksi: ${finalNames.length} file siap disimpan${dupNote}.`);
      }
    }

    setProcessing(false);
    setPaused(false);
    pausedRef.current = false;
  }, [files, jenisKegiatan, instansi, outputMode, addLog]);

  // Simpan versi terbaru handleProcess ke ref setiap render
  // Ini menghindari stale closure di handleRetryErrors
  useEffect(() => { processRef.current = handleProcess; });

  // Retry hanya file yang error — pakai processRef agar tidak stale
  const handleRetryErrors = useCallback(() => {
    if (!errorFileNames.length) return;
    addLog('info', `Retry ${errorFileNames.length} file error...`);
    processRef.current(errorFileNames);
  }, [errorFileNames, addLog]);

  const handleCopyLogs = useCallback(() => {
    if (!logs.length) return;
    const text = logs.map(l => {
      const time = new Date(l.ts).toLocaleTimeString();
      return `[${time}] [${l.type.toUpperCase()}] ${l.msg}`;
    }).join('\n');
    navigator.clipboard.writeText(text);
    setMessage({ type: 'success', text: 'Log berhasil disalin ke clipboard.' });
  }, [logs]);

  const handleExportLogs = useCallback(async () => {
    if (!logs.length) return;
    try {
      const text = logs.map(l => {
        const time = new Date(l.ts).toLocaleTimeString();
        return `[${time}] [${l.type.toUpperCase()}] ${l.msg}`;
      }).join('\n');
      const filename = `SintelisUtility_Log_${new Date().toISOString().slice(0, 10)}.txt`;
      const b64 = btoa(unescape(encodeURIComponent(text)));
      const res = await saveFileWithDialog(filename, b64);
      if (res && res.ok) {
        addLog('success', `Log diekspor ke: ${res.path}`);
        setMessage({ type: 'success', text: `Log berhasil disimpan ke: ${res.path}` });
      } else if (res && res.cancelled) {
        addLog('info', 'Penyimpanan log dibatalkan.');
      } else {
        const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
        triggerDownload(blob, filename);
        addLog('success', 'Log diekspor.');
      }
    } catch (err) {
      addLog('error', `Gagal ekspor log: ${err.message}`);
    }
  }, [logs, addLog]);

  const handleSave = useCallback(async (customItems = null) => {
    const isRetrySave = Array.isArray(customItems) && customItems.length > 0;
    const targetItems = isRetrySave ? customItems : results;
    if (!targetItems.length || processing) return;
    setProcessing(true);
    setProgress({ current: 0, total: targetItems.length });
    if (dirHandle) {
      let savedCount = 0;
      let failCount = 0;
      const currentFailed = [];
      const SAVE_CONCURRENCY = 4;
      for (let i = 0; i < targetItems.length; i += SAVE_CONCURRENCY) {
        const chunk = targetItems.slice(i, i + SAVE_CONCURRENCY);
        await Promise.all(chunk.map(async (f) => {
          try {
            await writeFileToDir(dirHandle, f.name, f.data, f.relativePath || f.name, conflictMode);
            savedCount++;
          } catch (err) {
            failCount++;
            currentFailed.push(f);
            addLog('error', `Gagal simpan "${f.name}": ${err.message}`);
          }
        }));
        setProgress({ current: savedCount + failCount, total: targetItems.length });
      }
      setFailedSaveItems(currentFailed);
      if (failCount === 0) {
        addLog('success', `${savedCount} file tersimpan ke "${dirHandle.name}"`);
        setMessage({ type: 'success', text: `${savedCount} file tersimpan ke "${dirHandle.name}"` });
      } else {
        addLog('warning', `${savedCount} file berhasil disimpan, ${failCount} gagal.`);
        setMessage({ type: 'warning', text: `${savedCount} file berhasil disimpan, ${failCount} gagal (lihat log). Klik tombol "Simpan Ulang Gagal" untuk mencoba lagi.` });
      }
    } else {
      try {
        const blob = await createZipBlob(targetItems);
        const reader = new FileReader();
        reader.onloadend = async () => {
          const b64data = reader.result.split(',')[1];
          const res = await saveFileWithDialog('Hasil_Rename.zip', b64data);
          if (res && res.ok) {
            setFailedSaveItems([]);
            addLog('success', `ZIP tersimpan: ${res.path}`);
            setMessage({ type: 'success', text: `ZIP berhasil disimpan ke: ${res.path}` });
          } else if (res && res.cancelled) {
            addLog('info', 'Penyimpanan ZIP dibatalkan.');
          } else {
            triggerDownload(blob, 'Hasil_Rename.zip');
            setFailedSaveItems([]);
            addLog('success', `ZIP diunduh (${targetItems.length} file)`);
            setMessage({ type: 'success', text: `${targetItems.length} file dalam ZIP diunduh.` });
          }
        };
        reader.readAsDataURL(blob);
      } catch (zipErr) {
        addLog('error', `Gagal membuat ZIP: ${zipErr.message}`);
      }
    }
    setProcessing(false);
  }, [results, dirHandle, addLog, processing, conflictMode]);

  const handleRetrySaveFailed = useCallback(() => {
    if (!failedSaveItems.length || processing) return;
    addLog('info', `Mencoba menyimpan ulang ${failedSaveItems.length} file yang gagal...`);
    handleSave(failedSaveItems);
  }, [failedSaveItems, processing, handleSave, addLog]);

  const handleExportExcel = useCallback(async () => {
    if (!results.length) return;
    try {
      const wsData = [['No', 'Nama File Baru']];
      results.forEach((r, i) => wsData.push([i + 1, r.name]));
      const ws = XLSX.utils.aoa_to_sheet(wsData);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, 'Hasil Rename');
      const filename = `Hasil_Rename_${new Date().toISOString().slice(0, 10)}.xlsx`;
      
      const b64 = XLSX.write(wb, { bookType: 'xlsx', type: 'base64' });
      const res = await saveFileWithDialog(filename, b64);
      if (res && res.ok) {
        addLog('success', `Excel tersimpan: ${res.path}`);
        setMessage({ type: 'success', text: `Excel berhasil disimpan ke: ${res.path}` });
      } else if (res && res.cancelled) {
        addLog('info', 'Penyimpanan Excel dibatalkan.');
      } else {
        XLSX.writeFile(wb, filename);
        addLog('success', `Excel diekspor (${results.length} file)`);
        setMessage({ type: 'success', text: 'Excel berhasil diekspor.' });
      }
    } catch (err) {
      addLog('error', `Gagal ekspor Excel: ${err.message}`);
      setMessage({ type: 'error', text: `Gagal ekspor Excel: ${err.message}` });
    }
  }, [results, addLog]);

  const handleHandoffFromDownloader = useCallback(async (downloadedFiles, folderPath) => {
    setMainTab('ocr');
    setMessage({
      type: 'info',
      text: `Memuat file PDF dari folder unduhan: ${folderPath}...`
    });
    addLog('info', `Diterima sinyal alih dokumen dari Downloader P3-STE. Folder: ${folderPath}`);

    // Otomatis arahkan folder penyimpanan output ke folder yang sama
    if (folderPath) {
      const folderName = folderPath.replace(/[\\/]+$/, '').split(/[\\/]/).pop() || folderPath;
      setDirHandle({ name: folderName, isDesktop: true, path: folderPath });
    }

    try {
      let fileTargets = Array.isArray(downloadedFiles) && downloadedFiles.length > 0 ? downloadedFiles : [];

      // Jika fileTargets kosong, ambil daftar file PDF langsung dari folder di backend
      if (!fileTargets.length && folderPath) {
        const listRes = await fetch(`/api/list-folder-pdfs?folder=${encodeURIComponent(folderPath)}`);
        if (listRes.ok) {
          const listData = await listRes.json();
          fileTargets = listData.files || [];
        }
      }

      if (!fileTargets.length) {
        setMessage({
          type: 'error',
          text: `Tidak ada file PDF yang ditemukan di folder: ${folderPath}`
        });
        addLog('warn', `Tidak ada file PDF ditemukan di folder: ${folderPath}`);
        return;
      }

      addLog('info', `Mengambil data ${fileTargets.length} file PDF ke Menu 1...`);
      const loadedFiles = [];
      for (const df of fileTargets) {
        try {
          const res = await fetch(`/api/get-file?path=${encodeURIComponent(df.path)}`);
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const blob = await res.blob();
          const file = new File([blob], df.name, { type: 'application/pdf' });
          file.nativePath = df.path;
          loadedFiles.push(file);
        } catch (fErr) {
          addLog('warn', `Gagal memuat ${df.name}: ${fErr.message}`);
        }
      }

      if (loadedFiles.length > 0) {
        setFiles(prev => {
          const existingNames = new Set(prev.map(f => f.name));
          const newFiles = loadedFiles.filter(f => !existingNames.has(f.name));
          return [...prev, ...newFiles];
        });
        setMessage({
          type: 'success',
          text: `Berhasil memuat ${loadedFiles.length} file PDF dari Downloader P3-STE. Klik tombol "Proses File" untuk memulai rename.`
        });
        addLog('success', `✓ ${loadedFiles.length} file PDF siap diproses di Menu 1!`);
      } else {
        setMessage({
          type: 'error',
          text: `Gagal membaca isi file PDF dari folder: ${folderPath}`
        });
      }
    } catch (err) {
      addLog('error', `Gagal menghubungkan file dari downloader: ${err.message}`);
      setMessage({
        type: 'error',
        text: `Error alih file: ${err.message}`
      });
    }
  }, [addLog]);

  return (
    <div className="app-layout-wrapper">
      {/* ── Collapsible Left Sidebar (NeuroNest Style) ── */}
      <Sidebar
        mainTab={mainTab}
        setMainTab={setMainTab}
        isCollapsed={isSidebarCollapsed}
        setIsCollapsed={setIsSidebarCollapsed}
      />

      {/* ── Main Workspace ── */}
      <main className="app-main-workspace">
        {/* Bento Stats & Workspace Title Header */}
        <BentoHeader
          currentVersion={currentVersion}
          serverVersion={serverVersion}
          updateAvailable={updateAvailable}
          onOpenUpdateModal={() => setShowUpdateModal(true)}
          activePreset={activePresetName || "Standar (Resor 1.21 Bogor)"}
          mainTab={mainTab}
        />

        {/* Hidden UpdateBanner for automated background check */}
        <div style={{ display: 'none' }}>
          <UpdateBanner
            onOpenModal={() => setShowUpdateModal(true)}
            onAutoOpen={(data) => {
              if (data) {
                if (data.currentVersion) {
                  const v = data.currentVersion.startsWith('v') ? data.currentVersion : `v${data.currentVersion}`;
                  setCurrentVersion(v);
                }
                if (data.serverVersion) {
                  const sv = data.serverVersion.startsWith('v') ? data.serverVersion : `v${data.serverVersion}`;
                  setServerVersion(sv);
                }
                if (data.updateAvailable) setUpdateAvailable(true);
              }
              setShowUpdateModal(true);
            }}
          />
        </div>

      {/* Timemark Tab View (Persisted in DOM) */}
      <div style={{ display: mainTab === 'timemark' ? 'flex' : 'none', flexDirection: 'column', flex: 1, width: '100%', minHeight: 0, overflow: 'hidden' }}>
        <TimemarkModule />
      </div>

      {/* Ubah Tanggal Tab View (Persisted in DOM) */}
      <div style={{ display: mainTab === 'ubah_tanggal' ? 'flex' : 'none', flexDirection: 'column', flex: 1, width: '100%', minHeight: 0, overflow: 'hidden' }}>
        <DateChangerPanel />
      </div>

      {/* Audit Aset Tab View (Standalone Full Page) */}
      <div style={{ display: mainTab === 'audit_aset' ? 'flex' : 'none', flexDirection: 'column', flex: 1, width: '100%', minHeight: 0, overflowY: 'auto', padding: '0.25rem 0.5rem' }}>
        <AssetAuditPanel
          results={results}
          onLog={addLog}
          onMessage={setMessage}
        />
      </div>

      {/* Downloader Tab View (Persisted in DOM to avoid reset on tab switch) */}
      <div style={{ display: mainTab === 'downloader' ? 'flex' : 'none', flexDirection: 'column', flex: 1, width: '100%', minHeight: 0, overflowY: 'auto' }}>
        <P3STEDownloader 
          onSendToOCR={handleHandoffFromDownloader} 
          onStopAllProcesses={handleCancel} 
        />
      </div>

      {/* OCR / Rename PDF Tab View (Persisted in DOM) */}
      <div className="main-content" style={{ display: mainTab === 'ocr' ? 'flex' : 'none', width: '100%' }}>
        {/* --------- LEFT PANEL --------- */}
        <div className="left-panel"
          onDragOver={e => { e.preventDefault(); }}
          onDrop={e => { e.preventDefault(); handleDrop(e); }}
        >
          <div className="card">
            <div className="card-title">Upload & Konfigurasi</div>

            <div className="select-group">
              <label>
                <span>Jenis Kegiatan</span>
                <select value={jenisKegiatan} onChange={e => setJenisKegiatan(e.target.value)}>
                  <option>Perawatan</option>
                  <option>Pemeriksaan</option>
                </select>
              </label>
              <label>
                <span>Instansi</span>
                <select value={instansi} onChange={e => setInstansi(e.target.value)}>
                  <option value="BTP JAK">BTP JAK</option>
                  <option value="BTP BD">BTP BD {formatBd ? '— KHUSUS SINTEL BOO' : ''}</option>
                </select>
              </label>
              <label>
                <span>Lokasi output</span>
                <select value={outputMode} onChange={e => setOutputMode(e.target.value)}>
                  <option value="root">Folder root</option>
                  <option value="asset">Folder per aset</option>
                </select>
              </label>
              <label>
                <span>Jika file sudah ada</span>
                <select value={conflictMode} onChange={e => setConflictMode(e.target.value)}>
                  <option value="rename">Tambah nama otomatis</option>
                  <option value="skip">Lewati</option>
                  <option value="overwrite">Timpa</option>
                </select>
              </label>
            </div>

            {formatBd && (
              <div className="message info">BTP BD KHUSUS SINTEL BOO</div>
            )}

            <div
              className="dropzone"
              onClick={() => inputRef.current?.click()}
              onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add('active'); }}
              onDragLeave={e => e.currentTarget.classList.remove('active')}
              onDrop={e => { e.currentTarget.classList.remove('active'); handleDrop(e); }}
            >
              <div className="dropzone-icon">📄</div>
              <div className="dropzone-text">
                <strong>Klik untuk pilih file</strong> atau drag & drop file PDF di sini
              </div>
              <input ref={inputRef} type="file" multiple accept=".pdf" style={{ display: 'none' }} onChange={handleFileSelect} />
            </div>

            {files.length > 0 && (
              <div className="file-list">
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{files.length} file dipilih</span>
                  <button className="btn btn-secondary" style={{ padding: '0.3rem 0.7rem', fontSize: '0.78rem' }}
                    onClick={() => { setFiles([]); setResults([]); setErrors([]); setMessage(null); setLogs([]); setFailedSaveItems([]); }}>
                    Hapus semua
                  </button>
                </div>
                {files.map(f => (
                  <div key={f.name} className="file-item">
                    <span className="file-status pending" />
                    <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</span>
                    <button className="btn btn-secondary" style={{ padding: '0.2rem 0.5rem', fontSize: '0.7rem', border: 'none' }}
                      onClick={() => removeFile(f.name)}>✕</button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {message && !processing && <div className={`message ${message.type}`}>{message.text}</div>}
        </div>

        {/* --------- RIGHT PANEL: ACTIONS + SPLIT (Hasil/Error | Log) --------- */}
        <div className="right-panel">
          <div className="card actions-card">
            {processing && (
              <div className="progress-bar-wrapper" style={{ marginBottom: '0.6rem' }}>
                <div className="progress-bar-fill" style={{ width: `${(progress.current / progress.total) * 100}%` }} />
              </div>
            )}
            <div className="actions-row">
              <button className="btn btn-primary" disabled={!files.length || processing} onClick={() => handleProcess()}>
                {processing ? 'Memproses...' : 'Proses File'}
              </button>
              {processing && !paused && (
                <button className="btn btn-secondary" onClick={handlePause}>
                  ⏸ Pause
                </button>
              )}
              {processing && paused && (
                <button className="btn btn-primary" onClick={handleResume}>
                  ▶ Lanjutkan
                </button>
              )}
              {processing && (
                <button className="btn btn-danger" onClick={handleCancel}>
                  ✕ Batal
                </button>
              )}
              <button className="btn btn-secondary" onClick={handlePickDir}>
                Pilih Folder Tujuan
              </button>
              {dirHandle && (
                <span style={{ fontSize: '0.78rem', color: 'var(--accent)', alignSelf: 'center' }}>
                  {dirHandle.name}
                </span>
              )}
            </div>
            {results.length > 0 && (
              <div style={{ marginTop: '0.5rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <button className="btn btn-primary" disabled={processing} onClick={() => handleSave()}>
                  {processing ? `Menyimpan (${progress.current}/${progress.total || results.length})...` : `Simpan ${results.length} File`}
                </button>
                <button className="btn btn-secondary" disabled={processing} onClick={handleExportExcel}>
                  📊 Ekspor Excel
                </button>
                <button
                  className={`btn btn-secondary ${activeTab === 'audit' ? 'active' : ''}`}
                  onClick={() => setActiveTab('audit')}
                >
                  📊 Audit Kelengkapan
                </button>
                {!processing && errorFileNames.length > 0 && (
                  <button className="btn btn-danger" onClick={handleRetryErrors}>
                    🔄 Proses Ulang Error ({errorFileNames.length} file)
                  </button>
                )}
                {!processing && failedSaveItems.length > 0 && (
                  <button className="btn btn-danger" onClick={handleRetrySaveFailed}>
                    🔄 Simpan Ulang Gagal ({failedSaveItems.length} file)
                  </button>
                )}
              </div>
            )}
          </div>

          {/* --------- Split View: Hasil/Error | Log --------- */}
          <div className="split-view">
            {/* Split Left: Hasil / Error / Audit (tabbed) */}
            <div className={`split-left ${activeTab === 'audit' ? 'audit-expanded' : ''}`}>
              <div className="tab-bar">
                <button
                  className={`tab-btn${activeTab === 'hasil' ? ' active' : ''}`}
                  onClick={() => setActiveTab('hasil')}
                >
                  Hasil{results.length > 0 && <span className="tab-badge">{results.length}</span>}
                </button>
                <button
                  className={`tab-btn${activeTab === 'error' ? ' active' : ''}`}
                  onClick={() => setActiveTab('error')}
                >
                  Error{errors.length > 0 && <span className="tab-badge" style={{ background: 'rgba(255,94,125,0.15)', color: 'var(--danger)' }}>{errors.length}</span>}
                </button>
                <button
                  className={`tab-btn${activeTab === 'audit' ? ' active' : ''}`}
                  onClick={() => setActiveTab('audit')}
                >
                  📊 Audit Aset
                </button>
              </div>
              <div className="split-lists" key={visibilityKey}>
                {activeTab === 'hasil' && (
                  <>
                    {results.length === 0 && (
                      <div className="file-item" style={{ justifyContent: 'center' }}>Belum ada hasil</div>
                    )}
                    {results.map((r, i) => (
                      <div key={i} className="file-item success">
                        <span className="file-status done" />
                        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.name}</span>
                      </div>
                    ))}
                  </>
                )}
                {activeTab === 'error' && (
                  <>
                    {errors.length === 0 && (
                      <div className="file-item" style={{ justifyContent: 'center' }}>Tidak ada error</div>
                    )}
                    {errors.map((e, i) => {
                      const parts = e.split('|');
                      const srcFile = parts[1] || '';
                      const msg = parts[2] || e;
                      return (
                        <div key={i} className="file-item error">
                          <span className="file-status fail" />
                          <span style={{ flex: 1, fontSize: '0.72rem', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            <strong>{srcFile}</strong>: {msg}
                          </span>
                        </div>
                      );
                    })}
                  </>
                )}
                {activeTab === 'audit' && (
                  <div style={{ padding: '0.5rem' }}>
                    <AssetAuditPanel
                      results={results}
                      onLog={addLog}
                      onMessage={setMessage}
                    />
                  </div>
                )}
              </div>
            </div>

            {/* Split Right: Log */}
            <div className="split-right">
              <div className="card-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <span>Log {logs.length > 0 && <span style={{ fontWeight: 400, textTransform: 'none' }}>({logs.length})</span>}</span>
                {logs.length > 0 && (
                  <div style={{ display: 'flex', gap: '0.4rem' }}>
                    <button className="btn btn-secondary" style={{ padding: '0.2rem 0.5rem', fontSize: '0.72rem' }} onClick={handleCopyLogs}>Salin</button>
                    <button className="btn btn-secondary" style={{ padding: '0.2rem 0.5rem', fontSize: '0.72rem' }} onClick={handleExportLogs}>Ekspor TXT</button>
                  </div>
                )}
              </div>
              <div className="log-panel" style={{ border: '1px solid var(--border-color)', borderRadius: '6px', padding: '0.4rem', background: 'var(--bg-secondary)' }}>
                {logs.length === 0 && (
                  <div className="log-item" style={{ justifyContent: 'center', color: 'var(--text-secondary)', background: 'none' }}>
                    Log akan muncul saat proses berjalan
                  </div>
                )}
                {logs.map((l, i) => (
                  <div key={i} className={`log-item ${l.type === 'success' ? 'success' : l.type === 'error' ? 'error' : ''}`}>
                    <span className={`file-status ${l.type === 'success' ? 'done' : l.type === 'error' ? 'fail' : 'processing'}`} />
                    <span style={{ flex: 1 }}>{l.msg}</span>
                  </div>
                ))}
                <div ref={logEndRef} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <UpdateModal isOpen={showUpdateModal} onClose={() => setShowUpdateModal(false)} />
    </div>
  );
}
