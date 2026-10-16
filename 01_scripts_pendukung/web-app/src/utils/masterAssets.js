// =============================================================================
// masterAssets.js — Master Data Aset & Audit Kelengkapan Pemeliharaan
// Acuan Resmi: DATA ASET SESUAI SAP UPT RESOR SINTELIS 1.21 BOO TAHUN 2026
// =============================================================================

import * as XLSX from 'xlsx';

const pairs = {
  'BOO-CLT': 'CLT-BOO',
  'CLT-BJD': 'BJD-CLT',
  'MSG-BTT': 'BTT-MSG',
  'CCR-MSG': 'MSG-CCR',
  'BTT-BOP': 'BOP-BTT',
  'BOO-BTT': 'BOP-BTT',
  'BOO-BOP': 'BOP',
};

/**
 * Normalisasi kode petak lintas bolak-balik ke format kanonikal master aset
 */
export function normalizeSectionLoc(loc) {
  if (!loc) return 'UNKNOWN';
  loc = loc.toUpperCase().trim();
  return pairs[loc] || loc;
}

const SECTION_STATION_MAP = {
  'BTT-MSG': ['BTT', 'COS', 'MSG'],
  'MSG-CCR': ['MSG', 'CGB', 'CCR'],
  'CLT-BOO': ['CLT', 'BOO'],
  'BJD-CLT': ['BJD', 'CLT'],
  'BOP-BTT': ['BOP', 'BTT'],
};

/**
 * Cek apakah dua lokasi stasiun/petak saling beririsan atau berada di petak yang sama
 */
export function locsOverlap(loc1, loc2) {
  if (!loc1 || !loc2) return false;
  const n1 = normalizeSectionLoc(loc1);
  const n2 = normalizeSectionLoc(loc2);
  if (n1 === n2) return true;
  const stationsFor = (loc) => {
    const list = [loc];
    if (SECTION_STATION_MAP[loc]) list.push(...SECTION_STATION_MAP[loc]);
    if (loc.includes('-')) list.push(...loc.split('-'));
    return list;
  };
  const s1 = stationsFor(n1);
  const s2 = stationsFor(n2);
  return s1.some(x => s2.includes(x));
}

/**
 * Daftar Master Aset Resor 1.21 BOO Sesuai Dokumen & Form Resmi SAP
 * period:
 *  - 'BULANAN': Pemeliharaan rutin bulanan / 2-mingguan
 *  - '3_BULANAN': Radio Waystation (Target: 9 file)
 *  - '6_BULANAN': Radio Basestation (Target: 5 file)
 *  - '1_TAHUNAN': Khusus Sistem Waystation (Target: 1 file)
 */
