"""Recompute distance-derived fields without changing the historical refresh date."""
import json
from pathlib import Path
from build_analytics import apply_distance_metrics
from publication import public_analytics
from validate_public import validate


def main():
    path = Path("docs/data/analytics.json")
    analytics = json.loads(path.read_text())
    distances = json.loads(Path("config/route_distances.json").read_text())
    apply_distance_metrics(analytics, distances)
    analytics = public_analytics(analytics)
    validate(analytics)
    path.write_text(json.dumps(analytics, indent=2) + "\n")

if __name__ == "__main__":
    main()
