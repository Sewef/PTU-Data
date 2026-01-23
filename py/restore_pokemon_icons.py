#!/usr/bin/env python3
"""
Script to restore Pokemon icon files to their original names (reverse of rename_pokemon_icons.py).
This is useful for testing or reverting changes.
"""

import os
import shutil
from pathlib import Path

# Configuration
SCRIPT_DIR = Path(__file__).parent
WORKSPACE_ROOT = SCRIPT_DIR.parent
ICON_REF_FILE = SCRIPT_DIR / "pokedex" / "icon_ref.csv"
POKEMON_IMG_DIR = WORKSPACE_ROOT / "ptu" / "img" / "pokemon" / "full"


def read_icon_mappings(csv_file):
    """Read icon_ref.csv and return a mapping of old_id -> new_name."""
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
                continue
            
            old_id, new_name = parts
            # Clean both values
            old_id = old_id.strip().lstrip('\ufeff')
            new_name = new_name.strip().lstrip('\ufeff')
            mappings[old_id] = new_name
    
    return mappings


def restore_pokemon_files(img_dir, mappings):
    """Restore Pokemon image files to original names."""
    if not img_dir.exists():
        raise FileNotFoundError(f"Pokemon image directory not found: {img_dir}")
    
    restored_count = 0
    
    for old_id, new_name in mappings.items():
        new_file = img_dir / f"{new_name}.png"
        old_file = img_dir / f"{old_id}.png"
        
        if new_file.exists():
            shutil.move(str(new_file), str(old_file))
            restored_count += 1
            print(f"✓ Restored: {new_name}.png → {old_id}.png")
        else:
            print(f"⚠ File not found: {new_name}.png (skipped)")
    
    print(f"\n✓ Successfully restored {restored_count} files")


if __name__ == "__main__":
    print("Restoring Pokemon icon files...")
    mappings = read_icon_mappings(ICON_REF_FILE)
    restore_pokemon_files(POKEMON_IMG_DIR, mappings)
