"""One-shot migration for explicit data links in feature JSON files.

The script is a dry run unless --write is passed. It intentionally limits edits to
prerequisite fields and table cells so ordinary prose is not linkified by mistake.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
FEATURES_DIR = REPO_ROOT / "ptu" / "data" / "features"
DEFAULT_FILES = (
    FEATURES_DIR / "features_core.json",
    FEATURES_DIR / "features_homebrew.json",
)
EDGE_FILES = (
    REPO_ROOT / "ptu" / "data" / "edges" / "edges_core.json",
    REPO_ROOT / "ptu" / "data" / "edges" / "edges_homebrew.json",
)
REFERENCE_FILES = {
    "move": tuple((REPO_ROOT / "ptu" / "data" / "moves").glob("moves_*.json")),
    "ability": tuple((REPO_ROOT / "ptu" / "data" / "abilities").glob("abilities_*.json")),
    "capability": tuple((REPO_ROOT / "ptu" / "data" / "capabilities").glob("capabilities_*.json")),
    "status": (
        REPO_ROOT / "ptu" / "data" / "statuses" / "statuses_core.json",
        REPO_ROOT / "ptu" / "data" / "statuses" / "statuses_homebrew.json",
    ),
    "pokeedge": (
        REPO_ROOT / "ptu" / "data" / "pokeedges" / "pokeedges_core.json",
    ),
    "item": tuple((REPO_ROOT / "ptu" / "data" / "items").glob("items_*.json")),
    "keyword": tuple((REPO_ROOT / "ptu" / "data" / "moves").glob("keywords_*.json")),
}
NAME_FIELDS = {
    "move": ("Move", "Name"),
    "ability": ("Name",),
    "capability": ("Name",),
    "status": ("Name",),
    "pokeedge": ("Name",),
    "item": ("Name",),
    "keyword": ("Name",),
}
REFERENCE_TOKEN_RE = re.compile(r"\[\[[^\]]+\]\](?:\([^)]*\))?")
FEATURE_TOKEN_RE = re.compile(r"\[\[feature:([^\]]+)\]\]", re.IGNORECASE)
FEATURE_EDGE_TOKEN_RE = re.compile(
    r"\[\[(feature|edge):([^\]]+)\]\](?:\(([^)]*)\))?", re.IGNORECASE
)
TYPED_REFERENCE_TOKEN_RE = re.compile(
    r"\[\[(move|ability|capability|status|edge|pokeedge|item|feature|keyword):"
    r"([^\]]+)\]\](?:\(([^)]*)\))?",
    re.IGNORECASE,
)
PROTECTED_TEXT_RE = re.compile(
    r"\[\[[^\]]+\]\](?:\([^)]*\))?|<[^>]+>", re.IGNORECASE
)
NON_REFERENCE_SUFFIX_RE = re.compile(r"^\s+Skills?\b", re.IGNORECASE)
SKIP_AUTOLINK_FIELDS = {
    "Name",
    "Frequency",
    "Action",
    "Tags",
    "Class",
    "AC",
    "Range",
    "Damage Base",
}
AUTOLINK_STOP_NAMES = {
    # Skill names that collide with Moves, Abilities, or Capabilities.
    "acrobatics",
    "athletics",
    "charm",
    "command",
    "combat",
    "focus",
    "general education",
    "guile",
    "intimidate",
    "intuition",
    "medicine education",
    "occult education",
    "perception",
    "pokémon education",
    "stealth",
    "survival",
    "technology education",
    # Type names and action/frequency terms that collide with entries.
    "bug",
    "dark",
    "dragon",
    "electric",
    "fairy",
    "fighting",
    "fire",
    "flying",
    "ghost",
    "grass",
    "ground",
    "ice",
    "normal",
    "poison",
    "psychic",
    "rock",
    "steel",
    "water",
    "static",
    "swift",
    "bind",
    "round",
    "immunity",
}
REFERENCE_CUE_WORDS = {
    "Move",
    "Moves",
    "Ability",
    "Abilities",
    "Capability",
    "Capabilities",
    "Status",
    "Edge",
    "Edges",
    "Feature",
    "Features",
    "Item",
    "Items",
    "Keyword",
    "Keywords",
}

# Old hand-authored links sometimes use an inflected label as their target. Keep
# that label on screen, but point the token at the exact name in the data index.
REFERENCE_ALIASES: dict[tuple[str, str], str] = {
    ("item", "glue cannons"): "Glue Cannon",
    ("item", "hand nets"): "Hand Net",
    ("item", "heavy shields"): "Heavy Shield",
    ("item", "helmets"): "Helmet",
    ("item", "light shields"): "Light Shield",
    ("item", "weighted net"): "Weighted Nets",
    ("keyword", "blessings"): "Blessing",
    ("keyword", "coats"): "Coat",
    ("keyword", "priority (advanced)"): "Priority",
    ("status", "enraged"): "Rage",
    ("status", "flinched"): "Flinch",
    ("status", "paralyzed"): "Paralysis",
    ("status", "trip"): "Tripped",
}

# These targets have no corresponding record. They are equipment categories or
# combat terms, so retaining a clickable token would lead to an unrelated fuzzy
# match in the reference modal.
INVALID_REFERENCE_TARGETS = {
    ("item", "cap cannons"),
    ("item", "fine weapons"),
    ("item", "lasso"),
    ("item", "lassos"),
    ("item", "simple weapons"),
    ("status", "grappled"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add feature and edge reference links to feature JSON files."
    )
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Feature JSON files to update (defaults to core and homebrew).",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write changes. Without this flag, only print the proposed changes.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Only print change counts, not every proposed replacement.",
    )
    parser.add_argument(
        "--audit-ambiguous",
        action="store_true",
        help="Report unlinked occurrences whose name exists in multiple data types.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Fail if an explicit link does not target an exact indexed record.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def iter_feature_entries(document: Any):
    """Mirror collectFeatureEntries() from ptu_reference_modal.js."""

    def collect(feature: Any):
        if not isinstance(feature, dict) or not isinstance(feature.get("Name"), str):
            return
        yield feature
        for key, value in feature.items():
            if key.startswith("_") or key in {"moveTable", "abilityTable"}:
                continue
            if not isinstance(value, list):
                continue
            for child in value:
                if isinstance(child, dict) and child.get("Name"):
                    yield from collect(child)

    if not isinstance(document, dict):
        return
    for class_data in document.values():
        if not isinstance(class_data, dict):
            continue
        branches = class_data.get("branches", [])
        if not isinstance(branches, list):
            continue
        for branch in branches:
            if not isinstance(branch, dict):
                continue
            features = branch.get("features", [])
            if not isinstance(features, list):
                continue
            for feature in features:
                yield from collect(feature)


def normalized_key(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold().strip()


def build_name_index(documents: list[Any]) -> tuple[dict[str, str], list[str]]:
    variants: dict[str, set[str]] = {}
    for document in documents:
        for value in iter_feature_entries(document):
            name = unicodedata.normalize("NFC", value["Name"]).strip()
            if name:
                variants.setdefault(normalized_key(name), set()).add(name)

    ambiguous = [
        " / ".join(sorted(names))
        for names in variants.values()
        if len(names) > 1
    ]
    index = {
        key: sorted(names)[0]
        for key, names in variants.items()
        if len(names) == 1
    }
    return index, sorted(ambiguous)


def compile_name_pattern(
    names: list[str], flags: int = re.IGNORECASE
) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(name) for name in sorted(names, key=len, reverse=True))
    return re.compile(rf"(?<![\w])(?:{alternatives})(?![\w])", flags)


def build_edge_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for path in EDGE_FILES:
        if not path.is_file():
            continue
        data = load_json(path)
        if not isinstance(data, dict):
            continue
        for name in data:
            if isinstance(name, str) and name.strip():
                index.setdefault(normalized_key(name), name.strip())
    return index


def build_reference_index(
    feature_index: dict[str, str], edge_index: dict[str, str]
) -> dict[str, tuple[str, str]]:
    overlaps = feature_index.keys() & edge_index.keys()
    if overlaps:
        names = ", ".join(sorted(feature_index[key] for key in overlaps))
        raise ValueError(f"Names shared by features and edges: {names}")
    return {
        **{key: ("feature", name) for key, name in feature_index.items()},
        **{key: ("edge", name) for key, name in edge_index.items()},
    }


def iter_item_names(document: Any):
    if not isinstance(document, dict):
        return
    for category_data in document.values():
        if not isinstance(category_data, dict):
            continue
        for subcategory, entries in category_data.items():
            if subcategory == "_display" or not isinstance(entries, list):
                continue
            for item in entries:
                if isinstance(item, dict) and item.get("Name"):
                    yield str(item["Name"]).strip()


def iter_status_names(document: Any):
    if not isinstance(document, dict):
        return
    for entries in document.values():
        if not isinstance(entries, dict):
            continue
        for name in entries:
            if isinstance(name, str) and name.strip():
                yield name.strip()


def iter_generic_names(document: Any, ref_type: str):
    fields = NAME_FIELDS[ref_type]
    if isinstance(document, list):
        for item in document:
            if not isinstance(item, dict):
                continue
            name = next((item.get(field) for field in fields if item.get(field)), None)
            if name:
                yield str(name).strip()
        return
    if not isinstance(document, dict):
        return
    for fallback_name, value in document.items():
        if not isinstance(fallback_name, str):
            continue
        if isinstance(value, dict):
            name = next((value.get(field) for field in fields if value.get(field)), None)
            yield str(name or fallback_name).strip()
        else:
            yield fallback_name.strip()


def build_all_reference_indexes(
    feature_index: dict[str, str], edge_index: dict[str, str]
) -> dict[str, dict[str, str]]:
    indexes = {
        "feature": dict(feature_index),
        "edge": dict(edge_index),
    }
    for ref_type, paths in REFERENCE_FILES.items():
        index: dict[str, str] = {}
        for path in paths:
            if not path.is_file():
                continue
            document = load_json(path)
            if ref_type == "item":
                names = iter_item_names(document)
            elif ref_type == "status":
                names = iter_status_names(document)
            else:
                names = iter_generic_names(document, ref_type)
            for name in names:
                if name:
                    index.setdefault(normalized_key(name), name)
        indexes[ref_type] = index
    return indexes


def build_unique_global_index(
    indexes: dict[str, dict[str, str]]
) -> tuple[dict[str, tuple[str, str]], dict[str, list[tuple[str, str]]]]:
    candidates: dict[str, list[tuple[str, str]]] = {}
    for ref_type, index in indexes.items():
        for key, name in index.items():
            candidates.setdefault(key, []).append((ref_type, name))
    unique = {key: values[0] for key, values in candidates.items() if len(values) == 1}
    ambiguous = {key: values for key, values in candidates.items() if len(values) > 1}
    return unique, ambiguous


def build_autolink_index(
    unique_index: dict[str, tuple[str, str]]
) -> dict[str, tuple[str, str]]:
    return {
        key: reference
        for key, reference in unique_index.items()
        if key not in AUTOLINK_STOP_NAMES
        and not reference[1].strip().isdigit()
        and len(reference[1].strip()) >= 3
    }


def correct_mistyped_edge_tokens(
    value: str,
    feature_index: dict[str, str],
    edge_index: dict[str, str],
) -> str:
    def replace_token(match: re.Match[str]) -> str:
        key = normalized_key(match.group(1))
        if key in feature_index or key not in edge_index:
            return match.group(0)
        return f"[[edge:{edge_index[key]}]]"

    return FEATURE_TOKEN_RE.sub(replace_token, value)


def unwrap_feature_edge_tokens(value: str) -> str:
    return FEATURE_EDGE_TOKEN_RE.sub(
        lambda match: match.group(3) or match.group(2), value
    )


def replace_references_outside_tokens(
    value: str,
    name_pattern: re.Pattern[str],
    reference_index: dict[str, tuple[str, str]],
    protected_pattern: re.Pattern[str] = REFERENCE_TOKEN_RE,
) -> str:
    def replace_segment(segment: str) -> str:
        def replace_match(match: re.Match[str]) -> str:
            ref_type, canonical = reference_index[normalized_key(match.group(0))]
            # In phrases such as "Mentor Skill", the name describes a game term
            # rather than referring to the feature itself.
            if (
                ref_type == "feature"
                and NON_REFERENCE_SUFFIX_RE.match(segment[match.end() :])
            ):
                return match.group(0)
            return f"[[{ref_type}:{canonical}]]"

        return name_pattern.sub(replace_match, segment)

    parts: list[str] = []
    cursor = 0
    for match in protected_pattern.finditer(value):
        parts.append(replace_segment(value[cursor : match.start()]))
        parts.append(match.group(0))
        cursor = match.end()
    parts.append(replace_segment(value[cursor:]))
    return "".join(parts)


def linkify_structured_value(
    value: str,
    reference_pattern: re.Pattern[str],
    reference_index: dict[str, tuple[str, str]],
) -> str:
    plain = unwrap_feature_edge_tokens(value)
    return replace_references_outside_tokens(
        plain, reference_pattern, reference_index
    )


def linkify_table_cell(
    value: str, reference_index: dict[str, tuple[str, str]]
) -> str:
    value = unwrap_feature_edge_tokens(value)
    first_line, separator, remainder = value.partition("\n")
    reference = reference_index.get(normalized_key(first_line))
    if not reference:
        return value
    ref_type, canonical = reference
    suffix = f"{separator}{remainder}" if separator else ""
    return f"[[{ref_type}:{canonical}]]{suffix}"


def build_split_edge_repairs(
    feature_index: dict[str, str],
    edge_index: dict[str, str],
) -> list[tuple[re.Pattern[str], str]]:
    repairs: list[tuple[re.Pattern[str], str]] = []
    for feature_name in feature_index.values():
        prefix = f"{feature_name} "
        for edge_name in edge_index.values():
            if not edge_name.casefold().startswith(prefix.casefold()):
                continue
            remainder = edge_name[len(prefix) :]
            pattern = re.compile(
                rf"\[\[feature:{re.escape(feature_name)}\]\]\s+{re.escape(remainder)}(?![\w])",
                re.IGNORECASE,
            )
            repairs.append((pattern, f"[[edge:{edge_name}]]"))
    return repairs


def repair_split_edge_tokens(
    value: str, repairs: list[tuple[re.Pattern[str], str]]
) -> str:
    for pattern, replacement in repairs:
        value = pattern.sub(replacement, value)
    return value


def linkify_edges_in_text(
    value: str,
    edge_pattern: re.Pattern[str],
    edge_index: dict[str, str],
) -> str:
    def replace_segment(segment: str) -> str:
        def replace_match(match: re.Match[str]) -> str:
            canonical = edge_index[normalized_key(match.group(0))]
            before = segment[: match.start()]
            after = segment[match.end() :]

            # Avoid matching the last word of another named game entry, such as
            # the Grace Edge inside the Serene Grace Ability.
            if " " not in canonical and re.search(r"\b[A-Z][\w'-]*\s+$", before):
                return match.group(0)

            following_word = re.match(r"\s+([A-Z][\w'-]*)", after)
            if (
                " " not in canonical
                and following_word
                and following_word.group(1) not in REFERENCE_CUE_WORDS
            ):
                return match.group(0)

            # Here Field Clinic describes a physical location, not the Edge.
            if canonical == "Field Clinic" and re.search(r"\bin a\s+$", before):
                return match.group(0)

            return f"[[edge:{canonical}]]"

        return edge_pattern.sub(replace_match, segment)

    parts: list[str] = []
    cursor = 0
    for match in PROTECTED_TEXT_RE.finditer(value):
        parts.append(replace_segment(value[cursor : match.start()]))
        parts.append(match.group(0))
        cursor = match.end()
    parts.append(replace_segment(value[cursor:]))
    return "".join(parts)


def linkify_unique_references_in_text(
    value: str,
    reference_pattern: re.Pattern[str],
    reference_index: dict[str, tuple[str, str]],
) -> str:
    def replace_segment(segment: str) -> str:
        def replace_match(match: re.Match[str]) -> str:
            ref_type, canonical = reference_index[normalized_key(match.group(0))]
            before = segment[: match.start()]
            after = segment[match.end() :]

            if ref_type == "feature" and NON_REFERENCE_SUFFIX_RE.match(after):
                return match.group(0)

            # A single-word entry at the end of another capitalized name is
            # usually a different game entry (for example Grace in Serene Grace).
            if " " not in canonical and re.search(r"\b[A-Z][\w'-]*\s+$", before):
                return match.group(0)

            following_word = re.match(r"\s+([A-Z][\w'-]*)", after)
            if (
                " " not in canonical
                and following_word
                and following_word.group(1) not in REFERENCE_CUE_WORDS
            ):
                return match.group(0)

            if ref_type == "edge" and canonical == "Field Clinic" and re.search(
                r"\bin a\s+$", before
            ):
                return match.group(0)

            return f"[[{ref_type}:{canonical}]]"

        return reference_pattern.sub(replace_match, segment)

    parts: list[str] = []
    cursor = 0
    for match in PROTECTED_TEXT_RE.finditer(value):
        parts.append(replace_segment(value[cursor : match.start()]))
        parts.append(match.group(0))
        cursor = match.end()
    parts.append(replace_segment(value[cursor:]))
    return "".join(parts)


def choose_ambiguous_reference(
    name: str, before: str, after: str, segment: str, full_value: str
) -> tuple[str, str, str | None] | None:
    key = normalized_key(name)
    fixed: dict[str, tuple[str, str]] = {
        "aura reader": ("capability", "Aura Reader"),
        "commander": ("feature", "Commander"),
        "confusion": ("status", "Confusion"),
        "dancer": ("feature", "Dancer"),
        "fling": ("move", "Fling"),
        "frisk": ("ability", "Frisk"),
        "hidden power": ("move", "Hidden Power"),
        "leftovers": ("item", "Leftovers"),
        "mixed power": ("feature", "Mixed Power"),
        "powder": ("keyword", "Powder"),
        "type brace": ("item", "Type Brace"),
    }
    if key in fixed:
        ref_type, canonical = fixed[key]
        return ref_type, canonical, None

    if key == "focus":
        if re.search(r"(?:create|effect as)\s+a\s+$", before, re.IGNORECASE):
            return "item", "Focus", None
        return None

    if key == "rage":
        move_context = bool(
            re.search(r"(?:learns?|Moves?|Damage Rolls with)\s+$", before, re.IGNORECASE)
            or re.search(r"\blearns?\b", full_value, re.IGNORECASE)
            or re.search(r"\bDamage Rolls with\b", full_value, re.IGNORECASE)
            or re.search(r"\bMoves?\s+Rage\b", full_value)
        )
        return ("move", "Rage", None) if move_context else ("status", "Rage", None)

    if key == "illusion":
        if re.match(r"\s+Ability\b", after):
            return "ability", "Illusion", None
        if re.match(r"\s+keyword\b", after, re.IGNORECASE):
            return "keyword", "Illusion", None
        return None

    if key in {"telekinetic", "telepath"}:
        canonical = name.strip()
        if re.match(r"\s+Capability\b", after):
            return "capability", canonical, None
        if "Class Features" in full_value:
            return "feature", canonical, None
        return None

    if key == "aura pulse":
        if re.match(r"\s+Capability\b", after):
            return "capability", "Aura Pulse", None
        if "Poke Edges" in full_value or "Poké Edges" in full_value:
            return "pokeedge", "Aura Pulse", None
        return None

    if key == "dive":
        if "craft" in full_value.casefold() and "Balls" in full_value:
            return "item", "Dive Ball", "Dive"
        return "feature", "Dive", None

    return None


def linkify_ambiguous_references_in_text(
    value: str,
    ambiguity_pattern: re.Pattern[str],
) -> str:
    def replace_segment(segment: str) -> str:
        def replace_match(match: re.Match[str]) -> str:
            before = segment[: match.start()]
            after = segment[match.end() :]
            choice = choose_ambiguous_reference(
                match.group(0), before, after, segment, value
            )
            if not choice:
                return match.group(0)
            ref_type, canonical, label = choice
            token = f"[[{ref_type}:{canonical}]]"
            return f"{token}({label})" if label else token

        return ambiguity_pattern.sub(replace_match, segment)

    parts: list[str] = []
    cursor = 0
    for match in PROTECTED_TEXT_RE.finditer(value):
        parts.append(replace_segment(value[cursor : match.start()]))
        parts.append(match.group(0))
        cursor = match.end()
    parts.append(replace_segment(value[cursor:]))
    return "".join(parts)


def normalize_explicit_reference_targets(value: str) -> str:
    """Make existing tokens resolve to an exact record without changing prose."""

    def replace(match: re.Match[str]) -> str:
        ref_type = match.group(1).casefold()
        target = match.group(2).strip()
        explicit_label = match.group(3)
        key = (ref_type, normalized_key(target))

        if key in INVALID_REFERENCE_TARGETS:
            return explicit_label if explicit_label is not None else target

        canonical = REFERENCE_ALIASES.get(key)
        if canonical is None:
            return match.group(0)

        label = explicit_label if explicit_label is not None else target
        token = f"[[{ref_type}:{canonical}]]"
        return token if label == canonical else f"{token}({label})"

    return TYPED_REFERENCE_TOKEN_RE.sub(replace, value)


def validate_explicit_references(
    documents: list[Any], indexes: dict[str, dict[str, str]]
) -> tuple[dict[str, int], list[tuple[str, str]]]:
    counts = {ref_type: 0 for ref_type in indexes}
    unresolved: set[tuple[str, str]] = set()
    for document in documents:
        serialized = json.dumps(document, ensure_ascii=False)
        for match in TYPED_REFERENCE_TOKEN_RE.finditer(serialized):
            ref_type = match.group(1).casefold()
            target = match.group(2).strip()
            if normalized_key(target) in indexes[ref_type]:
                counts[ref_type] += 1
            else:
                unresolved.add((ref_type, target))
    return counts, sorted(unresolved)


def migrate_document(
    document: Any,
    feature_index: dict[str, str],
    edge_index: dict[str, str],
    reference_index: dict[str, tuple[str, str]],
    reference_pattern: re.Pattern[str],
    edge_pattern: re.Pattern[str],
    split_edge_repairs: list[tuple[re.Pattern[str], str]],
    global_reference_index: dict[str, tuple[str, str]],
    global_reference_pattern: re.Pattern[str],
    ambiguity_pattern: re.Pattern[str],
) -> list[tuple[str, str, str]]:
    changes: list[tuple[str, str, str]] = []

    def visit(value: Any, path: str = "$") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}"
                if isinstance(child, str) and key.endswith("Prerequisites"):
                    updated = linkify_structured_value(
                        child, reference_pattern, reference_index
                    )
                elif isinstance(child, str) and key == "text":
                    updated = linkify_table_cell(child, reference_index)
                else:
                    updated = child

                if isinstance(updated, str):
                    updated = normalize_explicit_reference_targets(updated)
                    updated = re.sub(
                        r"\[\[feature:Lessons\]\]\s+in Rage and Pain",
                        "[[feature:Lessons In Rage and Pain]]",
                        updated,
                        flags=re.IGNORECASE,
                    )
                    updated = repair_split_edge_tokens(updated, split_edge_repairs)
                    updated = correct_mistyped_edge_tokens(
                        updated, feature_index, edge_index
                    )
                    if key not in SKIP_AUTOLINK_FIELDS:
                        updated = linkify_edges_in_text(
                            updated, edge_pattern, edge_index
                        )
                        updated = linkify_unique_references_in_text(
                            updated,
                            global_reference_pattern,
                            global_reference_index,
                        )
                        updated = linkify_ambiguous_references_in_text(
                            updated, ambiguity_pattern
                        )

                if updated != child:
                    value[key] = updated
                    changes.append((child_path, child, updated))
                visit(value[key], child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    visit(document)
    return changes


def find_ambiguous_occurrences(
    document: Any,
    ambiguities: dict[str, list[tuple[str, str]]],
) -> list[tuple[str, str, list[tuple[str, str]]]]:
    names = sorted(
        {name for values in ambiguities.values() for _, name in values},
        key=len,
        reverse=True,
    )
    pattern = compile_name_pattern(names, flags=0)
    occurrences: list[tuple[str, str, list[tuple[str, str]]]] = []

    def visit(value: Any, path: str = "$") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "Name":
                    continue
                visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")
        elif isinstance(value, str):
            plain = PROTECTED_TEXT_RE.sub(" ", value)
            for match in pattern.finditer(plain):
                key = normalized_key(match.group(0))
                if key not in ambiguities:
                    continue
                start = max(0, match.start() - 55)
                end = min(len(plain), match.end() + 55)
                context = plain[start:end].replace("\n", " / ")
                occurrences.append((path, context, ambiguities[key]))

    visit(document)
    return occurrences


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    args = parse_args()
    paths = [path.resolve() for path in args.files] if args.files else list(DEFAULT_FILES)
    missing = [path for path in paths if not path.is_file()]
    if missing:
        for path in missing:
            print(f"[ERROR] File not found: {path}", file=sys.stderr)
        return 1

    documents = [load_json(path) for path in paths]
    name_index, ambiguous = build_name_index(documents)
    if ambiguous:
        print("Ambiguous names excluded from automatic linking:")
        for name in ambiguous:
            print(f"  - {name}")

    edge_index = build_edge_index()
    reference_index = build_reference_index(name_index, edge_index)
    reference_pattern = compile_name_pattern(
        [name for _, name in reference_index.values()]
    )
    # Prose linking is deliberately case-sensitive to avoid ordinary words.
    edge_pattern = compile_name_pattern(list(edge_index.values()), flags=0)
    split_edge_repairs = build_split_edge_repairs(name_index, edge_index)
    all_indexes = build_all_reference_indexes(name_index, edge_index)
    unique_global_index, global_ambiguities = build_unique_global_index(all_indexes)
    global_reference_index = build_autolink_index(unique_global_index)
    global_reference_pattern = compile_name_pattern(
        [name for _, name in global_reference_index.values()], flags=0
    )
    ambiguity_pattern = compile_name_pattern(
        [name for values in global_ambiguities.values() for _, name in values],
        flags=0,
    )
    print("Reference index:")
    for ref_type in sorted(all_indexes):
        print(f"  {ref_type}: {len(all_indexes[ref_type])}")
    print(f"  ambiguous names skipped: {len(global_ambiguities)}")
    print(f"  safe unique names used for autolinking: {len(global_reference_index)}")
    total = 0
    added_by_type: dict[str, int] = {}
    for path, document in zip(paths, documents):
        changes = migrate_document(
            document,
            name_index,
            edge_index,
            reference_index,
            reference_pattern,
            edge_pattern,
            split_edge_repairs,
            global_reference_index,
            global_reference_pattern,
            ambiguity_pattern,
        )
        total += len(changes)
        for _, before, after in changes:
            for ref_type in all_indexes:
                marker = f"[[{ref_type}:"
                delta = after.count(marker) - before.count(marker)
                if delta:
                    added_by_type[ref_type] = added_by_type.get(ref_type, 0) + delta
        print(f"\n{display_path(path)}: {len(changes)} change(s)")
        if not args.summary:
            for json_path, before, after in changes:
                print(f"  {json_path}")
                print(f"    - {before!r}")
                print(f"    + {after!r}")

        if args.write and changes:
            with path.open("w", encoding="utf-8") as handle:
                json.dump(document, handle, indent=2, ensure_ascii=False)

        if args.audit_ambiguous:
            occurrences = find_ambiguous_occurrences(document, global_ambiguities)
            print(f"  ambiguous plain-text occurrences: {len(occurrences)}")
            for json_path, context, candidates in occurrences:
                options = ", ".join(f"{kind}:{name}" for kind, name in candidates)
                print(f"    {json_path}: {context!r} => {options}")

    mode = "applied" if args.write else "proposed (dry run)"
    print(f"\n{total} safe change(s) {mode}.")
    if added_by_type:
        print(
            "Links added/corrected: "
            + ", ".join(
                f"{ref_type}={count}"
                for ref_type, count in sorted(added_by_type.items())
            )
        )
    if not args.write and total:
        print("Run again with --write to apply them.")
    if args.validate:
        counts, unresolved = validate_explicit_references(documents, all_indexes)
        print(
            "Validated links: "
            + ", ".join(
                f"{ref_type}={counts[ref_type]}" for ref_type in sorted(counts)
            )
        )
        if unresolved:
            print("Unresolved explicit links:", file=sys.stderr)
            for ref_type, target in unresolved:
                print(f"  - {ref_type}:{target}", file=sys.stderr)
            return 1
        print("All explicit links resolve to an exact indexed record.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
