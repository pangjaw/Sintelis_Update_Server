#!/usr/bin/env python3
"""
scripts/export_dinasan_excel.py
--------------------------------
Generates official KAI-standard "DAFTAR DINASAN PEGAWAI" Excel spreadsheet.
Features:
- Automatic month & day-of-week generation (Senin..Minggu)
- Official KAI logo insertion
- Clean grid styling matching KAI Resor Sintelisp format
- Resor set to "P" for all days
- Tim 1 & Tim 2 personnel set to "P" on active maintenance days
- Non-scheduled cells left blank for user's manual customization
- Automatic Excel COUNTIF formulas for row & column totals
- Real-time Excel Conditional Formatting for P, S, M, L, CT codes
- Official signature block
"""

import sys
import os
import re
import json
import calendar
from datetime import datetime
from pathlib import Path
import argparse

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image as OpenpyxlImage
from openpyxl.formatting.rule import CellIsRule

from employee_manager import load_pegawai_config

try:
    from audit_and_correct_personnel import extract_personnel_from_pdf, get_roster_sets
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from audit_and_correct_personnel import extract_personnel_from_pdf, get_roster_sets

import fitz

MONTH_NAMES_ID = {
    1: "JANUARI", 2: "FEBRUARI", 3: "MARET", 4: "APRIL",
    5: "MEI", 6: "JUNI", 7: "JULI", 8: "AGUSTUS",
    9: "SEPTEMBER", 10: "OKTOBER", 11: "NOVEMBER", 12: "DESEMBER"
}

DAY_NAMES_ID = {
    0: "Senin", 1: "Selasa", 2: "Rabu", 3: "Kamis",
    4: "Jumat", 5: "Sabtu", 6: "Minggu"
}


