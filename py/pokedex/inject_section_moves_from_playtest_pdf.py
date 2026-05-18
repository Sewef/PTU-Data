#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Injecte les lignes de moves marquées par le symbole section (§) depuis
"1-6G Pokedex_Playtest105Plus.pdf" dans un fichier pokedex JSON.

Règle STAB:
- Si le move N'EST PAS de classe "status" (via PokeAPI)
- Et que le Type du move est dans les types du Pokémon
=> on ajoute le tag "Stab".

Format attendu des lignes PDF (exemples):
  § 31 Ancient Power - Rock
  §31  Ancient Power- Rock
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import requests
except ImportError as exc:
    raise SystemExit("Requires 'requests' (pip install requests)") from exc


SECTION_MOVE_RE = re.compile(r"^\s*§\s*(\d+)\s+(.+?)\s*-\s*([A-Za-z][A-Za-z ]*)\s*$")


def normalize_spaces(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("\u00A0", " ")
    value = re.sub(r"[\t ]+", " ", value)
    return value.strip()


def normalize_name_key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.replace("♀", " female ").replace("♂", " male ")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def slugify_move_name(move_name: str) -> str:
    value = unicodedata.normalize("NFKD", move_name)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().replace("'", "").replace("’", "")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value


def move_display_from_slug(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-"))


def canonical_type_name(type_name: str) -> str:
    cleaned = normalize_spaces(type_name)
    return cleaned.capitalize() if cleaned else cleaned


def make_session() -> requests.Session:
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=50, max_retries=0)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": "PTU-SectionMoveInjector/1.0"})
    return session


def http_get_json(session: requests.Session, url: str, tries: int = 3, backoff: float = 0.8) -> Optional[Dict[str, Any]]:
    last_error = ""
    for i in range(tries):
        try:
            response = session.get(url, timeout=25)
            if response.status_code == 200:
                return response.json()
            last_error = f"HTTP {response.status_code}"
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
        time.sleep(backoff * (i + 1))
    sys.stderr.write(f"[WARN] GET failed {url} -> {last_error}\n")
    return None


def extract_pdf_pages_text(pdf_path: Path) -> List[str]:
    # Try PyMuPDF first.
    try:
        import fitz  # type: ignore

        doc = fitz.open(str(pdf_path))
        pages = [normalize_spaces(page.get_text("text") or "") for page in doc]
        if any(page for page in pages):
            return pages
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"[INFO] PyMuPDF extraction failed: {exc}\n")

    # Fallback: PyPDF2.
    try:
        import PyPDF2  # type: ignore

        pages = []
        with pdf_path.open("rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                pages.append(normalize_spaces(page.extract_text() or ""))
        return pages
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Unable to extract text from PDF: {exc}") from exc


@dataclass
class ParsedSectionMove:
    page: int
    species: str
    form: Optional[str]
    level: int
    move_pdf_name: str
    move_type_pdf: str


def extract_species_map(pokedex: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    species_map: Dict[str, str] = {}
    for entry in pokedex:
        species = entry.get("Species")
        if isinstance(species, str) and species.strip():
            species_map[normalize_name_key(species)] = species
    return species_map


def extract_entries_by_species(pokedex: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for entry in pokedex:
        species = entry.get("Species")
        if isinstance(species, str) and species.strip():
            out.setdefault(species, []).append(entry)
    return out


def normalize_form_key(value: str) -> str:
    base = normalize_name_key(value)
    base = re.sub(r"\bforme?\b", "", base)
    base = re.sub(r"\s+", " ", base).strip()
    return base


def line_to_species_candidate(line: str) -> List[str]:
    src = normalize_spaces(line)
    if not src:
        return []

    variants = [src]
    variants.append(re.sub(r"^\s*#?\d{1,4}\s*[-.:)]?\s*", "", src))

    splitters = [" - ", " (", " [", " | "]
    extra_variants: List[str] = []
    for variant in variants:
        for splitter in splitters:
            if splitter in variant:
                extra_variants.append(variant.split(splitter, 1)[0].strip())
    variants.extend(extra_variants)

    out: List[str] = []
    for variant in variants:
        normalized = normalize_name_key(variant)
        if normalized and normalized not in out:
            out.append(normalized)
    return out


def detect_species_on_page(
    lines: Sequence[str],
    species_map: Dict[str, str],
    fallback_species: Optional[str] = None,
) -> Optional[str]:
    # We prioritize early lines where headings usually appear.
    for line in lines[:30]:
        candidates = line_to_species_candidate(line)
        for candidate in candidates:
            if candidate in species_map:
                return species_map[candidate]
    return fallback_species


def detect_form_on_page(lines: Sequence[str], entries_for_species: Sequence[Dict[str, Any]]) -> Optional[str]:
    if not entries_for_species:
        return None

    header_keys = [normalize_name_key(line) for line in lines[:6]]
    header_form_keys = [normalize_form_key(line) for line in lines[:6]]
    line_keys = [normalize_name_key(line) for line in lines[:40]]

    form_candidates: List[str] = []
    for entry in entries_for_species:
        form = entry.get("Form")
        if isinstance(form, str) and form.strip() and form not in form_candidates:
            form_candidates.append(form)

    # 1) Strong match in header lines with full form label.
    for form in form_candidates:
        form_key = normalize_name_key(form)
        if any(form_key and form_key in hk for hk in header_keys):
            return form

    # 2) Header fallback with compact form key (without "form/forme").
    # This stays limited to headers to avoid matching words like "Normal" in move text.
    for form in form_candidates:
        compact_form_key = normalize_form_key(form)
        if any(compact_form_key and compact_form_key in hfk for hfk in header_form_keys):
            return form

    # 3) Broad fallback with full form label only.
    for form in form_candidates:
        form_key = normalize_name_key(form)
        if any(form_key and form_key in lk for lk in line_keys):
            return form

    return None


def parse_section_lines_from_pdf_pages(
    pages: Sequence[str],
    species_map: Dict[str, str],
    entries_by_species: Dict[str, List[Dict[str, Any]]],
) -> Tuple[List[ParsedSectionMove], List[str]]:
    parsed: List[ParsedSectionMove] = []
    warnings: List[str] = []
    last_species: Optional[str] = None
    last_form: Optional[str] = None

    for idx, page_text in enumerate(pages, start=1):
        lines = [normalize_spaces(line) for line in (page_text or "").splitlines() if normalize_spaces(line)]
        if not lines:
            continue

        species = detect_species_on_page(lines, species_map, last_species)
        form: Optional[str] = None
        if species:
            entries_for_species = entries_by_species.get(species, [])
            if len(entries_for_species) > 1:
                form = detect_form_on_page(lines, entries_for_species)
                if not form and last_species == species:
                    form = last_form
                if not form:
                    warnings.append(f"Page {idx}: species '{species}' has multiple forms but none detected")
            last_species = species
            last_form = form

        for line in lines:
            match = SECTION_MOVE_RE.match(line)
            if not match:
                continue
            if not species:
                warnings.append(f"Page {idx}: section line found but species unresolved -> {line}")
                continue

            level = int(match.group(1))
            move_name = normalize_spaces(match.group(2))
            move_type = canonical_type_name(match.group(3))
            parsed.append(
                ParsedSectionMove(
                    page=idx,
                    species=species,
                    form=form,
                    level=level,
                    move_pdf_name=move_name,
                    move_type_pdf=move_type,
                )
            )
    return parsed, warnings


def fetch_move_payloads(session: requests.Session, move_names: Sequence[str], workers: int) -> Dict[str, Dict[str, Any]]:
    slugs = sorted({slugify_move_name(name) for name in move_names if slugify_move_name(name)})
    out: Dict[str, Dict[str, Any]] = {}

    def fetch_one(slug: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        data = http_get_json(session, f"https://pokeapi.co/api/v2/move/{slug}")
        return slug, data

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        future_map = {ex.submit(fetch_one, slug): slug for slug in slugs}
        for future in as_completed(future_map):
            slug, data = future.result()
            if data is not None:
                out[slug] = data

    return out


def ensure_levelup_list(species_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    moves = species_entry.setdefault("Moves", {})
    if not isinstance(moves, dict):
        species_entry["Moves"] = {}
        moves = species_entry["Moves"]
    levelup = moves.setdefault("Level Up Move List", [])
    if not isinstance(levelup, list):
        moves["Level Up Move List"] = []
        levelup = moves["Level Up Move List"]
    return levelup


def existing_display_move_name(levelup_list: Sequence[Dict[str, Any]], target_slug: str) -> Optional[str]:
    for item in levelup_list:
        if not isinstance(item, dict):
            continue
        name = item.get("Move")
        if isinstance(name, str) and slugify_move_name(name) == target_slug:
            return name
    return None


def is_duplicate_levelup_move(levelup_list: Sequence[Dict[str, Any]], level: int, move_slug: str) -> bool:
    for item in levelup_list:
        if not isinstance(item, dict):
            continue
        if item.get("Level") != level:
            continue
        move_name = item.get("Move")
        if isinstance(move_name, str) and slugify_move_name(move_name) == move_slug:
            return True
    return False


def insert_levelup_move(levelup_list: List[Dict[str, Any]], new_entry: Dict[str, Any]) -> None:
    """Insert after the last entry with the same level; otherwise append.

    This keeps existing ordering stable and avoids reshuffling the whole list.
    """
    level = new_entry.get("Level")
    last_same_level_index = -1
    for idx, entry in enumerate(levelup_list):
        if not isinstance(entry, dict):
            continue
        if entry.get("Level") == level:
            last_same_level_index = idx

    if last_same_level_index >= 0:
        levelup_list.insert(last_same_level_index + 1, new_entry)
    else:
        levelup_list.append(new_entry)


def inject_moves(
    pokedex: List[Dict[str, Any]],
    parsed_moves: Sequence[ParsedSectionMove],
    move_payloads: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    by_species: Dict[str, List[Dict[str, Any]]] = {}
    by_species_form: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for entry in pokedex:
        species = entry.get("Species")
        if isinstance(species, str):
            by_species.setdefault(species, []).append(entry)
            form = entry.get("Form")
            if isinstance(form, str) and form.strip():
                by_species_form[(species, form)] = entry

    added = 0
    duplicates = 0
    missing_species = 0
    ambiguous_species = 0
    missing_move_api = 0
    details: List[Dict[str, Any]] = []

    for item in parsed_moves:
        species_entry = None
        entries_for_species = by_species.get(item.species, [])
        if item.form:
            species_entry = by_species_form.get((item.species, item.form))
        if species_entry is None and len(entries_for_species) == 1:
            species_entry = entries_for_species[0]
        if species_entry is None and len(entries_for_species) > 1:
            no_form_entries = [e for e in entries_for_species if not isinstance(e.get("Form"), str) or not e.get("Form", "").strip()]
            if len(no_form_entries) == 1:
                species_entry = no_form_entries[0]
            else:
                ambiguous_species += 1
                details.append({
                    "status": "ambiguous_species_form",
                    "species": item.species,
                    "form": item.form,
                    "move": item.move_pdf_name,
                    "level": item.level,
                    "page": item.page,
                })
                continue

        if species_entry is None:
            missing_species += 1
            details.append({
                "status": "missing_species",
                "species": item.species,
                "form": item.form,
                "move": item.move_pdf_name,
                "level": item.level,
                "page": item.page,
            })
            continue

        levelup_list = ensure_levelup_list(species_entry)
        move_slug = slugify_move_name(item.move_pdf_name)
        if not move_slug:
            continue
        if is_duplicate_levelup_move(levelup_list, item.level, move_slug):
            duplicates += 1
            continue

        move_data = move_payloads.get(move_slug)
        if move_data is None:
            missing_move_api += 1

        damage_class = None
        api_type_name = None
        if move_data is not None:
            damage_class = ((move_data.get("damage_class") or {}).get("name") or "").lower()
            api_type_raw = ((move_data.get("type") or {}).get("name") or "").strip()
            api_type_name = api_type_raw.capitalize() if api_type_raw else None

        basic_info = species_entry.get("Basic Information") or {}
        pokemon_types = set()
        if isinstance(basic_info, dict):
            raw_types = basic_info.get("Type")
            if isinstance(raw_types, list):
                pokemon_types = {t for t in raw_types if isinstance(t, str)}

        chosen_type = api_type_name or item.move_type_pdf
        add_stab = bool(chosen_type in pokemon_types and damage_class != "status")

        display_name = existing_display_move_name(levelup_list, move_slug)
        if not display_name:
            if move_data and isinstance(move_data.get("name"), str):
                display_name = move_display_from_slug(move_data["name"])
            else:
                display_name = item.move_pdf_name

        new_entry: Dict[str, Any] = {
            "Level": item.level,
            "Move": display_name,
            "Type": chosen_type,
        }
        if add_stab:
            new_entry["Tags"] = ["Stab"]

        insert_levelup_move(levelup_list, new_entry)
        added += 1
        details.append({
            "status": "added",
            "species": item.species,
            "form": species_entry.get("Form"),
            "move": display_name,
            "level": item.level,
            "type": chosen_type,
            "stab": add_stab,
            "page": item.page,
        })

    return {
        "parsed_section_moves": len(parsed_moves),
        "added": added,
        "duplicates_skipped": duplicates,
        "missing_species": missing_species,
        "ambiguous_species_form": ambiguous_species,
        "missing_move_api": missing_move_api,
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Injecte les lignes § <niveau> <move> - <type> depuis le PDF vers un pokedex JSON."
    )
    parser.add_argument(
        "--pdf",
        default="py/1-6G Pokedex_Playtest105Plus.pdf",
        help="Chemin du PDF source.",
    )
    parser.add_argument(
        "--pokedex-in",
        default="ptu/data/pokedex/core/pokedex_core.json",
        help="Chemin du pokedex JSON en entrée.",
    )
    parser.add_argument(
        "--pokedex-out",
        default="ptu/data/pokedex/core/pokedex_core.with_section_moves.json",
        help="Chemin du pokedex JSON en sortie.",
    )
    parser.add_argument(
        "--report",
        default="py/pokedex/section_moves_injection_report.json",
        help="Chemin du rapport JSON.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Nombre de workers pour les appels PokeAPI.",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    pokedex_in = Path(args.pokedex_in)
    pokedex_out = Path(args.pokedex_out)
    report_path = Path(args.report)

    if not pdf_path.exists():
        raise SystemExit(f"[ERR] PDF not found: {pdf_path}")
    if not pokedex_in.exists():
        raise SystemExit(f"[ERR] Pokedex input not found: {pokedex_in}")

    with pokedex_in.open("r", encoding="utf-8") as f:
        pokedex = json.load(f)
    if not isinstance(pokedex, list):
        raise SystemExit("[ERR] pokedex-in must be a JSON array")

    species_map = extract_species_map(pokedex)
    entries_by_species = extract_entries_by_species(pokedex)

    pages = extract_pdf_pages_text(pdf_path)
    parsed_moves, parse_warnings = parse_section_lines_from_pdf_pages(pages, species_map, entries_by_species)

    session = make_session()
    move_payloads = fetch_move_payloads(session, [m.move_pdf_name for m in parsed_moves], workers=args.workers)

    inject_summary = inject_moves(pokedex, parsed_moves, move_payloads)

    pokedex_out.parent.mkdir(parents=True, exist_ok=True)
    with pokedex_out.open("w", encoding="utf-8") as f:
        json.dump(pokedex, f, ensure_ascii=False, indent=2)

    report = {
        "pdf": str(pdf_path),
        "pokedex_in": str(pokedex_in),
        "pokedex_out": str(pokedex_out),
        "pages_seen": len(pages),
        "warnings": parse_warnings,
        "summary": inject_summary,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(
        json.dumps(
            {
                "pages_seen": len(pages),
                "parsed_section_moves": inject_summary["parsed_section_moves"],
                "added": inject_summary["added"],
                "duplicates_skipped": inject_summary["duplicates_skipped"],
                "missing_species": inject_summary["missing_species"],
                "missing_move_api": inject_summary["missing_move_api"],
                "warnings": len(parse_warnings),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"Wrote pokedex output: {pokedex_out}")
    print(f"Wrote report: {report_path}")


if __name__ == "__main__":
    main()
