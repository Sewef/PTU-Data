import json

def filter_nodes(node):
    """
    Recursively filter nodes: keep only nodes that have 'set_up_effect' field,
    and process nested children if present.
    """
    if isinstance(node, dict):
        # Check if current node has 'set_up_effect'
        if 'set_up_effect' in node:
            # If node has children, filter them
            if 'children' in node:
                node['children'] = [filter_nodes(child) for child in node['children']]
            return node
        else:
            # Node without 'set_up_effect' is omitted
            return None
    elif isinstance(node, list):
        # For list of nodes, filter each
        return [filter_nodes(item) for item in node if filter_nodes(item) is not None]
    else:
        # For other types (should not occur if JSON is structured as expected)
        return node

def main(input_file, output_file):
    # Read JSON data from file
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Filter data
    filtered_data = filter_nodes(data)

    # Write filtered data to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(filtered_data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    input_json = 'moves_extraits.json'   # Replace with your input file path
    output_json = 'setup moves.json' # Replace with your desired output file path
    main(input_json, output_json)
