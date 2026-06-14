#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Add Number field to Insurgence Pokédex entries.
Assigns numbers from 727 to 924 in order.
"""

import json
from pathlib import Path

def main():
    input_file = Path("../../ptu/data/pokedex/fandex/pokedex_uranium.json")
    output_file = input_file
    
    # Load the data
    with input_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    
    if not isinstance(data, list):
        print("Error: Expected a list of Pokémon objects")
        return
    
    # Add Number field starting from 727
    start_number = 1
    for i, pokemon in enumerate(data):
        if isinstance(pokemon, dict):
            # Create new dict with Number right after Species
            new_pokemon = {}
            for key, value in pokemon.items():
                new_pokemon[key] = value
                if key == "Species":
                    new_pokemon["Number"] = start_number + i
            data[i] = new_pokemon
    
    # Write back
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✓ Added Number field to {len(data)} Pokémon")

if __name__ == "__main__":
    main()
