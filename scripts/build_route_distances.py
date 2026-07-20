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


# Process every trusted route in the
# current analytics database.
MIN_ROUTE_COUNT = 1

MAX_ROUTES = 60


# Public distances are rounded to
# the nearest 0.5 km.
DISTANCE_ROUNDING_KM = 0.5


# ============================================================
# PUBLIC LOCATION SEARCH QUERIES
#
# Exact private locations still come only
# from PRIVATE_LOCATIONS_JSON.
#
# Add alternative aliases here when the
# Grab/Gojek source uses different names
# for the same public destination.
# ============================================================

PUBLIC_LOCATION_QUERIES = {

    # --------------------------------------------------------
    # SHOPPING / LANDMARKS
    # --------------------------------------------------------

    "VIVOCITY":
        "VivoCity Singapore",

    "WEST COAST PLAZA":
        "West Coast Plaza Singapore",

    "JEM":
        "JEM Singapore",

    "CLEMENTI MALL":
        "The Clementi Mall Singapore",

    "CAUSEWAY POINT":
        "Causeway Point Singapore",

    "MUSTAFA CENTRE":
        "Mustafa Centre Singapore",

    "THE STAR VISTA":
        "The Star Vista Singapore",

    "PAN PACIFIC ORCHARD":
        "Pan Pacific Orchard Singapore",

    "MARINA BAY SANDS":
        "Marina Bay Sands Singapore",

    "CHANGI AIRPORT":
        "Changi Airport Singapore",


    # --------------------------------------------------------
    # RESTAURANTS
    # --------------------------------------------------------

    # Madras New Woodlands
    "MADRAS NEW WOODLANDS":
        "12 Upper Dickson Road Singapore",

    "NEW MADRAS WOODLANDS":
        "12 Upper Dickson Road Singapore",

    "NEW WOODLANDS MADRAS":
        "12 Upper Dickson Road Singapore",


    # Rendezvous Restaurant Hock Lock Kee
    "RENDEZVOUS RESTAURANT":
        "059817",

    "RENDEZVOUS":
        "059817",


    # Gayathri Restaurant, Little India
    "GAYATHRI LITTLE INDIA":
        "218583",

    "GAYATHRI RESTAURANT":
        "218583",

    "GAYATRI RESTAURANT":
        "218583",

    "GAYATHRI":
        "218583",


    # Other known restaurants
    "SAMY'S CURRY":
        "Samy's Curry Singapore",

    "SAMYS CURRY":
        "Samy's Curry Singapore",

}


# ============================================================
# ENVIRONMENT / FILE HELPERS
# ============================================================

def require_environment(
    name: str,
) -> str:

    value = os.environ.get(
        name,
        "",
    ).strip()


    if not value:

        raise RuntimeError(
            f"Missing required environment variable: {name}"
        )


    return value


def load_json(
    path: Path,
) -> dict[str, Any]:

    if not path.exists():

        return {}


    try:

        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )


    except json.JSONDecodeError:

        return {}


    if not isinstance(
        data,
        dict,
    ):

        return {}


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
        location,
    ) in data.items():

        clean_alias = str(
            alias
        ).strip()


        clean_location = str(
            location
        ).strip()


        if (
            clean_alias
            and
            clean_location
        ):

            output[
                clean_alias
            ] = clean_location


    return output


# ============================================================
# LOAD TRUSTED ANALYTICS ROUTES
# ============================================================

def load_routes() -> list[dict[str, Any]]:

    analytics = load_json(
        ANALYTICS_FILE
    )


    if not analytics:

        raise RuntimeError(
            "Unable to load docs/data/analytics.json."
        )


    routes = []


    for route in analytics.get(
        "routes",
        [],
    ):

        count = int(

            route
                .get(
                    "overall",
                    {},
                )
                .get(
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
            item[
                "count"
            ],
        reverse=True,
    )


    return routes[
        :MAX_ROUTES
    ]


# ============================================================
# HTTP HELPER
# ============================================================

def response_json(
    response: requests.Response,
    description: str,
) -> dict[str, Any]:

    if not response.ok:

        preview = (
            response.text[
                :500
            ]
            .replace(
                "\n",
                " "
            )
        )


        raise RuntimeError(
            f"{description} failed. "
            f"HTTP {response.status_code}. "
            f"Response: {preview}"
        )


    try:

        data = response.json()


    except ValueError as exc:

        raise RuntimeError(
            f"{description} returned invalid JSON."
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

        raise RuntimeError(
            "OneMap authentication returned no access token."
        )


    print(
        "OneMap authentication successful."
    )


    return str(
        token
    ).strip()


# ============================================================
# LOCATION SEARCH
# ============================================================

def location_query(
    alias: str,
    private_locations: dict[str, str],
) -> str:

    # Private aliases are always resolved
    # from the protected GitHub Secret.

    if alias in private_locations:

        return private_locations[
            alias
        ]


    # Known public locations use a
    # deliberately precise search value.

    if alias in PUBLIC_LOCATION_QUERIES:

        return PUBLIC_LOCATION_QUERIES[
            alias
        ]


    # Generic fallback for other trusted
    # public place names.

    return (
        f"{alias} Singapore"
    )


def geocode_location(
    session: requests.Session,
    alias: str,
    query: str,
) -> tuple[float, float]:

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
# ROUTING
# ============================================================

def calculate_driving_distance(
    session: requests.Session,
    start: tuple[float, float],
    end: tuple[float, float],
    route_key: str,
) -> float:

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


    total_distance = (

        data
            .get(
                "route_summary",
                {},
            )
            .get(
                "total_distance"
            )

    )


    if total_distance is None:

        raise RuntimeError(
            f"No driving distance returned for {route_key}."
        )


    distance_km = (

        float(
            total_distance
        )

        /

        1000

    )


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
        /
        DISTANCE_ROUNDING_KM

    ) * DISTANCE_ROUNDING_KM


# ============================================================
# MAIN
# ============================================================

def main() -> int:

    email = require_environment(
        "ONEMAP_EMAIL"
    )


    password = require_environment(
        "ONEMAP_PASSWORD"
    )


    private_locations = (
        load_private_locations()
    )


    routes = load_routes()


    print(
        f"Preparing distances for "
        f"{len(routes)} trusted routes."
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


    token = get_onemap_token(
        email,
        password,
    )


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
    # Collect every unique origin / destination alias
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
    # Geocode each alias once
    # --------------------------------------------------------

    coordinates: dict[
        str,
        tuple[
            float,
            float,
        ]
    ] = {}


    failed_aliases = []


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
            0.20
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
    # Calculate route distances
    # --------------------------------------------------------

    output_routes: dict[
        str,
        dict[str, Any]
    ] = {}


    failed_routes = []


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
                "origin or destination was not resolved."
            )


            failed_routes.append(
                key
            )


            continue


        try:

            exact_distance = (
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


            public_distance = (
                round_distance(
                    exact_distance
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
                    public_distance,

                "distance_precision_km":
                    DISTANCE_ROUNDING_KM,

                "route_type":
                    "drive",

                "source":
                    "OneMap",
            }


            print(
                f"Calculated {key}: "
                f"{public_distance:.1f} km"
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
            0.20
        )


    # --------------------------------------------------------
    # Safety check
    # --------------------------------------------------------

    if not output_routes:

        raise RuntimeError(
            "No route distances were generated. "
            "The existing output file has not been replaced."
        )


    # --------------------------------------------------------
    # Build output
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
    # Save only after successful generation
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


    print("")
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
            f"ERROR: {exc}",
            file=sys.stderr,
        )

        raise
