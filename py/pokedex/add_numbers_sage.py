import json

with open("../../ptu/data/pokedex/fandex/pokedex_sage.json", "r", encoding="utf-8") as f:
    data = json.load(f)

new_data = []

for idx, pokemon in enumerate(data, start=1):

    # À partir de l'index 103, on retire 1
    # pour avoir deux entrées avec le numéro 102
    number = idx if idx <= 102 else idx - 1

    new_pokemon = {}

    for key, value in pokemon.items():
        new_pokemon[key] = value

        if key == "Species":
            new_pokemon["Number"] = number

    new_data.append(new_pokemon)

with open("../../ptu/data/pokedex/fandex/pokedex_sage.json", "w", encoding="utf-8") as f:
    json.dump(new_data, f, ensure_ascii=False, indent=2)