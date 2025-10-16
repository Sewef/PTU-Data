#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filter Level-Up moves in a PTU-style pokedex JSON.

Rules (applied in this order):
1) On an evolved Pokémon (stage > 1): if a move appears at level 1 AND also later (higher level) OR as Evo,
   remove its level-1 occurrence(s) for that move.
2) If a move has an Evo occurrence, remove all other level-up occurrences for that move (keep only Evo).
3) If a move is learned multiple times (still duplicates remaining), remove in priority entries whose Tags include "Legends: Arceus".
   (If the only entries are from Legends: Arceus, keep one for the next tie-break.)
4) If duplicates still remain, keep the one with the lowest level (Evo considered lower than any numeric level).

Usage:
    python filter_levelup_moves.py --in pokedex_core.json --out pokedex_core.filtered.json
"""

import argparse
import json
from typing import Any, Dict, List, Tuple, Optional

def is_evo_level(level: Any) -> bool:
    # Treat any non-int or string "Evo" (case-insensitive) as Evo marker
    if isinstance(level, int):
        return False
    if isinstance(level, str):
        return level.strip().lower() == "evo"
    return True  # unknown -> consider Evo-like for safety

def get_level_value(level: Any) -> int:
    # For comparisons; Evo is considered -1 (so it wins as "lowest")
    if is_evo_level(level):
        return -1
    try:
        return int(level)
    except Exception:
        return 999999

def stage_of_species(entry: Dict[str, Any]) -> Optional[int]:
    """Try to determine the evolution stage of this species.
    Prefer a top-level numeric field 'Stage' or 'Stade' if present.
    Otherwise, infer from the 'Evolution' array by matching the current Species name.
    Return None if unknown.
    """
    # Direct field (English or French)
    for key in ("Stage", "Stade"):
        val = entry.get(key)
        if isinstance(val, int):
            return val
        # Sometimes stored inside Basic Information
        bi = entry.get("Basic Information") or {}
        if isinstance(bi, dict):
            v2 = bi.get(key) or bi.get(key.capitalize())
            try:
                return int(v2)
            except Exception:
                pass

    # Infer from Evolution chain
    species_name = entry.get("Species")
    evo_list = entry.get("Evolution") or []
    if isinstance(evo_list, list) and species_name:
        for evo in evo_list:
            if not isinstance(evo, dict):
                continue
            if evo.get("Species") == species_name:
                st = evo.get("Stade") or evo.get("Stage")
                try:
                    return int(st)
                except Exception:
                    return None
    return None

def has_tag_larceus(tags: Any) -> bool:
    """Return True if tags include 'Legends: Arceus' (case-insensitive)."""
    if not tags or not isinstance(tags, list):
        return False
    for t in tags:
        if isinstance(t, str) and t.strip().lower() == "legends: arceus":
            return True
    return False

def filter_levelup(levelups: List[Dict[str, Any]], is_evolved: bool) -> List[Dict[str, Any]]:
    # Group entries by Move name
    by_move: Dict[str, List[Dict[str, Any]]] = {}
    for e in levelups:
        mv = e.get("Move")
        if not isinstance(mv, str):
            continue
        by_move.setdefault(mv, []).append(e)

    result: List[Dict[str, Any]] = []

    for move_name, entries in by_move.items():
        # Step 1: evolved species level-1 cull if later exists
        current = list(entries)
        if is_evolved:
            has_later_or_evo = any((isinstance(x.get("Level"), int) and x["Level"] > 1) or is_evo_level(x.get("Level")) for x in current)
            if has_later_or_evo:
                current = [x for x in current if not (x.get("Level") == 1)]

        if not current:
            continue

        # Step 2: if any Evo exists, keep only Evo occurrences
        evo_exists = any(is_evo_level(x.get("Level")) for x in current)
        if evo_exists:
            current = [x for x in current if is_evo_level(x.get("Level"))]

        if not current:
            continue

        # Step 3: if multiple remain, drop Legends: Arceus in priority (unless they are the only ones)
        if len(current) > 1:
            non_la = [x for x in current if not has_tag_larceus(x.get("Tags"))]
            if non_la:
                current = non_la  # drop all LA items

        # Step 4: if still multiple, keep the lowest level (Evo first)
        if len(current) > 1:
            current.sort(key=lambda x: (get_level_value(x.get("Level")), str(x.get("Move"))))
            current = [current[0]]

        result.extend(current)

    # Deterministic pretty order: Evo first, then by level asc, then by name
    result.sort(key=lambda x: (0 if is_evo_level(x.get("Level")) else 1, get_level_value(x.get("Level")), str(x.get("Move"))))
    return result

def process_pokedex(pokedex: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for entry in pokedex:
        moves_block = entry.get("Moves")
        if not isinstance(moves_block, dict):
            continue
        lvl_list = moves_block.get("Level Up Move List")
        if not isinstance(lvl_list, list) or not lvl_list:
            continue

        # Determine stage
        stage = stage_of_species(entry)
        is_evolved = (stage is not None and stage > 1)

        # Apply level-up filtering rules
        filtered = filter_levelup(lvl_list, is_evolved=is_evolved)

        # Final step: if evolved, transfer remaining Level 1 moves to Tutor Move List with Tags ["N"]
        if is_evolved:
            to_transfer = [x for x in filtered if x.get("Level") == 1]
            if to_transfer:
                # Remove them from Level Up
                filtered = [x for x in filtered if x.get("Level") != 1]
                # Ensure Tutor list exists
                tutor_list = moves_block.get("Tutor Move List")
                if not isinstance(tutor_list, list):
                    tutor_list = []
                # Build a set for dedupe by move name (case-insensitive)
                existing = { (d.get("Move","").strip().lower()) for d in tutor_list if isinstance(d, dict) }
                # Append transfers
                for e in to_transfer:
                    mv = (e.get("Move") or "").strip()
                    if not mv:
                        continue
                    key = mv.lower()
                    if key in existing:
                        # Find existing tutor entry and ensure it has tag "N"
                        for _t in tutor_list:
                            if isinstance(_t, dict) and (_t.get("Move") or "").strip().lower() == key:
                                tags = _t.get("Tags")
                                if isinstance(tags, list):
                                    if "N" not in tags:
                                        tags.append("N")
                                elif tags is None:
                                    _t["Tags"] = ["N"]
                                else:
                                    _t["Tags"] = ["N"]
                        continue
                    tutor_entry = {
                        "Move": mv,
                        "Type": e.get("Type"),
                        "Method": "Tutor",
                        "Tags": ["N"],
                    }
                    tutor_list.append(tutor_entry)
                    existing.add(key)
                # Optionally sort for stability
                tutor_list = sorted(tutor_list, key=lambda d: (d.get("Move") or ""))

                moves_block["Tutor Move List"] = tutor_list

        # Write back filtered level-up
        moves_block["Level Up Move List"] = filtered

    return pokedex

def main():
    ap = argparse.ArgumentParser(description="Filter Level-Up moves according to rules.")
    ap.add_argument("--in", dest="inp", required=True, help="Input pokedex JSON")
    ap.add_argument("--out", dest="out", required=True, help="Output path for filtered pokedex JSON")
    args = ap.parse_args()

    with open(args.inp, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise SystemExit("Input JSON must be an array of species objects.")

    processed = process_pokedex(data)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(processed, f, ensure_ascii=False, indent=2)

    print(f"Wrote filtered pokedex to: {args.out}")

if __name__ == "__main__":
    main()
