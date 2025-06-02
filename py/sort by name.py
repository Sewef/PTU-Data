import json

# Replace 'input.json' with your JSON filename
input_file = 'moves.json'
output_file = 'sorted_output.json'

# Load the JSON data
with open(input_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Ensure data is a list of dictionaries
if isinstance(data, list):
    # Sort the list by the 'name' key
    sorted_data = sorted(data, key=lambda x: x.get('name', ''))
else:
    print("JSON data is not a list of objects.")

# Save the sorted data to a new file
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(sorted_data, f, indent=4)

print(f"JSON data sorted by 'name' and saved to {output_file}")