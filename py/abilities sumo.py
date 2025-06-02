import re
import json
import pdfplumber

def extraire_abilities(pdf_path):
    abilities = []

    with pdfplumber.open(pdf_path) as pdf:
        texte_total = ""
        for page in pdf.pages:
            texte_total += page.extract_text() + "\n"

    # Séparer par bloc commençant par "Ability:"
    blocs = re.split(r'(?=Ability\s*:)', texte_total, flags=re.IGNORECASE)

    for bloc in blocs:
        if not bloc.strip():
            continue

        # Extraire le nom
        nom_match = re.search(r'Ability\s*:\s*(.+)', bloc)
        if not nom_match:
            continue
        nom = nom_match.group(1).strip()

        # Supprimer la ligne "Ability: ..." pour traiter le reste
        reste = bloc[nom_match.end():].strip().splitlines()

        if len(reste) == 0:
            continue

        frequency_ = reste[0].strip()
        trigger = None
        effet = ""

        # Chercher Trigger et Effet
        effet_started = False
        for line in reste[1:]:
            if re.match(r'Trigger\s*:', line, re.IGNORECASE):
                trigger = re.sub(r'Trigger\s*:\s*', '', line, flags=re.IGNORECASE).strip()
            elif re.match(r'Effect\s*:', line, re.IGNORECASE):
                effet_started = True
                effet = re.sub(r'Effect\s*:\s*', '', line, flags=re.IGNORECASE).strip()
            elif effet_started:
                effet += ' ' + line.strip()

        # Construction du dictionnaire
        ability = {
            "nom": nom,
            "frequency": frequency_,
            "effet": effet.strip()
        }
        if trigger:
            ability["trigger"] = trigger
        abilities.append(ability)

    return abilities

# Utilisation
pdf_path = "SuMoBasics.pdf"
resultats = extraire_abilities(pdf_path)

# Sauvegarde JSON
with open("output.json", "w", encoding="utf-8") as f:
    json.dump(resultats, f, indent=2, ensure_ascii=False)

print(json.dumps(resultats, indent=2, ensure_ascii=False))