def _build_simple_dinasan_workbook(year: int, month: int, schedule_path: Path, output_path: Path, with_personnel: bool = False, config_path: Path = None):
    """Export compact maintenance list; optional PERSONIL column."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Dinasan {MONTH_NAMES_ID[month]} {year}"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.print_options.horizontalCentered = True
    ws.print_options.verticalCentered = False
    ws.page_margins.left = 0.25
    ws.page_margins.right = 0.25
    ws.page_margins.top = 0.35
    ws.page_margins.bottom = 0.35

    logo_path = Path("config/kai_logo.png")
    if logo_path.exists():
        img = OpenpyxlImage(str(logo_path))
        img.width, img.height = 110, 42
        ws.add_image(img, "A1")

    end_col = "E" if with_personnel else "D"
    ws.merge_cells(f"A1:{end_col}1")
    ws["A1"] = "DAFTAR JADWAL PERAWATAN"
    ws["A1"].font = Font(name="Arial", size=14, bold=True)
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.merge_cells(f"A2:{end_col}2")
    ws["A2"] = f"DINASAN {MONTH_NAMES_ID[month]} {year}"
    ws["A2"].font = Font(name="Arial", size=11, bold=True)
    ws["A2"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 32
    ws.row_dimensions[2].height = 22

    headers = ["NO", "PERAWATAN", "PROGRAM", "REALISASI"]
    if with_personnel:
        headers.append("PERSONIL")
    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    body_font = Font(name="Arial", size=10)
    border = Border(*(Side(style="thin", color="000000"),) * 4)
    for col, value in enumerate(headers, 1):
        cell = ws.cell(4, col, value)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border
    ws.row_dimensions[4].height = 22

    schedules = []
    if schedule_path.exists():
        with open(schedule_path, "r", encoding="utf-8") as f:
            schedules = json.load(f).get("schedules", [])
    by_date = {}
    personnel_by_date = {}
    cfg = load_pegawai_config(config_path)
    kaur_map, pnc_map, _ = get_roster_sets(cfg)
    roster_names = sorted(set(kaur_map) | set(pnc_map), key=len, reverse=True)
    if cfg.get("resor", {}).get("nama"):
        resor_name = cfg["resor"]["nama"].strip().upper()
        if resor_name and resor_name not in roster_names:
            roster_names.append(resor_name)

    def normalize_personnel(values):
        result = set()
        for value in values:
            text = re.sub(r'\s+', ' ', str(value).upper()).strip(' ,;')
            clean_text = re.sub(r'[^A-Z]', '', text)
            found = []
            for name in roster_names:
                clean_name = re.sub(r'[^A-Z]', '', name)
                if clean_name and (clean_name == clean_text or (len(clean_name) >= 6 and clean_name in clean_text) or (len(clean_text) >= 6 and clean_text in clean_name)):
                    found.append(name)
                else:
                    chars = [re.escape(c) for c in name if not c.isspace()]
                    if chars and re.search(r'\b' + r'\s*'.join(chars) + r'\b', text):
                        found.append(name)
            if found:
                result.update(found)
            elif text:
                result.add(text)
        return result

    pdf_by_date = {}
    for item in schedules:
        iso = item.get("iso_date", "")
        try:
            date_key = datetime.strptime(iso, "%Y-%m-%d").date()
        except ValueError:
            continue
        override = (item.get("personnel_override") or "").strip()
        if override:
            personnel_by_date.setdefault(date_key, set()).update(
                normalize_personnel(re.split(r"[,;\n]+", override))
            )
        elif item.get("personnel"):
            personnel_by_date.setdefault(date_key, set()).update(
                normalize_personnel(item["personnel"])
            )
        pdf_value = item.get("pdf_path") or item.get("file") or ""
        pdf_file = Path(str(pdf_value).replace('\\\\', '\\'))
        if not pdf_file.is_file() and item.get("file"):
            search_dirs = [pdf_file.parent] if pdf_file.parent.exists() else []
            search_dirs.extend([Path("02_pdf_target"), Path("01_pdf_source")])
            for root in search_dirs:
                matches = list(root.rglob(item["file"])) if root.exists() else []
                if matches:
                    pdf_file = matches[0]
                    break
        if pdf_file.is_file():
            pdf_by_date.setdefault(date_key, []).append(pdf_file)

    if with_personnel:
        for date_key, pdf_files in pdf_by_date.items():
            if not personnel_by_date.get(date_key):
                for pdf_file in pdf_files:
                    try:
                        with fitz.open(pdf_file) as doc:
                            _, _, raw_personnel = extract_personnel_from_pdf(doc, kaur_map, pnc_map)
                        personnel_by_date.setdefault(date_key, set()).update(
                            normalize_personnel(raw_personnel)
                        )
                    except Exception:
                        pass

    for item in schedules:
        try:
            dt = datetime.strptime(item.get("iso_date", ""), "%Y-%m-%d")
        except ValueError:
            continue
        if dt.year != year or dt.month != month:
            continue
        category = (item.get("category") or "").strip().upper()
        identifier = (item.get("identifier") or "").strip().upper()
        match = re.match(r"^(.*?)\s+((?:BOO|CLT|BOP|BTT|MSG|CGB|COS)(?:[- ].*)?)$", identifier)
        if match:
            asset_name, location = match.group(1).strip(), match.group(2).strip()
        else:
            asset_name, location = identifier, ""
        date_key = dt.date()
        group_key = (category, location)
        groups = by_date.setdefault(date_key, {})
        group = groups.setdefault(group_key, [])
        detail = asset_name
        if detail and detail not in group:
            group.append(detail)

    rows = []
    for date_key, groups in sorted(by_date.items()):
        details = []
        for (category, location), assets in groups.items():
            names = ", ".join(assets)
            suffix = f" {location}" if location else ""
            details.append(f"PERAWATAN {category} {names}{suffix}".strip())
        personnel = "\n".join(sorted(personnel_by_date.get(date_key, set()))) or "-"
        rows.append((datetime.combine(date_key, datetime.min.time()), "\n".join(details), personnel))

    for no, (dt, detail, personnel) in enumerate(rows, 1):
        date_text = dt.strftime("%d-%m-%Y")
        values = [no, detail, date_text, date_text]
        if with_personnel:
            values.append(personnel)
        row_number = 4 + no
        for col, value in enumerate(values, 1):
            cell = ws.cell(row_number, col, value)
            cell.font = body_font
            cell.border = border
            cell.alignment = Alignment(horizontal="center" if col not in (2, 5) else "left", vertical="center", wrap_text=True)
        col_b_wrap = 48 if with_personnel else 72
        wrapped_lines = sum(max(1, (len(line) + col_b_wrap - 1) // col_b_wrap) for line in detail.split("\n"))
        if with_personnel:
            wrapped_lines = max(wrapped_lines, len(personnel.split("\n")))
        ws.row_dimensions[row_number].height = max(24, min(140, 16 * wrapped_lines))

    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 48 if with_personnel else 72
    ws.column_dimensions["C"].width = 13
    ws.column_dimensions["D"].width = 13
    if with_personnel:
        ws.column_dimensions["E"].width = 26
    ws.print_title_rows = "1:4"
    ws.print_area = f"A1:{end_col}{max(4, 4 + len(rows))}"
    ws.freeze_panes = "A5"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    wb.close()
    print(f"[OK] Dinasan Excel exported successfully -> {output_path}")
    return output_path


def build_dinasan_workbook(year: int, month: int, schedule_path: Path, config_path: Path, output_path: Path, with_personnel: bool = False):
    return _build_simple_dinasan_workbook(year, month, schedule_path, output_path, with_personnel, config_path)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Dinasan {MONTH_NAMES_ID[month]} {year}"
    ws.views.sheetView[0].showGridLines = True
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.print_options.horizontalCentered = True
    ws.print_options.verticalCentered = True

    # ── 1. Load Configurations ──
    cfg = load_pegawai_config(config_path)
    resor = cfg.get("resor", {
        "nama": "S. SLAMET RIYADI",
        "nipp": "-",
        "jabatan": "KUPT RESOR STL 1.21 BOGOR"
    })
    kaur_list = cfg.get("kaur", [])
    pnc_list = cfg.get("pnc", [])

    # ── 2. Read Schedule & Determine Active Duties ──
    schedules = []
    if schedule_path.exists():
        try:
            with open(schedule_path, "r", encoding="utf-8") as f:
                s_data = json.load(f)
                schedules = s_data.get("schedules", [])
        except Exception as e:
            print(f"[WARN] Could not load schedule.json: {e}")

    # Map: day_number (1..num_days) -> {"tim1_files": [], "tim2_files": []}
    num_days = calendar.monthrange(year, month)[1]
    days_activity = {d: {"tim1": [], "tim2": []} for d in range(1, num_days + 1)}

    for item in schedules:
        iso = item.get("iso_date")
        if not iso:
            continue
        try:
            dt = datetime.strptime(iso, "%Y-%m-%d")
            if dt.year == year and dt.month == month:
                t = item.get("tim", 1)
                f_name = item.get("file")
                if t == 2:
                    days_activity[dt.day]["tim2"].append(f_name)
                else:
                    days_activity[dt.day]["tim1"].append(f_name)
        except Exception:
            continue

    # Pre-scan Tim 1 personnel from schedule PDF paths, fallback to 01_pdf_source
    pdf_by_date = {}
    try:
        with open(schedule_path, "r", encoding="utf-8") as f:
            for item in json.load(f).get("schedules", []):
                pdf_file = Path(item.get("pdf_path", ""))
                iso = item.get("iso_date", "")
                if not pdf_file.is_file() and item.get("file"):
                    search_dirs = [pdf_file.parent] if pdf_file.parent.exists() else []
                    search_dirs.extend([Path("02_pdf_target"), Path("01_pdf_source")])
                    for root in search_dirs:
                        matches = list(root.rglob(item["file"])) if root.exists() else []
                        if matches:
                            pdf_file = matches[0]
                            break
                if pdf_file.is_file() and iso:
                    d_key = datetime.strptime(iso, "%Y-%m-%d").strftime("%d-%m-%Y")
                    pdf_by_date.setdefault(d_key, []).append(pdf_file)
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    if not pdf_by_date:
        src_dir = Path("01_pdf_source")
        if src_dir.exists():
            for pdf_file in src_dir.rglob("*.pdf"):
                m = re.search(r'(\d{2})-(\d{2})-(\d{4})', pdf_file.name)
                if m:
                    pdf_by_date.setdefault(m.group(0), []).append(pdf_file)

    # Build duty roster per day: day -> set of UPPERCASE names on duty
    daily_duties = {}
    for day in range(1, num_days + 1):
        duty_set = set()
        # Resor is always on duty
        duty_set.add(resor.get("nama", "").strip().upper())

        act = days_activity[day]
        has_tim1 = len(act["tim1"]) > 0
        has_tim2 = len(act["tim2"]) > 0

        d_str = f"{day:02d}-{month:02d}-{year}"
        t1_tokens = set()

        if (has_tim1 or has_tim2) and d_str in pdf_by_date:
            for pdf_f in pdf_by_date[d_str]:
                try:
                    doc = fitz.open(pdf_f)
                    t1_tokens.update(extract_page1_tim1_personnel(doc))
                    doc.close()
                except Exception:
                    pass

        # Personil dari item jadwal dan koreksi Audit Jadwal Dinasan
        for item in schedules:
            if item.get("iso_date") == f"{year:04d}-{month:02d}-{day:02d}":
                if item.get("personnel"):
                    for p in item["personnel"]:
                        t1_tokens.add(str(p).strip().upper())

        override_names = set()
        for item in schedules:
            if item.get("iso_date") == f"{year:04d}-{month:02d}-{day:02d}" and item.get("personnel_override"):
                override_names.update(
                    name.strip().upper()
                    for name in re.split(r"[,;\\n]+", str(item["personnel_override"]))
                    if name.strip()
                )
        if override_names:
            t1_tokens.update(override_names)

        if has_tim1:
            for k in kaur_list:
                k_name = k.get("nama", "").strip().upper()
                if k_name in t1_tokens or any(part in t1_tokens for part in k_name.split() if len(part) > 3):
                    duty_set.add(k_name)
            for p in pnc_list:
                p_name = p.get("nama", "").strip().upper()
                if p_name in t1_tokens or any(part in t1_tokens for part in p_name.split() if len(part) > 3):
                    duty_set.add(p_name)

        if has_tim2:
            roster_tim2 = get_tim2_roster_for_date(d_str, t1_tokens, cfg)
            for r in roster_tim2:
                duty_set.add(r.get("nama", "").strip().upper())

        daily_duties[day] = duty_set

    # ── 3. Formatting & Styles ──
    font_family = "Arial"
    thin_border = Side(border_style="thin", color="000000")
    medium_border = Side(border_style="medium", color="000000")
    double_bottom = Side(border_style="double", color="000000")

    border_all_thin = Border(left=thin_border, right=thin_border, top=thin_border, bottom=thin_border)
    border_header_outer = Border(left=thin_border, right=thin_border, top=medium_border, bottom=thin_border)

    fill_header_gray = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    fill_sunday_red = PatternFill(start_color="FFE6E6", end_color="FFE6E6", fill_type="solid")
    fill_red_solid = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
    fill_blue_solid = PatternFill(start_color="00B0F0", end_color="00B0F0", fill_type="solid")

    font_title = Font(name=font_family, size=13, bold=True)
    font_subtitle = Font(name=font_family, size=11, bold=True)
    font_bold = Font(name=font_family, size=9, bold=True)
    font_bold_white = Font(name=font_family, size=9, bold=True, color="FFFFFF")
    font_regular = Font(name=font_family, size=9)
    font_small = Font(name=font_family, size=8)

    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_center_vert = Alignment(horizontal="center", vertical="center", text_rotation=90)
    align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)

    # ── 4. Insert Header & Titles ──
    # Logo KAI
    logo_path = Path("config/kai_logo.png")
    if logo_path.exists():
        try:
            img = OpenpyxlImage(str(logo_path))
            img.width = 110
            img.height = 42
            ws.add_image(img, "A1")
        except Exception as e:
            print(f"[WARN] Failed to add KAI logo image: {e}")

    # Title lines
    end_col_idx = 2 + num_days + 3  # NO, NAMA + num_days + L, P, CT
    end_col_letter = get_column_letter(end_col_idx)

    ws.merge_cells(f"A1:{end_col_letter}1")
    title_cell = ws["A1"]
    title_cell.value = "DAFTAR DINASAN PEGAWAI"
    title_cell.font = font_title
    title_cell.alignment = align_center

    ws.merge_cells(f"A2:{end_col_letter}2")
    sub_cell = ws["A2"]
    sub_cell.value = resor.get("jabatan", "RESOR SINTELIS 1.21 BOGOR")
    sub_cell.font = font_subtitle
    sub_cell.alignment = align_center

    ws.row_dimensions[1].height = 24
    ws.row_dimensions[2].height = 20

    # ── 5. Build Table Headers (Rows 3, 4, 5) ──
    # Row 3: Month spanning columns C..end of days
    first_day_col = "C"
    last_day_col = get_column_letter(2 + num_days)

    ws.merge_cells(f"A3:A5")
    ws["A3"].value = "NO"
    ws["A3"].font = font_bold
    ws["A3"].alignment = align_center

    ws.merge_cells(f"B3:B5")
    ws["B3"].value = "NAMA"
    ws["B3"].font = font_bold
    ws["B3"].alignment = align_center

    ws.merge_cells(f"{first_day_col}3:{last_day_col}3")
    month_cell = ws[f"{first_day_col}3"]
    month_cell.value = MONTH_NAMES_ID[month]
    month_cell.font = font_bold
    month_cell.alignment = align_center
    month_cell.fill = fill_header_gray

    # Total columns header
    tot_l_col = get_column_letter(2 + num_days + 1)
    tot_p_col = get_column_letter(2 + num_days + 2)
    tot_ct_col = get_column_letter(2 + num_days + 3)

    ws.merge_cells(f"{tot_l_col}3:{tot_ct_col}3")
    ws[f"{tot_l_col}3"].value = "TOTAL"
    ws[f"{tot_l_col}3"].font = font_bold
    ws[f"{tot_l_col}3"].alignment = align_center

    # Row 4: Day of Week Name
    ws.row_dimensions[4].height = 55
    ws.row_dimensions[5].height = 20

    for d in range(1, num_days + 1):
        col_let = get_column_letter(2 + d)
        dt = datetime(year, month, d)
        day_name = DAY_NAMES_ID[dt.weekday()]
        is_sunday = dt.weekday() == 6

        cell_day = ws[f"{col_let}4"]
        cell_day.value = day_name
        cell_day.font = font_small
        cell_day.alignment = align_center_vert
        if is_sunday:
            cell_day.fill = fill_sunday_red

        cell_num = ws[f"{col_let}5"]
        cell_num.value = d
        cell_num.font = font_bold
        cell_num.alignment = align_center
        if is_sunday:
            cell_num.fill = fill_sunday_red

    # Sub-headers for TOTAL
    ws.merge_cells(f"{tot_l_col}4:{tot_l_col}5")
    ws[f"{tot_l_col}4"].value = "L"
    ws[f"{tot_l_col}4"].font = font_bold_white
    ws[f"{tot_l_col}4"].alignment = align_center
    ws[f"{tot_l_col}4"].fill = fill_red_solid

    ws.merge_cells(f"{tot_p_col}4:{tot_p_col}5")
    ws[f"{tot_p_col}4"].value = "P"
    ws[f"{tot_p_col}4"].font = font_bold
    ws[f"{tot_p_col}4"].alignment = align_center

    ws.merge_cells(f"{tot_ct_col}4:{tot_ct_col}5")
    ws[f"{tot_ct_col}4"].value = "CT"
    ws[f"{tot_ct_col}4"].font = font_bold_white
    ws[f"{tot_ct_col}4"].alignment = align_center
    ws[f"{tot_ct_col}4"].fill = fill_blue_solid

    # Apply borders to header cells
    for r in range(3, 6):
        for c in range(1, end_col_idx + 1):
            ws.cell(row=r, column=c).border = border_all_thin

    # ── 6. Assemble Employee Rows ──
    # Row list: Resor first, then KAURs, then PNCs
    all_employees = []
    # Resor
    all_employees.append({
        "role": "RESOR",
        "nama": resor.get("nama", "FURQON SUSILO WARDOYO"),
        "nipp": resor.get("nipp", "64465")
    })
    for k in kaur_list:
        all_employees.append({
            "role": "KAUR",
            "nama": k.get("nama", ""),
            "nipp": k.get("nipp", "")
        })
    for p in pnc_list:
        all_employees.append({
            "role": "PNC",
            "nama": p.get("nama", ""),
            "nipp": p.get("nipp", "")
        })

    start_data_row = 6
    curr_row = start_data_row
    pnc_start_row = None
    pnc_end_row = None

    for idx, emp in enumerate(all_employees, start=1):
        ws.row_dimensions[curr_row].height = 28
        emp_role = emp["role"]
        emp_name = emp["nama"].strip().upper()
        emp_nipp = emp["nipp"].strip()

        if emp_role == "PNC" and pnc_start_row is None:
            pnc_start_row = curr_row
        if emp_role == "PNC":
            pnc_end_row = curr_row

        # Col A: NO
        c_no = ws.cell(row=curr_row, column=1, value=idx)
        c_no.font = font_bold
        c_no.alignment = align_center
        c_no.border = border_all_thin

        # Col B: NAMA \n NIPP : xxxxx
        disp_text = emp_name
        if emp_nipp:
            disp_text += f"\nNIPP : {emp_nipp}"
        c_nama = ws.cell(row=curr_row, column=2, value=disp_text)
        c_nama.font = font_bold
        c_nama.alignment = align_left
        c_nama.border = border_all_thin

        # Days 1..num_days
        for d in range(1, num_days + 1):
            c_day = ws.cell(row=curr_row, column=2 + d)
            c_day.alignment = align_center
            c_day.border = border_all_thin

            # Resor always gets P
            if emp_role == "RESOR":
                c_day.value = "P"
                c_day.font = font_bold
            else:
                if emp_name in daily_duties.get(d, set()):
                    c_day.value = "P"
                    c_day.font = font_bold
                else:
                    c_day.value = None

        # Formulas for TOTAL
        # L
        cL = ws.cell(row=curr_row, column=2 + num_days + 1)
        cL.value = f'=COUNTIF({first_day_col}{curr_row}:{last_day_col}{curr_row}, "L")'
        cL.font = font_bold
        cL.alignment = align_center
        cL.border = border_all_thin

        # P
        cP = ws.cell(row=curr_row, column=2 + num_days + 2)
        cP.value = f'=COUNTIF({first_day_col}{curr_row}:{last_day_col}{curr_row}, "P")'
        cP.font = font_bold
        cP.alignment = align_center
        cP.border = border_all_thin

        # CT
        cCT = ws.cell(row=curr_row, column=2 + num_days + 3)
        cCT.value = f'=COUNTIF({first_day_col}{curr_row}:{last_day_col}{curr_row}, "CT")'
        cCT.font = font_bold
        cCT.alignment = align_center
        cCT.border = border_all_thin

        curr_row += 1

    end_data_row = curr_row - 1

    # ── 7. Summary Rows below Data ──
    # S, M, L, P(PNC), P(ALL)
    summary_rows = [
        ("S", "S"),
        ("M", "M"),
        ("L", "L"),
        ("P(PNC)", "P_PNC"),
        ("P(ALL)", "P_ALL"),
    ]

    ws.row_dimensions[curr_row].height = 10  # blank spacer row
    curr_row += 1

    sum_start_row = curr_row
    for label, code in summary_rows:
        ws.row_dimensions[curr_row].height = 18
        lbl_cell = ws.cell(row=curr_row, column=2, value=label)
        lbl_cell.font = font_bold
        lbl_cell.alignment = Alignment(horizontal="center", vertical="center")
        lbl_cell.border = border_all_thin

        for d in range(1, num_days + 1):
            col_let = get_column_letter(2 + d)
            s_cell = ws.cell(row=curr_row, column=2 + d)
            s_cell.font = font_regular
            s_cell.alignment = align_center
            s_cell.border = border_all_thin

            if code == "P_PNC":
                if pnc_start_row and pnc_end_row:
                    s_cell.value = f'=COUNTIF({col_let}{pnc_start_row}:{col_let}{pnc_end_row}, "P")'
                else:
                    s_cell.value = 0
            elif code == "P_ALL":
                s_cell.value = f'=COUNTIF({col_let}{start_data_row}:{col_let}{end_data_row}, "P")'
            else:
                s_cell.value = f'=COUNTIF({col_let}{start_data_row}:{col_let}{end_data_row}, "{code}")'

        # Total on the right
        if code in ["S", "M", "L"]:
            tot_cell = ws.cell(row=curr_row, column=2 + num_days + 1)
            tot_cell.value = f'=SUM({first_day_col}{curr_row}:{last_day_col}{curr_row})'
            tot_cell.font = font_bold
            tot_cell.alignment = align_center
            tot_cell.border = border_all_thin
            if code == "L":
                tot_cell.fill = fill_red_solid
                tot_cell.font = font_bold_white

        curr_row += 1

    # ── 8. Conditional Formatting for Shift Cells ──
    # Data range: C6..[last_day_col][end_data_row]
    data_range = f"{first_day_col}{start_data_row}:{last_day_col}{end_data_row}"

    # L = Red
    ws.conditional_formatting.add(data_range, CellIsRule(
        operator='equal', formula=['"L"'], stopIfTrue=True,
        fill=fill_red_solid, font=font_bold_white
    ))
    # S = Green
    ws.conditional_formatting.add(data_range, CellIsRule(
        operator='equal', formula=['"S"'], stopIfTrue=True,
        fill=PatternFill(start_color="00B050", end_color="00B050", fill_type="solid"),
        font=font_bold_white
    ))
    # M = Yellow
    ws.conditional_formatting.add(data_range, CellIsRule(
        operator='equal', formula=['"M"'], stopIfTrue=True,
        fill=PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid"),
        font=font_bold
    ))
    # CT = Blue
    ws.conditional_formatting.add(data_range, CellIsRule(
        operator='equal', formula=['"CT"'], stopIfTrue=True,
        fill=fill_blue_solid, font=font_bold_white
    ))
    # P = Bold
    ws.conditional_formatting.add(data_range, CellIsRule(
        operator='equal', formula=['"P"'], stopIfTrue=True,
        font=font_bold
    ))

    # ── 9. Legend & Signature Block ──
    curr_row += 2
    legend_start = curr_row

    ws.cell(row=curr_row, column=2, value="KETERANGAN :").font = font_bold
    curr_row += 1
    ws.cell(row=curr_row, column=2, value="P :  Dinas Pagi mulai jam 08:00 s.d jam 16:00 (Pemeliharaan dan Perbaikan gangguan)").font = font_small
    curr_row += 1
    ws.cell(row=curr_row, column=2, value="S :  Dinas Siang mulai jam 16:00 s.d jam 24:00 (Piket dan Perbaikan gangguan)").font = font_small
    curr_row += 1
    ws.cell(row=curr_row, column=2, value="M :  Dinas Malam mulai jam 24:00 s.d jam 08:00 (Piket dan Perbaikan gangguan)").font = font_small
    curr_row += 1
    ws.cell(row=curr_row, column=2, value="L :  Libur dinas").font = font_small
    curr_row += 1
    ws.cell(row=curr_row, column=2, value="CT : Cuti Tahunan").font = font_small

    # Signature on the right side
    sig_col = 2 + num_days - 6
    sig_col_let = get_column_letter(sig_col)

    ws.cell(row=legend_start, column=sig_col, value=resor.get("jabatan", "KUPT RESOR STL 1.21 BOGOR")).font = font_bold
    ws.cell(row=legend_start + 4, column=sig_col, value=resor.get("nama", "S. SLAMET RIYADI")).font = font_bold
    ws.cell(row=legend_start + 5, column=sig_col, value=f"NIPP : {resor.get('nipp', '-')}").font = font_bold

    # ── 10. Column Widths ──
    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 24
    for d in range(1, num_days + 1):
        ws.column_dimensions[get_column_letter(2 + d)].width = 3.6
    ws.column_dimensions[tot_l_col].width = 4.2
    ws.column_dimensions[tot_p_col].width = 4.2
    ws.column_dimensions[tot_ct_col].width = 4.2

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    wb.close()
    print(f"[OK] Dinasan Excel exported successfully -> {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Export KAI Daftar Dinasan Pegawai to Excel")
    parser.add_argument("--month", type=str, default=None, help="Month in YYYY-MM format, e.g. 2026-08")
    parser.add_argument("--folder", type=str, default=None, help="Folder PDF kustom untuk diekstrak jadwalnya")
    parser.add_argument("--schedule", type=str, default="schedule.json", help="Path to schedule.json")
    parser.add_argument("--config", type=str, default="config/daftar_pegawai.json", help="Path to daftar_pegawai.json")
    parser.add_argument("--output", type=str, default=None, help="Output path for .xlsx")
    parser.add_argument("--with-personnel", action="store_true", help="Tambahkan kolom PERSONIL")
    args = parser.parse_args()

    sch_path = Path(args.schedule)
    cfg_path = Path(args.config)
    if not cfg_path.exists():
        cand_cfg = Path(__file__).resolve().parent / "daftar_pegawai.json"
        if cand_cfg.exists():
            cfg_path = cand_cfg

    if args.folder and Path(args.folder).exists():
        custom_pdf_dir = Path(args.folder).resolve()
        temp_sch = Path(args.output).parent / "temp_dinasan_schedule.json" if args.output else Path("logs/temp_dinasan_schedule.json")
        temp_sch.parent.mkdir(parents=True, exist_ok=True)
        try:
            from scheduler import build_schedule, load_mapping, load_data_acuan
        except ImportError:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from scheduler import build_schedule, load_mapping, load_data_acuan

        engine_dir = Path(__file__).resolve().parent
        m_path = engine_dir / "asset_waktu_mapping.json"
        if not m_path.exists() and (Path("config") / "asset_waktu_mapping.json").exists():
            m_path = Path("config") / "asset_waktu_mapping.json"
        mapping = load_mapping(m_path) if m_path.exists() else {}

        a_path = engine_dir / "data_acuan_tenaga_gabungan.json"
        if not a_path.exists() and (Path("config") / "data_acuan_tenaga_gabungan.json").exists():
            a_path = Path("config") / "data_acuan_tenaga_gabungan.json"
        acuan = load_data_acuan(a_path) if a_path.exists() else {}

        sched_data = build_schedule(
            pdf_dir=custom_pdf_dir,
            photos_dir=Path("./03_photos_export").resolve(),
            mapping=mapping,
            acuan=acuan,
            jam_mulai=7 * 60,
            jam_selesai=18 * 60,
            tim_max=2
        )
        try:
            with open(temp_sch, "w", encoding="utf-8") as f:
                json.dump(sched_data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        sch_path = temp_sch

    # Determine year & month
    year = None
    month = None

    if args.month:
        parts = args.month.split("-")
        year = int(parts[0])
        month = int(parts[1])
    else:
        # Detect from schedule.json
        if sch_path.exists():
            try:
                with open(sch_path, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                    for item in s_data.get("schedules", []):
                        iso = item.get("iso_date")
                        if iso:
                            dt = datetime.strptime(iso, "%Y-%m-%d")
                            year = dt.year
                            month = dt.month
                            break
            except Exception:
                pass

    if not year or not month:
        now = datetime.now()
        year = now.year
        month = now.month

    m_name = MONTH_NAMES_ID[month]
    if args.output:
        out_path = Path(args.output)
    else:
        out_path = Path(f"logs/DAFTAR_DINASAN_PEGAWAI_{m_name}_{year}.xlsx")

    build_dinasan_workbook(year, month, sch_path, cfg_path, out_path, args.with_personnel)


if __name__ == "__main__":
    main()
