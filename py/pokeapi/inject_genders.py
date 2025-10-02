#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Injecte le champ "Genders" (format: '50.0% Male / 50.0% Female' ou 'Unknown')
dans 'Other Information' de tous les JSON d'un dossier (récursif), en le plaçant:
- APRÈS "Size" (prioritaire), sinon APRÈS "Size Information" si "Size" absent,
- et AVANT "Diet" si "Size"/"Size Information" absents mais "Diet" existe.
- sinon en TÊTE du bloc "Other Information" si aucune des clés n'existe.

Source: un JSON avec:
  - "Other Information" -> "Genders" (prioritaire), OU
  - "gender_distribution": {"male":x, "female":y, "genderless":z}

Usage :
  python inject_genders.py --source genders_source.json --target-dir /path/to/jsons [--dry-run]
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Union

def load_source_mapping(source_path: Path) -> Dict[str, str]:
    """Construit: species_name_lower -> genders_string"""
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "results" in raw and isinstance(raw["results"], list):
        items = raw["results"]
    elif isinstance(raw, list):
        items = raw
    else:
        items = [raw]

    def compute_from_distribution(gd: Dict[str, Any]) -> str:
        try:
            gles = float(gd.get("genderless", 0) or 0)
            if gles >= 1.0:
                return "Unknown"
            male = float(gd.get("male", 0) or 0)
            female = float(gd.get("female", 0) or 0)
            if male < 0: male = 0.0
            if female < 0: female = 0.0
            s = male + female
            if s > 0:
                male /= s
                female /= s
            m_pct = round(male * 100.0, 1)
            f_pct = round(female * 100.0, 1)
            return f"{m_pct}% Male / {f_pct}% Female"
        except Exception:
            return "Unknown"

    mapping: Dict[str, str] = {}
    for it in items:
        sp = it.get("Species") or it.get("species")
        if not isinstance(sp, str) or not sp.strip():
            continue
        key = sp.strip().lower()

        # 1) Priorité : déjà formaté dans Other Information
        oi = it.get("Other Information") or it.get("Other information") or {}
        genders = None
        if isinstance(oi, dict):
            g = oi.get("Genders") or oi.get("genders")
            if isinstance(g, str) and g.strip():
                genders = g.strip()

        # 2) Sinon: gender_distribution -> format
        if not genders:
            gd = it.get("gender_distribution")
            if isinstance(gd, dict):
                genders = compute_from_distribution(gd)

        if genders:
            mapping[key] = genders

    return mapping


def find_json_files_recursive(root: Path) -> List[Path]:
    return [p for p in root.rglob("*.json") if p.is_file()]


def extract_species_objects(doc: Any) -> List[Tuple[Union[dict, list], dict]]:
    """Retourne (container, obj) pour chaque espèce détectée"""
    out: List[Tuple[Union[dict, list], dict]] = []
    if isinstance(doc, list):
        for obj in doc:
            if isinstance(obj, dict) and ("Species" in obj or "species" in obj):
                out.append((doc, obj))
    elif isinstance(doc, dict):
        if ("Species" in doc or "species" in doc):
            out.append((None, doc))
    return out


