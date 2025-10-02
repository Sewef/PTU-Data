#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, Iterable, List, Optional

# ------------------------------------------------------------
# Logging setup
# ------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(message)s"
)
log = logging.getLogger("reformat_moves")

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

RE_N_TAG = re.compile(r"\(N\)", re.IGNORECASE)
# Supprime les préfixes TM/HM/indices : "06 Toxic", "A1 Cut", "100 Confide"
RE_TM_PREFIX = re.compile(r"^[A-Za-z]*\d+\s+")

def clean_move_name(raw: str) -> (str, List[str]):
    """
    Nettoie un nom de move :
      - retire le préfixe TM/HM (ex: '06 Toxic' -> 'Toxic', 'A1 Cut' -> 'Cut')
      - retire le suffixe '(N)' et ajoute le tag 'N' si présent
      - strip espaces
    Retourne (move_name, tags_additionnels)
    """
    tags = []
    s = raw.strip()

    # 1) Enlever préfixe de code TM/HM (ex: "06 Toxic", "A1 Cut")
    s = RE_TM_PREFIX.sub("", s)

    # 2) Détecter et retirer (N) où qu'il se trouve
    if RE_N_TAG.search(s):
        tags.append("N")
        s = RE_N_TAG.sub("", s).strip()

    return s, tags


def get_move_info(move_name: str, moves_ref: Dict[str, Any]) -> Dict[str, Any]:
    """
    Récupère la fiche move depuis la référence.
    Si manquante, log une erreur et renvoie un "stub" vide.
    """
    info = moves_ref.get(move_name)
    if info is None:
        log.error(f"Move inconnu dans moves.json: '{move_name}'")
        return {"Type": None, "Class": None}
    return info


def should_tag_stab(move_info: Dict[str, Any], mon_types: Iterable[str]) -> bool:
    """
    STAB si move.Type ∈ types du Pokémon ET move.Class != 'Status'.
    Si info incomplète (Type ou Class manquant), on ne tag pas.
    """
    m_type = move_info.get("Type")
    m_class = move_info.get("Class")
    if not m_type or not m_class:
        return False
    if m_class.strip().lower() == "status":
        return False
    return m_type in mon_types


def build_entry(move_name: str,
                method: str,
                base_tags: Optional[List[str]],
                mon_types: Iterable[str],
                moves_ref: Dict[str, Any]) -> Dict[str, Any]:
    """
    Construit l'entrée finale {Move, Type, Tags, Method}
    """
    # Nettoyage du nom + tags (N)
    clean_name, tags_from_name = clean_move_name(move_name)
    tags = list(base_tags or []) + tags_from_name

    # Infos du move
    info = get_move_info(clean_name, moves_ref)
    mtype = info.get("Type")

    # STAB ?
    if should_tag_stab(info, mon_types):
        tags.append("Stab")

    # dédoublonner les tags en gardant l'ordre d'apparition
    seen = set()
    tags = [t for t in tags if not (t in seen or seen.add(t))]

    return {
        "Move": clean_name,
        "Type": mtype,
        "Tags": tags,
        "Method": method
    }


def process_pokemon(mon: Dict[str, Any], moves_ref: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Transforme toutes les sources de moves du Pokémon en liste normalisée.
    Sources prises en compte :
      - Level Up Move List  -> Method: "Level-Up"
      - TM/HM Move List     -> Method: "Machine"
      - Egg Move List       -> Method: "Egg"
      - Tutor Move List     -> Method: "Tutor"
    """
    out: List[Dict[str, Any]] = []

    # Types du Pokémon
    mon_types = mon.get("Basic Information", {}).get("Type", []) or []

    moves = mon.get("Moves", {})

    # 1) Level-Up
    lvl_list = moves.get("Level Up Move List") or []
    for item in lvl_list:
        # item attendu: {"Level": 3, "Move": "Harden", "Type": "Normal"}
        mv = item.get("Move")
        if not mv:
            continue
        out.append(
            build_entry(
                move_name=mv,
                method="Level-Up",
                base_tags=[],
                mon_types=mon_types,
                moves_ref=moves_ref
            )
        )

    # 2) TM/HM (Machine)
    tm_list = moves.get("TM/HM Move List") or []
    for raw in tm_list:
        out.append(
            build_entry(
                move_name=raw,
                method="Machine",
                base_tags=[],
                mon_types=mon_types,
                moves_ref=moves_ref
            )
        )

    # 3) Egg
    egg_list = moves.get("Egg Move List") or []
    for raw in egg_list:
        out.append(
            build_entry(
                move_name=raw,
                method="Egg",
                base_tags=[],
                mon_types=mon_types,
                moves_ref=moves_ref
            )
        )

    # 4) Tutor
    tutor_list = moves.get("Tutor Move List") or []
    for raw in tutor_list:
        out.append(
            build_entry(
                move_name=raw,
                method="Tutor",
                base_tags=[],
                mon_types=mon_types,
                moves_ref=moves_ref
            )
        )

    return out


def load_mon_file(path: Path) -> Dict[str, Any]:
    """
    Charge le Pokémon depuis un fichier JSON.
    Tolère que le fichier contienne directement l'objet, une liste, ou du JSONLines avec 1 objet.
    """
    text = path.read_text(encoding="utf-8").strip()

    # Cas JSON Lines: on prend la première ligne non vide
    if "\n" in text and not (text.startswith("{") or text.startswith("[")):
        for line in text.splitlines():
            line = line.strip()
            if line:
                return json.loads(line)

    data = json.loads(text)

    if isinstance(data, list):
        if not data:
            raise ValueError("Fichier Pokémon vide (liste vide).")
        if len(data) > 1:
            log.warning("Le fichier contient plusieurs entrées ; on utilise la première.")
        return data[0]
    elif isinstance(data, dict):
        return data
    else:
        raise ValueError("Format Pokémon inattendu (ni objet ni liste).")


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Reformate les moves d'un Pokémon en {Move, Type, Tags, Method}."
    )
    ap.add_argument("--pokemon", "-p", required=True, type=Path,
                    help="Fichier JSON du Pokémon (structure complète).")
    ap.add_argument("--moves", "-m", required=True, type=Path,
                    help="Fichier JSON de référence des moves (dict Move -> fiche).")
    ap.add_argument("--output", "-o", type=Path,
                    help="Fichier de sortie (JSON). Par défaut: stdout.")
    args = ap.parse_args()

    mon = load_mon_file(args.pokemon)
    moves_ref = json.loads(args.moves.read_text(encoding="utf-8"))

    result = process_pokemon(mon, moves_ref)

    out_text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(out_text, encoding="utf-8")
        log.info(f"Écrit: {args.output}")
    else:
        print(out_text)


if __name__ == "__main__":
    main()
