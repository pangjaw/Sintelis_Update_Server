// =============================================================================
// detector.js — Porting logika deteksi dari core.py/app.py ke JavaScript ES6
// =============================================================================

export const BTP_JAK_LOCS = ["BOO", "CLT"];
export const BTP_BD_LOCS = ["BOP", "BTT", "COS", "MSG", "CGB", "CCR"];

const WESEL_WHITELIST = {
  "BJD-CLT": new Set([]),
  "BOO": new Set(["W13", "W21A", "W21B1", "W21B2", "W23A", "W23B", "W31A", "W31B", "W31D", "W31E", "W41", "W43", "W51A1", "W51A2", "W61A1", "W61A2", "W81"]),
  "BOP": new Set(["W25", "W27A", "W27B", "W47A", "W47C", "W47D", "W67"]),
  "BOP-BTT": new Set([]),
  "BTT": new Set([]),
  "CGB": new Set([]),
  "CLT": new Set(["W11", "W13", "W21", "W23"]),
  "CLT-BOO": new Set([]),
  "COS": new Set([]),
  "MSG": new Set(["W11", "W13", "W21", "W23"]),
};

const ZP_WHITELIST = {
  "BJD-CLT": new Set(["ZP 101", "ZP 102", "ZP 205", "ZP 206", "ZP 207"]),
  "BOO": new Set(["ZP 10A", "ZP 10B", "ZP 12A", "ZP 12B", "ZP 13", "ZP 20A", "ZP 20B", "ZP 20C", "ZP 21A", "ZP 21B", "ZP 21C", "ZP 22A", "ZP 22B", "ZP 23A", "ZP 23B", "ZP 24A", "ZP 24B", "ZP 31A", "ZP 31B", "ZP 31C", "ZP 31D", "ZP 31E", "ZP 32A", "ZP 32B", "ZP 41", "ZP 41B", "ZP 42A", "ZP 42B", "ZP 42C", "ZP 52", "ZP 60", "ZP 61", "ZP 62A", "ZP 62B", "ZP 72", "ZP 92"]),
  "BOP": new Set(["ZP 25", "ZP 26A", "ZP 26B", "ZP 26C", "ZP 27A", "ZP 27B", "ZP 27C", "ZP 28A", "ZP 28B", "ZP 28C", "ZP 46A", "ZP 46B", "ZP 47A", "ZP 47B", "ZP 47C", "ZP 47D", "ZP 48A", "ZP 48B", "ZP 48C", "ZP 66A", "ZP 66B", "ZP 68"]),
  "BTT": new Set(["ZP 10B", "ZP 12A", "ZP 12B", "ZP 14A", "ZP 20B", "ZP 22A", "ZP 22B", "ZP 24A"]),
  "BOP-BTT": new Set(["ZP 10A", "ZP 20A", "ZP 28C", "ZP 48C"]),
  "BTT-BOP": new Set(["ZP 10A", "ZP 20A", "ZP 28C", "ZP 48C"]),
  "CGB": new Set(["ZP 101A", "ZP 101B", "ZP 201A", "ZP 201B"]),
  "CLT": new Set(["ZP 10A", "ZP 10B", "ZP 11", "ZP 12A", "ZP 12B", "ZP 13", "ZP 14A", "ZP 14B", "ZP 20A", "ZP 20B", "ZP 22A", "ZP 22B", "ZP 24A", "ZP 24B"]),
  "CLT-BOO": new Set(["ZP 101", "ZP 102", "ZP 103", "ZP 104", "ZP 105", "ZP 106", "ZP 107", "ZP 108", "ZP 109", "ZP 110", "ZP 111", "ZP 112", "ZP 201", "ZP 202", "ZP 203", "ZP 204", "ZP 205", "ZP 206", "ZP 207", "ZP 208", "ZP 209", "ZP 210", "ZP 211", "ZP 212", "ZP 213"]),
  "COS": new Set(["ZP 101A", "ZP 101B", "ZP 201A", "ZP 201B"]),
  "MSG": new Set(["ZP 10B", "ZP 10C", "ZP 11", "ZP 12A", "ZP 12B", "ZP 13", "ZP 14A", "ZP 14B", "ZP 20B", "ZP 20C", "ZP 22A", "ZP 22B", "ZP 24A", "ZP 24B"]),
  "BTT-MSG": new Set(["ZP 101A", "ZP 101B", "ZP 201A", "ZP 201B", "ZP 10A", "ZP 20A", "ZP 14B", "ZP 24B"]),
  "MSG-BTT": new Set(["ZP 101A", "ZP 101B", "ZP 201A", "ZP 201B", "ZP 10A", "ZP 20A", "ZP 14B", "ZP 24B"]),
  "MSG-CCR": new Set(["ZP 101A", "ZP 101B", "ZP 201A", "ZP 201B", "ZP 14C", "ZP 24C"]),
  "CCR-MSG": new Set(["ZP 101A", "ZP 101B", "ZP 201A", "ZP 201B", "ZP 14C", "ZP 24C"]),
};

const SINYAL_WHITELIST = {
  "BJD-CLT": new Set(["B101", "B102", "B205", "B206", "B207", "MJ20", "UB101", "UB102", "UB205", "UB206"]),
  "BOO": new Set(["B214", "J10", "J20", "JL12A", "JL12B", "JL22A", "JL22B", "JL32A", "JL32B", "JL42A", "JL42B", "JL42C", "JL52", "JL62B", "JL72", "JL92", "L20", "L60", "L62A", "L80", "MJ20"]),
  "BOP": new Set(["J28", "J48", "JL26A", "JL26B", "JL46A", "JL46B", "JL66B", "L28", "L47A", "L47B", "L68", "MJ28", "MJ48", "UJ26B"]),
  "BOP-BTT": new Set(["MJ10", "MJ20", "MJ28", "MJ48"]),
  "BTT": new Set(["J10", "J12A", "J12B", "J14", "J20", "J22A", "J22B", "J24", "MJ10", "MJ14", "MJ20", "MJ24"]),
  "CGB": new Set(["B101", "B201", "MB101", "MB201"]),
  "CLT": new Set(["J10", "J12A", "J12B", "J14", "J20", "J22", "J24", "MJ14", "MJ20"]),
  "CLT-BOO": new Set(["B101", "B102", "B103", "B104", "B105", "B106", "B107", "B108", "B109", "B110", "B111", "B112", "B201", "B202", "B203", "B204", "B205", "B206", "B207", "B208", "B209", "B210", "B211", "B212", "B213", "B214", "MJ14", "MJ20", "UB102", "UB103", "UB104", "UB105", "UB106", "UB110", "UB202", "UB206", "UB207", "UB208", "UB209", "UB210", "UB211", "UB212"]),
  "COS": new Set(["B101", "B201", "MB101", "MB201"]),
  "MSG": new Set(["J10", "J12", "J12B", "J14", "J20", "J22A", "J22B", "J24", "MJ10", "MJ14", "MJ20", "MJ24", "UJ12", "UJ22B"]),
  "BTT-MSG": new Set(["B101", "B201", "MB101", "MB201", "MJ10", "MJ14", "MJ20", "MJ24"]),
  "MSG-CCR": new Set(["B101", "B201", "MB101", "MB201", "MJ14", "MJ24"]),
};

