from __future__ import annotations

import hashlib
import json
import re

from pathlib import Path


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

        if (
            alias
            and
            any(
                str(fragment).strip().upper() in upper
                for fragment in fragments
                if str(fragment).strip()
            )
        ):
            return alias

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
    if (
        "OFFICE" in upper
        or "(WORK" in upper
        or (
            "SEMICONDUCTOR" in upper
            and "ASIA" in upper
        )
    ):
        return "OFFICE"

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
        if needle in upper:
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

    return (
        upper[:80]
        if upper
        else "UNKNOWN"
    )
