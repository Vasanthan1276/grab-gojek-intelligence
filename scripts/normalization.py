from __future__ import annotations

import hashlib
import json
import re

from pathlib import Path

# Explicit public place allowlist. Private matching fragments remain local-only.
SAFE_LOCATIONS = {
    "HOME", "OFFICE", "V_PLACE", "COMPASSVALE", "WEST COAST PLAZA", "VIVOCITY",
    "CAUSEWAY POINT", "JEM", "ION ORCHARD", "MUSTAFA CENTRE", "PAN PACIFIC ORCHARD",
    "CHANGI AIRPORT", "MARINA BAY SANDS", "THE STAR VISTA", "CLEMENTI MALL",
    "MADRAS NEW WOODLANDS", "RENDEZVOUS RESTAURANT", "GAYATHRI LITTLE INDIA",
    "SAMY'S CURRY", "YEW TEE POINT", "CLARKE QUAY CENTRAL", "DECATHLON - JOO KOON",
    "ANNALAKSHMI RESTAURANT", "CRAFTSMEN COFFEE (THOMSON)", "GEORGES MADBAR & GRILL",
    "KUMAR MESS - CLEMENTI", "NALAN RESTAURANT CITY HALL",
    "SUPER THAI BY SOI AROY @ PASIR PANJANG",
}


def _clean(value: str) -> str:
    """Clean location text before matching."""
    value = (
        str(value or "")
        .replace("‘", "")
        .replace("’", "")
        .replace("“", "")
        .replace("”", "")
    )

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip(" ,._-|;:")


def load_aliases(path: str | Path | None):
    """
    Load optional private aliases.

    The file is local-only and is ignored by Git.
    """
    if not path or not Path(path).exists():
        return []

    data = json.loads(
        Path(path).read_text(
            encoding="utf-8"
        )
    )

    return data.get(
        "aliases",
        []
    )


def _matches_private_alias(
    upper: str,
    aliases,
) -> str | None:
    for rule in aliases or []:
        alias = str(
            rule.get(
                "alias",
                ""
            )
        ).strip()

        fragments = (
            rule.get(
                "contains",
                []
            )
            or []
        )

        exact_values = rule.get("equals", []) or []
        if alias.upper() in {"HOME", "OFFICE", "V_PLACE", "COMPASSVALE"} and any(
            _clean(value).upper() == upper for value in exact_values if _clean(value)
        ):
            return alias.upper()

        if (
            alias.upper() in {"HOME", "OFFICE", "V_PLACE", "COMPASSVALE"}
            and
            any(
                str(fragment).strip().upper() in upper
                for fragment in fragments
                if str(fragment).strip()
            )
        ):
            return alias.upper()

    return None


def normalize_location(
    value: str,
    aliases=None,
) -> str:
    """
    Convert raw Grab/Gojek location names into consistent public-safe labels.

    Private aliases are checked first. Legacy readable workplace labels are
    consolidated into OFFICE. Existing PRIVATE_xxxxxx hashes remain private
    because their original addresses cannot be reconstructed from the hash.
    """
    value = _clean(
        value
    )

    upper = value.upper()

    if not upper:
        return "UNKNOWN"

    matched_alias = _matches_private_alias(
        upper,
        aliases,
    )

    if matched_alias:
        return matched_alias

    if upper in SAFE_LOCATIONS:
        return upper

    if upper == "PRIVATE_PLACE_1":
        return "COMPASSVALE"

    if upper in {
        "HOME",
        "OFFICE",
        "V_PLACE",
        "COMPASSVALE",
    }:
        return upper

    # Generic legacy work cleanup without publishing a private workplace address.
    # Workplace text must match an explicit private rule; substring matching can
    # otherwise turn unrelated offices into the user's workplace.

    public_rules = [
        ("COMPASSVALE", "COMPASSVALE"),
        ("WEST COAST PLAZA", "WEST COAST PLAZA"),
        ("VIVOCITY", "VIVOCITY"),
        ("CAUSEWAY POINT", "CAUSEWAY POINT"),
        ("JEM", "JEM"),
        ("ION ORCHARD", "ION ORCHARD"),
        ("MUSTAFA CENTRE", "MUSTAFA CENTRE"),
        ("PAN PACIFIC ORCHARD", "PAN PACIFIC ORCHARD"),
        ("CHANGI AIRPORT", "CHANGI AIRPORT"),
        ("MARINA BAY SANDS", "MARINA BAY SANDS"),
        ("THE STAR VISTA", "THE STAR VISTA"),
        ("CLEMENTI MALL", "CLEMENTI MALL"),
        ("MADRAS NEW WOODLANDS", "MADRAS NEW WOODLANDS"),
        ("NEW MADRAS WOODLANDS", "MADRAS NEW WOODLANDS"),
        ("NEW WOODLANDS MADRAS", "MADRAS NEW WOODLANDS"),
        ("RENDEZVOUS RESTAURANT", "RENDEZVOUS RESTAURANT"),
        ("GAYATHRI LITTLE INDIA", "GAYATHRI LITTLE INDIA"),
        ("GAYATHRI RESTAURANT", "GAYATHRI LITTLE INDIA"),
        ("GAYATRI RESTAURANT", "GAYATHRI LITTLE INDIA"),
        ("SAMY'S CURRY", "SAMY'S CURRY"),
        ("SAMYS CURRY", "SAMY'S CURRY"),
        ("YEW TEE POINT / YEWTEE", "YEW TEE POINT"),
        ("YEWTEE POINT", "YEW TEE POINT"),
        ("YEW TEE POINT", "YEW TEE POINT"),
    ]

    for needle, location_label in public_rules:
        if re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", upper):
            return location_label

    if upper.startswith("PRIVATE_"):
        return upper

    # Unrecognised address-looking locations are anonymised.
    if re.match(
        r"^(BLK\s*)?\d+\s+",
        upper,
    ):
        digest = hashlib.sha1(
            upper.encode()
        ).hexdigest()[:6].upper()

        return f"PRIVATE_{digest}"

    # Unknown readable text is not automatically safe for public publication.
    return "PRIVATE_" + hashlib.sha256(upper.encode()).hexdigest()[:12].upper()
