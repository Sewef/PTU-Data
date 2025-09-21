
import re, json, sys, pathlib

try:
    import pdfplumber
except Exception:
    pdfplumber = None



def page_to_columns_text_adaptive(page):
    words = page.extract_words(use_text_flow=True, x_tolerance=1, y_tolerance=1)
    if not words:
        return "", ""
    # Simple 2-means on x0 to separate columns
    xs = [w["x0"] for w in words]
    c1, c2 = min(xs), max(xs)
    for _ in range(12):
        g1, g2 = [], []
        for w in words:
            (g1 if abs(w["x0"]-c1) <= abs(w["x0"]-c2) else g2).append(w)
        new_c1 = sum(w["x0"] for w in g1)/len(g1) if g1 else c1
        new_c2 = sum(w["x0"] for w in g2)/len(g2) if g2 else c2
        if abs(new_c1-c1) < 0.5 and abs(new_c2-c2) < 0.5:
            break
        c1, c2 = new_c1, new_c2
    left, right = (g1, g2) if (g1 and g2 and (sum(w["x0"] for w in g1)/len(g1) < sum(w["x0"] for w in g2)/len(g2))) else (g2, g1)
    # Sort and line-merge
    def words_to_lines(ws):
        if not ws: return ""
        ws.sort(key=lambda w: (round(w["top"],2), w["x0"]))
        lines = []
        cur_y, cur = None, []
        for w in ws:
            y = round(w["top"],2)
            if cur_y is None or abs(y-cur_y) <= 2.0:
                cur.append(w["text"])
                cur_y = y if cur_y is None else (cur_y + y)/2
            else:
                lines.append(" ".join(cur))
                cur_y, cur = y, [w["text"]]
        if cur:
            lines.append(" ".join(cur))
        return "\n".join(lines)
    return words_to_lines(left), words_to_lines(right)

def read_pdf_pages(path):
    if pdfplumber is None:
        raise RuntimeError("pdfplumber is required but not available in this environment.")
    pages = []
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            l, r = page_to_columns_text_adaptive(p)
            pages.append({"left": l.strip(), "right": r.strip(), "both": (l + "\\n" + r).strip()})
    return pages

def normalize_text(txt: str) -> str:
    # Fix hyphen linebreaks and normalize whitespace
    txt = re.sub(r"(\w+)-\n(\w+)", r"\1\2", txt)
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    # Drop lines that are just page numbers (1-4 digits)
    txt = "\n".join([ln for ln in txt.splitlines() if not re.fullmatch(r"\s*\d{1,4}\s*", ln)])
    return txt

def get_line_after(label, block):
    m = re.search(label + r"\s*(.*)", block)
    return m.group(1).strip() if m else None

def extract_section(block, header, next_headers):
    start = re.search(header, block)
    if not start:
        return None
    s_idx = start.end()
    sub = block[s_idx:]
    next_positions = []
    for h in next_headers:
        # Accept header whether or not it's on a new line
        mm = re.search(h, sub)
        if mm:
            next_positions.append(mm.start())
    e_idx = s_idx + min(next_positions) if next_positions else len(block)
    return block[s_idx:e_idx].strip()

def split_commas_outside_parens(text: str):
    parts = []
    cur = []
    depth = 0
    for ch in text:
        if ch == '(':
            depth += 1
            cur.append(ch)
        elif ch == ')':
            depth = max(0, depth-1)
            cur.append(ch)
        elif ch == ',' and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur).strip())
    return [p for p in parts if p]
def drop_embedded_pagenums(s: str) -> str:
    # Remove 2-4 digit numbers glued to words: e.g., 'Dark553' -> 'Dark'
    s = re.sub(r'([A-Za-z])\d{2,4}(\b)', r'\1', s)
    # Also remove standalone 2-4 digit numbers
    s = re.sub(r'\b\d{2,4}\b', '', s)
    # Collapse spaces
    s = re.sub(r'\s{2,}', ' ', s).strip()
    return s


