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
            texte = (gauche or "") + "/n" + (droite or "")

            # Regrouper par bloc commençant par "Move:"
            blocs = re.split(r'/n(?=Move/s*:)', texte)
            for bloc in blocs:
                if "Move:" in bloc:
                    blocs_moves.append(bloc.strip())

    return blocs_moves

def formatter_move_en_json(bloc):
    lines = bloc.splitlines()
    move = {
        "Name": None,
        "Type": None,
        "Frequency": None,
        "AC": None,
        "Damage Base": None,
        "Class": None,
        "Range": None,
        "Effect": None,
        "Contest Type": None,
        "Contest Effect": None,
        "Trigger": None,
        "Special": None,
        "Set-Up Effect": None,
        "Resolution Effect": None
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
            move["Name"] = l.split(":", 1)[-1].strip()
            current_section = None
        elif l.startswith("Type:"):
            move["Type"] = l.split(":", 1)[-1].strip()
            current_section = None
        elif l.startswith("Frequency:"):
            move["Frequency"] = l.split(":", 1)[-1].strip()
            current_section = None
        elif l.startswith("AC:"):
            move["AC"] = l.split(":", 1)[-1].strip()
            current_section = None
        elif l.startswith("Damage Base"):
            move["Damage Base"] = l
            current_section = None
        elif l.startswith("Class:"):
            move["Class"] = l.split(":", 1)[-1].strip()
            current_section = None
        elif l.startswith("Range:"):
            move["Range"] = l.split(":", 1)[-1].strip()
            current_section = None
        elif l.startswith("Trigger:"):
            move["Trigger"] = l.split(":", 1)[-1].strip()
            current_section = None
        elif l.startswith("Special:"):
            move["Special"] = l.split(":", 1)[-1].strip()
            current_section = None
        elif l.startswith("Contest Type:"):
            move["Contest Type"] = l.split(":", 1)[-1].strip()
            current_section = None
        elif l.startswith("Contest Effect:"):
            move["Contest Effect"] = l.split(":", 1)[-1].strip()
            current_section = None
        elif l.startswith("Set-Up Effect:"):
            setup_lines.append(l.split(":", 1)[-1].strip())
            current_section = "Set-Up Effect"
        elif l.startswith("Resolution Effect:"):
            resolution_lines.append(l.split(":", 1)[-1].strip())
            current_section = "Resolution Effect"
        elif l.startswith("Effect:"):
            effect_lines.append(l.split(":", 1)[-1].strip())
            current_section = "Effect"
        else:
            # Lignes suivantes
            if current_section == "Effect":
                effect_lines.append(l)
            elif current_section == "Set-Up Effect":
                setup_lines.append(l)
            elif current_section == "Resolution Effect":
                resolution_lines.append(l)

    # Attribuer les sections dans move
    if setup_lines:
        move["Set-Up Effect"] = " ".join(setup_lines).strip()
    if resolution_lines:
        move["Resolution Effect"] = " ".join(resolution_lines).strip()
    if not (setup_lines or resolution_lines) and effect_lines:
        move["Effect"] = " ".join(effect_lines).strip()

    # Nettoyage des champs vides
    move = {k: v for k, v in move.items() if v}

    if not "Effect" in move:
        print(f"Attention: Move '{move.get('Name', 'Unknown')}' n'a pas d'effet défini.")
        move["Effect"] = "None."

    # Validation minimale
    if "Name" in move and ("Effect" in move or "Set-Up Effect" in move or "Resolution Effect" in move):
        return move
    return None

# 🔁 Utilisation
pdf_path = "Z:/Perso/PTU 1.05/Partage/Pokédex et Références/7G Alola Dex/SuMo References.pdf"
blocs_moves = extraire_blocs_moves(pdf_path)
moves_json = [formatter_move_en_json(bloc) for bloc in blocs_moves]
moves_json = [m for m in moves_json if m]

# 💾 Sauvegarde
with open("py/out.json", "w", encoding="utf-8") as f:
    json.dump(moves_json, f, indent=2, ensure_ascii=False)

# 🔍 Aperçu
print(json.dumps(moves_json[:3], indent=2, ensure_ascii=False))
