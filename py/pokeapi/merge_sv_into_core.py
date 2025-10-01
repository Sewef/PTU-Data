#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, json, re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Tuple

def normalize_species(s: str) -> str:
    if not isinstance(s, str):
        s = str(s or "")
    s = s.strip().lower()
    rep = s.replace("_", " ").replace("’", "'").replace("–", "-").replace("—", "-")
    rep = " ".join(rep.split())
    rep = rep.replace(" ", "-")
    return rep

def normalize_move_name(n: str) -> str:
    n = (n or "").strip()
    if n.endswith(" (N)"):
        n = n[:-4].strip()
    return n

def normal_case_method(m: str | None) -> str | None:
    if not m:
        return None
    m = m.strip().lower()
    if m in ("level-up", "level up"):
        return "Level-Up"
    return m.capitalize()

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

def pokemon_types_from_core(core_obj: dict) -> list[str]:
    t = ((core_obj.get("Basic Information") or {}).get("Type")) or []
    return [x for x in t if isinstance(x, str)]

def add_tag(tag_list: list[str], tag: str) -> None:
    if tag and tag not in tag_list:
        tag_list.append(tag)

def tag_stab_if_applicable(entry: dict, poke_types: list[str]) -> None:
    # Intentionally disabled unless you want STAB tagging here
    return
    t = entry.get("Type")
    if t and t in poke_types:
        add_tag(entry["Tags"], "Stab")

def parse_tm_string_to_obj(s: str) -> dict:
    s = (s or "").strip()
    tags: List[str] = []
    base = s
    if s.endswith(" (N)"):
        base = s[:-4].strip()
        tags.append("N")
    return {"Move": base, "Type": None, "Tags": tags, "Method": None}

def unify_tm_tutor_objects(tm_list: list, poke_types: list[str]) -> list[dict]:
    """
    Normalize TM/Tutor entries to objects {Move, Type, Tags, Method}.
    - Carry '(N)' into tag 'N'
    - Method preference when merging duplicates: prefer any non 'Level-Up'; else 'Level-Up' if present; else None (then default to 'Level-Up')
    - Deduplicate by Move (case-insensitive), merge tags, keep a known Type if available
    - Sort alphabetically by Move
    """
    objs: list[dict] = []
    for x in tm_list or []:
        if isinstance(x, str):
            obj = parse_tm_string_to_obj(x)
        elif isinstance(x, dict):
            obj = {"Move": normalize_move_name(x.get("Move")),
                   "Type": x.get("Type"),
                   "Tags": list(x.get("Tags") or []),
                   "Method": normal_case_method(x.get("Method") or x.get("method"))}
        else:
            continue
        obj["Move"] = normalize_move_name(obj.get("Move"))
        if "Tags" not in obj or not isinstance(obj["Tags"], list):
            obj["Tags"] = []
        # STAB tagging disabled here, but keep hook:
        tag_stab_if_applicable(obj, poke_types)
        objs.append(obj)

    def better_method(current: str | None, candidate: str | None) -> str | None:
        cur = current or None
        cand = candidate or None
        if cand and cand != "Level-Up":
            if (cur is None) or (cur == "Level-Up"):
                return cand
        return cur or cand

    by_key: dict[str, dict] = {}
    for o in objs:
        base = normalize_move_name(o.get("Move"))
        key = base.lower()
        if key not in by_key:
            by_key[key] = {"Move": base, "Type": o.get("Type"), "Tags": list(dict.fromkeys(o.get("Tags") or [])), "Method": o.get("Method")}
        else:
            tgt = by_key[key]
            if not tgt.get("Type") and o.get("Type"):
                tgt["Type"] = o["Type"]
            for tg in (o.get("Tags") or []):
                add_tag(tgt["Tags"], tg)
            tgt["Method"] = better_method(tgt.get("Method"), o.get("Method"))

    # Default Method to 'Level-Up' when still None
    for v in by_key.values():
        if not v.get("Method"):
            v["Method"] = "Level-Up"

    out = list(by_key.values())
    out.sort(key=lambda d: (d.get("Move") or "").lower())
    return out

