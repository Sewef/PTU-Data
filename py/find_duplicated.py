import json
from collections import Counter

# Load JSON data from file
with open("./ptu/data/abilities/abilities_homebrew.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Extract all "Name" values
names = [obj.get("Name") for obj in data if "Name" in obj]

# Count occurrences
counts = Counter(names)

# Find duplicates
duplicates = {name: count for name, count in counts.items() if count > 1}

print("Duplicate 'Name' fields:")
for name, count in duplicates.items():
    print(f"{name} → {count} times")
