import json

# Charger le fichier existant
with open("ptu/data/edges/edges_core.json", "r", encoding="utf-8") as f:
    edges = json.load(f)

# Règles simples pour catégoriser
def detect_category(name, desc):
    return "TODO"

# Appliquer une source générique par défaut
default_source = "Core"

# Mise à jour des edges
for name, data in edges.items():
    description = data.get("Description", "")
    data["Category"] = detect_category(name, description)
    data["Source"] = default_source

# Sauvegarder dans un nouveau fichier
with open("ptu/data/edges/edges_core.json", "w", encoding="utf-8") as f:
    json.dump(edges, f, indent=2, ensure_ascii=False)

print("✅ Fichier enrichi généré : edges_core_with_metadata.json")
