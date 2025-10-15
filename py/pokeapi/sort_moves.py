import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Union, Tuple

LevelType = Union[int, str]

def sort_level_up_moves(moves: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Sort level-up moves with "Evo" first, then by numeric level ascending.
    # If Level is a string convertible to int, treat as that int.
    # If Level is "Evo" (case-insensitive), it comes before numbers.
    # If Level is missing or unparseable, put at the end.
    # Stable for identical keys.
    def key_fn(entry: Dict[str, Any]) -> Tuple[int, int, str]:
        lvl = entry.get("Level", None)
        # Evo first
        if isinstance(lvl, str) and lvl.strip().lower() == "evo":
            return (0, -1, entry.get("Move",""))
        # numeric levels
        num_level = None
        if isinstance(lvl, (int, float)):
            try:
                num_level = int(lvl)
            except Exception:
                num_level = None
        elif isinstance(lvl, str):
            s = lvl.strip().lower().replace("lv", "").replace("level", "").replace(":", " ").replace("minimum", "").strip()
            digits = ''.join(ch if ch.isdigit() or ch==' ' else ' ' for ch in s).strip().split()
            if digits:
                try:
                    num_level = int(digits[0])
                except Exception:
                    num_level = None
        if num_level is not None:
            return (1, num_level, entry.get("Move",""))
        # unknown/missing levels go last
        return (2, 10**9, entry.get("Move",""))
    try:
        return sorted(moves, key=key_fn)
    except Exception:
        return moves

def sort_tm_tutor_moves(moves: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Sort TM/Tutor list alphabetically by Move name (case-insensitive).
    try:
        return sorted(moves, key=lambda e: (str(e.get("Move","")).casefold(), str(e.get("Type","")).casefold()))
    except Exception:
        return moves

def process_file(in_path: Path, out_path: Path, inplace: bool=False, indent: int=2) -> bool:
    try:
        with in_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[SKIP] {in_path.name}: not valid JSON ({e})")
        return False

    changed = False

    def handle_one(mon: Dict[str, Any]) -> None:
        nonlocal changed
        moves = mon.get("Moves")
        if not isinstance(moves, dict):
            return
        # Level Up
        lvl_list = moves.get("Level Up Move List")
        if isinstance(lvl_list, list):
            new_lvl_list = sort_level_up_moves(lvl_list)
            if new_lvl_list != lvl_list:
                moves["Level Up Move List"] = new_lvl_list
                changed = True
        # TM/Tutor
        tm_list = moves.get("TM/Tutor Moves List")
        if isinstance(tm_list, list):
            new_tm_list = sort_tm_tutor_moves(tm_list)
            if new_tm_list != tm_list:
                moves["TM/Tutor Moves List"] = new_tm_list
                changed = True

    if isinstance(data, list):
        for mon in data:
            if isinstance(mon, dict):
                handle_one(mon)
    elif isinstance(data, dict):
        handle_one(data)
    else:
        print(f"[WARN] {in_path.name}: unexpected JSON root type {type(data)}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
            f.write("\n")
        return True
    except Exception as e:
        print(f"[ERROR] Could not write {out_path}: {e}")
        return False

def main():
    p = argparse.ArgumentParser(description="Sort Level-Up and TM/Tutor moves in Pokémon JSON files.")
    p.add_argument("input_dir", help="Folder containing .json files to process")
    p.add_argument("-o","--output-dir", help="Folder to write sorted files into (default: in-place)", default=None)
    p.add_argument("--indent", type=int, default=2, help="JSON indentation (default: 2)")
    args = p.parse_args()

    in_dir = Path(args.input_dir)
    if not in_dir.exists() or not in_dir.is_dir():
        print(f"Input directory not found: {in_dir}")
        raise SystemExit(2)

    out_dir = Path(args.output_dir) if args.output_dir else in_dir
    inplace = (out_dir.resolve() == in_dir.resolve())

    count_total = 0
    count_ok = 0
    for path in sorted(in_dir.glob("*.json")):
        count_total += 1
        out_path = out_dir / path.name
        ok = process_file(path, out_path, inplace=inplace, indent=args.indent)
        if ok:
            count_ok += 1
            print(f"[OK]  {path.name} -> {out_path.relative_to(out_dir)}")
        else:
            print(f"[SKIP] {path.name}")

    print(f"Done. {count_ok}/{count_total} files written to {out_dir}")

if __name__ == "__main__":
    main()