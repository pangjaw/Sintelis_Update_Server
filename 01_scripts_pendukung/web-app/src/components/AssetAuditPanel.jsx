// =============================================================================
// AssetAuditPanel.jsx — Panel Audit Kelengkapan File Aset Pemeliharaan
// =============================================================================

import React, { useState, useMemo } from 'react';
import { performAssetAudit, exportAuditToExcel } from '../utils/masterAssets.js';
import { pickDirectory, listPdfsInFolder, saveFileWithDialog, triggerDownload } from '../utils/fsHandler.js';
import * as XLSX from 'xlsx';

export default function AssetAuditPanel({ results = [], onLog, onMessage }) {
  // Source: 'current' (hasil rename saat ini) atau 'folder' (folder arsip lokal)
  const [sourceMode, setSourceMode] = useState('current');
  const [folderData, setFolderData] = useState({ name: '', path: '', files: [] });
  const [folderLoading, setFolderLoading] = useState(false);

  // Filter state
  const [periodFilter, setPeriodFilter] = useState('BULANAN');
  const [viewMode, setViewMode] = useState('detail'); // 'detail' | 'category'
  const [selectedCategory, setSelectedCategory] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL'); // 'ALL' | 'MISSING' | 'COMPLETE'
  const [searchQuery, setSearchQuery] = useState('');

  // Tentukan file sumber yang diaudit
  const filesToAudit = useMemo(() => {
    if (sourceMode === 'current') {
      return results.map(r => r.name);
    }
    return folderData.files;
  }, [sourceMode, results, folderData.files]);

  // Jalankan kalkulasi audit
  const audit = useMemo(() => {
    return performAssetAudit(filesToAudit, periodFilter);
  }, [filesToAudit, periodFilter]);

  // Handler Pilih Folder Komputer
  const handlePickFolder = async () => {
    try {
      setFolderLoading(true);
      const dir = await pickDirectory();
      if (!dir) {
        setFolderLoading(false);
        return;
      }

      const files = await listPdfsInFolder(dir);
      setFolderData({
        name: dir.name,
        path: dir.path || dir.name,
        files: files || []
      });
      setSourceMode('folder');
      if (onLog) onLog('info', `Folder audit dipilih: ${dir.path || dir.name} (${files.length} file PDF)`);
      if (onMessage) onMessage({ type: 'info', text: `Memuat ${files.length} file PDF dari folder ${dir.name}` });
    } catch (err) {
      if (onLog) onLog('error', `Gagal membaca folder audit: ${err.message}`);
      if (onMessage) onMessage({ type: 'error', text: `Gagal membaca folder: ${err.message}` });
    } finally {
      setFolderLoading(false);
    }
  };

  // Handler Ekspor Excel Audit
  const handleExportExcel = async () => {
    try {
      const title = `Audit_Kelengkapan_${periodFilter}_${sourceMode === 'folder' ? (folderData.name || 'Folder') : 'Hasil_Rename'}`;
      const { b64, filename, wb } = exportAuditToExcel(audit, title);

      // Coba dialog native pywebview jika di desktop
      const res = await saveFileWithDialog(filename, b64);
      if (res && res.ok) {
        if (onLog) onLog('success', `Laporan audit Excel disimpan ke: ${res.path}`);
        if (onMessage) onMessage({ type: 'success', text: `Laporan Excel berhasil disimpan ke: ${res.path}` });
      } else if (res && res.cancelled) {
        if (onLog) onLog('info', 'Penyimpanan Excel dibatalkan.');
      } else {
        // Fallback browser download
        XLSX.writeFile(wb, filename);
        if (onLog) onLog('success', `Laporan audit Excel diekspor (${filename})`);
        if (onMessage) onMessage({ type: 'success', text: `Laporan audit berhasil diekspor.` });
      }
    } catch (err) {
      if (onLog) onLog('error', `Gagal ekspor Excel audit: ${err.message}`);
      if (onMessage) onMessage({ type: 'error', text: `Gagal ekspor Excel: ${err.message}` });
    }
  };

  // Filter aset untuk tampilan detail
  const filteredAssets = useMemo(() => {
    return audit.assetDetails.filter(a => {
      // Filter Kategori
      if (selectedCategory !== 'ALL' && a.category !== selectedCategory) {
        return false;
      }
      // Filter Status
      if (statusFilter === 'MISSING' && a.isComplete) return false;
      if (statusFilter === 'COMPLETE' && !a.isComplete) return false;

      // Filter Search
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const str = `${a.category} ${a.id} ${a.loc} ${a.statusLabel}`.toLowerCase();
        if (!str.includes(q)) return false;
      }
      return true;
    });
  }, [audit.assetDetails, selectedCategory, statusFilter, searchQuery]);

  // Daftar kategori unik untuk dropdown filter
  const categoryOptions = useMemo(() => {
    const cats = new Set(audit.assetDetails.map(a => a.category));
    return Array.from(cats).sort();
  }, [audit.assetDetails]);

  const { summary } = audit;
  const isAllDone = summary.totalMissing === 0 && summary.totalTarget > 0;

  return (
    <div className="asset-audit-panel" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {/* 1. Header & Sumber File */}
      <div className="audit-source-card" style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        padding: '0.75rem',
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: '0.6rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Sumber Audit:</span>
          <div style={{ display: 'inline-flex', background: 'var(--bg-primary)', borderRadius: '6px', padding: '2px', border: '1px solid var(--border-color)' }}>
            <button
              className={`btn btn-secondary ${sourceMode === 'current' ? 'active' : ''}`}
              style={{
                fontSize: '0.75rem',
                padding: '0.25rem 0.6rem',
                border: 'none',
                background: sourceMode === 'current' ? 'var(--accent)' : 'transparent',
                color: sourceMode === 'current' ? '#000' : 'var(--text-primary)',
                fontWeight: sourceMode === 'current' ? 600 : 400
              }}
              onClick={() => setSourceMode('current')}
            >
              Hasil Rename ({results.length})
            </button>
            <button
              className={`btn btn-secondary ${sourceMode === 'folder' ? 'active' : ''}`}
              style={{
                fontSize: '0.75rem',
                padding: '0.25rem 0.6rem',
                border: 'none',
                background: sourceMode === 'folder' ? 'var(--accent)' : 'transparent',
                color: sourceMode === 'folder' ? '#000' : 'var(--text-primary)',
                fontWeight: sourceMode === 'folder' ? 600 : 400
              }}
              onClick={() => {
                setSourceMode('folder');
                if (folderData.files.length === 0) handlePickFolder();
              }}
            >
              📁 Folder Komputer {folderData.files.length > 0 ? `(${folderData.files.length})` : ''}
            </button>
          </div>

          {sourceMode === 'folder' && (
            <button
              className="btn btn-secondary"
              style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
              onClick={handlePickFolder}
              disabled={folderLoading}
            >
              {folderLoading ? 'Memuat...' : 'Ganti Folder...'}
            </button>
          )}

          {sourceMode === 'folder' && folderData.name && (
            <span style={{ fontSize: '0.72rem', color: 'var(--accent)', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={folderData.path}>
              📂 {folderData.name}
            </span>
          )}
        </div>

        {/* Periode Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Periode:</span>
          <select
            value={periodFilter}
            onChange={e => setPeriodFilter(e.target.value)}
            style={{
              padding: '0.25rem 0.5rem',
              fontSize: '0.75rem',
              borderRadius: '6px',
              border: '1px solid var(--border-color)',
              background: 'var(--bg-primary)',
              color: 'var(--text-primary)'
            }}
          >
            <option value="BULANAN">🟢 Rutin Bulanan (Target: 398 File)</option>
            <option value="3_BULANAN">🟡 3 Bulanan — Radio Waystation (9 File)</option>
            <option value="6_BULANAN">🟠 6 Bulanan — Radio Basestation (5 File)</option>
            <option value="1_TAHUNAN">🔵 1 Tahunan — Sistem Waystation (1 File)</option>
            <option value="ALL">🌐 Semua Periode</option>
          </select>
        </div>
      </div>

      {/* 2. KPI Summary Banner */}
      <div style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        padding: '0.75rem'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
          <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>📊 Kelengkapan Target Pemeliharaan</span>
          <span style={{ fontSize: '0.85rem', fontWeight: 700, color: isAllDone ? 'var(--accent)' : 'var(--warning)' }}>
            {summary.totalFound} / {summary.totalTarget} File ({summary.percentComplete}%)
          </span>
        </div>

        {/* Progress Bar */}
        <div className="progress-bar-wrapper" style={{ height: '8px', marginBottom: '0.6rem' }}>
          <div
            className="progress-bar-fill"
            style={{
              width: `${summary.percentComplete}%`,
              background: isAllDone ? 'var(--accent)' : 'linear-gradient(90deg, #f59e0b, #10b981)'
            }}
          />
        </div>

        {/* 4 Kartu Metrik Ringkas */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem', textAlign: 'center' }}>
          <div style={{ background: 'rgba(255,255,255,0.03)', padding: '0.4rem', borderRadius: '6px' }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Target Total</div>
            <div style={{ fontSize: '0.95rem', fontWeight: 700 }}>{summary.totalTarget}</div>
          </div>
          <div style={{ background: 'rgba(16,185,129,0.1)', padding: '0.4rem', borderRadius: '6px' }}>
            <div style={{ fontSize: '0.7rem', color: '#10b981' }}>Realisasi (Ada)</div>
            <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#10b981' }}>{summary.totalFound}</div>
          </div>
          <div style={{ background: summary.totalMissing > 0 ? 'rgba(239,68,68,0.1)' : 'rgba(255,255,255,0.03)', padding: '0.4rem', borderRadius: '6px' }}>
            <div style={{ fontSize: '0.7rem', color: summary.totalMissing > 0 ? '#ef4444' : 'var(--text-secondary)' }}>Kekurangan</div>
            <div style={{ fontSize: '0.95rem', fontWeight: 700, color: summary.totalMissing > 0 ? '#ef4444' : 'inherit' }}>
              {summary.totalMissing}
            </div>
          </div>
          <div style={{ background: 'rgba(255,255,255,0.03)', padding: '0.4rem', borderRadius: '6px' }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>File Terproses</div>
            <div style={{ fontSize: '0.95rem', fontWeight: 700 }}>{summary.totalFilesProcessed}</div>
          </div>
        </div>
      </div>

      {/* 3. Toolbar Kontrol & Filter */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', alignItems: 'center' }}>
          {/* Toggle View Mode */}
          <div style={{ display: 'inline-flex', background: 'var(--bg-secondary)', borderRadius: '6px', padding: '2px', border: '1px solid var(--border-color)' }}>
            <button
              className={`btn btn-secondary ${viewMode === 'detail' ? 'active' : ''}`}
              style={{
                fontSize: '0.72rem',
                padding: '0.2rem 0.5rem',
                border: 'none',
                background: viewMode === 'detail' ? 'var(--accent)' : 'transparent',
                color: viewMode === 'detail' ? '#000' : 'var(--text-primary)',
                fontWeight: viewMode === 'detail' ? 600 : 400
              }}
              onClick={() => setViewMode('detail')}
            >
              🔍 Detail Per Aset
            </button>
            <button
              className={`btn btn-secondary ${viewMode === 'category' ? 'active' : ''}`}
              style={{
                fontSize: '0.72rem',
                padding: '0.2rem 0.5rem',
                border: 'none',
                background: viewMode === 'category' ? 'var(--accent)' : 'transparent',
                color: viewMode === 'category' ? '#000' : 'var(--text-primary)',
                fontWeight: viewMode === 'category' ? 600 : 400
              }}
              onClick={() => setViewMode('category')}
            >
              📋 Ringkasan Kategori
            </button>
          </div>

          {/* Filter Status (Hanya di Detail Mode) */}
          {viewMode === 'detail' && (
            <div style={{ display: 'inline-flex', background: 'var(--bg-secondary)', borderRadius: '6px', padding: '2px', border: '1px solid var(--border-color)' }}>
              <button
                className={`btn btn-secondary ${statusFilter === 'ALL' ? 'active' : ''}`}
                style={{
                  fontSize: '0.72rem',
                  padding: '0.2rem 0.5rem',
                  border: 'none',
                  background: statusFilter === 'ALL' ? 'rgba(255,255,255,0.1)' : 'transparent',
                  fontWeight: statusFilter === 'ALL' ? 600 : 400
                }}
                onClick={() => setStatusFilter('ALL')}
              >
                Semua ({audit.assetDetails.length})
              </button>
              <button
                className={`btn btn-secondary ${statusFilter === 'MISSING' ? 'active' : ''}`}
                style={{
                  fontSize: '0.72rem',
                  padding: '0.2rem 0.5rem',
                  border: 'none',
                  background: statusFilter === 'MISSING' ? 'rgba(239,68,68,0.2)' : 'transparent',
                  color: statusFilter === 'MISSING' ? '#ef4444' : 'inherit',
                  fontWeight: statusFilter === 'MISSING' ? 600 : 400
                }}
                onClick={() => setStatusFilter('MISSING')}
              >
                ❌ Kurang Saja ({audit.assetDetails.filter(a => !a.isComplete).length})
              </button>
              <button
                className={`btn btn-secondary ${statusFilter === 'COMPLETE' ? 'active' : ''}`}
                style={{
                  fontSize: '0.72rem',
                  padding: '0.2rem 0.5rem',
                  border: 'none',
                  background: statusFilter === 'COMPLETE' ? 'rgba(16,185,129,0.2)' : 'transparent',
                  color: statusFilter === 'COMPLETE' ? '#10b981' : 'inherit',
                  fontWeight: statusFilter === 'COMPLETE' ? 600 : 400
                }}
                onClick={() => setStatusFilter('COMPLETE')}
              >
                ✅ Lengkap ({audit.assetDetails.filter(a => a.isComplete).length})
              </button>
            </div>
          )}

          {/* Filter Kategori Dropdown */}
          <select
            value={selectedCategory}
            onChange={e => setSelectedCategory(e.target.value)}
            style={{
              padding: '0.2rem 0.4rem',
              fontSize: '0.72rem',
              borderRadius: '6px',
              border: '1px solid var(--border-color)',
              background: 'var(--bg-secondary)',
              color: 'var(--text-primary)'
            }}
          >
            <option value="ALL">Semua Kategori ({categoryOptions.length})</option>
            {categoryOptions.map(cat => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </div>

        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
          {/* Search Box */}
          {viewMode === 'detail' && (
            <input
              type="text"
              placeholder="Cari ID aset / stasiun..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{
                padding: '0.25rem 0.5rem',
                fontSize: '0.72rem',
                borderRadius: '6px',
                border: '1px solid var(--border-color)',
                background: 'var(--bg-secondary)',
                color: 'var(--text-primary)',
                width: '140px'
              }}
            />
          )}

          {/* Tombol Ekspor Excel */}
          <button
            className="btn btn-secondary"
            style={{ padding: '0.25rem 0.6rem', fontSize: '0.72rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}
            onClick={handleExportExcel}
            title="Ekspor laporan audit ke Excel (.xlsx)"
          >
            📊 Ekspor Excel
          </button>
        </div>
      </div>

      {/* 4. TAMPILAN TABEL */}
      <div style={{
        background: 'var(--bg-primary)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        overflow: 'hidden',
        maxHeight: '480px',
        overflowY: 'auto'
      }}>
        {/* A. Mode Ringkasan Kategori */}
        {viewMode === 'category' && (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem' }}>
            <thead>
              <tr style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-color)', textAlign: 'left', color: 'var(--text-secondary)', position: 'sticky', top: 0, zIndex: 1 }}>
                <th style={{ padding: '0.5rem' }}>Kategori Aset</th>
                <th style={{ padding: '0.5rem', textAlign: 'center' }}>Periode</th>
                <th style={{ padding: '0.5rem', textAlign: 'center' }}>Target</th>
                <th style={{ padding: '0.5rem', textAlign: 'center' }}>Ada</th>
                <th style={{ padding: '0.5rem', textAlign: 'center' }}>Selisih</th>
                <th style={{ padding: '0.5rem', textAlign: 'center' }}>Progress</th>
                <th style={{ padding: '0.5rem', textAlign: 'center' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {audit.categorySummary
                .filter(c => selectedCategory === 'ALL' || c.category === selectedCategory)
                .map(item => (
                  <tr
                    key={item.category}
                    style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', cursor: 'pointer' }}
                    onClick={() => {
                      setSelectedCategory(item.category);
                      setViewMode('detail');
                    }}
                    title="Klik untuk melihat detail aset kategori ini"
                  >
                    <td style={{ padding: '0.45rem 0.5rem', fontWeight: 600 }}>{item.categoryDisplay}</td>
                    <td style={{ padding: '0.45rem', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.7rem' }}>{item.period}</td>
                    <td style={{ padding: '0.45rem', textAlign: 'center', color: 'var(--text-secondary)' }}>{item.target}</td>
                    <td style={{ padding: '0.45rem', textAlign: 'center', fontWeight: 700 }}>{item.found}</td>
                    <td style={{ padding: '0.45rem', textAlign: 'center', color: item.missing > 0 ? '#ef4444' : 'var(--text-secondary)' }}>
                      {item.missing > 0 ? `-${item.missing}` : '0'}
                    </td>
                    <td style={{ padding: '0.45rem', textAlign: 'center' }}>{item.percent}%</td>
                    <td style={{ padding: '0.45rem', textAlign: 'center' }}>
                      {item.isComplete ? (
                        <span style={{ color: 'var(--accent)', background: 'var(--accent-dim)', padding: '0.15rem 0.4rem', borderRadius: '4px', fontSize: '0.68rem', fontWeight: 600 }}>
                          ✅ LENGKAP
                        </span>
                      ) : (
                        <span style={{ color: '#ef4444', background: 'rgba(239,68,68,0.15)', padding: '0.15rem 0.4rem', borderRadius: '4px', fontSize: '0.68rem', fontWeight: 600 }}>
                          ⚠️ KURANG {item.missing}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        )}

        {/* B. Mode Detail Per Aset */}
        {viewMode === 'detail' && (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem' }}>
            <thead>
              <tr style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-color)', textAlign: 'left', color: 'var(--text-secondary)', position: 'sticky', top: 0, zIndex: 1 }}>
                <th style={{ padding: '0.5rem', width: '35px', textAlign: 'center' }}>No</th>
                <th style={{ padding: '0.5rem' }}>Kategori</th>
                <th style={{ padding: '0.5rem' }}>ID Aset</th>
                <th style={{ padding: '0.5rem', textAlign: 'center' }}>Lokasi</th>
                <th style={{ padding: '0.5rem', textAlign: 'center' }}>Target</th>
                <th style={{ padding: '0.5rem', textAlign: 'center' }}>Ada</th>
                <th style={{ padding: '0.5rem', textAlign: 'center' }}>Status</th>
                <th style={{ padding: '0.5rem' }}>File yang Ditemukan</th>
              </tr>
            </thead>
            <tbody>
              {filteredAssets.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                    Tidak ada aset yang cocok dengan filter.
                  </td>
                </tr>
              ) : (
                filteredAssets.map((a, idx) => (
                  <tr key={a.key} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', background: !a.isComplete ? 'rgba(239,68,68,0.02)' : 'transparent' }}>
                    <td style={{ padding: '0.4rem', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.7rem' }}>{idx + 1}</td>
                    <td style={{ padding: '0.4rem', color: 'var(--text-secondary)', fontSize: '0.7rem' }}>{a.category}</td>
                    <td style={{ padding: '0.4rem', fontWeight: 600, color: a.isComplete ? 'var(--text-primary)' : '#f87171' }}>{a.id}</td>
                    <td style={{ padding: '0.4rem', textAlign: 'center' }}>
                      <span style={{ background: 'rgba(255,255,255,0.06)', padding: '0.1rem 0.35rem', borderRadius: '3px', fontSize: '0.68rem' }}>
                        {a.loc}
                      </span>
                    </td>
                    <td style={{ padding: '0.4rem', textAlign: 'center', color: 'var(--text-secondary)' }}>{a.target}</td>
                    <td style={{ padding: '0.4rem', textAlign: 'center', fontWeight: 700, color: a.isComplete ? '#10b981' : '#ef4444' }}>{a.found}</td>
                    <td style={{ padding: '0.4rem', textAlign: 'center' }}>
                      {a.isComplete ? (
                        <span style={{ color: 'var(--accent)', background: 'var(--accent-dim)', padding: '0.12rem 0.35rem', borderRadius: '4px', fontSize: '0.66rem', fontWeight: 600 }}>
                          ✅ Lengkap
                        </span>
                      ) : (
                        <span style={{ color: '#ef4444', background: 'rgba(239,68,68,0.15)', padding: '0.12rem 0.35rem', borderRadius: '4px', fontSize: '0.66rem', fontWeight: 600 }}>
                          Kurang {a.missing}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '0.4rem', fontSize: '0.7rem', maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={a.matchedFiles.join('\n')}>
                      {a.matchedFiles.length > 0 ? (
                        <span style={{ color: 'var(--text-secondary)' }}>
                          {a.matchedFiles[0]} {a.matchedFiles.length > 1 ? `(+${a.matchedFiles.length - 1} file)` : ''}
                        </span>
                      ) : (
                        <span style={{ color: '#ef4444', fontStyle: 'italic', fontSize: '0.68rem' }}>(Belum ada file)</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
