import json

def load_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def replace_nodes(original_nodes, new_nodes):
    # Create a dictionary for quick lookup of new nodes by 'name'
    new_nodes_dict = {node['name']: node for node in new_nodes}

    # Create a list for the result
    result_nodes = []

    for node in original_nodes:
        node_name = node.get('name')
        # If a matching new node exists, replace it
        if node_name in new_nodes_dict:
            result_nodes.append(new_nodes_dict[node_name])
            # Remove from new_nodes_dict to avoid duplicates if necessary
            del new_nodes_dict[node_name]
        else:
            # Keep original node if no replacement
            result_nodes.append(node)

    # Add any new nodes that didn't match existing ones
    for remaining_node in new_nodes_dict.values():
        result_nodes.append(remaining_node)

    return result_nodes

# File paths
json_file_1 = '8_abilities FULL swsh.json'  # Replace with your first JSON file path
json_file_2 = '9_abilities INC arc.json'  # Replace with your second JSON file path
output_file = '9_abilities FULL arc.json'  # Replace with desired output file path

# Load JSON data
original_data = load_json(json_file_1)
new_data = load_json(json_file_2)

# Assuming the JSON files contain lists of nodes
# If they are nested or differently structured, adjust accordingly
modified_data = replace_nodes(original_data, new_data)

# Save the result
save_json(modified_data, output_file)

print(f"Nodes replaced and saved to {output_file}")
