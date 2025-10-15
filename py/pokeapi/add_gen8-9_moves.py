#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Réintègre les moves supprimés (removed_moves_g8_to_g9.csv) dans un pokedex.json,
en s'appuyant sur un mapping PokeAPI <-> nom du dex.

Règles:
- Tout move ajouté reçoit le tag "Deleted".
- lvl == 0  -> Level "Evo" (Level Up Move List).
- lvl == 1 ET Stade d'évolution > 1 -> ajouter dans TM/Tutor Moves List (pas en level-up)
  avec le tag "N" en plus de "Deleted".
- Type & damage class (physical/special/status) récupérés via PokeAPI (/api/v2/move/{move}).
- Si damage class != status ET move.type ∈ {types du Pokémon} -> ajouter tag "Stab".
- Pas de doublon si le move est déjà présent dans la fiche.

Entrées attendues:
- pokedex.json (liste d'objets d'espèces, clé "Species")
- mapping.csv avec au moins 2 colonnes: "pokeapi","dex"
- removed_moves.csv avec au moins: "pokemon","move","left_min_level"

Sortie:
- pokedex_patched.json (par défaut) + rapport CSV des insertions (optionnel)

Usage:
  python reintegrate_removed_moves.py \
    --pokedex pokedex_core.json \
    --mapping mapping.csv \
    --removed removed_moves_g8_to_g9.csv \
    --out pokedex_patched.json \
    --report added_report.csv \
    --workers 12