def clean_commalist(text):
    items = [x.strip() for x in text.replace("\n", " ").split(",")]
    return [x for x in items if x]

def parse_level_up_moves(text):
    moves = []
    for line in text.splitlines():
        line = line.strip()
        if not line or not re.match(r"^\d+", line):
            continue
        m = re.match(r"^(\d+)\s+(.+?)(?:\s*-\s*[A-Za-z\. ]+)?\s*$", line)
        if m:
            lvl = m.group(1)
            name = m.group(2).strip()
            moves.append({"Level": lvl, "Move": name})
    return moves

def parse_skill_list(text):
    skills = {}
    for item in clean_commalist(text):
        m = re.match(r"^([A-Za-z:]+)\s+([\dd\+\-]+)$", item)
        if m:
            skills[m.group(1).strip()] = m.group(2).strip()
    return skills

def parse_evolution(text):
    evos = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        m = re.match(r"^\d+\s*-\s*(.+)$", s)
        if m:
            evos.append(m.group(1).strip())
    return evos

def parse_height_weight(text):
    height = None
    weight = None
    # Accept formats like: 3’ 7” / 1.1m (Medium)
    mh = re.search(r'(?i)height\\s*:\\s*([0-9\'’ \\./m\\(\\)A-Za-z]+)', text)
    if mh:
        height = mh.group(1).strip()
        # cut at first lowercase-to-uppercase transition typical of move names (very heuristic)
        height = re.split(r'\\b[A-Z][a-z]+\\b', height)[0].strip()
    mw = re.search(r'(?i)weight\\s*:\\s*([0-9\\. ]+\\s*(?:lbs\\.|kg)\\s*/\\s*[0-9\\.]+\\s*(?:kg|lbs\\.)\\s*\\([0-9]+\\))', text)
    if mw:
        weight = mw.group(1).strip()
    return {"Height": height, "Weight": weight}

def parse_gender_ratio(s):
    if not s:
        return {"Male": None, "Female": None}
    s = s.strip()
    if re.search(r"no gender", s, re.IGNORECASE):
        return {"Male": "0%", "Female": "0%"}
    m = re.search(r"([\d\.]+%)\s*M\s*/\s*([\d\.]+%)\s*F", s, re.IGNORECASE)
    if m:
        return {"Male": m.group(1), "Female": m.group(2)}
    return {"Male": None, "Female": None}

def parse_mega(text):
    if text is None:
        return None
    type_line = None
    ability_line = None
    stats_line = None
    for line in text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip().lower()
            v = v.strip()
            if k == "type":
                type_line = v
            elif k == "ability":
                ability_line = v
            elif k.startswith("stats"):
                stats_line = v
    res = {}
    if type_line: res["Type"] = type_line
    if ability_line: res["Ability"] = ability_line
    if stats_line:
        bonuses = {}
        for part in stats_line.split(","):
            part = part.strip()
            m = re.match(r"([+\-]?\d+)\s*(.+)$", part)
            if m:
                bonuses[m.group(2).strip()] = int(m.group(1))
        res["StatBonuses"] = bonuses
    return res if res else None

def smart_title(s):
    parts = s.split()
    out = []
    for w in parts:
        if len(w) <= 4 and w.isupper():
            out.append(w)
        else:
            out.append(w.title())
    return " ".join(out)




