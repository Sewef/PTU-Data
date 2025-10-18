#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
import csv
import glob
from pathlib import Path
from bs4 import BeautifulSoup

INPUT_GLOB = "dump_html/serebii_gen*_updatedstats.html"
OUT_CSV = "fooextra_changes_gen6_to_gen9.csv"

# Ordre d’affichage des stats dans les tableaux Serebii (après la colonne "Game")
STAT_NAMES = ["HP", "Att", "Def", "SpA", "SpD", "Spe"]

def is_int_cell_text(txt: str) -> bool:
    return bool(re.fullmatch(r"\d{1,3}", (txt or "").strip()))

def td_classes(td):
    return [c.lower() for c in (td.get("class") or [])]

def pick_name_from_row(tr):
    """Récupère le nom affiché (ex: 'Arbok アーボック' -> 'Arbok')."""
    for td in tr.find_all("td"):
        t = td.get_text(" ", strip=True)
        if t and not t.startswith("#") and re.search(r"[A-Za-z]", t):
            # éviter les étiquettes de jeu type 'Su/Mo', 'X/Y', 'US/UM', etc.
            if t in {"Su/Mo","US/UM","X/Y","Sw/Sh","BD/SP","SV"}:
                continue
            return t.split(" ")[0]  # on garde le nom anglais simple
    return ""

def extract_row_stats(tr):
    """Renvoie (vals, classes) pour les 6 dernières valeurs entières de la ligne."""
    vals, classes = [], []
    for td in tr.find_all("td"):
        txt = td.get_text(" ", strip=True)
        if is_int_cell_text(txt):
            vals.append(int(txt))
            classes.append(td_classes(td))
    if len(vals) < 6:
        return None, None
    return vals[-6:], classes[-6:]

def parse_file(path):
    """Retourne une liste de dicts {gen,name,stat,old,new,delta} pour un fichier dumpé."""
    m = re.search(r"gen(\d+)", os.path.basename(path).lower())
    gen = int(m.group(1)) if m else None

    html = Path(path).read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "lxml")

    rows = soup.find_all("tr")
    out = []
    i = 0
    while i < len(rows):
        tr_after = rows[i]
        tds = tr_after.find_all("td")
        if not tds:
            i += 1
            continue

        texts = [td.get_text(" ", strip=True) for td in tds]
        # Heuristique "ligne après" : contient un #NNN et au moins 6 entiers (les stats)
        is_after_row = any(txt.startswith("#") for txt in texts) and sum(is_int_cell_text(x) for x in texts) >= 6
        if not is_after_row:
            i += 1
            continue

        name = pick_name_from_row(tr_after)
        vals_after, cls_after = extract_row_stats(tr_after)
        if not vals_after:
            i += 1
            continue

        # Cherche la "ligne avant" suivante (avec au moins 6 entiers)
        j = i + 1
        found_before = False
        while j < len(rows):
            tr_before = rows[j]
            tds_b = tr_before.find_all("td")
            if not tds_b:
                j += 1
                continue

            texts_b = [td.get_text(" ", strip=True) for td in tds_b]
            if sum(is_int_cell_text(x) for x in texts_b) >= 6:
                vals_before, cls_before = extract_row_stats(tr_before)
                if not vals_before:
                    j += 1
                    continue

                # positions modifiées = 'fooextra' dans l'une des 2 lignes
                changed_mask = []
                for ca, cb in zip(cls_after, cls_before):
                    has = ("fooextra" in (ca or [])) or ("fooextra" in (cb or []))
                    changed_mask.append(has)

                for idx, changed in enumerate(changed_mask):
                    if not changed:
                        continue
                    old_v = vals_before[idx]
                    new_v = vals_after[idx]
                    if old_v == new_v:
                        continue
                    out.append({
                        "gen": gen,
                        "name": name or "",
                        "stat": STAT_NAMES[idx],
                        "old": old_v,
                        "new": new_v,
                        "delta": new_v - old_v,
                    })
                i = j  # on saute directement à la ligne "avant"
                found_before = True
                break
            j += 1

        # si on n'a pas trouvé de ligne "avant", on avance d'une ligne quand même
        if not found_before:
            i += 1
        else:
            i += 1

    return out

def main():
    files = sorted(glob.glob(INPUT_GLOB))
    if not files:
        print(f"[WARN] Aucun fichier trouvé pour {INPUT_GLOB}")
        return

    all_rows = []
    for fp in files:
        rows = parse_file(fp)
        print(f"[info] {os.path.basename(fp)} -> {len(rows)} changements relevés (fooextra)")
        all_rows.extend(rows)

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["gen", "name", "stat", "old", "new", "delta"])
        for r in all_rows:
            w.writerow([r["gen"], r["name"], r["stat"], r["old"], r["new"], r["delta"]])

    print(f"[OK] CSV écrit : {OUT_CSV}")

if __name__ == "__main__":
    main()
