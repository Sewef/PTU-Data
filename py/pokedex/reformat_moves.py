#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, json, logging, re, sys, shutil
from pathlib import Path
from typing import Dict, Any, List, Tuple, Iterable

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
log = logging.getLogger("reformat_moves")

RE_N_TAG = re.compile(r"\(N\)", re.IGNORECASE)
RE_TM_PREFIX = re.compile(r"^[A-Za-z]*\d+\s+")

def clean_move_name(raw: str) -> Tuple[str, List[str]]:
    tags: List[str] = []
    s = raw.strip()
    s = RE_TM_PREFIX.sub("", s)  # retire "06 " / "A1 " / "100 "
    if RE_N_TAG.search(s):
        tags.append("N")
        s = RE_N_TAG.sub("", s).strip()
    return s, tags

def get_move_info(move: str, moves_ref: Dict[str, Any]) -> Dict[str, Any]:
    info = moves_ref.get(move)
    if info is None:
        log.error(f"Move inconnu dans moves.json: '{move}'")
        return {"Type": None, "Class": None}
    return info

def should_tag_stab(move_info: Dict[str, Any], mon_types: Iterable[str]) -> bool:
    mtype = move_info.get("Type")
    mclass = move_info.get("Class")
    if not mtype or not mclass:
        return False
    if str(mclass).strip().lower() == "status":
        return False
    return mtype in set(mon_types or [])

def build_entry(move_name: str, method: str, mon_types: List[str],
                moves_ref: Dict[str, Any]) -> Dict[str, Any]:
    clean, tags = clean_move_name(move_name)
    info = get_move_info(clean, moves_ref)
    if should_tag_stab(info, mon_types):
        tags.append("Stab")
    # dédoublonnage
    seen = set()
    tags = [t for t in tags if not (t in seen or seen.add(t))]
    return {"Move": clean, "Type": info.get("Type"), "Tags": tags, "Method": method}

def reformat_moves_for_mon(mon: Dict[str, Any], moves_ref: Dict[str, Any]) -> Dict[str, Any]:
    mon_types = mon.get("Basic Information", {}).get("Type", []) or []
    moves = mon.get("Moves", {}) or {}
    out: List[Dict[str, Any]] = []

    # Level-Up
    for item in moves.get("Level Up Move List") or []:
        mv = item.get("Move")
        if mv and str(mv).strip():
            out.append(build_entry(mv, "Level-Up", mon_types, moves_ref))

    # Machine (TM/HM)
    for raw in moves.get("TM/HM Move List") or []:
        if raw and str(raw).strip():
            out.append(build_entry(raw, "Machine", mon_types, moves_ref))

    # Egg
    for raw in moves.get("Egg Move List") or []:
        if raw and str(raw).strip():
            out.append(build_entry(raw, "Egg", mon_types, moves_ref))

    # Tutor
    for raw in moves.get("Tutor Move List") or []:
        if raw and str(raw).strip():
            out.append(build_entry(raw, "Tutor", mon_types, moves_ref))

    mon2 = dict(mon)
    mon2["Moves"] = out
    return mon2


def transform_container(data: Any, moves_ref: Dict[str, Any]) -> Any:
    """
    Transforme selon la forme du pokedex_core:
      - dict d'un Pokémon        -> dict
      - list de Pokémon          -> list
      - dict {key -> Pokémon}    -> dict (mêmes clés)
    Les objets sans champ 'Moves' sont laissés tels quels.
    """
    if isinstance(data, dict):
        # Cas 1: semble être UN pokémon (a des clés Species/Number/etc.)
        if "Species" in data or "Moves" in data or "Basic Information" in data:
            return reformat_moves_for_mon(data, moves_ref)
        # Cas 2: mapping clé -> Pokémon
        out: Dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(v, dict) and ("Species" in v or "Moves" in v or "Basic Information" in v):
                out[k] = reformat_moves_for_mon(v, moves_ref)
            else:
                out[k] = v  # entrée non reconnue, intacte
        return out

    if isinstance(data, list):
        out_list: List[Any] = []
        for item in data:
            if isinstance(item, dict) and ("Species" in item or "Moves" in item or "Basic Information" in item):
                out_list.append(reformat_moves_for_mon(item, moves_ref))
            else:
                out_list.append(item)  # élément non-Pokémon, intact
        return out_list

    # Autres formes (JSON Lines, etc.) -> inchangé
    return data

def main():
    ap = argparse.ArgumentParser(description="Reformate la section Moves des Pokémon en format unifié.")
    ap.add_argument("--pokemon", "-p", required=True, type=Path, help="pokedex_core.json (objet, liste ou mapping).")
    ap.add_argument("--moves", "-m", required=True, type=Path, help="moves_core.json (dict Move -> fiche).")
    ap.add_argument("--output", "-o", required=True, type=Path, help="Fichier de sortie.")
    ap.add_argument("--inplace", action="store_true", help="Autorise l'écrasement du fichier source (crée un .bak).")
    args = ap.parse_args()

    src = args.pokemon.resolve()
    dst = args.output.resolve()

    if dst == src and not args.inplace:
        log.critical("Refus d'écrire sur le même fichier que l'entrée sans --inplace.")
        sys.exit(2)

    try:
        data = json.loads(args.pokemon.read_text(encoding="utf-8"))
    except Exception as e:
        log.critical(f"Impossible de lire {args.pokemon}: {e}")
        sys.exit(1)

    try:
        moves_ref = json.loads(args.moves.read_text(encoding="utf-8"))
    except Exception as e:
        log.critical(f"Impossible de lire {args.moves}: {e}")
        sys.exit(1)

    result = transform_container(data, moves_ref)
    out_text = json.dumps(result, ensure_ascii=False, indent=2)

    if dst == src and args.inplace:
        # backup
        backup = src.with_suffix(src.suffix + ".bak")
        shutil.copy2(src, backup)
        log.info(f"Backup créé: {backup}")

    try:
        args.output.write_text(out_text, encoding="utf-8")
        log.info(f"Écrit: {args.output}")
    except Exception as e:
        log.critical(f"Échec d'écriture {args.output}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