export const MASTER_ASSETS = [
  // =========================================================================
  // 1. WESEL (ELEKTRIK & MEKANIK) — Kode BPBYE1 (Frekuensi 2-Mingguan -> Target: 2 file)
  // Total 31 Unit = 62 File
  // =========================================================================
  ...[
    'W13', 'W21A', 'W21B1', 'W21B2', 'W23A', 'W23B',
    'W31A', 'W31B', 'W31D', 'W31E', 'W41', 'W43',
    'W51A1', 'W51A2', 'W61A1', 'W61A2'
  ].map(id => ({ key: `WESEL_${id}_BOO`, category: 'WESEL', categoryDisplay: 'WESEL (ELEKTRIK & MEKANIK)', id, loc: 'BOO', period: 'BULANAN', target: 2 })),

  ...['W11', 'W13', 'W21', 'W23'].map(id => ({ key: `WESEL_${id}_CLT`, category: 'WESEL', categoryDisplay: 'WESEL (ELEKTRIK & MEKANIK)', id, loc: 'CLT', period: 'BULANAN', target: 2 })),
  ...['W25', 'W27A', 'W27B', 'W47A', 'W47C', 'W47D', 'W67'].map(id => ({ key: `WESEL_${id}_BOP`, category: 'WESEL', categoryDisplay: 'WESEL (ELEKTRIK & MEKANIK)', id, loc: 'BOP', period: 'BULANAN', target: 2 })),
  ...['W11', 'W13', 'W21', 'W23'].map(id => ({ key: `WESEL_${id}_MSG`, category: 'WESEL', categoryDisplay: 'WESEL (ELEKTRIK & MEKANIK)', id, loc: 'MSG', period: 'BULANAN', target: 2 })),

  // =========================================================================
  // 2. POINT LOCK (PENGAMAN WESEL W81 BOO) — Kode BPBYE12 (Target: 2 file)
  // =========================================================================
  { key: 'POINTLOCK_W81_BOO', category: 'POINT LOCK', categoryDisplay: 'POINT LOCK (W81 BOO)', id: 'W81', loc: 'BOO', period: 'BULANAN', target: 2 },

  // =========================================================================
  // 3. PERAGA SINYAL — Kode BPBYE3 (Bulanan -> Target: 1 file)
  // Total 125 Unit
  // =========================================================================
  ...[
    'J10', 'J20', 'JL12A', 'JL12B', 'JL22A', 'JL22B', 'JL32A', 'JL32B',
    'JL42A', 'JL42B', 'JL42C', 'JL52', 'JL62B', 'JL72', 'JL92', 'L20', 'L60', 'L62A', 'L80', 'MJ20'
  ].map(id => ({ key: `SINYAL_${id}_BOO`, category: 'PERAGA SINYAL', categoryDisplay: 'PERAGA SINYAL', id, loc: 'BOO', period: 'BULANAN', target: 1 })),

  ...['J10', 'J12A', 'J12B', 'J14', 'J20', 'J22', 'J24', 'MJ14', 'MJ20'].map(id => ({ key: `SINYAL_${id}_CLT`, category: 'PERAGA SINYAL', categoryDisplay: 'PERAGA SINYAL', id, loc: 'CLT', period: 'BULANAN', target: 1 })),
  ...['J10', 'J12A', 'J12B', 'J14', 'J20', 'J22A', 'J22B', 'J24'].map(id => ({ key: `SINYAL_${id}_BTT`, category: 'PERAGA SINYAL', categoryDisplay: 'PERAGA SINYAL', id, loc: 'BTT', period: 'BULANAN', target: 1 })),
  ...['J28', 'J48', 'JL26A', 'JL26B', 'JL46A', 'JL46B', 'JL66B', 'L28', 'L47A', 'L47B', 'L68', 'UJ26B'].map(id => ({ key: `SINYAL_${id}_BOP`, category: 'PERAGA SINYAL', categoryDisplay: 'PERAGA SINYAL', id, loc: 'BOP', period: 'BULANAN', target: 1 })),
  ...['MJ10', 'MJ20', 'MJ28', 'MJ48'].map(id => ({ key: `SINYAL_${id}_BOP-BTT`, category: 'PERAGA SINYAL', categoryDisplay: 'PERAGA SINYAL', id, loc: 'BOP-BTT', period: 'BULANAN', target: 1 })),
  ...['B101', 'B201', 'MB101', 'MB201', 'MJ10', 'MJ14', 'MJ20', 'MJ24'].map(id => ({ key: `SINYAL_${id}_BTT-MSG`, category: 'PERAGA SINYAL', categoryDisplay: 'PERAGA SINYAL', id, loc: 'BTT-MSG', period: 'BULANAN', target: 1 })),
  ...['B101', 'B201', 'MB101', 'MB201', 'MJ14', 'MJ24'].map(id => ({ key: `SINYAL_${id}_MSG-CCR`, category: 'PERAGA SINYAL', categoryDisplay: 'PERAGA SINYAL', id, loc: 'MSG-CCR', period: 'BULANAN', target: 1 })),
  ...['J10', 'J12', 'J14', 'J20', 'J22A', 'J22B', 'J24', 'UJ12', 'UJ22B'].map(id => ({ key: `SINYAL_${id}_MSG`, category: 'PERAGA SINYAL', categoryDisplay: 'PERAGA SINYAL', id, loc: 'MSG', period: 'BULANAN', target: 1 })),
  ...['B101', 'B102', 'B205', 'B206', 'B207', 'UB101', 'UB102', 'UB205', 'UB206'].map(id => ({ key: `SINYAL_${id}_BJD-CLT`, category: 'PERAGA SINYAL', categoryDisplay: 'PERAGA SINYAL', id, loc: 'BJD-CLT', period: 'BULANAN', target: 1 })),
  ...[
    'B101', 'B102', 'B103', 'B104', 'B105', 'B106', 'B107', 'B108', 'B109', 'B110', 'B111', 'B112',
    'B201', 'B202', 'B203', 'B204', 'B205', 'B206', 'B207', 'B208', 'B209', 'B210', 'B211', 'B212', 'B213', 'B214',
    'UB102', 'UB103', 'UB104', 'UB105', 'UB106', 'UB110',
    'UB202', 'UB206', 'UB207', 'UB208', 'UB209', 'UB210', 'UB211', 'UB212'
  ].map(id => ({ key: `SINYAL_${id}_CLT-BOO`, category: 'PERAGA SINYAL', categoryDisplay: 'PERAGA SINYAL', id, loc: 'CLT-BOO', period: 'BULANAN', target: 1 })),

  // =========================================================================
  // 4. DETEKSI KA (AXLE COUNTER) — Kode BPBYE7 (Bulanan -> Target: 1 file)
  // Total 139 Unit
  // =========================================================================
  ...[
    'ZP 10A', 'ZP 10B', 'ZP 12A', 'ZP 12B', 'ZP 13', 'ZP 20A', 'ZP 20B', 'ZP 20C',
    'ZP 21A', 'ZP 21B', 'ZP 21C', 'ZP 22A', 'ZP 22B', 'ZP 23A', 'ZP 23B', 'ZP 24A', 'ZP 24B',
    'ZP 31A', 'ZP 31B', 'ZP 31C', 'ZP 31D', 'ZP 31E', 'ZP 32A', 'ZP 32B', 'ZP 41',
    'ZP 42A', 'ZP 42B', 'ZP 42C', 'ZP 52', 'ZP 60', 'ZP 61', 'ZP 62A', 'ZP 62B', 'ZP 72', 'ZP 92'
  ].map(id => ({ key: `AXL_${id}_BOO`, category: 'AXLE COUNTER', categoryDisplay: 'DETEKSI KA (AXLE COUNTER)', id, loc: 'BOO', period: 'BULANAN', target: 1 })),

  ...['ZP 10A', 'ZP 10B', 'ZP 11', 'ZP 12A', 'ZP 12B', 'ZP 13', 'ZP 14A', 'ZP 14B', 'ZP 20A', 'ZP 20B', 'ZP 22A', 'ZP 22B', 'ZP 24A', 'ZP 24B'].map(id => ({ key: `AXL_${id}_CLT`, category: 'AXLE COUNTER', categoryDisplay: 'DETEKSI KA (AXLE COUNTER)', id, loc: 'CLT', period: 'BULANAN', target: 1 })),
  ...['ZP 10B', 'ZP 12A', 'ZP 12B', 'ZP 14A', 'ZP 20B', 'ZP 22A', 'ZP 22B', 'ZP 24A'].map(id => ({ key: `AXL_${id}_BTT`, category: 'AXLE COUNTER', categoryDisplay: 'DETEKSI KA (AXLE COUNTER)', id, loc: 'BTT', period: 'BULANAN', target: 1 })),
  ...[
    'ZP 25', 'ZP 26A', 'ZP 26B', 'ZP 26C', 'ZP 27A', 'ZP 27B', 'ZP 27C', 'ZP 28A', 'ZP 28B',
    'ZP 46A', 'ZP 46B', 'ZP 47A', 'ZP 47B', 'ZP 47C', 'ZP 47D', 'ZP 48A', 'ZP 48B', 'ZP 66A', 'ZP 66B', 'ZP 68'
  ].map(id => ({ key: `AXL_${id}_BOP`, category: 'AXLE COUNTER', categoryDisplay: 'DETEKSI KA (AXLE COUNTER)', id, loc: 'BOP', period: 'BULANAN', target: 1 })),
  ...['ZP 10A', 'ZP 20A'].map(id => ({ key: `AXL_${id}_BTT-BOP`, category: 'AXLE COUNTER', categoryDisplay: 'DETEKSI KA (AXLE COUNTER)', id, loc: 'BTT-BOP', period: 'BULANAN', target: 1 })),
  ...['ZP 28C', 'ZP 48C'].map(id => ({ key: `AXL_${id}_BOP-BTT`, category: 'AXLE COUNTER', categoryDisplay: 'DETEKSI KA (AXLE COUNTER)', id, loc: 'BOP-BTT', period: 'BULANAN', target: 1 })),
  ...[
    'ZP 10B', 'ZP 10C', 'ZP 11', 'ZP 12A', 'ZP 12B', 'ZP 13', 'ZP 14A', 'ZP 14B',
    'ZP 20B', 'ZP 20C', 'ZP 22A', 'ZP 22B', 'ZP 24A', 'ZP 24B'
  ].map(id => ({ key: `AXL_${id}_MSG`, category: 'AXLE COUNTER', categoryDisplay: 'DETEKSI KA (AXLE COUNTER)', id, loc: 'MSG', period: 'BULANAN', target: 1 })),
  ...['ZP 101A', 'ZP 101B', 'ZP 201A', 'ZP 201B', 'ZP 10A', 'ZP 20A', 'ZP 14B', 'ZP 24B'].map(id => ({ key: `AXL_${id}_BTT-MSG`, category: 'AXLE COUNTER', categoryDisplay: 'DETEKSI KA (AXLE COUNTER)', id, loc: 'BTT-MSG', period: 'BULANAN', target: 1 })),
  ...['ZP 101A', 'ZP 101B', 'ZP 201A', 'ZP 201B', 'ZP 14C', 'ZP 24C'].map(id => ({ key: `AXL_${id}_MSG-CCR`, category: 'AXLE COUNTER', categoryDisplay: 'DETEKSI KA (AXLE COUNTER)', id, loc: 'MSG-CCR', period: 'BULANAN', target: 1 })),
  ...['ZP 101', 'ZP 102', 'ZP 205', 'ZP 206', 'ZP 207'].map(id => ({ key: `AXL_${id}_BJD-CLT`, category: 'AXLE COUNTER', categoryDisplay: 'DETEKSI KA (AXLE COUNTER)', id, loc: 'BJD-CLT', period: 'BULANAN', target: 1 })),
  ...[
    'ZP 101', 'ZP 102', 'ZP 103', 'ZP 104', 'ZP 105', 'ZP 106', 'ZP 107', 'ZP 108', 'ZP 109', 'ZP 110', 'ZP 111', 'ZP 112',
    'ZP 201', 'ZP 202', 'ZP 203', 'ZP 204', 'ZP 205', 'ZP 206', 'ZP 207', 'ZP 208', 'ZP 209', 'ZP 210', 'ZP 211', 'ZP 212', 'ZP 213'
  ].map(id => ({ key: `AXL_${id}_CLT-BOO`, category: 'AXLE COUNTER', categoryDisplay: 'DETEKSI KA (AXLE COUNTER)', id, loc: 'CLT-BOO', period: 'BULANAN', target: 1 })),

  // =========================================================================
  // 5. PINTU PERLINTASAN (JPL) — Kode BPBKS17 (Target: 10 file)
  // =========================================================================
  { key: 'JPL_2_BOO', category: 'PINTU PERLINTASAN', categoryDisplay: 'PINTU PERLINTASAN (JPL)', id: 'JPL 2', loc: 'BOO', period: 'BULANAN', target: 1 },
  { key: 'JPL_04_BOP', category: 'PINTU PERLINTASAN', categoryDisplay: 'PINTU PERLINTASAN (JPL)', id: 'JPL 04', loc: 'BOP', period: 'BULANAN', target: 1 },
  { key: 'JPL_07_BOP-BTT', category: 'PINTU PERLINTASAN', categoryDisplay: 'PINTU PERLINTASAN (JPL)', id: 'JPL 07', loc: 'BOP-BTT', period: 'BULANAN', target: 1 },
  { key: 'JPL_BNR_BOP-BTT', category: 'PINTU PERLINTASAN', categoryDisplay: 'PINTU PERLINTASAN (JPL)', id: 'JPL BNR', loc: 'BOP-BTT', period: 'BULANAN', target: 1 },
  { key: 'JPL_11_BTT', category: 'PINTU PERLINTASAN', categoryDisplay: 'PINTU PERLINTASAN (JPL)', id: 'JPL 11', loc: 'BTT', period: 'BULANAN', target: 1 },
  { key: 'JPL_15_CGB', category: 'PINTU PERLINTASAN', categoryDisplay: 'PINTU PERLINTASAN (JPL)', id: 'JPL 15', loc: 'CGB', period: 'BULANAN', target: 1 },
  { key: 'JPL_16_CGB', category: 'PINTU PERLINTASAN', categoryDisplay: 'PINTU PERLINTASAN (JPL)', id: 'JPL 16', loc: 'CGB', period: 'BULANAN', target: 1 },
  { key: 'JPL_26N_CLT', category: 'PINTU PERLINTASAN', categoryDisplay: 'PINTU PERLINTASAN (JPL)', id: 'JPL 26N', loc: 'CLT', period: 'BULANAN', target: 1 },
  { key: 'JPL_27_CLT-BOO', category: 'PINTU PERLINTASAN', categoryDisplay: 'PINTU PERLINTASAN (JPL)', id: 'JPL 27', loc: 'CLT-BOO', period: 'BULANAN', target: 1 },
  { key: 'JPL_28_CLT-BOO', category: 'PINTU PERLINTASAN', categoryDisplay: 'PINTU PERLINTASAN (JPL)', id: 'JPL 28', loc: 'CLT-BOO', period: 'BULANAN', target: 1 },

  // =========================================================================
  // 6. TELKOM PINTU PERLINTASAN (PTPP) (11 unit)
  // =========================================================================
  { key: 'PTPP_01_BOO', category: 'PTPP', categoryDisplay: 'TELKOM JPL (PTPP)', id: 'PTPP JPL 01', loc: 'BOO', period: 'BULANAN', target: 1 },
  { key: 'PTPP_02_BOO', category: 'PTPP', categoryDisplay: 'TELKOM JPL (PTPP)', id: 'PTPP JPL 02', loc: 'BOO', period: 'BULANAN', target: 1 },
  { key: 'PTPP_04_BOP', category: 'PTPP', categoryDisplay: 'TELKOM JPL (PTPP)', id: 'PTPP JPL 04', loc: 'BOP', period: 'BULANAN', target: 1 },
  { key: 'PTPP_07_BOP-BTT', category: 'PTPP', categoryDisplay: 'TELKOM JPL (PTPP)', id: 'PTPP JPL 07', loc: 'BOP-BTT', period: 'BULANAN', target: 1 },
  { key: 'PTPP_BNR_BOP-BTT', category: 'PTPP', categoryDisplay: 'TELKOM JPL (PTPP)', id: 'PTPP JPL BNR', loc: 'BOP-BTT', period: 'BULANAN', target: 1 },
  { key: 'PTPP_11_BTT', category: 'PTPP', categoryDisplay: 'TELKOM JPL (PTPP)', id: 'PTPP JPL 11', loc: 'BTT', period: 'BULANAN', target: 1 },
  { key: 'PTPP_15_CGB', category: 'PTPP', categoryDisplay: 'TELKOM JPL (PTPP)', id: 'PTPP JPL 15', loc: 'CGB', period: 'BULANAN', target: 1 },
  { key: 'PTPP_16_CGB', category: 'PTPP', categoryDisplay: 'TELKOM JPL (PTPP)', id: 'PTPP JPL 16', loc: 'CGB', period: 'BULANAN', target: 1 },
  { key: 'PTPP_26N_CLT', category: 'PTPP', categoryDisplay: 'TELKOM JPL (PTPP)', id: 'PTPP JPL 26N', loc: 'CLT', period: 'BULANAN', target: 1 },
  { key: 'PTPP_27_CLT-BOO', category: 'PTPP', categoryDisplay: 'TELKOM JPL (PTPP)', id: 'PTPP JPL 27', loc: 'CLT-BOO', period: 'BULANAN', target: 1 },
  { key: 'PTPP_28_CLT-BOO', category: 'PTPP', categoryDisplay: 'TELKOM JPL (PTPP)', id: 'PTPP JPL 28', loc: 'CLT-BOO', period: 'BULANAN', target: 1 },

  // =========================================================================
  // 7. CATU DAYA / RECTIFIER (9 unit)
  // =========================================================================
  { key: 'CATUDAYA_CLT', category: 'CATU DAYA', categoryDisplay: 'CATU DAYA / RECTIFIER', id: 'CATU DAYA', loc: 'CLT', period: 'BULANAN', target: 1 },
  { key: 'CATUDAYA_BOO_1', category: 'CATU DAYA', categoryDisplay: 'CATU DAYA / RECTIFIER', id: 'CATU DAYA ER SINYAL', loc: 'BOO', period: 'BULANAN', target: 1 },
  { key: 'CATUDAYA_BOO_2', category: 'CATU DAYA', categoryDisplay: 'CATU DAYA / RECTIFIER', id: 'CATU DAYA ER RADIO', loc: 'BOO', period: 'BULANAN', target: 1 },
  { key: 'CATUDAYA_BOP', category: 'CATU DAYA', categoryDisplay: 'CATU DAYA / RECTIFIER', id: 'CATU DAYA', loc: 'BOP', period: 'BULANAN', target: 1 },
  { key: 'CATUDAYA_BTT', category: 'CATU DAYA', categoryDisplay: 'CATU DAYA / RECTIFIER', id: 'CATU DAYA', loc: 'BTT', period: 'BULANAN', target: 1 },
  { key: 'CATUDAYA_COS_1', category: 'CATU DAYA', categoryDisplay: 'CATU DAYA / RECTIFIER', id: 'CATU DAYA ER SINYAL', loc: 'COS', period: 'BULANAN', target: 1 },
  { key: 'CATUDAYA_COS_2', category: 'CATU DAYA', categoryDisplay: 'CATU DAYA / RECTIFIER', id: 'CATU DAYA ER RADIO', loc: 'COS', period: 'BULANAN', target: 1 },
  { key: 'CATUDAYA_MSG', category: 'CATU DAYA', categoryDisplay: 'CATU DAYA / RECTIFIER', id: 'CATU DAYA', loc: 'MSG', period: 'BULANAN', target: 1 },
  { key: 'CATUDAYA_CGB', category: 'CATU DAYA', categoryDisplay: 'CATU DAYA / RECTIFIER', id: 'CATU DAYA', loc: 'CGB', period: 'BULANAN', target: 1 },

  // =========================================================================
  // 8. OPTIK OTB (22 unit)
  // =========================================================================
  ...['CLT_1', 'CLT_2'].map((_, i) => ({ key: `SO_CLT_${i+1}`, category: 'SERAT OPTIK', categoryDisplay: 'SERAT OPTIK (OTB)', id: `OTB ${i+1}`, loc: 'CLT', period: 'BULANAN', target: 1 })),
  ...['CLT-BOO_1', 'CLT-BOO_2'].map((_, i) => ({ key: `SO_CLT-BOO_${i+1}`, category: 'SERAT OPTIK', categoryDisplay: 'SERAT OPTIK (OTB)', id: `OTB ${i+1}`, loc: 'CLT-BOO', period: 'BULANAN', target: 1 })),
  ...['BOO_1', 'BOO_2', 'BOO_3', 'BOO_4'].map((_, i) => ({ key: `SO_BOO_${i+1}`, category: 'SERAT OPTIK', categoryDisplay: 'SERAT OPTIK (OTB)', id: `OTB ${i+1}`, loc: 'BOO', period: 'BULANAN', target: 1 })),
  { key: 'SO_BOP_1', category: 'SERAT OPTIK', categoryDisplay: 'SERAT OPTIK (OTB)', id: 'OTB 1', loc: 'BOP', period: 'BULANAN', target: 1 },
  ...['BOP-BTT_1', 'BOP-BTT_2'].map((_, i) => ({ key: `SO_BOP-BTT_${i+1}`, category: 'SERAT OPTIK', categoryDisplay: 'SERAT OPTIK (OTB)', id: `OTB ${i+1}`, loc: 'BOP-BTT', period: 'BULANAN', target: 1 })),
  ...['BTT_1', 'BTT_2', 'BTT_3'].map((_, i) => ({ key: `SO_BTT_${i+1}`, category: 'SERAT OPTIK', categoryDisplay: 'SERAT OPTIK (OTB)', id: `OTB ${i+1}`, loc: 'BTT', period: 'BULANAN', target: 1 })),
  ...['COS_1', 'COS_2'].map((_, i) => ({ key: `SO_COS_${i+1}`, category: 'SERAT OPTIK', categoryDisplay: 'SERAT OPTIK (OTB)', id: `OTB ${i+1}`, loc: 'COS', period: 'BULANAN', target: 1 })),
  ...['MSG_1', 'MSG_2'].map((_, i) => ({ key: `SO_MSG_${i+1}`, category: 'SERAT OPTIK', categoryDisplay: 'SERAT OPTIK (OTB)', id: `OTB ${i+1}`, loc: 'MSG', period: 'BULANAN', target: 1 })),
  ...['CGB_1', 'CGB_2', 'CGB_3', 'CGB_4'].map((_, i) => ({ key: `SO_CGB_${i+1}`, category: 'SERAT OPTIK', categoryDisplay: 'SERAT OPTIK (OTB)', id: `OTB ${i+1}`, loc: 'CGB', period: 'BULANAN', target: 1 })),

  // =========================================================================
  // 9. PDSE (PERALATAN DALAM) — Kode BPBYE5 (Bulanan -> Target: 1 file)
  // =========================================================================
  ...['CLT', 'BOO', 'BOP', 'BTT', 'COS', 'MSG', 'CGB'].map(loc => ({
    key: `PDSE_${loc}`,
    category: 'PDSE',
    categoryDisplay: 'PERALATAN DALAM (PDSE)',
    id: 'PDSE',
    loc,
    period: 'BULANAN',
    target: 1
  })),

  // =========================================================================
  // 10. PTDS (TELEKOMUNIKASI STASIUN) (Bulanan -> Target: 1 file, BOO: 2 file)
  // =========================================================================
  { key: 'PTDS_BOO', category: 'PTDS', categoryDisplay: 'TELKOM STASIUN (PTDS)', id: 'PTDS', loc: 'BOO', period: 'BULANAN', target: 2 },
  ...['CLT', 'BOP', 'BTT', 'COS', 'MSG', 'CGB'].map(loc => ({
    key: `PTDS_${loc}`,
    category: 'PTDS',
    categoryDisplay: 'TELKOM STASIUN (PTDS)',
    id: 'PTDS',
    loc,
    period: 'BULANAN',
    target: 1
  })),

  // =========================================================================
  // 11. PTLS (TELEKOMUNIKASI LUAR STASIUN) (Bulanan -> Total 8 file)
  // =========================================================================
  { key: 'PTLS_BOO_1', category: 'PTLS', categoryDisplay: 'TELKOM LUAR STASIUN (PTLS)', id: 'PTLS 1', loc: 'BOO', period: 'BULANAN', target: 1 },
  { key: 'PTLS_BOO_2', category: 'PTLS', categoryDisplay: 'TELKOM LUAR STASIUN (PTLS)', id: 'PTLS 2', loc: 'BOO', period: 'BULANAN', target: 1 },
  { key: 'PTLS_BOP', category: 'PTLS', categoryDisplay: 'TELKOM LUAR STASIUN (PTLS)', id: 'PTLS', loc: 'BOP', period: 'BULANAN', target: 1 },
  { key: 'PTLS_BTT', category: 'PTLS', categoryDisplay: 'TELKOM LUAR STASIUN (PTLS)', id: 'PTLS', loc: 'BTT', period: 'BULANAN', target: 1 },
  { key: 'PTLS_COS', category: 'PTLS', categoryDisplay: 'TELKOM LUAR STASIUN (PTLS)', id: 'PTLS', loc: 'COS', period: 'BULANAN', target: 1 },
  { key: 'PTLS_MSG_1', category: 'PTLS', categoryDisplay: 'TELKOM LUAR STASIUN (PTLS)', id: 'PTLS 1', loc: 'MSG', period: 'BULANAN', target: 1 },
  { key: 'PTLS_MSG_2', category: 'PTLS', categoryDisplay: 'TELKOM LUAR STASIUN (PTLS)', id: 'PTLS 2', loc: 'MSG', period: 'BULANAN', target: 1 },
  { key: 'PTLS_CGB', category: 'PTLS', categoryDisplay: 'TELKOM LUAR STASIUN (PTLS)', id: 'PTLS', loc: 'CGB', period: 'BULANAN', target: 1 },

  // =========================================================================
  // 12. CTC / CTS (Bulanan -> Target: 2 file)
  // =========================================================================
  { key: 'CTC_CLT', category: 'CTC-CTS', categoryDisplay: 'CTC / CTS', id: 'CTS', loc: 'CLT', period: 'BULANAN', target: 1 },
  { key: 'CTC_BOO', category: 'CTC-CTS', categoryDisplay: 'CTC / CTS', id: 'CTS', loc: 'BOO', period: 'BULANAN', target: 1 },

  // =========================================================================
  // 13. RADIO WAYSTATION — 3 BULANAN (Target: 9 file)
  // =========================================================================
  ...['BOO', 'CLT', 'BTT', 'BOP', 'COS', 'MSG', 'CGB', 'CCR', 'BJD'].map(loc => ({
    key: `WAYSTATION_${loc}`,
    category: 'RADIO WAYSTATION',
    categoryDisplay: 'RADIO WAYSTATION (3 BULANAN)',
    id: `WS ${loc}`,
    loc,
    period: '3_BULANAN',
    target: 1
  })),

  // =========================================================================
  // 14. RADIO BASESTATION — 6 BULANAN (Target: 5 file)
  // =========================================================================
  ...['BOO', 'BTT', 'COS', 'MSG', 'CGB'].map(loc => ({
    key: `BASESTATION_${loc}`,
    category: 'RADIO BASESTATION',
    categoryDisplay: 'RADIO BASESTATION (6 BULANAN)',
    id: `BS ${loc}`,
    loc,
    period: '6_BULANAN',
    target: 1
  })),

  // =========================================================================
  // 15. SISTEM WAYSTATION — 1 TAHUNAN (Target: 1 file)
  // =========================================================================
  {
    key: 'SISTEM_WAYSTATION_BOO',
    category: 'SISTEM WAYSTATION',
    categoryDisplay: 'SISTEM WAYSTATION (1 TAHUNAN)',
    id: 'SISTEM WS BOO',
    loc: 'BOO',
    period: '1_TAHUNAN',
    target: 1
  }
];

