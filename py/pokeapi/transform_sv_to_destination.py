#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Transform sv_all.json (produced by sv_moves_summary_async.py) to the user's destination format.

Rules (per user):
- Base Stats: base_stat / 10, rounding half up (0.5 -> up).  <-- set SCALE_DIVISOR below
- Moves:
  * "level-up" -> in "Level Up Move List" with {"Level": N | "Evo", "Move": name_en, "Type": TypeTitle}
    - If source has no level, use "Evo"
  * non "level-up" -> go to "TM/Tutor Moves List", keep ONLY the move name (use name_en)
  * If and only if stage > 0: all level-up moves with level == 1 are MOVED to TM/Tutor Moves List
    and we append " (N)" to the name. (Only keep the name as per TM/Tutor format.)
- Preserve original move order from sv_all.json when building lists.

Input:  a JSON file with {"results":[ ... species objects ... ]}  (or a plain list)
Output: a JSON array of destination Pokémon objects (one per species).
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

SCALE_DIVISOR = 10  # set to 100 if you truly want /100; /10 matches the sample provided

STAT_KEY_MAP = {
    "hp": "HP",
    "attack": "Attack",
    "defense": "Defense",
    "special-attack": "Special Attack",
    "special-defense": "Special Defense",
    "speed": "Speed",
}

def round_half_up(x: float) -> int:
    i = int(x)
    frac = x - i
    return i + (1 if frac >= 0.5 else 0)

def normalize_type(t: str | None) -> str | None:
    if t is None:
        return None
    return t[:1].upper() + t[1:].lower()

def transform_species(obj: Dict[str, Any]) -> Dict[str, Any]:
    species_name = obj.get("species") or obj.get("Species") or ""
    stage = obj.get("stage", 0)
    stats_in = obj.get("stats", {}) or {}

    # Base Stats transform
    base_stats: Dict[str, int] = {}
    for src_key, dest_key in STAT_KEY_MAP.items():
        val = stats_in.get(src_key)
        if isinstance(val, (int, float)):
            scaled = round_half_up(val / SCALE_DIVISOR)
            base_stats[dest_key] = int(scaled)

    # Moves transform
    level_up_list: List[Dict[str, Any]] = []
    tm_tutor_list: List[Dict[str, Any]] = []

    for m in obj.get("moves", []):
        method = m.get("method")
        move_name_en = m.get("name_en") or m.get("name")
        move_type = normalize_type(m.get("type"))
        level = m.get("level")

        if method == "level-up":
            if stage and level == 1:
                tm_tutor_list.append({
                "Move": move_name_en,
                "Type": move_type,
                "Method": "Level-Up",
                "Tags": ["N"]
            })
                continue

            entry: Dict[str, Any] = {
                "Level": level if isinstance(level, int) else "Evo",
                "Move": move_name_en,
            }
            if move_type is not None:
                entry["Type"] = move_type
            level_up_list.append(entry)
        else:
            tm_tutor_list.append({
            "Move": move_name_en,
            "Type": move_type,
            "Method": (method.capitalize() if method and method != "level-up" else "Level-Up"),
            "Tags": []
        })

        # Sort level-up moves (Evo first, then by level ascending)
    level_up_list.sort(
        key=lambda e: (
            0 if e["Level"] == "Evo" else 1,
            e["Level"] if isinstance(e["Level"], int) else 9999,
        )
    )

    # Sort TM/Tutor alphabetically by Move
    tm_tutor_list.sort(key=lambda e: e["Move"].lower())

    # Sort TM/Tutor list alphabetically
    tm_tutor_list = sorted(tm_tutor_list, key=lambda e: (e["Move"].lower() if isinstance(e, dict) else str(e).lower()))

    # Build Other Information with Genders string
    gd = obj.get("gender_distribution")
    genders_str = "Genderless"
    try:
        if isinstance(gd, dict):
            male = gd.get("male")
            female = gd.get("female")
            genderless = gd.get("genderless")
            if isinstance(genderless, (int, float)) and float(genderless) >= 1.0:
                genders_str = "Genderless"
            elif isinstance(male, (int, float)) and isinstance(female, (int, float)):
                m_pct = round(float(male) * 100.0, 1)
                f_pct = round(float(female) * 100.0, 1)
                genders_str = f"{m_pct}% Male / {f_pct}% Female"
    except Exception:
        genders_str = "Genderless"

    other_info = {
        "Genders": genders_str
    }

    dest = {
        "Species": species_name[:1].upper() + species_name[1:],
        "Base Stats": base_stats,
        "Other Information": other_info,
        "Moves": {
            "Level Up Move List": level_up_list,
            "TM/Tutor Moves List": tm_tutor_list,
        },
    }
    return dest


def load_input(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "results" in data and isinstance(data["results"], list):
        return data["results"]
    if isinstance(data, list):
        return data
    raise ValueError("Input must be a JSON list or an object with a 'results' list.")

def main():
    ap = argparse.ArgumentParser(description="Transform sv_all.json to destination format.")
    ap.add_argument("--in", dest="infile", required=True, help="Path to sv_all.json (JSON list or object with results[])")
    ap.add_argument("--out", dest="outfile", required=True, help="Output JSON path.")
    args = ap.parse_args()

    inp = Path(args.infile)
    outp = Path(args.outfile)

    species_list = load_input(inp)
    transformed = [transform_species(sp) for sp in species_list]

    outp.write_text(json.dumps(transformed, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] Wrote {outp} ({len(transformed)} species)")

if __name__ == "__main__":
    main()