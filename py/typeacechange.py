import json

def wrap_features_block(data, section_keys):
    """
    For each section key in section_keys (e.g., "Stat Ace", "Style Expert"),
    wrap each subtype under "Features" in a new "Features" block,
    mirroring the structure used for "Researcher".
    """
    for section in section_keys:
        section_data = data.get(section, {})
        original_features = section_data.get("Features", {})
        transformed_features = {}

        for subtype, content in original_features.items():
            # Wrap the existing content in a "Features" block
            transformed_features[subtype] = {
                "Features": content
            }

        # Update the section with transformed Features
        section_data["Features"] = transformed_features
        data[section] = section_data

    return data

# Example usage:
# Load your JSON data from a file or a variable
with open("py/typeace.json", "r", encoding="utf-8") as infile:
    data = json.load(infile)

# Specify the sections you want to transform
sections_to_transform = ["Researcher"]

# Apply the transformation
transformed_data = wrap_features_block(data, sections_to_transform)

# Save the transformed data back to a file
with open("py/typeace.json", "w", encoding="utf-8") as outfile:
    json.dump(transformed_data, outfile, ensure_ascii=False, indent=2)

print("Transformation complete!")
