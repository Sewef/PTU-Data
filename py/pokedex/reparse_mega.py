import json

# Nom du fichier à modifier
FILENAME = "../../ptu/data/pokedex/pokedex_core.json"

# Charger le JSON
with open(FILENAME, "r", encoding="utf-8") as f:
    data = json.load(f)

# data est une liste de Pokémon
for mon in data:
    if "Mega Evolution" in mon:
        mega_data = mon.pop("Mega Evolution")
        if "Battle-only Form" not in mon:
            mon["Battle-only Form"] = {}
        mon["Battle-only Form"]["Mega Evolution"] = mega_data

# Réécriture du fichier (écrasement)
with open(FILENAME, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

print(f"✅ Le fichier '{FILENAME}' a été mis à jour avec 'Battle-only Form'.")
