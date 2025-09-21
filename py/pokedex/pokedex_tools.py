
#!/usr/bin/env python3
import argparse, csv, json, re, time, sys
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

try:
    import requests
except Exception as e:
    requests = None

# Optional: rapidfuzz for better fuzzy if available
try:
    from rapidfuzz.fuzz import ratio as rf_ratio
    def fuzzy_ratio(a,b): return rf_ratio(a,b)/100.0
except Exception:
    from difflib import SequenceMatcher
    def fuzzy_ratio(a,b): return SequenceMatcher(None, a, b).ratio()

PUNCT_MAP = {"’":"'", "‘":"'", "“":'"', "”":'"', "—":"-", "–":"-"}

# --- Helpers ---
def normalize(s: str) -> str:
    if not s: return ""
    s = s.strip()
    for a,b in PUNCT_MAP.items():
        s = s.replace(a,b)
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    return s

def alias_variants(name: str) -> List[str]:
    """Generate reasonable alias variants for common punctuation/hyphen differences."""
    if not name: return []
    base = name
    v = set()
    def add(x): 
        if x: v.add(x)
    add(base)
    add(base.replace("-", " "))
    add(base.replace(" ", "-"))
    add(base.replace(".", ""))
    add(base.replace("’", "'"))
    add(base.replace("'", "’"))
    add(base.replace(":", ""))
    # Also collapse punctuation entirely
    add(re.sub(r"[-:'’.\s]+", " ", base))
    # Title-ish alt (for people who export Title Case)
    add(" ".join(w.capitalize() if w.islower() else w for w in base.split()))
    return list({normalize(x) for x in v})

# Special aliases (English)
SPECIAL_ALIASES = {
    "nidoran♀": ["nidoran f", "nidoran female", "nidoran-f"],
    "nidoran♂": ["nidoran m", "nidoran male", "nidoran-m"],
    "mr. mime": ["mr mime", "mr. mime"],
    "mime jr.": ["mime jr", "mime jr."],
    "farfetch’d": ["farfetchd", "farfetch'd"],
    "type: null": ["type null", "typenull"],
    "porygon-z": ["porygon z", "porygonz"],
    "ho-oh": ["ho oh", "hooh"],
}

# Form patterns (map to base species)
FORM_ALIASES = {
    "rotom": [
        "rotom normal form", "rotom appliance forms",
        "rotom heat", "rotom wash", "rotom frost", "rotom fan", "rotom mow"
    ],
    "meloetta": ["meloetta aria form", "meloetta step form"],
    "zygarde": ["zygarde 10% form", "zygarde 50% form", "zygarde complete form"],
    "necrozma": ["necrozma dusk mane", "necrozma dawn wings", "ultra necrozma"],
}

# Regional / mega / etc.
FORM_SUFFIXES = [
    "alolan", "galarian", "hisuian", "paldean",
    "mega", "gigantamax", "gmax", "primal",
]

def make_aliases_for_species(canon_name: str) -> List[str]:
    aliases = []
    # punctuation/hyphen/spaces variants
    aliases += alias_variants(canon_name)
    # specials
    if canon_name in SPECIAL_ALIASES:
        aliases += SPECIAL_ALIASES[canon_name]
    # forms
    base = canon_name.split(" (")[0]
    if base.lower() in FORM_ALIASES:
        aliases += FORM_ALIASES[base.lower()]
    # generic regional suffixes (e.g., "Meowth Alolan")
    for suf in FORM_SUFFIXES:
        aliases.append(f"{base} {suf}")
        aliases.append(f"{base}-{suf}")
    return sorted({normalize(a) for a in aliases})

# --- Fetch National Dex (English) from PokéAPI ---
POKEAPI = "https://pokeapi.co/api/v2"

def http_get(url, tries=3, sleep=0.3):
    last = None
    for _ in range(tries):
        try:
            r = requests.get(url, timeout=20)
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}"
        except Exception as e:
            last = str(e)
        time.sleep(sleep)
    raise RuntimeError(f"GET {url} failed: {last}")