def filter_tm_remove_levelup_objs(tm_objs: list[dict], level_up_list: list[dict]) -> tuple[list[dict], list[str]]:
    level_bases = set()
    for m in level_up_list or []:
        mv = m.get("Move")
        if isinstance(mv, str):
            level_bases.add(normalize_move_name(mv))
    out: list[dict] = []
    removed: list[str] = []
    for obj in tm_objs or []:
        base = normalize_move_name(obj.get("Move"))
        if base not in level_bases:
            out.append(obj)
        else:
            removed.append(base + (" (N)" if "N" in (obj.get("Tags") or []) else ""))
    return out, removed

def load_gen8_deleted_moves(path: str) -> set[str]:
    deleted = set()
    if not path:
        return deleted
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                name = parts[1] if len(parts) > 1 else parts[0]
                name = name.strip()
                if name:
                    deleted.add(normalize_move_name(name))
    except Exception:
        pass
    return deleted

def capture_kept_moves(old_moves: dict, deleted_set: set[str], poke_types: list[str]) -> tuple[list[dict], list[dict]]:
    kept_levelup: list[dict] = []
    kept_tm: list[dict] = []
    for m in (old_moves or {}).get("Level Up Move List", []) or []:
        if not isinstance(m, dict):
            continue
        mv = m.get("Move")
        if not isinstance(mv, str):
            continue
        base = normalize_move_name(mv)
        if base in deleted_set:
            kept = {"Level": m.get("Level"), "Move": base, "Type": m.get("Type"), "Tags": []}
            tag_stab_if_applicable(kept, poke_types)
            kept_levelup.append(kept)
    for x in (old_moves or {}).get("TM/Tutor Moves List", []) or []:
        if isinstance(x, str):
            obj = parse_tm_string_to_obj(x)
        elif isinstance(x, dict):
            obj = {"Move": normalize_move_name(x.get("Move")), "Type": x.get("Type"), "Tags": list(x.get("Tags") or []), "Method": normal_case_method(x.get("Method") or x.get("method"))}
        else:
            continue
        base = normalize_move_name(obj.get("Move"))
        if base in deleted_set:
            tag_stab_if_applicable(obj, poke_types)
            kept_tm.append(obj)
    return kept_levelup, kept_tm

