import json
import os
import sys

def minify_json_folder(folder):
    folder = folder.rstrip("/\\")
    if not os.path.isdir(folder):
        print(f"Error: '{folder}' is not a directory.")
        return

    for root, _, files in os.walk(folder):
        for filename in files:
            if not filename.endswith(".json") or filename.endswith(".min.json"):
                continue

            source_path = os.path.join(root, filename)
            dest_path = os.path.join(root, filename.replace(".json", ".min.json"))

            try:
                with open(source_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                with open(dest_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, separators=(",", ":"))

                print(f"✔ Minified: {source_path} → {dest_path}")

            except Exception as e:
                print(f"❌ Error with '{source_path}': {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python minify_json.py <folder>")
        sys.exit(1)

    minify_json_folder(sys.argv[1])
