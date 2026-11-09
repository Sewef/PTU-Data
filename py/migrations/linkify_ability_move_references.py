"""One-shot migration for references inside Ability and Move data.

Dry-run by default. Pass --write to update the source JSON files. The migration
only scans descriptive fields; mechanical metadata such as Type, AC, Class,
Frequency, Range, and Damage Base is deliberately left untouched.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import linkify_feature_references as shared


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FILES = (
    REPO_ROOT / "ptu/data/abilities/abilities_core.json",
    REPO_ROOT / "ptu/data/abilities/abilities_community.json",
    REPO_ROOT / "ptu/data/abilities/abilities_homebrew.json",
    REPO_ROOT / "ptu/data/moves/moves_core.json",
    REPO_ROOT / "ptu/data/moves/moves_community.json",
    REPO_ROOT / "ptu/data/moves/moves_homebrew.json",
)
DESCRIPTIVE_FIELDS = {
    "Effect",
    "Bonus",
    "Special",
    "Trigger",
    "Target",
    "Description",
    "Note",
    "Keywords",
    "Keyword",
    "Range",
    "text",
}
LEADING_CUE_RE = re.compile(
    r"(?:\b(?:Move|Moves|Ability|Abilities|Capability|Capabilities|Status|"
    r"Item|Items|Keyword|Keywords|Connection)\s*(?:[-–—:]\s*)?|"
    r"\b(?:use|uses|used|using|learn|learns|know|knows|activate|activates|"
    r"gain|gains|grants?|become|becomes|becoming|inflict|inflicts)\s+)$",
    re.IGNORECASE,
)
FOLLOWING_CUE_RE = re.compile(
    r"^\s+(?:Move|Moves|Ability|Abilities|Capability|Capabilities|Status|"
    r"Condition|Item|Items|Keyword|Keywords)\b",
    re.IGNORECASE,
)
TYPE_CUE_RE = re.compile(
    r"\b(Move|Moves|Ability|Abilities|Capability|Capabilities|Status|Condition|"
    r"Item|Items|Keyword|Keywords|Feature|Features|Edge|Edges)\s*(?:[-–—:]\s*)?$",
    re.IGNORECASE,
)
FOLLOWING_TYPE_CUE_RE = re.compile(
    r"^\s+(Move|Moves|Ability|Abilities|Capability|Capabilities|Status|Condition|"
    r"Item|Items|Keyword|Keywords|Feature|Features|Edge|Edges)\b",
    re.IGNORECASE,
)
ACTION_LIST_CUE_RE = re.compile(
    r"\b(?:Moves|Abilities|Capabilities|Items|Keywords|uses?|using|learns?|knows?|hits?)\b"
    r"[^.;:\n]*$",
    re.IGNORECASE,
)
LIST_SEPARATOR_RE = re.compile(r"(?:,|\bor\b|\band\b)\s*$", re.IGNORECASE)
STOP_REFERENCES = {
    ("feature", "dance move"),
    ("feature", "status moves"),
    ("feature", "type booster"),
}
STATUS_LABEL_ALIASES = {
    "Asleep": "Sleep",
    "Badly Poisons": "Badly Poisoned",
    "Blinds": "Blindness",
    "Burns": "Burned",
    "Confused": "Confusion",
    "Confuses": "Confusion",
    "Curses": "Cursed",
    "Deadly Poisons": "Badly Poisoned",
    "Disables": "Disabled",
    "Enraged": "Rage",
    "Enrages": "Rage",
    "Flinched": "Flinch",
    "Flinches": "Flinch",
    "Freezes": "Frozen",
    "Infatuates": "Infatuation",
    "Paralyzed": "Paralysis",
    "Paralyzes": "Paralysis",
    "Poisons": "Poisoned",
    "Slows": "Slowed",
    "Suppresses": "Suppressed",
    "Traps": "Trapped",
    "Trips": "Tripped",
}
CONTEXT_STATUS_ALIASES = {
    "Burn": "Burned",
    "Poison": "Poisoned",
}
TYPE_CUE_MAP = {
    "move": "move",
    "moves": "move",
    "ability": "ability",
    "abilities": "ability",
    "capability": "capability",
    "capabilities": "capability",
    "status": "status",
    "condition": "status",
    "item": "item",
    "items": "item",
    "keyword": "keyword",
    "keywords": "keyword",
    "feature": "feature",
    "features": "feature",
    "edge": "edge",
    "edges": "edge",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Link references inside Ability and Move descriptions."
    )
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--audit-ambiguous", action="store_true")
    return parser.parse_args()


def source_type(path: Path) -> str:
    return "ability" if path.name.startswith("abilities_") else "move"


def build_indexes() -> dict[str, dict[str, str]]:
    feature_documents = [shared.load_json(path) for path in shared.DEFAULT_FILES]
    feature_index, _ = shared.build_name_index(feature_documents)
    return shared.build_all_reference_indexes(feature_index, shared.build_edge_index())


def should_link_single_word(before: str, after: str, full_value: str) -> bool:
    if LEADING_CUE_RE.search(before) or FOLLOWING_CUE_RE.search(after):
        return True
    if ACTION_LIST_CUE_RE.search(before) and LIST_SEPARATOR_RE.search(before):
        return True
    # Quoted names in rules text conventionally denote a named game entry.
    left_quote = before.endswith(('"', "'", "“"))
    right_quote = after.startswith(('"', "'", "”"))
    return left_quote and right_quote


def explicit_cue_type(before: str, after: str) -> str | None:
    match = TYPE_CUE_RE.search(before) or FOLLOWING_TYPE_CUE_RE.search(after)
    return TYPE_CUE_MAP.get(match.group(1).casefold()) if match else None


def linkify_status_aliases(value: str) -> str:
    pattern = re.compile(
        r"\b("
        + "|".join(
            map(re.escape, sorted(STATUS_LABEL_ALIASES, key=len, reverse=True))
        )
        + r")\b"
    )

    def replace_segment(segment: str) -> str:
        updated = pattern.sub(
            lambda match: (
                f"[[status:{STATUS_LABEL_ALIASES[match.group(0)]}]]"
                f"({match.group(0)})"
            ),
            segment,
        )
        contextual_pattern = re.compile(
            r"\b(" + "|".join(map(re.escape, CONTEXT_STATUS_ALIASES)) + r")\b"
        )

        def replace_contextual(match: re.Match[str]) -> str:
            before = updated[: match.start()]
            after = updated[match.end() :]
            if re.match(r"(?:-Type|\s+Type)\b", after, re.IGNORECASE):
                return match.group(0)
            if not re.search(
                r"(?:\bcure\b|\binflicts?\b|\bbecomes?\b|\bfrom\b|"
                r"\bcondition\b|\baffliction\b|\bsuch as\b)[^.;:\n]*$",
                before,
                re.IGNORECASE,
            ):
                return match.group(0)
            canonical = CONTEXT_STATUS_ALIASES[match.group(0)]
            return f"[[status:{canonical}]]({match.group(0)})"

        return contextual_pattern.sub(replace_contextual, updated)

    parts: list[str] = []
    cursor = 0
    for match in shared.PROTECTED_TEXT_RE.finditer(value):
        parts.append(replace_segment(value[cursor : match.start()]))
        parts.append(match.group(0))
        cursor = match.end()
    parts.append(replace_segment(value[cursor:]))
    return "".join(parts)


def choose_ambiguous_type(
    before: str,
    after: str,
    candidates: list[tuple[str, str]],
    field: str,
) -> tuple[str, str] | None:
    if field == "Range":
        return next(
            (candidate for candidate in candidates if candidate[0] == "keyword"),
            None,
        )
    cue_type = explicit_cue_type(before, after)
    if cue_type:
        return next((candidate for candidate in candidates if candidate[0] == cue_type), None)

    if re.search(
        r"\b(?:use|uses|used|using|learn|learns|know|knows|hits?|Move|Moves|Connection)\b"
        r"[^.;:\n]*$",
        before,
        re.IGNORECASE,
    ):
        move = next((candidate for candidate in candidates if candidate[0] == "move"), None)
        if move:
            return move

    if re.search(
        r"(?:\bbecomes?|\bwhile|\bimmune to|\bcured of|\bsuffering from|"
        r"\bafflicted with|\bStatus|\bCondition)\s+$|\bcure\b[^.;:\n]*$",
        before,
        re.IGNORECASE,
    ):
        status = next((candidate for candidate in candidates if candidate[0] == "status"), None)
        if status:
            return status

    if re.search(r"\bgrants?\s+$", before, re.IGNORECASE):
        capability = next(
            (candidate for candidate in candidates if candidate[0] == "capability"),
            None,
        )
        if capability:
            return capability

    return None


def linkify_ambiguous_text(
    value: str,
    field: str,
    current_type: str,
    current_name: str,
    pattern: re.Pattern[str],
    ambiguities: dict[str, list[tuple[str, str]]],
) -> str:
    fixed = {
        "frisk": "ability",
        "hidden power": "move",
        "leftovers": "item",
        "type brace": "item",
    }

    def replace_segment(segment: str) -> str:
        def replace(match: re.Match[str]) -> str:
            key = shared.normalized_key(match.group(0))
            candidates = ambiguities[key]
            choice = choose_ambiguous_type(
                segment[: match.start()],
                segment[match.end() :],
                candidates,
                field,
            )
            if not choice and key in fixed:
                choice = next(
                    (candidate for candidate in candidates if candidate[0] == fixed[key]),
                    None,
                )
            if not choice:
                return match.group(0)
            ref_type, canonical = choice
            if (
                ref_type == current_type
                and shared.normalized_key(canonical)
                == shared.normalized_key(current_name)
            ):
                return match.group(0)
            return f"[[{ref_type}:{canonical}]]"

        return pattern.sub(replace, segment)

    parts: list[str] = []
    cursor = 0
    for match in shared.PROTECTED_TEXT_RE.finditer(value):
        parts.append(replace_segment(value[cursor : match.start()]))
        parts.append(match.group(0))
        cursor = match.end()
    parts.append(replace_segment(value[cursor:]))
    return "".join(parts)


def linkify_text(
    value: str,
    field: str,
    current_type: str,
    current_name: str,
    pattern: re.Pattern[str],
    reference_index: dict[str, tuple[str, str]],
    ambiguity_pattern: re.Pattern[str],
    ambiguities: dict[str, list[tuple[str, str]]],
) -> str:
    value = shared.normalize_explicit_reference_targets(value)
    value = linkify_ambiguous_text(
        value,
        field,
        current_type,
        current_name,
        ambiguity_pattern,
        ambiguities,
    )

    def replace_segment(segment: str) -> str:
        def replace(match: re.Match[str]) -> str:
            ref_type, canonical = reference_index[shared.normalized_key(match.group(0))]
            if (ref_type, shared.normalized_key(canonical)) in STOP_REFERENCES:
                return match.group(0)
            if (
                ref_type == current_type
                and shared.normalized_key(canonical)
                == shared.normalized_key(current_name)
            ):
                return match.group(0)
            cue_type = explicit_cue_type(
                segment[: match.start()], segment[match.end() :]
            )
            if cue_type and cue_type != ref_type:
                return match.group(0)
            if (
                field == "Range"
                and ref_type != "keyword"
                and not (ref_type == "ability" and canonical == "Reckless")
            ):
                return match.group(0)
            if field == "Range":
                return f"[[{ref_type}:{canonical}]]"
            if field in {"Keyword", "Keywords"} and ref_type == "keyword":
                return f"[[{ref_type}:{canonical}]]"
            if ref_type == "status":
                return f"[[{ref_type}:{canonical}]]"
            if " " not in canonical and not should_link_single_word(
                segment[: match.start()], segment[match.end() :], value
            ):
                return match.group(0)
            return f"[[{ref_type}:{canonical}]]"

        return pattern.sub(replace, segment)

    parts: list[str] = []
    cursor = 0
    for match in shared.PROTECTED_TEXT_RE.finditer(value):
        parts.append(replace_segment(value[cursor : match.start()]))
        parts.append(match.group(0))
        cursor = match.end()
    parts.append(replace_segment(value[cursor:]))
    return linkify_status_aliases("".join(parts))


def migrate_document(
    document: Any,
    current_type: str,
    pattern: re.Pattern[str],
    reference_index: dict[str, tuple[str, str]],
    ambiguity_pattern: re.Pattern[str],
    ambiguities: dict[str, list[tuple[str, str]]],
) -> list[tuple[str, str, str]]:
    changes: list[tuple[str, str, str]] = []

    def visit(value: Any, path: str, current_name: str = "", field: str = "") -> None:
        if isinstance(value, list):
            for index, child in enumerate(value):
                child_name = current_name
                if isinstance(child, dict) and isinstance(child.get("Name"), str):
                    child_name = child["Name"]
                visit(child, f"{path}[{index}]", child_name, field)
            return
        if not isinstance(value, dict):
            return

        object_name = current_name
        if isinstance(value.get("Name"), str):
            object_name = value["Name"]
        for key, child in value.items():
            child_path = f"{path}.{key}"
            entry_name = object_name
            if current_type == "move" and path == "$" and isinstance(child, dict):
                entry_name = key
            if isinstance(child, str) and key in DESCRIPTIVE_FIELDS:
                updated = linkify_text(
                    child,
                    key,
                    current_type,
                    entry_name,
                    pattern,
                    reference_index,
                    ambiguity_pattern,
                    ambiguities,
                )
                if updated != child:
                    value[key] = updated
                    changes.append((child_path, child, updated))
            visit(value[key], child_path, entry_name, key)

    visit(document, "$")
    return changes


def main() -> int:
    args = parse_args()
    paths = [path.resolve() for path in args.files] if args.files else list(DEFAULT_FILES)
    missing = [path for path in paths if not path.is_file()]
    if missing:
        for path in missing:
            print(f"[ERROR] File not found: {path}", file=sys.stderr)
        return 1

    indexes = build_indexes()
    unique_index, ambiguities = shared.build_unique_global_index(indexes)
    reference_index = shared.build_autolink_index(unique_index)
    pattern = shared.compile_name_pattern(
        [name for _, name in reference_index.values()], flags=0
    )
    ambiguity_pattern = shared.compile_name_pattern(
        [name for values in ambiguities.values() for _, name in values], flags=0
    )
    print(
        f"Safe unique names: {len(reference_index)}; "
        f"ambiguous names skipped: {len(ambiguities)}"
    )

    documents = [shared.load_json(path) for path in paths]
    total = 0
    added: dict[str, int] = {}
    for path, document in zip(paths, documents):
        changes = migrate_document(
            document,
            source_type(path),
            pattern,
            reference_index,
            ambiguity_pattern,
            ambiguities,
        )
        total += len(changes)
        for _, before, after in changes:
            for ref_type in indexes:
                marker = f"[[{ref_type}:"
                delta = after.count(marker) - before.count(marker)
                if delta:
                    added[ref_type] = added.get(ref_type, 0) + delta
        print(f"{path.relative_to(REPO_ROOT)}: {len(changes)} change(s)")
        if not args.summary:
            for json_path, before, after in changes:
                print(f"  {json_path}")
                print(f"    - {before!r}")
                print(f"    + {after!r}")
        if args.write and changes:
            path.write_text(
                json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        if args.audit_ambiguous:
            occurrences = shared.find_ambiguous_occurrences(document, ambiguities)
            print(f"  ambiguous plain-text occurrences: {len(occurrences)}")
            if not args.summary:
                for json_path, context, candidates in occurrences:
                    options = ", ".join(
                        f"{ref_type}:{name}" for ref_type, name in candidates
                    )
                    print(f"    {json_path}: {context!r} => {options}")

    mode = "applied" if args.write else "proposed (dry run)"
    print(f"{total} safe change(s) {mode}.")
    if added:
        print(
            "Links added/corrected: "
            + ", ".join(f"{key}={value}" for key, value in sorted(added.items()))
        )
    if args.validate:
        counts, unresolved = shared.validate_explicit_references(documents, indexes)
        print(
            "Validated links: "
            + ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
        )
        if unresolved:
            for ref_type, target in unresolved:
                print(f"[ERROR] Unresolved: {ref_type}:{target}", file=sys.stderr)
            return 1
        print("All explicit links resolve to an exact indexed record.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
