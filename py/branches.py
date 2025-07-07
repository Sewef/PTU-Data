import json, copy

def branchify_martial_artist(data):
    """
    Prend le JSON d'origine (classe Martial Artist avec branche 'Default')
    et renvoie la version branchée.
    """
    cls = data["Martial Artist"]
    default_branch = cls["branches"][0]          # celle nommée 'Default'
    new_branches = []

    for wrapper in default_branch["features"]:
        branch_name = wrapper["name"]            # ex. 'Guts'
        inner_dict  = wrapper["Martial Artist"]  # toutes les Features

        branch_features = []
        for feat_name, feat_data in inner_dict.items():
            feat = copy.deepcopy(feat_data)
            feat["name"] = feat_name
            branch_features.append(feat)

        new_branches.append({
            "name": branch_name,
            "features": branch_features
        })

    cls["branches"] = new_branches
    return data

# --- exemple d'utilisation -------------------------------------------------
with open("py/classetoconvert.json", "r", encoding="utf-8") as f:
    raw = json.load(f)

raw = branchify_martial_artist(raw)

with open("py/classetoconvert.json", "w", encoding="utf-8") as f:
    json.dump(raw, f, indent=2, ensure_ascii=False)
print("Conversion terminée !")