def fetch_national_dex() -> List[Tuple[int, str, str]]:
    """Return list of (number, english_name, species_url)."""
    dex = http_get(f"{POKEAPI}/pokedex/national")
    entries = dex["pokemon_entries"]
    out = []
    for e in entries:
        num = e["entry_number"]
        species_url = e["pokemon_species"]["url"]
        # Get English name from species
        sp = http_get(species_url)
        en_name = None
        for n in sp.get("names", []):
            if n["language"]["name"] == "en":
                en_name = n["name"]
                break
        if not en_name:
            # fallback to species 'name' (lower-hyphen) capitalized
            en_name = sp.get("name", "").replace("-", " ").title()
        out.append((num, en_name, species_url))
    # sort by number to be safe
    out.sort(key=lambda x: x[0])
    return out

def write_ref_csv(rows: List[Tuple[int,str,str]], out_path: str):
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["number","name","aliases"])
        for num, en_name, _ in rows:
            aliases = "; ".join(sorted(set(make_aliases_for_species(en_name)) - {normalize(en_name)}))
            w.writerow([num, en_name, aliases])

# --- Annotate parsed JSON by adding "number" ---
def load_ref_csv(path: str) -> Dict[str, int]:
    by_norm = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            num = int(row["number"])
            name = row["name"]
            alias_str = row.get("aliases","")
            keys = set([normalize(name)])
            for a in re.split(r"[;,]", alias_str):
                a = a.strip()
                if a:
                    keys.add(normalize(a))
            for k in keys:
                by_norm[k] = num
    return by_norm

def match_number(name: str, ref_index: Dict[str,int], min_fuzzy: float=0.86) -> Optional[int]:
    n = normalize(name)
    # exact
    if n in ref_index:
        return ref_index[n]
    # fuzzy over keys
    best_key = None
    best_score = 0.0
    for k in ref_index.keys():
        sc = fuzzy_ratio(n, k)
        if sc > best_score:
            best_score = sc
            best_key = k
    if best_key and best_score >= min_fuzzy:
        return ref_index[best_key]
    return None

def annotate(input_json: str, ref_csv: str, output_json: str, min_fuzzy: float):
    data = json.loads(Path(input_json).read_text(encoding="utf-8"))
    ref_index = load_ref_csv(ref_csv)
    for e in data:
        nm = e.get("Name") or e.get("name") or ""
        e["number"] = match_number(nm, ref_index, min_fuzzy=min_fuzzy)
    Path(output_json).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {output_json} with {len(data)} entries.")

# --- CLI ---
def main():
    ap = argparse.ArgumentParser(description="Pokédex tools: generate reference CSV and annotate parsed JSON with numbers.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate-ref", help="Fetch National Dex (English) from PokéAPI and write pokedex_ref.csv")
    g.add_argument("-o","--output", required=True, help="Output CSV (e.g., pokedex_ref.csv)")

    a = sub.add_parser("annotate", help='Add "number" to each entry in your parsed JSON using the reference CSV')
    a.add_argument("-i","--input", required=True, help="Input parsed JSON")
    a.add_argument("-r","--ref", required=True, help="Reference CSV (number,name,aliases)")
    a.add_argument("-o","--output", required=True, help="Output JSON with numbers")
    a.add_argument("--min-fuzzy", type=float, default=0.86, help="Fuzzy match threshold (0.0–1.0), default 0.86")

    args = ap.parse_args()

    if args.cmd == "generate-ref":
        if requests is None:
            print("This command requires 'requests' (pip install requests)", file=sys.stderr)
            sys.exit(1)
        rows = fetch_national_dex()
        write_ref_csv(rows, args.output)
        print(f"Wrote {args.output} with {len(rows)} entries.")
    elif args.cmd == "annotate":
        annotate(args.input, args.ref, args.output, args.min_fuzzy)

if __name__ == "__main__":
    main()
