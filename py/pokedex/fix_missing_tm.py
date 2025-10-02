#!/usr/bin/env python3
# merge_tmhm.py
import json
import argparse
from pathlib import Path

TM_KEYS_SOURCE_PRIORITY = [
    "TM/HM Move List",   # clé standard
    "TM Move List",      # variante simplifiée rencontrée sur certains PDFs
]

def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
        if not isinstance(data, list):
            raise ValueError(f"{path} doit contenir une liste d'objets Pokémon.")
        return data

def index_by_species(records):
    return {rec.get("Species"): rec for rec in records if rec.get("Species")}

def get_tm_list_from_source(src_moves: dict):
    """Retourne (liste_tm, key_trouvée) depuis la source, ou (None, None) si rien d’utile."""
    if not isinstance(src_moves, dict):
        return None, None
    for key in TM_KEYS_SOURCE_PRIORITY:
        val = src_moves.get(key)
        if isinstance(val, list) and len(val) > 0:
            return val, key
    return None, None

def get_tm_list_from_dest(dest_moves: dict):
    """Retourne la liste TM/HM de la destination (même si vide), et crée la clé si absente."""
    if not isinstance(dest_moves, dict):
        return None
    if "TM/HM Move List" not in dest_moves:
        dest_moves["TM/HM Move List"] = []
    return dest_moves["TM/HM Move List"]

def main():
    ap = argparse.ArgumentParser(description="Copie TM/HM Move List de source vers destination si vide.")
    ap.add_argument("source", help="JSON source (liste de Pokémon)")
    ap.add_argument("destination", help="JSON destination (liste de Pokémon)")
    ap.add_argument("-o", "--out", help="Fichier de sortie (par défaut, écrase la destination).", default=None)
    ap.add_argument("--dry-run", action="store_true", help="Ne pas écrire, juste rapporter.")
    args = ap.parse_args()

    src_path = Path(args.source)
    dst_path = Path(args.destination)
    out_path = Path(args.out) if args.out else dst_path

    source = load_json(src_path)
    dest = load_json(dst_path)
    src_index = index_by_species(source)

    updated = 0
    already_filled = 0
    not_found = []

    for drec in dest:
        species = drec.get("Species")
        if not species:
            continue

        srec = src_index.get(species)
        if not srec:
            not_found.append(species)
            continue

        src_moves = srec.get("Moves", {})
        src_tm_list, src_key = get_tm_list_from_source(src_moves)
        if not src_tm_list:
            print(f"[WARN] Aucun TM/HM trouvé dans la source pour {species}")
            continue

        d_moves = drec.setdefault("Moves", {})
        dst_tm_list = get_tm_list_from_dest(d_moves)

        if isinstance(dst_tm_list, list) and len(dst_tm_list) == 0:
            d_moves["TM/HM Move List"] = list(src_tm_list)
            updated += 1
            print(f"[OK] Copié TM/HM Move List pour {species} (depuis {src_key})")
        else:
            already_filled += 1
            print(f"[SKIP] {species} déjà rempli")

    # Rapport global
    print("\n=== RAPPORT ===")
    print(f"Espèces mises à jour : {updated}")
    print(f"Déjà renseignées     : {already_filled}")
    print(f"Pas trouvées dans la source : {len(not_found)}")

    if not_found:
        print("Liste des espèces pas trouvées :")
        for sp in not_found:
            print(" -", sp)

    if not args.dry_run:
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(dest, f, ensure_ascii=False, indent=2)
        print(f"\nÉcrit dans : {out_path}")
    else:
        print("\nDry-run : aucun fichier écrit.")

if __name__ == "__main__":
    main()
