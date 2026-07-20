from __future__ import annotations

import json

from datetime import date
from pathlib import Path
from typing import Any


ANALYTICS_FILE = Path(
    "docs/data/analytics.json"
)

DISTANCES_FILE = Path(
    "config/route_distances.json"
)


# ============================================================
# BASIC HELPERS
# ============================================================

def load_json(
    path: Path,
) -> dict[str, Any]:

    if not path.exists():

        raise RuntimeError(
            f"Required file not found: {path}"
        )


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


    if not isinstance(
        data,
        dict,
    ):

        raise RuntimeError(
            f"{path} must contain a JSON object."
        )


    return data


def round_money(
    value: float,
) -> float:

    return round(
        float(value),
        2,
    )


def divide_fare_by_distance(
    value: Any,
    distance_km: float,
) -> float | None:

    if value is None:

        return None


    try:

        number = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):

        return None


    if distance_km <= 0:

        return None


    return round_money(
        number
        /
        distance_km
    )


# ============================================================
# COST PER KM STATISTICS
# ============================================================

def cost_per_km_stats(
    stats: dict[str, Any] | None,
    distance_km: float,
) -> dict[str, Any] | None:

    if not stats:

        return None


    output: dict[str, Any] = {

        "count":
            int(
                stats.get(
                    "count",
                    0,
                )
                or 0
            ),

    }


    for field in [

        "average",

        "median",

        "min",

        "max",

        "p10",

        "p25",

        "p75",

        "p90",

    ]:

        result = (
            divide_fare_by_distance(
                stats.get(
                    field
                ),
                distance_km,
            )
        )


        if result is not None:

            output[
                field
            ] = result


    return output


# ============================================================
# ENRICH ONE ROUTE
# ============================================================

def enrich_route(
    route: dict[str, Any],
    distance_record: dict[str, Any],
) -> None:

    distance_km = float(

        distance_record.get(
            "distance_km",
            0,
        )

        or 0

    )


    if distance_km <= 0:

        return


    # --------------------------------------------------------
    # DISTANCE INFORMATION
    # --------------------------------------------------------

    route[
        "distance"
    ] = {

        "distance_km":
            distance_km,

        "route_type":
            distance_record.get(
                "route_type",
                "drive",
            ),

        "source":
            distance_record.get(
                "source",
                "OneMap",
            ),

        "distance_precision_km":
            distance_record.get(
                "distance_precision_km",
                0.5,
            ),

    }


    # --------------------------------------------------------
    # OVERALL COST PER KM
    # --------------------------------------------------------

    overall_cost = (
        cost_per_km_stats(

            route.get(
                "overall"
            ),

            distance_km,

        )
    )


    # --------------------------------------------------------
    # PROVIDER COST PER KM
    # --------------------------------------------------------

    provider_costs: dict[
        str,
        Any,
    ] = {}


    for (
        provider,
        stats,
    ) in route.get(
        "providers",
        {},
    ).items():

        result = (
            cost_per_km_stats(

                stats,

                distance_km,

            )
        )


        if result:

            provider_costs[
                provider
            ] = result


    # --------------------------------------------------------
    # GRAB PRICING TYPE COST PER KM
    #
    # Fixed
    # Metered
    # Premium
    # --------------------------------------------------------

    grab_pricing_costs: dict[
        str,
        Any,
    ] = {}


    for (
        pricing_type,
        stats,
    ) in route.get(
        "grab_pricing_types",
        {},
    ).items():

        result = (
            cost_per_km_stats(

                stats,

                distance_km,

            )
        )


        if result:

            grab_pricing_costs[
                pricing_type
            ] = result


    # --------------------------------------------------------
    # SAVE COST PER KM ANALYTICS
    # --------------------------------------------------------

    route[
        "cost_per_km"
    ] = {

        "overall":
            overall_cost,

        "providers":
            provider_costs,

        "grab_pricing_types":
            grab_pricing_costs,

    }


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    analytics = load_json(
        ANALYTICS_FILE
    )


    distance_data = load_json(
        DISTANCES_FILE
    )


    distance_routes = (

        distance_data.get(
            "routes",
            {}
        )

        or {}

    )


    if not distance_routes:

        raise RuntimeError(
            "route_distances.json contains no route distances."
        )


    analytics_routes = (

        analytics.get(
            "routes",
            []
        )

        or []

    )


    enriched_count = 0


    # --------------------------------------------------------
    # ENRICH MAIN ROUTE LIST
    # --------------------------------------------------------

    for route in analytics_routes:

        route_key = str(

            route.get(
                "key",
                ""
            )

        ).strip()


        distance_record = (

            distance_routes.get(
                route_key
            )

        )


        if not distance_record:

            continue


        enrich_route(

            route,

            distance_record,

        )


        enriched_count += 1


    if enriched_count == 0:

        raise RuntimeError(
            "No analytics routes matched route_distances.json."
        )


    # --------------------------------------------------------
    # UPDATE CORE ROUTES FROM THE ENRICHED ROUTE OBJECTS
    #
    # This ensures both sections always contain
    # exactly the same distance data.
    # --------------------------------------------------------

    enriched_routes_by_key = {

        str(
            route.get(
                "key",
                ""
            )
        ).strip():

            route

        for route in analytics_routes

    }


    updated_core_routes = []


    for core_route in analytics.get(

        "core_routes",

        [],

    ):

        key = str(

            core_route.get(
                "key",
                ""
            )

        ).strip()


        enriched = (

            enriched_routes_by_key.get(
                key
            )

        )


        if enriched:

            updated_core_routes.append(
                enriched
            )

        else:

            updated_core_routes.append(
                core_route
            )


    analytics[
        "core_routes"
    ] = updated_core_routes


    # --------------------------------------------------------
    # TOP-LEVEL CONFIGURATION
    # --------------------------------------------------------

    analytics[
        "distance_analysis"
    ] = {

        "generated_on":
            date.today().isoformat(),

        "routes_with_distance":
            enriched_count,

        "distance_source":
            "OneMap",

        "distance_precision_km":
            distance_data.get(
                "distance_rounding_km",
                0.5,
            ),

        "cost_per_km_enabled":
            True,

        "note":
            (
                "Cost per kilometre is calculated from "
                "historical final fares divided by rounded "
                "driving distance. It should be used as an "
                "additional comparison signal rather than "
                "the sole fare predictor."
            ),

    }


    # --------------------------------------------------------
    # WRITE SAFELY
    #
    # Write to temporary file first,
    # then replace analytics.json.
    # --------------------------------------------------------

    temporary_file = (

        ANALYTICS_FILE
        .with_suffix(
            ".json.tmp"
        )

    )


    temporary_file.write_text(

        json.dumps(

            analytics,

            indent=2,

            ensure_ascii=False,

        )

        +

        "\n",

        encoding="utf-8",

    )


    # Validate newly generated JSON
    # before replacing the working file.

    json.loads(

        temporary_file.read_text(
            encoding="utf-8"
        )

    )


    temporary_file.replace(
        ANALYTICS_FILE
    )


    print(
        "========================================"
    )


    print(
        f"Successfully enriched "
        f"{enriched_count} routes."
    )


    print(
        "Distance and cost-per-km "
        "metrics added to analytics.json."
    )


    print(
        "========================================"
    )


if __name__ == "__main__":

    main()
