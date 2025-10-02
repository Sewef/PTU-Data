#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import aiohttp
except ImportError:
    print("Ce script requiert le paquet 'aiohttp' (pip install aiohttp).", file=sys.stderr)
    sys.exit(1)

POKEAPI = "https://pokeapi.co/api/v2"
SV_GROUP_NAME = "scarlet-violet"
FALLBACK_VGS = [
    "sword-shield",
    "isle-of-armor",
    "crown-tundra",
    "brilliant-diamond-and-shining-pearl",
    "legends-arceus",
    "ultra-sun-ultra-moon",
    "sun-moon",
    "omega-ruby-alpha-sapphire",
    "x-y",
    # "black-2-white-2",
    # "black-white",
    # "heartgold-soulsilver",
    # "platinum",
    # "diamond-pearl",
    # "emerald",
    # "firered-leafgreen",
    # "ruby-sapphire",
    # "crystal",
    # "gold-silver",
    # "yellow",
    # "red-blue",
]  # ordre décroissant des générations


@dataclass
class FetcherConfig:
    base_url: str = POKEAPI
    timeout: int = 20
    concurrency: int = 32
    retries: int = 4
    retry_backoff: float = 0.8
    user_agent: str = "sv-moves-summary/1.5 (+https://pokeapi.co)"


class RateLimiter:
    def __init__(self, concurrency: int):
        self.sem = asyncio.Semaphore(concurrency)

    async def __aenter__(self):
        await self.sem.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.sem.release()


async def fetch_json(session: aiohttp.ClientSession, url: str, cfg: FetcherConfig) -> Any:
    last_exc = None
    for attempt in range(cfg.retries + 1):
        try:
            async with session.get(url, timeout=cfg.timeout) as resp:
                if resp.status == 200:
                    return await resp.json()
                if resp.status in (429, 500, 502, 503, 504):
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after is not None:
                        try:
                            delay = float(retry_after)
                        except ValueError:
                            delay = cfg.retry_backoff * (2 ** attempt)
                    else:
                        delay = cfg.retry_backoff * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                text = await resp.text()
                raise aiohttp.ClientResponseError(
                    status=resp.status,
                    history=resp.history,
                    request_info=resp.request_info,
                    message=f"GET {url} -> {resp.status}: {text[:200]}",
                )
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_exc = e
            delay = cfg.retry_backoff * (2 ** attempt)
            await asyncio.sleep(delay)
    raise RuntimeError(f"Échec après retries pour URL: {url} (dernier: {last_exc})")


def normalize_species_name(s: str) -> str:
    return s.strip().lower().replace(" ", "-")


def summarize_sv_moves_from_pokemon_json(
    pokemon_json: Dict[str, Any],
    include_types: bool,
    override_species_name: Optional[str] = None,
) -> Tuple[Dict[str, Any], Dict[str, Optional[str]]]:
    """
    Sans déduplication + multi-fallback de générations si SV est vide.
    Conserve l'ordre PokeAPI.
    """
    species_name = (
        override_species_name
        or pokemon_json.get("name")
        or (pokemon_json.get("species") or {}).get("name")
    )
    moves = pokemon_json.get("moves", []) or []

    def collect_for_vg(vg_name: str) -> Tuple[List[Dict[str, Any]], Dict[str, Optional[str]]]:
        items: List[Dict[str, Any]] = []
        need_types: Dict[str, Optional[str]] = {}
        for m in moves:
            move_name = (m.get("move") or {}).get("name")
            move_url = (m.get("move") or {}).get("url")
            if not move_name or not move_url:
                continue
            for det in (m.get("version_group_details") or []):
                vg = (det.get("version_group") or {})
                if vg.get("name") != vg_name:
                    continue
                method = (det.get("move_learn_method") or {}).get("name")
                level = det.get("level_learned_at") or 0
                row: Dict[str, Any] = {"name": move_name, "method": method, "move_url": move_url}
                if isinstance(level, int) and level > 0:
                    row["level"] = level
                items.append(row)
                if include_types:
                    need_types[move_url] = None
        return items, need_types

    # 1) Essayer la version cible (SV)
    items, need_types = collect_for_vg(SV_GROUP_NAME)
    used_vg = SV_GROUP_NAME

    # 2) Si vide, parcourir la liste de fallback (défaut ou override CLI)
    try:
        fb_list = fallback_list if isinstance(fallback_list, list) else FALLBACK_VGS
    except NameError:
        fb_list = FALLBACK_VGS

    if not items:
        for vg in fb_list:
            cand_items, cand_need = collect_for_vg(vg)
            if cand_items:
                items, need_types = cand_items, cand_need
                used_vg = vg
                break

    result = {
        "species": species_name,
        "version_group": used_vg,
        "moves": [{k: v for k, v in item.items() if k in ("name", "method", "level", "move_url")} for item in items],
    }
    return result, need_types


