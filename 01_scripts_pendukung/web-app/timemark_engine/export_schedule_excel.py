#!/usr/bin/env python3
"""export_schedule_excel.py — Ekspor jadwal perawatan dari schedule.json ke format Excel (.xlsx) rapi."""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

DEFAULT_SCHEDULE_PATH = Path("schedule.json")
DEFAULT_OUTPUT_PATH = Path("logs/jadwal_perawatan_gabungan.xlsx")


def parse_schedule_time(iso_ts: str) -> tuple[str, str]:
    """Parse '2025-08-23T07:00:00' -> ('2025-08-23', '07:00')."""
    try:
        dt = datetime.fromisoformat(iso_ts)
        return dt.strftime("%Y-%m-%d"), f"{dt.hour:02d}:{dt.minute:02d}"
    except Exception:
        return "", "07:00"


def generate_excel_from_schedule(schedule_file: Path, output_file: Path):
    if not schedule_file.exists():
        raise FileNotFoundError(f"Berkas jadwal {schedule_file} tidak ditemukan.")

    with open(schedule_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    schedules = data.get("schedules", [])
    output_file.parent.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Jadwal Perawatan"
    ws.views.sheetView[0].showGridLines = True

    # 1. Header Title
    ws.merge_cells("A1:L1")
    title_cell = ws["A1"]
    title_cell.value = "JADWAL PERAWATAN FASILITAS OPERASI KERETA API (TIM GABUNGAN)"
    title_cell.font = Font(name="Segoe UI", size=14, bold=True, color="1F2937")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 32

    ws.merge_cells("A2:L2")
    sub_cell = ws["A2"]
    sub_cell.value = f"Total Rekord: {len(schedules)} Aset | Diekspor pada: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}"
    sub_cell.font = Font(name="Segoe UI", size=10, italic=True, color="6B7280")
    sub_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 20

    # 2. Table Column Headers
    headers = [
        "No", "Tanggal Perawatan", "Jam Mulai (0%)", "Jam Tengah (50%)",
        "Jam Selesai (100%)", "Rentang Waktu", "Tim", "BTP / Wilayah",
        "Kategori", "Detail Aset / Identifier", "Durasi (Menit)", "File PDF Target"
    ]

    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")  # Navy
    header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")

    thin_border = Border(
        left=Side(style="thin", color="D1D5DB"),
        right=Side(style="thin", color="D1D5DB"),
        top=Side(style="thin", color="D1D5DB"),
        bottom=Side(style="thin", color="D1D5DB")
    )

    ws.row_dimensions[4].height = 28
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        cell.border = thin_border

    # 3. Data Rows
    tim1_fill = PatternFill(start_color="F0FDF4", end_color="F0FDF4", fill_type="solid")  # light green/white
    tim2_fill = PatternFill(start_color="FFFBEB", end_color="FFFBEB", fill_type="solid")  # light amber/orange
    zebra_alt = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")

    for row_idx, item in enumerate(schedules, 5):
        tim_n = item.get("tim", 1)
        tim_label = f"Tim {tim_n}"
        date_text = item.get("date", "")
        duration = item.get("waktu_menit", 45)
        btp = item.get("btp", "BTP JAK")
        category = item.get("category", "")
        identifier = item.get("identifier") or item.get("pdf_stem", "")
        pdf_file = item.get("file", "")

        photos = item.get("photos", {})
        _, t0 = parse_schedule_time(photos.get("0.jpg", ""))
        _, t50 = parse_schedule_time(photos.get("50.jpg", ""))
        _, t100 = parse_schedule_time(photos.get("100.jpg", ""))
        time_range = f"{t0} - {t100}"

        row_values = [
            row_idx - 4,
            date_text,
            t0,
            t50,
            t100,
            time_range,
            tim_label,
            btp,
            category,
            identifier,
            duration,
            pdf_file
        ]

        ws.row_dimensions[row_idx].height = 20
        row_bg = tim2_fill if tim_n == 2 else (zebra_alt if row_idx % 2 == 0 else tim1_fill)

        for col_idx, val in enumerate(row_values, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = Font(name="Segoe UI", size=9, color="111827")
            cell.fill = row_bg
            cell.border = thin_border

            # Alignment: No (1), Jam (3,4,5,6), Tim (7), Durasi (11) -> Center
            if col_idx in [1, 3, 4, 5, 6, 7, 11]:
                cell.alignment = center_align
            else:
                cell.alignment = left_align

    # 4. Auto Column Widths
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.row < 4:
                continue
            val_str = str(cell.value or "")
            max_len = max(max_len, len(val_str))
    try:
        wb.save(output_file)
        print(f"[OK] Schedule excel exported to: {output_file} ({len(schedules)} rows)")
        return str(output_file)
    except PermissionError:
        fallback_file = output_file.parent / f"{output_file.stem}_updated.xlsx"
        wb.save(fallback_file)
        print(f"[WARNING] Berkas {output_file.name} sedang dibuka di Excel. Berkas baru disimpan ke: {fallback_file} ({len(schedules)} rows)")
        return str(fallback_file)


def main():
    parser = argparse.ArgumentParser(description="Export schedule.json to formatted Excel.")
    parser.add_argument("--schedule", default=str(DEFAULT_SCHEDULE_PATH), help="Path to schedule.json")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Path to output .xlsx")
    args = parser.parse_args()

    schedule_path = Path(args.schedule).resolve()
    output_path = Path(args.output).resolve()

    generate_excel_from_schedule(schedule_path, output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
