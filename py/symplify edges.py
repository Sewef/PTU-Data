import json

def simplify_json(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    simplified = {}

    for key, entry in data.items():
        new_entry = {}

        # Move "description" to "Description"
        if "description" in entry:
            new_entry["Description"] = entry["description"]

        # Extract fields into top-level
        for field in entry.get("fields", []):
            field_name = field.get("name")
            field_value = field.get("value")
            if field_name and field_value:
                new_entry[field_name] = field_value

        # Only include the simplified structure
        simplified[key] = new_entry

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(simplified, f, indent=4, ensure_ascii=False)

# Example usage:
simplify_json("py/edge.json", "py/outputedge.json")
