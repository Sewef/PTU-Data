#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
merge_sv_into_core_stone_rules.py
---------------------------------
Fusionne sv_ptu (sortie de transform_sv_to_destination.py) dans pokedex_core
ET applique des règles spéciales pour les évolutions par *Stone*.

Règles Stone (pour une espèce donnée dans le core) :
1) Si l'espèce est une évolution par Pierre (Condition contient "Stone", insensible à la casse) :
   a) Si sa "Level Up Move List" (dans sv_ptu) contient < 10 moves :
      → on **ajoute** à la Level Up Move List de l'espèce la **Level Up Move List du stade inférieur** (celui avec "Stade" - 1).
      → On le **notifie** sur stdout (espèce, nb moves ajoutés).
   b) Ensuite, **tous les moves (sauf 'Evo')** dont le niveau est **strictement inférieur** au
      **"Minimum Level"** de l'espèce (dans le core) sont **déplacés** de "Level Up Move List" vers
      "TM/Tutor Moves List", en **ajoutant ' (N)'** au nom.
      → On le **notifie** sur stdout (espèce, niveau min, nb moves déplacés).

Autres comportements (comme merge_sv_into_core.py) :
- Correspondance par "Species" (insensible à la casse/espaces/traits).
- Remplace entièrement **Base Stats**.
- Remplace **Moves** par un objet ne contenant QUE :
  "Level Up Move List" et "TM/Tutor Moves List".
- Préserve les autres champs du core (Basic Information, Evolution, etc.).
- Format du core accepté : liste d'objets (préféré) ou dict {Species: obj}.

Tri :
- Après ajouts/déplacements, on trie "Level Up Move List" : "Evo" d'abord, puis niveau croissant.
- "TM/Tutor Moves List" : tri alphabétique simple.

Utilisation :
    python merge_sv_into_core_stone_rules.py --sv sv_ptu.json --core pokedex_core.json --out merged.json
    # Optionnel: échouer si une espèce du core n’est pas dans sv_ptu
    python merge_sv_into_core_stone_rules.py --sv sv_ptu.json --core pokedex_core.json --out merged.json --strict
