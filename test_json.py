import json
from pathlib import Path

def update_json_icons(obj, mappings):
    """Recursively traverse JSON object and replace icon IDs."""
    replacements = 0
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "Icon" and isinstance(value, int):
                # Found an Icon field with integer value
                old_id = str(value)
                if old_id in mappings:
                    obj[key] = mappings[old_id]
                    replacements += 1
            elif isinstance(value, (dict, list)):
                replacements += update_json_icons(value, mappings)
    
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                replacements += update_json_icons(item, mappings)
    
    return replacements

# Test
mappings = {'10033': '3-mega'}
test_obj = {
    "Icon": 10033,
    "Name": "test"
}

print(f"Before: {test_obj}")
count = update_json_icons(test_obj, mappings)
print(f"After: {test_obj}")
print(f"Replacements: {count}")
