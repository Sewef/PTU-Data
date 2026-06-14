import json

INPUT_FILE = "../../ptu/data/pokedex/fandex/pokedex_variant.json"
OUTPUT_FILE = INPUT_FILE

def normalize_gender(text):
    return (
        text.replace("% M", "% Male")
            .replace("% F", "% Female")
    )


with open(INPUT_FILE, "r", encoding="utf-8") as f:
    pokedex = json.load(f)

result = []

for pokemon in pokedex:

    breeding = pokemon.get("Breeding Information", {})

    other_info = {
        "Size Information": pokemon.get("Size Information", {}),
        "Genders": normalize_gender(
            breeding.get("Gender Ratio", "")
        ),
        "Diet": pokemon.get("Diet", ""),
        "Habitat": pokemon.get("Habitat", ""),
        "Egg Groups": breeding.get("Egg Group", "")
    }

    # Evolution
    for evo in pokemon.get("Evolution", []):

        if "Stage" in evo:
            evo["Stade"] = evo.pop("Stage")

        evo.setdefault("Condition", "")

    new_pokemon = {}

    for key, value in pokemon.items():

        if key in (
            "Size Information",
            "Breeding Information",
            "Diet",
            "Habitat",
        ):
            continue

        new_pokemon[key] = value

        # insertion au même endroit que dans le modèle PTU
        if key == "Evolution":
            new_pokemon["Other Information"] = other_info

    result.append(new_pokemon)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)