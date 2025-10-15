#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Version optimisée avec appels parallèles vers PokeAPI
Extraction des moves supprimés entre deux générations (7/8/9).
"""

import argparse
import csv
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Set, Tuple

import requests

POKEAPI_BASE_POKEMON = "https://pokeapi.co/api/v2/pokemon"
TIMEOUT = 30

# préréglages de version groups par génération
DEFAULT_GROUPS_BY_GEN = {
    7: ["ultra-sun-ultra-moon"],
    8: ["sword-shield"],
    9: ["scarlet-violet"],
}

def fetch_json(url: str) -> dict:
    r = requests.get(url, timeout=TIMEOUT)
    if r.status_code == 404:
        raise ValueError(f"Ressource non trouvée: {url}")
    r.raise_for_status()
    return r.json()

def list_all_pokemon_names(limit: int = None) -> List[str]:
    url = f"{POKEAPI_BASE_POKEMON}?limit=20000"
    data = fetch_json(url)
    results = data.get("results", [])
    names = [it["name"] for it in results]
    if limit is not None:
        names = names[:limit]
    return names

def fetch_pokemon_data(name: str) -> dict:
    url = f"{POKEAPI_BASE_POKEMON}/{name}"
    return fetch_json(url)

def extract_level_up_moves(data: dict, version_groups: Set[str]) -> Dict[str, int]:
    """Retourne {move: min_level} pour les moves appris par level-up."""
    result: Dict[str, int] = {}
    for move_entry in data.get("moves", []):
        move_name = move_entry["move"]["name"]
        for vgd in move_entry.get("version_group_details", []):
            vg_name = vgd["version_group"]["name"]
            if vg_name not in version_groups:
                continue
            if vgd["move_learn_method"]["name"] != "level-up":
                continue
            lvl = vgd.get("level_learned_at", 0)
            result[move_name] = min(result.get(move_name, lvl), lvl)
    return result

def compute_removed_moves_for_pokemon(
    name: str, 
    include_forms: bool,
    left_groups: Set[str], 
    right_groups: Set[str]
) -> Tuple[str, List[Tuple[str, int]]]:
    """
    Récupère un Pokémon et renvoie (name, [(move, lvl_left), ...]) pour les moves supprimés.
    """
    try:
        data = fetch_pokemon_data(name)
    except Exception as e:
        return name, [("__ERROR__", str(e))]

    if not include_forms and data.get("is_default") is False:
        return name, []  # ignoré

    left_map = extract_level_up_moves(data, left_groups)
    right_map = extract_level_up_moves(data, right_groups)
    removed = [(m, lvl) for m, lvl in left_map.items() if m not in right_map]
    return data["name"], removed

def humanize_move(m: str) -> str:
    return m.replace('-', ' ').title()

def main():
    parser = argparse.ArgumentParser(description="Compare toutes les moves supprimées entre deux générations via PokeAPI (parallèle)")
    parser.add_argument("--left-gen", type=int, choices=[7, 8, 9], default=7)
    parser.add_argument("--right-gen", type=int, choices=[7, 8, 9], default=8)
    parser.add_argument("--left-groups", nargs="+")
    parser.add_argument("--right-groups", nargs="+")
    parser.add_argument("--gen7-groups", nargs="+")
    parser.add_argument("--gen8-groups", nargs="+")
    parser.add_argument("--gen9-groups", nargs="+")
    parser.add_argument("--include-forms", action="store_true")
    parser.add_argument("--max", type=int)
    parser.add_argument("--out", default="removed_moves_parallel.csv")
    parser.add_argument("--aggregate-out", default=None)
    parser.add_argument("--workers", type=int, default=10, help="Nombre de threads parallèles (défaut: 10)")
    args = parser.parse_args()

    # config groupes
    groups_by_gen = DEFAULT_GROUPS_BY_GEN.copy()
    if args.gen7_groups: groups_by_gen[7] = args.gen7_groups
    if args.gen8_groups: groups_by_gen[8] = args.gen8_groups
    if args.gen9_groups: groups_by_gen[9] = args.gen9_groups

    left_groups = set(args.left_groups or groups_by_gen[args.left_gen])
    right_groups = set(args.right_groups or groups_by_gen[args.right_gen])
    left_label = f"Gen{args.left_gen} ({'/'.join(left_groups)})"
    right_label = f"Gen{args.right_gen} ({'/'.join(right_groups)})"

    print(f"[INFO] Comparaison : {left_label} → {right_label}")

    # Liste des Pokémon
    names = list_all_pokemon_names(limit=args.max)
    print(f"[INFO] Total Pokémon récupérés : {len(names)}")

    detailed_rows = []
    agg_counter = Counter()

    # Pool de threads
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                compute_removed_moves_for_pokemon,
                name, args.include_forms, left_groups, right_groups
            ): name
            for name in names
        }

        for i, fut in enumerate(as_completed(futures), 1):
            name = futures[fut]
            try:
                pname, removed = fut.result()
                if not removed:
                    continue
                for m, lvl in removed:
                    if m == "__ERROR__":
                        print(f"[WARN] {pname}: {lvl}", file=sys.stderr)
                        continue
                    detailed_rows.append({
                        "pokemon": pname,
                        "move": m,
                        "move_human": humanize_move(m),
                        "left_min_level": lvl,
                        "left_groups": "|".join(sorted(left_groups)),
                        "right_groups": "|".join(sorted(right_groups)),
                    })
                    agg_counter[m] += 1
            except Exception as e:
                print(f"[ERREUR] {name}: {e}", file=sys.stderr)

            if i % 50 == 0:
                print(f"[INFO] {i}/{len(names)} Pokémon traités...", file=sys.stderr)

    # CSV détaillé
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "pokemon", "move", "move_human", "left_min_level", "left_groups", "right_groups"
        ])
        writer.writeheader()
        writer.writerows(detailed_rows)
    print(f"[OK] CSV détaillé écrit : {args.out} ({len(detailed_rows)} lignes)")

    # CSV agrégé
    if args.aggregate_out:
        with open(args.aggregate_out, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["move", "move_human", "pokemon_count"])
            for m, c in sorted(agg_counter.items(), key=lambda x: (-x[1], x[0])):
                writer.writerow([m, humanize_move(m), c])
        print(f"[OK] CSV agrégé écrit : {args.aggregate_out} ({len(agg_counter)} moves)")

    print("[FIN] Terminé !")

if __name__ == "__main__":
    main()
