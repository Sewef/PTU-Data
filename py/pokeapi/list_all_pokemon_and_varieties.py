#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
list_all_pokemon_and_varieties.py
---------------------------------
- Récupère **tous** les noms reconnus par PokeAPI dans `/pokemon/` (inclut formes régionales, méga, gmax, etc.).
- (Optionnel) Lit un CSV d'espèces (colonne 1 par défaut, ou `--header/--column`) et produit :
    * un mapping species -> varieties (noms `/pokemon/` reliés à cette species)
    * la liste des species introuvables
- Sauvegarde la liste complète de `/pokemon/` et, si demandé, le mapping et les rapports.

Dépendances : aiohttp

Exemples :
    pip install aiohttp

    # Tout lister et écrire dans un fichier
    python list_all_pokemon_and_varieties.py --out-all all_pokemon.txt

    # Comparer à mon CSV d'espèces (en-tête 'species') et produire mapping + invalides
    python list_all_pokemon_and_varieties.py species.csv --header species \
        --map-out species_varieties.json --unfound-out species_not_found.txt --out-all all_pokemon.txt
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    import aiohttp
except ImportError:
    print("Ce script requiert 'aiohttp' (pip install aiohttp).", file=sys.stderr)
    sys.exit(1)

BASE = "https://pokeapi.co/api/v2"
UA = "list-all-pokemon/1.0 (+https://pokeapi.co)"


@dataclass
class Cfg:
    timeout: int = 20
    retries: int = 3
    backoff: float = 0.8
    concurrency: int = 48


class Limiter:
    def __init__(self, n: int):
        import asyncio as _asyncio
        self.sem = _asyncio.Semaphore(max(1, n))
    async def __aenter__(self):
        await self.sem.acquire()
        return self
    async def __aexit__(self, exc_type, exc, tb):
        self.sem.release()


