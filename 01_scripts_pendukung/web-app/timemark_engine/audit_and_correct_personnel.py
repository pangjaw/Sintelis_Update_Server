import sys
import os
import re
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from datetime import datetime
import argparse

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import fitz

# Ensure scripts folder is on path
sys.path.insert(0, str(Path(__file__).parent))
try:
    from employee_manager import load_pegawai_config, replace_page1_employee_names
except ImportError:
    load_pegawai_config = None
    replace_page1_employee_names = None


def get_roster_sets(pegawai_cfg: dict = None):
    if pegawai_cfg is None:
        if load_pegawai_config:
            pegawai_cfg = load_pegawai_config()
        else:
            pegawai_cfg = {}

    kaur_map = {}  # uppercase name -> dict {nama, nipp, no_sc}
    pnc_map = {}   # uppercase name -> dict {nama, nipp, no_sc}

    for k in pegawai_cfg.get('kaur', []):
        nm = k.get('nama', '').strip().upper()
        if nm:
            kaur_map[nm] = {
                'nama': nm,
                'nipp': k.get('nipp', ''),
                'no_sc': k.get('no_sc', '')
            }

    for p in pegawai_cfg.get('pnc', []):
        nm = p.get('nama', '').strip().upper()
        if nm:
            pnc_map[nm] = {
                'nama': nm,
                'nipp': p.get('nipp', ''),
                'no_sc': p.get('no_sc', '')
            }

    return kaur_map, pnc_map, pegawai_cfg


