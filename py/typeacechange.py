#!/usr/bin/env python3
"""
flatten_features.py – Éclate les sous-features imbriquées pour qu’il y ait
UN objet JSON par Feature dans chaque liste "features".

Usage
-----
$ python flatten_features.py input.json [output.json]
Si output.json est omis, un fichier "<nom>_flat.json" est écrit à côté.
"""

import json
import sys
from pathlib import Path
from copy import deepcopy

# Champs qui décrivent la Feature elle-même (à conserver dans l’objet racine)
SELF_KEYS = {
    "name", "Tags", "Prerequisites", "Frequency", "Target",
    "Effect", "Source", "Category",
    "Rank 1 Effect", "Rank 2 Effect",
    "Rank 1 Prerequisites", "Rank 2 Prerequisites",
    "Cost", "Ingredients"
}


def split_feature(feat, default_source):
    """
    Retourne une liste d’objets Features :
      – la Feature-mère nettoyée (sans ses sous-objets)
      – +1 objet par sous-feature détectée
    """
    base = {k: v for k, v in feat.items() if k in SELF_KEYS or not isinstance(v, dict)}
    out = [base]

    for key, val in feat.items():
        if isinstance(val, dict) and key not in SELF_KEYS:
            # Sous-feature → on en fait un nouvel objet
            sub = deepcopy(val)
            sub["name"] = key
            # Hérite d’une Source si absent
            if "Source" not in sub and "source" not in sub:
                if "Source" in feat:
                    sub["Source"] = feat["Source"]
                elif "source" in feat:
                    sub["Source"] = feat["source"]
                elif default_source:
                    sub["Source"] = default_source
            out.append(sub)

    return out


def transform(data):
    """Éclate toutes les sous-features de la structure complète."""
    for cls in data.values():
        cls_source = cls.get("source") or cls.get("Source")
        for branch in cls.get("branches", []):
            new_list = []
            for feat in branch.get("features", []):
                new_list.extend(split_feature(feat, cls_source))
            branch["features"] = new_list


def main(src, dst=None):
    with open(src, encoding="utf-8") as f:
        data = json.load(f)

    transform(data)

    if dst is None:
        p = Path(src)
        dst = p.with_stem(f"{p.stem}_flat")

    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✔ Fichier écrit : {dst}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python flatten_features.py input.json [output.json]")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
