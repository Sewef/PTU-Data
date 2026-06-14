#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
extract_min_level_from_evolutions.py
------------------------------------
Prend un fichier JSON (pokedex_insurgence, etc.) et parcourt toutes les entrées "Evolution".
Pour chaque string d'évolution du format "X - Species Name Minimum YY", on extrait:
- Le numéro de stage (X)
- Le nom de l'espèce (sans "Minimum YY")
- Le niveau minimum (YY) dans un champ "Minimum Level"

Le format d'entrée est un tableau de strings :
    "Evolution": ["1 - Delta Bulbasaur", "2 - Delta Ivysaur Minimum 15", ...]

Le format de sortie est un tableau d'objets :
    "Evolution": [
        {"Stage": 1, "Species": "Delta Bulbasaur"},
        {"Stage": 2, "Species": "Delta Ivysaur", "Minimum Level": 15},
        ...
    ]

Usage :
    python extract_min_level_from_evolutions.py --in pokedex_insurgence.json --out pokedex_insurgence.json
    # Optionnel --dry-run pour ne pas écrire et juste afficher un rapport
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

# Pattern pour "Minimum 15", "Minimum 30", etc.
LEVEL_PATTERN = re.compile(r'(?i)\bMinimum\s+(\d+)\b')
# Pattern pour le stage: "1 - Delta Bulbasaur"
STAGE_PATTERN = re.compile(r'^(\d+)\s*-\s*(.+)$')

def parse_evolution_string(evo_str: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Parse une string d'évolution du format "2 - Delta Ivysaur Minimum 15"
    et retourne (changed, object).
    
    L'objet résultant contient:
    - Stage: numéro de l'étape
    - Species: nom du Pokémon (sans le stage et sans "Minimum XX")
    - Minimum Level: le niveau extrait (si présent)
    """
    if not isinstance(evo_str, str):
        return (False, evo_str)
    
    original = evo_str.strip()
    changed = False
    
    # Extraire stage et reste
    stage_match = STAGE_PATTERN.match(original)
    if not stage_match:
        # Pas de format "X - ...", retourner tel quel
        return (False, evo_str)
    
    stage = int(stage_match.group(1))
    rest = stage_match.group(2).strip()
    
    # Chercher "Minimum XX"
    level_match = LEVEL_PATTERN.search(rest)
    
    result = {"Stage": stage}
    
    if level_match:
        # Extraire le niveau
        level_num = int(level_match.group(1))
        result["Minimum Level"] = level_num
        
        # Retirer "Minimum XX" du nom de l'espèce
        species = LEVEL_PATTERN.sub('', rest).strip()
        result["Species"] = species
        changed = True
    else:
        result["Species"] = rest
        # Toujours considéré comme changé car on structure en objet
        changed = True
    
    return (changed, result)


def process_document(data: Union[List[Any], Dict[str, Any]]) -> Tuple[Union[List[Any], Dict[str, Any]], Dict[str, Any]]:
    """
    Accepte soit une liste d'entrées (Pokémon), soit un dict {Species: obj}.
    Parcourt chaque entrée, puis son tableau Evolution (si présent) et transforme les items.
    Convertit les strings d'évolution en objets structurés avec extraction du niveau minimum.
    Retourne (data_modifiée, rapport).
    """
    stats = {"species_total": 0, "species_with_evolution": 0, "evolution_items_processed": 0, "min_level_extracted": 0}

    def handle_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
        nonlocal stats
        stats["species_total"] += 1
        evo = entry.get("Evolution")
        if not isinstance(evo, list):
            return entry

        stats["species_with_evolution"] += 1
        new_evo = []
        for it in evo:
            stats["evolution_items_processed"] += 1
            changed, new_it = parse_evolution_string(it)
            if changed and isinstance(new_it, dict) and "Minimum Level" in new_it:
                stats["min_level_extracted"] += 1
            new_evo.append(new_it)
        entry = {**entry, "Evolution": new_evo}
        return entry

    if isinstance(data, list):
        out_list = [handle_entry(x) if isinstance(x, dict) else x for x in data]
        return out_list, stats

    elif isinstance(data, dict):
        out_dict = {}
        for k, v in data.items():
            if isinstance(v, dict):
                out_dict[k] = handle_entry(v)
            else:
                out_dict[k] = v
        return out_dict, stats

    else:
        # format inattendu, ne rien changer
        return data, stats


def main():
    ap = argparse.ArgumentParser(description="Convertir Evolution strings en objets avec extraction de 'Minimum XX'.")
    ap.add_argument("--in", dest="infile", required=True, help="Chemin du JSON d'entrée (liste ou {Species: obj}).")
    ap.add_argument("--out", dest="outfile", required=False, help="Chemin du JSON de sortie.")
    ap.add_argument("--dry-run", action="store_true", help="N'écrit pas de fichier, affiche seulement le rapport.")
    args = ap.parse_args()

    in_path = Path(args.infile)
    data = json.loads(in_path.read_text(encoding="utf-8"))

    new_data, report = process_document(data)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if not args.dry_run:
        if not args.outfile:
            raise SystemExit("--out est requis sauf en --dry-run")
        out_path = Path(args.outfile)
        out_path.write_text(json.dumps(new_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[ok] Écrit: {out_path}")

if __name__ == "__main__":
    main()