const SIGNAL_PATTERN = /\b([BJLMSXU]+\.?\s?\d{1,3}[A-Z]?)\b/g;

const NOISE_WORDS = new Set([
  "DISETUJUI","DISETUJUL","PISETUJUI","DIKETAHUI","DILAKSANAKAN","OLEH",
  "TANGGAL","PERIODE","PERAWATAN","NO","SC","NOMOR","ASET",
  "PENGGERAK","WESEL","ELEKTRIK","MINGGUAN","BULANAN","TAHUNAN","HERU"
]);

const TRAILING_LOC_NOISE = new Set(["AN","EEN","SIE","SIEH","SIH","SETE","S","EE"]);

const LOC_MAP = {
  "MASENG":"MSG","CICURUG":"CCR","CILEBUT":"CLT","BOGOR":"BOO",
  "BATUTULIS":"BTT","BOGORPALEDANG":"BOP","PALEDANG":"BOP",
  "CIOMAS":"COS","CIGOMBONG":"CGB","BOJONGGEDE":"BJD","DEPOK":"BOO"
};
const LOC_CODES = new Set(["BOP","BTT","CLT","CGB","MSG","COS","BOO","CCR","BJD"]);
const SHORT_CODES = new Set(["BOO","CLT","BTT","BOP","COS","MSG","CGB","CCR","BJD"]);

// ---------- helpers ----------
function getUniqueList(items) {
  return [...new Set(items)];
}

export function getStandardLoc(text) {
  text = text.toUpperCase().replace(/\s+/g, "");
  if (text.includes("BOJONGGEDE")) return "BJD-CLT";
  if (text.includes("CIOMAS") || text.includes("COS")) return "COS";
  if (text.includes("CICURUG") || text.includes("CCR")) return "CCR";
  if (text.includes("CIGOMBONG") || text.includes("CGB")) return "CGB";
  if (text.includes("MASENG") || text.includes("MSG")) return "MSG";
  if (text.includes("BOGORPALEDANG") || text.includes("PALEDANG") || text.includes("BOP")) return "BOP";
  if (text.includes("BATUTULIS") || text.includes("BTT")) return "BTT";
  if (text.includes("CILEBUT") || text.includes("CLT")) return "CLT";
  if (text.includes("BOGOR") || text.includes("BOO")) return "BOO";

  // Fallback: cari keyword LOKASI / STASIUN / RESOR
  for (const keyword of ["LOKASI", "STASIUN", "RESOR"]) {
    const rx = new RegExp(`\\b${keyword}\\b`);
    const match = rx.exec(text);
    if (!match) continue;
    let tail = text.slice(match.index + match[0].length).replace(/^[\s:\-]+/, "");
    const locParts = [];
    for (const part of tail.match(/[A-Z0-9]+(?:-[A-Z0-9]+)*/g) || []) {
      if (NOISE_WORDS.has(part) || /^\d+$/.test(part)) break;
      locParts.push(part);
      if (locParts.length === 3) break;
    }
    while (locParts.length && TRAILING_LOC_NOISE.has(locParts[locParts.length - 1])) locParts.pop();
    if (locParts.length) return locParts.join(" ");
  }

  // Fallback filename: ambil setelah _ terakhir
  if (text.includes(".PDF") && text.includes("_")) {
    const tail = text.split("_").pop();
    const parts = (tail.match(/[A-Z0-9]+/g) || []).filter(p => !/^\d+$/.test(p) && p !== "PDF");
    if (parts.length) return parts.slice(0, 3).join(" ");
  }

  return "";
}

export function extractFuncloc(textCrop) {
  const lines = textCrop.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const m = /\bLOKASI\b/.exec(line.toUpperCase());
    if (!m) continue;
    let tail = line.slice(m.index + m[0].length).replace(/\r/g, "").trim().replace(/^[\s:|]+/, "");
    if (!tail) {
      for (let k = 1; k <= 3 && i + k < lines.length; k++) {
        const nextLine = lines[i + k].replace(/\r/g, "").trim().replace(/^[\s:|]+/, "");
        if (nextLine && !NOISE_WORDS.has(nextLine.toUpperCase())) {
          tail = nextLine;
          break;
        }
      }
    }
    const words = tail.toUpperCase().match(/[A-Z0-9]+/g) || [];
    const locParts = [];
    for (const w of words) {
      if (NOISE_WORDS.has(w)) continue;
      const std = LOC_MAP[w] || (LOC_CODES.has(w) ? w : null);
      if (std) {
        locParts.push(std);
      }
      if (locParts.length === 2) break;
    }
    if (locParts.length) return locParts.join("-");
  }
  return null;
}

function getPtlsLoc(textFlat, textCrop) {
  // 1. Cek stasiun langsung dari baris aset TRA / TLK (misal: MULTIPLEX BOO -> BOO)
  for (const rawLine of textCrop.split("\n")) {
    const ul = rawLine.replace(/\r/g, "").toUpperCase().trim();
    const cleanLine = ul.replace(/^[^A-Z0-9]+/, "");
    if (cleanLine.startsWith("TRA") || cleanLine.startsWith("TLK")) {
      for (const code of SHORT_CODES) {
        if (new RegExp("\\b" + code + "\\b").test(cleanLine)) return code;
      }
      for (const [full, code] of Object.entries(LOC_MAP)) {
        if (new RegExp("\\b" + full + "\\b").test(cleanLine)) return code;
      }
    }
  }

  // 2. Cek label LOKASI via extractFuncloc
  const funcloc = extractFuncloc(textCrop);
  if (funcloc) return funcloc;

  return getStandardLoc(textFlat);
}