// Helper Set untuk pencarian cepat
const SHORT_CODES = new Set(['BOO', 'CLT', 'BTT', 'BOP', 'COS', 'MSG', 'CGB', 'CCR', 'BJD']);
const LOC_MAP = {
  'MASENG': 'MSG', 'CICURUG': 'CCR', 'CILEBUT': 'CLT', 'BOGOR': 'BOO',
  'BATUTULIS': 'BTT', 'BATU TULIS': 'BTT', 'BOGORPALEDANG': 'BOP', 'PALEDANG': 'BOP',
  'CIOMAS': 'COS', 'CIGOMBONG': 'CGB', 'BOJONGGEDE': 'BJD', 'DEPOK': 'BOO'
};

export function extractLocFromText(text) {
  text = text.toUpperCase();
  const dualMatch = text.match(/\b(BJD|CLT|BOO|BOP|BTT|COS|MSG|CGB|CCR)-(BJD|CLT|BOO|BOP|BTT|COS|MSG|CGB|CCR)\b/);
  if (dualMatch) return normalizeSectionLoc(dualMatch[0]);

  for (const [full, code] of Object.entries(LOC_MAP)) {
    if (new RegExp(`\\b${full}\\b`).test(text)) return code;
  }
  for (const code of SHORT_CODES) {
    if (new RegExp(`\\b${code}\\b`).test(text)) return code;
  }
  return 'UNKNOWN';
}

