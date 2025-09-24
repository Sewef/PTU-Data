#!/usr/bin/env python3
import json, csv, re, argparse, pathlib
from collections import OrderedDict

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

    # Charger en OrderedDict pour préserver l'ordre à tous les niveaux
    raw = pathlib.Path(args.input).read_text(encoding="utf-8")
    data = json.loads(raw, object_pairs_hook=OrderedDict)

    ref = load_ref(args.ref)

    from collections import OrderedDict

    for i, e in enumerate(data):
        nm = normalize(e.get("Species", e.get("Specie", "")))
        number = ref.get(nm, None)

        # 1) clé d'espèce tolérante ("Species" ou "Specie")
        species_key = "Species" if "Species" in e else ("Specie" if "Specie" in e else None)

        # 2) enlever Number existant
        e.pop("Number", None)

        # 3) reconstruire l'entrée en imposant l'ordre
        new_e = OrderedDict()
        inserted = False
        for k, v in e.items():
            new_e[k] = v
            if species_key and k == species_key and not inserted:
                new_e["Number"] = number
                inserted = True
        if not inserted:
            # Pas de Species/Specie : on met Number en fin (fallback)
            new_e["Number"] = number

        # 4) remplacer l'objet en place
        data[i] = new_e


    pathlib.Path(args.output).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"Écrit {args.output} avec {len(data)} fiches")

if __name__ == "__main__":
    main()
