from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date
from typing import Any, Iterable

import numpy as np

TIMING_MINIMUM_RELIABLE_SAMPLE = 5
CORE_ROUTE_KEYS = [
    "HOME__OFFICE",
    "OFFICE__HOME",
    "OFFICE__V_PLACE",
    "V_PLACE__HOME",
    "HOME__V_PLACE",
]


def _stats(values: Iterable[float]) -> dict[str, Any] | None:
    vals = np.array([float(v) for v in values], dtype=float)
    if len(vals) == 0:
        return None
    return {
        "count": int(len(vals)),
        "average": round(float(vals.mean()), 2),
        "median": round(float(np.median(vals)), 2),
        "min": round(float(vals.min()), 2),
        "max": round(float(vals.max()), 2),
        "p10": round(float(np.percentile(vals, 10)), 2),
        "p25": round(float(np.percentile(vals, 25)), 2),
        "p75": round(float(np.percentile(vals, 75)), 2),
        "p90": round(float(np.percentile(vals, 90)), 2),
    }


def _time_bucket(hour: int) -> str:
    if hour < 5:
        return "Overnight (00-05)"
    if hour < 7:
        return "Early morning (05-07)"
    if hour < 10:
        return "Morning peak (07-10)"
    if hour < 14:
        return "Midday (10-14)"
    if hour < 17:
        return "Afternoon (14-17)"
    if hour < 21:
        return "Evening (17-21)"
    return "Night (21-24)"


def _day_type(weekday: str) -> str:
    return "Weekend" if weekday in {"Saturday", "Sunday"} else "Weekday"


def _pricing_type(row: dict[str, Any]) -> str | None:
    explicit = str(row.get("pricing_type") or "").strip()
    if explicit:
        return explicit

    if row.get("provider") != "Grab" or row.get("category") != "ride":
        return None

    service = str(row.get("service") or row.get("raw_service") or "").upper()
    if "METERED" in service:
        return "Metered"
    if "PLUS" in service or "PREMIUM" in service:
        return "Premium"
    return "Fixed"


def _hour_key(row: dict[str, Any]) -> str:
    return f"{int(row.get('hour', 0)):02d}"


def _group_stats(rows: list[dict[str, Any]], key_fn) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        key = key_fn(row)
        if key is None or key == "":
            continue
        groups[str(key)].append(float(row["amount"]))
    return {key: _stats(vals) for key, vals in sorted(groups.items()) if vals}


def _timing_choice(grouped: dict[str, dict[str, Any]], label_fn) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    reliable = [
        (key, stats)
        for key, stats in grouped.items()
        if int(stats.get("count", 0)) >= TIMING_MINIMUM_RELIABLE_SAMPLE
    ]
    if not reliable:
        return None, None

    best_key, best_stats = min(reliable, key=lambda item: float(item[1]["average"]))
    worst_key, worst_stats = max(reliable, key=lambda item: float(item[1]["average"]))

    def pack(key: str, stats: dict[str, Any]) -> dict[str, Any]:
        return {"key": key, "label": label_fn(key), "stats": deepcopy(stats)}

    return pack(best_key, best_stats), pack(worst_key, worst_stats)


def _hour_label(key: str) -> str:
    return f"{key}:00–{key}:59"


def _looks_publishable_location(value: str) -> bool:
    text = str(value or "").strip().upper()
    if not text or text == "UNKNOWN":
        return False
    if len(text) > 80:
        return False
    # Common OCR-garbage hints from the original Grab statement.
    suspicious = [
        "SEMICONDUCTOR ,",
        "SEMICONDUCTOR .",
        "ADMIN IN BUILDING",
        "ADMIN ON BUILDING",
        "DINA MK",
        "GREMIEWEES",
        "IE APE",
        "INA MI",
        "INA.",
        "BUILDING, MICRON ASIA ADMIN",
    ]
    return not any(token in text for token in suspicious)


