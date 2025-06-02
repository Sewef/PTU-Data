import pdfplumber
import re
import json

def extraire_blocs_moves(pdf_path):
    blocs_moves = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            width = page.width
            height = page.height

            # Extraire les deux colonnes
            gauche = page.within_bbox((0, 0, width / 2, height)).extract_text()
            droite = page.within_bbox((width / 2, 0, width, height)).extract_text()
            texte = (gauche or "") + "\n" + (droite or "")

            # Regrouper par bloc commençant par "Move:"
            blocs = re.split(r'\n(?=Move\s*:)', texte)
            for bloc in blocs:
                if "Move:" in bloc and "Effect:" in bloc:
                    blocs_moves.append(bloc.strip())

    return blocs_moves

def formatter_move_en_json(bloc):
    lines = bloc.splitlines()
    move = {
        "nom": None,
        "type": None,
        "frequency": None,
        "ac": None,
        "damage_base": None,
        "class": None,
        "range": None,
        "effect": None,
        "contest_type": None,
        "contest_effect": None,
        "trigger": None,
        "special": None
    }

    # Parsing ligne par ligne
    effect_started = False
    effect_lines = []

    for line in lines:
        l = line.strip()
        if not l:
            continue

        # Champs fixes
        if l.startswith("Move:"):
            move["nom"] = l.split(":", 1)[-1].strip()
        elif l.startswith("Type:"):
            move["type"] = l.split(":", 1)[-1].strip()
        elif l.startswith("Frequency:"):
            move["frequency"] = l.split(":", 1)[-1].strip()
        elif l.startswith("AC:"):
            move["ac"] = l.split(":", 1)[-1].strip()
        elif l.startswith("Damage Base"):
            move["damage_base"] = l
        elif l.startswith("Class:"):
            move["class"] = l.split(":", 1)[-1].strip()
        elif l.startswith("Range:"):
            move["range"] = l.split(":", 1)[-1].strip()
        elif l.startswith("Trigger:"):
            move["trigger"] = l.split(":", 1)[-1].strip()
        elif l.startswith("Special:"):
            move["special"] = l.split(":", 1)[-1].strip()
        elif l.startswith("Effect:"):
            effect_started = True
            effect_lines.append(l.split(":", 1)[-1].strip())
        elif l.startswith("Contest Type:"):
            move["contest_type"] = l.split(":", 1)[-1].strip()
        elif l.startswith("Contest Effect:"):
            move["contest_effect"] = l.split(":", 1)[-1].strip()
        elif effect_started:
            effect_lines.append(l.strip())

    if effect_lines:
        move["effect"] = " ".join(effect_lines)

    # Nettoyer les champs vides
    move = {k: v for k, v in move.items() if v}

    return move if "nom" in move and "effect" in move else None

# 🔁 Utilisation
pdf_path = '1-6G Indices and Reference.pdf'
blocs_moves = extraire_blocs_moves(pdf_path)
moves_json = [formatter_move_en_json(bloc) for bloc in blocs_moves]
moves_json = [m for m in moves_json if m]

# 💾 Sauvegarde
with open("moves_extraits.json", "w", encoding="utf-8") as f:
    json.dump(moves_json, f, indent=2, ensure_ascii=False)

# 🔍 Aperçu
print(json.dumps(moves_json[:3], indent=2, ensure_ascii=False))
