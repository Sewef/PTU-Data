import json
import re
import shutil
import unicodedata
from pathlib import Path
from typing import List, Dict, Tuple
from difflib import SequenceMatcher

# ---------------- Utils de normalisation ----------------

def strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))

def soft_norm(s: str) -> str:
    """
    Normalisation "tolérante":
    - minuscules
    - suppression des accents
    - ponctuation -> espace (conserve les mots dans les parenthèses)
    - compactage espaces
    """
    s = strip_accents(s).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def token_spans(s: str) -> List[Tuple[str, Tuple[int, int]]]:
    """
    Tokenise s en mots alphanum (avec apo/tirets internes) et retourne
    [(mot_normalise, (start,end)), ...] sur la chaîne ORIGINALE.
    """
    out = []
    for m in re.finditer(r"[A-Za-z0-9]+(?:['’\-:][A-Za-z0-9]+)*|[A-Za-z0-9]+", s):
        frag = m.group(0)
        out.append((soft_norm(frag), m.span()))
    return out

# ---------------- Index des espèces ----------------

def build_species_index(rows: List[dict]) -> List[Tuple[str, str]]:
    """
    [(species_originale, species_normalisee)] triée par longueur décroissante.
    """
    seen = set()
    items: List[Tuple[str, str]] = []
    for p in rows:
        name = str(p.get("Species", "")).strip()
        if not name:
            continue
        n = soft_norm(name)
        if n and n not in seen:
            seen.add(n)
            items.append((name, n))
    items.sort(key=lambda t: len(t[1]), reverse=True)
    return items

# ---------------- Parsing d'une ligne d'évolution ----------------

STAGE_RE = re.compile(r"^\s*(\d+)\s*-\s*(.+?)\s*$")

def split_stage_and_body(line: str) -> Tuple[int, str]:
    m = STAGE_RE.match(line)
    if not m:
        raise ValueError(f"Format d'évolution non reconnu: {line!r}")
    return int(m.group(1)), m.group(2)

