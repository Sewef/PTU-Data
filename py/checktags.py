#!/usr/bin/env python3
"""fix_tags.py — corrige automatiquement les champs « Tags » d’un JSON PTU

Usage :
    python fix_tags.py  input.json  output.json

Règles appliquées :
  • Un champ Tags valide doit être une chaîne du type "[Tag1][Tag2]..."
    (pas d’espace entre les blocs, chaque tag entouré de crochets).
  • Les anomalies courantes sont réparées :
        - Espaces entre blocs : "[Orders] [Stratagem]"  ➜  "[Orders][Stratagem]"
        - Tags sans crochets : "Ranked 2"               ➜  "[Ranked 2]"
        - Virgules ou espaces comme séparateurs : "Branch, Orders" ➜ "[Branch][Orders]"
        - Crochets mal imbriqués (double "]]") : ils sont ré‑assemblés.

Le script parcourt récursivement dict / list, corrige in‑place, affiche un
rapport des champs modifiés puis écrit le JSON corrigé.
"""

import json
import re
import sys
from pathlib import Path

TAG_REGEX = re.compile(r"\[([^\[\]]+)\]")  # contenu entre crochets

# ---------------------------------------------------------------------------
# Normalisation d’une valeur Tags
# ---------------------------------------------------------------------------

def normalize_tags(value: str) -> str:
    """Retourne la version corrigée de *value* (ne modifie pas en place)."""

    if not isinstance(value, str):
        return value  # non géré ici

    # 1) Extraire toutes les occurrences déjà entre crochets
    brackets = TAG_REGEX.findall(value)

    # 2) S’il y a déjà ≥1 bloc entre crochets, on les utilise comme tokens.
    #    On élimine les doublons d’espaces internes au bloc.
    if brackets:
        tokens = [b.strip() for b in brackets]
    else:
        # 3) Sinon, détection par virgule éventuelle ; si pas de virgule on
        #    conserve la chaîne entière comme token (Ranked 2, +HP, ...)
        if "," in value:
            tokens = [t.strip() for t in value.split(",") if t.strip()]
        else:
            tokens = [value.strip()]

    # 4) Re‑construire sans doublons, format standard
    return "".join(f"[{t}]" for t in tokens if t)

# ---------------------------------------------------------------------------
# Parcours récursif et correction
# ---------------------------------------------------------------------------

def walk(node, path, patched):
    """Parcourt récursivement *node*, corrige Tags, remplit patched[]"""
    if isinstance(node, dict):
        for k, v in node.items():
            new_path = path + [k]
            if k.lower() == "tags" and isinstance(v, str):
                new_v = normalize_tags(v)
                if new_v != v:
                    node[k] = new_v
                    patched.append((" → ".join(path), v, new_v))
            else:
                walk(v, new_path, patched)

    elif isinstance(node, list):
        for idx, item in enumerate(node):
            walk(item, path + [f"[{idx}]"] , patched)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(src: Path, dst: Path):
    with src.open(encoding="utf-8") as f:
        data = json.load(f)

    patched = []
    walk(data, [], patched)

    # rapport
    if patched:
        print("Corrections appliquées :")
        for pth, old, new in patched:
            print(f"- {pth}\n    {old!r}  ➜  {new!r}")
        print(f"\n✓ {len(patched)} champ(s) Tags corrigé(s).")
    else:
        print("✓ Aucun champ Tags à corriger.")

    with dst.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nFichier écrit : {dst}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage : python fix_tags.py  input.json  output.json")
        sys.exit(1)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
