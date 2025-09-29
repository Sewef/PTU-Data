#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
find_species_with_few_levelups.py
---------------------------------
Liste toutes les Species dont la "Level Up Move List" contient moins de N moves (défaut: 5).

Entrée attendue (sv_ptu) : résultat de transform_sv_to_destination.py
- JSON liste d'objets OU objet {"results":[...]}
- Chaque objet a la forme :
  {
    "Species": "Bulbasaur",
    "Base Stats": {...},
    "Moves": {
      "Level Up Move List": [...],
      "TM/Tutor Moves List": [...]
    }
  }

Sortie :
- Par défaut, affiche en stdout une liste triée par (count asc, Species).
- Optionnel: --out pour écrire un JSON avec
  [{"Species": "...", "count": 4}, ...]

Usage :
    python find_species_with_few_levelups.py --in sv_ptu.json
    python find_species_with_few_levelups.py --in sv_ptu.json --min 7 --out few_levelups.json
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def load_input(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        return data["results"]
    if isinstance(data, list):
        return data
    raise ValueError("Input must be a JSON list or an object with a 'results' list.")


def count_level_up_moves(poke: Dict[str, Any]) -> Tuple[str, int]:
    species = poke.get("Species") or poke.get("species") or "<Unknown>"
    moves = poke.get("Moves") or {}
    levelup = moves.get("Level Up Move List") or []
    return species, len(levelup)


def main():
    ap = argparse.ArgumentParser(description="Find species with fewer than N level-up moves.")
    ap.add_argument("--in", dest="infile", required=True, help="Path to sv_ptu.json")
    ap.add_argument("--min", dest="min_moves", type=int, default=5, help="Threshold N (default: 5)")
    ap.add_argument("--out", dest="outfile", help="Optional path to write JSON results")
    ap.add_argument("--only-stones", action="store_true", help="Ne lister que les espèces dont l'évolution utilise une Stone")

    args = ap.parse_args()

    inp = Path(args.infile)
    pokes = load_input(inp)

    few = []
    for p in pokes:
        sp, cnt = count_level_up_moves(p)

        if args.only_stones:
            evo_list = p.get("Evolution") or []
            # Chercher l'entrée de l'évolution qui correspond à l'espèce actuelle
            stone_user = False
            for evo in evo_list:
                if (evo.get("Species") or "").lower() == sp.lower():
                    cond = evo.get("Condition") or ""
                    if "stone" in cond.lower():
                        stone_user = True
                        break
            if not stone_user:
                continue  # ignorer si pas d'évolution par stone

        if cnt < args.min_moves:
            few.append({"Species": sp, "count": cnt})


    few.sort(key=lambda x: (x["count"], x["Species"]))

    if args.outfile:
        outp = Path(args.outfile)
        outp.write_text(json.dumps(few, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[ok] Wrote {outp} ({len(few)} species)")
    else:
        if not few:
            print("No species below threshold.")
            return
        print("Species with fewer than {} level-up moves:".format(args.min_moves))
        for item in few:
            print(f"- {item['Species']}: {item['count']}")

if __name__ == "__main__":
    main()
