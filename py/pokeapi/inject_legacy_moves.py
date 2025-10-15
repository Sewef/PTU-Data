#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SAFE injector v2: never deletes existing Level-Up moves and avoids duplicate insertions
caused by different punctuation/casing (e.g., "Double Edge" vs "Double-Edge").

What it does
- Fetch PokéAPI in parallel (Gen 9→6 window).
- Level-Up: only APPEND new entries following your rules; never removes/rewrites existing ones.
  * Legacy tag ONLY if the move is absent in Gen 9.
  * Early rule: if a move is learned at 0/Evo or 1 AND also at a later level somewhere (G6–G9),
    keep both the early (0/Evo/1) and the most-recent later level (>1). We only APPEND missing ones.
  * If move is missing in Gen 9 but existed earlier, inject levels from most recent earlier gen (8,7,6).
- TM/HM, Tutor, Egg: fill from any of Gen 9..6 and sort alphabetically.
- Diff CSV for ALL insertions (Level-Up, TM/HM, Tutor, Egg).
- NEW: canonicalize move names via slug for presence checks to prevent duplicates.
- NEW: when appending, reuse existing display text for a slug (keeps hyphen/spacing style).

Usage:
  python inject_legacy_moves_safe_v2.py \
    --pokedex pokedex_core.json \
    --mapping mapping.csv \
    --out pokedex_core.legacy.json \
    --diff-csv learnset_diff.csv \
    --workers 8
