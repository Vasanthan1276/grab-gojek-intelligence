from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_ALIASES = ["HOME", "OFFICE", "V_PLACE", "COMPASSVALE"]


def prompt_fragments(alias: str) -> list[str]:
    print()
    print(f"{alias}")
    print("Enter one or more distinctive text fragments exactly as they commonly appear in your Grab/Gojek report.")
    print("Use commas between alternatives. The file stays local and is ignored by Git.")
    raw = input("Fragments (or press Enter to skip): ").strip()
    return [part.strip() for part in raw.split(",") if part.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="config/private_aliases.json")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    path = Path(args.output)
    if path.exists() and not args.force:
        print(f"{path} already exists. Nothing changed.")
        print("Run again with --force only if you intentionally want to recreate it.")
        return

    rules = []
    print("Private location alias setup")
    print("This creates a LOCAL file only. Do not commit it to the public repository.")
    for alias in DEFAULT_ALIASES:
        fragments = prompt_fragments(alias)
        if fragments:
            rules.append({"alias": alias, "contains": fragments})

    if not rules:
        raise RuntimeError("No private aliases were entered. The file was not created.")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"aliases": rules}, indent=2) + "\n", encoding="utf-8")
    print()
    print(f"Saved {len(rules)} private alias rules to {path}")
    print("This path is covered by .gitignore.")


if __name__ == "__main__":
    main()