def inject_genders_in_obj(obj: dict, genders_str: str) -> bool:
    """
    Insère/met à jour "Other Information" -> "Genders" avec placement:
      - après "Size" (prioritaire), sinon après "Size Information",
      - sinon avant "Diet",
      - sinon en tête.
    Retourne True si modifié.
    """
    changed = False
    other = obj.get("Other Information") or obj.get("Other information")

    # Créer le bloc si absent
    if not isinstance(other, dict):
        obj["Other Information"] = {"Genders": genders_str}
        return True

    prev = other
    has_size = "Size" in prev
    has_size_info = "Size Information" in prev
    has_diet = "Diet" in prev

    # Reconstruire en respectant l'ordre
    new_other = {}
    inserted = False

    # Cas 1: taille présente -> insérer juste après "Size"
    if has_size:
        for k, v in prev.items():
            new_other[k] = v
            if k == "Size" and not inserted:
                if prev.get("Genders") != genders_str:
                    changed = True
                new_other["Genders"] = genders_str
                inserted = True

    # Cas 2: pas "Size" mais "Size Information" présente -> insérer après "Size Information"
    elif has_size_info:
        for k, v in prev.items():
            new_other[k] = v
            if k == "Size Information" and not inserted:
                if prev.get("Genders") != genders_str:
                    changed = True
                new_other["Genders"] = genders_str
                inserted = True

    else:
        # Cas 3: insérer avant Diet si present
        for k, v in prev.items():
            if k == "Diet" and not inserted:
                if prev.get("Genders") != genders_str:
                    changed = True
                new_other["Genders"] = genders_str
                inserted = True
            new_other[k] = v

    # Si toujours pas inséré : en tête
    if not inserted:
        # Placer en tête = reconstruire avec Genders d'abord
        # (on refait pour s'assurer qu'il est bien en tout premier)
        head_first = {"Genders": genders_str}
        if prev.get("Genders") != genders_str:
            changed = True
        for k, v in new_other.items() if new_other else prev.items():
            if k == "Genders":
                continue
            head_first[k] = v
        new_other = head_first

    obj["Other Information"] = new_other
    return changed


def process_file(path: Path, mapping: Dict[str, str]) -> Tuple[int, int]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return (0, 0)

    pairs = extract_species_objects(doc)
    if not pairs:
        return (0, 0)

    updates = 0
    for _, species_obj in pairs:
        name = species_obj.get("Species") or species_obj.get("species")
        if not isinstance(name, str):
            continue
        key = name.strip().lower()
        genders = mapping.get(key)
        if not genders:
            continue
        if inject_genders_in_obj(species_obj, genders):
            updates += 1

    if updates > 0:
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    return (len(pairs), updates)


def main() -> None:
    ap = argparse.ArgumentParser(description="Injecte 'Other Information' -> 'Genders' dans des JSON (récursif), placé après Size (ou Size Information) et avant Diet.")
    ap.add_argument("--source", required=True, help="Fichier JSON source (avec 'Other Information'.Genders ou 'gender_distribution').")
    ap.add_argument("--target-dir", required=True, help="Dossier racine des JSON à mettre à jour (récursif).")
    ap.add_argument("--dry-run", action="store_true", help="N'écrit rien ; affiche seulement le bilan.")
    args = ap.parse_args()

    source_path = Path(args.source)
    target_root = Path(args.target_dir)

    if not source_path.exists():
        raise SystemExit(f"[err] Source introuvable: {source_path}")
    if not target_root.is_dir():
        raise SystemExit(f"[err] Dossier cible introuvable: {target_root}")

    mapping = load_source_mapping(source_path)
    if not mapping:
        raise SystemExit("[warn] Aucun 'Genders' exploitable trouvé dans la source.")

    files = find_json_files_recursive(target_root)
    total_species = 0
    total_updates = 0

    for f in files:
        nsp, nup = process_file(f, mapping) if not args.dry_run else (0, 0)
        if args.dry_run:
            # Estimation dry-run
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            pairs = extract_species_objects(doc)
            if not pairs:
                continue
            upd = 0
            for _, species_obj in pairs:
                name = species_obj.get("Species") or species_obj.get("species")
                if isinstance(name, str) and name.strip().lower() in mapping:
                    genders = mapping[name.strip().lower()]
                    # Simule si différent
                    cur_oi = species_obj.get("Other Information") or {}
                    cur_g = cur_oi.get("Genders")
                    if cur_g != genders:
                        upd += 1
            nsp = len(pairs)
            nup = upd

        if nup:
            print(f"[ok] {f}: {nup}/{nsp} espèce(s) mise(s) à jour.")
        total_species += nsp
        total_updates += nup

    print(f"[bilan] Fichiers: {len(files)} | Espèces vues: {total_species} | Mises à jour: {total_updates}")


if __name__ == "__main__":
    main()
