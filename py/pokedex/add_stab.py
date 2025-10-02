#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, json, logging, sys, shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
log = logging.getLogger("add_stab_tags")

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
    """Retourne True si le move est de classe 'Status', False si non-Status,
    None si inconnu ou moves_ref absent."""
    if not moves_ref:
        return None
    info = moves_ref.get(move_name)
    if not isinstance(info, dict):
        return None
    klass = info.get("Class")
    if not isinstance(klass, str):
        return None
    return klass.strip().lower() == "status"

def add_stab_to_move_obj(move_obj: Dict[str, Any], mon_type_set: Set[str],
                         moves_ref: Optional[Dict[str, Any]]) -> None:
    """
    Ajoute 'Stab' à move_obj['Tags'] si:
      - move_obj['Type'] est une str présente dans mon_type_set
      - ET (moves_ref indique pas 'Status' OU moves_ref absent/inconnu)
    Ne modifie rien si les prérequis ne sont pas remplis.
    """
    mtype = move_obj.get("Type")
    if not isinstance(mtype, str):
        return

    # status check (best-effort)
    st = is_status(move_obj.get("Move", ""), moves_ref)
    if st is True:
        return  # explicitement Status -> pas de STAB

    if mtype in mon_type_set:
        tags = move_obj.get("Tags")
        if not isinstance(tags, list):
            tags = []
        if "Stab" not in tags:
            tags.append("Stab")
        # dédoublonnage simple
        seen = set()
        move_obj["Tags"] = [t for t in tags if isinstance(t, str) and not (t in seen or seen.add(t))]

# --------------- transformation -----------

def process_lists_on_mon(mon: Dict[str, Any],
                         list_keys: List[str],
                         moves_ref: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Ajoute STAB dans les objets des listes ciblées (si présentes).
    Ne convertit pas les formats: agit seulement si la liste contient des dicts move-obj.
    """
    mon2 = dict(mon)
    mon_types = coerce_type_set((mon.get("Basic Information", {}) or {}).get("Type", []))
    moves = mon.get("Moves", {})
    if not isinstance(moves, dict):
        return mon2

    moves2 = dict(moves)
    for key in list_keys:
        lst = moves2.get(key)
        if not isinstance(lst, list):
            continue
        out_list: List[Any] = []
        for item in lst:
            if isinstance(item, dict) and "Move" in item and "Type" in item:
                add_stab_to_move_obj(item, mon_types, moves_ref)
                out_list.append(item)
            else:
                # on laisse intact (strings, autres formats)
                out_list.append(item)
        moves2[key] = out_list

    mon2["Moves"] = moves2
    return mon2

def transform_container(data: Any,
                        list_keys: List[str],
                        moves_ref: Optional[Dict[str, Any]]) -> Any:
    """
    Gère: dict Pokémon, liste de Pokémon, mapping clé->Pokémon.
    Ajoute STAB uniquement dans les listes ciblées.
    """
    # dict qui ressemble à un Pokémon
    if isinstance(data, dict) and ("Species" in data or "Moves" in data or "Basic Information" in data):
        return process_lists_on_mon(data, list_keys, moves_ref)

    # mapping clé -> Pokémon
    if isinstance(data, dict):
        out: Dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(v, dict) and ("Species" in v or "Moves" in v or "Basic Information" in v):
                out[k] = process_lists_on_mon(v, list_keys, moves_ref)
            else:
                out[k] = v
        return out

    # liste de Pokémon
    if isinstance(data, list):
        out_list: List[Any] = []
        for item in data:
            if isinstance(item, dict) and ("Species" in item or "Moves" in item or "Basic Information" in item):
                out_list.append(process_lists_on_mon(item, list_keys, moves_ref))
            else:
                out_list.append(item)
        return out_list

    return data

# --------------- CLI ---------------------

def main():
    ap = argparse.ArgumentParser(
        description="Ajoute le tag 'Stab' aux moves (objets) des listes ciblées si le Type correspond aux types du Pokémon."
    )
    ap.add_argument("--pokemon", "-p", required=True, type=Path, help="Fichier pokedex (objet, liste, ou mapping).")
    ap.add_argument("--output", "-o", required=True, type=Path, help="Fichier de sortie.")
    ap.add_argument("--inplace", action="store_true", help="Autorise l'écrasement du fichier source (backup .bak).")
    ap.add_argument("--moves", "-m", type=Path,
                    help="(Optionnel) Fichier moves.json (dict Move -> fiche) pour éviter de tagger les moves de classe 'Status'.")
    ap.add_argument("--keys", nargs="*", default=["TM/Tutor Moves List"],
                    help="Clés de listes à traiter (défaut: 'TM/Tutor Moves List').")
    args = ap.parse_args()

    src = args.pokemon.resolve()
    dst = args.output.resolve()
    if dst == src and not args.inplace:
        log.critical("Refus d'écrire sur le même fichier sans --inplace.")
        sys.exit(2)

    try:
        data = json.loads(args.pokemon.read_text(encoding="utf-8"))
    except Exception as e:
        log.critical(f"Impossible de lire {args.pokemon}: {e}")
        sys.exit(1)

    moves_ref: Optional[Dict[str, Any]] = None
    if args.moves:
        try:
            moves_ref = json.loads(args.moves.read_text(encoding="utf-8"))
        except Exception as e:
            log.error(f"Impossible de lire {args.moves}: {e}. On continue sans filtrer 'Status'.")

    result = transform_container(data, args.keys, moves_ref)
    out_text = json.dumps(result, ensure_ascii=False, indent=2)

    if dst == src and args.inplace:
        backup = src.with_suffix(src.suffix + ".bak")
        try:
            shutil.copy2(src, backup)
            log.info(f"Backup créé: {backup}")
        except Exception as e:
            log.critical(f"Échec création du backup: {e}")
            sys.exit(1)

    try:
        args.output.write_text(out_text, encoding="utf-8")
        log.info(f"Écrit: {args.output}")
    except Exception as e:
        log.critical(f"Échec d'écriture {args.output}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
