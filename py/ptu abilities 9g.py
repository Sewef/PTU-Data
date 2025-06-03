import re
import pdfplumber

def extraire_blocs_abilities(pdf_path):
    blocs_extraits = []

    with pdfplumber.open(pdf_path) as pdf:
        texte_total = ""
        for page in pdf.pages:
            texte_total += page.extract_text() + "\n"

    # Séparer en blocs commençant par "Ability:"
    blocs = re.split(r'\n(?=Ability\s*:)', texte_total)

    for bloc in blocs:
        # Ne conserver que les blocs qui contiennent au moins "Ability:" et "Effect:"
        if "Ability:" in bloc and "Effect:" in bloc:
            blocs_extraits.append(bloc.strip())

    return blocs_extraits


# 🔁 Utilisation
pdf_path = "py/Community Gen 9 Homebrew Dex.pdf"
blocs = extraire_blocs_abilities(pdf_path)

# 💾 Sauvegarde en texte brut (optionnel)
with open("blocs_abilities.txt", "w", encoding="utf-8") as f:
    for b in blocs:
        f.write(b + "\n\n" + "="*40 + "\n\n")

# 🔍 Aperçu
for b in blocs[:3]:
    print(b)
    print("\n" + "="*40 + "\n")
