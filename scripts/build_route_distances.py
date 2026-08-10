from __future__ import annotations

import json
import os
import sys
import time

from datetime import date
from pathlib import Path
from typing import Any

import requests


ONEMAP_BASE_URL = "https://www.onemap.gov.sg"
AUTH_URL = f"{ONEMAP_BASE_URL}/api/auth/post/getToken"
SEARCH_URL = f"{ONEMAP_BASE_URL}/api/common/elastic/search"
ROUTE_URL = f"{ONEMAP_BASE_URL}/api/public/routingsvc/route"

ANALYTICS_FILE = Path("docs/data/analytics.json")
OUTPUT_FILE = Path("config/route_distances.json")

MIN_ROUTE_COUNT = 1
DISTANCE_ROUNDING_KM = 0.5
REQUEST_PAUSE_SECONDS = 0.20


PUBLIC_LOCATION_QUERIES = {
    "VIVOCITY": "VivoCity Singapore",
    "WEST COAST PLAZA": "West Coast Plaza Singapore",
    "JEM": "JEM Singapore",
    "CLEMENTI MALL": "The Clementi Mall Singapore",
    "CAUSEWAY POINT": "Causeway Point Singapore",
    "MUSTAFA CENTRE": "Mustafa Centre Singapore",
    "THE STAR VISTA": "The Star Vista Singapore",
    "PAN PACIFIC ORCHARD": "Pan Pacific Orchard Singapore",
    "MARINA BAY SANDS": "Marina Bay Sands Singapore",
    "CHANGI AIRPORT": "Changi Airport Singapore",
    "CLARKE QUAY CENTRAL": "059817",
    "DECATHLON - JOO KOON": "629117",
    "YEW TEE POINT": "689578",
    "YEW TEE POINT / YEWTEE": "689578",

    "MADRAS NEW WOODLANDS": "207474",
    "NEW MADRAS WOODLANDS": "207474",
    "NEW WOODLANDS MADRAS": "207474",
    "RENDEZVOUS RESTAURANT": "059817",
    "RENDEZVOUS": "059817",
    "GAYATHRI LITTLE INDIA": "218583",
    "GAYATHRI RESTAURANT": "218583",
    "GAYATRI RESTAURANT": "218583",
    "GAYATHRI": "218583",
    "SAMY'S CURRY": "249670",
    "SAMYS CURRY": "249670",
    "ANNALAKSHMI RESTAURANT": "068815",
    "CRAFTSMEN COFFEE (THOMSON)": "307623",
    "GEORGES MADBAR & GRILL": "459055",
    "KUMAR MESS - CLEMENTI": "129905",
    "NALAN RESTAURANT CITY HALL": "178905",
    "SUPER THAI BY SOI AROY @ PASIR": "118512",
    "SUPER THAI BY SOI AROY @ PASIR PANJANG": "118512",
}


def require_environment(name: str) -> str:
    value = os.environ.get(
        name,
        "",
    ).strip()

    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}"
        )

    return value


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{path} is not valid JSON."
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError(
            f"{path} must contain a JSON object."
        )

    return data


def load_private_locations() -> dict[str, str]:
    raw = require_environment(
        "PRIVATE_LOCATIONS_JSON"
    )

    try:
        data = json.loads(
            raw
        )
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "PRIVATE_LOCATIONS_JSON is not valid JSON."
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError(
            "PRIVATE_LOCATIONS_JSON must be a JSON object."
        )

    output: dict[str, str] = {}

    for alias, location in data.items():
        clean_alias = str(
            alias
        ).strip()

        clean_location = str(
            location
        ).strip()

        if clean_alias and clean_location:
            output[clean_alias] = clean_location

    return output


def safe_public_alias(alias: str) -> bool:
    text = str(
        alias or ""
    ).strip().upper()

    if not text or text == "UNKNOWN":
        return False

    if text.startswith("PRIVATE_"):
        return False

    return True


def load_routes() -> list[dict[str, Any]]:
    analytics = load_json(
        ANALYTICS_FILE
    )

    routes: list[dict[str, Any]] = []

    for route in analytics.get("routes", []):
        count = int(
            route.get(
                "overall",
                {},
            ).get(
                "count",
                0,
            )
            or 0
        )

        if count < MIN_ROUTE_COUNT:
            continue

        key = str(
            route.get("key", "")
        ).strip()

        origin = str(
            route.get("origin", "")
        ).strip()

        destination = str(
            route.get("destination", "")
        ).strip()

        if (
            not key
            or not safe_public_alias(origin)
            or not safe_public_alias(destination)
        ):
            continue

        routes.append(
            {
                "key": key,
                "origin": origin,
                "destination": destination,
                "count": count,
            }
        )

    routes.sort(
        key=lambda item: (
            -int(item["count"]),
            item["key"],
        )
    )

    # No route cap: process every current public route.
    return routes


