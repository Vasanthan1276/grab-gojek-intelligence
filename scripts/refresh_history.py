from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from build_analytics import (
    build,
    find_unpublished_route_candidates,
    is_publishable_location,
)
from import_gojek_pdf import import_gojek_pdf
from import_grab_pdf import import_grab_pdf
from normalization import load_aliases, normalize_location


def load_json(path: Path, default):
    if not path.exists():
        return deepcopy(default)

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def atomic_write_json(
    path: Path,
    data: Any,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp = path.with_suffix(
        path.suffix
        + ".tmp"
    )

    temp.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    json.loads(
        temp.read_text(
            encoding="utf-8"
        )
    )

    temp.replace(
        path
    )


def stable_key(
    row: dict[str, Any],
) -> str:
    """
    Stable deduplication fingerprint.

    Origin/destination are intentionally excluded so location cleanup cannot
    create a duplicate transaction.
    """
    parts = [
        str(row.get("provider") or ""),
        str(row.get("datetime") or ""),
        f"{float(row.get('amount') or 0):.2f}",
        str(row.get("currency") or ""),
        str(row.get("category") or ""),
    ]

    return "|".join(
        parts
    )


def record_id(
    row: dict[str, Any],
) -> str:
    return hashlib.sha1(
        stable_key(
            row
        ).encode(
            "utf-8"
        )
    ).hexdigest()[:16]


def normalize_record(
    row: dict[str, Any],
    aliases,
) -> dict[str, Any]:
    """Normalise new imports and the existing private historical master."""
    out = dict(
        row
    )

    dt = datetime.fromisoformat(
        str(
            out["datetime"]
        )
    )

    out["datetime"] = dt.isoformat(
        timespec="minutes"
    )
    out["date"] = dt.date().isoformat()
    out["time"] = dt.strftime("%H:%M")
    out["hour"] = dt.hour
    out["weekday"] = dt.strftime("%A")

    out["provider"] = str(
        out.get("provider") or ""
    ).strip()

    out["category"] = str(
        out.get("category") or "ride"
    ).strip()

    out["service"] = str(
        out.get("service")
        or (
            "Gojek"
            if out["provider"] == "Gojek"
            else "Standard"
        )
    ).strip()

    out["origin"] = normalize_location(
        out.get("origin") or "UNKNOWN",
        aliases,
    )

    out["destination"] = normalize_location(
        out.get("destination") or "UNKNOWN",
        aliases,
    )

    out["amount"] = round(
        float(out.get("amount") or 0),
        2,
    )

    out["currency"] = str(
        out.get("currency") or "SGD"
    ).strip().upper()

    out["id"] = str(
        out.get("id") or record_id(out)
    )

    if (
        out["provider"] == "Grab"
        and out["category"] == "ride"
    ):
        pricing = str(
            out.get("pricing_type") or ""
        ).strip()

        if not pricing:
            service_upper = out["service"].upper()

            if "METERED" in service_upper:
                pricing = "Metered"
            elif (
                "PLUS" in service_upper
                or "PREMIUM" in service_upper
            ):
                pricing = "Premium"
            else:
                pricing = "Fixed"

        out["pricing_type"] = pricing

    return out


def count_location_changes(
    before_rows: list[dict[str, Any]],
    after_rows: list[dict[str, Any]],
) -> int:
    changes = 0

    for before, after in zip(
        before_rows,
        after_rows,
    ):
        for field in (
            "origin",
            "destination",
        ):
            old = str(
                before.get(field) or "UNKNOWN"
            ).strip()

            new = str(
                after.get(field) or "UNKNOWN"
            ).strip()

            if old != new:
                changes += 1

    return changes


def migrated_trusted_route_keys(
    current_analytics: dict[str, Any],
    aliases,
) -> tuple[set[str], int]:
    """
    Re-normalise historical public route keys before carrying trust forward.
    Unpublishable/private routes are intentionally not trusted again.
    """
    output: set[str] = set()
    dropped = 0

    for route in current_analytics.get(
        "routes",
        [],
    ):
        origin = normalize_location(
            route.get("origin") or "UNKNOWN",
            aliases,
        )

        destination = normalize_location(
            route.get("destination") or "UNKNOWN",
            aliases,
        )

        if not (
            is_publishable_location(origin)
            and is_publishable_location(destination)
        ):
            dropped += 1
            continue

        output.add(
            f"{origin}__{destination}"
        )

    return output, dropped


def configure_tesseract_if_needed(
    grab_pdfs: list[Path],
) -> None:
    if not grab_pdfs:
        return

    import pytesseract

    executable = shutil.which(
        "tesseract"
    )

    if executable:
        pytesseract.pytesseract.tesseract_cmd = executable
        return

    candidates = [
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    ]

    for candidate in candidates:
        if candidate.exists():
            pytesseract.pytesseract.tesseract_cmd = str(
                candidate
            )
            return

    raise RuntimeError(
        "Grab PDF processing requires the Tesseract OCR desktop application. "
        "Install Tesseract OCR for Windows, then rerun refresh_history.bat."
    )


def validate_public_analytics(
    new_data: dict[str, Any],
    current_data: dict[str, Any],
) -> None:
    summary = new_data.get(
        "summary",
        {},
    )

    if int(
        summary.get("total_transactions", 0)
    ) <= 0:
        raise RuntimeError(
            "Generated analytics contains no transactions."
        )

    old_total = int(
        current_data.get(
            "summary",
            {},
        ).get(
            "total_transactions",
            0,
        )
        or 0
    )

    new_total = int(
        summary.get(
            "total_transactions",
            0,
        )
        or 0
    )

    if (
        old_total
        and new_total < old_total
    ):
        raise RuntimeError(
            f"Safety stop: transaction count would shrink from "
            f"{old_total} to {new_total}. "
            "The current analytics.json has not been replaced."
        )

    serialized = json.dumps(
        new_data,
        ensure_ascii=False,
    ).lower()

    forbidden_keys = [
        '"datetime"',
        '"booking_code"',
        '"phone"',
        '"email"',
    ]

    for token in forbidden_keys:
        if token in serialized:
            raise RuntimeError(
                f"Privacy validation failed: public analytics contains {token}."
            )

    routes = new_data.get(
        "routes",
        [],
    )

    if not isinstance(routes, list) or not routes:
        raise RuntimeError(
            "Generated analytics contains no publishable routes."
        )

    for route in routes:
        origin = str(
            route.get("origin") or ""
        ).strip()

        destination = str(
            route.get("destination") or ""
        ).strip()

        if not (
            is_publishable_location(origin)
            and is_publishable_location(destination)
        ):
            raise RuntimeError(
                "Privacy validation failed: an unpublishable route "
                "survived the analytics build."
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Safely merge reports into the private master, clean historical "
            "location labels, and rebuild public analytics."
        )
    )

    parser.add_argument("--input", default="local_data")
    parser.add_argument("--master", default="local_private/transactions.json")
    parser.add_argument("--aliases", default="config/private_aliases.json")
    parser.add_argument("--analytics", default="docs/data/analytics.json")
    parser.add_argument("--distances", default="config/route_distances.json")
    parser.add_argument("--report", default="local_private/last_refresh_report.json")
    args = parser.parse_args()

    root = Path(
        args.input
    )

    grab_pdfs = sorted(
        (root / "grab").glob("*.pdf")
    )

    gojek_pdfs = sorted(
        (root / "gojek").glob("*.pdf")
    )

    if not grab_pdfs and not gojek_pdfs:
        raise RuntimeError(
            "No PDFs found. Put fresh Grab reports in local_data/grab/ "
            "and/or Gojek reports in local_data/gojek/."
        )

    alias_path = Path(
        args.aliases
    )

    if not alias_path.exists():
        raise RuntimeError(
            "config/private_aliases.json is missing. "
            "Run setup_private_aliases.bat once before importing reports."
        )

    aliases = load_aliases(
        alias_path
    )

    configure_tesseract_if_needed(
        grab_pdfs
    )

    master_path = Path(
        args.master
    )

    raw_existing_master = load_json(
        master_path,
        [],
    )

    existing_master = [
        normalize_record(
            row,
            aliases,
        )
        for row in raw_existing_master
    ]

    location_fields_normalized = count_location_changes(
        raw_existing_master,
        existing_master,
    )

    current_analytics = load_json(
        Path(args.analytics),
        {},
    )

    trusted_route_keys, trusted_routes_dropped = migrated_trusted_route_keys(
        current_analytics,
        aliases,
    )

    imported: list[dict[str, Any]] = []
    import_files: list[dict[str, Any]] = []

    for path in gojek_pdfs:
        rows = [
            normalize_record(
                row,
                aliases,
            )
            for row in import_gojek_pdf(
                path,
                aliases,
            )
        ]

        imported.extend(
            rows
        )

        import_files.append(
            {
                "provider": "Gojek",
                "file": path.name,
                "records": len(rows),
            }
        )

        print(
            f"Imported {len(rows):4d} rows from Gojek file: {path.name}"
        )

    for path in grab_pdfs:
        rows = [
            normalize_record(
                row,
                aliases,
            )
            for row in import_grab_pdf(
                path,
                aliases,
            )
        ]

        imported.extend(
            rows
        )

        import_files.append(
            {
                "provider": "Grab",
                "file": path.name,
                "records": len(rows),
            }
        )

        print(
            f"Imported {len(rows):4d} rows from Grab file: {path.name}"
        )

    merged: dict[str, dict[str, Any]] = {}

    for row in existing_master:
        merged[
            stable_key(row)
        ] = row

    duplicate_count = 0
    added_count = 0

    for row in imported:
        key = stable_key(
            row
        )

        if key in merged:
            duplicate_count += 1
            continue

        merged[
            key
        ] = row
        added_count += 1

    transactions = sorted(
        merged.values(),
        key=lambda row: row["datetime"],
    )

    distance_data = load_json(
        Path(args.distances),
        {},
    )

    new_analytics = build(
        transactions,
        trusted_route_keys=trusted_route_keys,
        distance_data=distance_data,
    )

    validate_public_analytics(
        new_analytics,
        current_analytics,
    )

    candidates = find_unpublished_route_candidates(
        transactions,
        trusted_route_keys,
    )

    report = {
        "refreshed_at": datetime.now().isoformat(timespec="seconds"),
        "master_before": len(raw_existing_master),
        "historical_location_fields_normalized": location_fields_normalized,
        "trusted_route_keys_after_cleanup": len(trusted_route_keys),
        "trusted_routes_dropped_for_privacy": trusted_routes_dropped,
        "rows_read_from_reports": len(imported),
        "duplicates_skipped": duplicate_count,
        "new_transactions_added": added_count,
        "master_after": len(transactions),
        "public_routes": len(new_analytics.get("routes", [])),
        "routes_with_distance": int(
            new_analytics.get(
                "distance_analysis",
                {},
            ).get(
                "routes_with_distance",
                0,
            )
        ),
        "files": import_files,
        "unpublished_route_candidates": candidates,
    }

    analytics_path = Path(
        args.analytics
    )

    if analytics_path.exists():
        backup_dir = Path(
            "local_private/backups"
        )

        backup_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        stamp = datetime.now().strftime(
            "%Y%m%d-%H%M%S"
        )

        shutil.copy2(
            analytics_path,
            backup_dir / f"analytics-{stamp}.json",
        )

    atomic_write_json(
        master_path,
        transactions,
    )

    atomic_write_json(
        Path(args.report),
        report,
    )

    atomic_write_json(
        analytics_path,
        new_analytics,
    )

    print()
    print("============================================================")
    print("HISTORICAL REFRESH + PRIVACY CLEANUP COMPLETE")
    print("============================================================")
    print(f"Private master before       : {len(raw_existing_master)}")
    print(f"Historical location fields  : {location_fields_normalized} normalised")
    print(f"Old trusted routes dropped  : {trusted_routes_dropped}")
    print(f"Rows read from reports      : {len(imported)}")
    print(f"Duplicates skipped          : {duplicate_count}")
    print(f"New transactions added      : {added_count}")
    print(f"Private master after        : {len(transactions)}")
    print(f"Public routes               : {len(new_analytics.get('routes', []))}")
    print(
        "Routes with current distance: "
        f"{new_analytics.get('distance_analysis', {}).get('routes_with_distance', 0)}"
    )
    print()
    print("Public file updated: docs/data/analytics.json")
    print("Private master:       local_private/transactions.json (Git ignored)")
    print("Refresh report:       local_private/last_refresh_report.json (Git ignored)")

    if candidates:
        print(
            f"Review later: {len(candidates)} one-off/private/unclean route "
            "candidates remain private."
        )

    print()
    print(
        "Next: review the result, commit the safe public changes, then run "
        "Build Route Distances followed by Enrich Distance Metrics."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"\nERROR: {exc}",
            file=sys.stderr,
        )
        raise
