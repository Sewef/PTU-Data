import json
import re

def extract_rank_data(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    output = {}
    pattern = re.compile(r"Rank \d+ (Prerequisites|Effect)", re.IGNORECASE)

    for key, value in data.items():
        fields = value.get("fields", [])
        extracted = {}

        for field in fields:
            name = field.get("name", "")
            value = field.get("value", "")
            if pattern.fullmatch(name):
                extracted[name] = value

        if extracted:
            output[key] = extracted

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

# Example usage
extract_rank_data("py/input.json", "py/output.json")
