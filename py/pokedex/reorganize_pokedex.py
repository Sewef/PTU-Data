
import json, sys, re
from collections import OrderedDict

def as_list(val):
    if val is None:
        return []
    if isinstance(val, list):
        return [v for v in val if v is not None and f"{v}".strip() != ""]
    s = f"{val}".strip()
    if not s:
        return []
    parts = [p.strip() for p in re.split(r',|\s+/\s+', s) if p and p.strip()]
    return parts or [s]

def collect_abilities(basic_info: dict):
    abilities = []
    if not isinstance(basic_info, dict):
        return abilities
    for k, v in basic_info.items():
        if re.search(r'ability', k, flags=re.I):
            abilities.extend(as_list(v))
    seen = set()
    uniq = []
    for a in abilities:
        if a not in seen:
            seen.add(a)
            uniq.append(a)
    return uniq

def normalize_type(t):
    parts = as_list(t)
    return [p.strip() for p in parts if p.strip()]

def make_other_info(record):
    other = OrderedDict()
    # Size Information (top-level ou Basic Information)
    sz = record.get("Size Information") or (record.get("Basic Information", {}) or {}).get("Size Information") or {}
    if isinstance(sz, dict) and any(v for v in [sz.get("Height"), sz.get("Weight")]):
        other["Size Information"] = {k: v for k, v in sz.items() if v}

    # Genders (cherche directement dans Breeding ou Basic Information)
    br = record.get("Breeding Information") or {}
    bi = record.get("Basic Information") or {}
    genders = br.get("Genders") or br.get("Gender") or bi.get("Genders") or bi.get("Gender") or record.get("Genders") or bi.get("Gender Ratio") or record.get("Gender Ratio")
    if genders:
        genders = str(genders).strip()
        # Corrige le format "M / F"
        genders = re.sub(
            r'^(.*)\s*(?:M|Male)\s*/\s*(.*)\s*(?:F|Female)$',
            r'\1 Male / \2 Female',
            genders
        )
        # Corrige le format collé "Male Female" → "Male / Female"
        genders = re.sub(
            r'(\d+\.?\d*%?\s*Male)\s+(\d+\.?\d*%?\s*Female)',
            r'\1 / \2',
            genders
        )
        other["Genders"] = genders

    # Diet / Habitat
    if record.get("Diet"):
        other["Diet"] = f'{record.get("Diet")}'.strip()
    if record.get("Habitat"):
        other["Habitat"] = f'{record.get("Habitat")}'.strip()

    # Egg Groups
    egg = br.get("Egg Groups") or br.get("Egg Group")
    if egg:
        if isinstance(egg, list):
            egg_text = ", ".join(f"{e}".strip() for e in egg if e)
        else:
            egg_text = f"{egg}".strip()
        other["Egg Groups"] = egg_text

    return other


def reorganize_entry(rec):
    out = OrderedDict()
    if rec.get("Species"):
        out["Species"] = rec["Species"]

    if rec.get("Number"):
        out["Number"] = rec["Number"]
        
    if rec.get("Base Stats"):
        out["Base Stats"] = rec["Base Stats"]

    # Basic Information: Type + tous les champs Ability
    bi_src = rec.get("Basic Information") or {}
    basic = OrderedDict()
    if isinstance(bi_src, dict):
        if "Type" in bi_src and bi_src["Type"]:
            basic["Type"] = as_list(bi_src["Type"])
        for k, v in bi_src.items():
            if re.search(r'ability', k, flags=re.I):
                basic[k] = v if isinstance(v, str) or not isinstance(v, list) else v
    out["Basic Information"] = basic

    # Evolution
    if rec.get("Evolution") is not None:
        out["Evolution"] = rec["Evolution"]

    # Other Information
    other = make_other_info(rec)
    out["Other Information"] = other

    # Ajouter les champs restants
    consumed = set(["Species", "Number", "Basic Information", "Evolution", "Other Information",
                    "Size Information", "Breeding Information", "Diet", "Habitat"])
    for k, v in rec.items():
        if k in consumed:
            continue
        out[k] = v
    return out


def main(inp, outp):
    with open(inp, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        reorganized = reorganize_entry(data)
    else:
        reorganized = [reorganize_entry(r) for r in data]
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(reorganized, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    inp = sys.argv[1]
    outp = sys.argv[1]
    main(inp, outp)
