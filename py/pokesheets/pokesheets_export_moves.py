import json, re, sys
from typing import Any, Dict

crit_regex = re.compile(r"Critical Hit on.*?(\d+)\+")

def norm_frequency(freq: str) -> str:
    if not isinstance(freq, str):
        return ""
    return freq.replace("EOT", "EoT")

def parse_accuracy(ac: Any) -> Any:
    if ac is None:
        return ""
    if isinstance(ac, (int, float)):
        return int(ac)
    s = str(ac).strip()
    if s.lower() == "none" or s == "":
        return ""
    try:
        return int(s)
    except ValueError:
        return ""

def parse_damage_base(db: Any, damage_class: str) -> Any:
    if isinstance(damage_class, str) and damage_class.strip().lower() == "status":
        return ""
    if db is None:
        return ""
    m = re.search(r"Damage\s*Base\s*(\d+)", str(db))
    if m:
        return int(m.group(1))
    return ""

def clean_name(name: str) -> str:
    name = name.split("*")[0].strip()
    name = re.sub(r"\s*\[.*?\]\s*$", "", name).strip()
    return name

def coerce_none(v):
    if v is None:
        return ""
    if isinstance(v, str) and v.strip().lower() == "none":
        return ""
    return v

def derive_crits_on(effect_text: str):
    if not effect_text:
        return None
    m = crit_regex.search(effect_text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None

def transform_entry(name: str, src: Dict[str, Any]) -> Dict[str, Any]:
    out = {
        "name": clean_name(name),
        "type": src.get("Type", ""),
        "frequency": norm_frequency(src.get("Frequency", "")),
        "accuracyCheck": parse_accuracy(src.get("AC", "")),
        "damageBase": parse_damage_base(src.get("Damage Base", ""), src.get("Class", "")),
        "damageClass": src.get("Class", ""),
        "range": coerce_none(src.get("Range", "")),
        "effects": coerce_none(src.get("Effect", "")),
        "contestType": src.get("Contest Type", None),
        "contestEffect": src.get("Contest Effect", None),
        "critsOn": None,
    }
    out["critsOn"] = derive_crits_on(out["effects"])
    return out

def main():
    if len(sys.argv) < 3:
        print("Usage: python convert_moves_homebrew_to_movesjson.py <input_homebrew.json> <output_moves.json> [--minimize]")
        sys.exit(1)

    inp_path = sys.argv[1]
    out_path = sys.argv[2]
    minimize = "--minimize" in sys.argv

    with open(inp_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    result = []
    for raw_name, payload in data.items():
        result.append(transform_entry(raw_name, payload or {}))
    result.sort(key=lambda x: x["name"].lower())

    with open(out_path, "w", encoding="utf-8") as f:
        if minimize:
            json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(result, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    main()
