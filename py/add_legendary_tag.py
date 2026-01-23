#!/usr/bin/env python3
"""
Script to fetch legendary/mythical Pokémon from PokéAPI and add "Legendary": true tag
to the corresponding entries in PTU data pokedex files.
"""

import json
import csv
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Set

# Configuration
POKEAPI_BASE_URL = "https://pokeapi.co/api/v2"
MAPPING_FILE = Path("py/pokeapi/mapping.csv")
POKEDEX_DIRS = [
    Path("ptu/data/pokedex/core"),
    Path("ptu/data/pokedex/community"),
    Path("ptu/data/pokedex/homebrew"),
]

def load_mapping() -> Dict[str, str]:
    """Load the species name mapping from CSV."""
    mapping = {}
    with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            mapping[row['species']] = row['othername']
    return mapping

def fetch_url(url: str) -> dict:
    """Fetch JSON from URL with proper User-Agent."""
    request = urllib.request.Request(
        url,
        headers={'User-Agent': 'PTU-Data-Tagger/1.0 (+https://github.com/Sewef/PTU-Data)'}
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode('utf-8'))

def fetch_legendary_pokemon() -> Set[str]:
    """Fetch all legendary/mythical Pokémon from PokéAPI."""
    legendary = set()
    mythical = set()
    
    print("Fetching legendary Pokémon list from PokéAPI...")
    
    try:
        # Get legendary Pokémon
        url = f"{POKEAPI_BASE_URL}/pokemon-species/"
        page_count = 0
        while url:
            page_count += 1
            print(f"  Fetching page {page_count}...")
            data = fetch_url(url)
            
            for species in data.get('results', []):
                # Fetch species details to check if legendary/mythical
                species_url = species['url']
                try:
                    species_data = fetch_url(species_url)
                    
                    if species_data.get('is_legendary'):
                        legendary.add(species['name'])
                        print(f"    Found legendary: {species['name']}")
                    elif species_data.get('is_mythical'):
                        mythical.add(species['name'])
                        print(f"    Found mythical: {species['name']}")
                except (urllib.error.URLError, json.JSONDecodeError) as e:
                    print(f"    Warning: Could not fetch {species['name']}: {e}")
            
            # Next page
            url = data.get('next')
    
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"Error fetching from PokéAPI: {e}")
        return set()
    
    return legendary | mythical

def get_legendary_set_with_mapping(mapping: Dict[str, str]) -> Set[str]:
    """Get legendary Pokémon set, using mapping to match PTU species names."""
    pokeapi_legendary = fetch_legendary_pokemon()
    
    # Create a reverse mapping: pokeapi_name -> ptu_species_name
    reverse_mapping = {v: k for k, v in mapping.items()}
    
    # Map pokeapi names to PTU species names
    ptu_legendary = set()
    unmapped = set()
    
    for pokeapi_name in pokeapi_legendary:
        if pokeapi_name in reverse_mapping:
            ptu_legendary.add(reverse_mapping[pokeapi_name])
        else:
            # Try to find partial matches (for Pokémon with multiple forms)
            # e.g., "deoxys" matches "Deoxys Normal Forme", "Deoxys Attack Forme", etc.
            found = False
            for ptu_species, api_name in mapping.items():
                if api_name == pokeapi_name or api_name.startswith(pokeapi_name + '-'):
                    ptu_legendary.add(ptu_species)
                    found = True
                    # Don't break - some base forms have multiple variations
            
            if not found:
                unmapped.add(pokeapi_name)
    
    if unmapped:
        print(f"\nWarning: {len(unmapped)} legendary Pokémon could not be mapped:")
        for name in sorted(unmapped):
            print(f"  - {name}")
    
    return ptu_legendary

def process_pokedex_file(filepath: Path, legendary_set: Set[str]) -> int:
    """
    Add "Legendary": true to entries in a pokedex file.
    Returns the number of entries updated.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if not isinstance(data, list):
        print(f"Warning: {filepath} is not a JSON array, skipping")
        return 0
    
    updated = 0
    for entry in data:
        if isinstance(entry, dict) and 'Species' in entry:
            species_name = entry['Species']
            if species_name in legendary_set:
                entry['Legendary'] = True
                updated += 1
                print(f"  Tagged {species_name} as Legendary in {filepath.name}")
    
    # Write back only if changes were made
    if updated > 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  Saved {filepath.name} with {updated} updates")
    
    return updated

def main():
    print("=" * 60)
    print("PTU Legendary Pokémon Tagger")
    print("=" * 60)
    
    # Load mapping
    print("\nLoading species mapping...")
    mapping = load_mapping()
    print(f"Loaded {len(mapping)} species mappings")
    
    # Fetch legendary Pokémon from PokéAPI
    legendary_set = get_legendary_set_with_mapping(mapping)
    print(f"\nFound {len(legendary_set)} legendary/mythical Pokémon in PTU data")
    
    # Process all pokedex files
    print("\n" + "=" * 60)
    print("Processing pokedex files...")
    print("=" * 60)
    
    total_updated = 0
    for pokedex_dir in POKEDEX_DIRS:
        if not pokedex_dir.exists():
            print(f"Directory not found: {pokedex_dir}")
            continue
        
        print(f"\nProcessing {pokedex_dir}...")
        
        # Process both regular and minified files
        for json_file in sorted(pokedex_dir.glob("pokedex_*.json")):
            if json_file.name.endswith(".min.json"):
                continue  # Skip minified files for now
            
            updated = process_pokedex_file(json_file, legendary_set)
            total_updated += updated
    
    print("\n" + "=" * 60)
    print(f"Total entries updated: {total_updated}")
    print("=" * 60)

if __name__ == "__main__":
    main()
