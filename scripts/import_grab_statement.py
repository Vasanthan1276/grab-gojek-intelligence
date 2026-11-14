"""Strict text-table import for Grab exports; original PDFs remain private."""
import hashlib
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import fitz

from journey import possible_multistop
from normalization import normalize_location

HEADER = ['Date/Time', 'Booking Code', 'Pick-up Address', 'Drop-off Address',
          'Service Type', 'Currency', 'Amount']


def clean(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def parse_statement(pages, aliases=None, source_sha256=None):
    """Parse extracted tables only after header, period, count and total checks."""
    # Imported here to avoid the native/OCR dispatch import cycle.
    from import_grab_pdf import _service
    first = clean(pages[0]['text'])
    count_match = re.search(r'Total Transactions:\s*(\d+)\b', first)
    total_match = re.search(r'Amount:\s*(SGD|MYR)\s+([\d,]+\.\d{2})\b', first)
    period_match = re.search(r'(\d{4}-\d{2}-\d{2})\s*-\s*(\d{4}-\d{2}-\d{2})', first)
    if not count_match or not total_match or not period_match:
        raise ValueError('Grab statement count, total or date period is missing; review privately')
    start, end = [datetime.strptime(x, '%Y-%m-%d').date() for x in period_match.groups()]
    if start > end:
        raise ValueError('Grab statement period is reversed')
    records, booking_codes = [], set()
    for page_no, page in enumerate(pages, 1):
        tables = page['tables']
        matching = [table for table in tables if table and [clean(x) for x in table[0]] == HEADER]
        if len(matching) != 1:
            raise ValueError(f'Grab page {page_no} has no unique expected transaction table')
        for row_no, cells in enumerate(matching[0][1:], 2):
            if not any(clean(c) for c in cells):
                continue
            try:
                if len(cells) != 7:
                    raise ValueError()
                date_text, code, pickup, dropoff, raw_service, currency, amount_text = map(clean, cells)
                code = re.sub(r'\s+', '', code)  # long booking references wrap across lines
                dt = datetime.strptime(date_text, '%d %b %Y, %I:%M%p')
                if not start <= dt.date() <= end:
                    raise ValueError()
                if not re.fullmatch(r'[A-Za-z0-9-]+', code) or code in booking_codes:
                    raise ValueError()
                if currency not in {'SGD', 'MYR'} or not re.fullmatch(r'\d+(?:,\d{3})*\.\d{2}', amount_text):
                    raise ValueError()
                if not pickup or not dropoff or not raw_service:
                    raise ValueError()
                amount = Decimal(amount_text.replace(',', ''))
                service, category, pricing = _service(raw_service)
                records.append({
                    'datetime': dt.isoformat(timespec='minutes'), 'date': dt.date().isoformat(),
                    'time': dt.strftime('%H:%M'), 'hour': dt.hour, 'weekday': dt.strftime('%A'),
                    'provider': 'Grab', 'category': category, 'service': service,
                    'raw_service': raw_service, 'pricing_type': pricing,
                    'origin': normalize_location(pickup, aliases),
                    'destination': normalize_location(dropoff, aliases),
                    'amount': float(amount), 'currency': currency, 'booking_code': code,
                    'route_status': 'needs_review' if possible_multistop(pickup, dropoff) else 'stop_coverage_unknown',
                    'fare_basis': 'statement_total', 'fare_components': None,
                    'source_references': [{'sha256': source_sha256, 'page': page_no, 'table_row': row_no}],
                })
                booking_codes.add(code)
            except (ValueError, TypeError, ArithmeticError):
                raise ValueError(f'Grab page {page_no}, row {row_no} needs private review') from None
    if len(records) != int(count_match[1]):
        raise ValueError('Grab statement transaction count does not reconcile')
    if {r['currency'] for r in records} != {total_match[1]}:
        raise ValueError('Mixed-currency Grab statement requires separate reconciliation')
    total = sum((Decimal(str(r['amount'])) for r in records), Decimal(0))
    if total != Decimal(total_match[2].replace(',', '')):
        raise ValueError('Grab statement amount does not reconcile')
    return records


def import_grab_statement(pdf_path, aliases=None):
    """Return None only for image-based exports, so OCR remains available."""
    with fitz.open(pdf_path) as document:
        if not len(document):
            raise ValueError('Empty Grab PDF')
        first_text = document[0].get_text()
        if not first_text.strip():
            return None
        if not all(label in clean(first_text) for label in HEADER):
            raise ValueError('Unrecognised text-based Grab statement layout')
        pages = [{'text': page.get_text(), 'tables': [t.extract() for t in page.find_tables().tables]}
                 for page in document]
    digest = hashlib.sha256(Path(pdf_path).read_bytes()).hexdigest()
    return parse_statement(pages, aliases, digest)
