#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Update PTU Pokedex move lists using PokeAPI, generations 9..6.

Rules:
- Remove existing Level Up / TM/HM / Tutor lists before writing new ones.
- TM: gather all moves with method "machine" from gens 9..6 (inclusive), dedupe, sort alpha.
- Tutor: same with method "tutor".
- Egg: same with method "egg".
- Level Up:
    * Take the most recent generation available for this Pokémon (<= max-gen).
      Use only that version group's level-up moves as the base (with their levels).
    * Then, for each older game (down to min-gen), append its level-up moves
      that are not already present, with Tags: ["Legacy", "<jeu source>"], where
      "<jeu source>" is the version_group's nice name.
- Ignore silently if a mapping species doesn't exist in the pokedex JSON.
- Log HTTP 400 errors but don't crash.
- Parallelize HTTP calls.

Inputs:
    --pokedex /path/to/pokedex_core.json
    --mapping /path/to/mapping.csv   (columns: species,othername)
    --out     /path/to/output.json   (default: overwrite input pokedex)
    --min-gen 6 --max-gen 9          (defaults)
"""

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Set

import aiohttp

POKEAPI_BASE = "https://pokeapi.co/api/v2"

# Version-group to generation mapping (explicit and future-proof if extended).
# Keys are PokeAPI version_group "name" slugs; values are (gen_number, pretty_label).
VERSION_GROUPS = {
    # Gen 9
    "scarlet-violet": (9, "Scarlet/Violet"),
    # Gen 8
    "sword-shield": (8, "Sword/Shield"),
    "brilliant-diamond-and-shining-pearl": (8, "BDSP"),
    "legends-arceus": (8, "Legends: Arceus"),
    # Gen 7
    "sun-moon": (7, "Sun/Moon"),
    "ultra-sun-ultra-moon": (7, "Ultra Sun/Ultra Moon"),
    "lets-go-pikachu-lets-go-eevee": (7, "Let's Go Pikachu/Eevee"),
    # Gen 6
    "x-y": (6, "X/Y"),
    "omega-ruby-alpha-sapphire": (6, "Omega Ruby/Alpha Sapphire"),

    # ➜ Gen 5 (AJOUTER)
    "black-white": (5, "Black/White"),
    "black-2-white-2": (5, "Black 2/White 2"),

    # ➜ Gen 4 (AJOUTER)
    "diamond-pearl": (4, "Diamond/Pearl"),
    "platinum": (4, "Platinum"),
    "heartgold-soulsilver": (4, "HeartGold/SoulSilver"),
}

MOVE_METHOD_SLUG_TO_KIND = {
    "level-up": "level-up",
    "machine": "machine",
    "tutor": "tutor",
    "egg": "egg",
}

# Order (priority) for selecting the "most recent" version group inside the same generation,
# when a Pokémon has multiple entries in the same gen. Larger index = higher priority.
VERSION_GROUP_PRIORITY = [
    # ➜ Gen 4 (AJOUTER d'abord, plus ancien)
    "diamond-pearl",
    "platinum",
    "heartgold-soulsilver",

    # ➜ Gen 5 (AJOUTER ensuite)
    "black-white",
    "black-2-white-2",

    # Gen 6
    "x-y",
    "omega-ruby-alpha-sapphire",
    # Gen 7
    "sun-moon",
    "ultra-sun-ultra-moon",
    "lets-go-pikachu-lets-go-eevee",
    # Gen 8
    "sword-shield",
    "brilliant-diamond-and-shining-pearl",
    "legends-arceus",
    # Gen 9 (le plus récent à la fin)
    "scarlet-violet",
]

VG_PRIORITY_RANK = {vg: i for i, vg in enumerate(VERSION_GROUP_PRIORITY)}

def to_title(name: str) -> str:
    """Convert pokeapi 'fire-blast' -> 'Fire Blast'."""
    if not name:
        return name
    return " ".join(w.capitalize() for w in name.replace("-", " ").split())

def cap_type(t: str) -> str:
    return t.capitalize() if t else t

def unique_sorted_names(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Dedupe by Move name (case-insensitive), then sort by Move alphabetically."""
    seen = {}
    for it in items:
        key = it.get("Move", "").lower()
        if key and key not in seen:
            seen[key] = it
    return sorted(seen.values(), key=lambda x: x.get("Move",""))

