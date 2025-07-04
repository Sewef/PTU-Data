import json

def propagate_and_clean(obj, class_source=None):
    # Si ce n'est pas un dict, on retourne tel quel
    if not isinstance(obj, dict):
        return obj

    # Si c'est un conteneur de classe (avec "Features"), on récupère la Source et on supprime Category
    if "Features" in obj:
        class_source = obj.get("Source")
        obj.pop("Source", None)
        obj.pop("Category", None)
        # On traite récursivement les features
        for feat_name, feat_value in obj["Features"].items():
            obj["Features"][feat_name] = propagate_and_clean(feat_value, class_source)
        return obj

    # Pour tout autre dict (feature ou sous-feature)
    # Injecte la Source de la classe si on en a
    if class_source is not None:
        obj["Source"] = class_source
    # Supprime Category si présent
    obj.pop("Category", None)
    # Traite récursivement
    return {k: propagate_and_clean(v, class_source) for k, v in obj.items()}

if __name__ == "__main__":
    with open("py/general.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    transformed = {cls: propagate_and_clean(obj) for cls, obj in data.items()}

    with open("py/general.json", "w", encoding="utf-8") as f:
        json.dump(transformed, f, ensure_ascii=False, indent=2)
