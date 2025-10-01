#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_species_mapping_csv.py
-------------------------------
Lit un CSV d'entrée avec une colonne "species" (ou une colonne choisie) et produit un CSV :
    species;othername

- "species" : la valeur telle que présente dans TON CSV d'origine (sans modification)
- "othername" : le nom canonique selon PokeAPI (/pokemon-species/{name}) si trouvé ; sinon vide
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
import unicodedata
from dataclasses import dataclass
from typing import List, Optional, Tuple

try:
    import aiohttp
except ImportError:
    print("Ce script requiert 'aiohttp' (pip install aiohttp).", file=sys.stderr)
    sys.exit(1)

BASE = "https://pokeapi.co/api/v2"
UA = "gen-species-mapping/1.0 (+https://pokeapi.co)"


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


def simple_slug(s: str) -> str:
    s = s.strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    for ch in [" ", "_"]:
        s = s.replace(ch, "-")
    for ch in ["'", "'", '"', "\"", "\"", "´", "`"]:
        s = s.replace(ch, "")
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789-."
    s = "".join(ch for ch in s if ch in allowed)
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-")


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
                vals.append(val)
    return vals


async def fetch_species_name(session: aiohttp.ClientSession, q: str, cfg: Cfg) -> Tuple[int, Optional[str]]:
    url = f"{BASE}/pokemon-species/{q}/"
    last = None
    for attempt in range(cfg.retries + 1):
        try:
            async with session.get(url, timeout=cfg.timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return 200, data.get("name")
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
                return resp.status, None
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last = e
            await asyncio.sleep(cfg.backoff * (2 ** attempt))
    return 0, None


async def one_row(session: aiohttp.ClientSession, original: str, normalized: bool, cfg: Cfg, limiter: Limiter) -> Tuple[str, str]:
    q = simple_slug(original) if normalized else original.strip()
    async with limiter:
        status, canon = await fetch_species_name(session, q, cfg)
    return original, (canon or "")


async def main_async(args):
    cfg = Cfg(timeout=args.timeout, retries=args.retries, backoff=args.backoff, concurrency=args.concurrency)
    rows = read_species_from_csv(args.csv_file, args.header, args.column)
    if not rows:
        print("[warn] Aucune espèce trouvée dans le CSV.", file=sys.stderr)
        return

    async with aiohttp.ClientSession(headers={"User-Agent": UA}) as session:
        limiter = Limiter(cfg.concurrency)
        tasks = [asyncio.create_task(one_row(session, r, not args.no_normalize, cfg, limiter)) for r in rows]
        results = await asyncio.gather(*tasks)

    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(["species", "othername"])
        for species, other in results:
            w.writerow([species, other])

    print(f"[ok] Écrit : {args.out} ({len(results)} lignes)", file=sys.stderr)


def parse_args():
    p = argparse.ArgumentParser(description="Génère un CSV 'species;othername' en comparant tes espèces à PokeAPI (/pokemon-species/).")
    p.add_argument("csv_file", help="CSV source contenant la colonne des species.")
    p.add_argument("--header", help="Nom de la colonne species (sinon --column).")
    p.add_argument("--column", type=int, help="Index de la colonne species (défaut 0 si --header absent).")
    p.add_argument("--no-normalize", action="store_true", help="Ne pas normaliser les noms avant requête (par défaut on slugifie).")
    p.add_argument("--out", required=True, help="Fichier CSV de sortie (sera au format 'species;othername').")
    p.add_argument("--concurrency", type=int, default=48, help="Nombre de requêtes simultanées (défaut 48).")
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
