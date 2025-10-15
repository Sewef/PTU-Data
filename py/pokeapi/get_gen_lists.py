#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Rebuild move lists from PokeAPI (gens 9->6).
- Removes existing Level Up / TM/HM / Tutor lists.
- TM/HM + Tutor: all "machine" moves seen in gens 9..6 (dedup, alpha sort).
- Level Up: take the most recent gen (9..6) with level-ups as base (no tags),
  then add older games (down to gen6) level-ups tagged ["Legacy", "<jeu source>"].

Usage:
  python rebuild_moves_from_pokeapi.py \
      --pokedex /mnt/data/pokedex_core.json \
      --mapping /mnt/data/mapping.csv \
      --out /mnt/data/pokedex_core.moves.updated.json \
      [--max-conns 12]

Notes:
- Uses asyncio + aiohttp for parallel calls.
- Caches /move/{name} calls to fetch types.
- Version-group -> generation and label mapping is defined below.
"""

import argparse
import asyncio
import json
import sys
from collections import defaultdict, OrderedDict
from pathlib import Path

import aiohttp
import csv

POKEAPI_BASE = "https://pokeapi.co/api/v2"

# --- Version-group → (generation, label for tag) ----------------------------
# On cible Gens 9 à 6 uniquement.
VG_MAP = {
    # Gen 9
    "scarlet-violet":                (9, "SV"),
    # Gen 8
    "sword-shield":                  (8, "SwSh"),
    "brilliant-diamond-and-shining-pearl": (8, "BDSP"),
    "legends-arceus":                (8, "PLA"),
    # Gen 7
    "ultra-sun-ultra-moon":          (7, "USUM"),
    "sun-moon":                      (7, "SM"),
    "lets-go-pikachu-lets-go-eevee": (7, "LGPE"),
    # Gen 6
    "omega-ruby-alpha-sapphire":     (6, "ORAS"),
    "x-y":                           (6, "XY"),
}

TARGET_GENS = {9, 8, 7, 6}
ORDERED_VGS = [
    # From newest to oldest for base selection
    "scarlet-violet",
    "sword-shield",
    "brilliant-diamond-and-shining-pearl",
    "legends-arceus",
    "ultra-sun-ultra-moon",
    "sun-moon",
    "lets-go-pikachu-lets-go-eevee",
    "omega-ruby-alpha-sapphire",
    "x-y",
]

# --- Helpers ----------------------------------------------------------------

def load_mapping(csv_path: Path) -> OrderedDict:
    """
    CSV:
      species,othername
      Bulbasaur,bulbasaur
    Returns OrderedDict[species] = othername
    """
    out = OrderedDict()
    with csv_path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            sp = (row.get("species") or "").strip()
            on = (row.get("othername") or "").strip()
            if sp and on:
                out[sp] = on
    return out


def sort_alpha_moves(move_list):
    return sorted(move_list, key=lambda m: (m.get("Move", ""), m.get("Type", "")))


def dedupe_moves(move_list):
    seen = set()
    out = []
    for m in move_list:
        key = (m.get("Move", ""), m.get("Type", ""), m.get("Method", ""), m.get("Level", None), tuple(m.get("Tags") or []))
        if key in seen:
            continue
        seen.add(key)
        out.append(m)
    return out


# --- Async HTTP -------------------------------------------------------------

class PokeClient:
    def __init__(self, max_conns=12):
        self._session = None
        self._sem = asyncio.Semaphore(max_conns)
        self._move_type_cache = {}  # move-name(lower) -> type str

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=90)
        )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._session:
            await self._session.close()

    async def _get_json(self, url):
        async with self._sem:
            for attempt in range(3):
                try:
                    async with self._session.get(url) as resp:
                        if resp.status == 200:
                            return await resp.json()
                        # Gentle backoff on rate limits or server hiccups
                        if resp.status in (429, 500, 502, 503, 504):
                            await asyncio.sleep(0.5 * (attempt + 1))
                        else:
                            txt = await resp.text()
                            raise RuntimeError(f"GET {url} -> {resp.status}: {txt[:200]}")
                except aiohttp.ClientError as e:
                    await asyncio.sleep(0.5 * (attempt + 1))
            raise RuntimeError(f"GET {url} failed after retries")

    async def get_pokemon(self, othername: str) -> dict:
        url = f"{POKEAPI_BASE}/pokemon/{othername.lower().strip()}"
        return await self._get_json(url)

    async def get_move_type(self, move_name: str) -> str:
        key = move_name.lower()
        if key in self._move_type_cache:
            return self._move_type_cache[key]
        url = f"{POKEAPI_BASE}/move/{key}"
        data = await self._get_json(url)
        mv_type = (data.get("type") or {}).get("name") or "normal"
        mv_type = mv_type.capitalize()
        self._move_type_cache[key] = mv_type
        return mv_type


# --- Extraction logic -------------------------------------------------------

def pick_base_version_group(poke_moves) -> str | None:
    """
    Among ORDERED_VGS (newest→oldest), return the first VG that has any level-up entries.
    """
    for vg in ORDERED_VGS:
        for mv in poke_moves:
            for vgd in mv.get("version_group_details", []):
                if (vgd.get("version_group", {}).get("name") == vg and
                    (vgd.get("move_learn_method", {}).get("name") == "level-up")):
                    return vg
    return None


def vg_is_in_target(vg_name: str) -> bool:
    ginfo = VG_MAP.get(vg_name)
    return bool(ginfo and ginfo[0] in TARGET_GENS)


async def build_lists_for_species(client: PokeClient, othername: str):
    """
    Returns dict with:
      {
        "level_up": [ {Level, Move, Type, (Tags)}... ],
        "machine":  [ {Move, Type, Method="Machine"}... ]
      }
    """
    data = await client.get_pokemon(othername)
    poke_moves = data.get("moves", [])

    # --- MACHINE moves (gens 9..6), for both TM/HM and Tutor lists -----------
    machine_names = set()
    machine_entries = []
    for mv in poke_moves:
        mv_name = (mv.get("move", {}) or {}).get("name", "")
        if not mv_name:
            continue
        mv_name_disp = mv_name.replace("-", " ").title()  # Human readable

        # Any version-group with learn_method == "machine" in our gens?
        add = False
        for vgd in mv.get("version_group_details", []):
            vg_name = (vgd.get("version_group", {}) or {}).get("name", "")
            learn = (vgd.get("move_learn_method", {}) or {}).get("name", "")
            if learn == "machine" and vg_is_in_target(vg_name):
                add = True
                break
        if add and mv_name_disp not in machine_names:
            mv_type = await client.get_move_type(mv_name)
            machine_entries.append({
                "Move": mv_name_disp,
                "Type": mv_type.capitalize(),
                "Tags": [],
                "Method": "Machine",
            })
            machine_names.add(mv_name_disp)

    machine_entries = sort_alpha_moves(machine_entries)

    # --- LEVEL-UP moves ------------------------------------------------------
    base_vg = pick_base_version_group(poke_moves)
    level_up_entries = []

    if base_vg:
        # Collect base (no tags) from base_vg (newest available)
        for mv in poke_moves:
            mv_name = (mv.get("move", {}) or {}).get("name", "")
            if not mv_name:
                continue
            mv_name_disp = mv_name.replace("-", " ").title()
            for vgd in mv.get("version_group_details", []):
                vg_name = (vgd.get("version_group", {}) or {}).get("name", "")
                if vg_name != base_vg:
                    continue
                learn = (vgd.get("move_learn_method", {}) or {}).get("name", "")
                if learn != "level-up":
                    continue
                level = vgd.get("level_learned_at") or 0
                mv_type = await client.get_move_type(mv_name)
                level_up_entries.append({
                    "Level": level,
                    "Move": mv_name_disp,
                    "Type": mv_type.capitalize(),
                })

        # Add older gens (down to gen6) as Legacy
        # Find all VGs older than base_vg (in our ordered list) and within target gens.
        base_index = ORDERED_VGS.index(base_vg)
        older_vgs = [vg for vg in ORDERED_VGS[base_index+1:] if vg_is_in_target(vg)]

        for vg in older_vgs:
            gen, label = VG_MAP[vg]
            # For each level-up in that VG, append as Legacy (even si doublon du move)
            for mv in poke_moves:
                mv_name = (mv.get("move", {}) or {}).get("name", "")
                if not mv_name:
                    continue
                mv_name_disp = mv_name.replace("-", " ").title()
                for vgd in mv.get("version_group_details", []):
                    vg_name = (vgd.get("version_group", {}) or {}).get("name", "")
                    learn = (vgd.get("move_learn_method", {}) or {}).get("name", "")
                    if vg_name == vg and learn == "level-up":
                        level = vgd.get("level_learned_at") or 0
                        mv_type = await client.get_move_type(mv_name)
                        level_up_entries.append({
                            "Level": level,
                            "Move": mv_name_disp,
                            "Type": mv_type.capitalize(),
                            "Tags": ["Legacy", label],
                        })

    # Optionally: keep stable order by (Level, Move)
    level_up_entries.sort(key=lambda e: (e.get("Level", 0), e.get("Move", "")))

    return {
        "level_up": level_up_entries,
        "machine": machine_entries,
    }


# --- Main -------------------------------------------------------------------

async def main_async(pokedex_path: Path, mapping_path: Path, out_path: Path, max_conns: int):
    # Load data
    with pokedex_path.open(encoding="utf-8") as f:
        pokedex = json.load(f)

    mapping = load_mapping(mapping_path)

    # Build index: Species -> object reference
    # Your pokedex looks like a list of species objects
    species_index = {entry.get("Species"): entry for entry in pokedex if isinstance(entry, dict)}

    async with PokeClient(max_conns=max_conns) as client:
        tasks = []
        order = []
        for species, other in mapping.items():
            if species not in species_index:
                # print(f"[WARN] Species '{species}' from mapping not found in pokedex; skipping.", file=sys.stderr)
                continue
            tasks.append(build_lists_for_species(client, other))
            order.append(species)

        results = await asyncio.gather(*tasks)

    # Apply results
    for species, res in zip(order, results):
        node = species_index[species]
        moves = node.setdefault("Moves", {})
        # Remove the three lists
        moves["Level Up Move List"] = res["level_up"]
        moves["TM/HM Move List"] = dedupe_moves(res["machine"])
        # As requested: Tutor list built from the same machine set
        moves["Tutor Move List"] = dedupe_moves(res["machine"])

    # Write output
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(pokedex, f, ensure_ascii=False, indent=2)
    print(f"Done. Wrote: {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pokedex", required=True, type=Path)
    ap.add_argument("--mapping", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--max-conns", type=int, default=12)
    args = ap.parse_args()

    asyncio.run(main_async(args.pokedex, args.mapping, args.out, args.max_conns))


if __name__ == "__main__":
    main()
