import json, re
from pathlib import Path
import PyPDF2
import logging

PDF_PATH = "9G PaldeaDex.pdf"   # ← adapte si besoin
OUT_JSON = "../../ptu/data/pokedex/pokedex_9g.json"
OUT_NDJSON = "pokedex.ndjson"
OUT_LOG = "pokedex_extraction.log"
# Logging
logger = logging.getLogger("pokedex-extract")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(logging.Formatter("%(levelname)s:%(message)s"))
logger.addHandler(ch)
fh = logging.FileHandler(OUT_LOG, mode="w", encoding="utf-8")
fh.setLevel(logging.INFO)
fh.setFormatter(logging.Formatter("%(levelname)s:%(message)s"))
logger.addHandler(fh)

def split_outside_parentheses(text):
    """
    Split a string on commas, but ignore commas inside parentheses.
    """
    parts = []
    buf = []
    depth = 0
    for ch in text:
        if ch == '(':
            depth += 1
            buf.append(ch)
        elif ch == ')':
            depth = max(depth-1, 0)
            buf.append(ch)
        elif ch == ',' and depth == 0:
            part = ''.join(buf).strip()
            if part:
                parts.append(part)
            buf = []
        else:
            buf.append(ch)
    # dernier morceau
    last = ''.join(buf).strip()
    if last:
        parts.append(last)
    return parts

def split_capabilities(text):
    # Première passe : découper sur virgules hors parenthèses
    parts = split_outside_parentheses(text)
    final = []
    for p in parts:
        # Si on a quelque chose comme "Naturewalk (Forest, Mountain) Intoxicator"
        m = re.match(r'^(.*\))\s+(\S.*)$', p)
        if m:
            final.append(m.group(1).strip())
            final.append(m.group(2).strip())
        else:
            final.append(p.strip())
    return [x for x in final if x]




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

def parse_base_stats_block(lines, start_idx):
    canon = {
        'HP': 'HP',
        'ATK': 'Attack', 'ATTACK': 'Attack',
        'DEF': 'Defense', 'DEFENSE': 'Defense',
        'SP.ATK': 'Special Attack', 'SP ATK': 'Special Attack', 'SPATK': 'Special Attack', 'SPECIAL ATTACK': 'Special Attack', 'SP. ATK': 'Special Attack',
        'SP. DEF': 'Special Defense', 'SP.DEF': 'Special Defense', 'SP DEF': 'Special Defense', 'SPDEF': 'Special Defense', 'SPECIAL DEFENSE': 'Special Defense',
        'SPD': 'Speed', 'SPEED': 'Speed',
    }
    stats = {}
    window = lines[start_idx+1 : min(len(lines), start_idx+40)]
    for i, ln in enumerate(window):
        s = ln.strip()
        for lab, key in list(canon.items()):
            if re.search(rf'(?i)\b{re.escape(lab)}\b', s):
                m = re.search(r'(\d{1,3})\b', s)
                val = None
                if m:
                    val = int(m.group(1))
                else:
                    for j in range(1, 4):
                        if i + j < len(window):
                            m2 = re.search(r'(\d{1,3})\b', window[i+j])
                            if m2:
                                val = int(m2.group(1)); break
                if val is not None and key not in stats:
                    stats[key] = val
        if len(stats) >= 6:
            break
    if len(stats) < 6:
        text_block = ' '.join(window)
        text_block = re.sub(r'\s+', ' ', text_block)
        repl = {r'\bSPA\b': 'SP.ATK', r'\bSPD\b': 'SP.DEF', r'\bSPE\b': 'SPD'}
        for k,v in repl.items():
            text_block = re.sub(k, v, text_block)
        for lab, key in canon.items():
            m = re.search(rf'(?i)\b{re.escape(lab)}\b\s*[:\-]?\s*(\d{{1,3}})\b', text_block)
            if m and key not in stats:
                stats[key] = int(m.group(1))
    m_total = re.search(r'(?i)\bTotal\b\s*[:\-]?\s*(\d{1,3})\b', ' '.join(window))
    if m_total:
        stats['total'] = int(m_total.group(1))
    return stats

