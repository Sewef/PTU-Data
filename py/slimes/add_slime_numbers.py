#!/usr/bin/env python3
"""Add a sequential Number field after Species in the Slime Rancher Pokédex."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "ptu" / "data" / "pokedex" / "fandex" / "pokedex_slimerancher.json"


def add_numbers(entries: list[dict]) -> list[dict]:
    numbered = []

    for number, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise TypeError(f"Entry {number} is not a JSON object")
        if "Species" not in entry:
            raise ValueError(f"Entry {number} has no Species field")

        reordered = {}
        for key, value in entry.items():
            if key == "Number":
                continue
            reordered[key] = value
            if key == "Species":
                reordered["Number"] = number
        numbered.append(reordered)

    return numbered


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()

    with args.path.open("r", encoding="utf-8-sig") as source:
        data = json.load(source)
    if not isinstance(data, list):
        raise TypeError("The Pokédex root must be a JSON array")

    numbered = add_numbers(data)
    temporary = args.path.with_suffix(args.path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as destination:
        json.dump(numbered, destination, ensure_ascii=False, indent=2)
        destination.write("\n")
    temporary.replace(args.path)

    print(f"Numbered {len(numbered)} entries from 1 to {len(numbered)} in {args.path}")


if __name__ == "__main__":
    main()
