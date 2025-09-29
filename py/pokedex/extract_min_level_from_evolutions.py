#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
extract_min_level_from_evolutions.py
------------------------------------
Prend un fichier JSON (pokedex_core, etc.) et parcourt toutes les entrées "Evolution".
Pour chaque objet d'évolution, on extrait via regex les segments de type **"Lv XX Minimum"**
et on les place dans un champ **"Minimum Level"**. On nettoie ensuite **Condition** en retirant ce segment,
en conservant le reste si applicable (sinon Condition devient chaîne vide "").

- Détection insensible à la casse : r'(?i)\\bLv\\s*\\d+\\s*Minimum\\b'
- S'il y a plusieurs occurrences dans la même Condition, on garde la **première** pour "Minimum Level"
  et on supprime **toutes** les occurrences du texte dans Condition.

Usage :
    python extract_min_level_from_evolutions.py --in pokedex_core.json --out pokedex_core_fixed.json
    # Optionnel --dry-run pour ne pas écrire et juste afficher un rapport
"""

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

LEVEL_PATTERN = re.compile(r'(?i)\bLv\s*\d+\s*Minimum\b')

def tidy_condition_text(s: str) -> str:
    # Supprimer espaces multiples et espaces autour des virgules / tirets
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'\s*,\s*', ', ', s)
    s = re.sub(r'\s*-\s*', ' - ', s)
    # Nettoyer ponctuation résiduelle en bout
    s = s.strip(' ,;')
    return s

def process_evolution_item(item: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Retourne (changed, new_item). Si Condition contient "Lv XX Minimum",
    on stocke la première occurrence dans "Minimum Level" et on retire toutes les occurrences de Condition.
    """
    changed = False
    new_item = deepcopy(item)

    cond = new_item.get("Condition")
    if not isinstance(cond, str):
        return (False, new_item)

    matches = LEVEL_PATTERN.findall(cond)
    if not matches:
        return (False, new_item)

    # Garder la première occurrence telle quelle (respecte la casse du texte source)
    first = matches[0].strip()
    new_item["Minimum Level"] = first

    # Retirer toutes les occurrences du pattern de Condition
    cond_clean = LEVEL_PATTERN.sub('', cond)
    cond_clean = tidy_condition_text(cond_clean)

    new_item["Condition"] = cond_clean if cond_clean else ""

    changed = True
    return (changed, new_item)


def process_document(data: Union[List[Any], Dict[str, Any]]) -> Tuple[Union[List[Any], Dict[str, Any]], Dict[str, Any]]:
    """
    Accepte soit une liste d'entrées (Pokémon), soit un dict {Species: obj}.
    Parcourt chaque entrée, puis son tableau Evolution (si présent) et transforme les items.
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
            if isinstance(it, dict):
                stats["evolution_items_processed"] += 1
                changed, new_it = process_evolution_item(it)
                if changed:
                    stats["min_level_extracted"] += 1
                new_evo.append(new_it)
            else:
                new_evo.append(it)
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
    ap = argparse.ArgumentParser(description="Extraire 'Lv XX Minimum' depuis Evolution[].Condition -> 'Minimum Level'.")
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
