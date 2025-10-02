#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, json, logging, sys, shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
log = logging.getLogger("add_stab_tags_batch")

# ---------------- helpers ----------------

def coerce_type_set(mon_types) -> Set[str]:
    """Renvoie uniquement les types qui sont des strings; ignore dicts/None/etc."""
    out: Set[str] = set()
    if not mon_types:
        return out
    for t in mon_types:
        if isinstance(t, str):
            out.add(t)
    return out

def is_status(move_name: str, moves_ref: Optional[Dict[str, Any]]) -> Optional[bool]:
    """True si Class == 'Status', False si non-Status, None si inconnu/absent."""
    if not moves_ref:
        return None
    info = moves_ref.get(move_name)
    if not isinstance(info, dict):
        return None
    klass = info.get("Class")
    if not isinstance(klass, str):
        return None
    return klass.strip().lower() == "status"

def ensure_tags_list(obj: Dict[str, Any]) -> List[str]:
    tags = obj.get("Tags")
    if not isinstance(tags, list):
        tags = []
    obj["Tags"] = tags
    return tags

def add_stab_to_move_obj(move_obj: Dict[str, Any], mon_type_set: Set[str],
                         moves_ref: Optional[Dict[str, Any]]) -> bool:
    """
    Tente d'ajouter 'Stab' à move_obj['Tags'].
    Retourne True si l'objet a été modifié, False sinon.
    - Si move_obj['Type'] manquant, tente de le déduire via moves_ref[Move]['Type'].
    - Ne tag pas si moves_ref indique explicitement 'Status'.
    """
    move_name = move_obj.get("Move")
    if not isinstance(move_name, str) or not move_name.strip():
        return False

    mtype = move_obj.get("Type")
    if not isinstance(mtype, str) and moves_ref:
        mi = moves_ref.get(move_name)
        if isinstance(mi, dict) and isinstance(mi.get("Type"), str):
            mtype = mi["Type"]
            move_obj["Type"] = mtype  # on complète, c'est utile

    if not isinstance(mtype, str):
        return False

    st = is_status(move_name, moves_ref)
    if st is True:
        return False

    if mtype in mon_type_set:
        tags = ensure_tags_list(move_obj)
        if "Stab" not in tags:
            tags.append("Stab")
            # dédoublonnage simple
            seen = set()
            move_obj["Tags"] = [t for t in tags if isinstance(t, str) and not (t in seen or seen.add(t))]
            return True
    return False

# ---------------- core transform ----------------

def process_levelup_for_mon(mon: Dict[str, Any],
                            list_key: str,
                            moves_ref: Optional[Dict[str, Any]]) -> Tuple[Dict[str, Any], int]:
    """
    Ajoute STAB dans 'Level Up Move List' (ou autre clé si override).
    Retourne (mon_modifié, nb_modifs).
    """
    mon2 = dict(mon)
    basic_info = (mon.get("Basic Information", {}) or {})
    mon_type_set = coerce_type_set(basic_info.get("Type", []))

    moves = mon.get("Moves", {})
    if not isinstance(moves, dict):
        return mon2, 0

    lvl_list = moves.get(list_key)
    if not isinstance(lvl_list, list):
        return mon2, 0

    changed = 0
    new_list: List[Any] = []
    for item in lvl_list:
        if isinstance(item, dict) and "Move" in item:
            if add_stab_to_move_obj(item, mon_type_set, moves_ref):
                changed += 1
            new_list.append(item)
        else:
            new_list.append(item)  # laisser intact si non-dict
    if changed:
        moves2 = dict(moves)
        moves2[list_key] = new_list
        mon2["Moves"] = moves2
    return mon2, changed

def transform_container(data: Any,
                        list_key: str,
                        moves_ref: Optional[Dict[str, Any]]) -> Tuple[Any, int]:
    """
    Traite: dict Pokémon, liste de Pokémon, mapping clé->Pokémon.
    N'ajoute STAB que dans la liste 'list_key'.
    Retourne (data_modifiée, total_modifs).
    """
    total = 0

    # dict ressemblant à un Pokémon
    if isinstance(data, dict) and ("Species" in data or "Moves" in data or "Basic Information" in data):
        mon2, c = process_levelup_for_mon(data, list_key, moves_ref)
        return mon2, c

    # mapping clé -> Pokémon
    if isinstance(data, dict):
        out: Dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(v, dict) and ("Species" in v or "Moves" in v or "Basic Information" in v):
                v2, c = process_levelup_for_mon(v, list_key, moves_ref)
                total += c
                out[k] = v2
            else:
                out[k] = v
        return out, total

    # liste de Pokémon
    if isinstance(data, list):
        out_list: List[Any] = []
        for item in data:
            if isinstance(item, dict) and ("Species" in item or "Moves" in item or "Basic Information" in item):
                item2, c = process_levelup_for_mon(item, list_key, moves_ref)
                total += c
                out_list.append(item2)
            else:
                out_list.append(item)
        return out_list, total

    return data, 0

