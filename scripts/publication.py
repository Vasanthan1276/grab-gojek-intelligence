"""Public output policy, applied to new builds and existing aggregate migrations."""
from copy import deepcopy
from normalization import SAFE_LOCATIONS

MIN_PUBLIC_SAMPLE = 5

def _prune(value):
    if isinstance(value, dict):
        if "count" in value and any(k in value for k in ("median", "average", "total_spend")):
            if int(value.get("count") or 0) < MIN_PUBLIC_SAMPLE:
                return None
        output = {}
        for key, item in value.items():
            if key in {"min", "max"}:
                continue  # do not publish individual fare extremes
            clean = _prune(item)
            if clean is not None:
                output[key] = clean
        return output
    if isinstance(value, list):
        return [v for item in value if (v := _prune(item)) is not None]
    return value

def public_analytics(data):
    out = deepcopy(data)
    summary = out.get("summary", {})
    if int(summary.get("total_transactions", 0)) < MIN_PUBLIC_SAMPLE:
        for key in list(summary):
            if "spend" in key or "average" in key:
                summary.pop(key)
    if int(summary.get("food_orders", 0)) < MIN_PUBLIC_SAMPLE:
        summary.pop("food_spend_sgd", None)
        summary.pop("average_food_order", None)
        out["food"] = {"order_count": summary.get("food_orders", 0), "top_restaurants": []}
    for section in ("providers", "source_summary"):
        out[section] = {k:v for k,v in out.get(section, {}).items()
                        if int(v.get("transactions", 0)) >= MIN_PUBLIC_SAMPLE}
    for provider in out.get("providers", {}).values():
        if int(provider.get("rides", 0)) < MIN_PUBLIC_SAMPLE:
            provider.pop("average_ride", None)
            provider.pop("ride_spend_sgd", None)
    # Legacy monthly cells lack sample counts. Do not assume they are aggregates
    # of enough trips merely because the month total is large.
    monthly = []
    for month in out.get("monthly", []):
        if int(month.get("count", 0)) < MIN_PUBLIC_SAMPLE:
            continue
        for component in ("Grab rides", "Gojek rides", "GrabFood"):
            if int(month.get("component_counts", {}).get(component, 0)) < MIN_PUBLIC_SAMPLE:
                month.pop(component, None)
        monthly.append(month)
    out["monthly"] = monthly
    out["monthly_note"] = "Monthly detail is withheld unless source sample counts meet the public threshold; missing components are not zero."
    routes = []
    for route in out.get("routes", []):
        stops = route.get("stops") or [route.get("origin"), route.get("destination")]
        if not all(s in SAFE_LOCATIONS for s in stops):
            continue
        if int(route.get("overall", {}).get("count") or 0) < MIN_PUBLIC_SAMPLE:
            continue
        route.setdefault("journey_type", "stop_coverage_unknown")
        route.setdefault("date_range", None)
        route.setdefault("fare_basis", "statement_total_components_unavailable")
        route.pop("provider_comparison", None)  # mixed-service averages do not establish savings
        routes.append(route)
    out["routes"] = routes
    keys = {r["key"] for r in routes}
    out["core_routes"] = [deepcopy(r) for r in routes if r["key"] in
                          {c["key"] for c in out.get("core_routes", [])}]
    food = out.get("food", {})
    food["top_restaurants"] = [r for r in food.get("top_restaurants", [])
                               if r.get("restaurant") in SAFE_LOCATIONS]
    # Older aggregates lack currency sample counts; suppress non-SGD subtotals.
    out.get("summary", {}).pop("grab_myr_spend", None)
    for source in out.get("source_summary", {}).values():
        source.pop("myr_total", None)
        source.pop("sgd_total", None)
    out = _prune(out)
    out["privacy_policy"] = {"minimum_group_size": MIN_PUBLIC_SAMPLE,
        "note": "Small groups and fare extremes are withheld. Aggregates still describe personal habits; this is not guaranteed anonymity."}
    out["privacy_note"] = "Aggregated data only; approved place aliases, no raw receipts, exact addresses or trip timelines. Small groups withheld."
    out.setdefault("analysis_config", {})["timing_fallback_order"] = [
        "same provider/service + hour", "same provider/service + weekday", "same provider/service overall"]
    distance = out.setdefault("distance_analysis", {})
    distance["routes_with_distance"] = sum(bool(r.get("distance")) for r in out["routes"])
    distance["routes_without_distance"] = len(keys) - distance["routes_with_distance"]
    distance["note"] = "Fare divided by a rounded modelled driving distance, not measured trip distance or a fare prediction."
    return out
