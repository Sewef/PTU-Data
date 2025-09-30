#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, json, re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

def normalize_species(s: str) -> str:
    if not isinstance(s, str):
        s = str(s or "")
    s = s.strip().lower()
    rep = s.replace("_", " ").replace("’", "'").replace("–", "-").replace("—", "-")
    rep = " ".join(rep.split())
    rep = rep.replace(" ", "-")
    return rep

def index_sv(sv_data: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    idx: Dict[str, Dict[str, Any]] = {}
    for o in sv_data:
        sp = o.get("Species") or o.get("species")
        if not sp:
            continue
        idx[normalize_species(sp)] = o
    return idx

def load_sv(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        return data["results"]
    if isinstance(data, list):
        return data
    raise ValueError("sv input must be a list or an object with 'results' list")

def load_core(path: Path) -> Tuple[List[Dict[str, Any]], bool]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data, False
    elif isinstance(data, dict):
        if all(isinstance(v, dict) for v in data.values()):
            lst = []
            for sp, obj in data.items():
                if isinstance(obj, dict) and "Species" not in obj:
                    obj = {**obj, "Species": sp}
                lst.append(obj)
            return lst, True
        else:
            raise ValueError("Unsupported core JSON shape. Expected list or {Species: obj} dict.")
    else:
        raise ValueError("Unsupported core JSON type.")

def parse_min_level(evo_entry: Dict[str, Any]) -> int | None:
    txt = evo_entry.get("Minimum Level") or evo_entry.get("MinimumLevel") or evo_entry.get("Minimum") or ""
    if not isinstance(txt, str):
        return None
    m = re.search(r"(\d+)", txt)
    if m:
        return int(m.group(1))
    return None

def is_stone_evolution(evo_entry: Dict[str, Any]) -> bool:
    cond = evo_entry.get("Condition") or ""
    if not isinstance(cond, str):
        return False
    return "stone" in cond.lower()

def sort_level_up_list(lst: List[Dict[str, Any]]) -> None:
    lst.sort(key=lambda e: (0 if e.get("Level") == "Evo" else 1, e.get("Level") if isinstance(e.get("Level"), int) else 9999))

def dedupe_tm_tutor_list(names: list[str]) -> list[str]:
    keep = {}
    for raw in names or []:
        n = str(raw).strip()
        is_n = False
        base = n
        if n.endswith(" (N)"):
            is_n = True
            base = n[:-4].strip()
        key = base.lower()
        prev = keep.get(key)
        if prev is None:
            keep[key] = (base, is_n)
        else:
            b, had_n = prev
            if is_n and not had_n:
                keep[key] = (base, True)
    deduped = [ (b + (" (N)" if has_n else "")) for b, has_n in keep.values() ]
    deduped.sort()
    return deduped

def filter_tm_remove_levelup(tm_list: list[str], level_up_list: list[dict]) -> tuple[list[str], list[str]]:
    """
    Remove any TM/Tutor entries whose base name exists in Level Up Move List.
    Level Up base name is m["Move"]. TM base may have " (N)" suffix.
    """
    level_bases = set()
    for m in level_up_list or []:
        mv = m.get("Move")
        if isinstance(mv, str):
            level_bases.add(mv.strip())
    out = []
    removed = []
    for raw in tm_list or []:
        n = str(raw).strip()
        base = n[:-4].strip() if n.endswith(" (N)") else n
        if base not in level_bases:
            out.append(n)
        else:
            removed.append(n)
    return out, removed

def merge_and_apply_stone_rules(core_obj: Dict[str, Any], sv_obj: Dict[str, Any], sv_index: Dict[str, Dict[str, Any]], log_tm_pruned: bool = False) -> Tuple[int, int]:
    sv_stats = deepcopy(sv_obj.get("Base Stats") or {})
    if not isinstance(sv_stats, dict):
        sv_stats = {}
    core_obj["Base Stats"] = sv_stats

    sv_moves = sv_obj.get("Moves") or {}
    lvl = deepcopy(sv_moves.get("Level Up Move List") or [])
    tm  = deepcopy(sv_moves.get("TM/Tutor Moves List") or [])
    core_obj["Moves"] = {
        "Level Up Move List": lvl,
        "TM/Tutor Moves List": tm,
    }

    evolution = core_obj.get("Evolution") or []
    if not isinstance(evolution, list) or not evolution:
        # Remove TM entries that are also in Level Up, then dedupe
        _filtered, _removed = filter_tm_remove_levelup(core_obj["Moves"]["TM/Tutor Moves List"],
                                                                            core_obj["Moves"]["Level Up Move List"])
        if log_tm_pruned and _removed:
            spn = core_obj.get("Species") or core_obj.get("species") or "Unknown"
            print(f"[tm-pruned] {spn}: removed from TM/Tutor because in Level Up -> " + ", ".join(_removed))
        core_obj["Moves"]["TM/Tutor Moves List"] = dedupe_tm_tutor_list(_filtered)
        return (0, 0)

    this_sp = core_obj.get("Species") or core_obj.get("species") or ""
    this_row = None
    for row in evolution:
        if isinstance(row, dict) and normalize_species(row.get("Species", "")) == normalize_species(this_sp):
            this_row = row
            break
    if not this_row:
        _filtered, _removed = filter_tm_remove_levelup(core_obj["Moves"]["TM/Tutor Moves List"],
                                                                            core_obj["Moves"]["Level Up Move List"])
        if log_tm_pruned and _removed:
            spn = core_obj.get("Species") or core_obj.get("species") or "Unknown"
            print(f"[tm-pruned] {spn}: removed from TM/Tutor because in Level Up -> " + ", ".join(_removed))
        core_obj["Moves"]["TM/Tutor Moves List"] = dedupe_tm_tutor_list(_filtered)
        return (0, 0)

    added_from_parent = 0
    moved_below_min = 0

    if is_stone_evolution(this_row):
        try:
            stade = int(this_row.get("Stade"))
        except Exception:
            stade = None
        parent_species = None
        if stade and stade > 1:
            for row in evolution:
                try:
                    if int(row.get("Stade")) == (stade - 1):
                        parent_species = row.get("Species")
                        break
                except Exception:
                    continue

        if parent_species and len(core_obj["Moves"]["Level Up Move List"]) < 10:
            parent_key = normalize_species(parent_species)
            parent_sv = sv_index.get(parent_key)
            if parent_sv:
                parent_lvl = deepcopy((parent_sv.get("Moves") or {}).get("Level Up Move List") or [])
                core_obj["Moves"]["Level Up Move List"].extend(parent_lvl)
                added_from_parent = len(parent_lvl)
                print(f"[stone] {this_sp}: appended {added_from_parent} level-up moves from parent stage ({parent_species}).")
            else:
                print(f"[stone] {this_sp}: parent stage '{parent_species}' not found in sv_ptu, cannot append.", flush=True)

        # 2) KEEP moves below Minimum Level in Level Up (no relocation).
        #    BUT always move Level 1 moves to TM/Tutor (N)
        new_level_up: List[Dict[str, Any]] = []
        for m in core_obj["Moves"]["Level Up Move List"]:
            lvl_val = m.get("Level")
            if lvl_val == 1:
                name = m.get("Move")
                if isinstance(name, str):
                    core_obj["Moves"]["TM/Tutor Moves List"].append(f"{name} (N)")
                # drop from Level-Up
            else:
                new_level_up.append(m)
        core_obj["Moves"]["Level Up Move List"] = new_level_up


        sort_level_up_list(core_obj["Moves"]["Level Up Move List"])

    # Always: remove TM entries present in Level Up, then dedupe and sort
    _filtered, _removed = filter_tm_remove_levelup(core_obj["Moves"]["TM/Tutor Moves List"],
                                                                        core_obj["Moves"]["Level Up Move List"])
    if log_tm_pruned and _removed:
        spn = core_obj.get("Species") or core_obj.get("species") or "Unknown"
        print(f"[tm-pruned] {spn}: removed from TM/Tutor because in Level Up -> " + ", ".join(_removed))
    core_obj["Moves"]["TM/Tutor Moves List"] = dedupe_tm_tutor_list(_filtered)

    return (added_from_parent, moved_below_min)

def merge_all(sv_list: List[Dict[str, Any]], core_list: List[Dict[str, Any]], strict: bool = False, log_tm_pruned: bool = False) -> Dict[str, Any]:
    sv_index = index_sv(sv_list)
    matched = 0
    missing_in_sv: List[str] = []
    for entry in core_list:
        sp = entry.get("Species") or entry.get("species")
        key = normalize_species(sp) if sp else None
        if not key or key not in sv_index:
            missing_in_sv.append(sp or "<unknown>")
            continue
        sv_obj = sv_index[key]
        merge_and_apply_stone_rules(entry, sv_obj, sv_index, log_tm_pruned=log_tm_pruned)
        matched += 1
    if strict and missing_in_sv:
        missing_str = ", ".join(missing_in_sv[:10])
        raise RuntimeError(f"{len(missing_in_sv)} Species from core not found in sv: {missing_str}{' ...' if len(missing_in_sv) > 10 else ''}")
    report = {"core_count": len(core_list), "sv_count": len(sv_list), "matched": matched, "missing_in_sv": missing_in_sv}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report

def restore_shape(core_list: List[Dict[str, Any]], was_dict: bool):
    if not was_dict:
        return core_list
    out: Dict[str, Any] = {}
    for obj in core_list:
        sp = obj.get("Species") or obj.get("species") or "Unknown"
        out[sp] = obj
    return out

def main():
    ap = argparse.ArgumentParser(description="Merge sv_ptu into core with Stone-evolution rules and list hygiene.")
    ap.add_argument("--sv", required=True, help="Path to sv_ptu.json (list or obj with results[])")
    ap.add_argument("--core", required=True, help="Path to pokedex_core.json (list or {Species: obj})")
    ap.add_argument("--out", required=True, help="Output JSON path")
    ap.add_argument("--strict", action="store_true", help="Fail if some core Species are not present in sv")
    ap.add_argument("--log-tm-pruned", action="store_true", help="Log names removed from TM/Tutor because present in Level Up")
    args = ap.parse_args()

    sv_path = Path(args.sv); core_path = Path(args.core); out_path = Path(args.out)
    sv_list = load_sv(sv_path)
    core_list, was_dict = load_core(core_path)
    merge_all(sv_list, core_list, strict=args.strict, log_tm_pruned=args.log_tm_pruned)
    out_data = restore_shape(core_list, was_dict)
    out_path.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] wrote {out_path}")

if __name__ == "__main__":
    main()