def best_species_match(body: str, species_index: List[Tuple[str, str]]) -> Tuple[str, str]:
    """
    Choisit l'espèce la plus plausible en début de `body`.
    1) essai exact/préfixe (normalisé),a    
    2) sinon, fuzzy (difflib) sur toutes les coupures du début,
    Puis on coupe la Condition après avoir avalé une éventuelle parenthèse fermante.
    Retourne (species_canonique, condition_originale).
    """
    body_norm = soft_norm(body)

    def slice_condition_after(spec_norm: str, species_canonical: str) -> Tuple[str, str]:
        # Retrouver la fin du dernier token de l'espèce dans la chaîne ORIGINALE
        tokens = token_spans(body)
        spec_tokens = spec_norm.split(" ")
        j = 0
        last_end = 0
        for tn, (a, b) in tokens:
            if j < len(spec_tokens) and tn == spec_tokens[j]:
                last_end = b
                j += 1
            if j == len(spec_tokens):
                break

        # --- RÈGLE DEMANDÉE ---
        # Après le dernier token, sauter les espaces et avaler un ')' s'il est immédiatement présent.
        k = last_end
        while k < len(body) and body[k].isspace():
            k += 1
        if k < len(body) and body[k] == ')':
            last_end = k + 1  # inclure la parenthèse fermante dans la "zone espèce"

        condition = body[last_end:].strip(" -–—\t\r\n")
        return species_canonical, condition

    # 1) Exact / préfixe normalisé (index trié par longueur décroissante)
    for spec_orig, spec_norm in species_index:
        if body_norm == spec_norm or body_norm.startswith(spec_norm + " "):
            return slice_condition_after(spec_norm, spec_orig)

    # 2) Fuzzy prefix
    tokens = token_spans(body)
    if not tokens:
        return body.strip(), ""

    candidates = []
    for i in range(1, len(tokens) + 1):
        left_end = tokens[i-1][1][1]
        left_orig = body[:left_end].strip()
        left_norm = soft_norm(left_orig)
        if len(left_norm) >= 3:
            candidates.append((left_orig, left_norm, left_end))

    BEST = None  # (priorité, score, species_canonique, species_norm)
    THRESH = 0.86

    from difflib import SequenceMatcher
    for _left_orig, left_norm, _left_end in candidates:
        for spec_orig, spec_norm in species_index:
            if left_norm == spec_norm or left_norm.startswith(spec_norm + " "):
                prio, score = 3, 1.0
            else:
                ratio = SequenceMatcher(None, left_norm, spec_norm).ratio()
                if ratio < THRESH:
                    continue
                ln_toks = left_norm.split()
                sn_toks = spec_norm.split()
                overlap = sum(1 for t in ln_toks if t in sn_toks)
                cov = overlap / max(len(sn_toks), 1)
                prio = 2 if cov >= 0.6 else 1
                score = ratio + cov * 0.05

            if BEST is None or (prio, score) > (BEST[0], BEST[1]):
                BEST = (prio, score, spec_orig, spec_norm)

    if BEST:
        _, _, spec_orig, spec_norm = BEST
        return slice_condition_after(spec_norm, spec_orig)

    # 3) Fallback conservateur
    return body.strip(), ""

    """
    Choisit l'espèce la plus plausible en début de `body`.
    1) essai exact/préfixe (normalisé),
    2) sinon, fuzzy (difflib) sur toutes les coupures du début,
    Puis on coupe la Condition après avoir avalé une éventuelle parenthèse fermante.
    Retourne (species_canonique, condition_originale).
    """
    body_norm = soft_norm(body)

    def slice_condition_after(spec_norm: str, species_canonical: str) -> Tuple[str, str]:
        # Retrouver la fin du dernier token de l'espèce dans la chaîne ORIGINALE
        tokens = token_spans(body)
        spec_tokens = spec_norm.split(" ")
        j = 0
        last_end = 0
        for tn, (a, b) in tokens:
            if j < len(spec_tokens) and tn == spec_tokens[j]:
                last_end = b
                j += 1
            if j == len(spec_tokens):
                break

        # --- RÈGLE DEMANDÉE ---
        # Après le dernier token, sauter les espaces et avaler un ')' s'il est immédiatement présent.
        k = last_end
        while k < len(body) and body[k].isspace():
            k += 1
        if k < len(body) and body[k] == ')':
            last_end = k + 1  # inclure la parenthèse fermante dans la "zone espèce"

        condition = body[last_end:].strip(" -–—\t\r\n")
        return species_canonical, condition

    # 1) Exact / préfixe normalisé (index trié par longueur décroissante)
    for spec_orig, spec_norm in species_index:
        if body_norm == spec_norm or body_norm.startswith(spec_norm + " "):
            return slice_condition_after(spec_norm, spec_orig)

    # 2) Fuzzy prefix
    tokens = token_spans(body)
    if not tokens:
        return body.strip(), ""

    candidates = []
    for i in range(1, len(tokens) + 1):
        left_end = tokens[i-1][1][1]
        left_orig = body[:left_end].strip()
        left_norm = soft_norm(left_orig)
        if len(left_norm) >= 3:
            candidates.append((left_orig, left_norm, left_end))

    BEST = None  # (priorité, score, species_canonique, species_norm)
    THRESH = 0.86

    from difflib import SequenceMatcher
    for _left_orig, left_norm, _left_end in candidates:
        for spec_orig, spec_norm in species_index:
            if left_norm == spec_norm or left_norm.startswith(spec_norm + " "):
                prio, score = 3, 1.0
            else:
                ratio = SequenceMatcher(None, left_norm, spec_norm).ratio()
                if ratio < THRESH:
                    continue
                ln_toks = left_norm.split()
                sn_toks = spec_norm.split()
                overlap = sum(1 for t in ln_toks if t in sn_toks)
                cov = overlap / max(len(sn_toks), 1)
                prio = 2 if cov >= 0.6 else 1
                score = ratio + cov * 0.05

            if BEST is None or (prio, score) > (BEST[0], BEST[1]):
                BEST = (prio, score, spec_orig, spec_norm)

    if BEST:
        _, _, spec_orig, spec_norm = BEST
        return slice_condition_after(spec_norm, spec_orig)

    # 3) Fallback conservateur
    return body.strip(), ""

    """
    Détermine l'espèce la plus plausible en début de `body`.
    - Essaie d'abord un match exact/prefixe sur versions normalisées.
    - Sinon, essaie toutes les coupures possibles (token par token) et choisit l'espèce la plus similaire.
    Puis coupe la chaîne originale au bon endroit, en avalant une parenthèse fermante s'il y a lieu.
    Retourne (species_originale, condition_restante_originale).
    """
    body_norm = soft_norm(body)

    def slice_condition(spec_norm: str, spec_orig: str) -> Tuple[str, str]:
        # Re-trouve la fin du dernier token "espèce" dans la chaîne ORIGINALE
        tokens = token_spans(body)
        spec_tokens = spec_norm.split(" ")
        j = 0
        last_end = 0
        for tn, (a, b) in tokens:
            if j < len(spec_tokens) and tn == spec_tokens[j]:
                last_end = b
                j += 1
            if j == len(spec_tokens):
                break

        # --- Ajustement parenthèse fermante ---
        # Si l'espèce de référence contient une parenthèse fermante,
        # il est fréquent que notre tokenisation s'arrête avant le ')'.
        if ')' in spec_orig:
            k = last_end
            # sauter espaces
            while k < len(body) and body[k].isspace():
                k += 1
            # avaler la parenthèse fermante si elle suit immédiatement
            if k < len(body) and body[k] == ')':
                last_end = k + 1

        condition = body[last_end:].strip(" -–—\t\r\n")
        return spec_orig, condition

    # 1) Exact/prefixe sur normalisé (index trié par longueur décroissante)
    for spec_orig, spec_norm in species_index:
        if body_norm == spec_norm or body_norm.startswith(spec_norm + " "):
            return slice_condition(spec_norm, spec_orig)

    # 2) Fuzzy prefix : on teste toutes les coupures tokenisées
    tokens = token_spans(body)
    if not tokens:
        return body.strip(), ""

    candidates = []
    for i in range(1, len(tokens) + 1):
        left_end = tokens[i-1][1][1]
        left_orig = body[:left_end].strip()
        left_norm = soft_norm(left_orig)
        if not left_norm or len(left_norm) < 3:
            continue
        candidates.append((left_orig, left_norm, left_end))

    BEST = None  # (priority, score, spec_orig, spec_norm)
    THRESH = 0.86

    from difflib import SequenceMatcher
    for left_orig, left_norm, _left_end in candidates:
        for spec_orig, spec_norm in species_index:
            if left_norm == spec_norm or left_norm.startswith(spec_norm + " "):
                prio, score = 3, 1.0
            else:
                ratio = SequenceMatcher(None, left_norm, spec_norm).ratio()
                if ratio < THRESH:
                    continue
                ln_toks = left_norm.split()
                sn_toks = spec_norm.split()
                overlap = sum(1 for t in ln_toks if t in sn_toks)
                cov = overlap / max(len(sn_toks), 1)
                prio = 2 if cov >= 0.6 else 1
                score = ratio + cov * 0.05

            if BEST is None or (prio, score) > (BEST[0], BEST[1]):
                BEST = (prio, score, spec_orig, spec_norm)

    if BEST:
        _, _, spec_orig, spec_norm = BEST
        return slice_condition(spec_norm, spec_orig)

    # 3) Fallback conservateur
    return body.strip(), ""

    """
    Détermine l'espèce la plus plausible en début de `body`.
    - Essaie d'abord un match exact/prefixe sur versions normalisées.
    - Sinon, essaie toutes les coupures possibles du début (token par token)
      et choisit l'espèce dont la similarité est max (Seuil par défaut ~0.86).
    Retourne (species_originale, condition_restante_originale).
    """
    body_norm = soft_norm(body)

    # 1) Exact ou préfixe normalisé sur l'index (déjà trié par longueur décroissante)
    for spec_orig, spec_norm in species_index:
        if body_norm == spec_norm or body_norm.startswith(spec_norm + " "):
            # Retranche exactement la longueur normalisée dans la chaîne originale
            tokens = token_spans(body)
            spec_tokens = spec_norm.split(" ")
            j = 0
            last_end = 0
            for tn, (a, b) in tokens:
                if j < len(spec_tokens) and tn == spec_tokens[j]:
                    last_end = b
                    j += 1
                if j == len(spec_tokens):
                    break
            condition = body[last_end:].strip(" -–—\t\r\n")
            return spec_orig, condition

    # 2) Fuzzy prefix : on teste toutes les coupures tokenisées
    tokens = token_spans(body)
    if not tokens:
        return body.strip(), ""

    # Prépare toutes les coupures "début..i"
    # On impose une longueur minimale pour éviter de matcher un tout petit bout
    candidates = []
    for i in range(1, len(tokens) + 1):
        left_end = tokens[i-1][1][1]    # fin du i-ème token sur la chaîne originale
        left_orig = body[:left_end].strip()
        left_norm = soft_norm(left_orig)
        if not left_norm:
            continue
        candidates.append((left_orig, left_norm, left_end))

    BEST = None  # (score, ratio, spec_orig, left_end)
    THRESH = 0.86

    for left_orig, left_norm, left_end in candidates:
        # skip les micro-fragments (1 seul petit token)
        if len(left_norm) < 3:
            continue

        # Compare à toutes les espèces
        for spec_orig, spec_norm in species_index:
            # petite accélération: si la différence de longueur est énorme, passe
            if len(left_norm) < len(spec_norm)*0.5:
                continue

            if left_norm == spec_norm or left_norm.startswith(spec_norm + " "):
                score = (3, 1.0)  # exact/prefixe parfait
            else:
                ratio = SequenceMatcher(None, left_norm, spec_norm).ratio()
                if ratio < THRESH:
                    continue
                # Critères supplémentaires: recouvrement en mots
                ln_toks = left_norm.split()
                sn_toks = spec_norm.split()
                overlap = sum(1 for t in ln_toks if t in sn_toks)
                cov = overlap / max(len(sn_toks), 1)
                # score = (priorité, ratio, couverture)
                score = (2 if cov >= 0.6 else 1, ratio + cov*0.05)

            if BEST is None or score > (BEST[0], BEST[1]):
                BEST = (score[0], score[1], spec_orig, left_end)

    if BEST:
        _, _, spec_orig, left_end = BEST
        condition = body[left_end:].strip(" -–—\t\r\n")
        return spec_orig, condition

    # 3) Fallback ultra-conservateur
    return body.strip(), ""

