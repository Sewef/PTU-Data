
import re, json, sys, pathlib

try:
    import pdfplumber
except Exception:
    pdfplumber = None

def page_to_columns_text(page, gap_ratio=0.5):
    width = page.width
    split_x = width * gap_ratio
    words = page.extract_words(use_text_flow=True, x_tolerance=1, y_tolerance=1)
    left = [w for w in words if w["x0"] < split_x]
    right = [w for w in words if w["x0"] >= split_x]
    left.sort(key=lambda w: (round(w["top"],1), w["x0"]))
    right.sort(key=lambda w: (round(w["top"],1), w["x0"]))
    def words_to_lines(words):
        lines = []
        cur_y = None
        cur_line = []
        for w in words:
            y = round(w["top"],1)
            if cur_y is None or abs(y - cur_y) <= 2.0:
                cur_line.append(w["text"])
                cur_y = y if cur_y is None else (cur_y + y)/2
            else:
                lines.append(" ".join(cur_line))
                cur_line = [w["text"]]
                cur_y = y
        if cur_line:
            lines.append(" ".join(cur_line))
        return "\n".join(lines)
    return words_to_lines(left), words_to_lines(right)

def read_pdf_pages(path):
    if pdfplumber is None:
        raise RuntimeError("pdfplumber is required but not available in this environment.")
    pages = []
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            l, r = page_to_columns_text(p, 0.5)
            pages.append((l + "\n" + r).strip())
    return pages

def normalize_text(txt: str) -> str:
    txt = re.sub(r"(\w+)-\n(\w+)", r"\1\2", txt)  # fix hyphen linebreaks
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt


def detect_name_on_page(txt: str):
    lines = [l for l in txt.splitlines() if l.strip()]
    # locate Base Stats line index
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
        "EGG MOVE LIST", "TUTOR MOVE LIST", "MEGA EVOLUTION", "TYPE INFORMATION", "CAPABILITY INFORMATION",
        "SKILL INFORMATION", "SIZE INFORMATION:"
    }
    def first_token_all_caps(s):
        parts = s.strip().split()
        if not parts:
            return False
        first = parts[0]
        return len(first) >= 2 and first.upper() == first and first.isalpha()
    # scan upwards up to 20 lines
    for i in range(bs_idx-1, max(-1, bs_idx-25), -1):
        s = lines[i].strip()
        s_norm = re.sub(r"\s+", " ", s).upper()
        if s_norm in forbid:
            continue
        if first_token_all_caps(s):
            return s
    # fallback: first all-capsish at top
    for s in lines[:20]:
        if first_token_all_caps(s):
            return s
    return None


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

def clean_commalist(text):
    # Replace newlines with spaces, split by commas
    items = [x.strip() for x in text.replace("\n", " ").split(",")]
    cleaned = []
    for x in items:
        if not x:
            continue
        # Drop pure page numbers / numeric artifacts
        if re.fullmatch(r"\d{1,4}", x):
            continue
        # Remove trailing lone page numbers
        x = re.sub(r"\s+\d{2,4}$", "", x).strip()
        cleaned.append(x)
    return [x for x in cleaned if x]


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
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("height"):
            height = line.split(":",1)[1].strip()
        elif line.lower().startswith("weight"):
            weight = line.split(":",1)[1].strip()
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
            parts = [p.strip() for p in re.split(r"[/|]", type_line) if p.strip()]
            if parts:
                bi["Type 1"] = parts[0]
                if len(parts) > 1:
                    bi["Type 2"] = parts[1]
        fields = ["Basic Ability 1", "Basic Ability 2", "Adv Ability 1", "Adv Ability 2", "Adv Ability 3", "High Ability"]
        for f in fields:
            m = re.search(rf"^ *{re.escape(f)} *: *(.*)$", basic_info, re.MULTILINE)
            if m:
                bi[f] = m.group(1).strip()

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

    capability_list = split_commas_outside_parens((capability or "").replace("\n"," "))
    skills = parse_skill_list(skill or "") if skill else {}

    lvl_moves = parse_level_up_moves(level_up or "") if level_up else []
    tmhm_moves = clean_commalist(tmhm or "") if tmhm else []
    egg_moves = clean_commalist(egg or "") if egg else []
    tutor_moves = clean_commalist(tutor or "") if tutor else []
    mega_obj = parse_mega(mega)

    return {
        "Name": smart_title(name),
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
    for page_txt in pages:
        txt = normalize_text(page_txt)
        # Detect name: first ALL-CAPS-ish line near top; take whole line (multi-word OK)
        lines = [l for l in txt.splitlines() if l.strip()]
        name_line = detect_name_on_page(txt)
        if not name_line:
            continue
        name_start = txt.find(name_line)
        block = (name_line + "\n" + txt[name_start+len(name_line):]).strip()
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
