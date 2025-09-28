#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
sv_moves_summary_async.py
-------------------------
Résumé ultra-rapide des moves appris dans 'scarlet-violet' pour un grand nombre d'espèces.
- Récupère /pokemon/{species} en parallèle
- Filtre moves par version_group == 'scarlet-violet'
- Résout le type de chaque move via /move/{id} avec cache global (pour éviter les doublons inter-espèces)
- Sort tout dans un SEUL document JSON (ou JSONL) : species, version_group, moves[{name, method, level?, type?}]

Usage minimal :
    pip install aiohttp
    python sv_moves_summary_async.py --species-file species.txt --out sv_all.json

Autres exemples :
    # Depuis une liste d'espèces (une par ligne)
    python sv_moves_summary_async.py --species-file species.txt --out sv_all.json --concurrency 48

    # Depuis des JSON locaux au format PokeAPI (/pokemon/...)
    python sv_moves_summary_async.py --from-dir ./pokemon_json --out sv_all.json

    # Sans récupérer les types (pas d'appels /move/)
    python sv_moves_summary_async.py --species pikachu bulbasaur --no-types

    # En JSON Lines (une ligne par espèce)
    python sv_moves_summary_async.py --species-file species.txt --jsonl --out sv_all.jsonl

    # Avec un cache disque des types de moves (optimise les run répétés)
    python sv_moves_summary_async.py --species-file species.txt --move-cache move_types_cache.json --out sv_all.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
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


@dataclass
class FetcherConfig:
    base_url: str = POKEAPI
    timeout: int = 20
    concurrency: int = 32
    retries: int = 4
    retry_backoff: float = 0.8  # secondes, exponentiel
    user_agent: str = "sv-moves-summary/1.0 (+https://pokeapi.co)"


class RateLimiter:
    """Sémaphore de concurrence + délai minimal entre requêtes (si nécessaire)."""
    def __init__(self, concurrency: int):
        self.sem = asyncio.Semaphore(concurrency)

    async def __aenter__(self):
        await self.sem.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.sem.release()


async def fetch_json(session: aiohttp.ClientSession, url: str, cfg: FetcherConfig) -> Any:
    """GET JSON avec retries + backoff basique (gère 429/5xx)."""
    last_exc = None
    for attempt in range(cfg.retries + 1):
        try:
            async with session.get(url, timeout=cfg.timeout) as resp:
                if resp.status == 200:
                    return await resp.json()
                # En cas de rate-limit, on respecte le Retry-After si présent
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
                # autre code -> erreur directe
                text = await resp.text()
                raise aiohttp.ClientResponseError(
                    status=resp.status,
                    history=resp.history,
                    request_info=resp.request_info,
                    message=f"GET {url} -> {resp.status}: {text[:200]}"
                )
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_exc = e
            delay = cfg.retry_backoff * (2 ** attempt)
            await asyncio.sleep(delay)
    # si on sort de la boucle : échec
    raise RuntimeError(f"Échec après retries pour URL: {url} (dernier: {last_exc})")


def normalize_species_name(s: str) -> str:
    return s.strip().lower().replace(" ", "-")