// ---------- Dual-location scanner ----------
function getDualLoc(text) {
  const matches = [];
  for (const code of SHORT_CODES) {
    const rx = new RegExp(`\\b${code}\\b`, "g");
    let m;
    while ((m = rx.exec(text)) !== null) matches.push({ pos: m.index, code });
  }
  for (const [full, code] of Object.entries(LOC_MAP)) {
    const rx = new RegExp(`\\b${full}\\b`, "g");
    let m;
    while ((m = rx.exec(text)) !== null) matches.push({ pos: m.index, code });
  }
  if (!matches.length) return getStandardLoc(text);
  matches.sort((a, b) => a.pos - b.pos);
  const seen = new Set();
  const found = [];
  for (const { code } of matches) {
    if (!seen.has(code)) { seen.add(code); found.push(code); }
    if (found.length >= 2) break;
  }
  return found.join("-");
}

// ---------- JPL extraction ----------
function getJplInlineLoc(textSnippet) {
  const matches = [];
  for (const code of LOC_CODES) {
    const rx = new RegExp(`\\b${code}\\b`, "g");
    let m;
    while ((m = rx.exec(textSnippet)) !== null) matches.push({ pos: m.index, code });
  }
  matches.sort((a, b) => a.pos - b.pos);
  return [...new Set(matches.map(x => x.code))].join("-");
}

const JPL_KNOWN_LOCS = {
  "JPL 01": "BOO",
  "JPL 1": "BOO",
  "JPL 02": "BOO",
  "JPL 2": "BOO",
  "JPL 04": "BOP",
  "JPL 4": "BOP",
  "JPL BNR": "BOP-BTT",
  "JPL 07": "BOP-BTT",
  "JPL 7": "BOP-BTT",
  "JPL 11": "BTT",
  "JPL 26N": "CLT",
  "JPL 27": "CLT-BOO",
  "JPL 28": "CLT-BOO",
  "JPL 15": "CGB",
  "JPL 16": "CGB"
};

export function extractJplsFromFilename(fnUpper) {
  const results = [];
  if (!fnUpper || !fnUpper.includes("JPL")) return results;

  // Tangkap segmen setelah JPL, misal "JPL 7&BNR", "JPL 15, JPL 16", "JPL ELEKTRIK BNR", "JPL 07"
  const jplPartMatch = fnUpper.match(/JPL\s+(?:ELEKTRIK\s+)?([A-Z0-9]+(?:\s*[&,]\s*(?:JPL\s+)?(?:ELEKTRIK\s+)?([A-Z0-9]+))*)/i);
  if (!jplPartMatch) {
    const fallbackRx = /JPL\s+(?:ELEKTRIK\s+)?([A-Z0-9]+)/gi;
    let fm;
    while ((fm = fallbackRx.exec(fnUpper)) !== null) {
      let token = fm[1].toUpperCase();
      if (['ELEKTRIK', 'NO', 'DAN', 'AND'].includes(token)) continue;
      if (/^\d$/.test(token)) token = `0${token}`;
      results.push(`JPL ${token}`);
    }
    return [...new Set(results)];
  }

  const fullMatch = jplPartMatch[0];
  const tokenRx = /\b([0-9]+[A-Z]*|[A-Z]+)\b/g;
  let tm;
  while ((tm = tokenRx.exec(fullMatch)) !== null) {
    const token = tm[1].toUpperCase();
    if (['JPL', 'ELEKTRIK', 'NO', 'DAN', 'AND'].includes(token)) continue;
    let norm = token;
    if (/^\d$/.test(norm)) norm = `0${norm}`;
    results.push(`JPL ${norm}`);
  }
  return [...new Set(results)];
}

function extractJplAssets(textClean, textFlatRef, multiWord = false) {
  const result = [];
  const stopWords = new Set(["DISETUJUL","DIKETAHUI","OLEH","TANGGAL","ELEKTRIK","NO"]);

  // JPL Angka
  const numRx = /JPL\s+(?:ELEKTRIK\s+)?(?:NO[.\s]*)?([0-9]+[A-Z]*)/g;
  let m;
  while ((m = numRx.exec(textClean)) !== null) {
    let idPart = m[1].trim();
    if (/^\d$/.test(idPart)) idPart = `0${idPart}`;
    const aid = `JPL ${idPart}`;
    const start = m.index + m[0].length;
    const nlIdx = textClean.indexOf("\n", start);
    const snippet = nlIdx >= 0 ? textClean.slice(start, nlIdx) : textClean.slice(start);
    let loc = JPL_KNOWN_LOCS[aid] || getJplInlineLoc(snippet);
    if (!loc) loc = getStandardLoc(textClean.slice(start));
    if (loc === "LOKASI") loc = getStandardLoc(textFlatRef);
    if (!result.some(a => a.id === aid)) result.push({ id: aid, loc });
  }

  // JPL Huruf
  const wordRx = multiWord
    ? /JPL\s+([A-Z]+(?:\s+[A-Z\-]+)*)/g
    : /\bJPL\s+([A-Z]+)\b/g;
  while ((m = wordRx.exec(textClean)) !== null) {
    let aid = m[1].trim();
    
    // Split di stop words, location codes, location names, dan noise words
    const splitRx = /\s+\b(?:LOKASI|DISETUJUI|DISETUJUL|PISETUJUI|DIKETAHUI|TANGGAL|OLEH|BOP|BTT|BOO|CLT|MSG|COS|CGB|CCR|BJD|BOGOR|BATUTULIS|CILEBUT|MASENG|CIOMAS|CIGOMBONG|CICURUG|PALEDANG|EE|EEN|S)\b/i;
    aid = aid.split(splitRx)[0].trim();
    
    // Hilangkan kata "ELEKTRIK"
    aid = aid.replace(/\bELEKTRIK\b/gi, "").replace(/\s+/g, " ").trim();
    
    if (!aid || stopWords.has(aid)) continue;
    
    const fullAid = `JPL ${aid}`;
    const start = m.index + m[0].length;
    const nlIdx = textClean.indexOf("\n", start);
    const snippet = nlIdx >= 0 ? textClean.slice(start, nlIdx) : textClean.slice(start);
    let loc = JPL_KNOWN_LOCS[fullAid] || getJplInlineLoc(snippet);
    if (!loc) loc = getStandardLoc(textClean.slice(start));
    if (loc === "LOKASI") loc = getStandardLoc(textFlatRef);
    if (/[A-Z]{3}\s*-\s*[A-Z]{3}/.test(fullAid) && !JPL_KNOWN_LOCS[fullAid]) loc = "";
    if (!result.some(a => a.id === fullAid)) result.push({ id: fullAid, loc });
  }

  if (!result.length) result.push({ id: "JPL", loc: getStandardLoc(textFlatRef) });

  for (const item of result) {
    if (JPL_KNOWN_LOCS[item.id]) item.loc = JPL_KNOWN_LOCS[item.id];
  }

  return result;
}