def _route_allowed(
    key: str,
    origin: str,
    destination: str,
    count: int,
    trusted_route_keys: set[str],
) -> bool:
    if key in trusted_route_keys:
        return True
    # New routes are automatically published only after repetition and when
    # both labels look clean. One-off journeys remain in the private master.
    return (
        count >= 2
        and _looks_publishable_location(origin)
        and _looks_publishable_location(destination)
    )


def _build_route(rows: list[dict[str, Any]], origin: str, destination: str) -> dict[str, Any]:
    overall = _stats(row["amount"] for row in rows)
    providers: dict[str, Any] = {}
    for provider in ("Grab", "Gojek"):
        provider_rows = [row for row in rows if row["provider"] == provider]
        if provider_rows:
            providers[provider] = _stats(row["amount"] for row in provider_rows)

    time_buckets = _group_stats(rows, lambda row: _time_bucket(int(row["hour"])))
    weekdays = _group_stats(rows, lambda row: row["weekday"])
    hourly = _group_stats(rows, _hour_key)
    day_types = _group_stats(rows, lambda row: _day_type(row["weekday"]))

    provider_hourly: dict[str, Any] = {}
    provider_weekdays: dict[str, Any] = {}
    provider_day_types: dict[str, Any] = {}
    for provider in providers:
        provider_rows = [row for row in rows if row["provider"] == provider]
        provider_hourly[provider] = _group_stats(provider_rows, _hour_key)
        provider_weekdays[provider] = _group_stats(provider_rows, lambda row: row["weekday"])
        provider_day_types[provider] = _group_stats(provider_rows, lambda row: _day_type(row["weekday"]))

    provider_comparison = None
    if "Grab" in providers and "Gojek" in providers:
        grab_average = float(providers["Grab"]["average"])
        gojek_average = float(providers["Gojek"]["average"])
        cheaper = "Grab" if grab_average < gojek_average else "Gojek"
        provider_comparison = {
            "cheaper": cheaper,
            "average_saving": round(abs(grab_average - gojek_average), 2),
            "grab_average": round(grab_average, 2),
            "gojek_average": round(gojek_average, 2),
        }

    reliable_buckets = [
        (name, stats)
        for name, stats in time_buckets.items()
        if int(stats["count"]) >= TIMING_MINIMUM_RELIABLE_SAMPLE
    ]
    best_time_bucket = (
        min(reliable_buckets, key=lambda item: float(item[1]["average"]))[0]
        if reliable_buckets
        else None
    )

    best_hour, worst_hour = _timing_choice(hourly, _hour_label)
    best_weekday, worst_weekday = _timing_choice(weekdays, lambda key: key)
    by_provider: dict[str, Any] = {}
    for provider, grouped in provider_hourly.items():
        p_best, p_worst = _timing_choice(grouped, _hour_label)
        by_provider[provider] = {"best_hour": p_best, "worst_hour": p_worst}

    grab_rows = [row for row in rows if row["provider"] == "Grab"]
    grab_services = _group_stats(grab_rows, lambda row: row.get("service") or "Standard")

    pricing_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in grab_rows:
        pricing = _pricing_type(row)
        if pricing:
            pricing_rows[pricing].append(row)

    grab_pricing_types = {
        pricing: _stats(row["amount"] for row in pricing_group)
        for pricing, pricing_group in sorted(pricing_rows.items())
    }
    grab_pricing_hourly = {
        pricing: _group_stats(pricing_group, _hour_key)
        for pricing, pricing_group in sorted(pricing_rows.items())
    }
    grab_pricing_weekdays = {
        pricing: _group_stats(pricing_group, lambda row: row["weekday"])
        for pricing, pricing_group in sorted(pricing_rows.items())
    }

    return {
        "key": f"{origin}__{destination}",
        "origin": origin,
        "destination": destination,
        "overall": overall,
        "providers": providers,
        "time_buckets": time_buckets,
        "weekdays": weekdays,
        "provider_comparison": provider_comparison,
        "best_time_bucket": best_time_bucket,
        "hourly": hourly,
        "provider_hourly": provider_hourly,
        "provider_weekdays": provider_weekdays,
        "provider_day_types": provider_day_types,
        "day_types": day_types,
        "timing_insights": {
            "minimum_reliable_sample": TIMING_MINIMUM_RELIABLE_SAMPLE,
            "best_hour": best_hour,
            "worst_hour": worst_hour,
            "best_weekday": best_weekday,
            "worst_weekday": worst_weekday,
            "by_provider": by_provider,
        },
        "grab_services": grab_services,
        "grab_pricing_types": grab_pricing_types,
        "grab_pricing_hourly": grab_pricing_hourly,
        "grab_pricing_weekdays": grab_pricing_weekdays,
    }