async def fetch_json(session: aiohttp.ClientSession, url: str, cfg: Cfg):
    last = None
    for attempt in range(cfg.retries + 1):
        try:
            async with session.get(url, timeout=cfg.timeout) as resp:
                if resp.status == 200:
                    return await resp.json()
                if resp.status in (429, 500, 502, 503, 504):
                    ra = resp.headers.get("Retry-After")
                    if ra:
                        try:
                            delay = float(ra)
                        except ValueError:
                            delay = cfg.backoff * (2 ** attempt)
                    else:
                        delay = cfg.backoff * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                text = await resp.text()
                raise RuntimeError(f"GET {url} -> {resp.status}: {text[:180]}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last = e
            await asyncio.sleep(cfg.backoff * (2 ** attempt))
    raise RuntimeError(f"Échec après retries pour {url}: {last}")


async def list_all_pokemon(session: aiohttp.ClientSession, cfg: Cfg) -> List[str]:
    """Paginer /pokemon pour obtenir tous les noms (/pokemon/)"""
    names: List[str] = []
    url = f"{BASE}/pokemon?limit=2000&offset=0"
    while url:
        data = await fetch_json(session, url, cfg)
        for it in data.get("results", []):
            name = it.get("name")
            if name:
                names.append(name)
        url = data.get("next")
    return names


def read_species_from_csv(path: str, header: Optional[str], column: Optional[int]) -> List[str]:
    vals: List[str] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        if header is not None:
            try:
                headers = next(reader)
            except StopIteration:
                return []
            try:
                idx = headers.index(header)
            except ValueError:
                raise SystemExit(f"[err] Colonne '{header}' introuvable dans {path}. En-têtes: {headers}")
        else:
            idx = 0 if column is None else int(column)
        for row in reader:
            if not row or len(row) <= idx:
                continue
            val = row[idx].strip()
            if val:
                vals.append(val.lower().replace(" ", "-"))
    return vals


async def fetch_species_varieties(session: aiohttp.ClientSession, species: str, cfg: Cfg, limiter: Limiter) -> Tuple[str, Optional[List[str]]]:
    """Retourne (species, [variety_names]) ou (species, None) si introuvable."""
    url = f"{BASE}/pokemon-species/{species}/"
    async with limiter:
        try:
            data = await fetch_json(session, url, cfg)
        except Exception:
            return species, None
    vs = []
    for v in data.get("varieties", []) or []:
        p = v.get("pokemon") or {}
        n = p.get("name")
        if n:
            vs.append(n)
    return species, vs


async def build_species_varieties(session: aiohttp.ClientSession, csv_species: List[str], cfg: Cfg) -> Tuple[Dict[str, List[str]], List[str]]:
    """Pour une liste d'espèces (slugifiées), retourne mapping species->varieties et la liste des species introuvables."""
    limiter = Limiter(cfg.concurrency)
    tasks = [asyncio.create_task(fetch_species_varieties(session, sp, cfg, limiter)) for sp in csv_species]
    results = await asyncio.gather(*tasks)
    mapping: Dict[str, List[str]] = {}
    not_found: List[str] = []
    for sp, varieties in results:
        if varieties is None:
            not_found.append(sp)
        else:
            mapping[sp] = varieties
    return mapping, not_found


async def main_async(args):
    cfg = Cfg(timeout=args.timeout, retries=args.retries, backoff=args.backoff, concurrency=args.concurrency)
    async with aiohttp.ClientSession(headers={"User-Agent": UA}) as session:

        # 1) Liste complète de /pokemon (formes)
        all_pokemon: Optional[List[str]] = None
        if args.out_all:
            all_pokemon = await list_all_pokemon(session, cfg)
            with open(args.out_all, "w", encoding="utf-8") as f:
                for name in all_pokemon:
                    f.write(name + "\n")
            print(f"[ok] {len(all_pokemon)} entrées /pokemon/ écrites dans {args.out_all}", file=sys.stderr)

        # 2) Optionnel : comparer aux species du CSV -> mapping varieties & not_found
        if args.csv_file:
            species_list = read_species_from_csv(args.csv_file, args.header, args.column)
            mapping, not_found = await build_species_varieties(session, species_list, cfg)

            if args.map_out:
                with open(args.map_out, "w", encoding="utf-8") as f:
                    json.dump(mapping, f, ensure_ascii=False, indent=2)
                print(f"[ok] Mapping species->varieties écrit : {args.map_out}", file=sys.stderr)

            if args.unfound_out:
                with open(args.unfound_out, "w", encoding="utf-8") as f:
                    for s in not_found:
                        f.write(s + "\n")
                print(f"[ok] {len(not_found)} species introuvables écrites : {args.unfound_out}", file=sys.stderr)

            # Si on a aussi la liste all_pokemon, on peut en plus écrire les variétés *non couvertes* par le CSV
            if args.extra_forms_out and (all_pokemon is not None):
                covered = set()
                for vs in mapping.values():
                    covered.update(vs)
                extras = [n for n in all_pokemon if n not in covered]
                with open(args.extra_forms_out, "w", encoding="utf-8") as f:
                    for n in extras:
                        f.write(n + "\n")
                print(f"[ok] {len(extras)} formes /pokemon/ non couvertes par le CSV -> {args.extra_forms_out}", file=sys.stderr)


def parse_args():
    p = argparse.ArgumentParser(description="Lister tous les /pokemon (formes) et, optionnellement, mapper des species CSV vers leurs varieties.")
    # Partie comparaison CSV
    p.add_argument("csv_file", nargs="?", help="CSV d'espèces (optionnel).")
    p.add_argument("--header", help="Nom de la colonne espèces (si CSV donné).")
    p.add_argument("--column", type=int, help="Index de la colonne espèces (défaut 0 si --header absent).")

    # Sorties
    p.add_argument("--out-all", help="Fichier pour écrire la liste complète des noms /pokemon/.")
    p.add_argument("--map-out", help="JSON species->varieties pour le CSV fourni.")
    p.add_argument("--unfound-out", help="Fichier texte des species du CSV introuvables.")
    p.add_argument("--extra-forms-out", help="Fichier des /pokemon/ non couverts par le CSV (nécessite --out-all + CSV).")

    # Réseau
    p.add_argument("--concurrency", type=int, default=48, help="Concurrence (défaut 48).")
    p.add_argument("--timeout", type=int, default=20, help="Timeout HTTP (s).")
    p.add_argument("--retries", type=int, default=3, help="Retries sur 429/5xx.")
    p.add_argument("--backoff", type=float, default=0.8, help="Backoff initial (exponentiel).")

    return p.parse_args()


def main():
    args = parse_args()
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\n[info] Interrompu par l'utilisateur.", file=sys.stderr)


if __name__ == "__main__":
    main()
