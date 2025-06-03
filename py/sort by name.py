import json

# Replace with your JSON filename
input_file = '10_moves FULL 9G.json'
output_file = '10_moves FULL 9G.json'

# Read the JSON data
with open(input_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Ensure the data is a list of dictionaries
if isinstance(data, list):
    # Sort by 'name' key, considering UTF-8 order
    data_sorted = sorted(data, key=lambda x: x.get('name', ''))
else:
    raise ValueError("JSON data is not a list of objects.")

# Write the sorted data back to a new JSON file
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(data_sorted, f, ensure_ascii=False, indent=4)

print(f"Sorted data written to {output_file}")