// ---------- Wesel extraction ----------
function extractWeselIds(text, allowGeneric = false) {
  const result = [];
  const patterns = [
    /PENGGERAK\s+WESEL(?:\s+ELEKTRIK)?\s+(?:W\s*\.?\s*)?(\d{1,3})\s*([A-Z]?\d?)\b/g,
    /(?<![\\/|!])\bW(?!SL)\s*\.?\s*(\d{1,3})\s*([A-Z]?\d?)\b/g,
  ];
  if (allowGeneric) patterns.push(/(?<![\\/|!])\b(?:W\s*\.?\s*)?(\d{1,3})\s*([A-Z]\d?)\b/g);
  for (const rx of patterns) {
    let m;
    while ((m = rx.exec(text)) !== null) {
      result.push(`W${m[1]}${m[2]}`.replace(/\s/g, ""));
    }
  }
  return getUniqueList(result);
}

// ---------- Radio Waystation ----------
function extractRadioWaystationAssets(text) {
  const result = [];
  const stopWords = new Set(["LOKASI","DISETUJUI","DISETUJUL","PISETUJUI","DIKETAHUI","TANGGAL","PERIODE","PERAWATAN","DILAKSANAKAN","OLEH","NO","SC"]);
  const locCodes = new Set([...BTP_JAK_LOCS, ...BTP_BD_LOCS]);
  const longNames = new Set(["BOGOR","CILEBUT","BATUTULIS","BOGORPALEDANG","PALEDANG","CIOMAS","MASENG","CIGOMBONG"]);

  const rx = /\bTLK\d+\s*:\s*(WS\b[^:]+)/g;
  let m;
  while ((m = rx.exec(text)) !== null) {
    const tokens = m[1].match(/[A-Z0-9]+/g) || [];
    const aidParts = [];
    let loc = "";
    for (const token of tokens) {
      if (stopWords.has(token)) break;
      if (locCodes.has(token) || longNames.has(token)) {
        loc = getStandardLoc(token);
        break;
      }
      aidParts.push(token);
    }
    if (aidParts.length && aidParts[0] === "WS") {
      if (!loc) loc = getStandardLoc(text.slice(m.index + m[0].length));
      if (loc === "LOKASI") loc = getStandardLoc(text);
      const aid = aidParts.join(" ");
      if (!result.some(a => a.id === aid && a.loc === loc)) result.push({ id: aid, loc });
    }
  }
  if (!result.length) result.push({ id: "WS", loc: getStandardLoc(text) });
  return result;
}

// ======================= MAIN DETECT API =======================

