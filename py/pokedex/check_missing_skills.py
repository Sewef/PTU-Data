import json

# Liste de référence des skills obligatoires
required_skills = [
    "Athletics",
    "Acrobatics",
    "Combat",
    "Stealth",
    "Perception",
    "Focus"
]

def check_skills(json_file):
    # Charger le JSON depuis un fichier
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Vérifier si c'est une liste (plusieurs Pokémon) ou un seul dict
    if isinstance(data, dict):
        data = [data]

    for pokemon in data:
        name = pokemon.get("Species", "???")
        present_skills = pokemon.get("Skills", {}).keys()
        missing_skills = [s for s in required_skills if s not in present_skills]

        if missing_skills:
            print(f"❌ {name} - Compétences manquantes : {missing_skills}")

# Exemple d'utilisation
check_skills("../../ptu/data/pokedex/pokedex_9g.json")
