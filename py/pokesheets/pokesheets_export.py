#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, json, re, sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------- Utils I/O ----------------

def read_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def to_str(x) -> Optional[str]:
    if x is None:
        return None
    if isinstance(x, str):
        s = x.strip()
        return s if s else None
    return str(x)

def log(msg: str):
    print(msg, file=sys.stdout)

def warn(msg: str):
    print(f"[warn] {msg}", file=sys.stderr)

# ---------------- Parsing helpers ----------------

_SKILL_KEYS = [
    "athletics","acrobatics","combat","stealth","perception","focus",
    "charm","command","guile","intimidate","intuition","survival",
    "generalEdu","medicineEdu","occultEdu","pokemonEdu","techEdu",
]
_DEFAULT_SKILL_VAL = "1d6+0"

_NUMERIC_CAP_KEYS = [
    "Overland","Sky","Swim","Levitate","Burrow","High Jump","Long Jump","Power"
]

def parse_percentages(genders: Optional[str]) -> Tuple[Optional[float], Optional[float], bool]:
    """
    "50.0% Male / 50.0% Female" -> (50.0, 50.0, False)
    "Genderless" -> (None, None, True)
    """
    if not genders or not isinstance(genders, str):
        return (None, None, False)
    s = genders.strip()
    if not s:
        return (None, None, False)
    if "genderless" in s.lower():
        return (None, None, True)
    nums = re.findall(r"(\d+(?:\.\d+)?)\s*%\s*(Male|Female)", s, flags=re.I)
    male, female = None, None
    for val, label in nums:
        pct = float(val)
        if label.lower().startswith("male"):
            male = pct
        elif label.lower().startswith("female"):
            female = pct
    return (male, female, False)

