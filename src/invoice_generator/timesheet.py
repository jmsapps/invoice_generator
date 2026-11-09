from __future__ import annotations

import calendar
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HEADERS = ("Day", "Date", "Hours", "Notes")
DATE_COLUMN = 2
HOURS_COLUMN = 3
WEEKEND_FILL = PatternFill("solid", fgColor="F2F5F8")
MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")


class TimesheetError(Exception):
    pass


def parse_month(value: str) -> date:
    if not MONTH_PATTERN.match(value):
        raise ValueError(f"expected YYYY-MM, got '{value}'")
    year, month = value.split("-")
    return date(int(year), int(month), 1)


def month_period(month: date) -> tuple[date, date]:
    last_day = calendar.monthrange(month.year, month.month)[1]
    return month.replace(day=1), month.replace(day=last_day)


def invoices_dir(clients_root: Path, client: str) -> Path:
    return clients_root / client / "invoices"


def bundle_dir(clients_root: Path, client: str, month: date) -> Path:
    return invoices_dir(clients_root, client) / f"{month:%Y-%m}"


def timesheet_path(clients_root: Path, client: str, month: date, number: str) -> Path:
    return bundle_dir(clients_root, client, month) / f"invoice-{number}.timesheet.xlsx"


def latest_month(clients_root: Path, client: str) -> date | None:
    directory = invoices_dir(clients_root, client)
    if not directory.is_dir():
        return None
    months = [
        parse_month(path.name)
        for path in directory.iterdir()
        if path.is_dir() and MONTH_PATTERN.match(path.name)
    ]
    return max(months, default=None)


def _coerce_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def _coerce_hours(value: object, row: int) -> Decimal:
    if value is None or (isinstance(value, str) and not value.strip()):
        return Decimal(0)
    try:
        hours = Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise TimesheetError(f"row {row}: hours '{value}' is not a number") from exc
    if hours < 0:
        raise TimesheetError(f"row {row}: hours must not be negative")
    return hours


def read_hours(path: Path, month: date) -> Decimal:
    if not path.is_file():
        raise TimesheetError(f"no timesheet at {path}")
    workbook = load_workbook(path, data_only=True)
    sheet = workbook.active
    start, end = month_period(month)

    total = Decimal(0)
    seen: dict[date, int] = {}
    for row in range(2, sheet.max_row + 1):
        worked = _coerce_date(sheet.cell(row=row, column=DATE_COLUMN).value)
        if worked is None:
            continue
        if not start <= worked <= end:
            raise TimesheetError(f"row {row}: {worked} is outside {month:%B %Y}")
        if worked in seen:
            raise TimesheetError(f"row {row}: {worked} already logged on row {seen[worked]}")
        seen[worked] = row
        total += _coerce_hours(sheet.cell(row=row, column=HOURS_COLUMN).value, row)

    if total <= 0:
        raise TimesheetError(f"{path} has no hours logged")
    return total


def write_blank(path: Path, month: date, client_name: str) -> Path:
    if path.exists():
        raise TimesheetError(f"{path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = f"{month:%Y-%m}"

    for column, header in enumerate(HEADERS, start=1):
        cell = sheet.cell(row=1, column=column, value=header)
        cell.font = Font(bold=True)

    start, end = month_period(month)
    row = 2
    for day in range(start.day, end.day + 1):
        worked = month.replace(day=day)
        day_cell = sheet.cell(row=row, column=1, value=f'=IF($B{row}="","",TEXT($B{row},"ddd"))')
        day_cell.alignment = Alignment(horizontal="left")
        date_cell = sheet.cell(row=row, column=DATE_COLUMN, value=worked)
        date_cell.number_format = "yyyy-mm-dd"
        sheet.cell(row=row, column=HOURS_COLUMN).number_format = "0.00"
        if worked.weekday() >= 5:
            for column in range(1, len(HEADERS) + 1):
                sheet.cell(row=row, column=column).fill = WEEKEND_FILL
        row += 1

    total_row = row + 1
    label = sheet.cell(row=total_row, column=DATE_COLUMN, value="TOTAL")
    label.font = Font(bold=True)
    label.alignment = Alignment(horizontal="right")
    total = sheet.cell(row=total_row, column=HOURS_COLUMN, value=f"=SUM(C2:C{row - 1})")
    total.font = Font(bold=True)
    total.number_format = "0.00"

    sheet.column_dimensions[get_column_letter(1)].width = 8
    sheet.column_dimensions[get_column_letter(2)].width = 14
    sheet.column_dimensions[get_column_letter(3)].width = 10
    sheet.column_dimensions[get_column_letter(4)].width = 52
    sheet.freeze_panes = "A2"
    workbook.properties.title = f"{client_name} timesheet {month:%Y-%m}"
    workbook.save(path)
    return path
