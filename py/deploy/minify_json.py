import json
import os
import sys

def minify_json_folder(folder, force=False):
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

            if (
                not force
                and os.path.exists(dest_path)
                and os.path.getmtime(dest_path) >= os.path.getmtime(source_path)
            ):
                continue

            try:
                with open(source_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Pretty format the source file
                with open(source_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                # Create minified version
                with open(dest_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, separators=(",", ":"), ensure_ascii=False)

                print(f"[OK] Formatted & minified: {source_path} -> {dest_path}")

            except Exception as e:
                print(f"[ERROR] Error with '{source_path}': {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python minify_json.py <folder> [--force]")
        sys.exit(1)

    minify_json_folder(sys.argv[1], force="--force" in sys.argv[2:])
