#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Folder-mode: merge pre-evo Level Up moves into stone-evolved species across all JSON pokedex files.
Then move Level 1 moves to Tutor with tag ["N"], and sort Level Up (Evo first, then by level).

Usage:
  python merge_stone_evo_levelups.py --input-dir /path/to/folder --in-place
  # or
  python merge_stone_evo_levelups.py --input-dir /path/to/folder --out-dir /path/to/output
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

def parse_int(v, default=None) -> Optional[int]:
    try:
        return int(v)
    except Exception:
        return default

def get_self_evo_row(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Find the row in Evolution where Species == this Species."""
    species = entry.get("Species")
    evo_list = entry.get("Evolution") or []
    for row in evo_list:
        if row.get("Species") == species:
            return row
    for row in evo_list:
        if isinstance(row.get("Species"), str) and isinstance(species, str) and row.get("Species","").lower() == species.lower():
            return row
    return None

def get_stage(row: Dict[str, Any]) -> Optional[int]:
    if not row:
        return None
    return parse_int(row.get("Stade", row.get("Stage")))


def condition_non_empty(row: Dict[str, Any]) -> bool:
    """Return True if the evolution 'Condition' field is present and non-empty (any non-empty value)."""
    if not row:
        return False
    val = row.get("Condition")
    if isinstance(val, str):
        return val.strip() != ""
    return bool(val)


def find_prev_stage_species(entry: Dict[str, Any], current_stage: int) -> Optional[str]:
    evo_list = entry.get("Evolution") or []
    target = current_stage - 1 if current_stage is not None else None
    # Prefer exact stage-1 match
    if target is not None:
        for row in evo_list:
            st = parse_int(row.get("Stade", row.get("Stage")))
            if st == target:
                return row.get("Species")
    # Fallback: pick any species with lower stage, prefer largest stage < current
    best = None
    best_stage = -1
    for row in evo_list:
        st = parse_int(row.get("Stade", row.get("Stage")))
        if st is not None and (current_stage is None or st < current_stage):
            if st > best_stage:
                best_stage = st
                best = row.get("Species")
    return best

def get_level_up_list(entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    moves = entry.get("Moves") or {}
    lst = moves.get("Level Up Move List") or []
    return lst if isinstance(lst, list) else []

def set_level_up_list(entry: Dict[str, Any], new_list: List[Dict[str, Any]]):
    moves = entry.setdefault("Moves", {})
    moves["Level Up Move List"] = new_list

def get_tutor_list(entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    moves = entry.get("Moves") or {}
    lst = moves.get("Tutor Move List") or []
    return lst if isinstance(lst, list) else []

def set_tutor_list(entry: Dict[str, Any], new_list: List[Dict[str, Any]]):
    moves = entry.setdefault("Moves", {})
    moves["Tutor Move List"] = new_list

def merge_levelups(base: List[Dict[str, Any]], to_add: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return base + new entries from to_add that are not exact (Move,Level) duplicates."""
    def key(e: Dict[str, Any]) -> Tuple[str, str]:
        move = (e.get("Move") or "").strip().lower()
        lvl = e.get("Level")
        lvl_str = str(lvl) if lvl is not None else ""
        return (move, lvl_str)
    seen = {key(e) for e in base}
    out = list(base)
    for e in to_add:
        k = key(e)
        if k not in seen:
            out.append(e)
            seen.add(k)
    return out

def move_level1_to_tutor(entry: Dict[str, Any]) -> bool:
    """
    Move Level==1 entries from Level Up Move List to Tutor Move List with tag ["N"].
    Returns True if any change was made.
    """
    lvl_list = get_level_up_list(entry)
    if not isinstance(lvl_list, list) or not lvl_list:
        return False

    keep = []
    moved = []
    for e in lvl_list:
        lvl = e.get("Level", None)
        is_one = (isinstance(lvl, int) and lvl == 1) or (isinstance(lvl, str) and str(lvl).strip() == "1")
        if is_one:
            tutor_entry = {
                "Move": e.get("Move"),
                "Type": e.get("Type"),
                "Method": "Tutor",
                "Tags": ["N"]
            }
            moved.append(tutor_entry)
        else:
            keep.append(e)

    if not moved:
        return False

    set_level_up_list(entry, keep)

    tutor_list = get_tutor_list(entry)
    seen = { (t.get("Move") or "").strip().lower() for t in tutor_list }
    for t in moved:
        key = (t.get("Move") or "").strip().lower()
        if key not in seen and t.get("Move"):
            tutor_list.append(t)
            seen.add(key)
    set_tutor_list(entry, tutor_list)
    return True

def sort_level_up_list(entry: Dict[str, Any]) -> bool:
    """
    Sort Level Up Move List: "Evo" entries first, then numeric levels ascending, then by Move name.
    Returns True if order changed.
    """
    lst = get_level_up_list(entry)
    if not isinstance(lst, list) or len(lst) < 2:
        return False

    def sort_key(e: Dict[str, Any]):
        move = (e.get("Move") or "")
        lvl = e.get("Level")
        # "Evo" first
        if isinstance(lvl, str) and str(lvl).strip().lower() == "evo":
            return (0, 0, move)
        # numeric next
        try:
            n = int(lvl)
            return (1, n, move)
        except Exception:
            return (2, 0, move)

    before = list(lst)
    lst_sorted = sorted(lst, key=sort_key)
    if lst_sorted != before:
        set_level_up_list(entry, lst_sorted)
        return True
    return False

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", required=True, help="Folder containing pokedex JSON files (non-recursive)")
    ap.add_argument("--out-dir", default=None, help="Output folder (same filenames). If omitted and not --in-place, defaults to in-place.")
    ap.add_argument("--in-place", action="store_true", help="Overwrite input files (ignores --out-dir)")
    ap.add_argument("--threshold", type=int, default=10, help="Only merge when evolved species has fewer than this many Level Up moves (default 10)")
    args = ap.parse_args()

    in_dir = Path(args.input_dir).expanduser()
    out_dir = Path(args.out_dir).expanduser() if (args.out_dir and not args.in_place) else None
    if not in_dir.is_dir():
        raise SystemExit(f"Input directory not found: {in_dir}")

    files = sorted([p for p in in_dir.iterdir() if p.suffix.lower() == ".json" and p.is_file()])
    if not files:
        raise SystemExit("No .json files found in input directory.")

    # Load all & build global index
    datasets: Dict[Path, List[Dict[str, Any]]] = {}
    global_index: Dict[str, Tuple[Path, Dict[str, Any]]] = {}
    for fp in files:
        try:
            data = load_json(fp)
        except Exception as e:
            print(f"[WARN] Skipping {fp.name}: {e}")
            continue
        if not isinstance(data, list):
            continue
        datasets[fp] = data
        for e in data:
            name = e.get("Species")
            if isinstance(name, str) and name not in global_index:
                global_index[name] = (fp, e)

    total_changed = 0
    species_updated = 0

    for fp, data in datasets.items():
        file_changed = False
        local_index = { (e.get("Species") if isinstance(e.get("Species"), str) else None): e for e in data }

        for entry in data:
            self_row = get_self_evo_row(entry)
            if not self_row:
                continue
            cur_stage = get_stage(self_row)
            if cur_stage is None or cur_stage <= 1:
                continue
            if not condition_non_empty(self_row):
                continue

            prev_species = find_prev_stage_species(entry, cur_stage)
            if not prev_species or not isinstance(prev_species, str):
                continue

            prev_entry = local_index.get(prev_species)
            if prev_entry is None:
                gi = global_index.get(prev_species)
                prev_entry = gi[1] if gi else None
            if prev_entry is None:
                continue

            # Only proceed if the evolved species has fewer than threshold Level Up moves
            cur_lvl = get_level_up_list(entry)
            changed_here = False
            if len(cur_lvl) < args.threshold:
                prev_lvl = get_level_up_list(prev_entry)
                merged = merge_levelups(cur_lvl, prev_lvl)
                if len(merged) != len(cur_lvl):
                    set_level_up_list(entry, merged)
                    changed_here = True

                if move_level1_to_tutor(entry):
                    changed_here = True
                if sort_level_up_list(entry):
                    changed_here = True

            if changed_here:
                file_changed = True
                species_updated += 1

        if file_changed:
            total_changed += 1
            if args.in_place or out_dir is None:
                save_json(fp, data)
            else:
                out_dir.mkdir(parents=True, exist_ok=True)
                save_json(out_dir / fp.name, data)

    print(f"Done. Files changed: {total_changed}. Species updated: {species_updated}.")

if __name__ == "__main__":
    main()