def extract_size_weight(other_info: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """ Height like: 2' 4" / 0.7m (Small)  → size='Small'
        Weight like: 15.2 lbs. / 6.9 kg (Weight Class 1) → weight='15.2' (first number)
    """
    size_info = (other_info or {}).get("Size Information") or {}
    height = to_str(size_info.get("Height"))
    weight = to_str(size_info.get("Weight"))
    size = None
    if height:
        m = re.search(r"\(([^)]+)\)", height)
        if m:
            size = m.group(1).strip()
    w = None
    if weight:
        m = re.search(r"([\d.]+)", weight)
        if m:
            w = m.group(1)
    return size, w

def split_csv_like(s: Optional[str]) -> List[str]:
    """Split 'Forest, Grassland, Rainforest' → ['Forest','Grassland','Rainforest']"""
    if not s:
        return []
    parts = re.split(r"\s*,\s*|\s*/\s*", s.strip())
    return [p for p in parts if p]

def base_stats_to_pokesheets(bs: Dict[str, Any]) -> Dict[str, int]:
    def _num(v):
        try:
            return int(v)
        except Exception:
            try:
                return int(float(v))
            except Exception:
                return 0
    return {
        "hp": _num(bs.get("HP")),
        "atk": _num(bs.get("Attack")),
        "def": _num(bs.get("Defense")),
        "spatk": _num(bs.get("Special Attack")),
        "spdef": _num(bs.get("Special Defense")),
        "spd": _num(bs.get("Speed")),
    }

def map_level_up_moves(moves: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for m in moves or []:
        name = to_str(m.get("Move"))
        if not name:
            continue
        lvl = m.get("Level")
        if isinstance(lvl, str) and lvl.lower() == "evo":
            learned = 1
        else:
            try:
                learned = int(lvl)
            except Exception:
                learned = 1
        out.append({"moveName": name, "learnedLevel": learned})
    # conserve l'ordre source
    return out

def normalize_method(m: Optional[str]) -> Optional[str]:
    if not m:
        return None
    t = m.strip().lower()
    if t in ("machine", "tm"): return "Machine"
    if t == "egg": return "Egg"
    if t == "tutor": return "Tutor"
    if t in ("level-up","level up"): return "Level-Up"
    return m.capitalize()

def collect_tm_egg_tutor_moves(moves_block: Dict[str, Any]) -> Tuple[List[str], List[str], List[str]]:
    """
    Normalise en trois listes de strings :
      - machineMoves
      - eggMoves
      - tutorMoves
    En priorité, on lit 'TM/Tutor Moves List' (objets {Move, Type, Tags, Method}).
    On complète avec les listes historiques: TM/HM Move List, Egg Move List, Tutor Move List.
    """
    machine, egg, tutor = [], [], []

    # 1) Nouvelle liste unifiée (objets)
    tml = moves_block.get("TM/Tutor Moves List") or []
    for it in tml:
        if isinstance(it, str):
            mv = it.replace(" (N)", "").strip()
            if mv:
                tutor.append(mv)  # par défaut
            continue
        if isinstance(it, dict):
            mv = to_str(it.get("Move"))
            if not mv:
                continue
            method = normalize_method(to_str(it.get("Method")))
            if method == "Machine":
                machine.append(mv)
            elif method == "Egg":
                egg.append(mv)
            elif method in ("Tutor", "Level-Up", None):
                tutor.append(mv)
            else:
                tutor.append(mv)

    # 2) Listes legacy (strings)
    for mv in moves_block.get("TM/HM Move List") or []:
        if isinstance(mv, str) and mv.strip():
            machine.append(mv.replace(" (N)", "").strip())
    for mv in moves_block.get("Egg Move List") or []:
        if isinstance(mv, str) and mv.strip():
            egg.append(mv.replace(" (N)", "").strip())
    for mv in moves_block.get("Tutor Move List") or []:
        if isinstance(mv, str) and mv.strip():
            tutor.append(mv.replace(" (N)", "").strip())

    # dédoublonner en conservant l'ordre
    def dedupe(seq: List[str]) -> List[str]:
        seen, out = set(), []
        for x in seq:
            if x not in seen:
                seen.add(x); out.append(x)
        return out

    return dedupe(machine), dedupe(egg), dedupe(tutor)

# -------- abilities.json: prise en charge des clés capitalisées (Name/Effect/Frequency/Bonus/Target) --------

def _norm_key(s: Optional[str]) -> Optional[str]:
    return s.strip().lower() if isinstance(s, str) else None

def _norm_name_for_lookup(name: Optional[str]) -> Optional[str]:
    if not isinstance(name, str):
        return None
    return re.sub(r"\s+", " ", name.strip().lower())

def load_abilities_db(path: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    """
    abilities.json accepté sous plusieurs formes :
      - dict { "Absorb Force": { "Effect": "...", "Frequency": "...", ... }, ... }
      - list [ { "Name": "Absorb Force", "Effect": "...", "Bonus": "...", "Target": "...", "Frequency": "..." }, ... ]
      - list [ { "name": "Absorb Force", "effect": "...", "trigger": "...", "target": "...", "frequency": "..." }, ... ]

    On construit un dict normalisé indexé par le nom (insensible à la casse/espaces) :
      { norm_name: { name, effect, trigger, target, frequency } }
    - effect = Effect (+ " " + Bonus si présent)
    - trigger peut être absent → None
    """
    db: Dict[str, Dict[str, Any]] = {}
    if not path:
        return db
    try:
        data = read_json(path)
    except Exception as e:
        warn(f"failed to read abilities: {e}")
        return db

    def normalize_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # nom
        name = item.get("Name") or item.get("name")
        name = to_str(name)
        if not name:
            return None

        # candidates (case-insensitive)
        def pick(*keys):
            for k in keys:
                if k in item and item[k] is not None:
                    return item[k]
            # also search case-insensitively
            low = {k.lower(): v for k, v in item.items()}
            for k in keys:
                if isinstance(k, str) and k.lower() in low and low[k.lower()] is not None:
                    return low[k.lower()]
            return None

        effect   = pick("Effect", "effect", "Description", "description")
        bonus    = pick("Bonus", "bonus")
        trigger  = pick("Trigger", "trigger")
        target   = pick("Target", "target")
        freq     = pick("Frequency", "frequency")

        effect_s = to_str(effect) or None
        bonus_s  = to_str(bonus) or None
        if effect_s and bonus_s:
            # concaténer Bonus après un espace (comme demandé)
            effect_s = effect_s.rstrip() + " " + bonus_s.lstrip()

        return {
            "name": to_str(name),
            "effect": effect_s,
            "trigger": to_str(trigger),
            "target": to_str(target),
            "frequency": to_str(freq),
        }

    if isinstance(data, dict):
        # dict par nom → mapper chaque valeur
        for k, v in data.items():
            if isinstance(v, dict):
                item = {"Name": k, **v}
                norm = normalize_item(item)
                if norm:
                    db[_norm_name_for_lookup(norm["name"])] = norm
    elif isinstance(data, list):
        for v in data:
            if isinstance(v, dict):
                norm = normalize_item(v)
                if norm:
                    db[_norm_name_for_lookup(norm["name"])] = norm
    else:
        warn("abilities.json has unsupported shape")

    log(f"[info] abilities loaded: {len(db)} entries")
    return db

def map_abilities(basic_info: Dict[str, Any], abilities_db: Dict[str, Dict[str, Any]], species_name: Optional[str]=None):
    # Source: Basic Ability 1/2, Adv Ability 1/2, High Ability
    basics, advs, highs = [], [], []

    for k in ("Basic Ability 1","Basic Ability 2"):
        v = to_str((basic_info or {}).get(k))
        if v: basics.append(v)
    for k in ("Adv Ability 1","Adv Ability 2"):
        v = to_str((basic_info or {}).get(k))
        if v: advs.append(v)
    v = to_str((basic_info or {}).get("High Ability"))
    if v: highs.append(v)

    def lookup(name: str) -> Dict[str, Any]:
        norm = _norm_name_for_lookup(name)
        
        norm = norm.strip('*')

        # If name contains a parenthetical (e.g. "Type Aura (Water)"), try lookup without it
        # but restore the original name (with parentheses) on the matched entry.
        if isinstance(norm, str) and "(" in norm and ")" in norm:
            stripped_norm = re.sub(r"\s*\([^)]*\)", "", norm).strip()
            # normalize spaces like _norm_name_for_lookup would
            stripped_norm = re.sub(r"\s+", " ", stripped_norm)
            # try also without trailing commas
            alt_norms = [stripped_norm, stripped_norm.rstrip(",").strip()] if stripped_norm else []
            for candidate in alt_norms:
                if candidate and candidate in abilities_db:
                    # copy entry to preserve original DB shape but ensure returned name keeps parentheses
                    abilities_db[candidate] = {**abilities_db[candidate], "name": name}
                    norm = candidate
                    break
        
        meta = abilities_db.get(norm)
        if not meta:
            warn(f"[abilities] not found in abilities.json: {name} ({species_name})")
            return {
                "name": name,
                "effect": None,
                "trigger": None,
                "target": None,
                "frequency": None,
            }
        # renvoyer une copie pour éviter mutation
        return {
            "name": meta.get("name") or name,
            "effect": meta.get("effect"),
            "trigger": meta.get("trigger"),
            "target": meta.get("target"),
            "frequency": meta.get("frequency"),
        }

    basic_objs = [lookup(n) for n in basics]
    adv_objs   = [lookup(n) for n in advs]
    high_objs  = [lookup(n) for n in highs]
    return basic_objs, adv_objs, high_objs, basics, advs, highs

# -------- Capabilities: Jump X/Y -> High Jump=X, Long Jump=Y; manque = 0; autres -> clé -1 + recopie --------

def parse_capabilities_block(caps_raw) -> Tuple[Dict[str, Any], str]:
    """
    Transforme la liste 'Capabilities' source en :
      - dict capabilities Pokesheets: Numeric caps (Overland, Sky, ...) int ; 'Jump X/Y' -> High/Long Jump ;
        toutes caps manquantes dans _NUMERIC_CAP_KEYS forcées à 0 ;
        les autres caps agglomérées en un seul champ-string (comma-joined) et AUSSI ajoutées comme clé unique à -1.
      - otherCapabilities: string identique aux "autres caps"
    """
    numeric: Dict[str, Any] = {}
    others: List[str] = []

    def push_pair(key: str, value: str):
        key = key.strip()
        if not key:
            return
        # Jump X/Y
        if key.lower().startswith("jump"):
            s = str(value).strip()
            m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*/\s*(-?\d+(?:\.\d+)?)\s*$", s)
            if m:
                try:
                    numeric["High Jump"] = int(float(m.group(1)))
                except Exception:
                    numeric["High Jump"] = 0
                try:
                    numeric["Long Jump"] = int(float(m.group(2)))
                except Exception:
                    numeric["Long Jump"] = 0
                return
            # fallback "Jump 2" -> High Jump only
            try:
                numeric["High Jump"] = int(float(s))
            except Exception:
                numeric["High Jump"] = numeric.get("High Jump", 0)
            return

        # High/Long Jump individual values
        if key in ("High Jump","Long Jump"):
            try:
                numeric[key] = int(float(str(value)))
            except Exception:
                numeric[key] = numeric.get(key, 0)
            return

        # Numeric simple caps
        if key in _NUMERIC_CAP_KEYS:
            try:
                numeric[key] = int(float(str(value)))
            except Exception:
                numeric[key] = numeric.get(key, 0)
            return

        # Otherwise → other capability chip
        others.append(key)

    def from_string(s: str):
        s = s.strip()
        if not s:
            return
        # "Overland 5" / "Swim 3" / "Jump 1/1" / "Naturewalk (Forest, Grassland)"
        m = re.match(r"^(.+?)\s+(-?\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?)\s*$", s)
        if m:
            push_pair(m.group(1), m.group(2))
        else:
            others.append(s)

    # Accept many shapes
    if isinstance(caps_raw, list):
        for item in caps_raw:
            if item is None:
                continue
            if isinstance(item, str):
                from_string(item)
            elif isinstance(item, dict):
                for k, v in item.items():
                    if isinstance(v, str):
                        push_pair(k, v)
                    elif isinstance(v, (int, float)):
                        push_pair(k, str(v))
                    else:
                        from_string(str(k))
            else:
                from_string(str(item))
    elif isinstance(caps_raw, dict):
        for k, v in caps_raw.items():
            if isinstance(v, list):
                for x in v:
                    if isinstance(x, str):
                        from_string(f"{k} {x}")
                    else:
                        push_pair(k, str(x))
            elif isinstance(v, str):
                from_string(f"{k} {v}")
            else:
                push_pair(k, str(v))
    elif caps_raw is not None:
        from_string(str(caps_raw))

    # defaults : set missing numeric caps to 0
    for cap in _NUMERIC_CAP_KEYS:
        numeric.setdefault(cap, 0)

    # Build the "other caps" string
    other_caps = ", ".join(dict.fromkeys([o for o in others if o]))

    # Inject the weird "-1" entry if other_caps not empty
    if other_caps:
        numeric[other_caps] = -1

    return numeric, other_caps

# ---------------- Transform core → Pokesheets ----------------

def transform_entry(src: Dict[str, Any], abilities_db: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    species_src = to_str(src.get("Species")) or "Unknown"
    species_out = f"{species_src} Homebrew"  # append " Updated" as requested

    number = to_str(src.get("Number"))
    basic_info = src.get("Basic Information") or {}
    types = [t for t in (basic_info.get("Type") or []) if isinstance(t, str)]

    # Image URL
    image_info = src.get("Icon") or src.get("Number")
    image_url = "https://sewef.github.io/ptu/img/pokemon/icons/{}.png".format(str(image_info)) if image_info else None

    # Stats
    base_stats = base_stats_to_pokesheets(src.get("Base Stats") or {})

    # Other info
    other_info = src.get("Other Information") or {}
    genders = to_str(other_info.get("Genders"))
    malePct, femalePct, isGenderless = parse_percentages(genders)

    # --- TEMP: enforce 50/50 when gendered and missing ---
    if isGenderless:
        malePct = None
        femalePct = None
    else:
        if malePct is None and femalePct is None:
            malePct = 50.0
            femalePct = 50.0
            # log(f"[fix] {species_src}: gender split missing → forced 50/50")
        elif malePct is None and femalePct is not None:
            malePct = max(0.0, min(100.0, 100.0 - femalePct))
            log(f"[fix] {species_src}: male% computed as 100 - female% = {malePct:.1f}")
        elif femalePct is None and malePct is not None:
            femalePct = max(0.0, min(100.0, 100.0 - malePct))
            log(f"[fix] {species_src}: female% computed as 100 - male% = {femalePct:.1f}")

    size, weight = extract_size_weight(other_info)
    egg_groups = split_csv_like(to_str(other_info.get("Egg Groups")))
    habitats = split_csv_like(to_str(other_info.get("Habitat")))
    diets = split_csv_like(to_str(other_info.get("Diet")))

    # Abilities (avec lookup enrichi + logs si non trouvé)
    basic_abl_objs, adv_abl_objs, high_abl_objs, basic_names, adv_names, high_names = map_abilities(basic_info, abilities_db, species_src)

    # Evolution (stage + min level si présent sur la ligne de l'espèce)
    evolution = src.get("Evolution") or []
    this_norm = species_src.strip().lower()
    evolution_stage = 1
    evolution_min_level = None
    for row in evolution:
        if not isinstance(row, dict):
            continue
        if (row.get("Species") or "").strip().lower() == this_norm:
            try:
                evolution_stage = int(row.get("Stade"))
            except Exception:
                evolution_stage = 1
            evomin = to_str(row.get("Minimum Level"))
            if evomin:
                m = re.search(r"(\d+)", evomin)
                if m:
                    evolution_min_level = int(m.group(1))
            break

    # Moves
    moves_block = src.get("Moves") or {}
    level_up_moves = map_level_up_moves(moves_block.get("Level Up Move List") or [])
    machine_moves, egg_moves, tutor_moves = collect_tm_egg_tutor_moves(moves_block)

    # Skills (fill missing with 1d6+0)
    skills_src = src.get("Skills") or {}
    skills_out = {}
    # normalisation des noms source vers clés cible
    alias = {
        "Athletics":"athletics","Acrobatics":"acrobatics","Combat":"combat",
        "Stealth":"stealth","Perception":"perception","Focus":"focus",
        "Charm":"charm","Command":"command","Guile":"guile","Intimidate":"intimidate",
        "Intuition":"intuition","Survival":"survival",
        "General Education":"generalEdu","Medicine Education":"medicineEdu",
        "Occult Education":"occultEdu","Pokémon Education":"pokemonEdu","Pokemon Education":"pokemonEdu",
        "Technology Education":"techEdu",
    }
    for k_src, v in skills_src.items():
        k = alias.get(k_src, None)
        if not k:
            k2 = k_src.strip().lower().replace(" ", "").replace("é","e").replace("É","E")
            for candidate in _SKILL_KEYS:
                if candidate.lower().replace(" ", "") == k2:
                    k = candidate; break
        if k:
            skills_out[k] = to_str(v) or _DEFAULT_SKILL_VAL
    for key in _SKILL_KEYS:
        if key not in skills_out:
            skills_out[key] = _DEFAULT_SKILL_VAL

    # Capabilities reformat
    caps_raw = src.get("Capabilities")
    capabilities, other_caps = parse_capabilities_block(caps_raw)

    # --------- REQUIRED FIELDS SAFEGUARDS + LOGS ---------
    # types
    if not types:
        types = ["Normal"]
        # log(f"[fix] {species_src}: missing types → set to ['Normal']")

    # abilityLearnset.basicAbilities
    if not basic_abl_objs:
        basic_abl_objs = [{
            "name": "None",
            "effect": None,
            "trigger": None,
            "target": None,
            "frequency": None
        }]
        if not basic_names:
            basic_names = ["None"]
        # log(f"[fix] {species_src}: missing basicAbilities → injected placeholder")

    # levelUpMoves
    if not level_up_moves:
        level_up_moves = [{"moveName": "—", "learnedLevel": 1}]
        log(f"[fix] {species_src}: missing levelUpMoves → injected placeholder")

    out = {
        "pokedexEntryDocumentId": None,
        "pokedexDocumentId": None,
        "species": species_out,
        "form": None,
        "types": types,
        "legendary": False,
        "nationalDexNumber": number if number is not None else None,
        "regionOfOrigin": None,
        "entryText": None,
        "pokeApiId": number if number is not None else None,
        "imageFileUrl": image_url,
        "cryFileUrl": None,
        "baseStats": base_stats,
        "size": size,
        "weight": weight,
        "genderless": bool(parse_percentages(genders)[2]),
        "malePercent": malePct,
        "femalePercent": femalePct,
        "eggGroups": egg_groups,
        "hatchRate": None,
        "habitats": habitats,
        "diets": diets,
        "moveLearnset": {
            "levelUpMoves": level_up_moves,
            "machineMoves": machine_moves,
            "eggMoves": egg_moves,
            "tutorMoves": tutor_moves,
        },
        "abilityLearnset": {
            "basicAbilities": basic_abl_objs,     # objets enrichis depuis abilities.json
            "advancedAbilities": adv_abl_objs,
            "highAbilities": high_abl_objs,
        },
        "skills": skills_out,
        "evolutionFamily": {
            "familyName": None,
            "entries": []
        },
        "evolutionStage": evolution_stage,
        "evolutionsRemainingMale": None,
        "evolutionsRemainingFemale": None,
        "evolutionsRemainingGenderless": None,
        "evolutionMinLevel": evolution_min_level,
        "evolutionAtLevel": None,
        "megaEvolution": None,
        "levelUpMoves": {},  # champ supplémentaire dans l'exemple cible (laisse vide)
        "basicAbilities": basic_names,           # aussi les noms simples, comme dans l’exemple
        "advancedAbilities": adv_names,
        "highAbilities": high_names,
        "capabilities": capabilities,            # inclut numeric caps + la clé string à -1 si other caps
        "otherCapabilities": other_caps or "",
    }
    return out

# ---------------- Loader dossier ----------------

def load_all_species_from_dir(in_dir: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for path in sorted(in_dir.glob("*.json")):
        try:
            data = read_json(path)
        except Exception as e:
            warn(f"failed to read {path}: {e}")
            continue
        if isinstance(data, list):
            out.extend([x for x in data if isinstance(x, dict)])
        elif isinstance(data, dict):
            # {Species: obj}
            if data and all(isinstance(v, dict) for v in data.values()):
                for sp, obj in data.items():
                    if isinstance(obj, dict) and "Species" not in obj:
                        obj = {**obj, "Species": sp}
                    out.append(obj)
            else:
                results = data.get("results")
                if isinstance(results, list):
                    out.extend([x for x in results if isinstance(x, dict)])
        else:
            warn(f"unsupported JSON shape in {path.name}")
    return out

# ---------------- Main ----------------

def main():
    ap = argparse.ArgumentParser(description="Aggregate pokedex JSONs + abilities.json → Pokesheets format (with logs and fallbacks)")
    ap.add_argument("--in-dir", required=True, help="Directory with *.json pokedex files")
    ap.add_argument("--abilities", required=True, help="abilities.json path")
    ap.add_argument("--out", required=True, help="Output JSON path")
    ap.add_argument("--minimize", required=False, help="Minimize output JSON (no pretty print)", action="store_true")
    args = ap.parse_args()

    in_dir = Path(args.in_dir)
    if not in_dir.is_dir():
        raise SystemExit(f"--in-dir not a directory: {in_dir}")

    abilities_db = load_abilities_db(Path(args.abilities))

    src_entries = load_all_species_from_dir(in_dir)
    if not src_entries:
        warn("no species found in directory")

    log(f"[info] transforming {len(src_entries)} species…")
    transformed = [transform_entry(e, abilities_db) for e in src_entries]
    
    out_path = Path(args.out)
    if args.minimize:
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(transformed, f, ensure_ascii=False, separators=(",", ":"))
    else:
        write_json(out_path, transformed)


    log(f"[ok] wrote {args.out} (species: {len(transformed)})")

if __name__ == "__main__":
    main()
