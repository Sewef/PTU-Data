import argparse
import asyncio
import aiohttp
import json
import csv
import sys
import os
from typing import Any, Dict, List, Optional, Tuple, Iterable, Set
from dataclasses import dataclass

POKEAPI_BASE = "https://pokeapi.co/api/v2"

# ------------------------------
# Outils asynchrones / limites
# ------------------------------

class RateLimiter:
    """Limiteur simple via Semaphore pour contrôler la concurrence."""
    def __init__(self, concurrency: int):
        self._sem = asyncio.Semaphore(max(1, concurrency))

    async def __aenter__(self):
        await self._sem.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._sem.release()


@dataclass
class FetcherConfig:
    timeout: int = 30
    retries: int = 2
    user_agent: str = "sv_moves_summary/1.0 (+https://pokeapi.co)"
    concurrency: int = 8


# ------------------------------
# HTTP helpers
# ------------------------------

async def http_get_json(session: aiohttp.ClientSession, url: str, cfg: FetcherConfig, limiter: RateLimiter) -> Any:
    last_exc: Optional[Exception] = None
    for attempt in range(cfg.retries + 1):
        try:
            async with limiter:
                async with session.get(url, timeout=cfg.timeout) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        raise RuntimeError(f"GET {url} -> {resp.status}: {text[:200]}")
                    return await resp.json()
        except Exception as e:
            last_exc = e
            await asyncio.sleep(0.5 * (attempt + 1))
    raise last_exc if last_exc else RuntimeError(f"GET {url} failed")


async def fetch_pokemon_json(session: aiohttp.ClientSession, species: str, cfg: FetcherConfig, limiter: RateLimiter) -> Any:
    # /pokemon/{id or name}
    url = f"{POKEAPI_BASE}/pokemon/{species.lower().strip()}/"
    return await http_get_json(session, url, cfg, limiter)


async def fetch_move_detail(session: aiohttp.ClientSession, move_url: str, cfg: FetcherConfig, limiter: RateLimiter) -> Any:
    # move_url est déjà absolue depuis PokeAPI
    return await http_get_json(session, move_url, cfg, limiter)


# ------------------------------
# Parsing helpers
# ------------------------------

def _find_vg_entries(move_block: Dict[str, Any], vg_name: str) -> List[Dict[str, Any]]:
    """Extrait les version_group_details pour une version group donnée."""
    vgd = move_block.get("version_group_details") or []
    return [d for d in vgd if (d.get("version_group") or {}).get("name") == vg_name]


