import json

def remove_nodes_by_names(json_data, names_to_remove):
    """
    Recursively remove nodes with 'name' field matching any in names_to_remove.
    """
    if isinstance(json_data, dict):
        # If current node is a dict, process its keys
        return {
            key: remove_nodes_by_names(value, names_to_remove)
            for key, value in json_data.items()
        }
    elif isinstance(json_data, list):
        # If current node is a list, process each item
        return [
            remove_nodes_by_names(item, names_to_remove)
            for item in json_data
        ]
    else:
        # If current node is a primitive, check if it's a dict with 'name'
        # This case is covered above; primitives are returned as is
        return json_data

def filter_json_by_names(json_data, names_to_remove):
    """
    Remove all nodes with 'name' matching names_to_remove.
    """
    if isinstance(json_data, dict):
        # Check if this dict has a 'name' field that matches
        if 'name' in json_data and json_data['name'] in names_to_remove:
            return None  # Remove this node
        # Else, process its children
        filtered_dict = {}
        for key, value in json_data.items():
            result = filter_json_by_names(value, names_to_remove)
            if result is not None:
                filtered_dict[key] = result
        return filtered_dict
    elif isinstance(json_data, list):
        # Process list items, exclude items that are None
        filtered_list = []
        for item in json_data:
            result = filter_json_by_names(item, names_to_remove)
            if result is not None:
                filtered_list.append(result)
        return filtered_list
    else:
        # Primitive data type
        return json_data

# Example usage:

# Define the list of names to remove
names_to_remove = ["Aqua Boost", "Ignition Boost", "Thunder Boost", "Fairy Aura", "Dark Aura", "Instinct", "Daze", "Gulp", "Photosynthesis", "Covert", "Wave Rider", "Berry Storage", "Delivery Bird", "Tingly Tongue", "Run Up", "Fashion Designer", "Gardener", "Twisted Power"]  # replace with your list

# Read input JSON file
with open('input.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Remove nodes with specified names
filtered_data = filter_json_by_names(data, set(names_to_remove))

# Write the filtered JSON back to a file
with open('output.json', 'w', encoding='utf-8') as f:
    json.dump(filtered_data, f, ensure_ascii=False, indent=4)
