import json
from pathlib import Path
import re

def is_ranked_field(key):
    return re.fullmatch(r"Rank \d+ (Prerequisites|Effect)", key)

def deep_insert_ranked_fields(data, updates):
    """
    Recursively search `data` and insert matching keys from `updates`.
    Removes old 'Prerequisites' and 'Effect' keys when inserting ranked ones.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if key in updates and isinstance(value, dict) and isinstance(updates[key], dict):
                # Remove generic keys
                value.pop("Prerequisites", None)
                value.pop("Effect", None)
                # Only insert ranked fields
                for rk, rv in updates[key].items():
                    if is_ranked_field(rk):
                        value[rk] = rv
            else:
                deep_insert_ranked_fields(value, updates)

    elif isinstance(data, list):
        for item in data:
            deep_insert_ranked_fields(item, updates)

def main(file1_path, file2_path, output_path):
    with open(file1_path, 'r', encoding='utf-8') as f1:
        data1 = json.load(f1)

    with open(file2_path, 'r', encoding='utf-8') as f2:
        data2 = json.load(f2)

    deep_insert_ranked_fields(data1, data2)

    with open(output_path, 'w', encoding='utf-8') as fout:
        json.dump(data1, fout, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    main("ptu/data/features_core.json", "py/output.json", "py/merged.json")
