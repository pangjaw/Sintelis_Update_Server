import { useState, useEffect, useRef } from 'react';

const INITIAL_ACCOUNTS = [
  {
    id: 'acc_default',
    name: 'Akun Utama',
    nipp: '',
    password: ''
  }
];

function InfoTooltip({ text }) {
  return (
    <span className="info-tooltip-wrap">
      <span className="info-icon">ℹ</span>
      <span className="tooltip-bubble">{text}</span>
    </span>
  );
}

export default function P3STEDownloader({ onSendToOCR, onStopAllProcesses }) {
  // Accounts CRUD state (Multi-Akun NIPP & Password)
  const [accounts, setAccounts] = useState(() => {
    try {
      const savedV2 = localStorage.getItem('sintelis_p3ste_accounts_v2');
      if (savedV2) return JSON.parse(savedV2);
      
      // Fallback migration from older version
      const oldSaved = localStorage.getItem('sintelis_p3ste_accounts');
      if (oldSaved) {
        const parsed = JSON.parse(oldSaved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed.map(a => ({
            id: a.id || 'acc_' + Date.now(),
            name: a.name || 'Akun P3-STE',
            nipp: a.nipp || '',
            password: a.password || ''
          }));
        }
      }
      return INITIAL_ACCOUNTS;
    } catch {
      return INITIAL_ACCOUNTS;
    }
  });

  const [selectedAccountId, setSelectedAccountId] = useState(() => {
    try {
      const saved = localStorage.getItem('sintelis_p3ste_selected_acc_v2');
      return saved || 'acc_default';
    } catch {
      return 'acc_default';
    }
  });

  // Modal State
  const [showAccountModal, setShowAccountModal] = useState(false);
  const [editingAcc, setEditingAcc] = useState(null);
  const [accFormName, setAccFormName] = useState('');
  const [accFormNipp, setAccFormNipp] = useState('');
  const [accFormPassword, setAccFormPassword] = useState('');
  const [showModalPassword, setShowModalPassword] = useState(false);

  // Date States (Single input per date: YYYY-MM-DD)
  const [dateAwal, setDateAwal] = useState(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
  });
  const [dateAkhir, setDateAkhir] = useState(() => {
    const d = new Date();
    const lastDay = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`;
  });

  // Manual ID Range state & Dev options
  const [startId, setStartId] = useState('');
  const [endId, setEndId] = useState('');
  const [showBrowser, setShowBrowser] = useState(false); // Default Unchecked
  const [showDevOptions, setShowDevOptions] = useState(false); // Collapsible sub menu

  const [tipeChecklist, setTipeChecklist] = useState('2'); // 2 = Perawatan, 1 = Pemeriksaan
  const [targetFolder, setTargetFolder] = useState(null);
  
  const [isDownloading, setIsDownloading] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const [progress, setProgress] = useState({ current: 0, total: 0, percentage: 0 });
  const [logs, setLogs] = useState([]);
  const [downloadedFiles, setDownloadedFiles] = useState([]);
  const [copiedLog, setCopiedLog] = useState(false);
  const pollIntervalRef = useRef(null);
  const logTerminalRef = useRef(null);

  // Load accounts from backend file on mount (persistent across restarts)
  useEffect(() => {
    fetch('/api/accounts')
      .then(res => res.json())
      .then(data => {
        if (data && Array.isArray(data.accounts) && data.accounts.length > 0) {
          setAccounts(data.accounts);
          if (data.selected_id) {
            setSelectedAccountId(data.selected_id);
          }
        }
      })
      .catch(() => {});
  }, []);

  // Save accounts to localStorage AND backend disk (tahan restart aplikasi)
  useEffect(() => {
    try {
      localStorage.setItem('sintelis_p3ste_accounts_v2', JSON.stringify(accounts));
      localStorage.setItem('sintelis_p3ste_selected_acc_v2', selectedAccountId);
    } catch (e) {
      console.error(e);
    }

    fetch('/api/accounts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ accounts, selected_id: selectedAccountId })
    }).catch(() => {});
  }, [accounts, selectedAccountId]);

  // Non-intrusive auto-scroll (only inside container if already at bottom)
  useEffect(() => {
    if (logTerminalRef.current) {
      const el = logTerminalRef.current;
      const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
      if (isNearBottom) {
        el.scrollTop = el.scrollHeight;
      }
    }
  }, [logs]);

  // Clean up polling interval on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  const addLog = (type, msg) => {
    setLogs(prev => [...prev, { type, msg, ts: new Date().toLocaleTimeString() }]);
  };

  const handleCopyLogs = () => {
    if (!logs.length) return;
    const text = logs.map(l => `[${l.ts}] ${l.msg}`).join('\n');
    navigator.clipboard.writeText(text);
    setCopiedLog(true);
    setTimeout(() => setCopiedLog(false), 2000);
  };

  // Helper format YYYY-MM-DD -> DD/MM/YYYY
  const formatIsoToIndoDate = (isoStr) => {
    if (!isoStr) return '';
    const parts = isoStr.split('-');
    if (parts.length === 3) {
      return `${parts[2]}/${parts[1]}/${parts[0]}`;
    }
    return isoStr;
  };

  const activeAccount = accounts.find(a => a.id === selectedAccountId) || accounts[0] || INITIAL_ACCOUNTS[0];

  // Pick folder via Python native WebView endpoint
  const handleSelectFolder = async () => {
    try {
      addLog('info', 'Membuka dialog pemilihan folder...');
      const res = await fetch('/api/select-folder', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        if (data.path) {
          setTargetFolder(data.path);
          addLog('info', `Folder target dipilih: ${data.path}`);
        } else {
          addLog('warn', 'Pemilihan folder dibatalkan.');
        }
      } else {
        const errData = await res.json().catch(() => ({}));
        addLog('error', `Gagal membuka dialog folder: ${errData.error || res.statusText}`);
      }
    } catch (err) {
      addLog('error', `Gagal memilih folder: ${err.message}`);
    }
  };

  // Account Modal CRUD Handlers
  const handleOpenNewAccountModal = () => {
    setEditingAcc(null);
    setAccFormName('');
    setAccFormNipp('');
    setAccFormPassword('');
    setShowModalPassword(false);
    setShowAccountModal(true);
  };

  const handleOpenEditAccountModal = (acc) => {
    setEditingAcc(acc);
    setAccFormName(acc.name);
    setAccFormNipp(acc.nipp || '');
    setAccFormPassword(acc.password || '');
    setShowModalPassword(false);
    setShowAccountModal(true);
  };

  const handleSaveAccountForm = () => {
    if (!accFormName.trim()) {
      alert('Harap isi Nama Akun.');
      return;
    }
    if (!accFormNipp.trim()) {
      alert('Harap isi NIPP.');
      return;
    }
    if (!accFormPassword.trim()) {
      alert('Harap isi Kata Sandi.');
      return;
    }

    if (editingAcc) {
      setAccounts(prev => prev.map(a => a.id === editingAcc.id ? {
        ...a,
        name: accFormName.trim(),
        nipp: accFormNipp.trim(),
        password: accFormPassword.trim()
      } : a));
    } else {
      const newAcc = {
        id: 'acc_' + Date.now(),
        name: accFormName.trim(),
        nipp: accFormNipp.trim(),
        password: accFormPassword.trim()
      };
      setAccounts(prev => [...prev, newAcc]);
      setSelectedAccountId(newAcc.id);
    }
    setShowAccountModal(false);
  };

  const handleDeleteAccount = (accId) => {
    if (accounts.length <= 1) {
      alert('Minimal harus ada 1 akun login terdaftar.');
      return;
    }
    if (confirm('Yakin ingin menghapus data akun login ini?')) {
      const remaining = accounts.filter(a => a.id !== accId);
      setAccounts(remaining);
      if (selectedAccountId === accId) {
        setSelectedAccountId(remaining[0].id);
      }
    }
  };

  // Start download batch
  const handleStartDownload = async () => {
    setErrorMsg(null);
    setStatusMsg(null);

    if (!activeAccount || !activeAccount.nipp?.trim() || !activeAccount.password?.trim()) {
      setErrorMsg('Akun yang dipilih belum memiliki NIPP / Kata Sandi. Harap klik tombol "✏️ Edit" untuk mengisi NIPP dan Kata Sandi.');
      return;
    }

    const finalAwal = formatIsoToIndoDate(dateAwal);
    const finalAkhir = formatIsoToIndoDate(dateAkhir);

    if (!finalAwal || !finalAkhir) {
      setErrorMsg('Harap tentukan Tanggal Awal dan Tanggal Akhir.');
      return;
    }

    if (!targetFolder) {
      setErrorMsg('Harap pilih Folder Penyimpanan tempat file PDF akan disimpan.');
      return;
    }

    setIsDownloading(true);
    setProgress({ current: 0, total: 0, percentage: 0 });
    setLogs([]);
    setDownloadedFiles([]);
    addLog('info', `Memulai sesi login & unduh menggunakan ${activeAccount.name} (NIPP: ${activeAccount.nipp})...`);

    try {
      const res = await fetch('/api/p3ste/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nipp: activeAccount.nipp.trim(),
          password: activeAccount.password.trim(),
          awal: finalAwal,
          akhir: finalAkhir,
          type: tipeChecklist,
          folder: targetFolder,
          start_id: startId ? parseInt(startId) : null,
          end_id: endId ? parseInt(endId) : null,
          show_browser: showBrowser
        })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Gagal memulai download.');
      }

      addLog('success', 'Permintaan dikirim ke engine downloader. Memulai pemindaian PDF...');
      startPollingStatus();

    } catch (err) {
      setIsDownloading(false);
      setErrorMsg(err.message);
      addLog('error', `Error: ${err.message}`);
    }
  };

  const startPollingStatus = () => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

    pollIntervalRef.current = setInterval(async () => {
      try {
        const res = await fetch('/api/p3ste/status');
        if (res.ok) {
          const status = await res.json();
          
          if (status.logs && status.logs.length > 0) {
            setLogs(status.logs.map(l => ({ type: l.type || 'info', msg: l.msg, ts: l.ts || '' })));
          }

          const cur = status.current || 0;
          const tot = status.total || 0;
          const pct = tot > 0 ? Math.min(100, Math.round((cur / tot) * 100)) : 0;
          setProgress({ current: cur, total: tot, percentage: pct });

          if (status.downloaded_files) {
            setDownloadedFiles(status.downloaded_files);
          }

          if (!status.running) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
            setIsDownloading(false);

            if (status.error) {
              setErrorMsg(status.error);
              addLog('error', `Download terhenti dengan error: ${status.error}`);
            } else {
              setStatusMsg(`Selesai! Berhasil mengunduh ${status.downloaded_files?.length || 0} file PDF.`);
              addLog('success', 'Semua proses pengunduhan telah selesai.');
            }
          }
        }
      } catch (e) {
        console.error('Status polling error:', e);
      }
    }, 1000);
  };

  const handleCancelDownload = async () => {
    try {
      // 1. Hentikan timer polling di frontend seketika
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      setIsDownloading(false);
      setStatusMsg('🛑 Semua proses telah dihentikan.');
      addLog('warn', '🛑 Menghentikan semua proses yang sedang berjalan...');

      // 2. Hentikan proses OCR / Rename di Menu 1 jika aktif
      if (typeof onStopAllProcesses === 'function') {
        onStopAllProcesses();
      }

      // 3. Panggil backend untuk mematikan browser engine dan thread unduhan
      await fetch('/api/p3ste/cancel', { method: 'POST' });
    } catch (err) {
      console.error('Error saat membatalkan proses:', err);
    }
  };

  const handleSendToOCR = () => {
    if (onSendToOCR && targetFolder) {
      onSendToOCR(downloadedFiles, targetFolder);
    }
  };

  return (
    <div className="p3ste-downloader-container">
      {/* Header Info Banner */}
      <div className="banner info-banner">
        <div className="banner-icon">📥</div>
        <div className="banner-text">
          <h3>Downloader Rekap Checklist P3-STE</h3>
          <p>
            Unduh file PDF ceklis langsung dari portal P3-STE secara otomatis per halaman. Sesi login tersimpan permanen di aplikasi.
          </p>
        </div>
      </div>

      {errorMsg && (
        <div className="banner alert-banner error-banner">
          ⚠️ <strong>Error:</strong> {errorMsg}
        </div>
      )}

      {statusMsg && (
        <div className="banner alert-banner success-banner">
          ✅ {statusMsg}
        </div>
      )}

      <div className="downloader-grid">
        {/* Left Panel: Form Controls */}
        <div className="form-card">
          <div className="card-title-row">
            <h4 className="card-title">
              1. Akun Login P3-STE
              <InfoTooltip text="Pilih akun login yang digunakan. Sistem akan mengisi NIPP, Kata Sandi, dan Captcha secara otomatis." />
            </h4>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={handleOpenNewAccountModal}
              disabled={isDownloading}
            >
              ➕ Tambah Akun
            </button>
          </div>

          <div className="field-group">
            <div className="account-select-row">
              <select
                id="accountSelect"
                className="select-input"
                value={selectedAccountId}
                onChange={(e) => setSelectedAccountId(e.target.value)}
                disabled={isDownloading}
              >
                {accounts.map(acc => (
                  <option key={acc.id} value={acc.id}>
                    {acc.name} {acc.nipp ? `(NIPP: ${acc.nipp})` : '(Belum diatur)'}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                title="Edit data NIPP dan Kata Sandi akun ini"
                onClick={() => {
                  const acc = accounts.find(a => a.id === selectedAccountId);
                  if (acc) handleOpenEditAccountModal(acc);
                }}
                disabled={isDownloading}
              >
                ✏️ Edit
              </button>
            </div>

            {activeAccount && activeAccount.nipp ? (
              <div className="account-status-badge ready">
                <span>✓</span> Akun Terpasang: NIPP <strong>{activeAccount.nipp}</strong>
              </div>
            ) : (
              <div className="account-status-badge warning">
                <span>⚠️</span> NIPP & Kata Sandi belum diisi. Klik "✏️ Edit" untuk melengkapi.
              </div>
            )}
          </div>

          <h4 className="card-title" style={{ marginTop: '18px' }}>
            2. Filter Tanggal & Tipe Checklist
          </h4>
          
          <div className="form-row">
            <div className="field-group">
              <label htmlFor="datePickerAwal" className="field-label">
                Tanggal Awal
                <InfoTooltip text="Batas awal periode checklist dokumen perawatan atau pemeriksaan yang ingin diunduh." />
              </label>
              <input
                id="datePickerAwal"
                type="date"
                className="date-picker-single"
                value={dateAwal}
                onChange={(e) => setDateAwal(e.target.value)}
                disabled={isDownloading}
              />
            </div>

            <div className="field-group">
              <label htmlFor="datePickerAkhir" className="field-label">
                Tanggal Akhir
                <InfoTooltip text="Batas akhir periode checklist dokumen yang ingin diunduh." />
              </label>
              <input
                id="datePickerAkhir"
                type="date"
                className="date-picker-single"
                value={dateAkhir}
                onChange={(e) => setDateAkhir(e.target.value)}
                disabled={isDownloading}
              />
            </div>
          </div>

          <div className="field-group" style={{ marginTop: '10px' }}>
            <label className="field-label">
              Jenis Checklist:
              <InfoTooltip text="Pilih jenis laporan yang ingin ditarik dari P3-STE: Tipe 2 untuk Perawatan atau Tipe 1 untuk Pemeriksaan." />
            </label>
            <div className="radio-segmented">
              <label className={`segmented-option ${tipeChecklist === '2' ? 'active' : ''}`}>
                <input
                  type="radio"
                  name="tipeChecklist"
                  value="2"
                  checked={tipeChecklist === '2'}
                  onChange={() => setTipeChecklist('2')}
                  disabled={isDownloading}
                />
                🔴 Perawatan (Tipe 2)
              </label>
              <label className={`segmented-option ${tipeChecklist === '1' ? 'active' : ''}`}>
                <input
                  type="radio"
                  name="tipeChecklist"
                  value="1"
                  checked={tipeChecklist === '1'}
                  onChange={() => setTipeChecklist('1')}
                  disabled={isDownloading}
                />
                🔵 Pemeriksaan (Tipe 1)
              </label>
            </div>
          </div>

          <h4 className="card-title" style={{ marginTop: '18px' }}>
            3. Folder Penyimpanan
            <InfoTooltip text="Folder lokal di komputer Anda tempat seluruh file PDF hasil unduhan akan disimpan." />
          </h4>
          
          <div className="field-group">
            <div className="folder-picker-box">
              <button
                type="button"
                className="btn btn-secondary folder-btn"
                onClick={handleSelectFolder}
                disabled={isDownloading}
              >
                📂 Pilih Folder Penyimpanan
              </button>
              <div style={{ marginTop: '4px' }}>
                <input
                  type="text"
                  className="form-input"
                  style={{ fontSize: '0.82rem', width: '100%', fontFamily: 'monospace' }}
                  placeholder="Path folder penyimpanan (misal: D:\Checklist_Juli)"
                  value={targetFolder || ''}
                  onChange={(e) => setTargetFolder(e.target.value)}
                  disabled={isDownloading}
                />
              </div>
            </div>
          </div>

          {/* Sub Menu / Collapsible Dev Options */}
          <div className="dev-options-box">
            <button
              type="button"
              className="dev-options-toggle"
              onClick={() => setShowDevOptions(!showDevOptions)}
            >
              <span>⚙️ Opsi Pengembang & Filter ID Khusus</span>
              <span>{showDevOptions ? '▲ Tutup' : '▼ Buka'}</span>
            </button>
            {showDevOptions && (
              <div className="dev-options-content">
                <div className="form-row" style={{ marginBottom: '10px' }}>
                  <div className="field-group">
                    <label htmlFor="startIdInput" className="field-label" style={{ fontSize: '0.78rem' }}>
                      ID Awal (Manual):
                      <InfoTooltip text="Kosongkan untuk otomatis mengunduh semua. Isi hanya jika ingin menyaring rentang ID tertentu." />
                    </label>
                    <input
                      id="startIdInput"
                      type="number"
                      className="text-input"
                      placeholder="Misal: 778961"
                      value={startId}
                      onChange={(e) => setStartId(e.target.value)}
                      disabled={isDownloading}
                    />
                  </div>
                  <div className="field-group">
                    <label htmlFor="endIdInput" className="field-label" style={{ fontSize: '0.78rem' }}>
                      ID Akhir (Manual):
                      <InfoTooltip text="Batas atas nomor ID checklist untuk penyaringan rentang ID manual." />
                    </label>
                    <input
                      id="endIdInput"
                      type="number"
                      className="text-input"
                      placeholder="Misal: 780000"
                      value={endId}
                      onChange={(e) => setEndId(e.target.value)}
                      disabled={isDownloading}
                    />
                  </div>
                </div>

                <label className="dev-checkbox-row">
                  <input
                    type="checkbox"
                    checked={showBrowser}
                    onChange={(e) => setShowBrowser(e.target.checked)}
                    disabled={isDownloading}
                  />
                  <span>🖥️ Tampilkan Jendela Browser Edge (Debug Visual)</span>
                  <InfoTooltip text="Buka jendela browser nyata di layar untuk melihat navigasi halaman dan login secara visual." />
                </label>
              </div>
            )}
          </div>

          <div className="action-buttons" style={{ marginTop: '16px' }}>
            {!isDownloading ? (
              <button
                type="button"
                className="btn btn-primary btn-large"
                onClick={handleStartDownload}
              >
                ▶ Mulai Download PDF Rekap
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-danger btn-large"
                onClick={handleCancelDownload}
              >
                ⏹ Hentikan Proses
              </button>
            )}

            {downloadedFiles.length > 0 && !isDownloading && (
              <button
                type="button"
                className="btn btn-success btn-large"
                onClick={handleSendToOCR}
                style={{ marginTop: '10px' }}
              >
                ⚡ Langsung Rename di Menu 1 ({downloadedFiles.length} PDF)
              </button>
            )}
          </div>
        </div>

        {/* Right Panel: Progress & Real-time Logs */}
        <div className="status-card">
          <h4 className="card-title">📊 Real-Time Download Status</h4>
          
          <div className="progress-section">
            <div className="progress-label-row">
              <span>Progres Download:</span>
              <span className="progress-pct">
                {progress.total > 0
                  ? `${progress.percentage}%`
                  : (progress.current > 0 ? `${progress.current} file` : '0%')}
              </span>
            </div>
            <div className="progress-bar-bg">
              <div
                className={`progress-bar-fill ${progress.total === 0 && isDownloading ? 'indeterminate' : ''}`}
                style={{ width: `${progress.total > 0 ? progress.percentage : (progress.current > 0 ? 100 : 0)}%` }}
              />
            </div>
            <div className="progress-subtext">
              {progress.total > 0 ? (
                <>Terunduh / Terproses: <strong>{progress.current}</strong> dari <strong>{progress.total}</strong> file ({progress.percentage}%)</>
              ) : (
                <>Terunduh / Terproses: <strong>{progress.current}</strong> file {isDownloading && <span style={{ opacity: 0.7 }}>(menghitung total data...)</span>}</>
              )}
            </div>
          </div>

          <div className="card-title-row" style={{ marginTop: '10px' }}>
            <h4 className="card-title">🖥️ Log Terminal Engine</h4>
            {logs.length > 0 && (
              <button
                type="button"
                className={`btn btn-xs ${copiedLog ? 'btn-success' : 'btn-secondary'}`}
                onClick={handleCopyLogs}
              >
                {copiedLog ? '✓ Disalin ke Clipboard!' : '📋 Salin Log'}
              </button>
            )}
          </div>

          <div className="log-terminal" ref={logTerminalRef}>
            {logs.length === 0 ? (
              <div className="log-empty">Menunggu perintah download...</div>
            ) : (
              logs.map((item, idx) => (
                <div key={idx} className={`log-item log-${item.type}`}>
                  <span className="log-time">[{item.ts}]</span> {item.msg}
                </div>
              ))
            )}
          </div>

          {downloadedFiles.length > 0 && (
            <div className="downloaded-list-box">
              <h5>Daftar File PDF Terunduh ({downloadedFiles.length}):</h5>
              <ul className="downloaded-ul">
                {downloadedFiles.map((file, i) => (
                  <li key={i} className="downloaded-li">
                    📄 <span>{file.name}</span> <small>({Math.round(file.size / 1024)} KB)</small>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* Account CRUD Modal */}
      {showAccountModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h3>{editingAcc ? '✏️ Edit Data Akun P3-STE' : '➕ Tambah Akun P3-STE Baru'}</h3>
              <button
                className="modal-close-btn"
                onClick={() => setShowAccountModal(false)}
              >
                ✕
              </button>
            </div>
            <div className="modal-body">
              <div className="field-group">
                <label className="field-label">Nama / Label Akun:</label>
                <input
                  type="text"
                  className="text-input"
                  placeholder="Contoh: Akun Resor Sintel 1.21 BOO"
                  value={accFormName}
                  onChange={(e) => setAccFormName(e.target.value)}
                />
              </div>

              <div className="field-group" style={{ marginTop: '12px' }}>
                <label className="field-label">NIPP (Nomor Induk Pegawai):</label>
                <input
                  type="text"
                  className="text-input"
                  placeholder="Masukkan NIPP Anda"
                  value={accFormNipp}
                  onChange={(e) => setAccFormNipp(e.target.value)}
                />
              </div>

              <div className="field-group" style={{ marginTop: '12px' }}>
                <label className="field-label">Kata Sandi (Password):</label>
                <div className="password-input-wrapper">
                  <input
                    type={showModalPassword ? 'text' : 'password'}
                    className="text-input"
                    placeholder="Masukkan Kata Sandi P3-STE"
                    value={accFormPassword}
                    onChange={(e) => setAccFormPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    className="password-toggle-btn"
                    onClick={() => setShowModalPassword(prev => !prev)}
                    title={showModalPassword ? 'Sembunyikan sandi' : 'Tampilkan sandi'}
                  >
                    {showModalPassword ? '👁️' : '🙈'}
                  </button>
                </div>
                <small style={{ color: 'var(--text-secondary)', fontSize: '0.72rem', marginTop: '4px', display: 'block' }}>
                  🔒 Tersimpan secara aman di browser lokal komputer Anda.
                </small>
              </div>

              <div className="account-list-manager" style={{ marginTop: '18px' }}>
                <h5>Daftar Akun Tersimpan ({accounts.length}):</h5>
                <div className="accounts-list">
                  {accounts.map(acc => (
                    <div key={acc.id} className="account-card-item">
                      <div className="acc-info">
                        <strong>{acc.name}</strong>
                        <span className="acc-id">{acc.nipp ? `NIPP: ${acc.nipp}` : 'NIPP belum diatur'}</span>
                      </div>
                      <div className="acc-actions">
                        <button
                          type="button"
                          className="btn btn-secondary btn-xs"
                          onClick={() => handleOpenEditAccountModal(acc)}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          className="btn btn-danger btn-xs"
                          onClick={() => handleDeleteAccount(acc.id)}
                        >
                          Hapus
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowAccountModal(false)}
              >
                Batal
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleSaveAccountForm}
              >
                💾 Simpan Akun
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
