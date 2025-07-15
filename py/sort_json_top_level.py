import json
from collections import OrderedDict

def sort_json_top_level(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f, object_pairs_hook=OrderedDict)

    # Sort top-level keys only
    sorted_data = OrderedDict(sorted(data.items(), key=lambda item: item[0].lower()))

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(sorted_data, f, indent=4, ensure_ascii=False)

# Example usage
sort_json_top_level("ptu/data/moves/moves_homebrew.json", "ptu/data/moves/moves_homebrew.json")
