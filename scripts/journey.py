"""Conservative journey identity. No inference of stops from location aliases."""
import math
import re

def pricing_type(service):
    text = re.sub(r"\s+", " ", str(service or "")).strip().upper()
    if "METERED" in text:
        return "Metered"
    if "PREMIUM" in text or "PLUS" in text:
        return "Premium"
    if text in {"STANDARD", "STANDARD 4-SEATER", "STANDARD 4 SEATER", "JUSTGRAB",
                "STANDARD CAR OR TAXI", "CAR OR TAXI"}:
        return "Fixed"
    return "Unknown"

def possible_multistop(*values):
    return any(re.search(r"\b(?:via|stop\s*\d+|multi[ -]?stop|additional stop)\b|→|\s->\s",
                         str(v or ""), re.I) for v in values)

def journey(row):
    """Reviewed full ordered stops win. Ambiguous imports stay out of route benchmarks."""
    if row.get("route_status") == "needs_review":
        return None
    stops = row.get("stops")
    if stops is not None:
        if not isinstance(stops, list) or len(stops) < 2 or any(not isinstance(s, str) or not s for s in stops):
            return None
        if stops[0] != row.get("origin") or stops[-1] != row.get("destination"):
            return None
        return tuple(stops), "multi_stop" if len(stops) > 2 else "direct"
    origin, destination = row.get("origin"), row.get("destination")
    if not origin or not destination or possible_multistop(origin, destination):
        return None
    return (origin, destination), "stop_coverage_unknown"

def valid_amount(value):
    if value is None or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value)) and float(value) >= 0
    except (TypeError, ValueError):
        return False
