#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Compare les level-up moves entre deux générations (7, 8 ou 9) via PokeAPI.

• Choisis la paire à comparer avec --left-gen et --right-gen (valeurs: 7,8,9).
• Par défaut, les version groups utilisés sont :
    Gen 7 : ['ultra-sun-ultra-moon']
    Gen 8 : ['sword-shield']
    Gen 9 : ['scarlet-violet']
• Tu peux surclasser les groupes par génération avec --gen7-groups / --gen8-groups / --gen9-groups.
• Tu peux aussi ignorer ces préréglages et fournir explicitement --left-groups / --right-groups.

Exemples :
  python compare_moves.py pikachu                      # Gen7 vs Gen8
  python compare_moves.py --left-gen 7 --right-gen 9 charizard
  python compare_moves.py --left-gen 8 --right-gen 9 bulbasaur squirtle
  python compare_moves.py --gen9-groups scarlet-violet --left-gen 9 --right-gen 7 eevee
  python compare_moves.py --left-groups sword-shield --right-groups scarlet-violet gengar
"""

import argparse
import time
from typing import Dict, List, Set, Tuple
import requests

POKEAPI_BASE = "https://pokeapi.co/api/v2/pokemon/"
REQUEST_SLEEP = 0.2  # petite pause par requête

# préréglages de groupes par génération
DEFAULT_GROUPS_BY_GEN = {
    7: ["ultra-sun-ultra-moon"],   # alternatif: sun-moon, lets-go-pikachu-lets-go-eevee
    8: ["sword-shield"],           # alternatif: brilliant-diamond-and-shining-pearl, legends-arceus
    9: ["scarlet-violet"],         # Gen 9 (SV + DLCs référencés sous le même version_group dans PokeAPI)
}

def fetch_pokemon_data(name: str) -> dict:
    url = f"{POKEAPI_BASE}{name.strip().lower().replace(' ', '-')}"
    resp = requests.get(url, timeout=30)
    if resp.status_code == 404:
        raise ValueError(f"Pokémon introuvable dans PokeAPI: '{name}'")
    resp.raise_for_status()
    time.sleep(REQUEST_SLEEP)
    return resp.json()

def extract_level_up_moves(data: dict, version_groups: Set[str]) -> Dict[str, int]:
    """Retourne {move_name: min_level_observé} pour les moves appris par level-up dans les version_groups donnés."""
    result: Dict[str, int] = {}
    for move_entry in data.get("moves", []):
        move_name = move_entry["move"]["name"]
        for vgd in move_entry.get("version_group_details", []):
            vg_name = vgd["version_group"]["name"]
            if vg_name not in version_groups:
                continue
            if vgd["move_learn_method"]["name"] != "level-up":
                continue
            level_learned = vgd.get("level_learned_at", 0)
            if move_name not in result:
                result[move_name] = level_learned
            else:
                result[move_name] = min(result[move_name], level_learned)
    return result

def compare_moves(left: Dict[str, int], right: Dict[str, int]):
    """
    Compare deux dicts {move: level}.
    Retourne (only_left, only_right, level_changes) où level_changes = {move: (lvl_left, lvl_right)}.
    """
    setL, setR = set(left), set(right)
    only_left = setL - setR
    only_right = setR - setL
    common = setL & setR
    level_changes = {m: (left[m], right[m]) for m in common if left[m] != right[m]}
    return only_left, only_right, level_changes

def humanize_move(m: str) -> str:
    return m.replace('-', ' ').title()

def print_report(pokemon: str, left_label: str, right_label: str,
                 left_map: Dict[str, int], right_map: Dict[str, int]):
    onlyL, onlyR, changed = compare_moves(left_map, right_map)

    print("=" * 72)
    print(f"Pokémon : {pokemon}")
    print(f"- {left_label} : {len(left_map)} moves | - {right_label} : {len(right_map)} moves\n")

    if onlyL:
        print(f"❖ Présents uniquement côté {left_label}:")
        for m in sorted(onlyL):
            print(f"  - {humanize_move(m)} (lvl {left_map[m]})")
        print()
    else:
        print(f"❖ Aucun move exclusif côté {left_label}.\n")

    if onlyR:
        print(f"❖ Présents uniquement côté {right_label}:")
        for m in sorted(onlyR):
            print(f"  - {humanize_move(m)} (lvl {right_map[m]})")
        print()
    else:
        print(f"❖ Aucun move exclusif côté {right_label}.\n")

    if changed:
        print("❖ Niveaux différents pour les moves communs:")
        for m in sorted(changed):
            l, r = changed[m]
            print(f"  - {humanize_move(m)} : {left_label} lvl {l} → {right_label} lvl {r}")
        print()
    else:
        print("❖ Aucun niveau différent pour les moves communs.\n")

def main():
    parser = argparse.ArgumentParser(description="Compare level-up moves entre 7/8/9 via PokeAPI")
    parser.add_argument("pokemon", nargs="+", help="Nom(s) de Pokémon (ex: pikachu, charizard, mr-mime)")

    # Choix de la paire à comparer
    parser.add_argument("--left-gen", type=int, choices=[7, 8, 9], default=7, help="Génération côté gauche (défaut: 7)")
    parser.add_argument("--right-gen", type=int, choices=[7, 8, 9], default=8, help="Génération côté droit (défaut: 8)")

    # Surclassement des préréglages par génération
    parser.add_argument("--gen7-groups", nargs="+", help="Version groups pour la Gen 7 (ex: sun-moon ultra-sun-ultra-moon)")
    parser.add_argument("--gen8-groups", nargs="+", help="Version groups pour la Gen 8 (ex: sword-shield legends-arceus)")
    parser.add_argument("--gen9-groups", nargs="+", help="Version groups pour la Gen 9 (ex: scarlet-violet)")

    # Surclassement direct des côtés (ignore left/right-gen)
    parser.add_argument("--left-groups", nargs="+", help="Version groups côté gauche (prioritaire sur --left-gen)")
    parser.add_argument("--right-groups", nargs="+", help="Version groups côté droit (prioritaire sur --right-gen)")

    args = parser.parse_args()

    # Construire les groupes pour chaque gen, avec surclassements éventuels
    groups_by_gen = DEFAULT_GROUPS_BY_GEN.copy()
    if args.gen7_groups:
        groups_by_gen[7] = args.gen7_groups
    if args.gen8_groups:
        groups_by_gen[8] = args.gen8_groups
    if args.gen9_groups:
        groups_by_gen[9] = args.gen9_groups

    # Déterminer les groupes pour chaque côté
    if args.left_groups:
        left_groups = set(args.left_groups)
        left_label = " / ".join(args.left_groups)
    else:
        left_groups = set(groups_by_gen[args.left_gen])
        left_label = f"Gen{args.left_gen} ({' / '.join(groups_by_gen[args.left_gen])})"

    if args.right_groups:
        right_groups = set(args.right_groups)
        right_label = " / ".join(args.right_groups)
    else:
        right_groups = set(groups_by_gen[args.right_gen])
        right_label = f"Gen{args.right_gen} ({' / '.join(groups_by_gen[args.right_gen])})"

    for name in args.pokemon:
        try:
            data = fetch_pokemon_data(name)
        except Exception as e:
            print(f"[ERREUR] {name}: {e}")
            continue

        left_moves = extract_level_up_moves(data, left_groups)
        right_moves = extract_level_up_moves(data, right_groups)

        print_report(name, left_label, right_label, left_moves, right_moves)

if __name__ == "__main__":
    main()
