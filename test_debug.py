import json
from pathlib import Path

SCRIPT_DIR = Path('c:\\GitHub\\PTU-Data\\py')
WORKSPACE_ROOT = SCRIPT_DIR.parent
ICON_REF_FILE = SCRIPT_DIR / "pokedex" / "icon_ref.csv"
POKEDEX_DIR = WORKSPACE_ROOT / "ptu" / "data" / "pokedex"

def read_icon_mappings(csv_file):
    mappings = {}
    with open(csv_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(';')
            if len(parts) != 2:
                continue
            old_id, new_name = parts
            mappings[old_id] = new_name
    return mappings

mappings = read_icon_mappings(ICON_REF_FILE)
print(f"Loaded {len(mappings)} mappings")
print(f"Sample: {list(mappings.items())[:5]}")

pokedex_dir = POKEDEX_DIR
print(f"\nLooking in: {pokedex_dir}")

count = 0
for json_file in pokedex_dir.rglob('*.json'):
    count += 1
    is_min = json_file.name.endswith('.min.json')
    print(f"Found: {json_file.name} (min={is_min})")
    if count > 20:
        break

print(f"\nTotal JSON files found: {count}")

# Try to load and parse first non-min file
for json_file in pokedex_dir.rglob('*.json'):
    if not json_file.name.endswith('.min.json'):
        print(f"\nTesting with: {json_file}")
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"Type: {type(data)}")
        if isinstance(data, list):
            print(f"List of {len(data)} items")
            if len(data) > 0:
                print(f"First item: {type(data[0])}")
                if isinstance(data[0], dict) and 'Battle-Only Forms' in data[0]:
                    print("Found Battle-Only Forms!")
        break
