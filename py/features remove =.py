import re

def replace_equals_with_space_in_prerequisites(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = f.read()

    # Replace all '=' with space in lines containing "Prerequisites"
    def replacer(match):
        key, value = match.groups()
        new_value = value.replace('Skills ', '')
        return f'{key}"{new_value}"'

    pattern = r'("Prerequisites"\s*:\s*)"([^"]*)"'
    new_data = re.sub(pattern, replacer, data)

    with open(json_path, 'w', encoding='utf-8') as f:
        f.write(new_data)

# Example usage:
replace_equals_with_space_in_prerequisites('py/output.json')
