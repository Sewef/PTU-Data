#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, json, logging, sys, shutil
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
log = logging.getLogger("tag_deleted_moves")

# -----------------------------------------------------------------------------
# I/O helpers
# -----------------------------------------------------------------------------

def load_moves_from_txt(path: Path) -> Set[str]:
    """
    Charge un .txt où chaque ligne est:
      - soit '123<TAB>Move Name'
      - soit 'Move Name'
    Retourne un set de noms de moves (case-insensitive, trim).
    Les lignes vides / commentées (# ...) sont ignorées.
    """
    wanted: Set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # essaie split sur tab: "id \t Move"
        if "\t" in line:
            parts = line.split("\t", 1)
            move = parts[1].strip()
        else:
            move = line
        if move:
            wanted.add(move.lower())
    return wanted

def ensure_tags_list(move_obj: Dict[str, Any]) -> List[str]:
    tags = move_obj.get("Tags")
    if not isinstance(tags, list):
        tags = []
    move_obj["Tags"] = tags
    return tags

# -----------------------------------------------------------------------------
# Core transform
# -----------------------------------------------------------------------------

def tag_deleted_in_list(lst: Any, wanted_names_lc: Set[str]) -> int:
    """
    Parcourt une liste (si list) et ajoute 'Deleted' en premier dans Tags
    des objets move dont le nom correspond à wanted_names_lc (case-insensitive).
    Retourne le nombre de moves modifiés.
    """
    if not isinstance(lst, list):
        return 0

    changed = 0
    for item in lst:
        if not (isinstance(item, dict) and "Move" in item):
            continue
        mv_name = item.get("Move")
        if not isinstance(mv_name, str):
            continue
        if mv_name.strip().lower() not in wanted_names_lc:
            continue

        tags = ensure_tags_list(item)

        # Si 'Deleted' est déjà premier, rien à faire
        if tags and tags[0] == "Deleted":
            continue

        # S'il existe ailleurs, on le retire pour éviter doublon
        tags_others = [t for t in tags if t != "Deleted" and isinstance(t, str)]
        # Insérer Deleted en premier
        item["Tags"] = ["Deleted"] + tags_others
        changed += 1

    return changed

def process_mon(mon: Dict[str, Any], wanted_names_lc: Set[str], keys_to_scan: List[str]) -> Tuple[Dict[str, Any], int]:
    """
    Ajoute 'Deleted' aux moves correspondants dans les sous-listes `keys_to_scan`.
    Ne modifie que les listes d'objets move (ne convertit rien).
    Retourne (mon_modifié, nb_modifs).
    """
    moves = mon.get("Moves", {})
    if not isinstance(moves, dict):
        return mon, 0

    moves2 = dict(moves)
    total = 0
    for key in keys_to_scan:
        if key in moves2:
            total += tag_deleted_in_list(moves2[key], wanted_names_lc)

    if total > 0:
        mon2 = dict(mon)
        mon2["Moves"] = moves2
        return mon2, total
    return mon, 0

def transform_container(data: Any, wanted_names_lc: Set[str], keys_to_scan: List[str]) -> Tuple[Any, int]:
    """
    Gère:
      - dict d'un Pokémon (ou objet qui 'ressemble' à un Pokémon),
      - list de Pokémon,
      - dict mapping clé->Pokémon.
    Retourne (data_modifiée, total_modifs).
    """
    total = 0

    # cas: dict ressemblant à un Pokémon
    if isinstance(data, dict) and ("Species" in data or "Moves" in data or "Basic Information" in data):
        mon2, c = process_mon(data, wanted_names_lc, keys_to_scan)
        return mon2, c

    # cas: dict mapping clé -> mon
    if isinstance(data, dict):
        out: Dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(v, dict) and ("Species" in v or "Moves" in v or "Basic Information" in v):
                v2, c = process_mon(v, wanted_names_lc, keys_to_scan)
                total += c
                out[k] = v2
            else:
                out[k] = v
        return out, total

    # cas: liste de mons
    if isinstance(data, list):
        out_list: List[Any] = []
        for item in data:
            if isinstance(item, dict) and ("Species" in item or "Moves" in item or "Basic Information" in item):
                item2, c = process_mon(item, wanted_names_lc, keys_to_scan)
                total += c
                out_list.append(item2)
            else:
                out_list.append(item)
        return out_list, total

    # autre: inchangé
    return data, 0

# -----------------------------------------------------------------------------
# Batch file ops
# -----------------------------------------------------------------------------

def write_with_backup(path: Path, new_text: str, create_backup: bool) -> bool:
    if create_backup:
        backup = path.with_suffix(path.suffix + ".bak")
        try:
            shutil.copy2(path, backup)
            log.info(f"[{path}] Backup créé -> {backup.name}")
        except Exception as e:
            log.error(f"[{path}] Échec backup: {e}")
            return False
    try:
        path.write_text(new_text, encoding="utf-8")
        log.info(f"[{path}] Écrit.")
        return True
    except Exception as e:
        log.error(f"[{path}] Écriture échouée: {e}")
        return False

# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Ajoute le tag 'Deleted' (en 1er) aux moves présents dans un .txt (id<TAB>Move ou Move), à l'intérieur d'un pokedex.json."
    )
    ap.add_argument("--pokedex", "-p", required=True, type=Path, help="Fichier pokedex.json à modifier.")
    ap.add_argument("--moves-list", "-l", required=True, type=Path, help="Fichier .txt listant les moves à tagger Deleted.")
    ap.add_argument("--inplace", action="store_true", help="Écrase le fichier pokedex (backup .bak créé).")
    ap.add_argument("--output", "-o", type=Path, help="Fichier de sortie (si non --inplace).")
    ap.add_argument(
        "--keys",
        nargs="*",
        default=[
            "Level Up Move List",
            "TM/HM Move List",
            "TM/Tutor Moves List",
            "Tutor Move List",
            "Egg Move List",
        ],
        help="Sous-listes de Moves à parcourir (défaut: toutes les usuelles).",
    )
    args = ap.parse_args()

    if not args.pokedex.exists():
        log.critical(f"pokedex introuvable: {args.pokedex}")
        sys.exit(2)
    if not args.moves_list.exists():
        log.critical(f"moves-list introuvable: {args.moves_list}")
        sys.exit(2)

    if not args.inplace and not args.output:
        log.critical("Spécifie --inplace pour écraser ou --output pour écrire ailleurs.")
        sys.exit(2)

    # charge sources
    try:
        data = json.loads(args.pokedex.read_text(encoding="utf-8"))
    except Exception as e:
        log.critical(f"Lecture/parse pokedex échoué: {e}")
        sys.exit(1)

    try:
        wanted_names_lc = load_moves_from_txt(args.moves_list)
    except Exception as e:
        log.critical(f"Lecture moves-list échoué: {e}")
        sys.exit(1)

    if not wanted_names_lc:
        log.warning("Aucun move valide trouvé dans le .txt (rien à faire).")
        sys.exit(0)

    # transforme
    new_data, count = transform_container(data, wanted_names_lc, args.keys)
    if count == 0:
        log.info("Aucune entrée move correspondante trouvée (0 modif).")
        sys.exit(0)

    new_text = json.dumps(new_data, ensure_ascii=False, indent=2)

    # sortie
    if args.inplace:
        ok = write_with_backup(args.pokedex, new_text, create_backup=True)
        sys.exit(0 if ok else 1)
    else:
        try:
            args.output.write_text(new_text, encoding="utf-8")
            log.info(f"Écrit: {args.output}")
            sys.exit(0)
        except Exception as e:
            log.critical(f"Échec écriture {args.output}: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
