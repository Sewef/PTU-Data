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
                if "Move:" in bloc:
                    blocs_moves.append(bloc.strip())

    return blocs_moves

def formatter_move_en_json(bloc):
    lines = bloc.splitlines()
    move = {
        "name": None,
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
        "special": None,
        "set_up_effect": None,
        "resolution_effect": None
    }

    # Parsing ligne par ligne
    current_section = None
    effect_lines, setup_lines, resolution_lines = [], [], []

    for line in lines:
        l = line.strip()
        if not l:
            continue

        # Champs identifiés
        if l.startswith("Move:"):
            move["name"] = l.split(":", 1)[-1].strip()
            current_section = None
        elif l.startswith("Type:"):
            move["type"] = l.split(":", 1)[-1].strip()
            current_section = None
        elif l.startswith("Frequency:"):
            move["frequency"] = l.split(":", 1)[-1].strip()
            current_section = None
        elif l.startswith("AC:"):
            move["ac"] = l.split(":", 1)[-1].strip()
            current_section = None
        elif l.startswith("Damage Base"):
            move["damage_base"] = l
            current_section = None
        elif l.startswith("Class:"):
            move["class"] = l.split(":", 1)[-1].strip()
            current_section = None
        elif l.startswith("Range:"):
            move["range"] = l.split(":", 1)[-1].strip()
            current_section = None
        elif l.startswith("Trigger:"):
            move["trigger"] = l.split(":", 1)[-1].strip()
            current_section = None
        elif l.startswith("Special:"):
            move["special"] = l.split(":", 1)[-1].strip()
            current_section = None
        elif l.startswith("Contest Type:"):
            move["contest_type"] = l.split(":", 1)[-1].strip()
            current_section = None
        elif l.startswith("Contest Effect:"):
            move["contest_effect"] = l.split(":", 1)[-1].strip()
            current_section = None
        elif l.startswith("Set-Up Effect:"):
            setup_lines.append(l.split(":", 1)[-1].strip())
            current_section = "set_up"
        elif l.startswith("Resolution Effect:"):
            resolution_lines.append(l.split(":", 1)[-1].strip())
            current_section = "resolution"
        elif l.startswith("Effect:"):
            effect_lines.append(l.split(":", 1)[-1].strip())
            current_section = "effect"
        else:
            # Lignes suivantes
            if current_section == "effect":
                effect_lines.append(l)
            elif current_section == "set_up":
                setup_lines.append(l)
            elif current_section == "resolution":
                resolution_lines.append(l)

    # Attribuer les sections dans move
    if setup_lines:
        move["set_up_effect"] = " ".join(setup_lines).strip()
    if resolution_lines:
        move["resolution_effect"] = " ".join(resolution_lines).strip()
    if not (setup_lines or resolution_lines) and effect_lines:
        move["effect"] = " ".join(effect_lines).strip()

    # Nettoyage des champs vides
    move = {k: v for k, v in move.items() if v}

    # Validation minimale
    if "name" in move and ("effect" in move or "set_up_effect" in move or "resolution_effect" in move):
        return move
    return None

# 🔁 Utilisation
pdf_path = "py/SwSh + Armor_Crown References.pdf"
blocs_moves = extraire_blocs_moves(pdf_path)
moves_json = [formatter_move_en_json(bloc) for bloc in blocs_moves]
moves_json = [m for m in moves_json if m]

# 💾 Sauvegarde
with open("8_moves INC swsh.json", "w", encoding="utf-8") as f:
    json.dump(moves_json, f, indent=2, ensure_ascii=False)

# 🔍 Aperçu
print(json.dumps(moves_json[:3], indent=2, ensure_ascii=False))