def response_json(
    response: requests.Response,
    description: str,
) -> dict[str, Any]:
    if not response.ok:
        preview = response.text[:500].replace(
            "\n",
            " ",
        )

        raise RuntimeError(
            f"{description} failed. HTTP {response.status_code}. "
            f"Response: {preview}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"{description} returned invalid JSON."
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError(
            f"{description} returned an unexpected response."
        )

    return data


def get_onemap_token(
    email: str,
    password: str,
) -> str:
    print(
        "Authenticating with OneMap..."
    )

    response = requests.post(
        AUTH_URL,
        json={
            "email": email,
            "password": password,
        },
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        timeout=30,
    )

    data = response_json(
        response,
        "OneMap authentication",
    )

    token = (
        data.get("access_token")
        or data.get("token")
    )

    if not token:
        raise RuntimeError(
            "OneMap authentication returned no access token."
        )

    print(
        "OneMap authentication successful."
    )

    return str(
        token
    ).strip()


def location_query(
    alias: str,
    private_locations: dict[str, str],
) -> str:
    if alias in private_locations:
        return private_locations[alias]

    if alias in PUBLIC_LOCATION_QUERIES:
        return PUBLIC_LOCATION_QUERIES[alias]

    return f"{alias} Singapore"


def geocode_location(
    session: requests.Session,
    alias: str,
    query: str,
) -> tuple[float, float]:
    response = session.get(
        SEARCH_URL,
        params={
            "searchVal": query,
            "returnGeom": "Y",
            "getAddrDetails": "Y",
            "pageNum": 1,
        },
        timeout=30,
    )

    data = response_json(
        response,
        f"OneMap search for alias {alias}",
    )

    results = data.get(
        "results",
        [],
    )

    if not results:
        raise RuntimeError(
            f"No OneMap search results found for alias: {alias}"
        )

    first = results[0]

    latitude = first.get(
        "LATITUDE"
    )

    longitude = first.get(
        "LONGITUDE"
    )

    if latitude is None or longitude is None:
        raise RuntimeError(
            f"OneMap returned no coordinates for alias: {alias}"
        )

    return (
        float(latitude),
        float(longitude),
    )


def calculate_driving_distance(
    session: requests.Session,
    start: tuple[float, float],
    end: tuple[float, float],
    route_key: str,
) -> float:
    start_latitude, start_longitude = start
    end_latitude, end_longitude = end

    response = session.get(
        ROUTE_URL,
        params={
            "start": f"{start_latitude},{start_longitude}",
            "end": f"{end_latitude},{end_longitude}",
            "routeType": "drive",
        },
        timeout=60,
    )

    data = response_json(
        response,
        f"OneMap routing for {route_key}",
    )

    total_distance = data.get(
        "route_summary",
        {},
    ).get(
        "total_distance"
    )

    if total_distance is None:
        raise RuntimeError(
            f"No driving distance returned for {route_key}."
        )

    distance_km = float(
        total_distance
    ) / 1000

    if distance_km <= 0:
        raise RuntimeError(
            f"Invalid driving distance returned for {route_key}."
        )

    return distance_km


def round_distance(
    distance_km: float,
) -> float:
    return round(
        distance_km
        / DISTANCE_ROUNDING_KM
    ) * DISTANCE_ROUNDING_KM


def current_distance_record(
    old_routes: dict[str, Any],
    route: dict[str, Any],
) -> dict[str, Any] | None:
    record = old_routes.get(
        route["key"]
    )

    if not isinstance(record, dict):
        return None

    distance_km = float(
        record.get("distance_km") or 0
    )

    if distance_km <= 0:
        return None

    return {
        "origin": route["origin"],
        "destination": route["destination"],
        "historical_trips": route["count"],
        "distance_km": distance_km,
        "distance_precision_km": float(
            record.get("distance_precision_km")
            or DISTANCE_ROUNDING_KM
        ),
        "route_type": record.get(
            "route_type",
            "drive",
        ),
        "source": record.get(
            "source",
            "OneMap",
        ),
    }


def main() -> int:
    email = require_environment(
        "ONEMAP_EMAIL"
    )

    password = require_environment(
        "ONEMAP_PASSWORD"
    )

    private_locations = load_private_locations()
    routes = load_routes()

    if not routes:
        raise RuntimeError(
            "No current public routes were found in analytics.json."
        )

    print(
        f"Preparing distances for {len(routes)} public routes."
    )

    print(
        "Private location aliases available: "
        + ", ".join(
            sorted(
                private_locations.keys()
            )
        )
    )

    old_output = (
        load_json(OUTPUT_FILE)
        if OUTPUT_FILE.exists()
        else {}
    )

    old_routes = (
        old_output.get("routes", {})
        or {}
    )

    token = get_onemap_token(
        email,
        password,
    )

    session = requests.Session()

    # OneMap expects the token directly, not "Bearer <token>".
    session.headers.update(
        {
            "Authorization": token,
            "Accept": "application/json",
            "User-Agent": "grab-gojek-intelligence/1.0",
        }
    )

    aliases = sorted(
        {
            route["origin"]
            for route in routes
        }
        |
        {
            route["destination"]
            for route in routes
        }
    )

    print(
        f"Resolving {len(aliases)} unique location aliases."
    )

    coordinates: dict[str, tuple[float, float]] = {}
    failed_aliases: list[str] = []

    for alias in aliases:
        query = location_query(
            alias,
            private_locations,
        )

        try:
            coordinates[alias] = geocode_location(
                session,
                alias,
                query,
            )

            print(
                f"Resolved location alias: {alias}"
            )
        except Exception as exc:
            failed_aliases.append(
                alias
            )

            print(
                f"WARNING: Could not resolve {alias}: {exc}"
            )

        time.sleep(
            REQUEST_PAUSE_SECONDS
        )

    print(
        f"Successfully resolved {len(coordinates)} of "
        f"{len(aliases)} location aliases."
    )

    if failed_aliases:
        print(
            "Unresolved aliases: "
            + ", ".join(
                failed_aliases
            )
        )

    output_routes: dict[str, dict[str, Any]] = {}
    newly_calculated = 0
    carried_forward = 0
    failed_without_distance: list[str] = []

    for route in routes:
        key = route["key"]
        origin = route["origin"]
        destination = route["destination"]

        if (
            origin not in coordinates
            or destination not in coordinates
        ):
            old_record = current_distance_record(
                old_routes,
                route,
            )

            if old_record:
                output_routes[key] = old_record
                carried_forward += 1

                print(
                    f"Carried forward {key}: "
                    f"{old_record['distance_km']:.1f} km"
                )
            else:
                failed_without_distance.append(
                    key
                )

                print(
                    f"Skipping {key}: origin or destination was not resolved."
                )

            continue

        try:
            exact_distance = calculate_driving_distance(
                session,
                coordinates[origin],
                coordinates[destination],
                key,
            )

            public_distance = round_distance(
                exact_distance
            )

            output_routes[key] = {
                "origin": origin,
                "destination": destination,
                "historical_trips": route["count"],
                "distance_km": public_distance,
                "distance_precision_km": DISTANCE_ROUNDING_KM,
                "route_type": "drive",
                "source": "OneMap",
            }

            newly_calculated += 1

            print(
                f"Calculated {key}: {public_distance:.1f} km"
            )
        except Exception as exc:
            old_record = current_distance_record(
                old_routes,
                route,
            )

            if old_record:
                output_routes[key] = old_record
                carried_forward += 1

                print(
                    f"WARNING: Routing failed for {key}; carried forward "
                    f"{old_record['distance_km']:.1f} km. Reason: {exc}"
                )
            else:
                failed_without_distance.append(
                    key
                )

                print(
                    f"WARNING: Could not calculate {key}: {exc}"
                )

        time.sleep(
            REQUEST_PAUSE_SECONDS
        )

    if not output_routes:
        raise RuntimeError(
            "No route distances were generated or carried forward. "
            "The existing output file has not been replaced."
        )

    output = {
        "generated_on": date.today().isoformat(),
        "privacy_note": (
            "Exact private addresses and coordinates are not stored. "
            "Published driving distances are rounded."
        ),
        "distance_rounding_km": DISTANCE_ROUNDING_KM,
        "route_count": len(output_routes),
        "newly_calculated_count": newly_calculated,
        "carried_forward_count": carried_forward,
        "routes_without_distance": len(failed_without_distance),
        "routes": output_routes,
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_file = OUTPUT_FILE.with_suffix(
        ".json.tmp"
    )

    temp_file.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    json.loads(
        temp_file.read_text(
            encoding="utf-8"
        )
    )

    temp_file.replace(
        OUTPUT_FILE
    )

    print()
    print("========================================")
    print(f"Current public routes        : {len(routes)}")
    print(f"Newly calculated distances   : {newly_calculated}")
    print(f"Existing distances preserved : {carried_forward}")
    print(f"Routes still without distance: {len(failed_without_distance)}")
    print(f"Total saved route distances  : {len(output_routes)}")

    if failed_without_distance:
        print(
            "Still missing: "
            + ", ".join(
                failed_without_distance
            )
        )

    print(f"Saved output to: {OUTPUT_FILE}")
    print("========================================")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(
            main()
        )
    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        raise
