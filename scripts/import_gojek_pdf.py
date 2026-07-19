\
from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path
import pdfplumber
from normalization import normalize_location


def _first_line(cell):
    parts=[p.strip() for p in str(cell or '').splitlines() if p.strip()]
    return parts[0] if parts else ''


def import_gojek_pdf(pdf_path, aliases=None):
    records=[]
    with pdfplumber.open(pdf_path) as pdf:
        for page_no, page in enumerate(pdf.pages, 1):
            table=page.extract_table() or []
            if page_no == 1 and table and (table[0][0] or '').strip() == 'Date':
                table=table[1:]
            for row in table:
                if not row or len(row) < 7:
                    continue
                try:
                    dt=datetime.strptime((row[0] or '').replace('\n',' ').strip(), '%d/%m/%Y %I:%M:%S %p')
                    amount=float(re.search(r'[\d.]+', row[6] or '').group())
                except Exception:
                    continue
                records.append({
                    'datetime':dt.isoformat(timespec='minutes'), 'date':dt.date().isoformat(),
                    'time':dt.strftime('%H:%M'), 'hour':dt.hour, 'weekday':dt.strftime('%A'),
                    'provider':'Gojek','category':'ride','service':'Gojek',
                    'origin':normalize_location(_first_line(row[3]), aliases),
                    'destination':normalize_location(_first_line(row[4]), aliases),
                    'amount':round(amount,2),'currency':'SGD'
                })
    return records