def summarize_sv_moves_from_pokemon_json(pokemon_json: Dict[str, Any], include_types: bool) -> Tuple[Dict[str, Any], Dict[str, Optional[str]]]:
    """
    Prépare le résumé pour UNE espèce + liste des move_urls à typer.
    Retourne (summary_without_types, move_urls_map) où move_urls_map = {url: None} à résoudre.
    """
    species_name = pokemon_json.get("name") or (pokemon_json.get("species") or {}).get("name")
    moves = pokemon_json.get("moves", []) or []

    bucket: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for m in moves:
        move_name = m.get("move", {}).get("name")
        move_url = m.get("move", {}).get("url")
        if not move_name or not move_url:
            continue
        for det in m.get("version_group_details", []):
            vg = det.get("version_group", {}) or {}
            if vg.get("name") != SV_GROUP_NAME:
                continue
            method = (det.get("move_learn_method") or {}).get("name")
            level = det.get("level_learned_at") or 0
            key = (move_name, method or "")
            if key not in bucket:
                bucket[key] = {
                    "name": move_name,
                    "method": method,
                    "level": int(level) if (isinstance(level, int) and level > 0) else None,
                    "move_url": move_url,
                }
            else:
                prev = bucket[key].get("level")
                if (prev is None and level and level > 0) or (prev is not None and level and level > 0 and level < prev):
                    bucket[key]["level"] = int(level)

    items = list(bucket.values())

    def sort_key(item: Dict[str, Any]):
        method = item.get("method") or ""
        level = item.get("level")
        if method == "level-up":
            return (0, level if level is not None else 9999, item["name"])
        return (1, 0, item["name"])

    items.sort(key=sort_key)

    # Prépare la structure résultat (type à ajouter plus tard)
    result = {
        "species": species_name,
        "version_group": SV_GROUP_NAME,
        "moves": [
            {k: v for k, v in item.items() if k in ("name", "method", "level", "move_url") and v is not None}
            for item in items
        ],
    }

    # Collecte des URL à résoudre
    need_types = {}
    if include_types:
        for item in items:
            url = item.get("move_url")
            if url:
                need_types[url] = None

    return result, need_types


async def resolve_move_types(session: aiohttp.ClientSession, move_urls: List[str], cfg: FetcherConfig,
                             cache: Dict[str, Optional[str]], limiter: RateLimiter) -> None:
    """Remplit le cache {move_url -> type_name} en parallèle, en évitant les re-requests."""
    async def worker(url: str):
        if url in cache:
            return
        async with limiter:
            try:
                data = await fetch_json(session, url, cfg)
                t = (data.get("type") or {}).get("name")
            except Exception:
                t = None
            cache[url] = t

    tasks = [asyncio.create_task(worker(url)) for url in move_urls if url not in cache]
    if tasks:
        await asyncio.gather(*tasks)


async def fetch_pokemon_json(session: aiohttp.ClientSession, species: str, cfg: FetcherConfig, limiter: RateLimiter) -> Dict[str, Any]:
    url = f"{cfg.base_url}/pokemon/{normalize_species_name(species)}/"
    async with limiter:
        return await fetch_json(session, url, cfg)


def load_move_cache(path: Optional[str]) -> Dict[str, Optional[str]]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return {str(k): (v if isinstance(v, (str, type(None))) else None) for k, v in data.items()}
    except Exception:
        pass
    return {}


def save_move_cache(path: Optional[str], cache: Dict[str, Optional[str]]) -> None:
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[warn] Impossible d'écrire le move-cache: {e}", file=sys.stderr)


async def process_species_list(species_list: List[str], include_types: bool, cfg: FetcherConfig,
                               move_cache: Dict[str, Optional[str]]) -> List[Dict[str, Any]]:
    """Pipeline principal pour espèces en réseau."""
    results: List[Dict[str, Any]] = []
    async with aiohttp.ClientSession(headers={"User-Agent": cfg.user_agent}) as session:
        limiter = RateLimiter(cfg.concurrency)

        # 1) Fetch tous les /pokemon/{species}
        pokemons = await asyncio.gather(*[
            fetch_pokemon_json(session, sp, cfg, limiter) for sp in species_list
        ], return_exceptions=True)

        # 2) Parse, collect move URLs à typer
        needed_urls: Dict[str, Optional[str]] = {}
        summaries: List[Dict[str, Any]] = []
        for sp, data in zip(species_list, pokemons):
            if isinstance(data, Exception):
                print(f"[warn] Échec /pokemon/{sp}: {data}", file=sys.stderr)
                continue
            summary, need_types = summarize_sv_moves_from_pokemon_json(data, include_types)
            summaries.append(summary)
            for url in need_types.keys():
                needed_urls[url] = None

        # 3) Resolve move types (via cache + réseau)
        if include_types and summaries:
            to_resolve = [u for u in needed_urls.keys() if u not in move_cache]
            if to_resolve:
                await resolve_move_types(session, to_resolve, cfg, move_cache, limiter)

            # 4) Inject types
            for s in summaries:
                for m in s["moves"]:
                    url = m.pop("move_url", None)
                    if include_types:
                        m["type"] = move_cache.get(url) if url else None

        results.extend(summaries)

    return results


