#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, json, sys, re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

def load_json(p: Path) -> Any:
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

def dump_json(p: Path, data: Any) -> None:
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def is_null_stage(val: Any) -> bool:
    """True if 'Stade' is a JSON null or a string 'null' (any case)."""
    if val is None:
        return True
    if isinstance(val, str) and val.strip().lower() == "null":
        return True
    return False

def normalize_space(s: str) -> str:
    return " ".join(str(s).split())

def merge_condition(base: Optional[str], extra: Optional[str]) -> str:
    """Concatène proprement base + extra pour Condition."""
    base = (base or "").strip()
    extra = (extra or "").strip()
    if not base:
        return extra
    if not extra:
        return base
    return normalize_space(f"{base} {extra}")

def looks_like_min_level(text: str) -> bool:
    """
    Détecte si le texte ressemble à un minimum de niveau.
    Spéc pris: 'Lv 20 Minimum' OU tout ce qui COMMENCE par 'Lv' (insensible à la casse).
    """
    t = text.strip()
    if not t:
        return False
    if t.lower().startswith("lv"):
        return True
    return False

def merge_min_level(prev: Dict[str, Any], extra_min: str) -> None:
    """Injecte extra_min dans prev['Minimum Level'], en concaténant si déjà présent et différent."""
    extra_min = extra_min.strip()
    if not extra_min:
        return
    existing = (prev.get("Minimum Level") or "").strip()
    if not existing:
        prev["Minimum Level"] = extra_min
    else:
        if existing != extra_min:
            prev["Minimum Level"] = f"{existing} & {extra_min}"

def fix_one_evolution_list(evo: Any, species_name_for_logs: str) -> Any:
    """
    - Pour chaque entrée avec 'Stade': null, on regarde 'Species'.
      * Si 'Species' commence par 'Lv' -> injecte dans 'Minimum Level' du précédent.
      * Sinon -> injecte dans 'Condition' du précédent.
    - Supprime l'entrée 'Stade': null.
    - Gère plusieurs nulls d'affilée (accumulation).
    """
    if not isinstance(evo, list) or not evo:
        return evo

    fixed: List[Dict[str, Any]] = []
    pending_cond: List[str] = []   # accroches à ajouter à Condition
    pending_min:  List[str] = []   # accroches à ajouter à Minimum Level (si "Lv ...")

    def flush_pending_into_prev():
        """Applique pending_cond et pending_min dans le dernier élément 'valide' de fixed."""
        if not fixed:
            return
        prev = fixed[-1]
        if not isinstance(prev, dict):
            return

        if pending_cond:
            joined = " ".join(x.strip() for x in pending_cond if x and x.strip())
            if joined:
                prev["Condition"] = merge_condition(prev.get("Condition"), joined)

        if pending_min:
            for x in pending_min:
                if x and x.strip():
                    merge_min_level(prev, x.strip())

    for idx, item in enumerate(evo):
        if not isinstance(item, dict):
            # élément non-dict, on le recopie tel quel
            fixed.append(item)
            continue

        stade = item.get("Stade")
        if is_null_stage(stade):
            extra = str(item.get("Species", "")).strip()
            if extra:
                if looks_like_min_level(extra):
                    pending_min.append(extra)
                    print(f"[fix] {species_name_for_logs}: Evolution idx {idx} null 'Stade' → MIN LEVEL += '{extra}'", file=sys.stdout)
                else:
                    pending_cond.append(extra)
                    print(f"[fix] {species_name_for_logs}: Evolution idx {idx} null 'Stade' → CONDITION += '{extra}'", file=sys.stdout)
            else:
                print(f"[warn] {species_name_for_logs}: Evolution idx {idx} null 'Stade' but empty 'Species'; dropping", file=sys.stderr)
            # on supprime l'item null (pas d'ajout à fixed)
            continue

        # si on tombe sur un item normal et qu'on a des extras en attente, on les applique au précédent
        if (pending_cond or pending_min) and fixed:
            flush_pending_into_prev()
            pending_cond.clear()
            pending_min.clear()

        fixed.append(item)

    # Si la liste se termine par des nulls → appliquer au dernier élément gardé
    if (pending_cond or pending_min) and fixed:
        flush_pending_into_prev()
        pending_cond.clear()
        pending_min.clear()

    return fixed

def process_root(data: Union[List, Dict]) -> Union[List, Dict]:
    """
    Supporte:
      - Liste d'entrées pokédex (chacune dict avec 'Evolution')
      - Un seul objet pokédex
      - Mapping {SpeciesName: { ... }}
    """
    if isinstance(data, list):
        for entry in data:
            if not isinstance(entry, dict):
                continue
            sp = str(entry.get("Species") or entry.get("species") or "Unknown")
            evo = entry.get("Evolution")
            if evo is not None:
                entry["Evolution"] = fix_one_evolution_list(evo, sp)
        return data

    if isinstance(data, dict):
        # un seul pokémon
        if "Evolution" in data:
            sp = str(data.get("Species") or data.get("species") or "Unknown")
            data["Evolution"] = fix_one_evolution_list(data["Evolution"], sp)
            return data

        # mapping { SpeciesName : { ... } }
        if data and all(isinstance(v, dict) for v in data.values()):
            for sp, obj in data.items():
                evo = obj.get("Evolution") if isinstance(obj, dict) else None
                if evo is not None and isinstance(obj, dict):
                    obj["Evolution"] = fix_one_evolution_list(evo, sp)
            return data

    return data

def main():
    ap = argparse.ArgumentParser(description="Fusionne les entrées Evolution avec 'Stade': null dans l'élément précédent: 'Lv...' → Minimum Level, sinon → Condition.")
    ap.add_argument("--in", dest="inp", required=True, help="Fichier JSON d'entrée")
    ap.add_argument("--out", dest="out", required=True, help="Fichier JSON de sortie")
    args = ap.parse_args()

    in_path = Path(args.inp)
    out_path = Path(args.out)

    data = load_json(in_path)
    fixed = process_root(data)
    dump_json(out_path, fixed)
    print(f"[ok] écrit {out_path}", file=sys.stdout)

if __name__ == "__main__":
    main()