def parse_moves_list(lines, start_idx):
    sections = {
        "Level Up Move List": [],
        "TM/Tutor Moves List": [],
    }
    current = None
    i = start_idx
    while i < len(lines):
        line = lines[i]
        if re.search(r'(?i)^Move List$', line): current="Level Up Move List"; i+=1; continue
        if re.search(r'(?i)^TM/Tutor Moves$', line): current="TM/Tutor Moves List"; i+=1; continue
        if re.search(r'(?i)^(Base Stats|Basic Information|Evolution|Size Information|Breeding Information|Capabilities|Skill List)$', line): break
        if current: sections[current].append(line)
        i += 1

    def parse_levelup(block_lines):
        entries = []
        for ln in block_lines:
            m = re.match(r'^\s*(\d+)\s*-\s*(.*?)\s*-\s*([A-Za-z]+)(?:\s*(\[[^\]]+\]))?\s*$', ln)
            if m:
                level = int(m.group(1))
                move = clean_line(m.group(2))
                typ  = clean_line(m.group(3))
                tag  = m.group(4)
                if tag:
                    move = f"{move} {tag}"
                entries.append({"Level": level, "Move": move, "Type": typ})
        return entries

    def parse_comma_or_list(block_lines):
        text = re.sub(r'\s+', ' ', ' '.join(block_lines))
        return [clean_line(p) for p in re.split(r'\s*,\s*', text) if clean_line(p)]

    return {
        "Level Up Move List": parse_levelup(sections["Level Up Move List"]),
        "TM/Tutor Moves List": parse_comma_or_list(sections["TM/Tutor Moves List"]),
        #"_raw": sections
    }

def extract_page(page_text: str, page_index: int):
    lines = [clean_line(l) for l in (page_text or "").splitlines()]
    #logger.info(lines[0])

    lines[0] = re.sub(r'^\d+ Unofficial Homebrew\s(.*)', r'\1', lines[0], flags=re.IGNORECASE).strip()

    #record = {"_page_index": page_index, "_raw_text": page_text}
    record = {}
    # Titre d’espèce
    species = lines[0]

    if not species:
        # Fallback 2 : section Evolution "1 - <Species>"
        for l in lines:
            m = re.match(r'^\s*1\s*-\s*([A-Za-z’\'\- ]+?)\s*(?:$|\s{2,}|Lv|Minimum|\()', l)
            if m:
                species = m.group(1).strip()
                break

    record["Species"] = species
    if not species:
        logger.warning(f"[p{page_index}] Species title not detected.")

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
    idx_group = find_line(r'^Egg Groups')
    idx_cap   = find_line(r'^Capability List|^Capabilities')
    idx_skill = find_line(r'^Skill List')
    idx_move  = find_line(r'^Move List')
    idx_mega  = find_line(r'^Mega Evolution')

    # Base Stats
    if idx_base != -1:
        stats = parse_base_stats_block(lines, idx_base)
        record["Base Stats"] = stats
        if idx_base != -1 and not stats:
            logger.warning(f"[p{page_index} {species}] Base Stats header found but no stats parsed.")

    def insert_after(d: dict, key_after: str, new_key: str, new_val):
        out = {}
        inserted = False
        for k, v in d.items():
            out[k] = v
            if k == key_after:
                out[new_key] = new_val
                inserted = True
        if not inserted:
            out[new_key] = new_val
        d.clear()
        d.update(out)

    def collect_between(start_idx, next_indices):
        if start_idx == -1: return []
        following = [i for i in next_indices if i != -1 and i > start_idx]
        end = min(following) if following else len(lines)
        return lines[start_idx+1:end]

    next_all = [idx_evo, idx_size, idx_breed, idx_diet, idx_hab, idx_cap, idx_skill, idx_move, idx_mega, idx_base, idx_basic]

    # Basic Info
    basic_block = collect_between(idx_basic, next_all)
    size_info = None
    if basic_block:
        bi = parse_key_value_block(basic_block, 0, len(basic_block))

        # Type -> liste
        if "Type" in bi and bi["Type"]:
            bi["Type"] = [t.strip() for t in bi["Type"].split(" / ") if t.strip()]

        # Détection "Size:" réparti sur plusieurs lignes
        # --- Size (hauteur/poids) robustifié : concatène plusieurs lignes ---
        for i in range(len(basic_block)):
            if basic_block[i].startswith("Size:"):
                # On agrège jusqu'à rencontrer le prochain champ/section
                stop_pat = re.compile(r'(?i)^(Genders?:|Diet:|Habitat:|Capabilities\b|Skill List\b|Move List\b|Evolution:|Other Information\b)')
                parts = []
                k = i
                while k < len(basic_block) and len(parts) < 6:
                    ln = basic_block[k].strip()
                    if k > i and stop_pat.match(ln):
                        break
                    parts.append(ln)
                    k += 1

                item = ' '.join(parts)
                item = re.sub(r'\s+', ' ', item).strip()

                # Exemples :
                # "Size: 1’0’’ / 0.3m (Small) 35.3 lbs / 16.0 kg (Weight Class 2)"
                # "Size: 5’03’’ / 1.6m (Medium) 343.9 lbs / 156.0 kg (Weight Class 6)"
                m = re.search(r'(?i)Size:\s*(.*?\))\s+(.+?)(?:\s+(?:Genders?:|Diet:|Habitat:|Capabilities\b|Skill List\b|Move List\b|Evolution:|Other Information\b)|$)', item)
                if m:
                    height = m.group(1).strip()
                    weight = m.group(2).strip()
                    # Nettoie l’ancienne clé plate et stocke proprement
                    bi.pop("Size", None)
                    bi.setdefault("Size Information", {})
                    bi["Size Information"]["Height"] = height
                    bi["Size Information"]["Weight"] = weight
                else:
                    logger.warning(f"[p{page_index} {species}] Size line found but regex failed: {item}")
                break


        if not bi:
            logger.warning(f"[p{page_index} {species}] 'Basic Information' section empty after parse.")
        record["Basic Information"] = bi


    # ---- Evolution (format brut conservé, sans avaler les sections suivantes) ----
