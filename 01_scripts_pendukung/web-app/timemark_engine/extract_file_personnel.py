import sys
import os
import json
import re
from pathlib import Path
from datetime import datetime
import argparse

import fitz

sys.path.insert(0, str(Path(__file__).parent))
try:
    from audit_and_correct_personnel import extract_personnel_from_pdf, get_roster_sets
except ImportError:
    extract_personnel_from_pdf = None
    get_roster_sets = None
try:
    from employee_manager import load_pegawai_config, get_tim2_roster_for_date
except ImportError:
    get_tim2_roster_for_date = None
    load_pegawai_config = None


try:
    from scheduler import detect_category_from_filename
except ImportError:
    detect_category_from_filename = None

try:
    from extract_pdf_dates import parse_target_filename
except ImportError:
    parse_target_filename = None

DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
MONTHS_ID = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mei", 6: "Jun",
    7: "Jul", 8: "Agt", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Des"
}


def parse_date_helper(fn: str, page_text: str = ""):
    m = re.search(r'\b(\d{1,2})-(\d{1,2})-(\d{4})\b', fn)
    if m:
        try:
            d = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).date()
            return d.strftime('%Y-%m-%d'), f"{DAYS_ID[d.weekday()]}, {MONTHS_ID[d.month]} {d.day:02d} {d.year}"
        except ValueError:
            pass
    m = re.search(r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b', fn)
    if m:
        try:
            d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
            return d.strftime('%Y-%m-%d'), f"{DAYS_ID[d.weekday()]}, {MONTHS_ID[d.month]} {d.day:02d} {d.year}"
        except ValueError:
            pass
    if page_text:
        m_page = re.search(r'(?:Tanggal|Tgl)\s*[:]?\s*([^\n\r]+)', page_text, re.I)
        if m_page:
            p_str = m_page.group(1).strip()
            m = re.search(r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b', p_str)
            if m:
                try:
                    d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
                    return d.strftime('%Y-%m-%d'), f"{DAYS_ID[d.weekday()]}, {MONTHS_ID[d.month]} {d.day:02d} {d.year}"
                except ValueError:
                    pass
    return "", ""


def extract_names_from_page1(doc: fitz.Document, valid_names: set = None) -> list:
    if len(doc) == 0 or not extract_personnel_from_pdf:
        return []
    cfg = load_pegawai_config() if load_pegawai_config else {}
    kaur_map, pnc_map, _ = get_roster_sets(cfg) if get_roster_sets else ({}, {}, {})
    _, _, raw_personnel = extract_personnel_from_pdf(doc, kaur_map, pnc_map)
    return raw_personnel


def find_merged_file(file_name: str, tim: int):
    merged_dir = Path('05_pdf_merged') / f'Tim_{tim}'
    if not merged_dir.exists():
        return None
    matches = list(merged_dir.glob(f'**/{file_name}'))
    return matches[0] if matches else None


def main():
    parser = argparse.ArgumentParser(description='Extract and cache personnel for all PDF files.')
    parser.add_argument('--schedule', default='schedule.json', help='Path to schedule.json')
    parser.add_argument('--target-dir', default='02_pdf_target', help='Path to target directory')
    parser.add_argument('--output', default='logs/file_personnel_cache.json', help='Path to output cache JSON')
    args = parser.parse_args()

    schedule_path = Path(args.schedule)
    target_dir = Path(args.target_dir)
    output_path = Path(args.output)

    pegawai_cfg = load_pegawai_config() if load_pegawai_config else None
    valid_names = set()
    if pegawai_cfg:
        for k in pegawai_cfg.get('kaur', []):
            if k.get('nama'):
                valid_names.add(k['nama'].upper().strip())
        for p in pegawai_cfg.get('pnc', []):
            if p.get('nama'):
                valid_names.add(p['nama'].upper().strip())

    # Check if target_dir is custom (not 02_pdf_target) or schedule.json does not exist
    is_pipeline_target = target_dir.resolve() == Path('02_pdf_target').resolve()
    target_pdfs = sorted(target_dir.rglob('*.pdf')) if target_dir.exists() else []

    results = []

    if is_pipeline_target and schedule_path.exists():
        with open(schedule_path, 'r', encoding='utf-8') as f:
            schedules = json.load(f).get('schedules', [])

        files_map = {}
        for item in schedules:
            f_name = item.get('file')
            if not f_name:
                continue
            if f_name not in files_map:
                files_map[f_name] = {
                    'file': f_name,
                    'pdf_path': item.get('pdf_path', ''),
                    'date': item.get('date', ''),
                    'iso_date': item.get('iso_date', ''),
                    'tim': item.get('tim', 1),
                    'btp': item.get('btp', 'BTP JAK'),
                    'category': item.get('category', ''),
                    'identifiers': []
                }
            ident = item.get('identifier')
            if ident and ident not in files_map[f_name]['identifiers']:
                files_map[f_name]['identifiers'].append(ident)

        sorted_files = sorted(files_map.values(), key=lambda x: (x['iso_date'], x['file']))
        idx = 1
        for f_info in sorted_files:
            f_name = f_info['file']
            tim = f_info['tim']
            iso_date = f_info['iso_date']
            pdf_value = f_info.get('pdf_path') or f_name
            target_pdf = Path(str(pdf_value).replace('\\\\', '\\'))
            if not target_pdf.is_file():
                target_pdf = target_dir / f_name
            if not target_pdf.is_file():
                basename = Path(f_name).name
                matches = list(target_dir.rglob(basename)) if target_dir.exists() else []
                target_pdf = matches[0] if matches else Path()

            personnel = []
            raw_names = []
            if target_pdf.is_file():
                try:
                    doc = fitz.open(target_pdf)
                    raw_names = extract_names_from_page1(doc, valid_names)
                    doc.close()
                except Exception as e:
                    print(f'[WARN] Error reading {f_name}: {e}')

            if tim == 1:
                personnel = raw_names
                if not personnel:
                    personnel = ['SUTISNA', 'IWAN SETIAWAN', 'RAIHAN HERPIAN']
            else:
                merged_pdf = find_merged_file(f_name, 2)
                if merged_pdf and merged_pdf.exists():
                    try:
                        doc = fitz.open(merged_pdf)
                        personnel = extract_names_from_page1(doc, valid_names)
                        doc.close()
                    except Exception:
                        pass

                if not personnel and get_tim2_roster_for_date:
                    t2_roster = get_tim2_roster_for_date(iso_date, set(raw_names), pegawai_cfg)
                    personnel = [p['nama'] for p in t2_roster]

            results.append({
                'no': idx,
                'date': f_info['date'],
                'iso_date': iso_date,
                'tim': tim,
                'btp': f_info['btp'],
                'category': f_info['category'],
                'detail_aset': ', '.join(f_info['identifiers']) if f_info['identifiers'] else f_info['category'],
                'personnel': personnel,
                'file': f_name,
                'path': str(target_pdf).replace('\\', '/') if target_pdf.is_file() else ''
            })
            idx += 1
    else:
        # Direct folder scan mode (for custom folder or external directory)
        temp_items = []
        for pdf_p in target_pdfs:
            f_name = pdf_p.name
            page_text = ""
            raw_names = []
            try:
                doc = fitz.open(pdf_p)
                if len(doc) > 0:
                    page_text = doc[0].get_text()
                raw_names = extract_names_from_page1(doc, valid_names)
                doc.close()
            except Exception as e:
                print(f'[WARN] Error reading {f_name}: {e}')

            iso_date, date_str = parse_date_helper(f_name, page_text)

            cat = ""
            ident = ""
            if parse_target_filename:
                info = parse_target_filename(f_name)
                if info:
                    cat, ident, _ = info

            if not cat and detect_category_from_filename:
                cat = detect_category_from_filename(f_name)

            if not ident:
                stem = pdf_p.stem
                stem_clean = re.sub(r'\b\d{1,2}-\d{1,2}-\d{4}\b', '', stem).strip()
                ident = re.sub(r'^PERAWATAN\s+', '', stem_clean, flags=re.I).strip()

            temp_items.append({
                'file': f_name,
                'path': str(pdf_p).replace('\\', '/'),
                'date': date_str or 'Folder Kustom',
                'iso_date': iso_date or '',
                'tim': 1,
                'btp': 'BTP JAK',
                'category': cat or 'UMUM',
                'detail_aset': ident or f_name,
                'personnel': raw_names
            })

        temp_items.sort(key=lambda x: (x['iso_date'], x['file']))
        for idx, item in enumerate(temp_items, 1):
            item['no'] = idx
            results.append(item)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'generated_at': datetime.now().isoformat(),
            'total_files': len(results),
            'files': results
        }, f, indent=2, ensure_ascii=False)

    print(f'[OK] Successfully extracted personnel for {len(results)} files -> {output_path}')


if __name__ == '__main__':
    main()