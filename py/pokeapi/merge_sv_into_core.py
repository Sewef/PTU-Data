import argparse
import json
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


def replace_stats_and_moves(core_obj: Dict[str, Any], sv_obj: Dict[str, Any]) -> None:
    # Replace Base Stats
    sv_stats = deepcopy(sv_obj.get("Base Stats") or {})
    if not isinstance(sv_stats, dict):
        sv_stats = {}
    core_obj["Base Stats"] = sv_stats

    # Replace Moves with only the two lists
    sv_moves = sv_obj.get("Moves") or {}
    lvl = deepcopy(sv_moves.get("Level Up Move List") or [])
    tm  = deepcopy(sv_moves.get("TM/Tutor Moves List") or [])
    core_obj["Moves"] = {
        "Level Up Move List": lvl,
        "TM/Tutor Moves List": tm,
    }


def is_stone_evolution_for_species(core_obj: Dict[str, Any]) -> tuple[bool, int | None, str | None, list[dict] | None]:
    """
    Inspect core_obj["Evolution"] to decide if this object's Species entry is a stone evolution.
    Returns (is_stone, stage_of_species, prev_species_name, evolution_list)
    """
    evo = core_obj.get("Evolution")
    if not isinstance(evo, list):
        return (False, None, None, None)

    species_name = core_obj.get("Species") or core_obj.get("species")
    if not isinstance(species_name, str):
        return (False, None, None, evo)

    # Find this species entry in evolution list
    target = None
    for item in evo:
        if not isinstance(item, dict):
            continue
        if (item.get("Species") or item.get("species")) == species_name:
            target = item
            break

    if not target:
        return (False, None, None, evo)

    cond = target.get("Condition") or ""
    is_stone = isinstance(cond, str) and ("stone" in cond.lower())
    stage = target.get("Stade") or target.get("Stage")
    return (bool(is_stone), stage if isinstance(stage, int) else None, None, evo)


def find_prev_stage_species(evo_list: list[dict], current_stage: int) -> str | None:
    prev_candidates = [e for e in evo_list if isinstance(e, dict) and isinstance(e.get("Stade") or e.get("Stage"), int)]
    exact = [e for e in prev_candidates if (e.get("Stade") or e.get("Stage")) == current_stage - 1]
    if exact:
        return exact[0].get("Species") or exact[0].get("species")
    lower = [e for e in prev_candidates if (e.get("Stade") or e.get("Stage")) < current_stage]
    if not lower:
        return None
    lower.sort(key=lambda x: (x.get("Stade") or x.get("Stage")))
    return lower[-1].get("Species") or lower[-1].get("species")


def merge_sv_into_core(sv_list: List[Dict[str, Any]], core_list: List[Dict[str, Any]], strict: bool = False):
    idx = index_sv(sv_list)

    matched = 0
    missing_in_sv: List[str] = []
    stone_augmented: List[dict] = []

    for entry in core_list:
        sp = entry.get("Species") or entry.get("species")
        key = normalize_species(sp) if sp else None
        if not key or key not in idx:
            missing_in_sv.append(sp or "<unknown>")
            continue
        sv_obj = idx[key]
        replace_stats_and_moves(entry, sv_obj)
        matched += 1

        # Stone-evo rule
        is_stone, stage_num, _prev, evo_list = is_stone_evolution_for_species(entry)
        try:
            lvl_list = entry.get("Moves", {}).get("Level Up Move List") or []
        except Exception:
            lvl_list = []
        if is_stone and isinstance(lvl_list, list) and len(lvl_list) < 10 and isinstance(stage_num, int) and stage_num > 1:
            prev_name = find_prev_stage_species(evo_list or [], stage_num)
            if prev_name:
                prev_key = normalize_species(prev_name)
                prev_sv = idx.get(prev_key)
                if prev_sv:
                    prev_lvl = (prev_sv.get("Moves") or {}).get("Level Up Move List") or []
                    if isinstance(prev_lvl, list) and prev_lvl:
                        entry["Moves"]["Level Up Move List"] = lvl_list + deepcopy(prev_lvl)
                        stone_augmented.append({
                            "species": sp,
                            "reason": "stone-evolution with <10 level-up moves",
                            "prev_species": prev_name,
                            "added": len(prev_lvl)
                        })

    if strict and missing_in_sv:
        missing_str = ", ".join(missing_in_sv[:10])
        raise RuntimeError(f"{len(missing_in_sv)} Species from core not found in sv: {missing_str}{' ...' if len(missing_in_sv) > 10 else ''}")

    report = {
        "core_count": len(core_list),
        "sv_count": len(sv_list),
        "matched": matched,
        "missing_in_sv": missing_in_sv,
        "stone_augmented": stone_augmented,
    }
    return report


def restore_shape(core_list: List[Dict[str, Any]], was_dict: bool) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    if not was_dict:
        return core_list
    out: Dict[str, Any] = {}
    for obj in core_list:
        sp = obj.get("Species") or obj.get("species") or "Unknown"
        out[sp] = obj
    return out


def main():
    ap = argparse.ArgumentParser(description="Merge sv_ptu moves/stats into an existing core Pokédex JSON.")
    ap.add_argument("--sv", required=True, help="Path to sv_ptu.json (list or obj with results[])")
    ap.add_argument("--core", required=True, help="Path to pokedex_core.json (list or {Species: obj})")
    ap.add_argument("--out", required=True, help="Output JSON path")
    ap.add_argument("--strict", action="store_true", help="Fail if some core Species are not present in sv")
    args = ap.parse_args()

    sv_path = Path(args.sv)
    core_path = Path(args.core)
    out_path = Path(args.out)

    sv_list = load_sv(sv_path)
    core_list, was_dict = load_core(core_path)

    report = merge_sv_into_core(sv_list, core_list, strict=args.strict)

    out_data = restore_shape(core_list, was_dict)
    out_path.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()