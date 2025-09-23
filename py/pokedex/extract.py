
import json, re, logging
from pathlib import Path
import PyPDF2

PDF_PATH = "1-6G Pokedex_Playtest105Plus.pdf"   # ← adapte si besoin
OUT_JSON = "pokedex_core.json"
OUT_NDJSON = "pokedex_core.ndjson"
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
    s = s.replace('\xa0', ' ').replace('‒', '-').replace('–', '-').replace('—', '-')
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
        if re.search(r'(?i)^Move List$', line): i+=1; continue
        if re.search(r'(?i)^Level Up Move List$', line): current="Level Up Move List"; i+=1; continue
        if re.search(r'(?i)^TM/HM Move List$', line): current="TM/HM Move List"; i+=1; continue
        if re.search(r'(?i)^Egg Move List$', line): current="Egg Move List"; i+=1; continue
        if re.search(r'(?i)^Tutor Move List$', line): current="Tutor Move List"; i+=1; continue
        if re.search(r'(?i)^Mega Evolution', line): break
        if re.search(r'(?i)^(Base Stats:|Basic Information|Evolution:|Size Information|Breeding Information|Capability List|Skill List)$', line): break
        if current: sections[current].append(line)
        i += 1

    def parse_levelup(block_lines):
        entries = []
        for ln in block_lines:
            m = re.match(r'^\s*(\d+)\s+(.+)\s*-\s*([A-Za-z]+)\s*$', ln)
            if m:
                entries.append({"Level": int(m.group(1)),
                                "Move": clean_line(m.group(2)),
                                "Type": clean_line(m.group(3))})
        return entries

    def parse_comma_or_list(block_lines):
        # Joindre les lignes
        text = ' '.join(block_lines)
        # Corriger les césures "So - lar" -> "Solar"
        text = re.sub(r'(\w)\s*-\s+(\w)', r'\1\2', text)
        # Nettoyer les espaces multiples
        text = re.sub(r'\s+', ' ', text).strip()
        # Split sur virgule
        parts = [clean_line(p) for p in text.split(',')]
        # Filtrer les vides
        return [p for p in parts if p]

    return {
        "Level Up Move List": parse_levelup(sections["Level Up Move List"]),
        "TM/HM Move List": parse_comma_or_list(sections["TM/HM Move List"]),
        "Egg Move List": parse_comma_or_list(sections["Egg Move List"]),
        "Tutor Move List": parse_comma_or_list(sections["Tutor Move List"]),
        "_raw": sections
    }

