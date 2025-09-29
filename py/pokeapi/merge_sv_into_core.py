#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
merge_sv_into_core.py
---------------------
Fusionne un fichier sv_ptu (sortie de transform_sv_to_destination.py) avec un pokedex_core (7g, etc.).

Comportement:
- Mise en correspondance par "Species" (insensible à la casse/espaces/traits).
- Pour chaque entrée du core qui est trouvée dans sv_ptu:
  * Remplace entièrement **Base Stats** par ceux de sv_ptu.
  * Remplace entièrement **Moves** par un objet ne contenant QUE:
      - "Level Up Move List" (depuis sv_ptu)
      - "TM/Tutor Moves List" (depuis sv_ptu)
    => Toutes les anciennes sous-listes (Egg, Tutor, TM/HM, etc.) sont supprimées.
- Les autres champs du core sont préservés (Basic Information, Evolution, etc.).
- Les espèces présentes dans sv_ptu mais absentes du core sont ignorées (par défaut).
  Optionnel: --strict pour lever une erreur si des Species manquent.

Entrées attendues:
- sv_ptu.json: liste d'objets (ou {"results":[...]}), contenant:
    {
      "Species": "Bulbasaur",
      "Base Stats": {...},
      "Moves": {
        "Level Up Move List": [...],
        "TM/Tutor Moves List": [...]
      }
    }
- pokedex_core.json: typiquement une liste d'objets (chaque objet avec "Species").
  On supporte aussi un dict {Species: obj}.

Sortie:
- Un JSON du même "shape" que le core, avec Base Stats et Moves mis à jour.

Usage:
    python merge_sv_into_core.py --sv sv_ptu.json --core pokedex_core.json --out merged.json
    # Optionnel:
    python merge_sv_into_core.py --sv sv_ptu.json --core pokedex_core.json --out merged.json --strict
"""

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union


def normalize_species(s: str) -> str:
    if not isinstance(s, str):
        s = str(s or "")
    # minuscule + strip + remplacer espaces multiples par un seul, enlever points/quotes larges
    s = s.strip().lower()
    # commun pour PTU: remplacer espaces et underscores par tirets et aplatir doubles
    rep = s.replace("_", " ").replace("’", "'").replace("–", "-").replace("—", "-")
    rep = " ".join(rep.split())  # normalise espaces
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
    """
    Return (list_of_entries, was_dict)
    If input is dict {Species: obj}, convert to list but remember shape to restore if needed.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data, False
    elif isinstance(data, dict):
        # Detect {Species: obj}
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


def replace_stats_and_moves(core_obj: Dict[str, Any], sv_obj: Dict[str, Any]) -> None:
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


def merge_sv_into_core(sv_list: List[Dict[str, Any]], core_list: List[Dict[str, Any]], strict: bool = False):
    idx = index_sv(sv_list)

    matched = 0
    missing_in_sv: List[str] = []
    for entry in core_list:
        sp = entry.get("Species") or entry.get("species")
        key = normalize_species(sp) if sp else None
        if not key or key not in idx:
            missing_in_sv.append(sp or "<unknown>")
            continue
        sv_obj = idx[key]
        replace_stats_and_moves(entry, sv_obj)
        matched += 1

    if strict and missing_in_sv:
        missing_str = ", ".join(missing_in_sv[:10])
        raise RuntimeError(f"{len(missing_in_sv)} Species from core not found in sv: {missing_str}{' ...' if len(missing_in_sv) > 10 else ''}")

    report = {
        "core_count": len(core_list),
        "sv_count": len(sv_list),
        "matched": matched,
        "missing_in_sv": missing_in_sv,
    }
    return report


def restore_shape(core_list: List[Dict[str, Any]], was_dict: bool) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    if not was_dict:
        return core_list
    # convert back to {Species: obj}
    out: Dict[str, Any] = {}
    for obj in core_list:
        sp = obj.get("Species") or obj.get("species") or "Unknown"
        out[sp] = obj
    return out


def main():
    ap = argparse.ArgumentParser(description="Merge sv_ptu moves/stats into an existing core Pokédex JSON.")
    ap.add_argument("--sv", required=True, help="Path to sv_ptu.json (list or obj with results[])")
    ap.add_argument("--core", required=True, help="Path to pokedex_core.json (list or {Species: obj})")
    ap.add_argument("--out", required=True, help="Output JSON path")
    ap.add_argument("--strict", action="store_true", help="Fail if some core Species are not present in sv")
    args = ap.parse_args()

    sv_path = Path(args.sv)
    core_path = Path(args.core)
    out_path = Path(args.out)

    sv_list = load_sv(sv_path)
    core_list, was_dict = load_core(core_path)

    report = merge_sv_into_core(sv_list, core_list, strict=args.strict)

    out_data = restore_shape(core_list, was_dict)
    out_path.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Print a small report
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
