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


# Minimum number of historical rides
# before we calculate a route distance.
MIN_ROUTE_COUNT = 2


# Initially limit the number of routes.
#
# We can increase this later after checking
# that the distances look reasonable.
MAX_ROUTES = 20


# Round public distances to the nearest
# 0.5 km to reduce unnecessary location precision.
DISTANCE_ROUNDING_KM = 0.5


# ============================================================
# KNOWN PUBLIC LOCATIONS
#
# These are safe to keep in the public repository.
# Private addresses come from GitHub Secrets instead.
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
# HELPER FUNCTIONS
# ============================================================

def require_environment(
    name: str
) -> str:
    """
    Return a required environment variable.

    Raise a clear error when it is missing.
    """

    value = os.environ.get(
        name,
        ""
    ).strip()

    if not value:

        raise RuntimeError(
            f"Missing required environment variable: {name}"
        )

    return value


def load_private_locations() -> dict[str, str]:
    """
    Load private location aliases from the
    PRIVATE_LOCATIONS_JSON GitHub secret.

    Exact addresses are used only while the
    workflow runs and are never written to
    the output file.
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
        dict
    ):

        raise RuntimeError(
            "PRIVATE_LOCATIONS_JSON must contain a JSON object."
        )


    output = {}


    for (
        alias,
        address
    ) in data.items():

        alias_text = str(
            alias
        ).strip()

        address_text = str(
            address
        ).strip()


        if (
            alias_text
            and
            address_text
        ):

            output[
                alias_text
            ] = address_text


    return output


def load_routes() -> list[dict[str, Any]]:
    """
    Read trusted routes from the existing
    public analytics file.
    """

    if not ANALYTICS_FILE.exists():

        raise RuntimeError(
            f"Analytics file not found: {ANALYTICS_FILE}"
        )


    data = json.loads(
        ANALYTICS_FILE.read_text(
            encoding="utf-8"
        )
    )


    routes = []


    for route in data.get(
        "routes",
        []
    ):

        count = int(
            route
            .get(
                "overall",
                {}
            )
            .get(
                "count",
                0
            )
        )


        if count < MIN_ROUTE_COUNT:

            continue


        origin = str(
            route.get(
                "origin",
                ""
            )
        ).strip()


        destination = str(
            route.get(
                "destination",
                ""
            )
        ).strip()


        key = str(
            route.get(
                "key",
                ""
            )
        ).strip()


        if (
            not origin
            or
            not destination
            or
            not key
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
# ONEMAP AUTHENTICATION
# ============================================================

def get_onemap_token(
    email: str,
    password: str
) -> str:
    """
    Authenticate with OneMap and return
    the temporary access token.
    """

    response = requests.post(
        AUTH_URL,
        json={
            "email":
                email,

            "password":
                password,
        },
        timeout=30,
    )


    response.raise_for_status()


    data = response.json()


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
            "OneMap authentication succeeded "
            "but no access token was returned."
        )


    return str(
        token
    )


# ============================================================
# GEOCODING
# ============================================================

def location_query(
    alias: str,
    private_locations: dict[str, str]
) -> str:
    """
    Convert a safe dashboard alias into
    an address/search query.

    Private aliases are resolved from
    GitHub Secrets.

    Public places use readable search names.
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
    query: str
) -> tuple[float, float]:
    """
    Resolve a location into latitude
    and longitude using OneMap Search.

    The query itself is never printed,
    preventing private addresses from
    appearing in workflow logs.
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


    response.raise_for_status()


    data = response.json()


    results = data.get(
        "results",
        []
    )


    if not results:

        raise RuntimeError(
            f"Unable to locate alias: {alias}"
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
    end: tuple[float, float]
) -> float:
    """
    Calculate OneMap driving-route distance.

    OneMap returns total_distance in metres.
    Convert it to kilometres.
    """

    start_latitude, start_longitude = (
        start
    )

    end_latitude, end_longitude = (
        end
    )


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


    response.raise_for_status()


    data = response.json()


    summary = data.get(
        "route_summary",
        {}
    )


    total_distance = summary.get(
        "total_distance"
    )


    if total_distance is None:

        raise RuntimeError(
            "OneMap routing response did not "
            "contain route_summary.total_distance."
        )


    distance_metres = float(
        total_distance
    )


    return (
        distance_metres
        /
        1000
    )


def round_distance(
    distance_km: float
) -> float:
    """
    Round to the configured public precision.

    Example with 0.5 km rounding:

        18.24 -> 18.0
        18.31 -> 18.5
    """

    increment = (
        DISTANCE_ROUNDING_KM
    )


    return round(
        distance_km
        /
        increment
    ) * increment


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


    token = get_onemap_token(
        email,
        password
    )


    session = requests.Session()


    session.headers.update(
        {
            "Authorization":
                f"Bearer {token}",

            "Accept":
                "application/json",
        }
    )


    # --------------------------------------------------------
    # Geocode each unique safe alias only once.
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


    coordinates = {}


    for alias in aliases:

        query = location_query(
            alias,
            private_locations
        )


        try:

            coordinates[
                alias
            ] = geocode_location(
                session,
                alias,
                query
            )


            print(
                f"Resolved location alias: {alias}"
            )


        except Exception as exc:

            print(
                f"WARNING: Could not resolve "
                f"{alias}: {exc}"
            )


        time.sleep(
            0.2
        )


    # --------------------------------------------------------
    # Calculate route distances.
    # --------------------------------------------------------

    output_routes = {}


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
                f"Skipping route because a location "
                f"could not be resolved: {key}"
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

            print(
                f"WARNING: Could not calculate "
                f"{key}: {exc}"
            )


        time.sleep(
            0.2
        )


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


    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False
        )
        +
        "\n",
        encoding="utf-8",
    )


    print(
        f"Saved {len(output_routes)} routes "
        f"to {OUTPUT_FILE}"
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
