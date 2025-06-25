import json

def extract_prerequisites(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    output = {}
    for key, value in data.items():
        fields = value.get("fields", [])
        prereq = next((field["value"] for field in fields if field.get("name") == "Prerequisites"), None)
        if prereq:
            output[key] = {"Prerequisites": prereq}

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=4)

# Example usage
extract_prerequisites("py/input.json", "py/output.json")