/**
 * Mencocokkan nama file PDF ke kategori dan atribut aset master
 * @param {string} filename Nama file PDF
 * @returns {{ category: string, id: string, loc: string, period: string } | null}
 */
export function matchFileToAsset(filename) {
  if (!filename || typeof filename !== 'string') return null;
  // Hapus ekstensi dan penanda duplikat (2), (3) jika ada
  const base = filename.replace(/\s*\(\d+\)\.pdf$/i, '').replace(/\.pdf$/i, '').trim();

  const m = base.match(/^(?:PERAWATAN|PEMERIKSAAN)\s+(.*?)(?:\s+\d{2}-\d{2}-\d{4})?$/i);
  const s = (m ? m[1] : base).trim().toUpperCase();

  const is3Bulanan = s.includes('3 BULAN') || s.includes('3BULAN') || s.includes('TRIWULAN');
  const is6Bulanan = s.includes('6 BULAN') || s.includes('6BULAN') || s.includes('SEMESTER');
  const is1Tahunan = s.includes('1 TAHUN') || s.includes('TAHUNAN');

  // 1. SISTEM WAYSTATION (1 Tahunan)
  if (s.includes('SISTEM WAYSTATION') || (s.includes('WAYSTATION') && is1Tahunan)) {
    return { category: 'SISTEM WAYSTATION', id: 'SISTEM WS BOO', loc: extractLocFromText(s) || 'BOO', period: '1_TAHUNAN' };
  }

  // 2. RADIO WAYSTATION (3 Bulanan)
  if (s.includes('RADIO WAYSTATION') || (s.includes('WAYSTATION') && !s.includes('BASESTATION'))) {
    const loc = extractLocFromText(s);
    return { category: 'RADIO WAYSTATION', id: `WS ${loc}`, loc, period: '3_BULANAN' };
  }

  // 3. RADIO BASESTATION (6 Bulanan)
  if (s.includes('BASESTATION') || s.includes('BASE STATION')) {
    const loc = extractLocFromText(s);
    return { category: 'RADIO BASESTATION', id: `BS ${loc}`, loc, period: '6_BULANAN' };
  }

  // 4. WESEL
  const mw = s.match(/^WESEL\s+(W[0-9A-Z]+)\s+([A-Z-]+)$/i);
  if (mw) {
    return { category: 'WESEL', id: mw[1].toUpperCase(), loc: extractLocFromText(mw[2]), period: 'BULANAN' };
  }

  // 5. POINT LOCK
  if (s.includes('POINT LOCK') || s.includes('W81')) {
    const loc = extractLocFromText(s) || 'BOO';
    return { category: 'POINT LOCK', id: 'W81', loc, period: 'BULANAN' };
  }

  // 6. AXLE COUNTER / DETEKSI KA
  if (s.includes('AXLE COUNTER') || s.includes('DETEKSI KA') || /\bZP\s*[0-9]/i.test(s)) {
    const mz = s.match(/(ZP\s*[0-9]{1,3}[A-Z]*)/i);
    const zId = mz ? mz[1].replace(/\s+/g, ' ').toUpperCase() : 'ZP';
    const loc = extractLocFromText(s);
    return { category: 'AXLE COUNTER', id: zId, loc, period: 'BULANAN' };
  }

  // 7. PTPP (TELKOM JPL) — Harus dicek sebelum aturan JPL umum!
  if (s.includes('PTPP')) {
    const mj = s.match(/(JPL\s*[0-9A-Z]+)/i);
    const id = mj ? `PTPP ${mj[1].toUpperCase()}` : 'PTPP';
    const loc = extractLocFromText(s);
    return { category: 'PTPP', id, loc, period: 'BULANAN' };
  }

  // 8. SERAT OPTIK / OTB — Harus dicek sebelum aturan JPL / Sinyal umum!
  if (s.includes('SERAT OPTIK') || s.includes('OTB') || s.includes('FIBER OPTIK')) {
    const loc = extractLocFromText(s);
    let id = 'OTB';
    if (s.includes('ER RADIO')) id = 'ER RADIO';
    else if (s.includes('RUANG RADIO')) id = 'RUANG RADIO';
    else if (s.includes('ER TELKOM')) id = 'ER TELKOM';
    else if (s.includes('ER SINYAL')) id = 'ER SINYAL';
    else if (loc.includes('-')) id = 'PETAK';
    return { category: 'SERAT OPTIK', id, loc, period: 'BULANAN' };
  }

  // 9. PERAGA SINYAL
  if (s.includes('SINYAL') && !s.includes('CATU DAYA')) {
    const loc = extractLocFromText(s);
    const mSig = s.match(/^SINYAL\s+(?:MUKA\s+)?([A-Z0-9.]+)/i);
    let sigId = mSig ? mSig[1].replace(/\./g, '').toUpperCase() : '';
    if (['BOO', 'CLT', 'BTT', 'BOP', 'COS', 'MSG', 'CGB', 'CCR', 'BJD'].includes(sigId)) {
      sigId = '';
    }
    return { category: 'PERAGA SINYAL', id: sigId, loc, period: 'BULANAN' };
  }

  // 10. CATU DAYA
  if (s.includes('CATU DAYA') || s.includes('RECTIFIER')) {
    const loc = extractLocFromText(s);
    let id = 'CATU DAYA';
    if (s.includes('ER RADIO')) id = 'CATU DAYA ER RADIO';
    else if (s.includes('ER SINYAL')) id = 'CATU DAYA ER SINYAL';
    return { category: 'CATU DAYA', id, loc, period: 'BULANAN' };
  }

  // 11. PINTU PERLINTASAN (JPL)
  if (s.includes('PINTU PERLINTASAN') || /\bJPL\b/i.test(s)) {
    const mj = s.match(/(JPL\s*[0-9A-Z]+)/i);
    const jplId = mj ? mj[1].toUpperCase() : 'JPL';
    const loc = extractLocFromText(s);
    return { category: 'PINTU PERLINTASAN', id: jplId, loc, period: 'BULANAN' };
  }

  // 12. PDSE
  if (s.includes('PDSE') || s.includes('PERALATAN DALAM')) {
    const loc = extractLocFromText(s);
    return { category: 'PDSE', id: 'PDSE', loc, period: 'BULANAN' };
  }

  // 13. PTDS
  if (s.includes('PTDS') || s.includes('DI STASIUN') || s.includes('TELEKOMUNIKASI STASIUN')) {
    const loc = extractLocFromText(s);
    return { category: 'PTDS', id: 'PTDS', loc, period: 'BULANAN' };
  }

  // 14. PTLS
  if (s.includes('PTLS') || s.includes('LUAR STASIUN') || s.includes('TELEKOMUNIKASI LUAR STASIUN')) {
    const loc = extractLocFromText(s);
    return { category: 'PTLS', id: 'PTLS', loc, period: 'BULANAN' };
  }

  // 15. CTC / CTS
  if (s.includes('CTC') || s.includes('CTS')) {
    const loc = extractLocFromText(s);
    return { category: 'CTC-CTS', id: 'CTS', loc, period: 'BULANAN' };
  }

  return null;
}

