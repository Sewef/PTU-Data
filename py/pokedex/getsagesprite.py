import re
import csv
from bs4 import BeautifulSoup

INPUT_HTML = "sagetable.txt"
OUTPUT_CSV = "sprites.csv"


def clean_url(url: str) -> str:
    """
    Transforme :
    https://.../001.png/revision/latest?cb=123
    en :
    https://.../001.png
    """
    return re.sub(r"/revision/latest.*$", "", url)


def extract_timestamp(url: str) -> int:
    """
    Extrait le timestamp du paramètre cb=
    """
    match = re.search(r"cb=(\d+)", url)
    return int(match.group(1)) if match else 0


def newest_image(td):
    """
    Retourne l'URL nettoyée de l'image la plus récente
    de la cellule.
    """
    candidates = []

    for img in td.select("img"):
        src = img.get("data-src") or img.get("src")

        if not src:
            continue

        lower = src.lower()

        # Ignore les icônes de genre
        if "genderm" in lower or "genderf" in lower:
            continue

        candidates.append({
            "timestamp": extract_timestamp(src),
            "url": clean_url(src)
        })

    if not candidates:
        return ""

    newest = max(candidates, key=lambda x: x["timestamp"])
    return newest["url"]


with open(INPUT_HTML, "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f.read(), "html.parser")


rows = []

for tr in soup.select("table.article-table tr"):
    tds = tr.find_all("td")

    if len(tds) < 4:
        continue

    first_td = tds[0]

    link = first_td.find("a")
    if not link:
        continue

    espece = link.get_text(strip=True)

    text = first_td.get_text(" ", strip=True)

    numero_match = re.match(r"(\d+)\.", text)
    if not numero_match:
        continue

    numero = int(numero_match.group(1))

    rows.append({
        "numero": numero,
        "espece": espece,
        "front_sprite": newest_image(tds[1]),
        "back_sprite": newest_image(tds[2]),
        "mini_sprite": newest_image(tds[3]),
    })


rows.sort(key=lambda x: x["numero"])

with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "numero",
            "espece",
            "front_sprite",
            "back_sprite",
            "mini_sprite",
        ]
    )

    writer.writeheader()
    writer.writerows(rows)

print(f"{len(rows)} Pokémon exportés dans {OUTPUT_CSV}")