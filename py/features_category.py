import json

# Fichier source et destination
INPUT_FILE = "ptu/data/features/features_core.json"       # ton fichier actuel
OUTPUT_FILE = "py/features_with_meta.json"  # fichier transformé

# Charge les données brutes
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    raw_data = json.load(f)

# Construit la nouvelle structure
transformed = {}

for class_name, features in raw_data.items():
    transformed[class_name] = {
        "Category": "TODO",  # À remplir manuellement
        "Source": "TODO",    # À remplir manuellement
        "Features": features
    }

# Sauvegarde dans le nouveau fichier
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(transformed, f, indent=2, ensure_ascii=False)

print(f"✅ Conversion terminée. Modifie '{OUTPUT_FILE}' pour ajouter les Category et Source.")