def merge_and_apply_rules(core_obj: Dict[str, Any], sv_obj: Dict[str, Any], sv_index: Dict[str, Dict[str, Any]],
                          log_tm_pruned: bool = False, deleted_set: set[str] | None = None) -> Tuple[int, int]:
    if deleted_set is None:
        deleted_set = set()

    old_moves = deepcopy(core_obj.get("Moves") or {})
    poke_types = pokemon_types_from_core(core_obj)

    sv_stats = deepcopy(sv_obj.get("Base Stats") or {})
    if not isinstance(sv_stats, dict):
        sv_stats = {}
    core_obj["Base Stats"] = sv_stats

    sv_moves = sv_obj.get("Moves") or {}
    lvl = deepcopy(sv_moves.get("Level Up Move List") or [])
    tm  = deepcopy(sv_moves.get("TM/Tutor Moves List") or [])
    core_obj["Moves"] = {"Level Up Move List": lvl, "TM/Tutor Moves List": tm}

    evolution = core_obj.get("Evolution") or []
    if not isinstance(evolution, list):
        evolution = []
    this_sp = core_obj.get("Species") or core_obj.get("species") or ""
    this_row = None
    for row in evolution:
        if isinstance(row, dict) and normalize_species(row.get("Species", "")) == normalize_species(this_sp):
            this_row = row
            break

    added_from_parent = 0

    if isinstance(this_row, dict) and is_stone_evolution(this_row):
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
        new_level_up: List[Dict[str, Any]] = []
        for m in core_obj["Moves"]["Level Up Move List"]:
            lvl_val = m.get("Level")
            if lvl_val == 1:
                name = m.get("Move")
                if isinstance(name, str):
                    core_obj["Moves"]["TM/Tutor Moves List"].append({
                        "Move": normalize_move_name(name),
                        "Type": m.get("Type"),
                        "Tags": ["N"],
                        "Method": "Level-Up",
                    })
            else:
                new_level_up.append(m)
        core_obj["Moves"]["Level Up Move List"] = new_level_up
        sort_level_up_list(core_obj["Moves"]["Level Up Move List"])

    kept_levelup, kept_tm = capture_kept_moves(old_moves, deleted_set, poke_types)

    existing_lv_keys = {(m.get("Move"), m.get("Level")) for m in core_obj["Moves"]["Level Up Move List"] if isinstance(m, dict)}
    for km in kept_levelup:
        key = (km.get("Move"), km.get("Level"))
        if key not in existing_lv_keys:
            km = dict(km)
            km["Tags"] = list(km.get("Tags") or [])
            add_tag(km["Tags"], "Kept")
            core_obj["Moves"]["Level Up Move List"].append(km)
    sort_level_up_list(core_obj["Moves"]["Level Up Move List"])

    tm_objs = []
    for x in core_obj["Moves"]["TM/Tutor Moves List"] or []:
        if isinstance(x, dict):
            tm_objs.append({
                "Move": normalize_move_name(x.get("Move")),
                "Type": x.get("Type"),
                "Tags": list(x.get("Tags") or []),
                "Method": normal_case_method(x.get("Method") or x.get("method")),
            })
        elif isinstance(x, str):
            tm_objs.append(parse_tm_string_to_obj(x))
        else:
            continue

    for kt in kept_tm:
        tm_objs.append({
            "Move": normalize_move_name(kt.get("Move")),
            "Type": kt.get("Type"),
            "Tags": list(kt.get("Tags") or []) + ["Kept"],
            "Method": normal_case_method(kt.get("Method") or kt.get("method")),
        })

    tm_objs, removed_names = filter_tm_remove_levelup_objs(tm_objs, core_obj["Moves"]["Level Up Move List"])
    if log_tm_pruned and removed_names:
        spn = core_obj.get("Species") or core_obj.get("species") or "Unknown"
        print(f"[tm-pruned] {spn}: removed from TM/Tutor because in Level Up -> " + ", ".join(removed_names))

    tm_objs = unify_tm_tutor_objects(tm_objs, poke_types)
    core_obj["Moves"]["TM/Tutor Moves List"] = tm_objs

    return (added_from_parent, 0)

def merge_all(sv_list: List[Dict[str, Any]], core_list: List[Dict[str, Any]], strict: bool = False,
              log_tm_pruned: bool = False, deleted_set: set[str] | None = None) -> Dict[str, Any]:
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
        merge_and_apply_rules(entry, sv_obj, sv_index, log_tm_pruned=log_tm_pruned, deleted_set=(deleted_set or set()))
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
    ap = argparse.ArgumentParser(description="Merge sv_ptu into core with stone-evo rules, TM objects (+Method), and Gen8 Kept reinjection.")
    ap.add_argument("--sv", required=True, help="Path to sv_ptu.json (list or obj with results[])")
    ap.add_argument("--core", required=True, help="Path to pokedex_core.json (list or {Species: obj})")
    ap.add_argument("--out", required=True, help="Output JSON path")
    ap.add_argument("--strict", action="store_true", help="Fail if some core Species are not present in sv")
    ap.add_argument("--log-tm-pruned", action="store_true", help="Log names removed from TM/Tutor because present in Level Up")
    ap.add_argument("--gen8-deleted", help="Path to gen8_deleted_moves.txt to keep and reinject those moves with {Tags:[\"Kept\"]}")
    args = ap.parse_args()

    sv_path = Path(args.sv); core_path = Path(args.core); out_path = Path(args.out)
    sv_list = load_sv(sv_path)
    core_list, was_dict = load_core(core_path)
    deleted_set = load_gen8_deleted_moves(args.gen8_deleted) if args.gen8_deleted else set()

    merge_all(sv_list, core_list, strict=args.strict, log_tm_pruned=args.log_tm_pruned, deleted_set=deleted_set)
    out_data = restore_shape(core_list, was_dict)
    out_path.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] wrote {out_path}")

if __name__ == "__main__":
    main()
