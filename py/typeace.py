import json
import sys

def force_druidize_branch(branch_dict, class_name):
    """
    Regroupe TOUTES les features de la branche SOUS la clé class_name,
    même si elles étaient déjà partiellement sous class_name.
    """
    # Si déjà parfaitement druidisé : on vérifie si TOUTES les clés sont sous class_name
    if (
        isinstance(branch_dict, dict)
        and list(branch_dict.keys()) == [class_name]
        and isinstance(branch_dict[class_name], dict)
    ):
        return branch_dict  # On ne touche pas

    # Sinon, on fusionne tout ce qui n'est PAS class_name dans un nouvel objet
    new_features = {}
    # S'il y a déjà une clé class_name, on l'étale en premier
    if class_name in branch_dict and isinstance(branch_dict[class_name], dict):
        new_features.update(branch_dict[class_name])
    # Puis on ajoute tout le reste
    for k, v in branch_dict.items():
        if k != class_name:
            new_features[k] = v
    # Tout est maintenant regroupé SOUS class_name
    return {class_name: new_features}

def druidize_features(data, class_name="Type Ace"):
    """
    Pour chaque branche, regroupe toutes les features SOUS la clé class_name.
    """
    if class_name not in data:
        raise ValueError(f"Classe {class_name} absente du fichier.")

    features = data[class_name].get("Features", {})
    new_features = {}
    for branch, feat_dict in features.items():
        new_features[branch] = force_druidize_branch(feat_dict, class_name)
    data[class_name]["Features"] = new_features
    return data

def main():
    if len(sys.argv) != 3:
        print("Usage: python druidize_typeace.py input.json output.json")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    result = druidize_features(data, class_name="Type Ace")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("Conversion terminée.")

if __name__ == "__main__":
    main()
