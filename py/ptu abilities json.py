import pdfplumber
import re
import json

def extraire_blocs_abilities_colonnes(pdf_path):
    blocs_extraits = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            width = page.width
            height = page.height

            # Deux colonnes : gauche et droite
            gauche = page.within_bbox((0, 0, width / 2, height)).extract_text()
            droite = page.within_bbox((width / 2, 0, width, height)).extract_text()

            texte = (gauche or "") + "\n" + (droite or "")
            blocs = re.split(r'\n(?=Ability\s*:)', texte)

            for bloc in blocs:
                if "Ability:" in bloc and "Effect:" in bloc:
                    blocs_extraits.append(bloc.strip())

    return blocs_extraits

def formatter_bloc_en_json(bloc):
    lignes = bloc.splitlines()
    if not lignes or not lignes[0].startswith("Ability:"):
        return None

    name = lignes[0].split(":", 1)[-1].strip()
    frequency_ = None
    trigger = []
    effect = []
    trigger_started = False
    effect_started = False

    for line in lignes[1:]:
        l = line.strip()
        if not l:
            continue

        if l.lower().startswith("trigger:"):
            trigger_started = True
            effect_started = False
            trigger.append(l.split(":", 1)[-1].strip())
        elif l.lower().startswith("effect:"):
            effect_started = True
            trigger_started = False
            effect.append(l.split(":", 1)[-1].strip())
        elif trigger_started:
            trigger.append(l)
        elif effect_started:
            effect.append(l)
        elif not frequency_:
            frequency_ = l

    if name and frequency_ and effect:
        entry = {
            "name": name,
            "frequency": frequency_.strip(),
            "effect": " ".join(effect).strip()
        }
        if trigger:
            entry["trigger"] = " ".join(trigger).strip()
        return entry

    return None

# 📦 Pipeline complet
pdf_path = 'py/1-6G Indices and Reference.pdf'
blocs = extraire_blocs_abilities_colonnes(pdf_path)
abilities_json = [formatter_bloc_en_json(bloc) for bloc in blocs]
abilities_json = [a for a in abilities_json if a]  # Supprimer les Nones

# 💾 Sauvegarde en JSON
with open("abilities_extract.json", "w", encoding="utf-8") as f:
    json.dump(abilities_json, f, indent=2, ensure_ascii=False)

# 🔍 Aperçu
print(json.dumps(abilities_json[:3], indent=2, ensure_ascii=False))
