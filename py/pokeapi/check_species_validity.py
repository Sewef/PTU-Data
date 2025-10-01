#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
check_species_validity_async.py
-------------------------------
Valide rapidement une liste d'espèces depuis un CSV contre PokeAPI (/pokemon/{name}).
- Asynchrone avec aiohttp, concurrence réglable
- Retries + backoff, support 429 Retry-After
- Lecture par nom de colonne (--header) ou index (--column)
- Normalisation simple en "slug" (minuscules, espaces -> -, apostrophes retirées) activable/désactivable
- Sortie d'une liste d'espèces invalides (--out) et/ou rapport détaillé (--report)
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
    print("Ce script requiert le paquet 'aiohttp' (pip install aiohttp).", file=sys.stderr)
    sys.exit(1)

POKEAPI = "https://pokeapi.co/api/v2/pokemon"


@dataclass
class Config:
    timeout: int = 15
    retries: int = 3
    backoff: float = 0.8
    concurrency: int = 32
    user_agent: str = "check-species-validity/1.0 (+https://pokeapi.co)"


class Limiter:
    def __init__(self, n: int):
        self.sem = asyncio.Semaphore(max(1, n))
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


async def fetch_status(session: aiohttp.ClientSession, url: str, cfg: Config) -> Tuple[int, Optional[str]]:
    last_err = None
    for attempt in range(cfg.retries + 1):
        try:
            async with session.get(url, timeout=cfg.timeout) as resp:
                if resp.status == 200:
                    return 200, None
                if resp.status in (429, 500, 502, 503, 504):
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after:
                        try:
                            delay = float(retry_after)
                        except ValueError:
                            delay = cfg.backoff * (2 ** attempt)
                    else:
                        delay = cfg.backoff * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                text = await resp.text()
                return resp.status, text[:200]
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_err = str(e)
            await asyncio.sleep(cfg.backoff * (2 ** attempt))
    return 0, last_err or "network error"


async def validate_one(session: aiohttp.ClientSession, name: str, normalized: bool, cfg: Config, limiter: Limiter) -> Tuple[str, str, int, bool]:
    q = simple_slug(name) if normalized else name.strip()
    url = f"{POKEAPI}/{q}/"
    async with limiter:
        status, _ = await fetch_status(session, url, cfg)
    ok = (status == 200)
    return name, q, status, ok


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


async def main_async(args) -> None:
    cfg = Config(timeout=args.timeout, retries=args.retries, backoff=args.backoff, concurrency=args.concurrency)
    species = read_species_from_csv(args.csv_file, args.header, args.column)

    if not species:
        print("[warn] Aucune espèce trouvée dans le CSV.", file=sys.stderr)
        return

    async with aiohttp.ClientSession(headers={"User-Agent": cfg.user_agent}) as session:
        limiter = Limiter(cfg.concurrency)
        tasks = [asyncio.create_task(validate_one(session, sp, not args.no_normalize, cfg, limiter)) for sp in species]
        results = await asyncio.gather(*tasks)

    invalid = [orig for (orig, norm, status, ok) in results if not ok]

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            for s in invalid:
                f.write(s + "\n")
        print(f"[ok] {len(invalid)} espèces invalides écrites dans {args.out}", file=sys.stderr)
    else:
        print("Espèces invalides :")
        for s in invalid:
            print("-", s)

    if args.report:
        with open(args.report, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["original", "normalized", "status", "ok"])
            for orig, norm, status, ok in results:
                w.writerow([orig, norm, status, "true" if ok else "false"])
        print(f"[ok] Rapport écrit : {args.report}", file=sys.stderr)


def parse_args():
    p = argparse.ArgumentParser(description="Valide des noms d'espèces (CSV) contre PokeAPI en asynchrone.")
    p.add_argument("csv_file", help="Chemin du fichier CSV d'espèces (une espèce par ligne, ou préciser --header/--column).")
    p.add_argument("--header", help="Nom de la colonne à lire (sinon --column).", default=None)
    p.add_argument("--column", type=int, help="Index de la colonne à lire (défaut 0 si --header non fourni).", default=None)
    p.add_argument("--out", help="Fichier de sortie listant les espèces invalides (sinon stdout).")
    p.add_argument("--report", help="Fichier CSV pour un rapport détaillé (original, normalized, status, ok).")
    p.add_argument("--no-normalize", action="store_true", help="Ne pas normaliser les noms (par défaut on slugifie).")
    p.add_argument("--concurrency", type=int, default=32, help="Nombre de requêtes simultanées (défaut 32).")
    p.add_argument("--timeout", type=int, default=15, help="Timeout HTTP (s).")
    p.add_argument("--retries", type=int, default=3, help="Nombre de retries sur 429/5xx/erreurs réseau.")
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
