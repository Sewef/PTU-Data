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

def insert_after_species(e: OrderedDict, key: str, number_val):
    """
    e: entrée (OrderedDict)
    key: "Species" ou "Specie"
    number_val: valeur à mettre dans Number
    Retourne un OrderedDict avec Number juste après la clé 'key'
    """
    # enlever Number s'il existe déjà
    e.pop("Number", None)

    new_e = OrderedDict()
    inserted = False
    for k, v in e.items():
        new_e[k] = v
        if not inserted and k == key:
            new_e["Number"] = number_val
            inserted = True
    if not inserted:  # fallback si pas de clé espèce
        new_e["Number"] = number_val
    return new_e

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i","--input", required=True, help="JSON d’entrée (parser)")
    ap.add_argument("-r","--ref", required=True, help="CSV référence Pokédex")
    ap.add_argument("-o","--output", required=False, help="JSON de sortie")
    args = ap.parse_args()

    if not args.output:
        args.output = args.input

    # Charger le JSON en préservant l'ordre des paires
    raw = pathlib.Path(args.input).read_text(encoding="utf-8")
    data = json.loads(raw, object_pairs_hook=OrderedDict)

    ref = load_ref(args.ref)

    # Traiter chaque entrée
    out = []
    for e in data:
        # clé espèce tolérante
        species_key = "Species" if "Species" in e else ("Specie" if "Specie" in e else None)

        nm = normalize(e.get("Species", e.get("Specie", "")))
        number = ref.get(nm, None)  # None si non trouvé

        if species_key:
            e = insert_after_species(e, species_key, number)
        else:
            # pas de clé espèce -> juste assurer Number présent (fin de dict)
            e.pop("Number", None)
            e["Number"] = number

        out.append(e)

    # Écrire sans trier les clés (ordre préservé tel qu’inséré)
    pathlib.Path(args.output).write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"Écrit {args.output} avec {len(out)} fiches")

if __name__ == "__main__":
    main()
