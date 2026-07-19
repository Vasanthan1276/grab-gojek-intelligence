from __future__ import annotations

import hashlib
import json
import re

from pathlib import Path


def _clean(value: str) -> str:
    """
    Clean location text before matching.
    """

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
        value
    ).strip(
        " ,._-|;:"
    )


def load_aliases(
    path: str | Path | None
):
    """
    Load optional private aliases.

    These aliases can be stored locally
    without exposing exact private addresses
    in the public GitHub repository.
    """

    if (
        not path
        or
        not Path(path).exists()
    ):
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


def normalize_location(
    value: str,
    aliases=None
) -> str:
    """
    Convert raw Grab and Gojek location names
    into consistent location labels.
    """

    value = _clean(
        value
    )

    upper = value.upper()


    # =====================================================
    # PRIVATE USER ALIASES
    #
    # These are checked first.
    #
    # Examples:
    #
    # HOME
    # OFFICE
    # V_PLACE
    #
    # Exact private addresses do not need to be
    # stored in this public script.
    # =====================================================

    for rule in aliases or []:

        fragments = (
            rule.get(
                "contains",
                []
            )
        )

        if any(
            str(fragment).upper()
            in upper

            for fragment
            in fragments
        ):
            return rule[
                "alias"
            ]


    # =====================================================
    # KNOWN SAFE / PUBLIC-FACING LOCATION LABELS
    #
    # These rules allow readable names to remain
    # visible in the dashboard.
    # =====================================================

    public_rules = {

        # User-friendly area label.
        #
        # This catches Compassvale addresses without
        # publishing an exact residential address.
        "COMPASSVALE":
            "COMPASSVALE",

        "WEST COAST PLAZA":
            "WEST COAST PLAZA",

        "VIVOCITY":
            "VIVOCITY",

        "CAUSEWAY POINT":
            "CAUSEWAY POINT",

        "JEM":
            "JEM",

        "ION ORCHARD":
            "ION ORCHARD",

        "MUSTAFA CENTRE":
            "MUSTAFA CENTRE",

        "PAN PACIFIC ORCHARD":
            "PAN PACIFIC ORCHARD",

        "CHANGI AIRPORT":
            "CHANGI AIRPORT",

        "MARINA BAY SANDS":
            "MARINA BAY SANDS"
    }


    for (
        needle,
        location_label
    ) in public_rules.items():

        if needle in upper:

            return (
                location_label
            )


    # =====================================================
    # PRIVACY FALLBACK
    #
    # Any address-looking location that has not already
    # been recognised is converted into an anonymous,
    # repeatable identifier.
    #
    # Example:
    #
    # PRIVATE_A1B2C3
    #
    # The same address will always generate the same ID.
    # =====================================================

    if re.match(
        r"^(BLK\s*)?\d+\s+",
        upper
    ):

        digest = hashlib.sha1(
            upper.encode()
        ).hexdigest()[:6].upper()

        return (
            f"PRIVATE_{digest}"
        )


    # =====================================================
    # GENERAL LOCATION
    # =====================================================

    return (
        upper[:80]
        if upper
        else "UNKNOWN"
    )