async def fetch_json(session: aiohttp.ClientSession, url: str) -> Optional[Dict[str, Any]]:
    try:
        async with session.get(url) as resp:
            if resp.status == 400:
                sys.stderr.write(f"[WARN] 400 at {url}\n")
                return None
            resp.raise_for_status()
            return await resp.json()
    except aiohttp.ClientResponseError as e:
        if e.status == 400:
            sys.stderr.write(f"[WARN] 400 at {url}\n")
            return None
        sys.stderr.write(f"[ERROR] HTTP {e.status} for {url}: {e}\n")
        return None
    except Exception as e:
        sys.stderr.write(f"[ERROR] {url}: {e}\n")
        return None

async def get_move_type(session: aiohttp.ClientSession, move_name_slug: str, cache: Dict[str, str]) -> Optional[str]:
    if move_name_slug in cache:
        return cache[move_name_slug]
    data = await fetch_json(session, f"{POKEAPI_BASE}/move/{move_name_slug}")
    if not data:
        return None
    tname = data.get("type", {}).get("name")
    t = cap_type(tname) if tname else None
    if t:
        cache[move_name_slug] = t
    return t

def pick_latest_version_group(vgd_list: List[Dict[str, Any]], max_gen: int) -> Optional[str]:
    """
    From version_group_details list, pick the most recent version_group.name within <= max_gen
    using VERSION_GROUPS + VERSION_GROUP_PRIORITY. Return the chosen version_group slug or None.
    """
    best_vg = None
    best_rank = -1
    for vgd in vgd_list:
        vg = vgd.get("version_group", {}).get("name")
        if vg in VERSION_GROUPS:
            gen, _ = VERSION_GROUPS[vg]
            if gen <= max_gen:
                rank = VG_PRIORITY_RANK.get(vg, -1)
                if rank > best_rank:
                    best_rank = rank
                    best_vg = vg
    return best_vg

def version_group_gen(vg: str) -> Optional[int]:
    info = VERSION_GROUPS.get(vg)
    return info[0] if info else None

def version_group_label(vg: str) -> str:
    info = VERSION_GROUPS.get(vg)
    return info[1] if info else vg

