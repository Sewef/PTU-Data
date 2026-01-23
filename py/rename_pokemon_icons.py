#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to rename Pokemon icon files and update references in Pokedex JSON files.

The script reads icon_ref.csv which contains mappings from icon IDs to names,
then renames files in /ptu/img/pokemon/full/ and updates all references in
Pokedex JSON files.
"""

import os
import json
import sys
import shutil
from pathlib import Path

# Fix encoding on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Configuration
SCRIPT_DIR = Path(__file__).parent
WORKSPACE_ROOT = SCRIPT_DIR.parent
ICON_REF_FILE = SCRIPT_DIR / "pokedex" / "icon_ref.csv"
POKEMON_IMG_DIR = WORKSPACE_ROOT / "ptu" / "img" / "pokemon" / "full"
POKEDEX_DIR = WORKSPACE_ROOT / "ptu" / "data" / "pokedex"


def read_icon_mappings(csv_file):
    """Read icon_ref.csv and return a mapping of icon_id -> new_name."""
    mappings = {}
    
    if not csv_file.exists():
        raise FileNotFoundError(f"Icon reference file not found: {csv_file}")
    
    with open(csv_file, 'r', encoding='utf-8-sig') as f:  # utf-8-sig removes BOM
        for line in f:
            line = line.strip()
            # Remove any remaining BOM characters
            line = line.lstrip('\ufeff')
            if not line:
                continue
            
            parts = line.split(';')
            if len(parts) != 2:
                print(f"Warning: Skipping invalid line: {line}")
                continue
            
            icon_id, new_name = parts
            # Clean both values
            icon_id = icon_id.strip().lstrip('\ufeff')
            new_name = new_name.strip().lstrip('\ufeff')
            mappings[icon_id] = new_name
    
    print(f"✓ Loaded {len(mappings)} icon mappings from {csv_file.name}")
    return mappings


def rename_pokemon_files(img_dir, mappings):
    """Rename Pokemon image files based on mappings."""
    if not img_dir.exists():
        raise FileNotFoundError(f"Pokemon image directory not found: {img_dir}")
    
    renamed_count = 0
    errors = []
    
    for old_name, new_name in mappings.items():
        old_file = img_dir / f"{old_name}.png"
        new_file = img_dir / f"{new_name}.png"
        
        if old_file.exists():
            try:
                # Check if new file already exists
                if new_file.exists():
                    print(f"⚠ File already exists, skipping: {new_file.name}")
                    continue
                
                shutil.move(str(old_file), str(new_file))
                renamed_count += 1
                print(f"✓ Renamed: {old_name}.png → {new_name}.png")
                
            except Exception as e:
                errors.append(f"Error renaming {old_name}.png: {e}")
        else:
            print(f"⚠ File not found: {old_name}.png (skipped)")
    
    if errors:
        print("\nErrors encountered:")
        for error in errors:
            print(f"  ✗ {error}")
    
    print(f"\n✓ Successfully renamed {renamed_count} files")
    return renamed_count, errors


def update_pokedex_references(pokedex_dir, mappings):
    """Update all references to renamed icons in Pokedex JSON files using proper JSON parsing."""
    if not pokedex_dir.exists():
        raise FileNotFoundError(f"Pokedex directory not found: {pokedex_dir}")
    
    updated_count = 0
    errors = []
    total_replacements = 0
    
    # Walk through all JSON files in pokedex subdirectories
    for json_file in pokedex_dir.rglob("*.json"):
        try:
            # Skip minified files for now (they'll be regenerated)
            if json_file.name.endswith('.min.json'):
                continue
            
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            replacements = update_json_icons(data, mappings)
            
            # If changes were made, save the file
            if replacements > 0:
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"✓ Updated {json_file.name}: {replacements} references replaced")
                updated_count += 1
                total_replacements += replacements
        
        except json.JSONDecodeError as e:
            errors.append(f"JSON decode error in {json_file.name}: {e}")
        except Exception as e:
            errors.append(f"Error processing {json_file.name}: {e}")
    
    if errors:
        print("\nErrors encountered while updating references:")
        for error in errors:
            print(f"  ✗ {error}")
    
    print(f"\n✓ Updated references in {updated_count} JSON files ({total_replacements} total replacements)")
    return updated_count, errors


def update_json_icons(obj, mappings):
    """Recursively traverse JSON object and replace icon IDs."""
    replacements = 0
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "Icon" and isinstance(value, int):
                # Found an Icon field with integer value
                old_id = str(value)
                if old_id in mappings:
                    obj[key] = mappings[old_id]
                    replacements += 1
            elif isinstance(value, (dict, list)):
                replacements += update_json_icons(value, mappings)
    
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                replacements += update_json_icons(item, mappings)
    
    return replacements


def main():
    """Main execution function."""
    print("=" * 60)
    print("Pokemon Icon Renaming Script")
    print("=" * 60)
    print()
    
    try:
        # Step 1: Load icon mappings
        print("Step 1: Loading icon mappings...")
        mappings = read_icon_mappings(ICON_REF_FILE)
        print()
        
        # Step 2: Rename files
        print("Step 2: Renaming Pokemon image files...")
        print(f"Directory: {POKEMON_IMG_DIR}")
        rename_count, rename_errors = rename_pokemon_files(POKEMON_IMG_DIR, mappings)
        print()
        
        # Step 3: Update references in JSON files
        print("Step 3: Updating Pokedex JSON references...")
        print(f"Directory: {POKEDEX_DIR}")
        update_count, update_errors = update_pokedex_references(POKEDEX_DIR, mappings)
        print()
        
        # Summary
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Files renamed: {rename_count}")
        print(f"JSON files updated: {update_count}")
        print()
        
        if rename_errors or update_errors:
            print("⚠ Some errors were encountered. Please review above.")
            return 1
        else:
            print("✓ All operations completed successfully!")
            return 0
    
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