def finalize_name(name: str) -> str:
    s = name.replace("\n", " ").strip()
    # Keep full name; cut at the first comma to avoid capability list leakage
    s = s.split(",", 1)[0].strip()
    # Remove backslash-letter artifacts like \N, \n
    s = re.sub(r"\\[A-Za-z]", " ", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    # If the second token looks like a Capability keyword, keep only the first token
    capability_heads = {
        "Overland","Swim","Levitate","Jump","Power","Phasing","Darkvision","Invisibility",
        "Glow","Underdog","Wired","Zapper","Naturewalk","Telepathy","Burrow","Mountable"
    }
    parts = s.split()
    if len(parts) >= 2:
        second = parts[1].strip("()[]{}.:;!,")
        if second in capability_heads:
            return parts[0]
    return s


def clean_detected_name(raw: str) -> str:
    # Cut at first comma if any (capability lists often have commas)
    s = raw.split(",", 1)[0].strip()
    # Tokens after the first ALL-CAPS token that we allow in names (forms, regions, etc.)
    allowed = {
        "Normal","Form","Forms","Appliance","Mega","Primal","Alolan","Galarian","Hisuian","Paldean",
        "Therian","Origin","Sky","Land","Incarnate","Black","White","Red","Blue","Yellow","Green",
        "Orange","Frost","Wash","Heat","Fan","Mow"
    , "Confined","Unbound","Unbounded","Forme"}
    parts = s.split()
    if not parts:
        return s
    head = parts[0]
    tail = []
    for t in parts[1:]:
        t_clean = t.strip("()[]{}.:;!-_'\"")
        if t_clean in allowed or t_clean.upper() == t_clean and len(t_clean) <= 5:
            tail.append(t_clean)
        else:
            # stop at first unknown token (prevents 'Phasing' etc.)
            break
    name = " ".join([head] + tail)
    return name.strip()
def detect_name_from_left(left_txt: str):
    lines = [l for l in left_txt.splitlines() if l.strip()]
    bs_idx = None
    for i, l in enumerate(lines):
        if "Base Stats:" in l:
            bs_idx = i
            break
    if bs_idx is None:
        return None
    forbid = {
        "BASE STATS:", "BASIC INFORMATION", "SIZE INFORMATION", "BREEDING INFORMATION",
        "CAPABILITY LIST", "SKILL LIST", "MOVE LIST", "LEVEL UP MOVE LIST", "TM/HM MOVE LIST",
        "EGG MOVE LIST", "TUTOR MOVE LIST", "MEGA EVOLUTION", "DIET :", "HABITAT :"
    }
    def first_token_is_caps(s: str) -> bool:
        tok = s.strip().split()[0]
        if not re.search(r"[A-Z]", tok):
            return False
        return tok == tok.upper()
    for i in range(bs_idx-1, max(-1, bs_idx-25), -1):
        s = lines[i].strip()
        s_norm = re.sub(r"\s+", " ", s).upper()
        if s_norm in forbid:
            continue
        if first_token_is_caps(s):
            return clean_detected_name(s)
    for s in lines[:20]:
        ss = s.strip()
        if first_token_is_caps(ss):
            return clean_detected_name(ss)
    return None

POKEMON_TYPES = {"Normal","Fire","Water","Grass","Electric","Ice","Fighting","Poison","Ground","Flying","Psychic","Bug","Rock","Ghost","Dragon","Dark","Steel","Fairy"}

def parse_entry(block: str):
    lines = [l for l in block.splitlines() if l.strip()]
    name = lines[0].strip()
    content = "\n".join(lines[1:])

    base_stats = extract_section(content, r"Base Stats:", [r"\n\s*Basic Information", r"\n\s*Size Information", r"\n\s*Breeding Information", r"\n\s*Diet", r"\n\s*Capability List", r"\n\s*Skill List", r"\n\s*Move List", r"\n\s*Level Up Move List", r"\n\s*Base Stats:"])
    basic_info = extract_section(content, r"Basic Information", [r"\n\s*Evolution:", r"\n\s*Size Information", r"\n\s*Breeding Information", r"\n\s*Diet", r"\n\s*Capability List", r"\n\s*Skill List", r"\n\s*Move List", r"\n\s*Level Up Move List", r"\n\s*Base Stats:"])
    evolution = extract_section(content, r"Evolution:", [r"\n\s*Size Information", r"\n\s*Breeding Information", r"\n\s*Diet", r"\n\s*Capability List", r"\n\s*Skill List", r"\n\s*Move List", r"\n\s*Level Up Move List", r"\n\s*Base Stats:"])
    size_info = extract_section(content, r"Size Information", [r"\n\s*Breeding Information", r"\n\s*Diet", r"\n\s*Capability List", r"\n\s*Skill List", r"\n\s*Move List", r"\n\s*Level Up Move List", r"\n\s*Base Stats:"])
    breeding_info = extract_section(content, r"Breeding Information", [r"\n\s*Diet", r"\n\s*Habitat", r"\n\s*Capability List", r"\n\s*Skill List", r"\n\s*Move List", r"\n\s*Level Up Move List", r"\n\s*Base Stats:"])
    diet_line = re.search(r"^ *Diet *: *(.*)$", content, re.MULTILINE)
    habitat_line = re.search(r"^ *Habitat *: *(.*)$", content, re.MULTILINE)

    capability = extract_section(content, r"Capability List", [r"\n\s*Skill List", r"\n\s*Move List", r"\n\s*Level Up Move List", r"\n\s*Base Stats:"])

    if capability:
        # remove everything after any of these markers (even if glued on same line)
        for marker in ["Skill List", "Move List", "Level Up Move List", "TM/HM Move List", "Egg Move List", "Tutor Move List", "Mega Evolution", "Base Stats:"]:
            idx = capability.find(marker)
            if idx != -1:
                capability = capability[:idx].rstrip()

    skill = extract_section(content, r"Skill List", [r"\n\s*Move List", r"\n\s*Level Up Move List", r"\n\s*Base Stats:"])

    level_up = extract_section(content, r"Level Up Move List", [r"\n\s*TM/HM Move List", r"\n\s*Egg Move List", r"\n\s*Tutor Move List", r"\n\s*Mega Evolution", r"\n\s*Base Stats:"])
    tmhm = extract_section(content, r"TM/HM Move List", [r"\n\s*Egg Move List", r"\n\s*Tutor Move List", r"\n\s*Mega Evolution", r"\n\s*Base Stats:"])
    egg = extract_section(content, r"Egg Move List", [r"\n\s*Tutor Move List", r"\n\s*Mega Evolution", r"\n\s*TM/HM Move List", r"\n\s*Base Stats:"])
    tutor = extract_section(content, r"Tutor Move List", [r"\n\s*Mega Evolution", r"\n\s*Egg Move List", r"\n\s*TM/HM Move List", r"\n\s*Base Stats:"])
    mega = extract_section(content, r"Mega Evolution", [r"\n[A-Z0-9' \-\u2019\u00C0-\u017F]+\n", r"$"])

    # Base stats
    bs = {}
    if base_stats:
        for line in base_stats.splitlines():
            line = line.strip()
            m = re.match(r"([A-Za-z ]+):\s*([0-9]+)", line)
            if m:
                bs[m.group(1).strip()] = int(m.group(2))

    bi = {}
    if basic_info:
        type_line_m = re.search(r"^ *Type *: *(.*)$", basic_info, re.MULTILINE)
        type_line = type_line_m.group(1).strip() if type_line_m else None
        if type_line:
            type_line = re.sub(r",[\s\S]*$", "", type_line).strip()
            parts_raw = [p.strip() for p in re.split(r"[/|]", type_line) if p.strip()]
            parts = []
            for pr in parts_raw:
                cand = pr.split()[0]
                if cand in POKEMON_TYPES:
                    parts.append(cand)
            
            if parts:
                bi["Type 1"] = parts[0]
                if len(parts) > 1:
                    bi["Type 2"] = parts[1]
        fields = ["Basic Ability 1", "Basic Ability 2", "Adv Ability 1", "Adv Ability 2", "Adv Ability 3", "High Ability"]
        for f in fields:
            m = re.search(rf"^ *{re.escape(f)} *: *(.*)$", basic_info, re.MULTILINE)
            if m:
                bi[f] = re.split(r"\b\d{1,3}\b", re.sub(r",[\s\S]*$", "", m.group(1)).strip())[0].strip()

    evo = parse_evolution(evolution or "") if evolution else []
    size = parse_height_weight(size_info or "") if size_info else {}

    breed = {}
    if breeding_info:
        grm = re.search(r"^ *Gender Ratio *: *(.*)$", breeding_info, re.MULTILINE)
        gr = grm.group(1).strip() if grm else None
        breed["Gender Ratio"] = parse_gender_ratio(gr)
        egm = re.search(r"^ *Egg Group *: *(.*)$", breeding_info, re.MULTILINE)
        if egm:
            breed["Egg Group"] = [x.strip() for x in egm.group(1).split("/")]
        ahm = re.search(r"^ *Average Hatch Rate *: *(.*)$", breeding_info, re.MULTILINE)
        if ahm:
            breed["Average Hatch Rate"] = ahm.group(1).strip()

    capability_list = [re.sub(r"^\d{1,4}\s+","", x.replace("\\n"," ")).strip() for x in split_commas_outside_parens((capability or "").replace("\n"," ").replace("\\n"," ")) if x.strip()]
    skills = parse_skill_list(skill or "") if skill else {}

    lvl_moves = parse_level_up_moves(level_up or "") if level_up else []
    tmhm_moves = [re.sub(r"\s+\d{1,4}$","", m).strip() for m in (clean_commalist(tmhm or "") if tmhm else [])]
    egg_moves = [re.sub(r"\s+\d{1,4}$","", m).strip() for m in (clean_commalist(egg or "") if egg else [])]
    tutor_moves = [re.sub(r"\s+\d{1,4}$","", m).strip() for m in (clean_commalist(tutor or "") if tutor else [])]
    mega_obj = parse_mega(mega)

    return {
        "Name": smart_title(finalize_name(name)),
        "Base Stats": bs,
        "Basic Information": bi,
        "Evolution": evo,
        "Size Information": size,
        "Breeding Information": breed,
        "Diet": split_commas_outside_parens(diet_line.group(1)) if diet_line else [],
        "Habitat": split_commas_outside_parens(habitat_line.group(1)) if habitat_line else [],
        "Capability List": capability_list,
        "Skill List": skills,
        "Moves": {
            "Level Up": lvl_moves,
            "TMHM": tmhm_moves,
            "Egg": egg_moves,
            "Tutor": tutor_moves,
        },
        "Mega Evolution": mega_obj,
    }

def parse_pokedex(path):
    pages = read_pdf_pages(path)
    parsed = []
    for page in pages:
        left = normalize_text(page["left"])
        both = normalize_text(page["both"])
        name_line = detect_name_from_left(left) if 'detect_name_from_left' in globals() else detect_name_on_page(left)
        if not name_line:
            continue
        # Build block for this page only
        name_start = both.find(name_line)
        if name_start == -1:
            # fallback: just use both (rare)
            block = (name_line + "\\n" + both).strip()
        else:
            block = (name_line + "\\n" + both[name_start+len(name_line):]).strip()
        try:
            parsed.append(parse_entry(block))
        except Exception as e:
            parsed.append({"Name": smart_title(name_line), "error": str(e)})
    return parsed

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Parse a Pokedex PDF into JSON.")
    ap.add_argument("pdf", help="Path to the Pokedex PDF")
    ap.add_argument("-o", "--output", help="Output JSON path (defaults to same folder with .json)")
    args = ap.parse_args()
    data = parse_pokedex(args.pdf)
    out_path = pathlib.Path(args.output) if args.output else pathlib.Path(args.pdf).with_suffix(".json")
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path} with {len(data)} entries.")

if __name__ == "__main__":
    main()