async def resolve_move_types(session: aiohttp.ClientSession, move_urls: List[str], cfg: FetcherConfig,
                             cache: Dict[str, Optional[str]], limiter: RateLimiter) -> None:
    async def worker(url: str):
        if url in cache:
            return
        async with limiter:
            try:
                data = await fetch_json(session, url, cfg)
                t = (data.get("type") or {}).get("name")
                name_en = None
                for nm in (data.get("names") or []):
                    lang = (nm.get("language") or {}).get("name")
                    if lang == "en":
                        name_en = nm.get("name")
                        break
            except Exception:
                t = None
                name_en = None
            cache[url] = {"type": t, "name_en": name_en}

    tasks = [asyncio.create_task(worker(url)) for url in move_urls if url not in cache]
    if tasks:
        await asyncio.gather(*tasks)


async def fetch_pokemon_json(session: aiohttp.ClientSession, fetch_key: str, cfg: FetcherConfig, limiter: RateLimiter) -> Dict[str, Any]:
    url = f"{cfg.base_url}/pokemon/{normalize_species_name(fetch_key)}/"
    async with limiter:
        return await fetch_json(session, url, cfg)


async def fetch_species_json(session: aiohttp.ClientSession, species_url: str, cfg: FetcherConfig, limiter: RateLimiter) -> Dict[str, Any]:
    async with limiter:
        return await fetch_json(session, species_url, cfg)


async def fetch_evolution_chain_json(session: aiohttp.ClientSession, evo_url: str, cfg: FetcherConfig, limiter: RateLimiter) -> Dict[str, Any]:
    async with limiter:
        return await fetch_json(session, evo_url, cfg)


def compute_stage_from_chain(chain: Dict[str, Any], target_species: str) -> int:
    target = target_species.strip().lower()

    def dfs(node: Dict[str, Any], depth: int) -> int:
        sp = (node.get("species") or {}).get("name", "").strip().lower()
        if sp == target:
            return depth
        for nxt in (node.get("evolves_to") or []):
            d = dfs(nxt, depth + 1)
            if d != -1:
                return d
        return -1

    return dfs(chain or {}, 0)


