\
from __future__ import annotations
import hashlib, json, re
from pathlib import Path


def _clean(value: str) -> str:
    value = str(value or '').replace('‘','').replace('’','').replace('“','').replace('”','')
    return re.sub(r'\s+', ' ', value).strip(' ,._-|;:')


def load_aliases(path: str | Path | None):
    if not path or not Path(path).exists():
        return []
    return json.loads(Path(path).read_text(encoding='utf-8')).get('aliases', [])


def normalize_location(value: str, aliases=None) -> str:
    value = _clean(value)
    upper = value.upper()
    for rule in aliases or []:
        if any(str(fragment).upper() in upper for fragment in rule.get('contains', [])):
            return rule['alias']

    # Common public places can remain readable.
    public_rules = {
        'WEST COAST PLAZA':'WEST COAST PLAZA', 'VIVOCITY':'VIVOCITY',
        'CAUSEWAY POINT':'CAUSEWAY POINT', 'JEM':'JEM', 'ION ORCHARD':'ION ORCHARD',
        'MUSTAFA CENTRE':'MUSTAFA CENTRE', 'PAN PACIFIC ORCHARD':'PAN PACIFIC ORCHARD',
        'CHANGI AIRPORT':'CHANGI AIRPORT', 'MARINA BAY SANDS':'MARINA BAY SANDS'
    }
    for needle, label in public_rules.items():
        if needle in upper:
            return label

    # Mask address-like labels unless explicitly aliased locally.
    if re.match(r'^(BLK\s*)?\d+\s+', upper):
        digest = hashlib.sha1(upper.encode()).hexdigest()[:6].upper()
        return f'PRIVATE_{digest}'
    return upper[:80] if upper else 'UNKNOWN'
