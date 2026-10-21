#!/usr/bin/env python3
"""Keep only explicitly allowed values in every ``Tags`` list of JSON files."""

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Set, Tuple


DEFAULT_ALLOWED_TAGS = ("N", "Stab")


def filter_tags(node: Any, allowed: Set[str]) -> Tuple[int, int]:
    """Mutate *node* recursively and return (fields changed, tags removed)."""
    fields_changed = 0
    tags_removed = 0

    if isinstance(node, dict):
        tags = node.get("Tags")
        if isinstance(tags, list):
            kept = []
            seen = set()
            for tag in tags:
                if isinstance(tag, str) and tag in allowed and tag not in seen:
                    kept.append(tag)
                    seen.add(tag)
            if kept != tags:
                node["Tags"] = kept
                fields_changed += 1
                tags_removed += len(tags) - len(kept)

        for value in node.values():
            changed, removed = filter_tags(value, allowed)
            fields_changed += changed
            tags_removed += removed

    elif isinstance(node, list):
        for value in node:
            changed, removed = filter_tags(value, allowed)
            fields_changed += changed
            tags_removed += removed

    return fields_changed, tags_removed


def iter_source_json(input_path: Path) -> Iterable[Path]:
    if input_path.is_file():
        yield input_path
        return
    for path in sorted(input_path.rglob("*.json")):
        if path.is_file() and not path.name.endswith(".min.json"):
            yield path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Filter every Tags list in JSON files to an explicit allow-list."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--allowed", nargs="+", default=list(DEFAULT_ALLOWED_TAGS))
    parser.add_argument("--inplace", action="store_true")
    args = parser.parse_args()

    if not args.input.exists():
        parser.error(f"Input does not exist: {args.input}")

    allowed = set(args.allowed)
    total_fields = 0
    total_removed = 0

    for path in iter_source_json(args.input):
        data = json.loads(path.read_text(encoding="utf-8"))
        fields_changed, tags_removed = filter_tags(data, allowed)
        total_fields += fields_changed
        total_removed += tags_removed

        if fields_changed and args.inplace:
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        print(
            f"{path}: fields changed={fields_changed}, tags removed={tags_removed}"
        )

    print(
        f"Done. Fields changed={total_fields}, tags removed={total_removed}, "
        f"allowed={sorted(allowed)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