async def process_pairs(pairs: List[Tuple[str, str]], include_types: bool, cfg: FetcherConfig,
                        move_cache: Dict[str, Optional[str]]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    async with aiohttp.ClientSession(headers={"User-Agent": cfg.user_agent}) as session:
        limiter = RateLimiter(cfg.concurrency)

        pokemons = await asyncio.gather(*[
            fetch_pokemon_json(session, fetch_key, cfg, limiter) for fetch_key, _ in pairs
        ], return_exceptions=True)

        species_json_cache: Dict[str, Dict[str, Any]] = {}
        evo_json_cache: Dict[str, Dict[str, Any]] = {}

        async def get_stage_for_pokemon(poke_json: Dict[str, Any]) -> int:
            try:
                sp_url = (poke_json.get("species") or {}).get("url")
                if not sp_url:
                    return -1
                if sp_url not in species_json_cache:
                    species_json_cache[sp_url] = await fetch_species_json(session, sp_url, cfg, limiter)
                spj = species_json_cache[sp_url]
                evo = (spj.get("evolution_chain") or {}).get("url")
                if not evo:
                    return -1
                if evo not in evo_json_cache:
                    evo_json_cache[evo] = await fetch_evolution_chain_json(session, evo, cfg, limiter)
                evj = evo_json_cache[evo]
                chain = evj.get("chain") or {}
                target = (poke_json.get("species") or {}).get("name") or poke_json.get("name")
                if not target:
                    return -1
                return compute_stage_from_chain(chain, target)
            except Exception:
                return -1

        needed_urls: Dict[str, Optional[str]] = {}
        summaries: List[Dict[str, Any]] = []

        stage_tasks = []
        for data in pokemons:
            if isinstance(data, Exception):
                stage_tasks.append(asyncio.create_task(asyncio.sleep(0, result=-1)))
            else:
                stage_tasks.append(asyncio.create_task(get_stage_for_pokemon(data)))

        for (fetch_key, display_species), data, st_fut in zip(pairs, pokemons, stage_tasks):
            if isinstance(data, Exception):
                print(f"[warn] Échec /pokemon/{fetch_key}: {data}", file=sys.stderr)
                continue

            stage_val = await st_fut
            stats_map = {s["stat"]["name"]: s["base_stat"] for s in data.get("stats", []) if s.get("stat")}

            ms, need_types = summarize_sv_moves_from_pokemon_json(
                data, include_types, override_species_name=display_species
            )

            # Compute gender distribution using species_json_cache (or fetch if missing)
            gender_dist = {"male": 0.0, "female": 0.0, "genderless": 0.0}
            try:
                sp_url = (data.get("species") or {}).get("url")
                if sp_url:
                    if sp_url not in species_json_cache:
                        species_json_cache[sp_url] = await fetch_species_json(session, sp_url, cfg, limiter)
                    spj = species_json_cache.get(sp_url, {})
                    gr = spj.get("gender_rate", -1)
                    if gr == -1:
                        gender_dist = {"male": 0.0, "female": 0.0, "genderless": 1.0}
                    else:
                        female = float(gr) / 8.0
                        male = 1.0 - female
                        gender_dist = {"male": male, "female": female, "genderless": 0.0}
            except Exception:
                pass

            summary = {
                "Species": display_species,
                "species": ms.get("species"),
                "stage": stage_val,
                "stats": stats_map,
                "version_group": ms.get("version_group"),
                "moves": ms.get("moves"),
                "gender_distribution": gender_dist,
            }

            summaries.append(summary)
            for url in need_types.keys():
                needed_urls[url] = None

        if include_types and summaries:
            to_resolve = [u for u in needed_urls.keys() if u not in move_cache]
            if to_resolve:
                await resolve_move_types(session, to_resolve, cfg, move_cache, limiter)

            for s in summaries:
                for m in s["moves"]:
                    url = m.pop("move_url", None)
                    info = move_cache.get(url) if url else None
                    if isinstance(info, dict):
                        m["type"] = info.get("type")
                        if info.get("name_en") is not None:
                            m["name_en"] = info.get("name_en")
                    else:
                        m["type"] = info

        results.extend(summaries)

    return results


def load_pokemon_jsons_from_dir_with_names(dir_path: str) -> List[Tuple[Dict[str, Any], str]]:
    out = []
    for p in sorted(Path(dir_path).glob("*.json")):
        try:
            with p.open("r", encoding="utf-8") as f:
                pj = json.load(f)
                disp = pj.get("name") or (pj.get("species") or {}).get("name") or p.stem
                out.append((pj, disp))
        except Exception as e:
            print(f"[warn] Échec lecture {p}: {e}", file=sys.stderr)
    return out


def build_document(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "version_group": SV_GROUP_NAME,
        "generated_at": int(time.time()),
        "species_count": len(results),
        "results": results,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Résumé moves SV (async) + mapping CSV + stage + fallbacks multi-générations.")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--mapping-csv", help="CSV avec en-têtes 'species;othername' (séparateur ';').")
    src.add_argument("--species", nargs="+", help="Liste d'espèces (noms ou ids).")
    src.add_argument("--species-file", help="Fichier texte (une espèce par ligne).")
    src.add_argument("--from-dir", help="Dossier de JSON /pokemon/ au format PokeAPI.")

    p.add_argument("--no-types", action="store_true", help="Ne pas récupérer le type des moves.")
    p.add_argument("--move-cache", help="Fichier JSON cache des types de moves (lecture/écriture).")
    p.add_argument("--concurrency", type=int, default=32, help="Niveau de parallélisme (défaut: 32).")
    p.add_argument("--base-url", default=POKEAPI, help="Base URL PokeAPI (défaut: officiel).")
    p.add_argument("--timeout", type=int, default=20, help="Timeout HTTP en secondes (défaut: 20).")
    p.add_argument("--out", required=True, help="Chemin de sortie du JSON (ou JSONL si --jsonl).")
    p.add_argument("--jsonl", action="store_true", help="Émettre en JSON Lines (une ligne par espèce).")
    p.add_argument("--fallback-vgs", help="Liste de version_groups de fallback séparés par des virgules (par défaut: ordre décroissant des générations).")

    return p.parse_args()


def read_species_file(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]


def read_mapping_csv(path: str) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=';')
        field_map = {k.lower(): k for k in (reader.fieldnames or [])}
        if "species" not in field_map or "othername" not in field_map:
            raise ValueError("Le CSV doit contenir les en-têtes: species;othername")
        sp_key = field_map["species"]
        on_key = field_map["othername"]
        for row in reader:
            species = (row.get(sp_key) or "").strip()
            other = (row.get(on_key) or "").strip()
            if not species or not other:
                continue
            pairs.append((other, species))
    return pairs