export function detectDoc(textFlat, textCrop, filenameUpper, formatBd) {
  let kode = "";
  let kategori = "";
  let assets = [];

  // ---------- OCR-based detection ----------

  // POINT LOCK
  if (textFlat.includes("POINT LOCK") || textFlat.includes("PENGAMAN WESEL")) {
    kode = "BPBYE12"; kategori = "POINT LOCK";
    const wMatch = extractWeselIds(textFlat, true);
    if (wMatch.length) {
      for (const w of wMatch) {
        let wLoc = null;
        for (const line of textCrop.split("\n")) {
          if (line.includes(w) && !line.toUpperCase().includes("PERAWATAN")) {
            wLoc = getDualLoc(line); break;
          }
        }
        const loc = wLoc || extractFuncloc(textCrop) || getStandardLoc(textFlat);
        if (loc === "BOO" && w !== "W81") continue;
        assets.push({ id: w, loc });
      }
    } else {
      assets.push({ id: "W81", loc: "BOO" });
    }
  }

  // WESEL
  else if (textFlat.includes("PERAWATAN WESEL") || textFlat.includes("PENGGERAK WESEL")) {
    kode = "BPBYE1"; kategori = "WESEL";
    const wMatch = extractWeselIds(textFlat, true);
    if (wMatch.length) {
      for (const w of wMatch) {
        let wLoc = null;
        for (const line of textCrop.split("\n")) {
          if (line.includes(w) && !line.toUpperCase().includes("PERAWATAN")) {
            wLoc = getDualLoc(line); break;
          }
        }
        const loc = wLoc || extractFuncloc(textCrop) || getStandardLoc(textFlat);
        const allowed = WESEL_WHITELIST[loc];
        if (allowed && !allowed.has(w)) continue;
        assets.push({ id: w, loc });
      }
    } else {
      const loc = extractFuncloc(textCrop) || getStandardLoc(textFlat);
      assets.push({ id: "W_UNKNOWN", loc });
    }
  }

  else if (textFlat.includes("PERALATAN DALAM PERSINYALAN ELEKTRIK")) {
    kode = "BPBYE2"; kategori = "PDSE";
    let loc = extractFuncloc(textCrop) || getStandardLoc(textFlat);
    assets.push({ id: "", loc });
  }

  // PTPP
  else if (textFlat.includes("TELEKOMUNIKASI DI PINTU PERLINTASAN")) {
    kode = "BPBKS17"; kategori = "PTPP";
    let textClean = textFlat.replace(/\bJPL\d+\b/g, "");
    for (const marker of ["NO ITEM", "ITEM PERAWATAN"]) {
      const idx = textClean.toUpperCase().indexOf(marker);
      if (idx >= 0) { textClean = textClean.slice(0, idx); break; }
    }
    assets = extractJplAssets(textClean, textFlat, false);
    // Dedup
    const dedup = {};
    for (const a of assets) {
      if (!dedup[a.id]) dedup[a.id] = { ...a };
      else {
        const existingLocs = dedup[a.id].loc.split("-");
        const newLocs = a.loc.split("-");
        const merged = [...new Set([...existingLocs, ...newLocs])];
        dedup[a.id].loc = merged.join("-");
      }
    }
    assets = Object.values(dedup);
    const fnLoc = getDualLoc(filenameUpper) || getStandardLoc(filenameUpper);
    const fnJpls = extractJplsFromFilename(filenameUpper);

    if (assets.length > 1) {
      // Multi-aset dokumen: pertahankan semua JPL terdeteksi dan pastikan lokasinya valid
      for (const item of assets) {
        if (!item.loc) {
          item.loc = JPL_KNOWN_LOCS[item.id] || fnLoc || extractFuncloc(textCrop) || getStandardLoc(textFlat);
        }
      }
    } else if (fnJpls.length === 1) {
      const targetJpl = fnJpls[0];
      const ocrMatch = assets.find(a => a.id === targetJpl || a.id.replace(/\b0(\d)\b/, '$1') === targetJpl.replace(/\b0(\d)\b/, '$1'));
      if (ocrMatch) {
        if (!ocrMatch.loc) ocrMatch.loc = fnLoc;
        assets = [{ ...ocrMatch, id: targetJpl }];
      } else {
        assets = [{ id: targetJpl, loc: JPL_KNOWN_LOCS[targetJpl] || fnLoc || "" }];
      }
    } else if (fnJpls.length > 1) {
      const matchedAssets = [];
      for (const fnJpl of fnJpls) {
        const ocrMatch = assets.find(a => a.id === fnJpl || a.id.replace(/\b0(\d)\b/, '$1') === fnJpl.replace(/\b0(\d)\b/, '$1'));
        if (ocrMatch) {
          if (!ocrMatch.loc) ocrMatch.loc = fnLoc;
          matchedAssets.push({ ...ocrMatch, id: fnJpl });
        } else {
          matchedAssets.push({ id: fnJpl, loc: JPL_KNOWN_LOCS[fnJpl] || fnLoc || "" });
        }
      }
      assets = matchedAssets;
    } else {
      // Pastikan semua aset memiliki lokasi valid
      for (const item of assets) {
        if (!item.loc) {
          item.loc = fnLoc || extractFuncloc(textCrop) || getStandardLoc(textFlat);
        }
      }
    }
  }

  // PINTU PERLINTASAN (tanpa TELEKOMUNIKASI)
  else if (textFlat.includes("PINTU PERLINTASAN") && !textFlat.includes("TELEKOMUNIKASI")) {
    kode = "BPBKS17"; kategori = "PINTU PERLINTASAN";
    let textClean = textFlat.replace(/\bJPL\d+\b/g, "");
    assets = extractJplAssets(textClean, textFlat, true);
    
    const fnLoc = getDualLoc(filenameUpper) || getStandardLoc(filenameUpper);
    const fnJpls = extractJplsFromFilename(filenameUpper);

    if (assets.length > 1) {
      // Multi-aset dokumen: pertahankan semua JPL terdeteksi dan pastikan lokasinya valid
      for (const item of assets) {
        if (!item.loc) {
          item.loc = JPL_KNOWN_LOCS[item.id] || fnLoc || extractFuncloc(textCrop) || getStandardLoc(textFlat);
        }
      }
    } else if (fnJpls.length === 1) {
      const targetJpl = fnJpls[0];
      const ocrMatch = assets.find(a => a.id === targetJpl || a.id.replace(/\b0(\d)\b/, '$1') === targetJpl.replace(/\b0(\d)\b/, '$1'));
      if (ocrMatch) {
        if (!ocrMatch.loc) ocrMatch.loc = fnLoc;
        assets = [{ ...ocrMatch, id: targetJpl }];
      } else {
        assets = [{ id: targetJpl, loc: JPL_KNOWN_LOCS[targetJpl] || fnLoc || "" }];
      }
    } else if (fnJpls.length > 1) {
      const matchedAssets = [];
      for (const fnJpl of fnJpls) {
        const ocrMatch = assets.find(a => a.id === fnJpl || a.id.replace(/\b0(\d)\b/, '$1') === fnJpl.replace(/\b0(\d)\b/, '$1'));
        if (ocrMatch) {
          if (!ocrMatch.loc) ocrMatch.loc = fnLoc;
          matchedAssets.push({ ...ocrMatch, id: fnJpl });
        } else {
          matchedAssets.push({ id: fnJpl, loc: JPL_KNOWN_LOCS[fnJpl] || fnLoc || "" });
        }
      }
      assets = matchedAssets;
    } else {
      // Pertahankan semua JPL terdeteksi dan pastikan lokasinya valid
      for (const item of assets) {
        if (!item.loc) {
          item.loc = fnLoc || extractFuncloc(textCrop) || getStandardLoc(textFlat);
        }
      }
    }
  }

  // PTDS
  else if (textFlat.includes("TELEKOMUNIKASI DI STASIUN")) {
    kode = "BPBKS15"; kategori = "PTDS";
    let loc = extractFuncloc(textCrop);
    if (!loc) {
      for (const line of textCrop.split("\n")) {
        const ul = line.replace(/\r/g, "").toUpperCase().trim();
        if (ul.startsWith("TLK") || ul.startsWith("JPL")) {
          for (const code of SHORT_CODES) {
            if (new RegExp("\\b" + code + "\\b").test(ul)) { loc = code; break; }
          }
          if (loc) break;
        }
      }
    }
    if (!loc) loc = getStandardLoc(textFlat);
    assets.push({ id: "", loc });
  }

  // PTLS
  else if (textFlat.includes("TELEKOMUNIKASI DI LUAR STASIUN")) {
    kode = "BPBKS16"; kategori = "PTLS";
    let loc = getPtlsLoc(textFlat, textCrop);
    assets.push({ id: "", loc });
  }

  // RADIO BASESTATION
  else if (textFlat.includes("RADIO BASESTATION")) {
    const loc = extractFuncloc(textCrop) || getStandardLoc(textFlat);
    if (textFlat.includes("TAIT")) { kode = "BPBKF3"; kategori = "RADIO BASESTATION TAIT"; }
    else if (textFlat.includes("DIGITAL")) { kode = "BPBKF2"; kategori = "RADIO BASESTATION DIGITAL"; }
    else { kode = "BPBKF1"; kategori = "RADIO BASESTATION"; }
    assets.push({ id: "", loc });
  }

  // WAYSTATION / RADIO WAYSTATION
  else if (textFlat.includes("SISTEM WAYSTATION") || textFlat.includes("RADIO WAYSTATION") || textFlat.includes("RADIO WAY STATION")) {
    if (textFlat.includes("SISTEM WAYSTATION")) {
      kode = "BPBKS5"; kategori = "SISTEM WAYSTATION";
      const loc = extractFuncloc(textCrop) || getStandardLoc(textFlat);
      assets.push({ id: "", loc });
    } else {
      kode = "BPBKS16"; kategori = "RADIO WAYSTATION";
      assets = extractRadioWaystationAssets(textFlat);
    }
  }

  else if (textFlat.includes("CTC") && textFlat.includes("CTS")) {
    kode = "BPBYE4"; kategori = "CTC-CTS";
    let loc = extractFuncloc(textCrop) || getStandardLoc(textFlat);
    assets.push({ id: "", loc });
  }

  // AXLE COUNTER
  else if (textFlat.includes("PERAWATAN AXLE COUNTER")) {
    kode = "BPBYE7"; kategori = "AXLE COUNTER";
    const zpRx = /\bZP\s?(\d{1,3})([A-Z]{1,2})?\b(?!\.\d)/g;
    let m;
    const zpMatches = [];
    while ((m = zpRx.exec(textFlat)) !== null) {
      if (m[1] === "43" && !m[2]) continue;
      zpMatches.push({ id: `ZP ${m[1]}${m[2] || ""}`, pos: m.index });
    }
    if (zpMatches.length) {
      const seen = new Set();
      for (const { id: zId, pos } of zpMatches) {
        if (seen.has(zId)) continue;
        seen.add(zId);
        let zpLoc = null;
        for (const line of textCrop.split("\n")) {
          if (line.includes(zId) && !line.toUpperCase().includes("PERAWATAN")) {
            zpLoc = getDualLoc(line); break;
          }
        }
        const loc = zpLoc || extractFuncloc(textCrop) || getDualLoc(textFlat);
        
        // Filter via ZP_WHITELIST if location is found
        if (ZP_WHITELIST[loc] && !ZP_WHITELIST[loc].has(zId)) {
          continue;
        }
        
        assets.push({ id: zId, loc });
      }
    } else {
      const loc = extractFuncloc(textCrop) || getDualLoc(textFlat);
      assets.push({ id: "ZP", loc });
    }
  }

  // PERAGA SINYAL / PERAWATAN SINYAL / SEMBOYAN TETAP
  else if (textFlat.includes("PERAGA SINYAL") || textFlat.includes("PERAWATAN SINYAL") || textFlat.includes("SEMBOYAN TETAP")) {
    kode = "BPBYE3"; kategori = "PERAGA SINYAL";
    const defaultLoc = getDualLoc(textFlat);
    const seen = new Set();

    // === STRATEGI 1: Ekstraksi presisi langsung dari baris tabel aset (SIN... / SC... : SINYAL ...) ===
    const normalizedCrop = (textCrop || textFlat || "").replace(/([A-Z]{3})\s*-\s*([A-Z]{3})/g, '$1-$2');
    const sinyalRowRx = /(?:\b(?:SIN|SC)\d{4,6}\s*[:|;.]*\s*.*?|\bSINYAL(?:\s+[A-Za-z]+)+?\s+)([BJLMSXU]+\.?\s?\d{1,3}[A-Za-z]?)\s*(.*)/i;
    const lines = normalizedCrop.split("\n");
    for (let i = 0; i < lines.length; i++) {
      let line = lines[i].replace(/\r/g, "");
      if (line.includes("NOMOR SINYAL") || line.includes("REFERENSI STANDAR")) continue;
      let m = line.match(sinyalRowRx);
      // Multi-line lookahead jika teks terpecah kolom/baris saat OCR
      if (!m && i + 1 < lines.length && !lines[i + 1].includes("NOMOR SINYAL")) {
        const cand2 = `${line.trim()} ${lines[i + 1].replace(/\r/g, "").trim()}`;
        m = cand2.match(sinyalRowRx);
        if (m) {
          line = cand2;
        } else if (i + 2 < lines.length && !lines[i + 2].includes("NOMOR SINYAL")) {
          const cand3 = `${cand2} ${lines[i + 2].replace(/\r/g, "").trim()}`;
          m = cand3.match(sinyalRowRx);
          if (m) line = cand3;
        }
      }
      if (m) {
        const sigId = m[1].replace(/[\s.]/g, "").toUpperCase();
        if (/^M\d+$/.test(sigId)) continue; // skip false positive seperti M14
        const locPart = m[2].trim();
        const loc = (getDualLoc(locPart) || getDualLoc(line) || defaultLoc).trim();
        if (SINYAL_WHITELIST[loc] && !SINYAL_WHITELIST[loc].has(sigId)) continue;
        const key = `${sigId}|${loc}`;
        if (!seen.has(key)) {
          seen.add(key);
          assets.push({ id: sigId, loc });
        }
      }
    }

    // === STRATEGI 2: Scan pelengkap sinyal valid sesuai whitelist stasiun ===
    const signalMatches = textFlat.match(SIGNAL_PATTERN) || [];
    const validSignals = [];
    for (const s of signalMatches) {
      const sClean = s.replace(/[\s.]/g, "");
      if (/^M\d+$/.test(sClean)) continue;
      if (/^[BJLMSXU]+\d+/.test(sClean)) validSignals.push(sClean);
    }
    if (validSignals.length) {
      const uniqueSig = getUniqueList(validSignals);
      for (const s of uniqueSig) {
        let sigLoc = null;
        for (const line of textCrop.split("\n")) {
          const lineFlat = line.replace(/[\s.]/g, "");
          if ((line.includes(s) || lineFlat.includes(s)) && !line.toUpperCase().includes("PERAWATAN")) {
            sigLoc = getDualLoc(line); break;
          }
        }
        const loc = (sigLoc && sigLoc.trim()) ? sigLoc.trim() : defaultLoc;
        // Filter via SINYAL_WHITELIST if location is found in whitelist
        if (SINYAL_WHITELIST[loc] && !SINYAL_WHITELIST[loc].has(s)) {
          continue;
        }
        
        const key = `${s}|${loc}`;
        if (!seen.has(key)) {
          seen.add(key);
          assets.push({ id: s, loc });
        }
      }
    }

    // === STRATEGI 3: Fallback akhir jika tidak ada nomor aset terdeteksi ===
    if (!assets.length) {
      assets.push({ id: "", loc: defaultLoc });
    }
  }

  else if (textFlat.includes("CATU DAYA")) {
    const cdaLines = textCrop.split("\n").filter(l => l.toUpperCase().includes("CDA"));
    const combinedCda = cdaLines.join(" ").toUpperCase();
    if (combinedCda.includes("ER RADIO")) { kode = "BPBYE14"; kategori = "CATU DAYA ER RADIO"; }
    else if (combinedCda.includes("ER SINYAL")) { kode = "BPBYE14"; kategori = "CATU DAYA ER SINYAL"; }
    else { kode = "BPBYE14"; kategori = "CATU DAYA"; }
    let loc = extractFuncloc(textCrop) || getDualLoc(textFlat);
    assets.push({ id: "", loc });
  }

  // SERAT OPTIK JPL (Prioritas jika ada indikasi JPL di OCR atau filename)
  else if ((textFlat.includes("SERAT OPTIK") || filenameUpper.includes("SERAT OPTIK")) &&
           (textCrop.toUpperCase().includes("JPL") || filenameUpper.includes("JPL"))) {
    kode = "BPBKF4"; kategori = "SERAT OPTIK";
    const fnLoc = getDualLoc(filenameUpper) || getStandardLoc(filenameUpper);
    let loc = fnLoc || extractFuncloc(textCrop) || getStandardLoc(textFlat);

    // Scan OCR for TRA lines with JPL secara global
    const jplSet = new Set();
    const traGlobalRx = /(?:TRA\d+\s*[:|;.]*\s*)?OTB\s+FO\s+JPL\s+([A-Z0-9]+)/gi;
    let tm;
    while ((tm = traGlobalRx.exec(textCrop)) !== null) {
      let jId = tm[1].trim().toUpperCase();
      if (/^\d$/.test(jId)) jId = `0${jId}`;
      jplSet.add(jId);
    }

    const fnJpls = extractJplsFromFilename(filenameUpper);

    if (jplSet.size > 1) {
      assets = [...jplSet].sort().map(jplId => {
        const fullAid = `JPL ${jplId}`;
        const itemLoc = JPL_KNOWN_LOCS[fullAid] || loc;
        return { id: fullAid, loc: itemLoc };
      });
    } else if (fnJpls.length === 1) {
      const fullAid = fnJpls[0];
      const itemLoc = JPL_KNOWN_LOCS[fullAid] || loc || "";
      assets = [{ id: fullAid, loc: itemLoc }];
    } else if (fnJpls.length > 1) {
      assets = fnJpls.map(fullAid => ({
        id: fullAid,
        loc: JPL_KNOWN_LOCS[fullAid] || loc || ""
      }));
    } else if (jplSet.size) {
      assets = [...jplSet].sort().map(jplId => {
        const fullAid = `JPL ${jplId}`;
        const itemLoc = JPL_KNOWN_LOCS[fullAid] || loc;
        return { id: fullAid, loc: itemLoc };
      });
    } else {
      assets = [{ id: "JPL", loc: loc || "" }];
    }
  }

  // SERAT OPTIK ER / RUANG RADIO (OTB 1-10 ER SINYAL / ER RADIO / ER TELKOM / ER / RUANG RADIO)
  else if ((textFlat.includes("SERAT OPTIK") || filenameUpper.includes("SERAT OPTIK")) &&
           (/\bER\s+SINYAL\b/.test(textFlat) || /\bER\s+RADIO\b/.test(textFlat) || /\bER\s+TELKOM\b/.test(textFlat) ||
            /\bRUANG\s+RADIO\b/.test(textFlat) ||
            /OTB\s+(?:FO\s+)?(?:ER|RUANG\s+RADIO)\b/.test(textFlat) || /OTB\s+\d+\s+ER\b/.test(textFlat) ||
            filenameUpper.includes("ER SINYAL") || filenameUpper.includes("ER RADIO") || filenameUpper.includes("ER TELKOM") ||
            filenameUpper.includes("RUANG RADIO") || filenameUpper.includes(" ER "))) {
    kode = "BPBKF4"; kategori = "SERAT OPTIK";

    // === 1. Deteksi sub-type ER / RUANG RADIO: SINYAL > RADIO / RUANG RADIO > TELKOM > generic ER ===
    let erType = null;
    // OCR priority
    if (/\bER\s+SINYAL\b/.test(textFlat)) {
      erType = "ER SINYAL";
    } else if (/\bER\s+RADIO\b/.test(textFlat)) {
      erType = "ER RADIO";
    } else if (/\bRUANG\s+RADIO\b/.test(textFlat)) {
      erType = "RUANG RADIO";
    } else if (textFlat.includes("TELKOM")) {
      erType = "ER TELKOM";
    }
    // Filename fallback (terpisah per keyword)
    if (!erType) {
      if (filenameUpper.includes("SINYAL")) {
        erType = "ER SINYAL";
      } else if (filenameUpper.includes("ER RADIO")) {
        erType = "ER RADIO";
      } else if (filenameUpper.includes("RUANG RADIO")) {
        erType = "RUANG RADIO";
      } else if (filenameUpper.includes("RADIO")) {
        erType = "ER RADIO";
      } else if (filenameUpper.includes("TELKOM")) {
        erType = "ER TELKOM";
      }
    }
    if (!erType) erType = "ER";

    // === 2. Scan OTB numbers ===
    let firstOtb = 0, otbMin = 1, otbMax = 1;
    let hasOtbNumbers = false;

    // Filter OTB: exclude ODF/OTB (core count) via check on preceding char
    const allOtbNums = [];
    const simpleOtbRx = /\bOTB\s+(\d+)\b/g;
    let om;
    while ((om = simpleOtbRx.exec(textFlat)) !== null) {
      const preChar = textFlat[om.index - 1] || "";
      if (preChar === "/" || /[A-Za-z]/.test(preChar)) continue;
      allOtbNums.push(+om[1]);
    }
    if (allOtbNums.length) {
      otbMin = Math.min(...allOtbNums);
      otbMax = Math.max(...allOtbNums);
      firstOtb = otbMin;
      hasOtbNumbers = true;
    } else {
      // Fallback from filename
      const rangeMatch = filenameUpper.match(/OTB\s+(\d+)-(\d+)/);
      const singleMatch = filenameUpper.match(/OTB\s+(\d+)(?!\s*-)/);
      if (rangeMatch) {
        otbMin = +rangeMatch[1]; otbMax = +rangeMatch[2]; firstOtb = otbMin;
        hasOtbNumbers = true;
      } else if (singleMatch) {
        otbMin = +singleMatch[1]; otbMax = +singleMatch[1]; firstOtb = otbMin;
        hasOtbNumbers = true;
      }
    }

    // === 3. Ekstrak lokasi dari OCR ===
    let loc = null;
    for (const line of textCrop.split("\n")) {
      const ul = line.toUpperCase();
      if (ul.includes("OTB") && (ul.includes("ER") || ul.includes("SINYAL") || ul.includes("TELKOM") || ul.includes("RADIO"))) {
        const parts = ul.split(":");
        if (parts.length >= 2) {
          let after = parts[parts.length - 1].trim();
          after = after.replace(/TRA\d+\s*:\s*/gi, "");
          after = after.replace(/OTB\s+FO\s+\d+\s*/gi, "");
          after = after.replace(/OTB\s+FO\s+/gi, "");            // OTB FO tanpa digit
          after = after.replace(/OTB\s+\d+\s*/gi, "");
          after = after.replace(/^OTB\s+/gi, "");               // OTB tanpa FO dan tanpa digit
          after = after.replace(/^ER\s+SINYAL\s+/i, "");
          after = after.replace(/^ER\s+RADIO\s+/i, "");
          after = after.replace(/^RUANG\s+RADIO\s+/i, "");
          after = after.replace(/^ER\s+TELKOM\s+/i, "");
          after = after.replace(/^ER\s+/i, "");
          loc = after.trim();
          if (loc) {
            loc = getStandardLoc(loc) || loc;
            break;
          }
        }
      }
    }
    if (!loc) {
      loc = getDualLoc(filenameUpper) || getStandardLoc(filenameUpper) || extractFuncloc(textCrop) || getStandardLoc(textFlat);
    }

    assets = [{ id: erType, loc, firstOtb, erType, otbMin, otbMax, hasOtbNumbers }];
  }

  // SERAT OPTIK Bulanan biasa (Stasiun / Non-ER Non-JPL)
  else if (textFlat.includes("SERAT OPTIK") || filenameUpper.includes("SERAT OPTIK")) {
    kode = "BPBKF4"; kategori = "SERAT OPTIK";
    const fnLoc = getDualLoc(filenameUpper) || getStandardLoc(filenameUpper);
    let loc = fnLoc || extractFuncloc(textCrop) || getStandardLoc(textFlat);
    const seqMatch = filenameUpper.match(/_0*(\d+)\s/) || filenameUpper.match(/\((\d+)\)/);
    const seqNum = seqMatch ? +seqMatch[1] : 1;
    assets = [{ id: "", loc, seqNum, isBulanan: true }];
  }

  // ---------- Filename-based fallback ----------
  if (!assets.length) {
    let loc = getDualLoc(filenameUpper) || getStandardLoc(filenameUpper);

    if (filenameUpper.includes("WESEL")) {
      kode = "BPBYE1"; kategori = "WESEL";
      assets = [{ id: "W_UNKNOWN", loc }];
    } else if (filenameUpper.includes("POINT LOCK")) {
      kode = "BPBYE12"; kategori = "POINT LOCK";
      assets = [{ id: "W81", loc: "BOO" }];
    } else if (filenameUpper.includes("AXLE COUNTER")) {
      kode = "BPBYE7"; kategori = "AXLE COUNTER";
      assets = [{ id: "ZP", loc }];
    } else if (filenameUpper.includes("SINYAL")) {
      kode = "BPBYE3"; kategori = "PERAGA SINYAL";
      assets = [{ id: "", loc }];
    } else if (filenameUpper.includes("SERAT OPTIK")) {
      kode = "BPBKF4"; kategori = "SERAT OPTIK";
      if (filenameUpper.includes("ER TELKOM")) assets = [{ id: "ER TELKOM", loc }];
      else if (filenameUpper.includes(" ER ") || filenameUpper.endsWith(" ER")) assets = [{ id: "ER", loc }];
      else assets = [{ id: "", loc }];
    } else if (filenameUpper.includes("CTC") && filenameUpper.includes("CTS")) {
      kode = "BPBYE4"; kategori = "CTC-CTS";
      assets = [{ id: "", loc }];
    } else if (filenameUpper.includes("RADIO BASESTATION")) {
      if (filenameUpper.includes("TAIT")) { kode = "BPBKF3"; kategori = "RADIO BASESTATION TAIT"; }
      else if (filenameUpper.includes("DIGITAL")) { kode = "BPBKF2"; kategori = "RADIO BASESTATION DIGITAL"; }
      else { kode = "BPBKF1"; kategori = "RADIO BASESTATION"; }
      assets = [{ id: "", loc }];
    } else if (filenameUpper.includes("SISTEM WAYSTATION")) {
      kode = "BPBKS5"; kategori = "SISTEM WAYSTATION"; assets = [{ id: "", loc }];
    } else if (filenameUpper.includes("RADIO WAYSTATION") || filenameUpper.includes("RADIO WAY STATION")) {
      kode = "BPBKS16"; kategori = "RADIO WAYSTATION"; assets = [{ id: "WS", loc }];
    } else if (filenameUpper.includes("PTPP") || filenameUpper.includes("PINTU PERLINTASAN")) {
      kode = "BPBKS17"; kategori = "PTPP";
      const fnJpls = extractJplsFromFilename(filenameUpper);
      if (fnJpls.length > 0) {
        assets = fnJpls.map(aid => ({ id: aid, loc: JPL_KNOWN_LOCS[aid] || loc || "" }));
      } else {
        assets = [{ id: "", loc: loc || "" }];
      }
    } else if (filenameUpper.includes("PDSE") || filenameUpper.includes("PERALATAN DALAM PERSINYALAN")) {
      kode = "BPBYE2"; kategori = "PDSE"; 
      assets = [{ id: "", loc }];
    } else if (filenameUpper.includes("PTDS") || filenameUpper.includes("TELEKOMUNIKASI DI STASIUN")) {
      kode = "BPBKS15"; kategori = "PTDS"; assets = [{ id: "", loc }];
    } else if (filenameUpper.includes("PTLS") || filenameUpper.includes("TELEKOMUNIKASI DI LUAR STASIUN")) {
      kode = "BPBKS16"; kategori = "PTLS"; 
      assets = [{ id: "", loc }];
    }
  }

  // Ensure location is never empty (fallback to UNKNOWN for tracing)
  for (const a of assets) {
    if (!a.loc) {
      a.loc = "UNKNOWN";
    }
  }

  return { kode, kategori, assets };
}

export function getBtp(loc) {
  return BTP_JAK_LOCS.includes(loc) ? "BTP JAK" : "BTP BD";
}

export function buildFilename(prefixPeriode, kode, jenis, identitas, tglFull, formatBd) {
  identitas = identitas.replace(/PERAGA SINYAL/g, "SINYAL").replace(/PERAWATAN SINYAL/g, "SINYAL");
  if (formatBd) {
    return `${prefixPeriode}_Resor 1.21 Boo_${kode}_${jenis}_${identitas}_${tglFull}.pdf`;
  }
  return `${jenis.toUpperCase()} ${identitas} ${tglFull}.pdf`;
}
