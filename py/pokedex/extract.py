
import json, re, logging
from pathlib import Path
import PyPDF2

DEBUG_KEEP_RAW = False

def split_commas_outside_parens(text: str):
    """Split a string on commas, but ignore commas inside parentheses.
    Returns a list of trimmed parts."""
    parts = []
    buf = []
    level = 0
    for ch in text:
        if ch == '(':
            level += 1
            buf.append(ch)
        elif ch == ')':
            level = max(0, level - 1)
            buf.append(ch)
        elif ch == ',' and level == 0:
            part = ''.join(buf).strip()
            if part:
                parts.append(part)
            buf = []
        else:
            buf.append(ch)
    last = ''.join(buf).strip()
    if last:
        parts.append(last)
    return parts


PDF_PATH = "8G HisuiDex.pdf"
OUT_JSON = "../../ptu/data/pokedex/pokedex_8g_hisui.json"
OUT_LOG = "pokedex_extraction.log"

# --- Logging setup ---
logger = logging.getLogger("pokedex-extract")
logger.setLevel(logging.INFO)
# Console handler
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(logging.Formatter("%(levelname)s:%(message)s"))
logger.addHandler(ch)
# File handler
fh = logging.FileHandler(OUT_LOG, mode="w", encoding="utf-8")
fh.setLevel(logging.INFO)
fh.setFormatter(logging.Formatter("%(levelname)s:%(message)s"))
logger.addHandler(fh)

def clean_line(s: str) -> str:
    s = s.replace('\xa0', ' ').replace('‒', '-').replace('–', '-').replace('—', '-').replace(' )', ')')
    s = re.sub(r'[ \t]+', ' ', s)
    return s.strip()

def is_all_caps_title(line: str) -> bool:
    l = line.strip()
    if not l: return False
    if l.upper() in {"POKÉDEX", "POKEDEX", "HOW TO READ: POKEDEX ENTRIES", "CONTENTS"}:
        return False
    letters = re.sub(r'[^A-Za-z]', '', l)
    return len(letters) >= 3 and letters.isupper()

def fix_species_spacing(name: str) -> str:
    # Exemple: "HOOP A Confined" -> "HOOPA Confined"
    # On corrige uniquement les majuscules séparées par un espace
    return re.sub(r'\b([A-Z]{2,})\s+([A-Z]{1,})(\b| )', lambda m: m.group(1) + m.group(2) + m.group(3), name)

def compare_string_with_spaces(s: str, c: str):
    return (s.replace(' ', '')).startswith(c.replace(' ', ''))

def fallback_title(lines):
    # Try to pull an UPPERCASE species token even if the line contains "Normal Form", numbers, etc.
    for l in lines[:40]:
        if not l:
            continue
        # Case 1: Line begins with page number then species (e.g., "607ROTOM Normal Form")
        m = re.match(r'^\s*\d+\s*([A-Z][A-Z \-\'\.]+)\b', l)
        if m:
            token = m.group(1).strip()
            if token and token not in {"BASE STATS", "BASIC INFORMATION"}:
                return fix_species_spacing(l)  # Return the whole line instead of just the token
        # Case 2: Find the longest ALL-CAPS token in the line
        caps = re.findall(r'([A-Z]{3,}(?:[ \-][A-Z]{3,})*)', l)
        if caps:
            caps.sort(key=len, reverse=True)
            token = caps[0].strip()
            if token and token not in {"BASE STATS", "BASIC INFORMATION"}:
                return fix_species_spacing(l)  # Return the whole line instead of just the token
        # Case 3: Capitalized species name alone
        if re.match(r'^[A-Z][a-z]+(?:[ \-][A-Za-z]+){0,3}$', l):
            return fix_species_spacing(l)
    return None

def parse_key_value_block(lines, start_idx, end_idx=None):
    data = {}
    i = start_idx
    end_idx = end_idx if end_idx is not None else len(lines)
    while i < end_idx:
        line = lines[i]
        m = re.match(r'(?i)^([A-Za-z ][A-Za-z 0-9/()+\'.-]*?)\s*:\s*(.*)$', line)
        if m:
            key = clean_line(m.group(1))
            val = clean_line(m.group(2))
            data[key] = val
        i += 1
    return data