def main() -> None:
    args = parse_args()

    include_types = not args.no_types
    cfg = FetcherConfig(
        base_url=args.base_url,
        timeout=args.timeout,
        concurrency=max(1, int(args.concurrency)),
    )

    # CLI override for fallback list
    global fallback_list
    fallback_list = None
    if args.fallback_vgs:
        fallback_list = [s.strip() for s in args.fallback_vgs.split(",") if s.strip()]

    move_cache: Dict[str, Optional[str]] = {}
    if args.move_cache:
        p = Path(args.move_cache)
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, dict):
                            move_cache[str(k)] = {"type": v.get("type"), "name_en": v.get("name_en")}
                        elif isinstance(v, (str, type(None))):
                            move_cache[str(k)] = {"type": v, "name_en": None}
                        else:
                            move_cache[str(k)] = {"type": None, "name_en": None}
            except Exception:
                move_cache = {}

    results: List[Dict[str, Any]] = []

    if args.mapping_csv:
        pairs = read_mapping_csv(args.mapping_csv)
        if not pairs:
            print("[warn] Le mapping CSV est vide ou invalide.", file=sys.stderr)
        results = asyncio.run(process_pairs(pairs, include_types, cfg, move_cache))

    elif args.from_dir:
        pokes = load_pokemon_jsons_from_dir_with_names(args.from_dir)
        summaries: List[Dict[str, Any]] = []
        needed_urls: Dict[str, Optional[str]] = {}

        async def enrich_and_collect():
            async with aiohttp.ClientSession(headers={"User-Agent": cfg.user_agent}) as session:
                limiter = RateLimiter(cfg.concurrency)
                species_json_cache: Dict[str, Dict[str, Any]] = {}
                evo_json_cache: Dict[str, Dict[str, Any]] = {}

                async def get_stage_for_pokemon(poke_json: Dict[str, Any]) -> int:
                    try:
                        sp_url = (poke_json.get("species") or {}).get("url")
                        if not sp_url:
                            return -1
                        if sp_url not in species_json_cache:
                            species_json_cache[sp_url] = await fetch_species_json(session, sp_url, cfg, limiter)
                        spj = species_json_cache[sp_url]
                        evo = (spj.get("evolution_chain") or {}).get("url")
                        if not evo:
                            return -1
                        if evo not in evo_json_cache:
                            evo_json_cache[evo] = await fetch_evolution_chain_json(session, evo, cfg, limiter)
                        evj = evo_json_cache[evo]
                        chain = evj.get("chain") or {}
                        target = (poke_json.get("species") or {}).get("name") or poke_json.get("name")
                        if not target:
                            return -1
                        return compute_stage_from_chain(chain, target)
                    except Exception:
                        return -1

                stage_tasks = [asyncio.create_task(get_stage_for_pokemon(pj)) for pj, _ in pokes]

                for (pj, disp), st_fut in zip(pokes, stage_tasks):
                    stage_val = await st_fut
                    stats_map = {s["stat"]["name"]: s["base_stat"] for s in pj.get("stats", []) if s.get("stat")}

                    ms, need_types = summarize_sv_moves_from_pokemon_json(pj, include_types, override_species_name=disp)

                    # Compute gender distribution for --from-dir path
                    gender_dist = {"male": 0.0, "female": 0.0, "genderless": 0.0}
                    try:
                        sp_url = (pj.get("species") or {}).get("url")
                        if sp_url:
                            if sp_url not in species_json_cache:
                                species_json_cache[sp_url] = await fetch_species_json(session, sp_url, cfg, limiter)
                            spj = species_json_cache.get(sp_url, {})
                            gr = spj.get("gender_rate", -1)
                            if gr == -1:
                                gender_dist = {"male": 0.0, "female": 0.0, "genderless": 1.0}
                            else:
                                female = float(gr) / 8.0
                                male = 1.0 - female
                                gender_dist = {"male": male, "female": female, "genderless": 0.0}
                    except Exception:
                        pass

                    summary = {
                        "Species": disp,
                        "species": ms.get("species"),
                        "stage": stage_val,
                        "stats": stats_map,
                        "version_group": ms.get("version_group"),
                        "moves": ms.get("moves"),
                        "gender_distribution": gender_dist,
                    }
                    summaries.append(summary)
                    for url in need_types.keys():
                        needed_urls[url] = None

                if include_types and summaries and needed_urls:
                    to_resolve = list(needed_urls.keys())
                    await resolve_move_types(session, to_resolve, cfg, move_cache, limiter)

                if include_types:
                    for s in summaries:
                        for m in s["moves"]:
                            url = m.pop("move_url", None)
                            info = move_cache.get(url) if url else None
                            if isinstance(info, dict):
                                m["type"] = info.get("type")
                                if info.get("name_en") is not None:
                                    m["name_en"] = info.get("name_en")
                            else:
                                m["type"] = info

        try:
            asyncio.run(enrich_and_collect())
        except Exception as e:
            print(f"[warn] Enrichissement stages/types en mode --from-dir: {e}", file=sys.stderr)

        results = summaries

    else:
        if args.species:
            species_list = args.species
        else:
            species_list = read_species_file(args.species_file)

        pairs = [(sp, sp) for sp in species_list]
        results = asyncio.run(process_pairs(pairs, include_types, cfg, move_cache))

    if args.move_cache:
        try:
            Path(args.move_cache).write_text(json.dumps(move_cache, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[warn] Impossible d'écrire le move-cache: {e}", file=sys.stderr)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.jsonl:
        with out_path.open("w", encoding="utf-8") as f:
            for s in results:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
    else:
        doc = build_document(results)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
    print(f"[ok] Écrit: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()