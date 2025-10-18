#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json, sys, re
from pathlib import Path
from typing import Any, Dict, List, Tuple

MOVE_LIST_KEYS = ["TM/HM Move List", "Tutor Move List", "Egg Move List"]

def sort_key_move(entry: Dict[str, Any]) -> Tuple[int, str]:
    mv = entry.get("Move")
    if isinstance(mv, str) and mv.strip():
        return (0, mv.strip().lower())
    return (1, "")

def sort_lists_in_pokedex(pokedex: List[Dict[str, Any]]) -> Dict[str, int]:
    changed = 0
    species_seen = 0
    for sp in pokedex:
        if not isinstance(sp, dict):
            continue
        species_seen += 1
        moves = sp.get("Moves")
        if not isinstance(moves, dict):
            continue
        for lk in MOVE_LIST_KEYS:
            lst = moves.get(lk)
            if not isinstance(lst, list) or len(lst) <= 1:
                continue
            try:
                new_lst = sorted(lst, key=sort_key_move)
            except Exception:
                continue
            if new_lst != lst:
                moves[lk] = new_lst
                changed += 1
    return {"species_seen": species_seen, "lists_changed": changed}

def process_file(path: Path, write_back: bool, make_backup: bool, verbose: bool) -> Dict[str, int]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.stderr.write(f"[ERROR] Failed to parse JSON: {path} :: {e}\n")
        return {"error": 1}
    if not isinstance(data, list):
        sys.stderr.write(f"[WARN] JSON root is not a list (skipping): {path}\n")
        return {"skipped": 1}
    report = sort_lists_in_pokedex(data)
    if write_back and report.get("lists_changed"):
        if make_backup:
            bak = path.with_suffix(path.suffix + ".bak")
            bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if verbose:
        print(f"{path}: species={report.get('species_seen',0)} lists_changed={report.get('lists_changed',0)}")
    return report

def main():
    ap = argparse.ArgumentParser(description="Sort TM/HM, Tutor, and Egg move lists alphabetically in pokedex JSON files (recursive).");
    ap.add_argument("--root", required=True, help="Root directory to scan recursively")
    ap.add_argument("--pattern", default="pokedex*.json", help="Glob pattern (default: pokedex*.json)")
    ap.add_argument("--in-place", dest="in_place", action="store_true")
    ap.add_argument("--no-in-place", dest="in_place", action="store_false")
    ap.add_argument("--backup", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.set_defaults(in_place=True)
    args = ap.parse_args()
    root = Path(args.root)
    if not root.exists():
        sys.stderr.write(f"[ERROR] Root not found: {root}\n"); sys.exit(1)
    files = sorted(root.rglob(args.pattern))
    if not files:
        print(json.dumps({"files": 0, "total_lists_changed": 0}, ensure_ascii=False)); sys.exit(0)
    total_lists_changed = total_species = total_skipped = total_errors = 0
    for p in files:
        rep = process_file(p, write_back=(args.in_place and not args.dry_run), make_backup=args.backup, verbose=args.verbose)
        total_lists_changed += rep.get("lists_changed", 0)
        total_species += rep.get("species_seen", 0)
        total_skipped += rep.get("skipped", 0)
        total_errors += rep.get("error", 0)
    print(json.dumps({"files": len(files), "total_species_seen": total_species, "total_lists_changed": total_lists_changed, "skipped": total_skipped, "errors": total_errors}, ensure_ascii=False, indent=2))
    sys.exit(0 if total_errors == 0 else 2)

if __name__ == "__main__": main()
