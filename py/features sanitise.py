import json

def flatten_dict(obj):
    """
    Flattens a dict or list into a string of key=value pairs separated by semicolons.
    """
    if isinstance(obj, dict):
        return ', '.join(f"{k}={flatten_dict(v)}" for k, v in obj.items())
    elif isinstance(obj, list):
        return ', '.join(flatten_dict(i) for i in obj)
    else:
        return str(obj)

def inline_after_depth(obj, current_depth=0, max_depth=3):
    """
    Recursively serialize JSON object.
    After reaching max_depth, serialize sub-objects as a string of all child keys with their value.
    """
    if current_depth >= max_depth:
        # Properly escape the flattened string for JSON
        return json.dumps(flatten_dict(obj))
    
    if isinstance(obj, dict):
        items = []
        for k, v in obj.items():
            serialized_value = inline_after_depth(v, current_depth + 1, max_depth)
            items.append(f'"{k}": {serialized_value}')
        return '{' + ', '.join(items) + '}'
    elif isinstance(obj, list):
        items = [inline_after_depth(i, current_depth + 1, max_depth) for i in obj]
        return '[' + ', '.join(items) + ']'
    else:
        return json.dumps(obj)

def pretty_print_json_with_inline(filename, max_depth=3):
    with open(filename, 'r') as f:
        data = json.load(f)

    result = inline_after_depth(data, current_depth=0, max_depth=max_depth)
    parsed = json.loads(result)
    print(json.dumps(parsed, indent=4))

if __name__ == "__main__":
    import sys
    filename = sys.argv[1] if len(sys.argv) > 1 else 'py/features_core.json'
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'py/output.json'

    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)

    result = inline_after_depth(data, current_depth=0, max_depth=3)
    parsed = json.loads(result)

    with open(output_file, 'w', encoding='utf-8') as out_f:
        json.dump(parsed, out_f, indent=4, ensure_ascii=False)