# ---------------- batch over directory ----------------

def find_json_files(root: Path) -> List[Path]:
    return [p for p in root.rglob("*.json") if p.is_file()]

def process_file(path: Path, list_key: str, moves_ref: Optional[Dict[str, Any]],
                 inplace: bool, backup: bool, dry_run: bool) -> int:
    """
    Traite un fichier .json, renvoie le nombre de moves modifiés.
    Écrit en place (avec backup) sauf si dry_run=True.
    """
    try:
        original = path.read_text(encoding="utf-8")
        data = json.loads(original)
    except Exception as e:
        log.error(f"[{path}] Lecture/parse échoué: {e}")
        return 0

    new_data, count = transform_container(data, list_key, moves_ref)
    if count == 0:
        log.info(f"[{path}] 0 modif")
        return 0

    new_text = json.dumps(new_data, ensure_ascii=False, indent=2)
    if new_text == original:
        log.info(f"[{path}] 0 modif effective")
        return 0

    if dry_run:
        log.info(f"[{path}] {count} move(s) taggés STAB (dry-run)")
        return count

    # écriture
    if inplace:
        if backup:
            backup_path = path.with_suffix(path.suffix + ".bak")
            try:
                shutil.copy2(path, backup_path)
            except Exception as e:
                log.error(f"[{path}] Backup échoué: {e}")
                return 0
        try:
            path.write_text(new_text, encoding="utf-8")
            log.info(f"[{path}] {count} move(s) taggés STAB, écrit.")
        except Exception as e:
            log.error(f"[{path}] Écriture échouée: {e}")
            return 0
    else:
        # mode non-inplace : écrire à côté avec suffixe .out.json
        out_path = path.with_suffix(".out.json")
        try:
            out_path.write_text(new_text, encoding="utf-8")
            log.info(f"[{path}] {count} move(s) taggés STAB, écrit -> {out_path.name}")
        except Exception as e:
            log.error(f"[{path}] Écriture échouée: {e}")
            return 0

    return count

# ---------------- CLI ----------------

def main():
    ap = argparse.ArgumentParser(
        description="Ajoute le tag 'Stab' aux moves d'une liste (par défaut 'Level Up Move List') pour tous les JSON d'un dossier (récursif)."
    )
    ap.add_argument("--input", "-i", required=True, type=Path,
                    help="Fichier unique .json OU dossier contenant des .json (récursif).")
    ap.add_argument("--moves", "-m", type=Path,
                    help="(Optionnel) moves.json (dict Move -> fiche) pour éviter de tagger les moves 'Status'.")
    ap.add_argument("--list-key", default="Level Up Move List",
                    help="Clé de la liste à traiter (défaut: 'Level Up Move List').")
    ap.add_argument("--inplace", action="store_true",
                    help="Écrit en place (sinon crée un .out.json à côté).")
    ap.add_argument("--no-backup", action="store_true",
                    help="Avec --inplace, n'écrit pas de backup .bak.")
    ap.add_argument("--dry-run", action="store_true",
                    help="N'écrit rien, affiche seulement le nombre de modifs.")
    args = ap.parse_args()

    # charge moves_ref si fourni
    moves_ref: Optional[Dict[str, Any]] = None
    if args.moves:
        try:
            moves_ref = json.loads(args.moves.read_text(encoding="utf-8"))
        except Exception as e:
            log.error(f"Impossible de lire {args.moves}: {e}. On continue sans filtrer 'Status'.")

    # build file list
    targets: List[Path] = []
    if args.input.is_dir():
        targets = find_json_files(args.input)
        if not targets:
            log.warning("Aucun .json trouvé dans le dossier.")
    elif args.input.is_file():
        targets = [args.input]
    else:
        log.critical(f"Chemin invalide: {args.input}")
        sys.exit(2)

    total_mods = 0
    for f in targets:
        total_mods += process_file(
            path=f,
            list_key=args.list_key,
            moves_ref=moves_ref,
            inplace=args.inplace,
            backup=(not args.no_backup),
            dry_run=args.dry_run,
        )

    log.info(f"Terminé. Total moves taggés STAB: {total_mods}")

if __name__ == "__main__":
    main()