def load_pokemon_jsons_from_dir(dir_path: str) -> List[Dict[str, Any]]:
    out = []
    for p in sorted(Path(dir_path).glob("*.json")):
        try:
            with p.open("r", encoding="utf-8") as f:
                out.append(json.load(f))
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
    p = argparse.ArgumentParser(description="Résumé des moves 'scarlet-violet' pour beaucoup d'espèces (asynchrone).")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--species", nargs="+", help="Liste d'espèces (noms ou ids).")
    src.add_argument("--species-file", help="Fichier texte (une espèce par ligne).")
    src.add_argument("--from-dir", help="Dossier contenant des JSON /pokemon/ au format PokeAPI.")

    p.add_argument("--no-types", action="store_true", help="Ne pas récupérer le type des moves.")
    p.add_argument("--move-cache", help="Fichier JSON cache des types de moves (lecture/écriture).")
    p.add_argument("--concurrency", type=int, default=32, help="Niveau de parallélisme (défaut: 32).")
    p.add_argument("--base-url", default=POKEAPI, help="Base URL PokeAPI (défaut: officiel).")
    p.add_argument("--timeout", type=int, default=20, help="Timeout HTTP en secondes (défaut: 20).")
    p.add_argument("--out", required=True, help="Chemin de sortie du JSON (ou JSONL si --jsonl).")
    p.add_argument("--jsonl", action="store_true", help="Émettre en JSON Lines (une ligne par espèce).")

    return p.parse_args()


def read_species_file(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]


def main() -> None:
    args = parse_args()

    include_types = not args.no_types
    cfg = FetcherConfig(
        base_url=args.base_url,
        timeout=args.timeout,
        concurrency=max(1, int(args.concurrency)),
    )

    move_cache = load_move_cache(args.move_cache)

    results: List[Dict[str, Any]] = []

    if args.from_dir:
        # Mode offline local : on lit les JSON /pokemon/ depuis un dossier
        pokes = load_pokemon_jsons_from_dir(args.from_dir)
        summaries: List[Dict[str, Any]] = []
        needed_urls: Dict[str, Optional[str]] = {}
        for pj in pokes:
            summary, need_types = summarize_sv_moves_from_pokemon_json(pj, include_types)
            summaries.append(summary)
            for url in need_types.keys():
                needed_urls[url] = None

        # Si on veut quand même typer et que les URL sont valides, on peut tenter réseau
        if include_types and summaries and needed_urls:
            # réseau pour typer (si accessible)
            try:
                results_async = asyncio.run(process_species_list(
                    [], include_types=True, cfg=cfg, move_cache=move_cache
                ))
            except Exception:
                # on ignore, on n'a pas de species à traiter ici, donc rien
                pass

            # Comme on n'a pas téléchargé ici, on tente de résoudre via réseau uniquement les types manquants
            async def resolve_only():
                async with aiohttp.ClientSession(headers={"User-Agent": cfg.user_agent}) as session:
                    limiter = RateLimiter(cfg.concurrency)
                    to_resolve = [u for u in needed_urls.keys() if u not in move_cache]
                    if to_resolve:
                        await resolve_move_types(session, to_resolve, cfg, move_cache, limiter)
            try:
                asyncio.run(resolve_only())
            except Exception as e:
                print(f"[warn] Impossible de résoudre les types via réseau en mode --from-dir : {e}", file=sys.stderr)

        # injecter types si on les a
        if include_types:
            for s in summaries:
                for m in s["moves"]:
                    url = m.pop("move_url", None)
                    m["type"] = move_cache.get(url) if url else None
        else:
            for s in summaries:
                for m in s["moves"]:
                    m.pop("move_url", None)

        results = summaries

    else:
        # Mode réseau complet : espèces en arguments ou via fichier
        if args.species:
            species_list = args.species
        else:
            species_list = read_species_file(args.species_file)

        # pipeline async
        results = asyncio.run(process_species_list(species_list, include_types, cfg, move_cache))

    # Sauvegardes
    save_move_cache(args.move_cache, move_cache)

    # Sortie
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
