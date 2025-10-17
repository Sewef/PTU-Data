#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audit evolved Pokémon (stage > 1) with fewer than N level-up moves.
Usage:
  python audit_evolved_low_levelup.py --pokedex /path/to/pokedex_core.json --threshold 10
"""
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

def parse_int(v, default=None) -> Optional[int]:
    try:
        return int(v)
    except Exception:
        return default

def get_stage_for_species(entry: Dict[str, Any]) -> Optional[int]:
    """Return the Stage/Stade value for this species from its Evolution list, if present."""
    species_name = entry.get("Species")
    evo_list = entry.get("Evolution") or []
    # Look for the row in Evolution where Species == this species (case-sensitive first, then fallback case-insensitive)
    match = None
    for row in evo_list:
        if row.get("Species") == species_name:
            match = row
            break
    if match is None:
        for row in evo_list:
            if isinstance(row.get("Species"), str) and isinstance(species_name, str) and row.get("Species","").lower() == species_name.lower():
                match = row
                break
    if match is None:
        return None
    # Stage/Stade might be under "Stade" (FR) or "Stage" (EN)
    stage = match.get("Stade", match.get("Stage"))
    return parse_int(stage)

def count_level_up_moves(entry: Dict[str, Any]) -> int:
    moves_block = entry.get("Moves") or {}
    level_list = moves_block.get("Level Up Move List") or []
    # If entries are dicts, count length; if malformed, try to coerce
    if isinstance(level_list, list):
        return len(level_list)
    return 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pokedex", required=True, help="Path to pokedex_core.json")
    ap.add_argument("--threshold", type=int, default=10, help="Max number of Level Up moves to flag (default 10)")
    args = ap.parse_args()

    p = Path(args.pokedex)
    data = json.loads(p.read_text(encoding="utf-8"))

    rows: List[Dict[str, Any]] = []
    for entry in data:
        stage = get_stage_for_species(entry)
        if stage is None or stage <= 1:
            continue  # only evolved (stage > 1)
        cnt = count_level_up_moves(entry)
        if cnt < args.threshold:
            rows.append({
                "Species": entry.get("Species"),
                "Stage": stage,
                "LevelUpCount": cnt
            })

    print(json.dumps(rows, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
