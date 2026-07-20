from __future__ import annotations

import json
import os
import sys
import time

from datetime import date
from pathlib import Path
from typing import Any

import requests


# ============================================================
# CONFIGURATION
# ============================================================

ONEMAP_BASE_URL = "https://www.onemap.gov.sg"

AUTH_URL = (
    f"{ONEMAP_BASE_URL}"
    "/api/auth/post/getToken"
)

SEARCH_URL = (
    f"{ONEMAP_BASE_URL}"
    "/api/common/elastic/search"
)

ROUTE_URL = (
    f"{ONEMAP_BASE_URL}"
    "/api/public/routingsvc/route"
)


ANALYTICS_FILE = Path(
    "docs/data/analytics.json"
)

OUTPUT_FILE = Path(
    "config/route_distances.json"
)


# Only routes with at least this many
# historical trips will be processed.
MIN_ROUTE_COUNT = 2


# Start with the 20 most-used routes.
# We can increase this later.
MAX_ROUTES = 20


# Public distances are rounded to
# the nearest 0.5 km.
DISTANCE_ROUNDING_KM = 0.5


# ============================================================
# PUBLIC LOCATION SEARCH NAMES
#
# These locations are safe to keep in the repository.
# Exact private addresses are loaded only from GitHub Secrets.
# ============================================================

PUBLIC_LOCATION_QUERIES = {

    "VIVOCITY":
        "VivoCity Singapore",

    "WEST COAST PLAZA":
        "West Coast Plaza Singapore",

    "MADRAS NEW WOODLANDS":
        "Madras New Woodlands Restaurant Singapore",

    "JEM":
        "JEM Singapore",

    "RENDEZVOUS RESTAURANT":
        "Rendezvous Restaurant Singapore",

    "CLEMENTI MALL":
        "The Clementi Mall Singapore",

    "MUSTAFA CENTRE":
        "Mustafa Centre Singapore",

    "CAUSEWAY POINT":
        "Causeway Point Singapore",

    "SAMY'S CURRY":
        "Samy's Curry Singapore",

    "THE STAR VISTA":
        "The Star Vista Singapore",

    "PAN PACIFIC ORCHARD":
        "Pan Pacific Orchard Singapore",

    "MARINA BAY SANDS":
        "Marina Bay Sands Singapore",

    "CHANGI AIRPORT":
        "Changi Airport Singapore",
}


# ============================================================
# BASIC HELPERS
# ============================================================

def require_environment(
    name: str,
) -> str:
    """
    Read a required environment variable.
    """

    value = os.environ.get(
        name,
        "",
    ).strip()

    if not value:

        raise RuntimeError(
            f"Missing required environment variable: {name}"
        )

    return value


def load_private_locations() -> dict[str, str]:
    """
    Load private aliases and addresses from the
    PRIVATE_LOCATIONS_JSON GitHub Secret.

    Exact addresses are never written to the
    generated route_distances.json file.
    """

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


    if not isinstance(
        data,
        dict,
    ):

        raise RuntimeError(
            "PRIVATE_LOCATIONS_JSON must be a JSON object."
        )


    output: dict[str, str] = {}


    for (
        alias,
        address,
    ) in data.items():

        clean_alias = str(
            alias
        ).strip()

        clean_address = str(
            address
        ).strip()


        if (
            clean_alias
            and
            clean_address
        ):

            output[
                clean_alias
            ] = clean_address


    return output


# ============================================================
# ANALYTICS ROUTES
# ============================================================