"""

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union


def normalize_species(s: str) -> str:
    if not isinstance(s, str):
        s = str(s or "")
    s = s.strip().lower()
    rep = s.replace("_", " ").replace("’", "'").replace("–", "-").replace("—", "-")
    rep = " ".join(rep.split())
    rep = rep.replace(" ", "-")
    return rep


def index_sv(sv_data: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    idx: Dict[str, Dict[str, Any]] = {}
    for o in sv_data:
        sp = o.get("Species") or o.get("species")
        if not sp:
            continue
        idx[normalize_species(sp)] = o
    return idx


def load_sv(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        return data["results"]
    if isinstance(data, list):
        return data
    raise ValueError("sv input must be a list or an object with 'results' list")


def load_core(path: Path) -> Tuple[List[Dict[str, Any]], bool]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data, False
    elif isinstance(data, dict):
        if all(isinstance(v, dict) for v in data.values()):
            lst = []
            for sp, obj in data.items():
                if isinstance(obj, dict) and "Species" not in obj:
                    obj = {**obj, "Species": sp}
                lst.append(obj)
            return lst, True
        else:
            raise ValueError("Unsupported core JSON shape. Expected list or {Species: obj} dict.")
    else:
        raise ValueError("Unsupported core JSON type.")


def parse_min_level(evo_entry: Dict[str, Any]) -> int | None:
    """
    evo_entry example:
      {"Stade": 3, "Species": "Poliwrath", "Condition": "Water Stone", "Minimum Level": "Lv 30 Minimum"}
    Return int level if found, else None.
    """
    txt = evo_entry.get("Minimum Level") or evo_entry.get("MinimumLevel") or evo_entry.get("Minimum") or ""
    if not isinstance(txt, str):
        return None
    m = re.search(r"(\d+)", txt)
    if m:
        return int(m.group(1))
    return None


def is_stone_evolution(evo_entry: Dict[str, Any]) -> bool:
    cond = evo_entry.get("Condition") or ""
    if not isinstance(cond, str):
        return False
    return "stone" in cond.lower()


def sort_level_up_list(lst: List[Dict[str, Any]]) -> None:
    lst.sort(key=lambda e: (0 if e.get("Level") == "Evo" else 1, e.get("Level") if isinstance(e.get("Level"), int) else 9999))


def merge_and_apply_stone_rules(core_obj: Dict[str, Any], sv_obj: Dict[str, Any], sv_index: Dict[str, Dict[str, Any]]) -> Tuple[int, int]:
    """
    Merge Base Stats + Moves, then if Stone evo and conditions met, enrich from parent and move low-level moves.
    Returns (added_from_parent_count, moved_below_min_count).
    """
    # Replace Base Stats
    sv_stats = deepcopy(sv_obj.get("Base Stats") or {})
    if not isinstance(sv_stats, dict):
        sv_stats = {}
    core_obj["Base Stats"] = sv_stats

    # Replace Moves with only the two lists
    sv_moves = sv_obj.get("Moves") or {}
    lvl = deepcopy(sv_moves.get("Level Up Move List") or [])
    tm  = deepcopy(sv_moves.get("TM/Tutor Moves List") or [])
    core_obj["Moves"] = {
        "Level Up Move List": lvl,
        "TM/Tutor Moves List": tm,
    }

    # Prepare evolution info from core
    evolution = core_obj.get("Evolution") or []
    if not isinstance(evolution, list) or not evolution:
        return (0, 0)

    # Find this species entry in Evolution
    this_sp = core_obj.get("Species") or core_obj.get("species") or ""
    # Try to locate row for this species (case-insensitive compare)
    this_row = None
    for row in evolution:
        if isinstance(row, dict) and normalize_species(row.get("Species", "")) == normalize_species(this_sp):
            this_row = row
            break
    if not this_row:
        return (0, 0)

    added_from_parent = 0
    moved_below_min = 0

    if is_stone_evolution(this_row):
        # Determine previous stage species (Stade - 1)
        try:
            stade = int(this_row.get("Stade"))
        except Exception:
            stade = None
        parent_species = None
        if stade and stade > 1:
            for row in evolution:
                try:
                    if int(row.get("Stade")) == (stade - 1):
                        parent_species = row.get("Species")
                        break
                except Exception:
                    continue

        # 1) If < 10 moves in Level Up, append parent's Level Up list
        if parent_species and len(core_obj["Moves"]["Level Up Move List"]) < 10:
            parent_key = normalize_species(parent_species)
            parent_sv = sv_index.get(parent_key)
            if parent_sv:
                parent_lvl = deepcopy((parent_sv.get("Moves") or {}).get("Level Up Move List") or [])
                core_obj["Moves"]["Level Up Move List"].extend(parent_lvl)
                added_from_parent = len(parent_lvl)
                print(f"[stone] {this_sp}: appended {added_from_parent} level-up moves from parent stage ({parent_species}).")
            else:
                print(f"[stone] {this_sp}: parent stage '{parent_species}' not found in sv_ptu, cannot append.", flush=True)

        # 2) Move moves below Minimum Level to TM/Tutor with (N)
        min_level = parse_min_level(this_row)
        if min_level is not None:
            new_level_up: List[Dict[str, Any]] = []
            moved_names: List[str] = []
            for m in core_obj["Moves"]["Level Up Move List"]:
                lvl_val = m.get("Level")
                if isinstance(lvl_val, int) and lvl_val < min_level:
                    name = m.get("Move")
                    if isinstance(name, str):
                        core_obj["Moves"]["TM/Tutor Moves List"].append(f"{name} (N)")
                        moved_names.append(name)
                    moved_below_min += 1
                    # exclude from level-up list
                else:
                    new_level_up.append(m)
            if moved_below_min:
                core_obj["Moves"]["Level Up Move List"] = new_level_up
                print(f"[stone] {this_sp}: moved {moved_below_min} moves below min level {min_level} -> TM/Tutor (N).")
        else:
            print(f"[stone] {this_sp}: no parsable 'Minimum Level' found; skip move relocation.", flush=True)

        # Finally: sort lists as per rules
        sort_level_up_list(core_obj["Moves"]["Level Up Move List"])
        core_obj["Moves"]["TM/Tutor Moves List"] = sorted(core_obj["Moves"]["TM/Tutor Moves List"])

    return (added_from_parent, moved_below_min)


def merge_all(sv_list: List[Dict[str, Any]], core_list: List[Dict[str, Any]], strict: bool = False) -> Dict[str, Any]:
    sv_index = index_sv(sv_list)

    matched = 0
    missing_in_sv: List[str] = []
    stone_reports: List[Dict[str, Any]] = []

    for entry in core_list:
        sp = entry.get("Species") or entry.get("species")
        key = normalize_species(sp) if sp else None
        if not key or key not in sv_index:
            missing_in_sv.append(sp or "<unknown>")
            continue
        sv_obj = sv_index[key]
        added, moved = merge_and_apply_stone_rules(entry, sv_obj, sv_index)
        matched += 1
        if added or moved:
            stone_reports.append({"Species": sp, "appended_from_parent": added, "moved_below_min": moved})

    if strict and missing_in_sv:
        missing_str = ", ".join(missing_in_sv[:10])
        raise RuntimeError(f"{len(missing_in_sv)} Species from core not found in sv: {missing_str}{' ...' if len(missing_in_sv) > 10 else ''}")

    report = {
        "core_count": len(core_list),
        "sv_count": len(sv_list),
        "matched": matched,
        "missing_in_sv": missing_in_sv,
        "stone_reports": stone_reports,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def restore_shape(core_list: List[Dict[str, Any]], was_dict: bool) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    if not was_dict:
        return core_list
    out: Dict[str, Any] = {}
    for obj in core_list:
        sp = obj.get("Species") or obj.get("species") or "Unknown"
        out[sp] = obj
    return out


def main():
    ap = argparse.ArgumentParser(description="Merge sv_ptu into core with Stone-evolution rules.")
    ap.add_argument("--sv", required=True, help="Path to sv_ptu.json (list or obj with results[])")
    ap.add_argument("--core", required=True, help="Path to pokedex_core.json (list or {Species: obj})")
    ap.add_argument("--out", required=True, help="Output JSON path")
    ap.add_argument("--strict", action="store_true", help="Fail if some core Species are not present in sv")
    args = ap.parse_args()

    sv_path = Path(args.sv); core_path = Path(args.core); out_path = Path(args.out)

    sv_list = load_sv(sv_path)
    core_list, was_dict = load_core(core_path)

    merge_all(sv_list, core_list, strict=args.strict)

    out_data = restore_shape(core_list, was_dict)
    out_path.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] wrote {out_path}")

if __name__ == "__main__":
    main()