def _cost_per_km_stats(stats: dict[str, Any] | None, distance_km: float) -> dict[str, Any] | None:
    if not stats or distance_km <= 0:
        return None
    output = {"count": int(stats.get("count", 0))}
    for field in ("average", "median", "min", "max", "p10", "p25", "p75", "p90"):
        if stats.get(field) is not None:
            output[field] = round(float(stats[field]) / distance_km, 2)
    return output


def apply_distance_metrics(analytics: dict[str, Any], distance_data: dict[str, Any] | None) -> int:
    if not distance_data:
        return 0
    distance_routes = distance_data.get("routes", {}) or {}
    enriched = 0
    for route in analytics.get("routes", []):
        record = distance_routes.get(route["key"])
        if not record:
            continue
        distance_km = float(record.get("distance_km") or 0)
        if distance_km <= 0:
            continue

        route["distance"] = {
            "distance_km": distance_km,
            "route_type": record.get("route_type", "drive"),
            "source": record.get("source", "OneMap"),
            "distance_precision_km": record.get(
                "distance_precision_km",
                distance_data.get("distance_rounding_km", 0.5),
            ),
        }
        route["cost_per_km"] = {
            "overall": _cost_per_km_stats(route.get("overall"), distance_km),
            "providers": {
                provider: _cost_per_km_stats(stats, distance_km)
                for provider, stats in route.get("providers", {}).items()
            },
            "grab_pricing_types": {
                pricing: _cost_per_km_stats(stats, distance_km)
                for pricing, stats in route.get("grab_pricing_types", {}).items()
            },
        }
        enriched += 1

    routes_by_key = {route["key"]: route for route in analytics.get("routes", [])}
    analytics["core_routes"] = [
        deepcopy(routes_by_key[route["key"]]) if route.get("key") in routes_by_key else route
        for route in analytics.get("core_routes", [])
    ]
    analytics["distance_analysis"] = {
        "generated_on": date.today().isoformat(),
        "routes_with_distance": enriched,
        "distance_source": "OneMap",
        "distance_precision_km": distance_data.get("distance_rounding_km", 0.5),
        "cost_per_km_enabled": enriched > 0,
        "note": (
            "Cost per kilometre is calculated from historical final fares divided by rounded "
            "driving distance. It is an additional comparison signal, not the sole fare predictor."
        ),
    }
    return enriched