def extract_page_ocr_text(page: fitz.Page) -> str:
    """Fallback OCR extraction for image-only/scanned PDF pages."""
    try:
        import pytesseract
        from PIL import Image
        import io

        candidates = [
            os.environ.get("TESSERACT_CMD"),
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
        tesseract_bin = next((c for c in candidates if c and os.path.isfile(c)), None)
        if not tesseract_bin:
            import shutil
            tesseract_bin = shutil.which("tesseract")
        if tesseract_bin:
            pytesseract.pytesseract.tesseract_cmd = str(tesseract_bin)

        pix = page.get_pixmap(dpi=150)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        raw_ocr = pytesseract.image_to_string(img)

        # Normalize common OCR misreadings for Indonesian railway names:
        # e.g. DED! -> DEDI, pipes/1 inside letters -> I
        t = re.sub(r'(?<=[A-Za-z])!', 'I', raw_ocr)
        t = re.sub(r'!(?=[A-Za-z])', 'I', t)
        t = re.sub(r'(?<=[A-Za-z])[|1](?=[A-Za-z])', 'I', t)
        return t.upper()
    except Exception:
        return ""


def extract_personnel_from_pdf(doc: fitz.Document, kaur_map: dict, pnc_map: dict, return_unauthorized: bool = False):
    if len(doc) == 0:
        return ([], [], [], []) if return_unauthorized else ([], [], [])

    text = doc[0].get_text('text').upper()
    # OCR Fallback if page 1 is scanned or contains no digital text (aktif otomatis secara default)
    if len(text.strip()) < 10 and os.environ.get("ENABLE_OCR_FALLBACK", "1") != "0":
        ocr_text = extract_page_ocr_text(doc[0])
        if ocr_text:
            text = ocr_text

    lines = [re.sub(r'\s+', ' ', line).strip(' :;,') for line in text.splitlines()]
    start = None
    for i, line in enumerate(lines):
        if re.search(r'^DILAKSANAKAN\s+OLEH', line):
            start = i
            break
        if line == 'DILAKSANAKAN' and i + 1 < len(lines) and re.match(r'^OLEH', lines[i + 1]):
            start = i + 1
            break

    found_kaur, found_pnc, names = [], [], []
    seen = set()
    roster = list(kaur_map.items()) + list(pnc_map.items())
    stop_words = {
        'TIDAK', 'MIRING', 'BERSIH', 'ADA', 'RETAK', 'KOTOR', 'TERTAMBAT',
        'KUAT', 'DAN', 'RATA', 'BAIK', 'KENCANG', 'YA', 'TIDAK ADA',
        'LOKASI', 'CILEBUT', 'BOGOR', 'CIOMAS', 'BOO', 'CLT', 'COS', 'BOP', 'BTT', 'MSG', 'CGB',
        'DISETUJUI', 'DIKETAHUI', 'DISETUJUI OLEH', 'DIKETAHUI OLEH', 'PRP', 'NIPP', 'TANGGAL', 'TGL',
        'HASIL', 'KETERANGAN', 'KEGIATAN', 'REFERENSI', 'STANDAR', 'ITEM',
        'NO', 'SC', 'NO.', 'SC.'
    }
    unauthorized = []
    section_lines = []

    def make_roster_pat(n: str) -> str:
        clean_chars = [re.escape(c) for c in re.sub(r'[^A-Z]', '', n.upper())]
        return r'\b' + r'\s*'.join(clean_chars) + r'\b'

    if start is not None:
        for line in lines[start + 1:]:
            if re.search(r'^(DISETUJUI|DIKETAHUI)\b', line) or re.search(r'\b(DISETUJUI\s+OLEH|DIKETAHUI\s+OLEH)\b', line):
                break
            if re.match(r'^(ITEM\s+PERAWATAN|NOMOR\s+ASET|NOMOR\s+SINYAL)', line.strip(), re.I):
                break
            if re.match(r'^(NO\.?\s*SC|NO\b|SC\b)', line.strip(), re.I):
                continue
            if line and not re.match(r'^(PRP|NIPP)\b', line.strip(), re.I):
                section_lines.append(line)
        section = '\n'.join(section_lines)

        matched_roster = []
        for name, obj in roster:
            pattern = make_roster_pat(name)
            if re.search(pattern, section) and name not in seen:
                seen.add(name)
                matched_roster.append((name, obj))
                target = found_kaur if name in kaur_map else found_pnc
                if obj['nama'] not in {x['nama'] for x in target}:
                    target.append(obj)

        for name, _ in matched_roster:
            names.append(name)

    unauthorized = []
    for raw in section_lines:
        for segment in re.split(r'[,;]', raw):
            candidate = re.sub(r'[^A-Z .-]', ' ', segment).strip()
            candidate = re.sub(r'\s+', ' ', candidate).strip(' .,-')
            words = candidate.split()
            if not (1 <= len(words) <= 4) or any(word in stop_words for word in words):
                continue
            if not re.fullmatch(r'[A-Z][A-Z .-]*', candidate):
                continue
            contained_roster = [name for name, _ in roster
                                if re.search(make_roster_pat(name), candidate)]
            if contained_roster:
                for matched_name in contained_roster:
                    obj = kaur_map.get(matched_name) or pnc_map.get(matched_name)
                    if obj:
                        target = found_kaur if matched_name in kaur_map else found_pnc
                        if obj['nama'] not in {x['nama'] for x in target}:
                            target.append(obj)
                if candidate not in seen:
                    seen.add(candidate)
                    names.append(candidate)
            else:
                if candidate not in unauthorized:
                    unauthorized.append(candidate)

    # Some PDFs place personnel below the checklist, after a second NO. SC.
    # Detect name lines followed by PRP/NIPP identifiers across the full page.
    if not names:
        page_lines = [re.sub(r'\s+', ' ', line).strip(' :;,') for line in text.splitlines()]
        for i, line in enumerate(page_lines[:-1]):
            next_line = page_lines[i + 1]
            candidate = line.strip()
            if not re.fullmatch(r'[A-Z][A-Z .-]*', candidate):
                continue
            words = candidate.split()
            if not (1 <= len(words) <= 4) or any(word in stop_words for word in words):
                continue
            if not re.match(r'^(PRP|NIPP)\.?\s*[.\d-]+$', next_line):
                continue
            if candidate not in seen:
                seen.add(candidate)
                names.append(candidate)
                for r_name, r_obj in roster:
                    if re.search(make_roster_pat(r_name), candidate):
                        target = found_kaur if r_name in kaur_map else found_pnc
                        if r_obj['nama'] not in {x['nama'] for x in target}:
                            target.append(r_obj)

    # If layout separated personnel columns (e.g. CTC-CTS where KAUR/PNC appear in adjacent blocks),
    # search full page 1 text for any roster members not yet captured.
    if len(found_kaur) < 1 or len(found_pnc) < 2:
        found_names = {x['nama'] for x in found_kaur} | {x['nama'] for x in found_pnc}
        for name, obj in roster:
            if name in found_names:
                continue
            pattern = make_roster_pat(name)
            if re.search(pattern, text):
                seen.add(name)
                target = found_kaur if name in kaur_map else found_pnc
                if obj['nama'] not in {x['nama'] for x in target}:
                    target.append(obj)
                names.append(name)

    clean_technicians = [k['nama'] for k in found_kaur] + [p['nama'] for p in found_pnc]
    if not clean_technicians:
        seen_clean = set()
        for candidate in names:
            if candidate not in seen_clean:
                seen_clean.add(candidate)
                clean_technicians.append(candidate)

    if return_unauthorized:
        return found_kaur, found_pnc, clean_technicians, unauthorized
    return found_kaur, found_pnc, clean_technicians



def extract_missing_no_sc(doc: fitz.Document, personnel_names: list[str], kaur_map: dict, pnc_map: dict):
    """Return profile names whose PRP/NIPP cell is blank on the same PDF row."""
    if len(doc) == 0 or not personnel_names:
        return []
    page = doc[0]

    blocks = page.get_text('dict').get('blocks', [])
    lines_with_spans = []
    all_spans = []
    for b in blocks:
        for l in b.get('lines', []):
            line_spans = [s for s in l.get('spans', []) if s.get('text', '').strip()]
            if line_spans:
                all_spans.extend(line_spans)
                line_str = ' '.join(s['text'].strip() for s in line_spans).upper()
                lines_with_spans.append((line_str, l['bbox'], line_spans))

    names = {re.sub(r'\s+', ' ', n).strip().upper() for n in personnel_names}

    # Locate technician rows
    tech_rows = []
    matched_names = set()
    for name in names:
        norm_name = re.sub(r'[^A-Z]', '', name)
        for line_str, bbox, _ in lines_with_spans:
            clean_l = re.sub(r'[^A-Z]', '', line_str)
            if norm_name and (norm_name == clean_l or (len(norm_name) >= 6 and norm_name in clean_l)):
                tech_rows.append((name, bbox))
                matched_names.add(name)
                break

    for name in names - matched_names:
        norm_name = re.sub(r'[^A-Z]', '', name)
        for s in all_spans:
            clean_s = re.sub(r'[^A-Z]', '', s.get('text', '')).upper()
            if norm_name and (norm_name == clean_s or (len(norm_name) >= 6 and norm_name in clean_s)):
                tech_rows.append((name, s['bbox']))
                matched_names.add(name)
                break

    if not tech_rows:
        return []

    # Fast column boundary: standard railway checklist column has SC/PRP/NIPP at right
    try:
        name_right = max(r[1][2] for r in tech_rows)
        value_left = max(name_right + 8.0, 420.0)
    except Exception:
        value_left = 430.0

    missing = []
    for name, bbox in tech_rows:
        profile = kaur_map.get(name) or pnc_map.get(name)
        if not profile or not profile.get('no_sc'):
            continue
        y0, y1 = bbox[1], bbox[3]
        row_values = [
            s for s in all_spans
            if s['bbox'][0] >= value_left - 15
            and s['bbox'][1] < y1 + 5
            and s['bbox'][3] > y0 - 5
        ]
        has_sc = any(
            re.match(r'^(PRP|NIPP)\.?\s*[.\d-]+$', s['text'].strip(), re.I)
            for s in row_values
        )
        if not has_sc:
            missing.append(name)
    return list(dict.fromkeys(missing))


def classify_audit_status(found_kaur: list, found_pnc: list, unauthorized: list = None):
    num_k = len(found_kaur)
    num_p = len(found_pnc)
    short_label = f'{num_k} KAUR, {num_p} PNC'

    # Jika ada personil non-teknisi (misal KUPT / pihak luar) yang masuk ke kolom pelaksana -> TEMUAN UTAMA (Perlu Koreksi)
    if unauthorized:
        unauth_str = ', '.join(unauthorized)
        return 'CRITICAL', f'🚨 {short_label} (Temuan: Ada Personil Non-Teknisi ({unauth_str}) di Kolom Pelaksana - Perlu Koreksi)', 'CRITICAL'

    # 1. Tepat 1 KAUR dan 2 PNC (Sesuai Aturan Standar)
    if num_k == 1 and num_p == 2:
        return 'OK', '✅ 1 KAUR, 2 PNC (Sesuai Aturan)', 'OK'

    # 2. Kurang dari 1 KAUR atau kurang dari 2 PNC -> TEMUAN UTAMA (Perlu Koreksi)
    if num_k < 1 or num_p < 2:
        issues = []
        if num_k == 0:
            issues.append('Tanpa KAUR')
        if num_p < 2:
            issues.append(f'Kurang PNC ({num_p}/2)')
        issue_desc = ' & '.join(issues)
        return 'CRITICAL', f'🚨 {short_label} (Temuan Utama: {issue_desc} - Perlu Koreksi)', 'CRITICAL'

    # 3. 2 KAUR 2 PNC, 1 KAUR 3 PNC, dsb (Kelebihan Personil) -> TEMUAN BIASA (Aman / Tidak Perlu Koreksi)
    return 'WARNING', f'ℹ️ {short_label} (Temuan Biasa: Kelebihan Personil - Tidak Perlu Koreksi)', 'WARNING'


def audit_folder(folder_path: Path, pegawai_cfg: dict = None):
    import concurrent.futures
    kaur_map, pnc_map, cfg = get_roster_sets(pegawai_cfg)

    IGNORED_DIRS = {
        'backups', 'backup', '_temp_merged', '_temp', '03_photos_export',
        '04_photos_edited', '05_pdf_merged', '.git', 'node_modules', '__pycache__'
    }
    pdf_files = []
    for root, dirs, fnames in os.walk(folder_path):
        dirs[:] = [d for d in dirs if d.lower() not in IGNORED_DIRS and not d.startswith('.')]
        for fn in sorted(fnames):
            if fn.lower().endswith('.pdf'):
                pdf_files.append(Path(root) / fn)

    def _audit_single_pdf(pdf_p: Path):
        fname = pdf_p.name
        try:
            doc = fitz.open(pdf_p)
            found_k, found_p, raw_personnel, unauth = extract_personnel_from_pdf(doc, kaur_map, pnc_map, return_unauthorized=True)
            if raw_personnel and not found_k and not found_p:
                for raw_name in raw_personnel:
                    normalized = re.sub(r'\s+', ' ', raw_name).strip().upper()
                    if normalized in kaur_map:
                        found_k.append(kaur_map[normalized])
                    elif normalized in pnc_map:
                        found_p.append(pnc_map[normalized])
            missing_no_sc = extract_missing_no_sc(doc, raw_personnel, kaur_map, pnc_map)
            doc.close()
        except Exception:
            found_k, found_p, raw_personnel, unauth, missing_no_sc = [], [], [], [], []

        status_code, status_label, severity = classify_audit_status(found_k, found_p, unauth)
        if missing_no_sc:
            status_label += f' | ⚠️ SC belum lengkap: {len(missing_no_sc)}'
        key = f'{len(found_k)} KAUR, {len(found_p)} PNC'
        if unauth:
            key += f' + {len(unauth)} Non-Teknisi'

        m_date = re.search(r'(\d{2})-(\d{2})-(\d{4})', fname)
        file_date_str = m_date.group(0) if m_date else ''

        is_compliant = (severity == 'OK')
        needs_corr = (severity == 'CRITICAL')
        needs_sc = bool(missing_no_sc)

        return {
            'file': fname,
            'path': str(pdf_p).replace('\\', '/'),
            'date': file_date_str,
            'status': 'compliant' if (is_compliant and not needs_sc) else status_code,
            'status_code': status_code,
            'status_label': status_label,
            'severity': severity,
            'needs_correction': needs_corr,
            'needs_sc_correction': needs_sc,
            'missing_no_sc': missing_no_sc,
            'no_sc_missing_count': len(missing_no_sc),
            'unauthorized': unauth,
            'key': key,
            'kaur': [k['nama'] for k in found_k],
            'pnc': [p['nama'] for p in found_p],
            'personnel': raw_personnel or [k['nama'] for k in found_k] + [p['nama'] for p in found_p],
            'personnel_source': 'file' if raw_personnel else 'profile_fallback',
            'num_kaur': len(found_k),
            'num_pnc': len(found_p)
        }

    max_workers = min(12, max(4, (os.cpu_count() or 4) * 2))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        files_result = list(executor.map(_audit_single_pdf, pdf_files))

    file_to_tim = load_or_build_file_tim_mapping(folder_path)
    all_kaur = list(kaur_map.values())
    all_pnc = list(pnc_map.values())

    files_by_date = defaultdict(list)
    for f in files_result:
        f['tim'] = file_to_tim.get(f['file'], 1)
        f['team_label'] = f"Tim {f['tim']}"
        d = f.get('date') or 'UNKNOWN'
        files_by_date[d].append(f)

    for d_str, date_files in files_by_date.items():
        m_day = re.match(r'^(\d{2})', d_str)
        day_num = int(m_day.group(1)) if m_day else 1

        tim1_files = [f for f in date_files if f.get('tim', 1) == 1]
        tim2_files = [f for f in date_files if f.get('tim', 1) == 2]
        tim3_files = [f for f in date_files if f.get('tim', 1) >= 3]

        # ── 1. TIM 1: selalu memakai personil yang sudah tertulis di berkas fisik asli ──
        t1_kaur_found = []
        t1_pnc_found = []
        for f in tim1_files:
            for k in f.get('kaur', []):
                if k in kaur_map and kaur_map[k] not in t1_kaur_found:
                    t1_kaur_found.append(kaur_map[k])
            for p in f.get('pnc', []):
                if p in pnc_map and pnc_map[p] not in t1_pnc_found:
                    t1_pnc_found.append(pnc_map[p])

        if not t1_kaur_found and all_kaur:
            k_idx = (day_num - 1) % len(all_kaur)
            t1_kaur_found.append(all_kaur[k_idx])
        while len(t1_pnc_found) < 2 and all_pnc:
            for p in all_pnc:
                if p not in t1_pnc_found:
                    t1_pnc_found.append(p)
                    break

        t1_kaur_names = {k['nama'] for k in t1_kaur_found}
        t1_pnc_names = {p['nama'] for p in t1_pnc_found}

        for f in tim1_files:
            f['expected_kaur'] = list(t1_kaur_names)
            f['expected_pnc'] = list(t1_pnc_names)
            f['team_mismatch'] = False

        # ── 2. TIM 2: rotasi dari profil dinasan pegawai yang belum bertugas di Tim 1 ──
        if tim2_files:
            rem_kaur = [k for k in all_kaur if k['nama'] not in t1_kaur_names]
            chosen_kaur_t2 = rem_kaur[0] if rem_kaur else all_kaur[day_num % len(all_kaur)]

            rem_pnc = [p for p in all_pnc if p['nama'] not in t1_pnc_names]
            if len(rem_pnc) >= 2:
                shift = (day_num - 1) % len(rem_pnc)
                chosen_pnc_t2 = [rem_pnc[shift], rem_pnc[(shift + 1) % len(rem_pnc)]]
            elif len(rem_pnc) == 1:
                chosen_pnc_t2 = [rem_pnc[0]]
                for p in all_pnc:
                    if p not in chosen_pnc_t2:
                        chosen_pnc_t2.append(p)
                        break
            else:
                chosen_pnc_t2 = [all_pnc[(day_num - 1) % len(all_pnc)], all_pnc[day_num % len(all_pnc)]]

            exp_k_name = chosen_kaur_t2['nama']
            exp_p_names = [p['nama'] for p in chosen_pnc_t2]

            for f in tim2_files:
                f['expected_kaur'] = [exp_k_name]
                f['expected_pnc'] = exp_p_names
                curr_k = f.get('kaur', [])
                curr_p = f.get('pnc', [])

                matched = (
                    len(curr_k) == 1 and curr_k[0] == exp_k_name and
                    set(curr_p) == set(exp_p_names)
                )
                if not matched:
                    f['team_mismatch'] = True
                    f['needs_correction'] = True
                    f['severity'] = 'CRITICAL'
                    f['status_code'] = 'TEAM_MISMATCH'
                    terbaca_str = ', '.join(curr_k + curr_p) or 'Kosong'
                    seharusnya_str = f"{exp_k_name}, {', '.join(exp_p_names)}"
                    f['status_label'] = f"⚠️ Tim 2 Beda Personil: Terbaca ({terbaca_str}), Seharusnya Tim 2 ({seharusnya_str})"
                else:
                    f['team_mismatch'] = False

        # ── 3. TIM 3: rotasi konsisten dari profil ──
        if tim3_files:
            seed = sum(ord(c) for c in f"{d_str}_tim3")
            rng = random.Random(seed)
            chosen_kaur_t3 = rng.choice(all_kaur)
            sample_pnc = rng.sample(all_pnc, min(2, len(all_pnc)))
            exp_k3_name = chosen_kaur_t3['nama']
            exp_p3_names = [p['nama'] for p in sample_pnc]

            for f in tim3_files:
                f['expected_kaur'] = [exp_k3_name]
                f['expected_pnc'] = exp_p3_names
                curr_k = f.get('kaur', [])
                curr_p = f.get('pnc', [])
                matched = (
                    len(curr_k) == 1 and curr_k[0] == exp_k3_name and
                    set(curr_p) == set(exp_p3_names)
                )
                if not matched:
                    f['team_mismatch'] = True
                    f['needs_correction'] = True
                    f['severity'] = 'CRITICAL'
                    f['status_code'] = 'TEAM_MISMATCH'
                    terbaca_str = ', '.join(curr_k + curr_p) or 'Kosong'
                    seharusnya_str = f"{exp_k3_name}, {', '.join(exp_p3_names)}"
                    f['status_label'] = f"⚠️ Tim 3 Beda Personil: Terbaca ({terbaca_str}), Seharusnya Tim 3 ({seharusnya_str})"
                else:
                    f['team_mismatch'] = False

    counts_by_key = {}
    ok_count = 0
    critical_count = 0
    warning_count = 0

    for item in files_result:
        key = item['key']
        counts_by_key[key] = counts_by_key.get(key, 0) + 1
        sev = item['severity']
        if sev == 'OK' and not item.get('team_mismatch'):
            ok_count += 1
        elif sev == 'CRITICAL' or item.get('team_mismatch'):
            critical_count += 1
        else:
            warning_count += 1

    total_sc_missing = sum(1 for f in files_result if f.get('needs_sc_correction'))
    total_team_mismatch = sum(1 for f in files_result if f.get('team_mismatch'))
    summary = {
        'total_files': len(files_result),
        'compliant': ok_count,
        'needs_correction': critical_count,
        'needs_sc_correction': total_sc_missing,
        'warning_count': warning_count,
        'team_mismatch_count': total_team_mismatch,
        'tim_1_count': sum(1 for f in files_result if f.get('tim', 1) == 1),
        'tim_2_count': sum(1 for f in files_result if f.get('tim', 1) == 2),
        'tim_3_count': sum(1 for f in files_result if f.get('tim', 1) >= 3),
    }

    return {
        'total_files': len(files_result),
        'ok_count': ok_count,
        'critical_count': critical_count,
        'warning_count': warning_count,
        'mismatch_count': critical_count + warning_count,
        'counts_by_key': counts_by_key,
        'summary': summary,
        'files': files_result
    }


def correct_single_file(pdf_path: Path, kaur_obj: dict, pnc1_obj: dict, pnc2_obj: dict, sc_only: bool = False) -> bool:
    if not pdf_path.exists():
        raise FileNotFoundError(f'File tidak ditemukan: {pdf_path}')

    new_employees = [
        {'nama': kaur_obj['nama'], 'no_sc': kaur_obj.get('no_sc', '')},
        {'nama': pnc1_obj['nama'], 'no_sc': pnc1_obj.get('no_sc', '')},
        {'nama': pnc2_obj['nama'], 'no_sc': pnc2_obj.get('no_sc', '')}
    ]

    doc = fitz.open(pdf_path)
    ok = replace_page1_employee_names(doc, new_employees, sc_only=sc_only)
    if ok:
        doc.save(pdf_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
    doc.close()
    return ok


def load_or_build_file_tim_mapping(folder_path: Path) -> dict[str, int]:
    """Mengembalikan pemetaan {filename: tim_number (1, 2, 3)} untuk folder target."""
    app_data = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        folder_path / "schedule.json",
        folder_path.parent / "schedule.json",
        folder_path.parent.parent / "schedule.json",
        folder_path / "temp_custom_schedule.json",
        folder_path / "temp_dinasan_schedule.json",
        Path("schedule.json"),
        Path("logs/schedule.json"),
        Path("logs/temp_custom_schedule.json"),
        Path("logs/temp_dinasan_schedule.json"),
    ]
    if app_data:
        candidates.insert(3, Path(app_data) / "SintelisUtility" / "schedule.json")

    for cand in candidates:
        if cand.is_file():
            try:
                with open(cand, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    mapping = {}
                    for s in data.get("schedules", []):
                        f_name = s.get("file")
                        tim_num = s.get("tim", 1)
                        if f_name:
                            mapping[f_name] = tim_num
                    if mapping:
                        return mapping
            except Exception:
                pass

    try:
        from scheduler import build_schedule, load_mapping, load_data_acuan
        engine_dir = Path(__file__).parent
        base_dir = engine_dir.parent
        m_candidates = [
            engine_dir / "asset_waktu_mapping.json",
            base_dir / "config" / "asset_waktu_mapping.json",
        ]
        m_path = next((p for p in m_candidates if p.is_file()), None)
        mapping = load_mapping(m_path) if m_path else {}

        a_candidates = [
            engine_dir / "data_acuan_tenaga_gabungan.json",
            base_dir / "config" / "data_acuan_tenaga_gabungan.json",
        ]
        a_path = next((p for p in a_candidates if p.is_file()), None)
        acuan = load_data_acuan(a_path) if a_path else {}

        sched = build_schedule(
            pdf_dir=folder_path,
            photos_dir=Path("03_photos_export"),
            mapping=mapping,
            acuan=acuan,
            jam_mulai=7 * 60,
            jam_selesai=18 * 60,
            tim_max=2
        )
        if sched.get("schedules"):
            return {s.get("file"): s.get("tim", 1) for s in sched["schedules"] if s.get("file")}
    except Exception:
        pass

    return {}


def auto_correct_files(folder_path: Path, target_file_names: list = None, pegawai_cfg: dict = None):
    kaur_map, pnc_map, cfg = get_roster_sets(pegawai_cfg)
    all_kaur = list(kaur_map.values())
    all_pnc = list(pnc_map.values())

    if not all_kaur or len(all_pnc) < 2:
        raise ValueError('Daftar pegawai minimal harus memiliki 1 KAUR dan 2 PNC.')

    audit_res = audit_folder(folder_path, cfg)
    all_files = audit_res['files']

    # Dapatkan pemetaan tim untuk setiap file (Tim 1, Tim 2, Tim 3)
    file_to_tim = load_or_build_file_tim_mapping(folder_path)

    # Kelompokkan berkas berdasarkan tanggal (DD-MM-YYYY)
    files_by_date = defaultdict(list)
    for f in all_files:
        d = f.get('date') or 'UNKNOWN'
        files_by_date[d].append(f)

    target_set = set(target_file_names) if target_file_names else None
    corrected = []
    failed = []

    for d_str, date_files in sorted(files_by_date.items()):
        # Parse nomor hari untuk rotasi deterministik
        m_day = re.match(r'^(\d{2})', d_str)
        day_num = int(m_day.group(1)) if m_day else 1

        # Pisahkan file pada tanggal ini berdasarkan tim
        tim1_files = [f for f in date_files if file_to_tim.get(f['file'], 1) == 1]
        tim2_files = [f for f in date_files if file_to_tim.get(f['file'], 1) == 2]
        tim3_files = [f for f in date_files if file_to_tim.get(f['file'], 1) >= 3]

        # ── 1. TIM 1 ──
        # Kumpulkan personil yang ada di berkas Tim 1
        t1_kaur_found = []
        t1_pnc_found = []
        t1_pnc_usage = Counter()

        for f in tim1_files:
            for k in f.get('kaur', []):
                if k in kaur_map and kaur_map[k] not in t1_kaur_found:
                    t1_kaur_found.append(kaur_map[k])
            for p in f.get('pnc', []):
                if p in pnc_map:
                    if pnc_map[p] not in t1_pnc_found:
                        t1_pnc_found.append(pnc_map[p])
                    t1_pnc_usage[p] += 1

        # Pastikan pool Tim 1 memiliki minimal 1 KAUR dan 2 PNC
        if not t1_kaur_found:
            k_idx = (day_num - 1) % len(all_kaur)
            t1_kaur_found.append(all_kaur[k_idx])

        while len(t1_pnc_found) < 2:
            p_shift = ((day_num - 1) * 2 + len(t1_pnc_found)) % len(all_pnc)
            cand = all_pnc[p_shift]
            if cand not in t1_pnc_found:
                t1_pnc_found.append(cand)
            else:
                for p in all_pnc:
                    if p not in t1_pnc_found:
                        t1_pnc_found.append(p)
                        break

        # Koreksi berkas Tim 1 yang defisit
        for f_info in tim1_files:
            if target_set and f_info['file'] not in target_set:
                continue
            if not f_info.get('needs_correction'):
                continue

            f_path = Path(f_info['path'])
            if not f_path.exists():
                failed.append({'file': f_info['file'], 'error': 'File not found'})
                continue

            existing_k = [kaur_map[k] for k in f_info['kaur'] if k in kaur_map]
            chosen_kaur = existing_k[0] if existing_k else t1_kaur_found[0]

            existing_p = [pnc_map[p] for p in f_info['pnc'] if p in pnc_map]
            chosen_pnc = list(existing_p)

            available_pnc = [p for p in t1_pnc_found if p not in chosen_pnc]
            available_pnc.sort(key=lambda p: (t1_pnc_usage[p['nama']], all_pnc.index(p)))

            while len(chosen_pnc) < 2 and available_pnc:
                p_pick = available_pnc.pop(0)
                chosen_pnc.append(p_pick)
                t1_pnc_usage[p_pick['nama']] += 1

            while len(chosen_pnc) < 2:
                for p in all_pnc:
                    if p not in chosen_pnc:
                        chosen_pnc.append(p)
                        break

            try:
                ok = correct_single_file(f_path, chosen_kaur, chosen_pnc[0], chosen_pnc[1])
                if ok:
                    corrected.append({'file': f_info['file'], 'kaur': chosen_kaur['nama'], 'pnc': [p['nama'] for p in chosen_pnc]})
                else:
                    failed.append({'file': f_info['file'], 'error': 'Gagal menerapkan redaksi'})
            except Exception as e:
                failed.append({'file': f_info['file'], 'error': str(e)})

        # ── 2. TIM 2 ──
        # Sesuai kesepakatan: Personil Tim 2 diambil dari profil yang belum bertugas di Tim 1
        if tim2_files:
            t1_kaur_names = {k['nama'] for k in t1_kaur_found}
            t1_pnc_names = {p['nama'] for p in t1_pnc_found}

            rem_kaur = [k for k in all_kaur if k['nama'] not in t1_kaur_names]
            chosen_kaur_t2 = rem_kaur[0] if rem_kaur else all_kaur[day_num % len(all_kaur)]

            rem_pnc = [p for p in all_pnc if p['nama'] not in t1_pnc_names]
            chosen_pnc_t2 = []
            if len(rem_pnc) >= 2:
                shift = (day_num - 1) % len(rem_pnc)
                chosen_pnc_t2 = [rem_pnc[shift], rem_pnc[(shift + 1) % len(rem_pnc)]]
            elif len(rem_pnc) == 1:
                chosen_pnc_t2.append(rem_pnc[0])
                for p in all_pnc:
                    if p not in chosen_pnc_t2:
                        chosen_pnc_t2.append(p)
                        break
            else:
                chosen_pnc_t2 = [all_pnc[(day_num - 1) % len(all_pnc)], all_pnc[day_num % len(all_pnc)]]

            for f_info in tim2_files:
                if target_set and f_info['file'] not in target_set:
                    continue

                f_path = Path(f_info['path'])
                if not f_path.exists():
                    failed.append({'file': f_info['file'], 'error': 'File not found'})
                    continue

                curr_k = f_info.get('kaur', [])
                curr_p = f_info.get('pnc', [])
                already_matched = (
                    len(curr_k) == 1 and curr_k[0] == chosen_kaur_t2['nama'] and
                    set(curr_p) == {p['nama'] for p in chosen_pnc_t2}
                )
                if already_matched:
                    continue

                try:
                    ok = correct_single_file(f_path, chosen_kaur_t2, chosen_pnc_t2[0], chosen_pnc_t2[1])
                    if ok:
                        corrected.append({'file': f_info['file'], 'kaur': chosen_kaur_t2['nama'], 'pnc': [p['nama'] for p in chosen_pnc_t2]})
                    else:
                        failed.append({'file': f_info['file'], 'error': 'Gagal menerapkan redaksi'})
                except Exception as e:
                    failed.append({'file': f_info['file'], 'error': str(e)})

        # ── 3. TIM 3 ──
        # Sesuai kesepakatan: Tim 3 menggunakan KAUR dan 2 PNC konsisten dari profil untuk seluruh berkas Tim 3 hari itu
        if tim3_files:
            seed = sum(ord(c) for c in f"{d_str}_tim3")
            rng = random.Random(seed)
            chosen_kaur_t3 = rng.choice(all_kaur)
            sample_pnc = rng.sample(all_pnc, min(2, len(all_pnc)))
            chosen_pnc_t3 = list(sample_pnc)
            while len(chosen_pnc_t3) < 2:
                for p in all_pnc:
                    if p not in chosen_pnc_t3:
                        chosen_pnc_t3.append(p)
                        break

            for f_info in tim3_files:
                if target_set and f_info['file'] not in target_set:
                    continue

                f_path = Path(f_info['path'])
                if not f_path.exists():
                    failed.append({'file': f_info['file'], 'error': 'File not found'})
                    continue

                curr_k = f_info.get('kaur', [])
                curr_p = f_info.get('pnc', [])
                already_matched = (
                    len(curr_k) == 1 and curr_k[0] == chosen_kaur_t3['nama'] and
                    set(curr_p) == {p['nama'] for p in chosen_pnc_t3}
                )
                if already_matched:
                    continue

                try:
                    ok = correct_single_file(f_path, chosen_kaur_t3, chosen_pnc_t3[0], chosen_pnc_t3[1])
                    if ok:
                        corrected.append({'file': f_info['file'], 'kaur': chosen_kaur_t3['nama'], 'pnc': [p['nama'] for p in chosen_pnc_t3]})
                    else:
                        failed.append({'file': f_info['file'], 'error': 'Gagal menerapkan redaksi'})
                except Exception as e:
                    failed.append({'file': f_info['file'], 'error': str(e)})

    post_audit = audit_folder(folder_path, cfg)
    return {
        'total_scanned': len(all_files),
        'total_attempted': len(corrected) + len(failed),
        'total_corrected': len(corrected),
        'total_failed': len(failed),
        'corrected': corrected,
        'failed': failed,
        'summary': post_audit.get('summary'),
        'total_files': post_audit.get('total_files'),
        'ok_count': post_audit.get('ok_count'),
        'critical_count': post_audit.get('critical_count'),
        'files': post_audit.get('files')
    }


def correct_no_sc_file(pdf_path: Path, profiles: list[dict]) -> bool:
    if not pdf_path.exists():
        raise FileNotFoundError(f'File tidak ditemukan: {pdf_path}')
    doc = fitz.open(pdf_path)
    employees = [{'nama': p['nama'], 'no_sc': p.get('no_sc', '')} for p in profiles]
    ok = replace_page1_employee_names(doc, employees, sc_only=True)
    if ok:
        doc.save(pdf_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
    doc.close()
    return ok


def auto_correct_no_sc_files(folder_path: Path, pegawai_cfg: dict = None):
    kaur_map, pnc_map, cfg = get_roster_sets(pegawai_cfg)
    audit_res = audit_folder(folder_path, cfg)
    targets = [f for f in audit_res['files'] if f.get('needs_sc_correction')]
    corrected, failed = [], []
    for info in targets:
        profiles = []
        unresolved = []
        for name in info.get('missing_no_sc', []):
            key = re.sub(r'\s+', ' ', name).strip().upper()
            profile = kaur_map.get(key) or pnc_map.get(key)
            if profile and profile.get('no_sc'):
                profiles.append(profile)
            else:
                unresolved.append(name)
        try:
            ok = correct_no_sc_file(Path(info['path']), profiles) if profiles else False
            if ok:
                corrected.append({'file': info['file'], 'names': [p['nama'] for p in profiles]})
            if unresolved or not ok:
                reasons = []
                if unresolved:
                    reasons.append('Profil/nomor SC tidak tersedia: ' + ', '.join(unresolved))
                if profiles and not ok:
                    reasons.append('Layout PDF tidak dapat dibaca')
                failed.append({'file': info['file'], 'error': '; '.join(reasons)})
        except Exception as exc:
            failed.append({'file': info['file'], 'error': str(exc)})
    post_audit = audit_folder(folder_path, cfg)
    return {
        'total_scanned': len(audit_res.get('files', [])),
        'total_sc_attempted': len(targets),
        'total_sc_corrected': len(corrected),
        'total_sc_failed': len(failed),
        'corrected': corrected,
        'failed': failed,
        'summary': post_audit.get('summary'),
        'total_files': post_audit.get('total_files'),
        'ok_count': post_audit.get('ok_count'),
        'critical_count': post_audit.get('critical_count'),
        'files': post_audit.get('files')
    }


def main():
    parser = argparse.ArgumentParser(description='Audit and correct personnel compliance (1 KAUR, 2 PNC).')
    parser.add_argument('--action', choices=['audit', 'correct-single', 'auto-correct-batch', 'auto-correct-no-sc'], default='audit')
    parser.add_argument('--folder', default='02_pdf_target', help='Target directory containing PDF files')
    parser.add_argument('--file', help='Single PDF file path for correct-single')
    parser.add_argument('--kaur', help='KAUR name for correct-single')
    parser.add_argument('--pnc1', help='PNC 1 name for correct-single')
    parser.add_argument('--pnc2', help='PNC 2 name for correct-single')
    args = parser.parse_args()

    folder_path = Path(args.folder)

    if args.action == 'audit':
        if not folder_path.exists():
            print(json.dumps({'error': f'Folder tidak ditemukan: {folder_path}'}))
            sys.exit(1)
        res = audit_folder(folder_path)
        print(json.dumps(res, indent=2))

    elif args.action == 'correct-single':
        if not args.file:
            print(json.dumps({'error': 'Parameter --file diperlukan untuk correct-single'}))
            sys.exit(1)
        pdf_path = Path(args.file)
        kaur_map, pnc_map, _ = get_roster_sets()
        k_obj = kaur_map.get(args.kaur.strip().upper()) if args.kaur else None
        p1_obj = pnc_map.get(args.pnc1.strip().upper()) if args.pnc1 else None
        p2_obj = pnc_map.get(args.pnc2.strip().upper()) if args.pnc2 else None
        if not k_obj or not p1_obj or not p2_obj:
            print(json.dumps({'error': 'Nama personil tidak valid atau tidak terdaftar di konfigurasi'}))
            sys.exit(1)
        ok = correct_single_file(pdf_path, k_obj, p1_obj, p2_obj)
        print(json.dumps({'success': ok, 'file': str(pdf_path)}))

    elif args.action == 'auto-correct-batch':
        if not folder_path.exists():
            print(json.dumps({'error': f'Folder tidak ditemukan: {folder_path}'}))
            sys.exit(1)
        print(f"[STEP 3.5] Memulai audit dan koreksi personil (1 KAUR, 2 PNC) pada folder: {folder_path}...", file=sys.stderr)
        res = auto_correct_files(folder_path)
        print(f"[STEP 3.5] Selesai! Berkas diperiksa: {res.get('total_scanned', 0)}, Temuan utama perlu koreksi: {res['total_attempted']}, Berhasil dikoreksi: {res['total_corrected']}, Gagal: {res['total_failed']}.", file=sys.stderr)
        
        # Invalidate cache if 02_pdf_target
        cache_path = Path('logs/file_personnel_cache.json')
        if cache_path.exists() and ('02_pdf_target' in str(folder_path) or folder_path.name == '02_pdf_target'):
            try:
                cache_path.unlink()
            except Exception:
                pass

        print(json.dumps(res, indent=2))

    elif args.action == 'auto-correct-no-sc':
        if not folder_path.exists():
            print(json.dumps({'error': f'Folder tidak ditemukan: {folder_path}'}))
            sys.exit(1)
        res = auto_correct_no_sc_files(folder_path)
        cache_path = Path('logs/file_personnel_cache.json')
        if cache_path.exists() and ('02_pdf_target' in str(folder_path) or folder_path.name == '02_pdf_target'):
            try:
                cache_path.unlink()
            except Exception:
                pass
        print(json.dumps(res, indent=2))


if __name__ == '__main__':
    main()
