#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json, re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Tuple

def parse_min_level_for_species(obj: Dict[str, Any]) -> tuple[bool, int | None]:
    species = obj.get("Species") or obj.get("species") or ""
    evo = obj.get("Evolution") or []
    if not isinstance(evo, list) or not species:
        return (False, None)
    current = None
    for row in evo:
        if isinstance(row, dict) and str(row.get("Species", "")).lower() == str(species).lower():
            current = row
            break
    if not isinstance(current, dict):
        return (False, None)
    try:
        stade = int(current.get("Stade"))
        evolved = stade > 1
    except Exception:
        evolved = False
    min_level = None
    txt = current.get("Minimum Level") or current.get("MinimumLevel") or ""
    if isinstance(txt, str):
        m = re.search(r"(\d+)", txt)
        if m:
            min_level = int(m.group(1))
    return (evolved, min_level)

def dedupe_tm_tutor(tm_list: List[str]) -> List[str]:
    keep = {}
    out = []
    for raw in tm_list or []:
        n = str(raw).strip()
        is_n = n.endswith(" (N)")
        base = n[:-4].strip() if is_n else n
        key = base.lower()
        if key not in keep:
            keep[key] = (base, is_n)
        else:
            b, had_n = keep[key]
            if is_n and not had_n:
                keep[key] = (base, True)
    for base, has_n in keep.values():
        out.append(base + (" (N)" if has_n else ""))
    return out

def process_pokemon(obj: Dict[str, Any]) -> Dict[str, Any]:
    moves = obj.get("Moves") or {}
    lvl = deepcopy(moves.get("Level Up Move List") or [])
    tm  = list(moves.get("TM/Tutor Moves List") or [])

    evolved, min_level = parse_min_level_for_species(obj)

    if evolved:
        new_lvl = []
        for m in lvl:
            L = m.get("Level")
            if L == 1:
                name = m.get("Move")
                if isinstance(name, str):
                    tm.append(f"{name} (N)")
            elif isinstance(L, int) and (min_level is not None) and (L < min_level):
                name = m.get("Move")
                if isinstance(name, str):
                    tm.append(f"{name} (N)")
            else:
                new_lvl.append(m)
        lvl = new_lvl

    levelup_bases = { str(m.get("Move")).strip() for m in (lvl or [])
                      if isinstance(m, dict) and isinstance(m.get("Move"), str) }
    tm = [ n for n in tm if (n[:-4].strip() if n.endswith(" (N)") else n) not in levelup_bases ]

    # Dedupe TM/Tutor (prefer (N))
    tm = dedupe_tm_tutor(tm)

    # 🔽 Nouveau : tri alphabétique
    tm.sort(key=lambda x: x.lower())

    # Write back
    obj = dict(obj)
    obj["Moves"] = {
        "Level Up Move List": lvl,
        "TM/Tutor Moves List": tm,
    }
    return obj

def load_any(path: Path) -> list[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if isinstance(data.get("Pokedex"), list):
            return data["Pokedex"]
        return [data]
    raise ValueError("Unsupported input JSON format.")

def save_like_input(out_path: Path, original, processed_list: list[Dict[str, Any]]) -> None:
    if isinstance(original, dict) and isinstance(original.get("Pokedex"), list):
        out_data = dict(original)
        out_data["Pokedex"] = processed_list
    elif isinstance(original, dict):
        out_data = processed_list[0] if processed_list else {}
    else:
        out_data = processed_list
    out_path.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")

def main():
    ap = argparse.ArgumentParser(description="Apply evolution move rules to a Pokédex JSON.")
    ap.add_argument("--in", dest="infile", required=True, help="Input JSON path (object, list, or {Pokedex: [...]})")
    ap.add_argument("--out", dest="outfile", required=True, help="Output JSON path")
    args = ap.parse_args()

    in_path = Path(args.infile); out_path = Path(args.outfile)
    original = json.loads(in_path.read_text(encoding="utf-8"))
    if isinstance(original, list):
        pokes = original
    elif isinstance(original, dict) and isinstance(original.get("Pokedex"), list):
        pokes = original["Pokedex"]
    elif isinstance(original, dict):
        pokes = [original]
    else:
        raise ValueError("Unsupported input JSON structure.")

    processed = [process_pokemon(p) for p in pokes]
    save_like_input(out_path, original, processed)
    print(f"[ok] Processed {len(processed)} entries -> {out_path}")

if __name__ == "__main__":
    main()