def _best_entry_for_move(vg_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Heuristique simple: on privilégie un entry avec un level_learned_at le plus élevé,
    sinon le premier.
    """
    if not vg_entries:
        return {}
    return sorted(vg_entries, key=lambda d: d.get("level_learned_at", 0), reverse=True)[0]


def summarize_sv_moves_from_pokemon_json(poke: Dict[str, Any], vg_name: str = "scarlet-violet") -> Tuple[Dict[str, Any], Dict[str, None]]:
    """
    Extrait la liste des moves pertinents pour Scarlet/Violet
    Retourne:
      - summary: {"species": <name>, "moves": [ {name, url, method, level} ]}
      - needed_move_urls: {url: None} (pour ensuite récupérer noms anglais/types)
    """
    species_name = (poke.get("species") or {}).get("name") or poke.get("name") or "unknown"
    moves_block = poke.get("moves") or []

    result_moves: List[Dict[str, Any]] = []
    need_urls: Dict[str, None] = {}

    for m in moves_block:
        move_info = m.get("move") or {}
        move_name = move_info.get("name")
        move_url = move_info.get("url")
        if not move_name or not move_url:
            continue

        vg_entries = _find_vg_entries(m, vg_name)
        if not vg_entries:
            continue  # move non présent pour ce version group

        best = _best_entry_for_move(vg_entries)
        method = (best.get("move_learn_method") or {}).get("name")
        level = best.get("level_learned_at")

        result_moves.append({
            "name": move_name,
            "url": move_url,
            "method": method,
            "level": level,
        })
        need_urls[move_url] = None

    summary = {
        "species": species_name,
        "moves": result_moves
    }
    return summary, need_urls


# ------------------------------
# Move cache helpers (JSON)
# ------------------------------

def load_move_cache(path: Optional[str]) -> Dict[str, Dict[str, Any]]:
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def save_move_cache(path: Optional[str], cache: Dict[str, Dict[str, Any]]) -> None:
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[warn] Échec d'écriture cache moves: {e}", file=sys.stderr)


def english_name_from_move_detail(detail: Dict[str, Any]) -> Optional[str]:
    names = detail.get("names") or []
    for n in names:
        lang = (n.get("language") or {}).get("name")
        if lang == "en":
            return n.get("name")
    # fallback: english absent -> None
    return None


def type_from_move_detail(detail: Dict[str, Any]) -> Optional[str]:
    t = detail.get("type") or {}
    return t.get("name")


# ------------------------------
# Lecture des entrées
# ------------------------------

def read_species_file(path: str) -> List[str]:
    # supporte BOM
    with open(path, "r", encoding="utf-8-sig") as f:
        return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]


def read_mapping_csv(path: str) -> Tuple[List[str], List[str]]:
    """
    Lit un CSV séparé par ';' avec colonnes 'Species' et 'othername'.
    Supporte UTF-8 (avec ou sans BOM) et latin-1/cp1252.
    Retourne (api_names, display_names).
    """
    encodings_to_try = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
    last_err: Exception | None = None
    for enc in encodings_to_try:
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                reader = csv.DictReader(f, delimiter=";")
                api_names: List[str] = []
                display_names: List[str] = []
                for row in reader:
                    if not row:
                        continue
                    species_val = row.get("Species") or row.get("species") or row.get("SPECIES")
                    other_val = row.get("othername") or row.get("OtherName") or row.get("OTHERNAME")
                    if species_val and other_val:
                        display_names.append(species_val.strip())
                        api_names.append(other_val.strip())
                if api_names:
                    return api_names, display_names
        except UnicodeDecodeError as e:
            last_err = e
            continue
    raise RuntimeError(
        f"Impossible de décoder {path} avec encodages {encodings_to_try}: {last_err}"
    )


# ------------------------------
# Pipeline principal
# ------------------------------

async def process_species_list(
    species_list: List[str],
    include_types: bool,
    cfg: FetcherConfig,
    move_cache: Dict[str, Dict[str, Any]],
    aliases: Optional[List[Optional[str]]] = None,
    vg_name: str = "scarlet-violet",
) -> List[Dict[str, Any]]:
    """
    Pipeline complet:
      1. Fetch /pokemon/{species} pour chaque espèce
      2. Parse moves pour le version group 'scarlet-violet'
      3. Collecter toutes les URLs de moves à compléter (nom anglais, type)
      4. Fetch en parallèle les détails des moves (en utilisant cache quand possible)
      5. Remplir moves avec 'name_en' (et 'type' si include_types)
    """
    results: List[Dict[str, Any]] = []
    async with aiohttp.ClientSession(headers={"User-Agent": cfg.user_agent}) as session:
        limiter = RateLimiter(cfg.concurrency)

        # 1) Fetch pokémon JSON
        pokemons = await asyncio.gather(*[
            fetch_pokemon_json(session, sp, cfg, limiter) for sp in species_list
        ], return_exceptions=True)

        needed_urls: Dict[str, None] = {}
        summaries: List[Dict[str, Any]] = []

        # 2) Parse per pokemon
        for idx, (sp, data) in enumerate(zip(species_list, pokemons)):
            if isinstance(data, Exception):
                print(f"[warn] Échec /pokemon/{sp}: {data}", file=sys.stderr)
                continue
            summary, need_urls = summarize_sv_moves_from_pokemon_json(data, vg_name=vg_name)
            # alias d'affichage si fourni
            if aliases and idx < len(aliases) and aliases[idx]:
                summary["species"] = aliases[idx]
            summaries.append(summary)
            for url in need_urls.keys():
                needed_urls[url] = None

        # 3) Fetch move details (nom anglais + type), avec cache
        to_fetch: List[str] = [u for u in needed_urls.keys() if u not in move_cache]
        fetched: List[Any] = []
        if to_fetch:
            fetched = await asyncio.gather(*[
                fetch_move_detail(session, u, cfg, limiter) for u in to_fetch
            ], return_exceptions=True)
        # Enregistrer dans cache
        for url, data in zip(to_fetch, fetched):
            if isinstance(data, Exception):
                print(f"[warn] Échec fetch move {url}: {data}", file=sys.stderr)
                continue
            move_cache[url] = {
                "name_en": english_name_from_move_detail(data),
                "type": type_from_move_detail(data),
            }

    # 4) Injecter name_en (et type si demandé) dans chacune des listes de moves
    for summary in summaries:
        for m in summary["moves"]:
            url = m.get("url")
            if not url:
                continue
            cache_entry = move_cache.get(url) or {}
            m["name_en"] = cache_entry.get("name_en")
            if include_types:
                m["type"] = cache_entry.get("type")
        # Ordonner par nom anglais si dispo, sinon par nom brut
        summary["moves"].sort(key=lambda x: (x.get("name_en") or x.get("name") or ""))

    results = summaries
    return results


# ------------------------------
# Entrée/Sortie
# ------------------------------

def write_output(data: Any, path: Optional[str]) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        print(text)


# ------------------------------
# CLI
# ------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Résumé des moves 'scarlet-violet' pour une ou plusieurs espèces (asynchrone).")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--species", nargs="+", help="Liste d'espèces (noms ou ids).")
    src.add_argument("--species-file", help="Fichier texte (une espèce par ligne).")
    src.add_argument("--from-dir", help="Dossier contenant des JSON /pokemon/ au format PokeAPI (mode offline).")
    src.add_argument("--mapping-csv", help="CSV ';' avec colonnes Species;othername (PokeAPI sera appelée avec othername).")

    p.add_argument("--out", help="Fichier de sortie JSON (stdout si absent).")
    p.add_argument("--include-types", action="store_true", help="Inclure aussi le type du move (via détail du move).")
    p.add_argument("--move-cache", help="Fichier JSON cache pour détails de moves.")
    p.add_argument("--concurrency", type=int, default=8, help="Nombre de requêtes concurrentes (défaut: 8).")
    p.add_argument("--timeout", type=int, default=30, help="Timeout HTTP en secondes (défaut: 30).")
    p.add_argument("--retries", type=int, default=2, help="Nombre de retries HTTP (défaut: 2).")
    return p.parse_args()


# ------------------------------
# Mode offline (from-dir)
# ------------------------------

import glob

def read_pokemon_json_from_dir(d: str) -> List[Dict[str, Any]]:
    files = sorted(glob.glob(os.path.join(d, "*.json")))
    res: List[Dict[str, Any]] = []
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                res.append(json.load(f))
        except Exception as e:
            print(f"[warn] Échec lecture {fp}: {e}", file=sys.stderr)
    return res


def process_from_dir(d: str, include_types: bool, move_cache: Dict[str, Dict[str, Any]], vg_name: str = "scarlet-violet") -> List[Dict[str, Any]]:
    pokemons = read_pokemon_json_from_dir(d)
    summaries: List[Dict[str, Any]] = []
    needed_urls: Dict[str, None] = {}
    for poke in pokemons:
        summary, need_urls = summarize_sv_moves_from_pokemon_json(poke, vg_name=vg_name)
        summaries.append(summary)
        for url in need_urls.keys():
            needed_urls[url] = None

    # Offline: si include_types, on ne peut pas fetch, donc on remplit avec ce que le cache possède déjà
    for url in list(needed_urls.keys()):
        if url not in move_cache:
            print(f"[warn] Move {url} absent du cache en mode offline. Le nom anglais/type ne seront pas renseignés.", file=sys.stderr)

    for summary in summaries:
        for m in summary["moves"]:
            url = m.get("url")
            cache_entry = move_cache.get(url) or {}
            m["name_en"] = cache_entry.get("name_en")
            if include_types:
                m["type"] = cache_entry.get("type")
        summary["moves"].sort(key=lambda x: (x.get("name_en") or x.get("name") or ""))
    return summaries


# ------------------------------
# Main
# ------------------------------

def main() -> None:
    args = parse_args()
    cfg = FetcherConfig(
        timeout=args.timeout,
        retries=args.retries,
        concurrency=args.concurrency
    )

    move_cache = load_move_cache(args.move_cache)

    if args.from_dir:
        results = process_from_dir(args.from_dir, args.include_types, move_cache)
        write_output(results, args.out)
        save_move_cache(args.move_cache, move_cache)
        return

    # Mode réseau complet : via mapping, liste, ou fichier
    if args.mapping_csv:
        api_names, display_names = read_mapping_csv(args.mapping_csv)
        results = asyncio.run(process_species_list(api_names, args.include_types, cfg, move_cache, aliases=display_names))
    else:
        if args.species:
            species_list = args.species
        else:
            species_list = read_species_file(args.species_file)
        results = asyncio.run(process_species_list(species_list, args.include_types, cfg, move_cache))

    write_output(results, args.out)
    save_move_cache(args.move_cache, move_cache)


if __name__ == "__main__":
    main()