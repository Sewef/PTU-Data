import json

def deep_update_matching_key(base, updates):
    """
    Recursively find any matching keys in the base JSON and update their fields from updates.
    """
    if isinstance(base, dict):
        for key in list(base.keys()):
            if key in updates and isinstance(base[key], dict):
                base[key].update(updates[key])
            else:
                deep_update_matching_key(base[key], updates)
    elif isinstance(base, list):
        for item in base:
            deep_update_matching_key(item, updates)

def main(base_file, update_file, output_file):
    with open(base_file, 'r', encoding='utf-8') as f:
        base_data = json.load(f)

    with open(update_file, 'r', encoding='utf-8') as f:
        update_data = json.load(f)

    deep_update_matching_key(base_data, update_data)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(base_data, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    main("ptu/data/features_core.json", "py/output.json", "py/merged.json")