def parse_moves_list(lines, start_idx):
    def compact_contains(haystack: str, needle: str) -> bool:
        return needle.replace(' ', '').lower() in haystack.replace(' ', '').lower()

    sections = {
        "Level Up Move List": [],
        "TM/HM Move List": [],
        "Egg Move List": [],
        "Tutor Move List": [],
    }
    current = None
    i = start_idx
    while i < len(lines):
        line = lines[i]
        nxt = lines[i+1] if i+1 < len(lines) else ""

        # Stop si on voit "Mega Evolution" (même en plein milieu de ligne)
        if compact_contains(line, "Mega Evolution") or (line == "Mega" and nxt == "Evolution"):
            logger.debug(f"[Moves] Stopped at Mega Evolution (inline or split): {line} | {nxt}")
            break

        # Sauter "Move List" nu (ligne de titre)
        if compare_string_with_spaces(line, "Move List"):
            i += 1
            continue

        # Têtes de sous-sections (tolérant aux espaces / césures)
        if compare_string_with_spaces(line, "Level Up Move List") or (line == "Level Up" and nxt == "Move List"):
            current = "Level Up Move List"
            i += 2 if (line == "Level Up" and nxt == "Move List") else 1
            continue

        if compare_string_with_spaces(line, "TM/HM Move List") or (line == "TM/HM" and nxt == "Move List"):
            current = "TM/HM Move List"
            i += 2 if (line == "TM/HM" and nxt == "Move List") else 1
            continue

        if compare_string_with_spaces(line, "Egg Move List") or (line == "Egg" and nxt == "Move List"):
            current = "Egg Move List"
            i += 2 if (line == "Egg" and nxt == "Move List") else 1
            continue

        if compare_string_with_spaces(line, "Tutor Move List") or (line == "Tutor" and nxt == "Move List"):
            current = "Tutor Move List"
            i += 2 if (line == "Tutor" and nxt == "Move List") else 1
            continue

        # Stop si on arrive à une autre grande section
        if any(compare_string_with_spaces(line, h) for h in [
            "Base Stats:", "Basic Information", "Evolution:", "Size Information",
            "Breeding Information", "Diet", "Habitat", "Capability List",
            "Skill List", "Mega Evolution"
        ]):
            break

        if current:
            sections[current].append(line)
        i += 1

    def parse_levelup(block_lines):
        entries = []
        for ln in block_lines:
            m = re.match(r'^\s*(\d+)\s+(.+?)\s*-\s*([A-Za-z]+)\s*$', ln)
            if m:
                entries.append({"Level": int(m.group(1)),
                                "Move": clean_line(m.group(2)),
                                "Type": clean_line(m.group(3))})
        return entries

    def parse_comma_or_list(block_lines):
        text = ' '.join(block_lines)
        text = re.sub(r'(\w)\s*-\s+(\w)', r'\1\2', text)
        text = re.sub(r'\s+', ' ', text).strip()
        parts = [clean_line(p) for p in text.split(',')]
        return [p for p in parts if p]

    if DEBUG_KEEP_RAW:
        return {
            "Level Up Move List": parse_levelup(sections["Level Up Move List"]),
            "TM/HM Move List": parse_comma_or_list(sections["TM/HM Move List"]),
            "Egg Move List": parse_comma_or_list(sections["Egg Move List"]),
            "Tutor Move List": parse_comma_or_list(sections["Tutor Move List"]),
            "_raw": sections
        }
    return {
        "Level Up Move List": parse_levelup(sections["Level Up Move List"]),
        "TM/HM Move List": parse_comma_or_list(sections["TM/HM Move List"]),
        "Egg Move List": parse_comma_or_list(sections["Egg Move List"]),
        "Tutor Move List": parse_comma_or_list(sections["Tutor Move List"])
    }