async def build_moves_for_pokemon(
    session: aiohttp.ClientSession,
    pokemon_slug: str,
    min_gen: int,
    max_gen: int,
    move_type_cache: Dict[str, str],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Return dict with keys:
        level_up: list of dicts with {"Level": int or "Evo"/"Start", "Move": str, "Type": str, "Tags": [...]?}
        machine:  list of dicts {"Move","Type","Method":"Machine"}
        tutor:    list of dicts {"Move","Type","Method":"Tutor"}
        egg:      list of dicts {"Move","Type","Method":"Egg"}
    """
    data = await fetch_json(session, f"{POKEAPI_BASE}/pokemon/{pokemon_slug}")
    if not data:
        return {"level_up": [], "machine": [], "tutor": [], "egg": []}
    # Get species URL from the /pokemon data to avoid alt-form slugs 404
    species_url = (data.get("species") or {}).get("url")
    evolved = False
    if species_url:
        species_json = await fetch_json(session, species_url)
        evolved = bool(species_json and species_json.get("evolves_from_species"))

    # Collect by method and version_group
    per_method: Dict[str, Dict[str, List[Tuple[int, str]]]] = {
        "level-up": {},
        "machine": {},
        "tutor": {},
        "egg": {},
    }
    all_moves = data.get("moves", [])
    for m in all_moves:
        move_slug = m.get("move", {}).get("name")  # e.g., "razor-leaf"
        vgd_list = m.get("version_group_details", [])
        for vgd in vgd_list:
            vg = vgd.get("version_group", {}).get("name")
            if vg not in VERSION_GROUPS:
                continue
            gen = VERSION_GROUPS[vg][0]
            if not (min_gen <= gen <= max_gen):
                continue
            method_slug = vgd.get("move_learn_method", {}).get("name")  # "level-up", "machine", "tutor", "egg"
            if method_slug not in MOVE_METHOD_SLUG_TO_KIND:
                continue
            level = vgd.get("level_learned_at") or 0
            per_method.setdefault(method_slug, {}).setdefault(vg, []).append((level, move_slug))

        # TM/Machine, Tutor, Egg: collect across gens min..max, avec Tags Legacy selon le jeu source
    async def as_move_dicts(pairs_by_vg: Dict[str, List[Tuple[int, str]]], method_label: str) -> List[Dict[str, Any]]:
        out = []
        for vg, pairs in pairs_by_vg.items():
            gen = version_group_gen(vg)
            if gen is None or gen < min_gen or gen > max_gen:
                continue
            label = version_group_label(vg)
            for _, slug in pairs:
                t = await get_move_type(session, slug, move_type_cache)
                tags = []
                # Si ce n’est pas de la gen max, on ajoute le tag Legacy
                if gen < max_gen:
                    tags = ["Legacy", label]
                out.append({"Move": to_title(slug), "Type": t or None, "Tags": tags, "Method": method_label})
        return out

    machine = unique_sorted_names(await as_move_dicts(per_method.get("machine", {}), "Machine"))
    tutor   = unique_sorted_names(await as_move_dicts(per_method.get("tutor", {}), "Tutor"))
    if evolved:
        egg = []
    else:
        egg = unique_sorted_names(await as_move_dicts(per_method.get("egg", {}), "Egg"))

        # Level-up:
    # 1) Choose latest VG (<= max_gen) that has level-up entries. Use only its moves (with levels) as base.
    # 2) For each older VG (down to min_gen), add moves — even duplicates — if the LEVEL differs.
    #    Add Tags ["Legacy","<jeu source>"].
    lv_vg_to_pairs = per_method.get("level-up", {})

    latest_vg = None
    best_rank = -1
    for vg in lv_vg_to_pairs.keys():
        rank = VG_PRIORITY_RANK.get(vg, -1)
        if rank > best_rank:
            best_rank = rank
            latest_vg = vg

    level_up: List[Dict[str, Any]] = []
    have_pairs: Set[Tuple[str, str]] = set()  # (move_lower, level_str)

    async def level_entry(level: int, slug: str, tags: Optional[List[str]] = None) -> Dict[str, Any]:
        t = await get_move_type(session, slug, move_type_cache)
        entry: Dict[str, Any] = {"Move": to_title(slug), "Type": t or None}
        if level > 0:
            entry["Level"] = level
            lvl_key = str(level)
        else:
            entry["Level"] = "Evo"
            lvl_key = "Evo"
        if tags:
            entry["Tags"] = tags
        return entry, lvl_key

    if latest_vg:
        # Base from latest
        base = sorted(lv_vg_to_pairs[latest_vg], key=lambda x: (x[0], x[1]))
        for lvl, slug in base:
            e, lvl_key = await level_entry(lvl, slug)
            level_up.append(e)
            have_pairs.add((e["Move"].lower(), lvl_key))

        # Older legacy additions — allow same move if level differs
        older_vgs = [
            vg for vg in sorted(lv_vg_to_pairs.keys(), key=lambda k: VG_PRIORITY_RANK.get(k, -1), reverse=True)
            if VG_PRIORITY_RANK.get(vg, -1) < VG_PRIORITY_RANK.get(latest_vg, -1)
        ]
        for vg in older_vgs:
            gen = version_group_gen(vg)
            if gen is None or gen < min_gen:
                continue
            label = version_group_label(vg)
            for lvl, slug in sorted(lv_vg_to_pairs[vg], key=lambda x: (x[0], x[1])):
                e, lvl_key = await level_entry(lvl, slug, tags=["Legacy", label])
                key = (e["Move"].lower(), lvl_key)
                if key in have_pairs:
                    continue  # skip exact same move+level only
                level_up.append(e)
                have_pairs.add(key)
    else:
        level_up = []

    # Sort with "Evo" first, then numeric ascending
    def sort_key(e: Dict[str, Any]):
        lvl = e.get("Level")
        if isinstance(lvl, str):  # "Evo" first
            return (0, 0, e["Move"])
        return (1, int(lvl), e["Move"])

    level_up = sorted(level_up, key=sort_key)

    return {"level_up": level_up, "machine": machine, "tutor": tutor, "egg": egg}



async def main_async(args):
    pokedex_path = Path(args.pokedex).expanduser()
    out_path = Path(args.out).expanduser() if args.out else pokedex_path
    mapping_path = Path(args.mapping).expanduser()

    with pokedex_path.open("r", encoding="utf-8") as f:
        try:
            pokedex: List[Dict[str, Any]] = json.load(f)
        except json.JSONDecodeError as e:
            sys.stderr.write(f"Failed to parse pokedex JSON: {e}\n")
            return 2

    # Build name -> index map
    idx_by_species: Dict[str, int] = {}
    for i, sp in enumerate(pokedex):
        name = sp.get("Species")
        if isinstance(name, str):
            idx_by_species[name] = i

    # Read mapping
    mapping: List[Tuple[str, str]] = []
    with mapping_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            species = (row.get("species") or "").strip()
            other = (row.get("othername") or "").strip()
            if species and other:
                mapping.append((species, other))

    # Prepare HTTP client & cache
    timeout = aiohttp.ClientTimeout(total=60)
    conn = aiohttp.TCPConnector(limit=30)  # parallelism cap
    move_type_cache: Dict[str, str] = {}

    async with aiohttp.ClientSession(timeout=timeout, connector=conn) as session:
        # Process in small batches for fairness
        sem = asyncio.Semaphore(30)

        async def process_one(species: str, slug: str):
            if species not in idx_by_species:
                # Silently ignore missing species in pokedex
                return
            async with sem:
                moves = await build_moves_for_pokemon(session, slug, args.min_gen, args.max_gen, move_type_cache)
            # Mutate pokedex entry
            entry = pokedex[idx_by_species[species]]
            moves_block = entry.setdefault("Moves", {})
            # Remove old lists
            for k in ["Level Up Move List", "TM/HM Move List", "Tutor Move List", "Egg Move List"]:
                if k in moves_block:
                    del moves_block[k]
            # Write new lists
            moves_block["Level Up Move List"] = moves["level_up"]
            moves_block["TM/HM Move List"]   = moves["machine"]
            moves_block["Tutor Move List"]   = moves["tutor"]
            moves_block["Egg Move List"]     = moves["egg"]

        tasks = [process_one(species, other) for species, other in mapping]
        # Run with progress
        for chunk_start in range(0, len(tasks), 50):
            await asyncio.gather(*tasks[chunk_start:chunk_start+50])

    # Save
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(pokedex, f, ensure_ascii=False, indent=2)

    print(f"Updated pokedex written to: {out_path}")
    return 0

def parse_args():
    p = argparse.ArgumentParser(description="Update PTU pokedex move lists from PokeAPI.")
    p.add_argument("--pokedex", required=True, help="Path to pokedex_core.json")
    p.add_argument("--mapping", required=True, help="Path to mapping.csv (columns: species,othername)")
    p.add_argument("--out", default=None, help="Output path (default: overwrite pokedex)")
    p.add_argument("--min-gen", type=int, default=6, help="Minimum generation (inclusive), default 6")
    p.add_argument("--max-gen", type=int, default=9, help="Maximum generation (inclusive), default 9")
    return p.parse_args()

def main():
    args = parse_args()
    try:
        exit_code = asyncio.run(main_async(args))
    except KeyboardInterrupt:
        sys.stderr.write("Interrupted.\n")
        exit_code = 130
    except Exception as e:
        sys.stderr.write(f"Fatal error: {e}\n")
        exit_code = 1
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