def load_routes() -> list[dict[str, Any]]:
    """
    Load the most frequently used trusted routes
    from the current analytics.json file.
    """

    if not ANALYTICS_FILE.exists():

        raise RuntimeError(
            f"Analytics file not found: {ANALYTICS_FILE}"
        )


    try:

        analytics = json.loads(
            ANALYTICS_FILE.read_text(
                encoding="utf-8"
            )
        )

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            "docs/data/analytics.json is not valid JSON."
        ) from exc


    routes: list[
        dict[str, Any]
    ] = []


    for route in analytics.get(
        "routes",
        [],
    ):

        overall = route.get(
            "overall",
            {},
        )


        count = int(
            overall.get(
                "count",
                0,
            )
            or 0
        )


        if count < MIN_ROUTE_COUNT:

            continue


        key = str(
            route.get(
                "key",
                "",
            )
        ).strip()


        origin = str(
            route.get(
                "origin",
                "",
            )
        ).strip()


        destination = str(
            route.get(
                "destination",
                "",
            )
        ).strip()


        if (
            not key
            or
            not origin
            or
            not destination
        ):

            continue


        routes.append(
            {
                "key":
                    key,

                "origin":
                    origin,

                "destination":
                    destination,

                "count":
                    count,
            }
        )


    routes.sort(
        key=lambda item:
            item["count"],
        reverse=True,
    )


    selected_routes = routes[
        :MAX_ROUTES
    ]


    if not selected_routes:

        raise RuntimeError(
            "No eligible routes were found in analytics.json."
        )


    return selected_routes


# ============================================================
# HTTP RESPONSE HELPER
# ============================================================

def response_json(
    response: requests.Response,
    description: str,
) -> dict[str, Any]:
    """
    Validate an HTTP response and return JSON.

    Error messages include the API response,
    but never include the private search query.
    """

    if not response.ok:

        response_preview = (
            response.text[:500]
            .replace(
                "\n",
                " ",
            )
        )

        raise RuntimeError(
            f"{description} failed. "
            f"HTTP {response.status_code}. "
            f"Response: {response_preview}"
        )


    try:

        data = response.json()

    except ValueError as exc:

        response_preview = (
            response.text[:500]
            .replace(
                "\n",
                " ",
            )
        )

        raise RuntimeError(
            f"{description} returned invalid JSON. "
            f"Response: {response_preview}"
        ) from exc


    if not isinstance(
        data,
        dict,
    ):

        raise RuntimeError(
            f"{description} returned an unexpected response."
        )


    return data


# ============================================================
# ONEMAP AUTHENTICATION
# ============================================================

def get_onemap_token(
    email: str,
    password: str,
) -> str:
    """
    Authenticate with OneMap and obtain
    an access token.
    """

    print(
        "Authenticating with OneMap..."
    )


    response = requests.post(
        AUTH_URL,
        json={
            "email":
                email,

            "password":
                password,
        },
        headers={
            "Accept":
                "application/json",

            "Content-Type":
                "application/json",
        },
        timeout=30,
    )


    data = response_json(
        response,
        "OneMap authentication",
    )


    token = (
        data.get(
            "access_token"
        )
        or
        data.get(
            "token"
        )
    )


    if not token:

        available_fields = ", ".join(
            sorted(
                str(
                    key
                )
                for key in data.keys()
            )
        )

        raise RuntimeError(
            "OneMap authentication response did not "
            "contain an access token. "
            f"Returned fields: {available_fields}"
        )


    print(
        "OneMap authentication successful."
    )


    return str(
        token
    ).strip()


# ============================================================
# LOCATION RESOLUTION
# ============================================================

def location_query(
    alias: str,
    private_locations: dict[str, str],
) -> str:
    """
    Convert a public alias into a OneMap
    search query.

    Private locations are retrieved from
    GitHub Secrets.
    """

    if alias in private_locations:

        return private_locations[
            alias
        ]


    if alias in PUBLIC_LOCATION_QUERIES:

        return PUBLIC_LOCATION_QUERIES[
            alias
        ]


    return (
        f"{alias} Singapore"
    )


