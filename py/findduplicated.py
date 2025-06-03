import json
from collections import Counter

def collect_names(json_data):
    """
    Recursively collect all 'name' field values from the JSON structure.
    """
    names = []
    if isinstance(json_data, dict):
        if 'name' in json_data:
            names.append(json_data['name'])
        for value in json_data.values():
            names.extend(collect_names(value))
    elif isinstance(json_data, list):
        for item in json_data:
            names.extend(collect_names(item))
    return names

if __name__ == "__main__":
    # Load your JSON file
    with open('work files/moves.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Collect all names
    all_names = collect_names(data)

    # Count duplicates
    name_counts = Counter(all_names)
    duplicates = {name: count for name, count in name_counts.items() if count > 1}

    if duplicates:
        print("Duplicate names found:")
        for name, count in duplicates.items():
            print(f"{name}: {count} times")
    else:
        print("No duplicate names found.")