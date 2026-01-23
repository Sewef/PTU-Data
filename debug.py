import json
from pathlib import Path

pokedex_dir = Path('c:\\GitHub\\PTU-Data\\ptu\\data\\pokedex')
for json_file in pokedex_dir.rglob('*.json'):
    is_min = json_file.name.endswith('.min.json')
    print(f'{json_file.name}: ends with .min.json = {is_min}')
    if not is_min:
        print(f'  -> Would process this file')