"""
import argparse,json, sys, time, re, threading
from typing import Dict, List, Tuple, Optional, Any, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
from csv import DictReader, DictWriter
try:
    import requests
except ImportError:
    print("Requires 'requests' (pip install requests)", file=sys.stderr)
    raise

# ---------- Logging ----------
def log_info(msg: str): sys.stderr.write(f"[INFO] {msg}\n")
def log_warn(msg: str): sys.stderr.write(f"[WARN] {msg}\n")

# ---------- Version Group → Generation ----------
VG_TO_GEN = {
    "x-y": 6,
    "omega-ruby-alpha-sapphire": 6,
    "sun-moon": 7,
    "ultra-sun-ultra-moon": 7,
    "lets-go-pikachu-lets-go-eevee": 7,
    "sword-shield": 8,
    "brilliant-diamond-and-shining-pearl": 8,
    "legends-arceus": 8,
    "scarlet-violet": 9,
}
GENS = [9,8,7,6]

# ---------- Caches ----------
POKEMON_CACHE: Dict[str, dict] = {}
MOVE_CACHE: Dict[str, dict] = {}
LOCK = threading.Lock()

# ---------- HTTP ----------
def make_session()->requests.Session:
    s = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100, max_retries=0)
    s.mount("http://", adapter); s.mount("https://", adapter)
    s.headers.update({"User-Agent":"PTU-Legacy-Moves/SAFE-2.0"})
    return s

def http_get(session, url, tries=3, backoff=0.8):
    last=None
    for i in range(tries):
        try:
            r = session.get(url, timeout=25)
            if r.status_code==200: return r.json()
            if r.status_code in (429,500,502,503,504): last=f"HTTP {r.status_code}"
            else: last=f"HTTP {r.status_code}"
        except Exception as e:
            last=str(e)
        time.sleep(backoff*(i+1))
    log_warn(f"GET failed {url} -> {last}")
    return None

def slugify(name:str)->str:
    s=name.strip().lower().replace("’","").replace("'","")
    s=re.sub(r"\s+","-",s)
    s=re.sub(r"[^a-z0-9\-]+","",s)
    return s

# ---------- API ----------
def get_pokemon(session, name:str)->Optional[dict]:
    key=name.strip().lower()
    with LOCK:
        if key in POKEMON_CACHE: return POKEMON_CACHE[key]
    data=http_get(session, f"https://pokeapi.co/api/v2/pokemon/{key}")
    if data:
        with LOCK: POKEMON_CACHE[key]=data
    return data

def get_move(session, name:str)->Optional[dict]:
    key=slugify(name)
    with LOCK:
        if key in MOVE_CACHE: return MOVE_CACHE[key]
    data=http_get(session, f"https://pokeapi.co/api/v2/move/{key}")
    if data:
        with LOCK: MOVE_CACHE[key]=data
    return data

# ---------- Helpers ----------
def extract_levelup_levels_by_gen(pdata:dict)->Dict[str, Dict[int, List[int]]]:
    out={}
    for m in pdata.get("moves",[]):
        mslug=m.get("move",{}).get("name","")
        if not mslug: continue
        for vgd in m.get("version_group_details",[]):
            if vgd.get("move_learn_method",{}).get("name","")!="level-up": continue
            gen=VG_TO_GEN.get(vgd.get("version_group",{}).get("name",""))
            if gen not in GENS: continue
            lvl=vgd.get("level_learned_at",0)
            out.setdefault(mslug,{}).setdefault(gen,[])
            if lvl not in out[mslug][gen]: out[mslug][gen].append(lvl)
    for gmap in out.values():
        for g in gmap: gmap[g]=sorted(gmap[g])
    return out

def extract_methods_by_gen(pdata:dict)->Dict[str, Dict[str, Set[int]]]:
    out={}
    for m in pdata.get("moves",[]):
        mslug=m.get("move",{}).get("name","")
        if not mslug: continue
        for vgd in m.get("version_group_details",[]):
            meth=vgd.get("move_learn_method",{}).get("name","")
            if meth not in ("machine","tutor","egg","level-up"): continue
            gen=VG_TO_GEN.get(vgd.get("version_group",{}).get("name",""))
            if gen not in GENS: continue
            out.setdefault(mslug,{}).setdefault(meth,set()).add(gen)
    return out

def titlecase_from_slug(slug:str)->str:
    return " ".join(p.capitalize() for p in slug.split("-"))

def move_type_from_cache(slug:str)->Optional[str]:
    data=MOVE_CACHE.get(slugify(slug))
    if not data: return None
    t=data.get("type",{}).get("name")
    return t.capitalize() if t else None

def choose_latest_later_level(levels_by_gen:Dict[int,List[int]])->Optional[int]:
    later={g:[L for L in lvls if L>1] for g,lvls in levels_by_gen.items()}
    later={g:v for g,v in later.items() if v}
    if not later: return None
    g=max(later.keys())
    return max(later[g])

def decide(levels_by_gen:Dict[int,List[int]]):
    has9=9 in levels_by_gen and bool(levels_by_gen[9])
    early=set(); later_by_gen={}
    for g,lvls in levels_by_gen.items():
        for L in lvls:
            if L in (0,1): early.add(L)
            elif L>1: later_by_gen.setdefault(g,[]).append(L)
    mr_later=max(later_by_gen.keys()) if later_by_gen else None
    early_keep=sorted(list(early)) if mr_later is not None else []
    inject_from_recent=[]
    if not has9:
        for g in [8,7,6]:
            if g in levels_by_gen and levels_by_gen[g]:
                inject_from_recent=sorted(levels_by_gen[g]); break
    return inject_from_recent, early_keep, mr_later, has9

# ---- Canonical presence checks & display reuse ----
def species_display_for_slug(entries:list, slug:str)->Optional[str]:
    """Return first existing display text for this slug in entries (by 'Move'), if any."""
    s=slugify(slug)
    for e in entries:
        if isinstance(e,dict):
            nm=e.get("Move","")
            if slugify(nm)==s: return nm
    return None

def levelup_has(entries:list, slug:str, level)->bool:
    s=slugify(slug)
    for e in entries:
        if isinstance(e,dict):
            if slugify(e.get("Move",""))==s and e.get("Level")==level:
                return True
    return False

def list_has_move(entries:list, slug:str)->bool:
    s=slugify(slug)
    for e in entries:
        if isinstance(e,dict) and slugify(e.get("Move",""))==s: return True
        if isinstance(e,str) and slugify(e)==s: return True
    return False

def normalize_simple_list(name:str, species:str, lst:list)->list:
    if not isinstance(lst,list):
        log_warn(f"{species}: '{name}' is not a list (type {type(lst).__name__}); replaced with []")
        return []
    changed=0
    for i,e in enumerate(list(lst)):
        if isinstance(e,str):
            lst[i]={"Move": e}; changed+=1
        elif isinstance(e,dict):
            if "Move" not in e: log_warn(f"{species}: '{name}[{i}]' dict without 'Move': {e!r}")
        else:
            log_warn(f"{species}: '{name}[{i}]' unexpected type {type(e).__name__}: {e!r}")
    if changed: log_info(f"{species}: {name} — normalized {changed} string entries into dicts")
    return lst

# ---------- Main ----------
def main():
    ap=argparse.ArgumentParser(description="SAFE inject v3 (never deletes by default; optional dedupe to fix duplicate later levels)")
    ap.add_argument("--pokedex", required=True)
    ap.add_argument("--mapping", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--diff-csv", default=None)
    ap.add_argument("--dedupe-output", action="store_true", help="If set, collapse later-level duplicates per move to the canonical one.")
    ap.add_argument("--dedupe-report", default=None, help="CSV path to write removed entries during dedupe.")
    ap.add_argument("--workers", type=int, default=8)
    args=ap.parse_args()

    with open(args.pokedex,"r",encoding="utf-8") as f: pokedex=json.load(f)
    # mapping
    mp={}
    with open(args.mapping,"r",encoding="utf-8-sig",newline="") as f:
        for row in DictReader(f):
            s=(row.get("species") or "").strip(); o=(row.get("othername") or "").strip()
            if s and o: mp[s]=o
    if not mp:
        sys.stderr.write("[ERROR] Mapping CSV is empty or missing headers species,othername\n"); sys.exit(2)

    # pairs
    pairs=[]
    for spec in pokedex:
        sname=spec.get("Species")
        if not sname: continue
        oname=mp.get(sname)
        if not oname: 
            log_warn(f"No mapping for '{sname}'"); 
            continue
        pairs.append((sname,oname))

    session=make_session()

    # fetch pokemon parallel
    log_info(f"Fetching PokéAPI for {len(pairs)} species with {args.workers} workers...")
    def fp(pair):
        disp,api=pair
        data=get_pokemon(session, api)
        if not data: log_warn(f"Missing data for {api}")
        return (disp,api,data)
    poke_payloads={}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        fut={ex.submit(fp,p):p for p in pairs}
        for f in as_completed(fut):
            disp,api,data=f.result()
            if data: poke_payloads[api]=data

    # extract + collect moves
    log_info("Extracting learnsets...")
    levels_by_api={}
    methods_by_api={}
    unique_moves=set()
    for disp,api in pairs:
        pdata=poke_payloads.get(api)
        if not pdata: continue
        lv=extract_levelup_levels_by_gen(pdata)
        md=extract_methods_by_gen(pdata)
        levels_by_api[api]=lv
        methods_by_api[api]=md
        unique_moves.update(lv.keys()); unique_moves.update(md.keys())

    # fetch move types
    log_info(f"Fetching {len(unique_moves)} move payloads for types...")
    def fm(m): return (m, get_move(session, m))
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        fut={ex.submit(fm,m):m for m in unique_moves}
        for f in as_completed(fut):
            mname,data=f.result()
            if not data: log_warn(f"Missing move payload: {mname}")

    # inject

    # container to collect dedupe removals if enabled
    dedupe_removed_rows = []
    diff_rows=[]
    total_added=0
    for spec in pokedex:
        sname=spec.get("Species"); 
        if not sname: continue
        oname=mp.get(sname)
        if not oname: continue

        lvmap=levels_by_api.get(oname,{})
        mdmap=methods_by_api.get(oname,{})
        moves=spec.setdefault("Moves",{})
        lvl_list=moves.setdefault("Level Up Move List",[])
        tmhm=moves.setdefault("TM/HM Move List",[])
        tutor=moves.setdefault("Tutor Move List",[])
        egg=moves.setdefault("Egg Move List",[])

        # normalize non-level lists
        tmhm=normalize_simple_list("TM/HM Move List", sname, tmhm)
        tutor=normalize_simple_list("Tutor Move List", sname, tutor)
        egg=normalize_simple_list("Egg Move List", sname, egg)

        # helper to pick display text consistent with existing entries for a slug
        def pick_display(slug: str)->str:
            existing = species_display_for_slug(lvl_list, slug) or species_display_for_slug(tmhm, slug) or species_display_for_slug(tutor, slug) or species_display_for_slug(egg, slug)
            return existing if existing else titlecase_from_slug(slug)

        # per-move injection
        for mslug, levels in lvmap.items():
            disp = pick_display(mslug)
            mtype = move_type_from_cache(mslug)
            inject_from_recent, early_keep, mr_later_gen, has9 = decide(levels)
            canonical_later = choose_latest_later_level(levels)

            # Missing in Gen9 → copy most recent earlier
            if not has9 and inject_from_recent:
                src_gen = next((g for g in (8,7,6) if g in levels and levels[g]), None)
                for L in inject_from_recent:
                    if L>1 and canonical_later is not None and L!=canonical_later: 
                        continue
                    Lfield="Evo" if L==0 else L
                    if not levelup_has(lvl_list, mslug, Lfield):
                        entry={"Level": Lfield, "Move": disp, "Type": mtype if mtype else None, "Tags":["Legacy"]}
                        lvl_list.append(entry)
                        total_added+=1
                        diff_rows.append({"Species": sname, "PokeAPIName": oname, "Move": disp, "Level": Lfield, "Type": entry["Type"], "Reason": "MissingInGen9FromEarlierGen", "SourceGen": src_gen})

            # Early + later pair rule (append only missing ones)
            if early_keep and canonical_later is not None:
                for L in early_keep:
                    Lfield="Evo" if L==0 else L
                    if not levelup_has(lvl_list, mslug, Lfield):
                        entry={"Level": Lfield, "Move": disp, "Type": mtype if mtype else None}
                        if not has9: entry["Tags"]=["Legacy"]
                        lvl_list.append(entry); total_added+=1
                        diff_rows.append({"Species": sname, "PokeAPIName": oname, "Move": disp, "Level": Lfield, "Type": entry["Type"], "Reason": "EarlyAndLaterPair", "SourceGen": mr_later_gen})
                L=canonical_later
                if L is not None:
                    if not levelup_has(lvl_list, mslug, L):
                        entry={"Level": L, "Move": disp, "Type": mtype if mtype else None}
                        if not has9: entry["Tags"]=["Legacy"]
                        lvl_list.append(entry); total_added+=1
                        diff_rows.append({"Species": sname, "PokeAPIName": oname, "Move": disp, "Level": L, "Type": entry["Type"], "Reason": "EarlyAndLaterPair", "SourceGen": mr_later_gen})

        # TM/HM / Tutor / Egg additions
        for mslug, methods in mdmap.items():
            disp = pick_display(mslug)
            mtype = move_type_from_cache(mslug)

            if methods.get("machine"):
                if not list_has_move(tmhm, mslug):
                    tmhm.append({"Move": disp, "Type": mtype if mtype else None})
                    diff_rows.append({"Species": sname, "PokeAPIName": oname, "Move": disp, "Level": "", "Type": mtype if mtype else None, "Reason":"TM/HM", "SourceGen": max(methods["machine"])})

            if methods.get("tutor"):
                if not list_has_move(tutor, mslug):
                    tutor.append({"Move": disp, "Type": mtype if mtype else None})
                    diff_rows.append({"Species": sname, "PokeAPIName": oname, "Move": disp, "Level": "", "Type": mtype if mtype else None, "Reason":"Tutor", "SourceGen": max(methods["tutor"])})

            if methods.get("egg"):
                if not list_has_move(egg, mslug):
                    egg.append({"Move": disp, "Type": mtype if mtype else None})
                    diff_rows.append({"Species": sname, "PokeAPIName": oname, "Move": disp, "Level": "", "Type": mtype if mtype else None, "Reason":"Egg", "SourceGen": max(methods["egg"])})

        # sort non-level lists
        def sort_alpha(lst:List[dict]): lst.sort(key=lambda e: (str(e.get("Move","")), str(e.get("Type",""))))
        sort_alpha(tmhm); sort_alpha(tutor); sort_alpha(egg)

        # sort level-up by Level then Move (stable)
        def sort_key(e:dict):
            L=e.get("Level")
            n=0 if isinstance(L,str) and str(L).lower()=="evo" else (L if isinstance(L,int) else 9999)
            return (n, e.get("Move",""))
        lvl_list.sort(key=sort_key)


    # optional output dedupe pass (fix duplicate later levels) — removes entries
    if args.dedupe_output:
        # build convenient maps for generation levels
        def canonical_later_for(api_name: str, move_slug: str) -> Optional[int]:
            lvmap = levels_by_api.get(api_name, {})
            levels_by_gen = lvmap.get(move_slug, {})
            # compute canonical later as earlier
            later={g:[L for L in lvls if L>1] for g,lvls in levels_by_gen.items()}
            later={g:v for g,v in later.items() if v}
            if not later: return None
            g=max(later.keys())
            return max(later[g])

        for spec in pokedex:
            sname = spec.get("Species")
            if not sname: continue
            oname = mp.get(sname)
            if not oname: continue

            moves = spec.get("Moves", {})
            lvl_list = moves.get("Level Up Move List", [])
            if not isinstance(lvl_list, list): continue

            # group indices by slug
            by_slug = {}
            for idx, e in enumerate(lvl_list):
                if not isinstance(e, dict): continue
                m = e.get("Move", "")
                s = slugify(m)
                by_slug.setdefault(s, []).append(idx)

            to_keep = set()
            to_drop = set()

            for s, idxs in by_slug.items():
                # pull slug→any one slug string to query canonical level
                # We need the original mslug as PokéAPI uses dashes; our slug should match move endpoint names
                # Reconstruct a "slug-ish" name: already good.
                mslug = s
                # map indices entries
                entries = [lvl_list[i] for i in idxs if isinstance(lvl_list[i], dict)]
                # detect canonical later using API data:
                can_later = canonical_later_for(oname, mslug)
                if can_later is None:
                    # No later anywhere: keep everything untouched
                    to_keep.update(idxs)
                    continue

                # Keep all early (Evo/0 and/or 1) that are present
                for i in idxs:
                    e = lvl_list[i]
                    if not isinstance(e, dict): 
                        to_keep.add(i); 
                        continue
                    L = e.get("Level")
                    if (isinstance(L, str) and str(L).lower()=="evo") or L==1:
                        to_keep.add(i)

                # Keep exactly one later: the canonical one; drop others with Level >1
                kept_one = False
                for i in idxs:
                    e = lvl_list[i]
                    if not isinstance(e, dict): 
                        continue
                    L = e.get("Level")
                    if isinstance(L, int) and L>1:
                        if L == can_later and not kept_one:
                            to_keep.add(i); kept_one=True
                        else:
                            to_drop.add(i)

                # If no canonical later found among entries (e.g., only old later levels present), we do not synthesize here.
                # The injection phase already tried to add canonical later if missing. If still missing, we keep nothing extra.

            if to_drop:
                # Record removals for report
                for i in sorted(to_drop):
                    e = lvl_list[i]
                    if isinstance(e, dict):
                        dedupe_removed_rows.append({
                            "Species": sname,
                            "PokeAPIName": oname,
                            "Move": e.get("Move"),
                            "Level": e.get("Level"),
                            "Type": e.get("Type"),
                            "Reason": "RemovedByDedupe",
                            "SourceGen": ""
                        })
                # Apply removal
                lvl_list[:] = [e for i, e in enumerate(lvl_list) if i in to_keep]

        # write dedupe report CSV if requested
        if args.dedupe_report:
            import csv
            with open(args.dedupe_report, "w", encoding="utf-8", newline="") as f:
                w = DictWriter(f, fieldnames=["Species","PokeAPIName","Move","Level","Type","Reason","SourceGen"])
                w.writeheader(); w.writerows(dedupe_removed_rows)

    # write out
    with open(args.out,"w",encoding="utf-8") as f:
        json.dump(pokedex, f, ensure_ascii=False, indent=2)

    if args.diff_csv:
        with open(args.diff_csv,"w",encoding="utf-8",newline="") as f:
            w=DictWriter(f, fieldnames=["Species","PokeAPIName","Move","Level","Type","Reason","SourceGen"])
            w.writeheader(); w.writerows(diff_rows)

    log_info(f"[DONE] Added {total_added} Level-Up entries across {len(pokedex)} species.")
if __name__=="__main__":
    main()
