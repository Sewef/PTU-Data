#!/usr/bin/env python3
import json, csv, re, argparse, pathlib, difflib

def normalize(s):
    return re.sub(r"\s+", " ", s.strip().lower())

def load_ref(path):
    ref = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            num = int(row["number"])
            name = row["name"]
            aliases = [a.strip() for a in row.get("aliases","").split(";") if a.strip()]
            for key in [name] + aliases:
                ref[normalize(key)] = num
    return ref

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i","--input", required=True, help="JSON d’entrée (parser)")
    ap.add_argument("-r","--ref", required=True, help="CSV référence Pokédex")
    ap.add_argument("-o","--output", required=True, help="JSON de sortie")
    args = ap.parse_args()

    data = json.loads(pathlib.Path(args.input).read_text(encoding="utf-8"))
    ref = load_ref(args.ref)

    for e in data:
        nm = normalize(e.get("Name",""))
        e["Number"] = ref.get(nm, None)  # None si non trouvé

    pathlib.Path(args.output).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"Écrit {args.output} avec {len(data)} fiches")

if __name__ == "__main__":
    main()
