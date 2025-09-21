
#!/usr/bin/env python3
import argparse, csv, json, re
from pathlib import Path
from typing import Dict, List, Optional
try:
    from rapidfuzz.fuzz import ratio as rf_ratio
    def fuzzy_ratio(a,b): return rf_ratio(a,b)/100.0
except Exception:
    from difflib import SequenceMatcher
    def fuzzy_ratio(a,b): return SequenceMatcher(None, a, b).ratio()

PUNCT_MAP = {"’":"'", "‘":"'", "“":'"', "”":'"', "—":"-", "–":"-"}

def normalize(s: str) -> str:
    if not s: return ""
    s = s.strip()
    for a,b in PUNCT_MAP.items():
        s = s.replace(a,b)
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    return s

# ---- OFFLINE built-in minimal map (extend if desired) ----
NATIONAL_DEX: Dict[int, str] = {
    1: "Bulbasaur",
    2: "Ivysaur",
    3: "Venusaur",
    479: "Rotom",
    618: "Stunfisk",
    648: "Meloetta",
    702: "Dedenne",
}

SPECIAL_ALIASES = {
    "nidoran♀": ["nidoran f", "nidoran female", "nidoran-f"],
    "nidoran♂": ["nidoran m", "nidoran male", "nidoran-m"],
    "mr. mime": ["mr mime", "mr. mime"],
    "mime jr.": ["mime jr", "mime jr."],
    "farfetch’d": ["farfetchd", "farfetch'd"],
    "type: null": ["type null", "typenull"],
    "porygon-z": ["porygon z", "porygonz"],
    "ho-oh": ["ho oh", "hooh"],
    "rotom": ["rotom normal form", "rotom appliance forms", "rotom heat", "rotom wash", "rotom frost", "rotom fan", "rotom mow"],
    "meloetta": ["meloetta aria form", "meloetta step form"],
}

def alias_variants(name: str) -> List[str]:
    v = set()
    v.add(name)
    v.add(name.replace("-", " "))
    v.add(name.replace(" ", "-"))
    v.add(name.replace(".", ""))
    v.add(name.replace("’", "'"))
    v.add(name.replace("'", "’"))
    v.add(re.sub(r"[-:'’.\s]+", " ", name))
    v.add(" ".join(w.capitalize() if w.islower() else w for w in name.split()))
    return [normalize(x) for x in v]

def build_index_from_builtin() -> Dict[str, int]:
    idx: Dict[str, int] = {}
    for num, canon in NATIONAL_DEX.items():
        nn = normalize(canon)
        idx[nn] = num
        for a in alias_variants(canon):
            idx[a] = num
        if canon.lower() in SPECIAL_ALIASES:
            for a in SPECIAL_ALIASES[canon.lower()]:
                idx[normalize(a)] = num
    return idx

def load_ref_csv(path: str) -> Dict[str,int]:
    idx = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            num = int(row["number"])
            name = row["name"]
            keys = {normalize(name)}
            alias_str = row.get("aliases","")
            for a in re.split(r"[;,]", alias_str):
                a = a.strip()
                if a:
                    keys.add(normalize(a))
            for k in keys:
                idx[k] = num
    return idx

def match_number(name: str, ref_index: Dict[str,int], min_fuzzy: float=0.86) -> Optional[int]:
    n = normalize(name)
    if n in ref_index:
        return ref_index[n]
    best_k, best_s = None, 0.0
    for k in ref_index.keys():
        s = fuzzy_ratio(n, k)
        if s > best_s:
            best_s, best_k = s, k
    if best_k and best_s >= min_fuzzy:
        return ref_index[best_k]
    return None

def cmd_generate_ref(output_csv: str, from_csv: str | None):
    if from_csv:
        # Expect PokeAPI's pokemon_species_names.csv: columns include 'pokemon_species_id','local_language_id','name'
        # Filter local_language_id == 9 (English) and write number,name,aliases (aliases auto from variants)
        with open(from_csv, encoding="utf-8") as f_in, open(output_csv, "w", encoding="utf-8", newline="") as f_out:
            reader = csv.DictReader(f_in)
            rows = [r for r in reader if str(r.get("local_language_id","")) == "9"]
            # Build mapping id->English name
            id2name = {}
            for r in rows:
                try:
                    pid = int(r["pokemon_species_id"])
                except Exception:
                    continue
                id2name[pid] = r["name"]
            # Write
            w = csv.writer(f_out); w.writerow(["number","name","aliases"])
            for num in sorted(id2name.keys()):
                name = id2name[num]
                aliases = []
                aliases += alias_variants(name)
                if name.lower() in SPECIAL_ALIASES:
                    aliases += SPECIAL_ALIASES[name.lower()]
                aliases = sorted(set(a for a in aliases if a != normalize(name)))
                w.writerow([num, name, "; ".join(aliases)])
        print(f"Wrote {output_csv} from {from_csv} (language_id=9).")
        return
    # Fallback: built-in small map
    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["number","name","aliases"])
        for num in sorted(NATIONAL_DEX.keys()):
            name = NATIONAL_DEX[num]
            aliases = []
            aliases += alias_variants(name)
            if name.lower() in SPECIAL_ALIASES:
                aliases += SPECIAL_ALIASES[name.lower()]
            aliases = sorted(set(a for a in aliases if a != normalize(name)))
            w.writerow([num, name, "; ".join(aliases)])
    print(f"Wrote {output_csv} from built-in NATIONAL_DEX ({len(NATIONAL_DEX)} species).")

def cmd_annotate(input_json: str, ref_csv: str | None, output_json: str, min_fuzzy: float):
    if ref_csv:
        ref_index = load_ref_csv(ref_csv)
    else:
        ref_index = build_index_from_builtin()
    data = json.loads(Path(input_json).read_text(encoding="utf-8"))
    for e in data:
        nm = e.get("Name") or e.get("name") or ""
        e["Number"] = match_number(nm, ref_index, min_fuzzy=min_fuzzy)
    Path(output_json).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {output_json} with {len(data)} entries.")

def main():
    ap = argparse.ArgumentParser(description="OFFLINE Pokédex tools (with PokeAPI CSV support).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate-ref", help="Write pokedex_ref.csv from PokeAPI CSV (language_id=9) or built-in map")
    g.add_argument("-o","--output", required=True, help="Output CSV path")
    g.add_argument("--from-csv", default=None, help="Path to pokemon_species_names.csv (offline, downloaded)")

    a = sub.add_parser("annotate", help='Add "number" to each entry in your parsed JSON (offline)')
    a.add_argument("-i","--input", required=True, help="Parsed JSON input")
    a.add_argument("-r","--ref", default=None, help="Reference CSV; if omitted, built-in map is used")
    a.add_argument("-o","--output", required=True, help="Output JSON")
    a.add_argument("--min-fuzzy", type=float, default=0.86, help="Fuzzy threshold (0..1), default 0.86")

    args = ap.parse_args()
    if args.cmd == "generate-ref":
        cmd_generate_ref(args.output, args.from_csv)
    elif args.cmd == "annotate":
        cmd_annotate(args.input, args.ref, args.output, args.min_fuzzy)

if __name__ == "__main__":
    main()
