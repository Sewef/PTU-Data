import json
import os
from pathlib import Path
from collections import defaultdict


def extract_moves_from_pokemon(pokemon_data):
    """Extrait tous les moves d'un Pokémon."""
    moves = set()
    
    if not isinstance(pokemon_data, dict):
        return moves
    
    moves_section = pokemon_data.get("Moves", {})
    
    # Parcourir toutes les sections de moves (Level Up, TM/HM, Egg Moves, Tutor, etc.)
    for section_name, move_list in moves_section.items():
        if isinstance(move_list, list):
            for move_entry in move_list:
                if isinstance(move_entry, dict) and "Move" in move_entry:
                    move_name = move_entry["Move"]
                    # Ignorer les moves avec un astérisque et les entrées spéciales
                    if '*' not in move_name and not move_name.startswith("Mew can"):
                        moves.add(move_name)
    
    return moves


def get_moves_from_pokedex_file(file_path):
    """Lit un fichier pokedex et extrait tous les moves."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        moves = set()
        if isinstance(data, list):
            for pokemon in data:
                moves.update(extract_moves_from_pokemon(pokemon))
        elif isinstance(data, dict):
            moves.update(extract_moves_from_pokemon(data))
            
        return moves
    except Exception as e:
        print(f"Erreur lors de la lecture de {file_path}: {e}")
        return set()


def get_moves_from_moves_file(file_path):
    """Lit un fichier de moves et retourne l'ensemble des noms de moves."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        moves = set()
        if isinstance(data, dict):
            for move_key in data.keys():
                # Ajouter la clé complète
                moves.add(move_key)
                # Si la clé contient un *, ajouter aussi la version sans * ni description
                if '*' in move_key:
                    # Extraire le nom de base avant le *
                    base_name = move_key.split('*')[0].strip()
                    moves.add(base_name)
        return moves
    except Exception as e:
        print(f"Erreur lors de la lecture de {file_path}: {e}")
        return set()


def find_missing_moves():
    """Trouve les moves présents dans les pokedex mais absents des fichiers de moves."""
    base_path = Path("ptu/data")
    
    # Dictionnaire pour stocker les moves par catégorie
    pokedex_moves = {
        'core': set(),
        'community': set(),
        'homebrew': set()
    }
    
    moves_db = {
        'core': set(),
        'community': set(),
        'homebrew': set()
    }
    
    # Collecter tous les moves des pokedex
    for category in ['core', 'community', 'homebrew']:
        pokedex_dir = base_path / 'pokedex' / category
        
        if pokedex_dir.exists():
            print(f"\n=== Analyse des pokedex {category.upper()} ===")
            for json_file in pokedex_dir.glob('*.json'):
                # Ignorer les fichiers minifiés
                if '.min.json' in json_file.name:
                    continue
                    
                print(f"  Lecture de {json_file.name}...")
                moves = get_moves_from_pokedex_file(json_file)
                pokedex_moves[category].update(moves)
                print(f"    {len(moves)} moves trouvés")
            
            print(f"  Total: {len(pokedex_moves[category])} moves uniques dans {category}")
    
    # Collecter tous les moves des fichiers de moves
    print(f"\n=== Analyse des fichiers de moves ===")
    for category in ['core', 'community', 'homebrew']:
        moves_file = base_path / 'moves' / f'moves_{category}.json'
        
        if moves_file.exists():
            print(f"  Lecture de moves_{category}.json...")
            moves = get_moves_from_moves_file(moves_file)
            moves_db[category].update(moves)
            print(f"    {len(moves)} moves trouvés")
    
    # Analyser les moves manquants
    print(f"\n{'='*70}")
    print(f"=== RÉSULTATS: MOVES MANQUANTS ===")
    print(f"{'='*70}\n")
    
    all_missing = defaultdict(set)
    
    for category in ['core', 'community', 'homebrew']:
        # Moves dans le pokedex mais pas dans le fichier de moves
        missing = pokedex_moves[category] - moves_db[category]
        
        if missing:
            print(f"\n--- {category.upper()} ---")
            print(f"Moves dans le pokedex mais absents de moves_{category}.json:")
            for move in sorted(missing):
                print(f"  - {move}")
                all_missing[category].add(move)
        else:
            print(f"\n--- {category.upper()} ---")
            print(f"✓ Tous les moves du pokedex sont présents dans moves_{category}.json")
    
    # Résumé global
    print(f"\n{'='*70}")
    print(f"=== RÉSUMÉ ===")
    print(f"{'='*70}")
    for category in ['core', 'community', 'homebrew']:
        total_pokedex = len(pokedex_moves[category])
        total_moves_db = len(moves_db[category])
        total_missing = len(all_missing[category])
        
        print(f"\n{category.upper()}:")
        print(f"  Moves dans le pokedex: {total_pokedex}")
        print(f"  Moves dans moves_{category}.json: {total_moves_db}")
        print(f"  Moves manquants: {total_missing}")
        if total_missing > 0:
            percentage = (total_missing / total_pokedex * 100) if total_pokedex > 0 else 0
            print(f"  Pourcentage manquant: {percentage:.2f}%")
    
    return all_missing


if __name__ == "__main__":
    print("Recherche des moves manquants...")
    print(f"Répertoire de travail: {os.getcwd()}\n")
    
    missing_moves = find_missing_moves()
    
    # Sauvegarder les résultats dans un fichier JSON
    output_file = "missing_moves_report.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(
            {category: sorted(list(moves)) for category, moves in missing_moves.items()},
            f,
            indent=2,
            ensure_ascii=False
        )
    
    print(f"\n\nRapport sauvegardé dans: {output_file}")