def extract_page(page_text: str, page_index: int):
    lines = [clean_line(l) for l in (page_text or "").splitlines()]

    # --- Dirty fix: some Capability List are wrongly formatted ---
    KNOWN_HEADERS = [
        "Base Stats", "Basic Information", "Evolution", "Size Information",
        "Breeding Information", "Diet", "Habitat", "Capability List", "Skill List",
        "Move List", "Level Up Move List", "TM/HM Move List",
        "Egg Move List", "Tutor Move List", "Mega Evolution"
    ]

    def compact(s: str) -> str:
        return (s or "").replace(' ', '').lower()

    fixed_lines = []
    skip_next = False
    # Normalize wrapped headers like 'Level Up' '\n' 'Move List' -> 'Level Up Move List'
    j = 0
    while j < len(lines):
        if skip_next:
            skip_next = False
            j += 1
            continue
        cur = lines[j]
        nxt = lines[j+1] if j+1 < len(lines) else ""
        if cur == "Level Up" and nxt == "Move List":
            fixed_lines.append("Level Up Move List")
            skip_next = True
        elif cur == "Tutor" and nxt == "Move List":
            fixed_lines.append("Tutor Move List")
            skip_next = True
        elif cur == "TM/HM" and nxt == "Move List":
            fixed_lines.append("TM/HM Move List")
            skip_next = True
        elif cur == "Egg" and nxt == "Move List":
            fixed_lines.append("Egg Move List")
            skip_next = True
        elif cur == "Mega" and nxt == "Evolution":
            fixed_lines.append("Mega Evolution")
            skip_next = True
        else:
            fixed_lines.append(cur)
        j += 1

    # Continue with subsequent header splitting fixes using fixed_lines as base
    lines = fixed_lines
    fixed_lines = []
    for i, l in enumerate(lines):
        if skip_next:
            skip_next = False
            continue

        # --- Recoller les mots coupés en fin de ligne ---
        if l.endswith('-') and i + 1 < len(lines):
            merged = l[:-1].rstrip() + lines[i + 1].lstrip()
            logger.debug(f"[Page {page_index}] Recollé '{l}' + '{lines[i+1]}' -> '{merged}'")
            l = merged
            skip_next = True

        # --- Découper les headers collés sur la même ligne ---
        found = []
        for h in KNOWN_HEADERS:
            pos = l.find(h)
            if pos > 0:
                found.append((pos, h))
        if found:
            found.sort()
            start = 0
            for pos, h in found:
                before = l[start:pos].strip()
                if before:
                    fixed_lines.append(before)
                fixed_lines.append(h)
                start = pos + len(h)
            rest = l[start:].strip()
            if rest:
                fixed_lines.append(rest)
        else:
            fixed_lines.append(l)

    lines = fixed_lines
    fixed_lines = []
    for l in lines:
        # Cas spécial : "Capability List" + contenu collés
        if compare_string_with_spaces(l, "Capability List "):
            fixed_lines.append("Capability List")
            fixed_lines.append(l[len("Capability List "):].strip())
        else:
            fixed_lines.append(l)

    lines = fixed_lines

    if DEBUG_KEEP_RAW:
        record = {"_page_index": page_index, "_raw_text": page_text}
    else:
        record = {}

    # Species title
    species = None
    for l in lines[:40]:
        if is_all_caps_title(l):
            species = l
            break
    if not species:
        species = fallback_title(lines)
        if species:
            logger.debug(f"[p{page_index}] Fallback title used: {species}")

    if species:
        species = re.sub(r'^\s*\d+\s*', '', species)
        species = fix_species_spacing(species)
        species = re.sub(r'(^[A-Z])\s([A-Z])(.*)$', lambda m: m[1] + m[2].lower() + m[3], species)
        species = species.title()
    record["Species"] = species

    # --- Helpers basés sur compare_string_with_spaces ---
    def index_of(header: str) -> int:
        for i, l in enumerate(lines):
            if compare_string_with_spaces(l, header):
                return i
        return -1

    def contains_token(i: int, token: str) -> bool:
        return token.replace(' ', '').lower() in lines[i].replace(' ', '').lower()

    # Indices des sections (d’abord via compare_string_with_spaces, avec fallback regex si besoin)
    idx_base  = index_of("Base Stats")
    if idx_base == -1:
        idx_base = next((i for i,l in enumerate(lines) if re.search(r'(?i)^Base Stats:?', l)), -1)

    idx_basic = index_of("Basic Information")
    idx_evo   = index_of("Evolution:")
    if idx_evo == -1:
        idx_evo = next((i for i,l in enumerate(lines) if re.search(r'(?i)^Evolution:', l)), -1)

    idx_size  = index_of("Size Information")
    idx_breed = index_of("Breeding Information")
    idx_diet  = index_of("Diet")
    idx_hab   = index_of("Habitat")
    idx_cap   = index_of("Capability List")
    if idx_cap == -1:
        idx_cap = next((i for i,l in enumerate(lines) if re.search(r'(?i)Capability.*List', l)), -1)

    idx_skill = index_of("Skill List")
    idx_move  = index_of("Move List")

    # Mega Evolution (tolérant)
    idx_mega = next((i for i in range(len(lines)) if contains_token(i, "Mega Evolution")), -1)
    if idx_mega == -1:
        for k in range(len(lines)-1):
            if lines[k] == 'Mega' and lines[k+1] == 'Evolution':
                idx_mega = k+1
                break

    # Base Stats
    if idx_base != -1:
        stats = {}
        for l in lines[idx_base+1 : idx_base+25]:
            m = re.match(r'(?i)^(HP|Attack|Defense|Special Attack|Special Defense|Speed)\s*:\s*([0-9]+)', l)
            if m:
                stats[m.group(1)] = int(m.group(2))
        if not stats:
            logger.warning(f"[p{page_index} {species}] 'Base Stats' section found but no stats parsed.")
        record["Base Stats"] = stats

    def collect_between(start_idx, next_indices):
        if start_idx == -1: return []
        following = [i for i in next_indices if i != -1 and i > start_idx]
        end = min(following) if following else len(lines)
        return lines[start_idx+1:end]

    next_all = [idx_evo, idx_size, idx_breed, idx_diet, idx_hab, idx_cap, idx_skill, idx_move, idx_mega, idx_base, idx_basic]

    # Basic Info
    basic_block = collect_between(idx_basic, next_all)
    if basic_block:
        bi = parse_key_value_block(basic_block, 0, len(basic_block))
        if "Type" in bi and bi["Type"]:
           bi["Type"] = bi["Type"].split(" / ")
        if not bi:
            logger.warning(f"[p{page_index} {species}] 'Basic Information' section empty after parse.")
        record["Basic Information"] = bi

    # Evolution
    evo_block = collect_between(idx_evo, next_all)
    if evo_block:
        evo_lines = [l for l in evo_block if l]
        record["Evolution"] = evo_lines

    # Size
    size_block = collect_between(idx_size, next_all)
    if size_block:
        si = parse_key_value_block(size_block, 0, len(size_block))
        record["Size Information"] = si

    # Breeding
    breed_block = collect_between(idx_breed, next_all)
    if breed_block:
        br = parse_key_value_block(breed_block, 0, len(breed_block))
        record["Breeding Information"] = br

    # Diet / Habitat
    if idx_diet != -1:
        line = lines[idx_diet]
        if ':' in line:
            record["Diet"] = clean_line(line.split(':',1)[1])
        else:
            if idx_diet + 1 < len(lines):
                nxt = lines[idx_diet + 1].strip()
                if nxt.startswith(':'):
                    nxt = nxt[1:]
                if nxt and ':' not in nxt:
                    record["Diet"] = clean_line(nxt)
    if "Diet" not in record:
        logger.warning(f"[p{page_index}] 'Diet' not found in these lines: {lines[idx_diet:idx_diet+3]}")

    if idx_hab != -1:
        if ':' in lines[idx_hab]:
            record["Habitat"] = clean_line(lines[idx_hab].split(':',1)[1])
        else:
            logger.warning(f"[p{page_index} {species}] 'Habitat' header found but no ':' value.")

    # Capabilities (parenthesis-aware join + comma split outside parentheses)
    cap_block = collect_between(idx_cap, next_all)
    if cap_block:
        acc = ""
        level = 0
        for j, raw in enumerate(cap_block):
            l = clean_line(raw)
            if not l:
                continue
            needs_comma = (level > 0 and acc and not acc.rstrip().endswith((',', '('))
                           and not l.startswith((')', ',')))
            if needs_comma:
                acc += ', ' + l
            else:
                if acc and not acc.endswith(' '):
                    acc += ' '
                acc += l
            level += l.count('(') - l.count(')')

        if level != 0:
            logger.warning(f"[p{page_index} {species}] Capability parentheses look unbalanced after join (level={level}).")

        parts = split_commas_outside_parens(acc)
        caps = [clean_line(p) for p in parts if clean_line(p)]
        record["Capabilities"] = caps
    else:
        logger.warning(f"[p{page_index} {species}] No 'Capability List' section found.")

    # Skills
    skill_block = collect_between(idx_skill, next_all)
    if skill_block:
        skills_text = ' '.join(skill_block)
        skills = {}

        # normalise léger : espaces autour des ':'
        skills_text = re.sub(r'\s*:\s*', ': ', skills_text)

        def normalize_skill_name(n: str) -> str:
            n = clean_line(n)

            # Variantes "Edu" (ordre et espaces indifférents)
            if compare_string_with_spaces(n, "Edu: Tech") or compare_string_with_spaces(n, "Tech Edu"):
                return "Tech Edu"
            if (compare_string_with_spaces(n, "Edu: Pokémon")
                or compare_string_with_spaces(n, "Edu: Pokemon")
                or compare_string_with_spaces(n, "Pokémon Edu")
                or compare_string_with_spaces(n, "Pokemon Edu")):
                return "Pokémon Edu"
            if compare_string_with_spaces(n, "Edu: Occult") or compare_string_with_spaces(n, "Occult Edu"):
                return "Occult Edu"
            if compare_string_with_spaces(n, "Edu: General") or compare_string_with_spaces(n, "General Edu"):
                return "General Edu"
            if (compare_string_with_spaces(n, "Edu: Medicine")
                or compare_string_with_spaces(n, "Medicine Edu")
                or compare_string_with_spaces(n, "Med Edu")):
                return "Medicine Edu"

            # Abréviations courantes
            if compare_string_with_spaces(n, "Athl"):   return "Athletics"
            if compare_string_with_spaces(n, "Acro"):   return "Acrobatics"
            if compare_string_with_spaces(n, "Percep"): return "Perception"

            # Principales compétences « simples » (tolérance aux espaces en trop)
            for canonical in [
                "Acrobatics","Athletics","Charm","Command","Guile",
                "Intimidate","Intuition","Perception","Stealth",
                "Survival","Focus"
            ]:
                if compare_string_with_spaces(n, canonical):
                    return canonical

            return n  # défaut : on garde tel quel

        # extraction "Nom 2d6(+X)" robuste
        for m in re.finditer(r'([A-Za-z][A-Za-z :/]+?)\s+([0-9]d6(?:\+\d+)?)', skills_text):
            raw_name = m.group(1)
            dice = m.group(2)
            name = normalize_skill_name(raw_name)

            # garde-fou longueur (évite de mauvaises captures qui explosent tout)
            if len(name) > 64:
                continue

            skills[name] = dice

        if not skills:
            logger.info(f"[p{page_index} {species}] 'Skill List' present but no skills parsed.")
        record["Skills"] = skills


    # Moves
    if idx_move != -1:
        record["Moves"] = parse_moves_list(lines, idx_move)

    # Mega Evolution
    if idx_mega != -1:
        mega_block = collect_between(idx_mega, next_all)
        joined = ' '.join([clean_line(x) for x in mega_block])
        joined = re.sub(r'\s+', ' ', joined).strip()

        mega = {}

        m = re.search(r'(?i)\bType\s*:\s*(.+?)(?=\s+(Ability|Stats)\b|$)', joined)
        if m:
            mega['Type'] = clean_line(m.group(1))

        m = re.search(r'(?i)\bAbility\s*:\s*(.+?)(?=\s+Stats\b|$)', joined)
        if m:
            mega['Ability'] = clean_line(m.group(1))

        stats_text = None
        m = re.search(r'(?i)\bStats\s*:\s*(.+)$', joined)
        if m:
            stats_text = clean_line(m.group(1))

        if stats_text:
            delta = {}
            for pat, key in [(r'Atk','Attack'), (r'Def','Defense'),
                             (r'Sp\.?\s*Atk','Special Attack'), (r'Sp\.?\s*Def','Special Defense'),
                             (r'Speed','Speed'), (r'HP','HP')]:
                m2 = re.search(rf'([+-]?\d+)\s*{pat}', stats_text, flags=re.IGNORECASE)
                if m2:
                    try:
                        delta[key] = int(m2.group(1))
                    except Exception:
                        pass
            mega['Stats'] = delta if delta else stats_text

        if mega:
            record["Mega Evolution"] = mega

        if DEBUG_KEEP_RAW:
            record["mega_evolution_raw"] = mega_block

    return record