def extract_page(page_text: str, page_index: int):
    lines = [clean_line(l) for l in (page_text or "").splitlines()]

    # --- Dirty fix: some Capability List are wrongly formatted ---
    # Liste des en-têtes que l’on veut isoler
    KNOWN_HEADERS = [
        "Base Stats", "Basic Information", "Evolution", "Size Information",
        "Breeding Information", "Diet", "Habitat", "Capability List", "Skill List",
        "Move List", "Level Up Move List", "TM/HM Move List",
        "Egg Move List", "Tutor Move List", "Mega Evolution"
    ]

    fixed_lines = []
    skip_next = False
    for i, l in enumerate(lines):
        if skip_next:
            skip_next = False
            continue

        # --- Corriger les mots coupés en fin de ligne ---
        if l.endswith('-') and i + 1 < len(lines):
            merged = l[:-1].rstrip() + lines[i + 1].lstrip()
            logger.debug(f"[Page {page_index}] Recollé '{l}' + '{lines[i+1]}' -> '{merged}'")
            l = merged
            skip_next = True

        # --- Découper les headers collés sur la même ligne ---
        found = []
        for h in KNOWN_HEADERS:
            pos = l.find(h)
            if pos > 0:   # header trouvé, mais pas en début de ligne
                found.append((pos, h))
        if found:
            found.sort()  # trier par position
            start = 0
            for pos, h in found:
                before = l[start:pos].strip()
                if before:
                    fixed_lines.append(before)
                fixed_lines.append(h)  # insérer le header comme ligne à part
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
        if l.startswith("Capability List "):
            fixed_lines.append("Capability List")
            fixed_lines.append(l[len("Capability List "):].strip())
        else:
            fixed_lines.append(l)

    lines = fixed_lines


    record = {"_page_index": page_index, "_raw_text": page_text}

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

    # Remove leading numbers and normalize capitalization
    if species:
        species = re.sub(r'^\s*\d+\s*', '', species)  # remove leading number
        species = fix_species_spacing(species)        # <<<< ajout
        species = species.title()
    record["Species"] = species

    def find_line(pat):
        for i,l in enumerate(lines):
            if re.search(pat, l, flags=re.IGNORECASE): return i
        return -1

    idx_base  = find_line(r'^Base Stats:?')
    idx_basic = find_line(r'^Basic Information')
    idx_evo   = find_line(r'^Evolution:')
    idx_size  = find_line(r'^Size Information')
    idx_breed = find_line(r'^Breeding Information')
    idx_diet  = find_line(r'^Diet')
    idx_hab   = find_line(r'^Habitat')
    idx_cap   = find_line(r'^.*Capability.*List.*')
    idx_skill = find_line(r'^Skill List')
    idx_move  = find_line(r'^Move List')
    idx_mega  = find_line(r'^Mega Evolution')

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
    # Diet
    if idx_diet != -1:
        line = lines[idx_diet]
        if ':' in line:
            record["Diet"] = clean_line(line.split(':',1)[1])
        else:
            # Cas où la valeur est sur la ligne suivante
            if idx_diet + 1 < len(lines):
                nxt = lines[idx_diet + 1].strip()
                if nxt.startswith(':'):
                    nxt = nxt[1:]  # enlever le ':' en début
                if nxt and ':' not in nxt:   # éviter de prendre un autre champ
                    record["Diet"] = clean_line(nxt)
    if "Diet" not in record:
        logger.warning(f"[p{page_index}] 'Diet' not found in these lines: {lines[idx_diet:idx_diet+3]}")

    if idx_hab != -1:
        if ':' in lines[idx_hab]:
            record["Habitat"] = clean_line(lines[idx_hab].split(':',1)[1])
        else:
            logger.warning(f"[p{page_index} {species}] 'Habitat' header found but no ':' value.")

    # Capabilities
    cap_block = collect_between(idx_cap, next_all)
    if cap_block:
        caps = [clean_line(x) for x in re.split(r'\s*,\s*', ' '.join(cap_block)) if clean_line(x)]
        record["Capabilities"] = caps
    else:
        logger.warning(f"[p{page_index} {species}] No 'Capability List' section found.")

    # Skills (broadened and normalized)
    skill_block = collect_between(idx_skill, next_all)
    if skill_block:
        skills_text = ' '.join(skill_block)
        skills = {}
        for m in re.finditer(r'([A-Za-z][A-Za-z :]+?)\s+([0-9]d6(?:\+\d+)?)', skills_text):
            name = clean_line(m.group(1))
            dice = m.group(2)
            if len(name) > 32:
                continue
            name_map = {
                "Edu: Tech": "Tech Edu",
                "Edu: Pokémon": "Pokémon Edu",
                "Edu: Pokemon": "Pokémon Edu",
                "Edu: Occult": "Occult Edu",
                "Edu: General": "General Edu",
                "Edu: Medicine": "Medicine Edu",
                "Athl": "Athletics",
                "Acro": "Acrobatics",
                "Percep": "Perception",
            }
            name = name_map.get(name, name)
            skills[name] = dice
        if not skills:
            logger.info(f"[p{page_index} {species}] 'Skill List' present but no skills parsed.")
        record["Skills"] = skills

    # Moves
    if idx_move != -1:
        record["Moves"] = parse_moves_list(lines, idx_move)

    # Mega Evolution
    if idx_mega != -1:
        mega_block = collect_between(idx_mega, [])
        mega = {}
        stats_lines = []
        for l in mega_block:
            if re.search(r'(?i)^Type', l):
                mega['Type'] = l.split(':', 1)[1].strip() if ':' in l else l
            elif re.search(r'(?i)^Ability', l):
                mega['Ability'] = l.split(':', 1)[1].strip() if ':' in l else l
            elif re.search(r'(?i)^Stats', l):
                # première ligne de stats
                first_stats = l.split(':', 1)[1].strip() if ':' in l else l
                stats_lines.append(first_stats)
            elif stats_lines:
                # toutes les lignes suivantes après Stats
                stats_lines.append(l.strip())
        
        if stats_lines:
            # concaténer ou garder en string séparé par une virgule
            mega['Stats'] = ', '.join(stats_lines)
            mega['Stats'] = mega['Stats'].replace(',,', ',')  # Nettoyer les doubles virgules

        if mega:
            record["Mega Evolution"] = mega
        record["mega_evolution_raw"] = mega_block

    return record

def main():
    reader = PyPDF2.PdfReader(PDF_PATH)
    records = []
    pages_with_text = 0
    for i in range(11, len(reader.pages)):
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
    with open(OUT_NDJSON, 'w', encoding='utf-8') as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\\n")

    logger.info(f"Parsed {len(records)} records from {pages_with_text} non-empty pages.")
    logger.info(f"Wrote {OUT_JSON} and {OUT_NDJSON}. Log: {OUT_LOG}")

if __name__ == "__main__":
    main()