def build(
    transactions: list[dict[str, Any]],
    trusted_route_keys: set[str] | None = None,
    distance_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trusted_route_keys = set(trusted_route_keys or set())
    sgd = [row for row in transactions if row.get("currency") == "SGD"]
    rides = [row for row in sgd if row.get("category") == "ride"]
    all_rides = [row for row in transactions if row.get("category") == "ride"]
    foods = [row for row in sgd if row.get("category") == "food"]

    source_summary: dict[str, Any] = {}
    for provider in ("Grab", "Gojek"):
        rows = [row for row in transactions if row.get("provider") == provider]
        if not rows:
            continue
        dates = [str(row.get("date")) for row in rows if row.get("date")]
        source_summary[provider] = {
            "transactions": len(rows),
            "period": f"{min(dates)} to {max(dates)}" if dates else None,
            "sgd_total": round(sum(float(row["amount"]) for row in rows if row.get("currency") == "SGD"), 2),
            "myr_total": round(sum(float(row["amount"]) for row in rows if row.get("currency") == "MYR"), 2),
        }

    grab_sgd = [row for row in sgd if row.get("provider") == "Grab"]
    gojek_sgd = [row for row in sgd if row.get("provider") == "Gojek"]
    grab_myr = [row for row in transactions if row.get("provider") == "Grab" and row.get("currency") == "MYR"]

    summary = {
        "total_transactions": len(transactions),
        "ride_transactions": len(all_rides),
        "food_orders": len(foods),
        "total_spend_sgd": round(sum(float(row["amount"]) for row in sgd), 2),
        "ride_spend_sgd": round(sum(float(row["amount"]) for row in rides), 2),
        "food_spend_sgd": round(sum(float(row["amount"]) for row in foods), 2),
        "grab_spend_sgd": round(sum(float(row["amount"]) for row in grab_sgd), 2),
        "gojek_spend_sgd": round(sum(float(row["amount"]) for row in gojek_sgd), 2),
        "grab_myr_spend": round(sum(float(row["amount"]) for row in grab_myr), 2),
        "average_food_order": round(
            sum(float(row["amount"]) for row in foods) / len(foods), 2
        ) if foods else 0.0,
    }

    providers: dict[str, Any] = {}
    for provider in ("Grab", "Gojek"):
        rows = [row for row in sgd if row.get("provider") == provider]
        provider_rides = [row for row in rows if row.get("category") == "ride"]
        if not rows:
            continue
        providers[provider] = {
            "transactions": len(rows),
            "spend_sgd": round(sum(float(row["amount"]) for row in rows), 2),
            "rides": len(provider_rides),
            "ride_spend_sgd": round(sum(float(row["amount"]) for row in provider_rides), 2),
            "average_ride": round(
                sum(float(row["amount"]) for row in provider_rides) / len(provider_rides), 2
            ) if provider_rides else 0.0,
        }

    months = sorted({str(row["date"])[:7] for row in sgd if row.get("date")})
    monthly = []
    for month in months:
        grab_rides = sum(
            float(row["amount"])
            for row in sgd
            if str(row["date"]).startswith(month)
            and row.get("provider") == "Grab"
            and row.get("category") == "ride"
        )
        gojek_rides = sum(
            float(row["amount"])
            for row in sgd
            if str(row["date"]).startswith(month)
            and row.get("provider") == "Gojek"
            and row.get("category") == "ride"
        )
        grabfood = sum(
            float(row["amount"])
            for row in sgd
            if str(row["date"]).startswith(month)
            and row.get("category") == "food"
        )
        monthly.append({
            "month": month,
            "Grab rides": round(grab_rides, 2),
            "Gojek rides": round(gojek_rides, 2),
            "GrabFood": round(grabfood, 2),
            "total": round(grab_rides + gojek_rides + grabfood, 2),
        })

    route_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rides:
        origin = str(row.get("origin") or "UNKNOWN").strip()
        destination = str(row.get("destination") or "UNKNOWN").strip()
        route_groups[(origin, destination)].append(row)

    routes = []
    for (origin, destination), rows in route_groups.items():
        key = f"{origin}__{destination}"
        if _route_allowed(key, origin, destination, len(rows), trusted_route_keys):
            routes.append(_build_route(rows, origin, destination))
    routes.sort(key=lambda route: (-int(route["overall"]["count"]), route["key"]))

    routes_by_key = {route["key"]: route for route in routes}
    core_routes = [deepcopy(routes_by_key[key]) for key in CORE_ROUTE_KEYS if key in routes_by_key]

    restaurant_groups: dict[str, list[float]] = defaultdict(list)
    for row in foods:
        restaurant_groups[str(row.get("origin") or "UNKNOWN")].append(float(row["amount"]))
    top_restaurants = []
    for restaurant, vals in restaurant_groups.items():
        top_restaurants.append({
            "restaurant": restaurant,
            "count": len(vals),
            "total_spend": round(sum(vals), 2),
            "average_order": round(sum(vals) / len(vals), 2),
        })
    top_restaurants.sort(key=lambda item: (-item["count"], -item["total_spend"], item["restaurant"]))

    grab_ride_rows = [row for row in rides if row.get("provider") == "Grab"]
    service_groups: dict[str, list[float]] = defaultdict(list)
    pricing_groups: dict[str, list[float]] = defaultdict(list)
    for row in grab_ride_rows:
        service_groups[str(row.get("service") or "Standard")].append(float(row["amount"]))
        pricing = _pricing_type(row)
        if pricing:
            pricing_groups[pricing].append(float(row["amount"]))

    analytics = {
        "generated_on": date.today().isoformat(),
        "privacy_note": (
            "Only aggregated analytics are published. Raw reports, exact addresses, phone numbers, "
            "email addresses, booking codes and transaction-level timelines are not included in the website."
        ),
        "source_summary": source_summary,
        "summary": summary,
        "providers": providers,
        "monthly": monthly,
        "core_routes": core_routes,
        "routes": routes,
        "food": {
            "top_restaurants": top_restaurants,
            "order_count": len(foods),
            "total_spend_sgd": round(sum(float(row["amount"]) for row in foods), 2),
        },
        "analysis_config": {
            "timing_minimum_reliable_sample": TIMING_MINIMUM_RELIABLE_SAMPLE,
            "hourly_analysis_enabled": True,
            "provider_hourly_analysis_enabled": True,
            "weekday_analysis_enabled": True,
            "timing_fallback_order": [
                "route + Grab pricing type + hour",
                "route + provider + hour",
                "route + hour",
                "route + Grab pricing type + weekday",
                "route + provider + weekday",
                "route + weekday",
                "route + Grab pricing type",
                "route + provider",
                "route overall",
            ],
            "grab_service_analysis_enabled": True,
            "grab_pricing_type_analysis_enabled": True,
            "grab_pricing_type_groups": {
                "Fixed": ["Standard", "JustGrab", "Standard 4-seater"],
                "Metered": ["Metered Taxi"],
                "Premium": ["Standard Plus", "Premium"],
            },
        },
        "grab_service_summary": {
            service: _stats(vals) for service, vals in sorted(service_groups.items())
        },
        "grab_pricing_summary": {
            pricing: _stats(vals) for pricing, vals in sorted(pricing_groups.items())
        },
    }

    apply_distance_metrics(analytics, distance_data)
    return analytics


def find_unpublished_route_candidates(
    transactions: list[dict[str, Any]],
    trusted_route_keys: set[str] | None = None,
) -> list[dict[str, Any]]:
    trusted_route_keys = set(trusted_route_keys or set())
    groups: Counter[tuple[str, str]] = Counter()
    for row in transactions:
        if row.get("currency") != "SGD" or row.get("category") != "ride":
            continue
        origin = str(row.get("origin") or "UNKNOWN").strip()
        destination = str(row.get("destination") or "UNKNOWN").strip()
        key = f"{origin}__{destination}"
        if key in trusted_route_keys:
            continue
        groups[(origin, destination)] += 1

    output = []
    for (origin, destination), count in groups.most_common():
        key = f"{origin}__{destination}"
        if _route_allowed(key, origin, destination, count, trusted_route_keys):
            continue
        output.append({
            "key": key,
            "origin": origin,
            "destination": destination,
            "count": count,
            "reason": "one-off or location label needs review before public route analytics",
        })
    return output