/**
 * Melakukan audit kelengkapan aset dari daftar file yang diberikan
 * @param {Array<string|{name: string}>} files Daftar nama file atau objek file
 * @param {string} periodFilter 'BULANAN' | '3_BULANAN' | '6_BULANAN' | '1_TAHUNAN' | 'ALL'
 * @returns {object} Hasil audit terstruktur
 */
export function performAssetAudit(files, periodFilter = 'BULANAN') {
  const fileNames = (files || []).map(f => (typeof f === 'string' ? f : f.name || '')).filter(Boolean);

  const masterScope = periodFilter === 'ALL'
    ? MASTER_ASSETS
    : MASTER_ASSETS.filter(a => a.period === periodFilter);

  const assetMap = new Map();
  masterScope.forEach(a => {
    assetMap.set(a.key, {
      ...a,
      found: 0,
      matchedFiles: [],
    });
  });

  const unmatchedFiles = [];
  const DESCRIPTIVE_CATEGORIES = new Set(['PDSE', 'PTDS', 'PTLS', 'CATU DAYA', 'SERAT OPTIK', 'CTC-CTS']);

  for (const fname of fileNames) {
    const matched = matchFileToAsset(fname);
    if (!matched) {
      unmatchedFiles.push({ filename: fname, reason: 'Format nama file tidak teridentifikasi' });
      continue;
    }

    let matchedKey = null;

    // Helper ID matcher: persis sama atau normalisasi format tanpa spasi/leading zeros
    const idMatches = (masterId, fileId) => {
      if (!masterId || !fileId) return false;
      if (masterId.toUpperCase().trim() === fileId.toUpperCase().trim()) return true;
      const mNorm = masterId.toUpperCase().replace(/\s+/g, '').replace(/^JPL0*/i, 'JPL').replace(/^PTPP0*/i, 'PTPP');
      const fNorm = fileId.toUpperCase().replace(/\s+/g, '').replace(/^JPL0*/i, 'JPL').replace(/^PTPP0*/i, 'PTPP');
      return mNorm === fNorm;
    };

    // 1. Exact match (category + id + loc)
    for (const [key, a] of assetMap.entries()) {
      if (a.category === matched.category && normalizeSectionLoc(a.loc) === normalizeSectionLoc(matched.loc)) {
        if (idMatches(a.id, matched.id)) {
          matchedKey = key;
          break;
        }
      }
    }

    // 2. Cross-location match untuk aset spesifik ber-ID (B214 di CLT-BOO cocok ke B214 di BOO-CLT/BOO/CLT)
    if (!matchedKey && matched.id && !DESCRIPTIVE_CATEGORIES.has(matched.category)) {
      for (const [key, a] of assetMap.entries()) {
        if (a.category === matched.category && idMatches(a.id, matched.id)) {
          if (locsOverlap(a.loc, matched.loc)) {
            matchedKey = key;
            break;
          }
        }
      }
    }

    // 3. Unique ID di kategori aset master
    if (!matchedKey && matched.id && !DESCRIPTIVE_CATEGORIES.has(matched.category)) {
      const candidates = [];
      for (const [key, a] of assetMap.entries()) {
        if (a.category === matched.category && idMatches(a.id, matched.id)) {
          candidates.push(key);
        }
      }
      if (candidates.length === 1) {
        matchedKey = candidates[0];
      }
    }

    // 4. Lokasi match untuk aset deskriptif (PDSE, PTDS, PTLS, Catu Daya, Serat Optik)
    if (!matchedKey && DESCRIPTIVE_CATEGORIES.has(matched.category)) {
      // 4a. Prioritas 1: Lokasi eksak
      for (const [key, a] of assetMap.entries()) {
        if (a.category === matched.category && normalizeSectionLoc(a.loc) === normalizeSectionLoc(matched.loc)) {
          if (a.found < a.target) {
            matchedKey = key;
            break;
          } else if (!matchedKey) {
            matchedKey = key;
          }
        }
      }
      // 4b. Prioritas 2: Overlapping location
      if (!matchedKey) {
        for (const [key, a] of assetMap.entries()) {
          if (a.category === matched.category && locsOverlap(a.loc, matched.loc)) {
            if (a.found < a.target) {
              matchedKey = key;
              break;
            } else if (!matchedKey) {
              matchedKey = key;
            }
          }
        }
      }
    }

    // 5. Fallback UNKNOWN location untuk aset deskriptif
    if (!matchedKey && matched.loc === 'UNKNOWN' && DESCRIPTIVE_CATEGORIES.has(matched.category)) {
      for (const [key, a] of assetMap.entries()) {
        if (a.category === matched.category) {
          if (a.found < a.target) {
            matchedKey = key;
            break;
          } else if (!matchedKey) {
            matchedKey = key;
          }
        }
      }
    }

    if (matchedKey && assetMap.has(matchedKey)) {
      const entry = assetMap.get(matchedKey);
      entry.found += 1;
      entry.matchedFiles.push(fname);
    } else {
      unmatchedFiles.push({ filename: fname, matchedInfo: matched, reason: 'Tidak ada slot master aset yang sesuai pada periode ini' });
    }
  }

  const assetDetails = Array.from(assetMap.values()).map(a => {
    const missing = Math.max(0, a.target - a.found);
    const isComplete = a.found >= a.target;
    return {
      ...a,
      missing,
      isComplete,
      statusLabel: isComplete ? 'LENGKAP' : `KURANG ${missing}`,
    };
  });

  const catGroups = {};
  for (const item of assetDetails) {
    if (!catGroups[item.category]) {
      catGroups[item.category] = {
        category: item.category,
        categoryDisplay: item.categoryDisplay,
        period: item.period,
        target: 0,
        found: 0,
        missing: 0,
      };
    }
    catGroups[item.category].target += item.target;
    catGroups[item.category].found += item.found;
    catGroups[item.category].missing += item.missing;
  }

  const categorySummary = Object.values(catGroups).map(c => {
    const isComplete = c.found >= c.target;
    const percent = c.target > 0 ? Math.min(100, Math.round((c.found / c.target) * 100)) : 100;
    return {
      ...c,
      isComplete,
      percent,
      status: isComplete ? 'LENGKAP' : `KURANG ${c.missing}`,
    };
  });

  const totalTarget = assetDetails.reduce((acc, a) => acc + a.target, 0);
  const totalFound = assetDetails.reduce((acc, a) => acc + a.found, 0);
  const totalMissing = assetDetails.reduce((acc, a) => acc + a.missing, 0);
  const percentComplete = totalTarget > 0 ? Math.min(100, Math.round((totalFound / totalTarget) * 100)) : 100;

  return {
    periodFilter,
    summary: {
      totalTarget,
      totalFound,
      totalMissing,
      percentComplete,
      totalFilesProcessed: fileNames.length,
    },
    categorySummary,
    assetDetails,
    unmatchedFiles,
  };
}

