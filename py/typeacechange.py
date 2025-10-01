#!/usr/bin/env python3
"""
normalize_names.py  –  Place "Name" en tête de chaque objet JSON.

Usage
-----
$ python normalize_names.py chemin/entree.json [chemin/sortie.json]

• Si le paramètre de sortie est omis, le script crée "<nom>_named.json".
"""

import json
import sys
from pathlib import Path
from collections import OrderedDict
from copy import deepcopy

def normalize(node, parent_key=None):
    """Renvoie une copie de *node* où 'Name' est présent et premier."""
    # --- si c'est un dict ---------------------------------------------------
    if isinstance(node, dict):
        out = OrderedDict()

        # 1) Déterminer la valeur du champ Name ------------------------------
        if "Name" in node:
            name_val = node["Name"]
        elif "name" in node:
            name_val = node["name"]
        else:
            name_val = parent_key            # tombe à None pour la racine

        # 2) Ajouter Name en tout premier ------------------------------------
        if name_val is not None:
            out["name"] = name_val

        # 3) Recopier les autres clés dans l'ordre d'origine -----------------
        for k, v in node.items():
            if k in ("name", "Name"):          # déjà géré
                continue
            out[k] = normalize(v, k)           # récursion

        return out

    # --- si c'est une liste -------------------------------------------------
    if isinstance(node, list):
        return [normalize(item, parent_key) for item in node]

    # --- base case : valeur simple -----------------------------------------
    return node


def main(src_path, dst_path=None):
    with open(src_path, encoding="utf-8") as f:
        data = json.load(f)

    data_named = normalize(data)

    if dst_path is None:
        p = Path(src_path)
        dst_path = p.with_stem(f"{p.stem}_named")

    with open(dst_path, "w", encoding="utf-8") as f:
        json.dump(data_named, f, ensure_ascii=False, indent=2)

    print(f"✔ Fichier écrit : {dst_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python normalize_names.py input.json [output.json]")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
