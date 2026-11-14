from __future__ import annotations
import re
from datetime import datetime
import pdfplumber
from normalization import normalize_location
from journey import possible_multistop


def _first_line(cell):
    parts = [p.strip() for p in str(cell or '').splitlines() if p.strip()]
    return parts[0] if parts else ''


def parse_row(row, aliases=None):
    if len(row) < 7:
        raise ValueError('Incomplete Gojek table row')
    dt = datetime.strptime((row[0] or '').replace('\n', ' ').strip(), '%d/%m/%Y %I:%M:%S %p')
    text = str(row[6] or '').strip()
    match = re.fullmatch(r'(?:(SGD|S\$|MYR)\s*)?([+-]?\d+(?:,\d{3})*(?:\.\d{1,2})?)', text)
    if not match:
        raise ValueError('Unrecognised Gojek amount')
    amount = float(match[2].replace(',', ''))
    if amount < 0:
        raise ValueError('Refund requires separate reconciliation')
    currency = {'SGD':'SGD', 'S$':'SGD', 'MYR':'MYR'}.get(match[1], 'UNKNOWN')
    return {
        'datetime': dt.isoformat(timespec='minutes'), 'date': dt.date().isoformat(),
        'time': dt.strftime('%H:%M'), 'hour': dt.hour, 'weekday': dt.strftime('%A'),
        'provider': 'Gojek', 'category': 'ride', 'service': 'Gojek',
        'origin': normalize_location(_first_line(row[3]), aliases),
        'destination': normalize_location(_first_line(row[4]), aliases),
        'amount': round(amount, 2), 'currency': currency,
        'route_status': 'needs_review' if possible_multistop(row[3], row[4]) else 'stop_coverage_unknown',
        'fare_basis': 'statement_total', 'fare_components': None,
    }


def import_gojek_pdf(pdf_path, aliases=None):
    records = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_no, page in enumerate(pdf.pages, 1):
            table = page.extract_table() or []
            if not table:
                raise ValueError(f'No Gojek table on page {page_no}; review locally')
            for row_no, row in enumerate(table, 1):
                if not row or not any(row) or _first_line(row[0]).lower() == 'date':
                    continue
                try:
                    records.append(parse_row(row, aliases))
                except (ValueError, TypeError):
                    raise ValueError(f'Gojek page {page_no}, row {row_no} needs review; no output written') from None
    return records
