import json
import sys

def insert_trigger_after_frequency(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Process each dictionary to insert 'trigger' after 'frequency'
    for entry in data:
        if 'frequency' in entry and 'trigger' in entry:
            # Create a new ordered dict with 'trigger' after 'frequency'
            new_entry = {}
            for key in entry:
                new_entry[key] = entry[key]
                if key == 'frequency':
                    # Insert 'trigger' after 'frequency'
                    new_entry['trigger'] = entry['trigger']  # Keep existing trigger value
            # Now, replace the old entry with the new one
            entry.clear()
            entry.update(new_entry)
        else:
            # If 'frequency' is present but 'trigger' is absent, do nothing
            pass

    # Write back to the same file (overwrite)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python insert_trigger.py <path_to_json_file>")
    else:
        file_path = sys.argv[1]
        insert_trigger_after_frequency(file_path)
        print(f"Updated file: {file_path}")