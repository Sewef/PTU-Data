import json
import re

def is_prereq_key(key):
    return key == "Prerequisites" or re.fullmatch(r"Rank \d+ Prerequisites", key)

def reorder_keys(d):
    """
    Reorder keys in the dictionary so that all Prerequisites (including ranked ones)
    come just before 'Frequency'. Recurses into nested dicts and lists.
    """
    if isinstance(d, dict):
        keys = list(d.keys())

        # Find 'Frequency' index if it exists
        if "Frequency" in keys:
            freq_index = keys.index("Frequency")

            # Separate prerequisite keys
            prereq_keys = [k for k in keys if is_prereq_key(k)]
            other_keys = [k for k in keys if k not in prereq_keys]

            # Reconstruct key order
            new_keys = []
            for k in other_keys:
                if k == "Frequency":
                    new_keys.extend(prereq_keys)  # insert prereqs before Frequency
                new_keys.append(k)

            # Build new ordered dict
            reordered = {k: reorder_keys(d[k]) for k in new_keys}
            return reordered
        else:
            # No Frequency key — recurse only
            return {k: reorder_keys(v) for k, v in d.items()}

    elif isinstance(d, list):
        return [reorder_keys(item) for item in d]

    return d  # primitive types unchanged

def main(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as fin:
        data = json.load(fin)

    reordered_data = reorder_keys(data)

    with open(output_path, 'w', encoding='utf-8') as fout:
        json.dump(reordered_data, fout, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    main("ptu/data/features_core.json", "py/reordered.json")
