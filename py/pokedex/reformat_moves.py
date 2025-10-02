#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, json, logging, re, sys, shutil
from pathlib import Path
from typing import Dict, Any, List, Tuple, Iterable, Set, Optional
import re

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
log = logging.getLogger("reformat_moves")

RE_N_TAG = re.compile(r"\(N\)", re.IGNORECASE)
RE_TM_PREFIX = re.compile(r"^[A-Za-z]*\d+\s+")  # "06 Toxic", "A1 Cut", "100 Confide"

# ---------- helpers ----------------------------------------------------------
def _resolve_wildcard_key(move: str, moves_ref: Dict[str, Any]) -> Optional[str]:
    """
    Si 'move' contient un '*', on cherche dans moves_ref une clé qui commence par
    le préfixe avant le '*', et qui contient bien un '*' juste après ce préfixe.
    Exemple: move = 'Sugar Rush*'  -> match 'Sugar Rush* [Trailblaze]'
    Règle: on choisit le match le plus court (le plus proche).
    """
    if "*" not in move:
        return None

    prefix = move.split("*", 1)[0].strip()
    if not prefix:
        return None

    # regex: ^<prefix>\*.*$
    pattern = re.compile(r"^" + re.escape(prefix) + r"\*.*$")
    candidates = [k for k in moves_ref.keys() if pattern.match(k)]
    if not candidates:
        return None

    # Choisir le plus court (closest match)
    candidates.sort(key=len)
    return candidates[0]

def clean_move_name(raw: str) -> Tuple[str, List[str]]:
    """Retire le code TM/HM au début + retire '(N)' et ajoute le tag 'N'."""
    tags: List[str] = []
    s = raw.strip()
    s = RE_TM_PREFIX.sub("", s)
    if RE_N_TAG.search(s):
        tags.append("N")
        s = RE_N_TAG.sub("", s).strip()
    return s, tags

def get_move_info(move: str, moves_ref: Dict[str, Any]) -> Dict[str, Any]:
    """
    1) Essaye correspondance exacte.
    2) Si échec et move contient '*', tente une recherche par préfixe avant '*'
       (ex: 'Sugar Rush*' -> 'Sugar Rush* [Trailblaze]').
    3) Si rien trouvé: log erreur et renvoie stub.
    """
    info = moves_ref.get(move)
    if info is not None:
        return info

    # fallback wildcard
    key = _resolve_wildcard_key(move, moves_ref)
    if key is not None:
        return moves_ref[key]

    log.error(f"Move inconnu dans moves.json: '{move}'")
    return {"Type": None, "Class": None}

def coerce_type_set(mon_types) -> Set[str]:
    """Renvoie uniquement les types qui sont des strings; ignore le reste (dicts, None, etc.)."""
    out: Set[str] = set()
    if not mon_types:
        return out
    for t in mon_types:
        if isinstance(t, str):
            out.add(t)
        # sinon: on ignore (comportement souhaité)
    return out

def should_tag_stab(move_info: Dict[str, Any], mon_types_iterable) -> bool:
    mtype = move_info.get("Type")
    mclass = move_info.get("Class")
    if not mtype or not mclass:
        return False
    if str(mclass).strip().lower() == "status":
        return False
    type_set = coerce_type_set(mon_types_iterable)
    return mtype in type_set

def build_entry(move_name: str,
                method: Optional[str],
                mon_types: List[str],
                moves_ref: Dict[str, Any]) -> Dict[str, Any]:
    """
    Construit l'objet final. Si 'method' est None, on n'ajoute pas de clé 'Method'.
    """
    clean, tags = clean_move_name(move_name)
    info = get_move_info(clean, moves_ref)
    if should_tag_stab(info, mon_types):
        tags.append("Stab")
    # dédoublage tags en préservant l'ordre
    seen = set()
    tags = [t for t in tags if not (t in seen or seen.add(t))]

    obj = {"Move": clean, "Type": info.get("Type"), "Tags": tags}
    if method is not None:
        obj["Method"] = method
    return obj

def convert_string_list(lst: Any,
                        method: Optional[str],
                        mon_types: List[str],
                        moves_ref: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convertit une liste de chaînes en objets normalisés.
    - Ignore les entrées vides ou non-string.
    - 'method' peut être 'Machine' / 'Egg' / 'Tutor' OU None pour ne PAS inclure la clé 'Method'.
    """
    out: List[Dict[str, Any]] = []
    if not isinstance(lst, list):
        return out
    for raw in lst:
        if not isinstance(raw, str):
            continue
        if not raw or not raw.strip():
            continue  # ne rien ajouter si string vide
        out.append(build_entry(raw, method, mon_types, moves_ref))
    return out

# ---------- transformer un Pokémon ------------------------------------------

def reformat_moves_for_mon(mon: Dict[str, Any], moves_ref: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ne modifie PAS 'Level Up Move List'.
    Convertit SEULEMENT:
      - 'TM/HM Move List'    -> objets {Move, Type, Tags, Method:'Machine'}
      - 'Egg Move List'      -> objets {Move, Type, Tags, Method:'Egg'}
      - 'Tutor Move List'    -> objets {Move, Type, Tags, Method:'Tutor'}
      - 'TM/Tutor Moves List'-> objets {Move, Type, Tags} (PAS de 'Method')
    """
    raw_types = (mon.get("Basic Information", {}) or {}).get("Type", []) or []
    mon_types = list(coerce_type_set(raw_types))  # strings uniquement
    moves = dict(mon.get("Moves", {}) or {})

    if "TM/HM Move List" in moves:
        moves["TM/HM Move List"] = convert_string_list(
            moves.get("TM/HM Move List"), "Machine", mon_types, moves_ref
        )
    if "Egg Move List" in moves:
        moves["Egg Move List"] = convert_string_list(
            moves.get("Egg Move List"), "Egg", mon_types, moves_ref
        )
    if "Tutor Move List" in moves:
        moves["Tutor Move List"] = convert_string_list(
            moves.get("Tutor Move List"), "Tutor", mon_types, moves_ref
        )
    if "TM/Tutor Moves List" in moves:
        moves["TM/Tutor Moves List"] = convert_string_list(
            moves.get("TM/Tutor Moves List"), None, mon_types, moves_ref
        )

    mon2 = dict(mon)
    mon2["Moves"] = moves
    return mon2

# ---------- container (objet / liste / mapping) ------------------------------

def transform_container(data: Any, moves_ref: Dict[str, Any]) -> Any:
    """
    Traite:
      - dict d'un Pokémon (clé 'Species' ou 'Moves' ou 'Basic Information')
      - list de Pokémon
      - dict {clé -> Pokémon}
    """
    if isinstance(data, dict):
        if "Species" in data or "Moves" in data or "Basic Information" in data:
            return reformat_moves_for_mon(data, moves_ref)
        out: Dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(v, dict) and ("Species" in v or "Moves" in v or "Basic Information" in v):
                out[k] = reformat_moves_for_mon(v, moves_ref)
            else:
                out[k] = v
        return out

    if isinstance(data, list):
        out_list: List[Any] = []
        for item in data:
            if isinstance(item, dict) and ("Species" in item or "Moves" in item or "Basic Information" in item):
                out_list.append(reformat_moves_for_mon(item, moves_ref))
            else:
                out_list.append(item)
        return out_list

    return data

# ---------- CLI ----------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Normalise TM/Egg/Tutor (et TM/Tutor Moves List) en gardant Level Up intact."
    )
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
        backup = src.with_suffix(src.suffix + ".bak")
        try:
            shutil.copy2(src, backup)
            logging.info(f"Backup créé: {backup}")
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
