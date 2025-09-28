#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import csv
from pathlib import Path
import argparse
import sys

def extract_species_from_json(data):
    """
    data peut être un dict (un seul Pokémon) ou une liste de dicts.
    On récupère uniquement la clé top-level 'Species'.
    """
    species_list = []

    if isinstance(data, dict):
        val = data.get("Species")
        if isinstance(val, str):
            species_list.append(val)

    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                val = item.get("Species")
                if isinstance(val, str):
                    species_list.append(val)

    return species_list


def main():
    parser = argparse.ArgumentParser(
        description="Extrait les clés 'Species' de tous les .json d'un dossier et produit un CSV à une colonne."
    )
    parser.add_argument("input_dir", help="Dossier contenant les fichiers .json")
    parser.add_argument("-o", "--output", default="species.csv",
                        help="Chemin du CSV de sortie (par défaut: species.csv)")
    parser.add_argument("-r", "--recursive", action="store_true",
                        help="Parcourir récursivement les sous-dossiers")
    args = parser.parse_args()

    input_path = Path(args.input_dir)
    if not input_path.is_dir():
        print(f"Erreur: {input_path} n'est pas un dossier.", file=sys.stderr)
        sys.exit(1)

    pattern = "**/*.json" if args.recursive else "*.json"
    json_files = sorted(input_path.glob(pattern))

    if not json_files:
        print("Aucun fichier .json trouvé.", file=sys.stderr)
        sys.exit(2)

    # Assurer pokedex_core.json en premier
    ordered_files = []
    core_file = input_path / "pokedex_core.json"
    if core_file in json_files:
        ordered_files.append(core_file)
        json_files.remove(core_file)

    # Ajouter le reste en ordre alphabétique
    ordered_files.extend(sorted(json_files, key=lambda p: p.name))

    all_species = []

    for jf in ordered_files:
        try:
            text = jf.read_text(encoding="utf-8").strip()
            if not text:
                continue
            data = json.loads(text)
        except Exception as e:
            print(f"[WARN] Impossible de lire/parse {jf}: {e}", file=sys.stderr)
            continue

        species_here = extract_species_from_json(data)
        all_species.extend(species_here)

    # Écriture du CSV à une colonne
    out_path = Path(args.output)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        #writer.writerow(["Species"])
        for s in all_species:
            writer.writerow([s])

    print(f"OK : {len(all_species)} entrées écrites dans {out_path}")

if __name__ == "__main__":
    main()
