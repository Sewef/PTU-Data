import csv
import os
from pathlib import Path
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

CSV_FILE = "sprites.csv"
OUTPUT_DIR = "sprites"

MAX_WORKERS = 32

session = requests.Session()

for folder in ["front", "back", "mini"]:
    (Path(OUTPUT_DIR) / folder).mkdir(parents=True, exist_ok=True)


def get_extension(url):
    ext = os.path.splitext(urlparse(url).path)[1].lower()

    if ext not in [".png", ".gif", ".jpg", ".jpeg", ".webp"]:
        ext = ".png"

    return ext


def download_file(url, output_path):
    try:
        r = session.get(url, timeout=30)
        r.raise_for_status()

        with open(output_path, "wb") as f:
            f.write(r.content)

        return f"✓ {output_path}"

    except Exception as e:
        return f"✗ {output_path} -> {e}"


jobs = []

with open(CSV_FILE, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)

    for row in reader:
        num = int(row["numero"])

        mapping = [
            ("front_sprite", "front"),
            ("back_sprite", "back"),
            ("mini_sprite", "mini"),
        ]

        for column, folder in mapping:
            url = row[column].strip()

            if not url:
                continue

            ext = get_extension(url)

            output_path = (
                Path(OUTPUT_DIR)
                / folder
                / f"{num:03d}{ext}"
            )

            if output_path.exists():
                continue

            jobs.append((url, output_path))

print(f"{len(jobs)} fichiers à télécharger")


with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = [
        executor.submit(download_file, url, path)
        for url, path in jobs
    ]

    completed = 0

    for future in as_completed(futures):
        completed += 1

        if completed % 50 == 0:
            print(f"{completed}/{len(jobs)}")

        print(future.result())

print("Téléchargement terminé.")