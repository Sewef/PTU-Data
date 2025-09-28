# fix_skills_text.py
# -*- coding: utf-8 -*-

import re
import sys
from typing import Dict, List, Tuple

# --- Abréviations -> noms canoniques ---
ABBREV_MAP = {
    "athl": "Athletics",
    "acro": "Acrobatics",
    "percep": "Perception",
    "perc": "Perception",
    "stealth": "Stealth",
    "focus": "Focus",
    "combat": "Combat",
    "athletics": "Athletics",
    "acrobatics": "Acrobatics",
    "perception": "Perception",
}

DICE_RE = re.compile(r"([A-Za-z]+)\s+(\d+d\d+(?:\+\d+)?)", flags=re.IGNORECASE)

def canon(label: str) -> str:
    return ABBREV_MAP.get(label.strip().lower(), label.strip().title())

def extract_skills_pairs(raw_block: str) -> List[Tuple[str, str]]:
    """
    Extrait des paires (label, dice) depuis un bloc texte libre:
    ex: "Athl 2d6, Acro 2d6, Stealth 3d6+1"
    """
    pairs = []
    for m in DICE_RE.finditer(raw_block.replace("\n", " ")):
        label, dice = m.group(1), m.group(2)
        pairs.append((canon(label), dice))
    # déduplique en conservant l'ordre
    seen = set()
    uniq = []
    for k, v in pairs:
        if k not in seen:
            seen.add(k)
            uniq.append((k, v))
    return uniq

def render_skills_object(pairs: List[Tuple[str, str]], indent: str, trailing_comma: bool) -> str:
    """
    Rend un objet JSON formaté avec l'indentation fournie.
    """
    inner_indent = indent + "  "
    lines = [f'{indent}"Skills": {{']
    for i, (k, v) in enumerate(pairs):
        comma = "," if i < len(pairs) - 1 else ""
        lines.append(f'{inner_indent}"{k}": "{v}"{comma}')
    lines.append(f"{indent}}}{',' if trailing_comma else ''}")
    return "\n".join(lines)

def replace_skills_block(text: str) -> Tuple[str, bool]:
    """
    Trouve un champ "Skills": <...> terminé par '},' ou '],'
    Remplace par un objet normalisé via find & replace.
    Retourne (nouveau_texte, remplacé_ou_non)
    """
    lines = text.splitlines()
    out = []
    i = 0
    changed = False

    while i < len(lines):
        line = lines[i]
        if '"Skills"' not in line:
            out.append(line)
            i += 1
            continue

        # On a trouvé la ligne contenant "Skills"
        # On détecte l'indentation en préfixe
        indent_match = re.match(r"^(\s*)", line)
        indent = indent_match.group(1) if indent_match else ""

        # On capture depuis cette ligne jusqu'à la ligne de fermeture (qui
        # se termine par '},' ou '],') pour le champ Skills.
        block_lines = [line]
        i += 1
        while i < len(lines):
            block_lines.append(lines[i])
            if re.search(r"^\s*[}\]],?\s*$", lines[i]):  # ligne qui est juste '}' ou '}]', possiblement avec une virgule
                # Mais on doit s'assurer que c'est bien la fermeture du champ Skills
                # Heuristique simple : si on a ouvert un objet ou un array immédiatement après "Skills":
                break
            i += 1

        # Joindre le bloc capturé
        raw_block = "\n".join(block_lines)

        # Déterminer si on laisse une virgule après l'objet Skills
        trailing_comma = raw_block.rstrip().endswith(",")

        # Extraire uniquement le contenu après "Skills": pour alimenter la regex
        # On récupère tout après le premier ':' dans le bloc
        after_colon = raw_block.split(":", 1)[1] if ":" in raw_block else raw_block

        # Extraire les paires dans ce bloc
        pairs = extract_skills_pairs(after_colon)

        if not pairs:
            # Rien à extraire -> on ne change pas ce bloc
            out.extend(block_lines)
            i += 1
            continue

        # Rendu de l'objet Skills propre
        rendered = render_skills_object(pairs, indent=indent, trailing_comma=trailing_comma)

        # On remplace en "find & replace" le bloc complet par la version propre
        out.append(rendered)
        changed = True
        i += 1  # on a déjà consommé la ligne de fermeture
    return ("\n".join(out), changed)

def main(in_path: str, out_path: str, write_in_place: bool = False):
    with open(in_path, "r", encoding="utf-8") as f:
        text = f.read()

    new_text, changed = replace_skills_block(text)

    if not changed:
        print("ℹ️  Aucun bloc Skills à corriger (ou rien d'extractible).")
    else:
        print("✅ Bloc Skills normalisé via find & replace.")

    if write_in_place:
        out_path = in_path
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_text)
    print(f"✍️  Écrit: {out_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print("Usage: python fix_skills_text.py input.txt output.txt [--in-place]")
        sys.exit(1)
    in_path, out_path = sys.argv[1], sys.argv[2]
    in_place = (len(sys.argv) == 4 and sys.argv[3] == "--in-place")
    main(in_path, out_path, write_in_place=in_place)