def parse_evolution_smart(evo_list: List[str], species_index: List[Tuple[str, str]]) -> List[Dict]:
    out = []
    for raw in evo_list:
        if not isinstance(raw, str) or not raw.strip():
            continue
        try:
            stade, body = split_stage_and_body(raw)
        except ValueError:
            out.append({"Stade": None, "Species": raw.strip(), "Condition": ""})
            continue

        species, condition = best_species_match(body, species_index)
        out.append({"Stade": stade, "Species": species, "Condition": condition})
    return out

# ---------------- I/O principal ----------------

def load_rows_any(filename: Path):
    with filename.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "Pokedex" in data and isinstance(data["Pokedex"], list):
        return data["Pokedex"], data
    elif isinstance(data, list):
        return data, data
    else:
        raise ValueError('Format JSON inattendu (array ou {"Pokedex": [...]} attendu)')

def save_rows_any(filename: Path, rows, root):
    if isinstance(root, dict) and "Pokedex" in root and isinstance(root["Pokedex"], list):
        root["Pokedex"] = rows
        obj_to_dump = root
    else:
        obj_to_dump = rows
    with filename.open("w", encoding="utf-8") as f:
        json.dump(obj_to_dump, f, indent=2, ensure_ascii=False)

def normalize_evolutions_in_file(filename_str: str):
    filename = Path(filename_str)
    if not filename.exists():
        raise FileNotFoundError(filename)
    backup = filename.with_suffix(filename.suffix + ".bak")
    #shutil.copy2(filename, backup)

    rows, root = load_rows_any(filename)
    species_index = build_species_index(rows)

    for p in rows:
        evo = p.get("Evolution")
        if isinstance(evo, list) and evo:
            p["Evolution"] = parse_evolution_smart(evo, species_index)

    save_rows_any(filename, rows, root)
    print(f"✅ Évolutions normalisées")

if __name__ == "__main__":
    # Mets ici le nom de ton JSON source
    normalize_evolutions_in_file("../../ptu/data/pokedex/pokedex_8g_hisui.json")