# ---- Evolution (format brut conservé) ----

    evo_block = []

    if idx_evo != -1:
        # Cas normal : il y a un vrai header "Evolution"
        for ln in lines[idx_evo+1:]:
            if re.match(r'(?i)^(Other Information|Size:|Genders?:|Diet:|Habitat:|Capabilities\b|Skill List\b|Move List\b|TM/HM Move List|TM/Tutor Moves|Egg Move List|Tutor Move List|Mega Evolution|Base Stats|Basic Information)\b', ln):
                break
            if ln.strip():
                evo_block.append(clean_line(ln))
    else:
        # Fallback : pas de header explicite → on scanne les lignes
        for ln in lines:
            if re.match(r'^\s*\d+\s*-\s*\S', ln):
                evo_block.append(clean_line(ln))
            # On arrête si on tombe sur une nouvelle section
            elif evo_block and re.match(r'(?i)^(Other Information|Size:|Genders?:|Diet:|Habitat:|Capabilities\b|Skill List\b|Move List\b|TM/HM Move List|TM/Tutor Moves|Egg Move List|Tutor Move List|Mega Evolution|Base Stats|Basic Information)\b', ln):
                break

    if evo_block:
        record["Evolution"] = evo_block
    else:
        logger.info(f"[p{page_index} {species}] Evolution header not found or empty.")


    # Size
    size_block = collect_between(idx_size, next_all)
    if size_block:
        record["Size Information"] = parse_key_value_block(size_block, 0, len(size_block))

    # Breeding
    breed_block = collect_between(idx_breed, next_all)
    if breed_block:
        record["Breeding Information"] = parse_key_value_block(breed_block, 0, len(breed_block))
    # Diet / Habitat
    if idx_diet != -1 and ':' in lines[idx_diet]:
        record["Diet"] = clean_line(lines[idx_diet].split(':',1)[1])
    if idx_hab != -1 and ':' in lines[idx_hab]:
        record["Habitat"] = clean_line(lines[idx_hab].split(':',1)[1].replace('Capabilities', '').strip())

   # --- Egg Groups (souvent collé après Habitat ou sur la/les lignes suivantes) ---
    egg_groups_val = None

    # Cas 1 : sur la même ligne que Habitat
    hline = lines[idx_hab] if idx_hab != -1 and idx_hab < len(lines) else ""
    m = re.search(r'(?i)\bEgg\s+Groups?\s*:\s*(.+)$', hline)
    if m:
        egg_groups_val = m.group(1).strip()

    # Cas 2 : sur les lignes suivantes (jusqu'au prochain header)
    if not egg_groups_val and idx_hab != -1:
        # on concatène quelques lignes pour couvrir les retours à la ligne
        look = ' '.join(lines[idx_hab+1 : min(len(lines), idx_hab+6)])
        look = re.sub(r'\s+', ' ', look).strip()
        mm = re.search(
            r'(?i)\bEgg\s+Groups?\s*:\s*(.+?)(?=\s+(Capabilities|Skill List|Move List|Evolution:|Other Information|Basic Information|Size Information|Breeding Information)\b|$)',
            look
        )
        if mm:
            egg_groups_val = mm.group(1).strip()

    if egg_groups_val:
        # coupe si un header a été collé après
        egg_groups_val = re.sub(
            r'(?i)\b(Capabilities|Skill List|Move List|Evolution:|Other Information|Basic Information|Size Information|Breeding Information)\b.*$',
            '',
            egg_groups_val
        ).strip()
        groups = [clean_line(x) for x in re.split(r'\s*,\s*', egg_groups_val) if clean_line(x)]
        record.setdefault("Breeding Information", {})
        record["Breeding Information"]["Egg Groups"] = groups


    # Capabilities
    idx_cap = -1
    for i, l in enumerate(lines):
        if re.search(r'\bCapabilities\b', l, flags=re.I):
            idx_cap = i
            if not re.match(r'(?i)^\s*Capabilities', l):
                # On découpe la ligne en deux : avant et après "Capabilities"
                parts = re.split(r'(?i)\bCapabilities\b', l, maxsplit=1)
                lines[i] = parts[0].strip()         # ex: "Habitat: Grassland, Forest"
                lines.insert(i+1, "Capabilities")   # nouvelle ligne propre
            break

    cap_block = collect_between(idx_cap, next_all)
    if cap_block:
        text = ' '.join(cap_block).replace('Capabilities ', '')
        caps = [clean_line(x) for x in split_capabilities(text) if clean_line(x)]
        record["Capabilities"] = caps

    # Skills
    skill_block = collect_between(idx_skill, next_all)
    if skill_block:
        skills_text = ' '.join(skill_block)
        skills = {}
        for m in re.finditer(r'(Athl|Acro|Combat|Stealth|Percep|Focus)\s+([0-9]d6(?:\+\d+)?)', skills_text):
            skills[m.group(1)] = m.group(2)
        record["Skills"] = skills

    # Moves
    if idx_move != -1:
        record["Moves"] = parse_moves_list(lines, idx_move)

    # Mega Evolution
    if idx_mega != -1:
        mega_block = collect_between(idx_mega, [])
        mega = {}
        for l in mega_block:
            if re.search(r'(?i)^Type', l):    mega['Type'] = l.split(':',1)[1].strip() if ':' in l else l
            elif re.search(r'(?i)^Ability', l): mega['Ability'] = l.split(':',1)[1].strip() if ':' in l else l
            elif re.search(r'(?i)^Stats', l):   mega['Stats Delta'] = l.split(':',1)[1].strip() if ':' in l else l
        if mega: record["Mega Evolution"] = mega
        #record["mega_evolution_raw"] = mega_block

    return record

def main():
    reader = PyPDF2.PdfReader(PDF_PATH)
    records = []
    #for i in range(len(reader.pages)):
    for i in range(46, 174):
        page_text = reader.pages[i].extract_text() or ""
        if not page_text.strip(): continue
        rec = extract_page(page_text, i)
        if rec.get("Species") and (rec.get("Base Stats") or rec.get("Moves") or rec.get("Basic Information")):
            records.append(rec)

    Path(OUT_JSON).write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    # Sanity: report if Rotom appears in text but not parsed
    try:
        all_text = []
        for i in range(46,len(reader.pages)):
            t = reader.pages[i].extract_text() or ""
            all_text.append(t)
        if any(re.search(r"(?i)\brotom\b", t) for t in all_text) and not any("ROTOM" in (r.get("Species","").upper()) for r in records):
            logger.error("ROTOM appears in PDF text but no Rotom records parsed. Check title/header parsing.")
    except Exception as e:
        logger.info(f"Rotom check skipped: {e}")
    logger.info(f"Parsed {len(records)} records.")
    logger.info(f"Outputs: {OUT_JSON}, {OUT_NDJSON}. Log: {OUT_LOG}")

    with open(OUT_NDJSON, 'w', encoding='utf-8') as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    main()
