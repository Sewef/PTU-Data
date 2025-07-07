#!/usr/bin/env python3
"""
convert_classes.py – transforme l’ancien JSON de Classes/Fonctions
vers le nouveau schéma unifié et plus simple à parcourir côté front.

Usage :
    python convert_classes.py  classes_old.json  classes_new.json
"""

import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# 1) Détection d’une Feature « feuille »
# ---------------------------------------------------------------------------
LEAF_KEYS = {"effect", "frequency", "tags", "trigger", "target",
             "Effect", "Frequency", "Tags", "Trigger", "Target"}

def is_leaf_feature(obj: dict) -> bool:
    """True si l’objet ressemble à une Feature terminale."""
    return any(k in obj for k in LEAF_KEYS)


# ---------------------------------------------------------------------------
# 2) Conversion récursive d’un bloc { FeatureName: {...}, ... } en liste
# ---------------------------------------------------------------------------
def flatten_features(dico: dict) -> list[dict]:
    """
    Transforme un mapping de Features en liste :
    { "Trickster": {...}, "Bag of Tricks": {...} }  ->  [ {...}, {...} ]
    Les sous-Features éventuelles passent dans .children.
    """
    feats = []
    for name, data in dico.items():

        # Copie défensive pour ne pas modifier l’original
        data = dict(data)

        # Sépare un éventuel sous-ensemble « Features »
        children_raw = data.pop("Features", None)

        feature = {"name": name, **data}

        if children_raw:
            feature["children"] = flatten_features(children_raw)

        feats.append(feature)
    return feats


# ---------------------------------------------------------------------------
# 3) Conversion d’une classe complète
# ---------------------------------------------------------------------------
def convert_class(class_dict: dict) -> dict:
    """
    Retourne le nouvel objet « classe » :
    {
      category, source,
      branches: [
        { name, features: [...] },
        ...
      ]
    }
    """
    category = class_dict.get("Category", "Other")
    source   = class_dict.get("Source",   "Unknown")

    features_root = class_dict.get("Features", {})

    # Déterminer si le 1er niveau est déjà une branche (Beauty, Bug, …)
    # Heuristique : un nœud est une branche si **tous** ses enfants
    # contiennent une clé 'Features'. Sinon, on est déjà au niveau features.
    sample = next(iter(features_root.values()), None)
    has_branch_level = isinstance(sample, dict) and "Features" in sample

    branches = []

    if has_branch_level:
        for branch_name, branch_wrap in features_root.items():
            branches.append({
                "name": branch_name,
                "features": flatten_features(branch_wrap.get("Features", {}))
            })
    else:
        branches.append({
            "name": "Default",
            "features": flatten_features(features_root)
        })

    return {"category": category,
            "source": source,
            "branches": branches}


# ---------------------------------------------------------------------------
# 4) Programme principal
# ---------------------------------------------------------------------------
def main(src_path: Path, dst_path: Path) -> None:
    with src_path.open(encoding="utf-8") as f:
        old_data = json.load(f)

    new_data = { cls_name: convert_class(cls_obj)
                 for cls_name, cls_obj in old_data.items() }

    with dst_path.open("w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Conversion terminée : {dst_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage : python convert_classes.py  input.json  output.json")
        sys.exit(1)

    src, dst = map(Path, sys.argv[1:])
    main(src, dst)
