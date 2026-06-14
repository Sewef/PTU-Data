import json
import requests
from pathlib import Path

INPUT_FILE = "../../ptu/data/pokedex/fandex/pokedex_variant.json"
OUTPUT_FILE = "../../ptu/data/pokedex/fandex/pokedex_variant.json"

API_URL = "https://pokeapi.co/api/v2/pokemon-species/{}"


def get_pokemon_number(species_name):
    response = requests.get(API_URL.format(species_name.lower()), timeout=10)

    if response.status_code != 200:
        print(f"Impossible de trouver {species_name}")
        return None

    return response.json()["id"]


with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

for pokemon in data:
    species = pokemon.get("Species")

    if species:
        pokemon["Number"] = get_pokemon_number(species)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Fichier généré : {OUTPUT_FILE}")