"""

import argparse
import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import requests

POKEAPI_MOVE_BASE = "https://pokeapi.co/api/v2/move/"
TIMEOUT = 30

# ----------------------------
# Utilitaires de normalisation
# ----------------------------

def humanize_move_name(move_api: str) -> str:
    """pokeapi 'flame-burst' -> 'Flame Burst' (style du dex)."""
    return move_api.replace('-', ' ').title()

def dehumanize_move_name(move_title: str) -> str:
    """dex 'Flame Burst' -> 'flame-burst' (pour PokeAPI)."""
    return move_title.strip().lower().replace(' ', '-')

def normalize_species_name(s: str) -> str:
    return s.strip()

# ----------------------------
# Chargement des données
# ----------------------------

def load_pokedex(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def load_mapping(path: Path) -> Dict[str, str]:
    """
    Retourne un dict: pokeapi_name -> dex_species_name
    Compatible avec:
      - en-têtes 'pokeapi','dex' (CSV virgule)
      - en-têtes 'species','othername' (CSV point-virgule)
      - variants/aliases usuels.
    Détection auto du délimiteur (',', ';', tab).
    """
    # --- détecter le délimiteur ---
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            # fallback simple: s'il y a plus de ';' que de ',', utiliser ';'
            delim = ";" if sample.count(";") > sample.count(",") else ","
            class _D(csv.Dialect):
                delimiter = delim
                quotechar = '"'
                doublequote = True
                skipinitialspace = False
                lineterminator = "\n"
                quoting = csv.QUOTE_MINIMAL
            dialect = _D()

        reader = csv.DictReader(f, dialect=dialect)
        if not reader.fieldnames:
            raise ValueError("mapping.csv: en-têtes introuvables")

        # mappe les colonnes en lower pour être tolérant
        header_lc = {h.lower(): h for h in reader.fieldnames}

        # Alias possibles
        api_candidates = ["pokeapi", "pokeapi_name", "othername", "api", "slug"]
        dex_candidates = ["dex", "dex_name", "species", "name"]

        col_api = next((header_lc[c] for c in api_candidates if c in header_lc), None)
        col_dex = next((header_lc[c] for c in dex_candidates if c in header_lc), None)

        if not col_api or not col_dex:
            raise ValueError(
                f"mapping.csv: colonnes attendues non trouvées. "
                f"Présentes: {reader.fieldnames}. "
                f"Accepte p.ex. 'species;othername' ou 'pokeapi,dex'."
            )

        mapping: Dict[str, str] = {}
        for row in reader:
            api = (row.get(col_api) or "").strip()
            dex = (row.get(col_dex) or "").strip()
            if api:
                mapping[api] = dex
        return mapping


def load_removed(path: Path) -> List[dict]:
    """
    Lit removed_moves csv (colonnes minimales: pokemon, move, left_min_level).
    Retourne une liste de dicts homogènes.
    """
    rows = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = {c.lower(): c for c in reader.fieldnames or []}
        col_p = cols.get("pokemon") or "pokemon"
        col_m = cols.get("move") or "move"
        col_lvl = cols.get("left_min_level") or cols.get("level") or "left_min_level"
        for r in reader:
            pokemon = r[col_p].strip()
            move_api = r[col_m].strip().lower()
            lvl_raw = (r.get(col_lvl, "") or "").strip()
            try:
                lvl = int(lvl_raw)
            except Exception:
                # si vide ou invalide, considérer None
                lvl = None
            rows.append({"pokemon": pokemon, "move_api": move_api, "level": lvl})
    return rows

# ----------------------------
# Accès PokeAPI (moves)
# ----------------------------

def fetch_move_info(move_api_name: str) -> Optional[Tuple[str, str]]:
    """
    Retourne (type_name, damage_class) en minuscules pour le move,
    ex: ('fire', 'special') ; None si non trouvé.
    """
    url = f"{POKEAPI_MOVE_BASE}{move_api_name}"
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        j = resp.json()
        mtype = (j.get("type", {}) or {}).get("name")
        dmgc = (j.get("damage_class", {}) or {}).get("name")
        if mtype and dmgc:
            return mtype.lower(), dmgc.lower()
        return None
    except Exception:
        return None

def fetch_moves_info_parallel(move_names: List[str], workers: int = 12) -> Dict[str, Optional[Tuple[str, str]]]:
    """
    move_names: liste de noms PokeAPI ('flame-burst')
    Retourne dict move_api -> (type, damage_class) ou None.
    """
    unique = sorted(set(move_names))
    out: Dict[str, Optional[Tuple[str, str]]] = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fetch_move_info, m): m for m in unique}
        for fut in as_completed(futs):
            m = futs[fut]
            try:
                out[m] = fut.result()
            except Exception:
                out[m] = None
    return out

# ----------------------------
# Opérations sur le Pokédex
# ----------------------------

def species_stage(spec: dict) -> int:
    """
    Détermine le 'Stade' de l'espèce dans son propre tableau Evolution.
    Si introuvable -> 1 par défaut.
    """
    evo = spec.get("Evolution") or []
    name = spec.get("Species", "")
    for step in evo:
        if normalize_species_name(step.get("Species", "")) == name:
            try:
                return int(step.get("Stade", 1))
            except Exception:
                return 1
    return 1

def species_types(spec: dict) -> List[str]:
    """
    Retourne la liste des types (majuscules initiales, ex: 'Grass','Poison')
    telle que stockée dans le dex.
    """
    types = ((spec.get("Basic Information") or {}).get("Type") or [])
    # normaliser en lower pour comparaison simple
    return [t.strip() for t in types]

def move_entry_exists_levelup(levelup_list: List[dict], move_title: str) -> bool:
    mt = move_title
    for e in levelup_list:
        if e.get("Move") == mt:
            return True
    return False

def move_entry_exists_tmtutor(tmlist: List[dict], move_title: str) -> bool:
    mt = move_title
    for e in tmlist:
        if e.get("Move") == mt:
            return True
    return False

def ensure_tags_list(d: dict) -> None:
    if "Tags" not in d or d["Tags"] is None:
        d["Tags"] = []

def add_tag(d: dict, tag: str) -> None:
    ensure_tags_list(d)
    if tag not in d["Tags"]:
        d["Tags"].append(tag)

# ----------------------------
# Pipeline principal
# ----------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pokedex", required=True, help="pokedex.json d'entrée")
    ap.add_argument("--mapping", required=True, help="mapping.csv (colonnes: pokeapi,dex)")
    ap.add_argument("--removed", required=True, help="removed_moves_g8_to_g9.csv")
    ap.add_argument("--out", default="pokedex_patched.json", help="fichier json de sortie")
    ap.add_argument("--report", default=None, help="csv rapport des insertions (optionnel)")
    ap.add_argument("--workers", type=int, default=12, help="concurrence pour PokeAPI (défaut: 12)")
    args = ap.parse_args()

    pokedex_path = Path(args.pokedex)
    mapping_path = Path(args.mapping)
    removed_path = Path(args.removed)
    out_path = Path(args.out)
    report_path = Path(args.report) if args.report else None

    # Charger données
    dex = load_pokedex(pokedex_path)
    mapping = load_mapping(mapping_path)  # pokeapi -> dex
    removed_rows = load_removed(removed_path)

    # Indexer le dex par nom d'espèce
    by_species: Dict[str, dict] = {
        normalize_species_name(sp.get("Species", "")): sp for sp in dex
    }

    # Préparer la liste des moves à requêter (PokeAPI)
    all_moves_api = [r["move_api"] for r in removed_rows]
    move_meta = fetch_moves_info_parallel(all_moves_api, workers=args.workers)

    # Rapport des ajouts
    report_rows: List[dict] = []

    # Traitement de chaque suppression
    for r in removed_rows:
        pokeapi_name = r["pokemon"]              # ex: 'charmander'
        move_api = r["move_api"]                 # ex: 'flame-burst'
        lvl = r["level"]                         # int ou None
        move_title = humanize_move_name(move_api)

        # Trouver le nom dans le dex via mapping
        dex_name = mapping.get(pokeapi_name)
        if not dex_name:
            print(f"[WARN] mapping manquant pour '{pokeapi_name}' -> move '{move_title}' ignoré", file=sys.stderr)
            continue

        spec = by_species.get(dex_name)
        if not spec:
            print(f"[WARN] espèce '{dex_name}' introuvable dans le dex (depuis mapping)", file=sys.stderr)
            continue

        # Récup types du move via PokeAPI
        meta = move_meta.get(move_api)
        if not meta:
            print(f"[WARN] meta PokeAPI manquante pour move '{move_api}'", file=sys.stderr)
            continue
        move_type_api, dmg_class = meta  # ex ('fire','special')

        # Types du Pokémon (du dex), pour STAB
        sp_types = species_types(spec)  # ex: ['Grass','Poison']
        sp_types_lower = {t.lower() for t in sp_types}

        # Préparer structures de listes
        moves_section = spec.setdefault("Moves", {})
        lvlup_list: List[dict] = moves_section.setdefault("Level Up Move List", [])
        tmtutor_list: List[dict] = moves_section.setdefault("TM/Tutor Moves List", [])

        # Déterminer où insérer selon règles
        stage = species_stage(spec)

        # Construire tags pour l'entrée à ajouter
        tags: List[str] = []
        # STAB si physical/special et type ∈ types du Pokémon
        if dmg_class in ("physical", "special") and move_type_api in sp_types_lower:
            tags.append("Stab")
        tags.append("Deleted")

        # 1) Cas lvl 1 et stage > 1 -> TM/Tutor avec tag N + Deleted
        if lvl == 1 and stage > 1:
            tags_tm = list(tags)
            if "N" not in tags_tm:
                tags_tm.append("N")

            # éviter doublon
            if not move_entry_exists_tmtutor(tmtutor_list, move_title):
                tmtutor_list.append({
                    "Move": move_title,
                    "Type": move_type_api.capitalize(),  # style du dex ('Fire')
                    "Tags": tags_tm,
                    "Method": "Machine"
                })
                report_rows.append({
                    "Species": spec.get("Species"),
                    "Where": "TM/Tutor",
                    "Move": move_title,
                    "Type": move_type_api.capitalize(),
                    "Level": "",
                    "Tags": "|".join(tags_tm)
                })
            # ne pas ajouter en level-up dans ce cas
            continue

        # 2) Sinon, ajouter en Level Up Move List (avec Evo si lvl==0)
        level_field = "Evo" if lvl == 0 else (lvl if isinstance(lvl, int) else 1)

        # éviter doublon level-up
        if not move_entry_exists_levelup(lvlup_list, move_title):
            entry = {
                "Level": level_field,
                "Move": move_title,
                "Type": move_type_api.capitalize(),
                "Tags": tags
            }
            lvlup_list.append(entry)
            report_rows.append({
                "Species": spec.get("Species"),
                "Where": "Level-Up",
                "Move": move_title,
                "Type": move_type_api.capitalize(),
                "Level": level_field,
                "Tags": "|".join(tags)
            })

    # Sauvegarde du dex patché
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(dex, f, ensure_ascii=False, indent=2)
    print(f"[OK] Écrit: {out_path}")

    # Rapport optionnel
    if report_path:
        with report_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["Species", "Where", "Move", "Type", "Level", "Tags"])
            w.writeheader()
            w.writerows(report_rows)
        print(f"[OK] Rapport: {report_path} ({len(report_rows)} ajouts)")

if __name__ == "__main__":
    main()