def geocode_location(
    session: requests.Session,
    alias: str,
    query: str,
) -> tuple[float, float]:
    """
    Resolve a location alias to coordinates.

    The private query itself is deliberately
    excluded from all workflow log messages.
    """

    response = session.get(
        SEARCH_URL,
        params={
            "searchVal":
                query,

            "returnGeom":
                "Y",

            "getAddrDetails":
                "Y",

            "pageNum":
                1,
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


    first = results[
        0
    ]


    latitude = first.get(
        "LATITUDE"
    )


    longitude = first.get(
        "LONGITUDE"
    )


    if (
        latitude is None
        or
        longitude is None
    ):

        raise RuntimeError(
            f"OneMap returned no coordinates for alias: {alias}"
        )


    return (
        float(
            latitude
        ),
        float(
            longitude
        ),
    )


# ============================================================
# DRIVING ROUTE CALCULATION
# ============================================================

def calculate_driving_distance(
    session: requests.Session,
    start: tuple[float, float],
    end: tuple[float, float],
    route_key: str,
) -> float:
    """
    Calculate driving distance between
    two coordinates.

    Returned distance is converted from
    metres to kilometres.
    """

    (
        start_latitude,
        start_longitude,
    ) = start


    (
        end_latitude,
        end_longitude,
    ) = end


    response = session.get(
        ROUTE_URL,
        params={
            "start":
                (
                    f"{start_latitude},"
                    f"{start_longitude}"
                ),

            "end":
                (
                    f"{end_latitude},"
                    f"{end_longitude}"
                ),

            "routeType":
                "drive",
        },
        timeout=60,
    )


    data = response_json(
        response,
        f"OneMap routing for {route_key}",
    )


    route_summary = data.get(
        "route_summary",
        {},
    )


    total_distance = route_summary.get(
        "total_distance"
    )


    if total_distance is None:

        raise RuntimeError(
            f"OneMap routing returned no distance for {route_key}."
        )


    distance_metres = float(
        total_distance
    )


    if distance_metres <= 0:

        raise RuntimeError(
            f"OneMap returned an invalid distance for {route_key}."
        )


    return (
        distance_metres
        /
        1000
    )


def round_distance(
    distance_km: float,
) -> float:
    """
    Round public distance to the
    configured precision.
    """

    return round(
        distance_km
        /
        DISTANCE_ROUNDING_KM
    ) * DISTANCE_ROUNDING_KM


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    """
    Generate route_distances.json.
    """

    # --------------------------------------------------------
    # Read GitHub Secrets
    # --------------------------------------------------------

    email = require_environment(
        "ONEMAP_EMAIL"
    )


    password = require_environment(
        "ONEMAP_PASSWORD"
    )


    private_locations = (
        load_private_locations()
    )


    print(
        "Private location aliases available: "
        +
        ", ".join(
            sorted(
                private_locations.keys()
            )
        )
    )


    # --------------------------------------------------------
    # Load trusted routes
    # --------------------------------------------------------

    routes = load_routes()


    print(
        f"Preparing distances for "
        f"{len(routes)} trusted routes."
    )


    # --------------------------------------------------------
    # Authenticate
    # --------------------------------------------------------

    token = get_onemap_token(
        email,
        password,
    )


    # --------------------------------------------------------
    # Create authenticated HTTP session
    #
    # IMPORTANT:
    #
    # OneMap expects the token itself as
    # the Authorization header value.
    #
    # Do NOT prefix it with "Bearer ".
    # --------------------------------------------------------

    session = requests.Session()


    session.headers.update(
        {
            "Authorization":
                token,

            "Accept":
                "application/json",

            "User-Agent":
                "grab-gojek-intelligence/1.0",
        }
    )


    # --------------------------------------------------------
    # Find all aliases used by selected routes
    # --------------------------------------------------------

    aliases = sorted(
        {
            route[
                "origin"
            ]
            for route in routes
        }
        |
        {
            route[
                "destination"
            ]
            for route in routes
        }
    )


    print(
        f"Resolving {len(aliases)} unique location aliases."
    )


    # --------------------------------------------------------
    # Geocode locations
    # --------------------------------------------------------

    coordinates: dict[
        str,
        tuple[
            float,
            float,
        ]
    ] = {}


    failed_aliases: list[
        str
    ] = []


    for alias in aliases:

        query = location_query(
            alias,
            private_locations,
        )


        try:

            coordinates[
                alias
            ] = geocode_location(
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
                f"WARNING: Could not resolve "
                f"{alias}: {exc}"
            )


        time.sleep(
            0.25
        )


    print(
        f"Successfully resolved "
        f"{len(coordinates)} of "
        f"{len(aliases)} location aliases."
    )


    if failed_aliases:

        print(
            "Unresolved aliases: "
            +
            ", ".join(
                failed_aliases
            )
        )


    # --------------------------------------------------------
    # Calculate driving distances
    # --------------------------------------------------------

    output_routes: dict[
        str,
        dict[str, Any]
    ] = {}


    failed_routes: list[
        str
    ] = []


    for route in routes:

        key = route[
            "key"
        ]


        origin = route[
            "origin"
        ]


        destination = route[
            "destination"
        ]


        if (
            origin not in coordinates
            or
            destination not in coordinates
        ):

            print(
                f"Skipping {key}: "
                "origin or destination "
                "was not resolved."
            )


            failed_routes.append(
                key
            )


            continue


        try:

            exact_distance_km = (
                calculate_driving_distance(
                    session,
                    coordinates[
                        origin
                    ],
                    coordinates[
                        destination
                    ],
                    key,
                )
            )


            public_distance_km = (
                round_distance(
                    exact_distance_km
                )
            )


            output_routes[
                key
            ] = {
                "origin":
                    origin,

                "destination":
                    destination,

                "historical_trips":
                    route[
                        "count"
                    ],

                "distance_km":
                    public_distance_km,

                "distance_precision_km":
                    DISTANCE_ROUNDING_KM,

                "route_type":
                    "drive",

                "source":
                    "OneMap",
            }


            print(
                f"Calculated {key}: "
                f"{public_distance_km:.1f} km"
            )


        except Exception as exc:

            failed_routes.append(
                key
            )


            print(
                f"WARNING: Could not calculate "
                f"{key}: {exc}"
            )


        time.sleep(
            0.25
        )


    # ========================================================
    # SAFETY CHECK
    #
    # Never overwrite the existing output with
    # another empty routes object.
    # ========================================================

    if not output_routes:

        raise RuntimeError(
            "No route distances were generated. "
            "The output file has NOT been replaced. "
            "Review the OneMap errors above in the workflow log."
        )


    # --------------------------------------------------------
    # Build safe public output
    # --------------------------------------------------------

    output = {
        "generated_on":
            date.today().isoformat(),

        "privacy_note":
            (
                "Exact private addresses and coordinates "
                "are not stored. Published driving "
                "distances are rounded."
            ),

        "distance_rounding_km":
            DISTANCE_ROUNDING_KM,

        "route_count":
            len(
                output_routes
            ),

        "routes":
            output_routes,
    }


    # --------------------------------------------------------
    # Write only after successful generation
    # --------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        )
        +
        "\n",
        encoding="utf-8",
    )


    print(
        ""
    )


    print(
        "========================================"
    )


    print(
        f"Successfully generated "
        f"{len(output_routes)} route distances."
    )


    if failed_routes:

        print(
            f"{len(failed_routes)} routes "
            "could not be calculated."
        )


    print(
        f"Saved output to: {OUTPUT_FILE}"
    )


    print(
        "========================================"
    )


    return 0


if __name__ == "__main__":

    try:

        raise SystemExit(
            main()
        )

    except Exception as exc:

        print(
            "",
            file=sys.stderr,
        )


        print(
            "========================================",
            file=sys.stderr,
        )


        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )


        print(
            "========================================",
            file=sys.stderr,
        )


        raise
