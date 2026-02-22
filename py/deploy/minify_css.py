import os
import sys

try:
    from rcssmin import cssmin
except ImportError:
    print("Installing rcssmin...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "rcssmin"])
    from rcssmin import cssmin

def minify_css_folder(folder):
    folder = folder.rstrip("/\\")
    if not os.path.isdir(folder):
        print(f"Error: '{folder}' is not a directory.")
        return

    for root, _, files in os.walk(folder):
        for filename in files:
            # Skip already minified files
            if not filename.endswith(".css") or filename.endswith(".min.css"):
                continue

            source_path = os.path.join(root, filename)
            dest_filename = filename.replace(".css", ".min.css")
            dest_path = os.path.join(root, dest_filename)

            try:
                with open(source_path, "r", encoding="utf-8") as f:
                    css_content = f.read()

                minified = cssmin(css_content)

                with open(dest_path, "w", encoding="utf-8") as f:
                    f.write(minified)

                print(f"✔ Minified: {source_path} → {dest_path}")

            except Exception as e:
                print(f"❌ Error with '{source_path}': {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python minify_css.py <folder>")
        sys.exit(1)

    minify_css_folder(sys.argv[1])
