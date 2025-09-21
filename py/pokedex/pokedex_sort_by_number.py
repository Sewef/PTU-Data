import json

# Replace with your JSON filename
input_file = 'pokedex_numbered.json'
#output_file = 'work files/8_moves FULL swsh.json'
output_file = 'pokedex_orderbynumber.json'

# Read the JSON data
with open(input_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Ensure the data is a list of dictionaries
if isinstance(data, list):
    # Sort by 'Number' key as integer, handling None or missing values
    data_sorted = sorted(data, key=lambda x: int(x.get('Number') or 0))
else:
    raise ValueError("JSON data is not a list of objects.")

# Write the sorted data back to a new JSON file
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(data_sorted, f, ensure_ascii=False, indent=4)

print(f"Sorted data written to {output_file}")
