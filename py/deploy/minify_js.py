import os
import sys

try:
    from rjsmin import jsmin
except ImportError:
    print("Installing rjsmin...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "rjsmin"])
    from rjsmin import jsmin

def minify_js_folder(folder):
    folder = folder.rstrip("/\\")
    if not os.path.isdir(folder):
        print(f"Error: '{folder}' is not a directory.")
        return

    for root, _, files in os.walk(folder):
        for filename in files:
            # Skip already minified files
            if not filename.endswith(".js") or filename.endswith(".min.js"):
                continue

            source_path = os.path.join(root, filename)
            dest_filename = filename.replace(".js", ".min.js")
            dest_path = os.path.join(root, dest_filename)

            try:
                with open(source_path, "r", encoding="utf-8") as f:
                    js_content = f.read()

                minified = jsmin(js_content)

                with open(dest_path, "w", encoding="utf-8") as f:
                    f.write(minified)

                print(f"✔ Minified: {source_path} → {dest_path}")

            except Exception as e:
                print(f"❌ Error with '{source_path}': {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python minify_js.py <folder>")
        sys.exit(1)

    minify_js_folder(sys.argv[1])
