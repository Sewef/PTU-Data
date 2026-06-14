import json

REQUIRED_STATS = [
    "HP",
    "Attack",
    "Defense",
    "Special Attack",
    "Special Defense",
    "Speed"
]

def check_missing_base_stats(file_path):
    # Lecture du fichier JSON
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    missing_report = []

    for obj in data:
        species = obj.get("Species", "Unknown")
        base_stats = obj.get("Base Stats", {})

        missing = [stat for stat in REQUIRED_STATS if stat not in base_stats]

        if missing:
            missing_report.append({
                "Species": species,
                "Missing Stats": missing
            })

    return missing_report


# ===== UTILISATION =====
file_path = "../../ptu/data/pokedex/fandex/pokedex_slimerancher.json"  # <-- mets ton fichier ici

result = check_missing_base_stats(file_path)

if result:
    for item in result:
        print(f"{item['Species']} manque: {', '.join(item['Missing Stats'])}")
else:
    print("Tous les objets ont leurs Base Stats complètes.")