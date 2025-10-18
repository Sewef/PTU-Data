#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import json
import math
from pathlib import Path
from collections import defaultdict

CSV2JSON_STAT = {
    "hp": "HP",
    "att": "Attack",
    "def": "Defense",
    "spa": "Special Attack",
    "spd": "Special Defense",
    "spe": "Speed",
}

SPECIAL_NAME_FIX = {
    "farfetch'd": "farfetchd",
    "mr mime": "mr-mime",
    "mime jr": "mime-jr",
    "type: null": "type-null",
    "nidoran♀": "nidoran-f",
    "nidoran♂": "nidoran-m",
}

def norm_name(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("’", "'").replace("é", "e")
    for ch in ".:()":
        s = s.replace(ch, "")
    s = " ".join(s.split())
    s = s.replace(" ", "-").replace("'", "")
    return SPECIAL_NAME_FIX.get(s, s)

def round_ptu(x: float) -> int:
    frac = x - math.floor(x)
    return math.ceil(x) if frac > 0.5 else math.floor(x)

def load_final_stats_from_csv(csv_path: Path):
    """
    Lit le CSV (gen,name,stat,old,new,delta) et garde pour chaque (name,stat)
    la valeur 'new' du gen le plus récent (7/8/9).
    Retourne:
      final_stats[name_norm][json_stat_key] = final_new_int
      csv_names_map[name_norm] = dernier_nom_brut rencontré (pour logs)
    """
    best_by_key = {}  # (name_norm, json_stat_key) -> (gen, new_int)
    csv_names_map = {}  # name_norm -> display/original (pour log lisible)

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                gen = int(row.get("gen") or 0)
                name_raw = (row.get("name") or "").strip()
                stat = (row.get("stat") or "").strip().lower()
                new_val = int(row.get("new") or 0)
            except Exception:
                continue
            if not name_raw or stat not in CSV2JSON_STAT:
                continue

            name_key = norm_name(name_raw)
            json_stat_key = CSV2JSON_STAT[stat]
            key = (name_key, json_stat_key)

            prev = best_by_key.get(key)
            if prev is None or gen > prev[0]:
                best_by_key[key] = (gen, new_val)

            # conserve le nom brut "le plus récent" pour affichage
            csv_names_map[name_key] = name_raw

    final_stats = defaultdict(dict)
    for (name_key, json_stat_key), (_, new_val) in best_by_key.items():
        final_stats[name_key][json_stat_key] = new_val
    return final_stats, csv_names_map

def discover_json_files(root: Path):
    return [p for p in root.rglob("*.json") if p.is_file()]

def update_entry(entry: dict, species_map: dict, matched: set) -> int:
    """Met à jour une entrée (un Pokémon) si le nom matche. Retourne nb de champs modifiés."""
    if not isinstance(entry, dict):
        return 0
    species = (entry.get("Species") or "").strip()
    if not species:
        return 0

    name_key = norm_name(species)
    if name_key not in species_map:
        return 0

    # ✅ Marquer comme trouvé dès qu'on a une correspondance de nom
    matched.add(name_key)

    base = entry.get("Base Stats")
    if not isinstance(base, dict):
        return 0

    updates = 0
    for stat_key, final_new in species_map[name_key].items():
        ptu_val = round_ptu(final_new / 10.0)
        if base.get(stat_key) != ptu_val:
            base[stat_key] = ptu_val
            updates += 1
    return updates


def inject_into_file(fp: Path, species_map: dict, matched: set, dry_run=False, backup=False):
    """
    Ouvre fp et injecte, que la racine soit un dict (1 entrée) ou une liste (n entrées).
    Retourne (fichier_scanné, nb_champs_modifiés, fichier_modifié_bool)
    """
    try:
        raw = fp.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception:
        print(f"[skip] {fp} (JSON illisible)")
        return 1, 0, False

    total_updates = 0
    changed = False

    if isinstance(data, list):
        for entry in data:
            total_updates += update_entry(entry, species_map, matched)
        changed = total_updates > 0
    elif isinstance(data, dict):
        total_updates += update_entry(data, species_map, matched)
        changed = total_updates > 0
    else:
        return 1, 0, False

    if changed and not dry_run:
        if backup:
            bak = fp.with_suffix(fp.suffix + ".bak")
            try:
                if not bak.exists():
                    bak.write_text(raw, encoding="utf-8")
            except Exception:
                pass
        fp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    return 1, total_updates, changed

def main():
    ap = argparse.ArgumentParser(description="Injecte les stats finales (CSV fooextra) dans des pokedex.json")
    ap.add_argument("--csv", required=True, help="CSV (gen,name,stat,old,new,delta)")
    ap.add_argument("--root", required=True, help="Racine du dossier des pokedex.json (récursif)")
    ap.add_argument("--dry-run", action="store_true", help="N'écrit rien (aperçu)")
    ap.add_argument("--backup", action="store_true", help="Crée un .bak avant d'écrire")
    ap.add_argument("--log-missing", default="missing_species.txt", help="Fichier de log des espèces non trouvées")
    args = ap.parse_args()

    species_final, csv_names_map = load_final_stats_from_csv(Path(args.csv))
    if not species_final:
        print("[warn] Aucune stat finale détectée dans le CSV.")
        return

    files = discover_json_files(Path(args.root))
    scanned = 0
    changed_files = 0
    changed_fields = 0
    matched_species = set()

    for fp in files:
        s, u, ch = inject_into_file(fp, species_final, matched_species, dry_run=args.dry_run, backup=args.backup)
        scanned += s
        changed_fields += u
        if ch:
            changed_files += 1

    # Log des espèces non trouvées
    wanted = set(species_final.keys())
    missing = sorted(wanted - matched_species)
    if missing:
        # map vers noms bruts lisibles pour le log
        display_missing = [csv_names_map.get(k, k) for k in missing]
        Path(args.log_missing).write_text("\n".join(display_missing), encoding="utf-8")
        print(f"[info] espèces NON trouvées: {len(display_missing)} (voir {args.log_missing})")
        # Affiche un aperçu (les 10 premières)
        preview = ", ".join(display_missing[:10])
        if len(display_missing) > 10:
            preview += ", …"
        print(f"       ex: {preview}")
    else:
        print("[info] Toutes les espèces du CSV ont été trouvées.")

    print(f"[done] fichiers scannés: {scanned} | fichiers modifiés: {changed_files} | champs changés: {changed_fields}")
    if args.dry_run:
        print("(dry-run: aucune écriture)")

if __name__ == "__main__":
    main()