def main():
    reader = PyPDF2.PdfReader(PDF_PATH)
    records = []
    pages_with_text = 0
    for i in range(len(reader.pages)):
    #for i in range(0,11):
        try:
            page_text = reader.pages[i].extract_text() or ""
        except Exception as e:
            logger.exception(f"[p{i}] Error extracting text: {e}")
            continue
        if not page_text.strip():
            logger.warning(f"[p{i}] Empty/blank page text.")
            continue
        pages_with_text += 1
        rec = extract_page(page_text, i)

        # Inclusion condition: species + any meaningful section parsed
        has_any = any(rec.get(k) for k in ["Base Stats", "Moves", "Basic Information", "Skills", "Capabilities"])
        if not rec.get("Species"):
            logger.warning(f"[p{i}] Skipped: no Species title detected.")
            continue
        if not has_any:
            logger.warning(f"[p{i} {rec.get('Species')}] Skipped: no parsable sections found.")
            continue
        records.append(rec)

    Path(OUT_JSON).write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    #with open(OUT_NDJSON, 'w', encoding='utf-8') as f:
    #    for r in records:
    #        f.write(json.dumps(r, ensure_ascii=False) + "\\n")

    logger.info(f"Parsed {len(records)} records from {pages_with_text} non-empty pages.")
    #logger.info(f"Wrote {OUT_JSON} and {OUT_NDJSON}. Log: {OUT_LOG}")

if __name__ == "__main__":
    main()
    logger.info("DO ROTOM, PUMKABOO, GOURGEIST AND HOOPA MANUALLY")