/**
 * Menghasilkan objek workbook dan base64 untuk ekspor Excel laporan audit kelengkapan
 * @param {object} auditResult Hasil dari performAssetAudit()
 * @param {string} title Judul / periode untuk nama file
 */
export function exportAuditToExcel(auditResult, title = 'Audit_Kelengkapan_Aset') {
  const wb = XLSX.utils.book_new();

  // Sheet 1: Ringkasan per Kategori
  const s1Data = [
    ['LAPORAN REKAP KELENGKAPAN FILE PEMELIHARAAN RESOR SINTELIS 1.21 BOO'],
    [`Tanggal Audit: ${new Date().toLocaleDateString('id-ID')} | Periode: ${auditResult.periodFilter}`],
    [`Total Target: ${auditResult.summary.totalTarget} File | Realisasi: ${auditResult.summary.totalFound} File (${auditResult.summary.percentComplete}%) | Kurang: ${auditResult.summary.totalMissing} File`],
    [],
    ['No', 'Kategori Aset', 'Periode', 'Target File', 'Realisasi File', 'Kekurangan', 'Persentase', 'Status']
  ];

  auditResult.categorySummary.forEach((c, idx) => {
    s1Data.push([
      idx + 1,
      c.categoryDisplay,
      c.period,
      c.target,
      c.found,
      c.missing > 0 ? -c.missing : 0,
      `${c.percent}%`,
      c.isComplete ? 'LENGKAP' : `KURANG ${c.missing}`
    ]);
  });

  const ws1 = XLSX.utils.aoa_to_sheet(s1Data);
  XLSX.utils.book_append_sheet(wb, ws1, 'Ringkasan Kategori');

  // Sheet 2: Daftar Aset yang Belum Lengkap (Missing Only)
  const missingAssets = auditResult.assetDetails.filter(a => !a.isComplete);
  const s2Data = [
    ['DAFTAR ASET YANG BELUM LENGKAP (FILE KURANG)'],
    [`Total Aset Kurang: ${missingAssets.length} Aset | Kekurangan File: ${auditResult.summary.totalMissing} File`],
    [],
    ['No', 'Kategori', 'ID Aset', 'Lokasi / Stasiun', 'Target', 'Ada', 'Kekurangan File', 'Status', 'File yang Ditemukan']
  ];

  missingAssets.forEach((a, idx) => {
    s2Data.push([
      idx + 1,
      a.categoryDisplay,
      a.id,
      a.loc,
      a.target,
      a.found,
      a.missing,
      a.statusLabel,
      a.matchedFiles.join(', ') || '(Belum Ada File)'
    ]);
  });

  const ws2 = XLSX.utils.aoa_to_sheet(s2Data);
  XLSX.utils.book_append_sheet(wb, ws2, 'Daftar Aset Kurang');

  // Sheet 3: Master Semua Aset
  const s3Data = [
    ['MASTER CHECKLIST KELENGKAPAN SELURUH ASET RESOR 1.21 BOO'],
    [`Total Aset: ${auditResult.assetDetails.length} Unit | Target: ${auditResult.summary.totalTarget} File`],
    [],
    ['No', 'Kategori', 'ID Aset', 'Lokasi', 'Periode', 'Target', 'Ada', 'Kekurangan', 'Status', 'File Terdaftar']
  ];

  auditResult.assetDetails.forEach((a, idx) => {
    s3Data.push([
      idx + 1,
      a.categoryDisplay,
      a.id,
      a.loc,
      a.period,
      a.target,
      a.found,
      a.missing,
      a.isComplete ? 'LENGKAP' : `KURANG ${a.missing}`,
      a.matchedFiles.join(', ') || '-'
    ]);
  });

  const ws3 = XLSX.utils.aoa_to_sheet(s3Data);
  XLSX.utils.book_append_sheet(wb, ws3, 'Semua Aset');

  const b64 = XLSX.write(wb, { bookType: 'xlsx', type: 'base64' });
  const filename = `${title}_${new Date().toISOString().slice(0, 10)}.xlsx`;

  return { b64, filename, wb };
}
