import json
from pathlib import Path

def deep_merge_by_key(data, updates):
    """
    Recursively search through `data`, and if any dict key matches one in `updates`,
    update that dict in place.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            # If current key is in updates, merge the dicts
            if key in updates and isinstance(value, dict) and isinstance(updates[key], dict):
                data[key].update(updates[key])
            else:
                # Recurse deeper
                deep_merge_by_key(value, updates)
    elif isinstance(data, list):
        for item in data:
            deep_merge_by_key(item, updates)

def main(file1_path, file2_path, output_path):
    with open(file1_path, 'r', encoding='utf-8') as f1:
        data1 = json.load(f1)

    with open(file2_path, 'r', encoding='utf-8') as f2:
        data2 = json.load(f2)

    deep_merge_by_key(data1, data2)

    with open(output_path, 'w', encoding='utf-8') as fout:
        json.dump(data1, fout, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    main("ptu/data/features_core.json", "py/output.json", "py/merged.json")