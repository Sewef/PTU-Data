#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pragmatic per-page Base Stats injector:

- On each PDF page:
  * Species name = FIRST non-empty line.
  * Capture stats using straightforward regexes:
      "HP <num>", "ATK <num>", "DEF <num>",
      "Sp.ATK <num>", "Sp.DEF <num>",
      "SPD <num>" (or "Spe <num>" or "Speed <num>").
    (Case-insensitive; accepts "Attack"/"Defense", "SpA"/"SpD", optional dots/spaces.)
  * Ignore any "Total" numbers.

- If text extraction returns nothing, fall back to OCR (PyMuPDF + Tesseract).

Usage:
  python inject_base_stats_from_pdf_pages.py \
    --pdf "Community Gen 9 Homebrew Dex.pdf" \
    --pokedex-in pokedex.json \
    --pokedex-out pokedex.out.json \
    [--mapping name_map.csv] \
    [--dpi 200] \
    [--force-ocr] \
    [--debug]

Requires:
  pip install pdfminer.six PyPDF2 pymupdf pytesseract
  and Tesseract OCR installed & in PATH (Windows build: https://github.com/UB-Mannheim/tesseract/wiki)
"""

import argparse, csv, json, re, sys, unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
def normalize(s: str) -> str:
    # Normalize unicode & spaces
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u00A0", " ").replace("\u2009", " ").replace("\u202F", " ")
    s = s.replace("：", ":").replace("＝", "=")
    # Collapse horizontal spaces, keep newlines
    s = re.sub(r"[ \t]+", " ", s)
    return s

def text_from_pdf(pdf_path: Path) -> List[str]:
    """Return list of page texts using pdfminer/PyPDF2 (no OCR)."""
    pages: List[str] = []
    # Try pdfminer first
    try:
        from pdfminer.high_level import extract_text_to_fp
        from pdfminer.layout import LAParams
        import io
        with open(pdf_path, "rb") as f:
            output = io.StringIO()
            extract_text_to_fp(f, output, laparams=LAParams(), output_type="text", codec=None)
            whole = output.getvalue()
        # Split by form feed if present, else naive split on '\f'
        parts = whole.split("\f")
        if len(parts) > 1:
            pages = parts
        else:
            pages = [whole]
        return [normalize(p) for p in pages]
    except Exception as e:
        sys.stderr.write(f"[INFO] pdfminer failed ({e}); trying PyPDF2...\n")
    # PyPDF2 fallback
    try:
        import PyPDF2
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for pg in reader.pages:
                try:
                    txt = pg.extract_text() or ""
                except Exception as e2:
                    sys.stderr.write(f"[WARN] PyPDF2 page error: {e2}\n")
                    txt = ""
                pages.append(normalize(txt))
    except Exception as e:
        sys.stderr.write(f"[INFO] PyPDF2 failed ({e}).\n")
    return pages

def text_from_pdf_ocr(pdf_path: Path, dpi: int) -> List[str]:
    """OCR each page with PyMuPDF + Tesseract."""
    try:
        import fitz  # PyMuPDF
    except Exception as e:
        raise RuntimeError("PyMuPDF (fitz) is required for OCR fallback. pip install pymupdf") from e
    try:
        import pytesseract
    except Exception as e:
        raise RuntimeError("pytesseract is required for OCR fallback. pip install pytesseract and install Tesseract OCR engine.") from e

    doc = fitz.open(str(pdf_path))
    out: List[str] = []
    for page in doc:
        mat = fitz.Matrix(dpi/72.0, dpi/72.0)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        import tempfile, os
        tmp_png = Path(tempfile.gettempdir()) / f"_ocr_{os.getpid()}_{page.number+1}.png"
        pix.save(str(tmp_png))
        txt = pytesseract.image_to_string(str(tmp_png), lang="eng")
        try:
            tmp_png.unlink(missing_ok=True)
        except Exception:
            pass
        out.append(normalize(txt))
    return out

# Pragmatic patterns
RE_HP   = re.compile(r"\bHP\b\s*[:=]?\s*(\d{1,3})", re.IGNORECASE)
RE_ATK  = re.compile(r"\b(?:ATK|Atk|Attack)\b\s*[:=]?\s*(\d{1,3})", re.IGNORECASE)
RE_DEF  = re.compile(r"\b(?:DEF|Def|Defense)\b\s*[:=]?\s*(\d{1,3})", re.IGNORECASE)
RE_SPA  = re.compile(r"\b(?:Sp\.?\s*ATK|SpA|Special\s*ATK|Special\s*Attack)\b\s*[:=]?\s*(\d{1,3})", re.IGNORECASE)
RE_SPDf = re.compile(r"\b(?:Sp\.?\s*DEF|SpD|Special\s*DEF|Special\s*Defense)\b\s*[:=]?\s*(\d{1,3})", re.IGNORECASE)
RE_SPE  = re.compile(r"\b(?:SPD|Spe|Speed)\b\s*[:=]?\s*(\d{1,3})", re.IGNORECASE)
RE_TOTAL= re.compile(r"\bTotal\b\s*[:=]?\s*(\d{1,3})", re.IGNORECASE)

def first_nonempty_line(text: str) -> Optional[str]:
    for ln in text.splitlines():
        s = ln.strip()
        if s:
            return s
    return None

def parse_page_stats(text: str) -> Optional[Tuple[int,int,int,int,int,int]]:
    # 0) virer "Total: xx" pour éviter les faux positifs
    t = RE_TOTAL.sub("", text)

    # 1) Récupérer Sp.ATK et Sp.DEF d'abord
    spa_m = RE_SPA.search(t)
    spdf_m = RE_SPDf.search(t)
    spa_val = int(spa_m.group(1)) if spa_m else None
    spdf_val = int(spdf_m.group(1)) if spdf_m else None

    # 2) MASQUER ces segments pour que ATK/DEF/Speed ne matchent pas dedans
    masked = list(t)
    for m in (spa_m, spdf_m):
        if m:
            for i in range(m.start(), m.end()):
                masked[i] = "§"   # remplace par un char neutre
    t2 = "".join(masked)

    # 3) Chercher le reste sur le texte masqué
    hp_m  = RE_HP.search(t2)
    atk_m = RE_ATK.search(t2)
    def_m = RE_DEF.search(t2)
    spe_m = RE_SPE.search(t2)

    if all([hp_m, atk_m, def_m, spa_val is not None, spdf_val is not None, spe_m]):
        return (int(hp_m.group(1)),
                int(atk_m.group(1)),
                int(def_m.group(1)),
                int(spa_val),
                int(spdf_val),
                int(spe_m.group(1)))
    return None


def load_mapping_csv(path: Optional[Path]) -> Dict[str, str]:
    if not path: return {}
    mapping: Dict[str, str] = {}
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pdf_name = (row.get("pdf_name") or "").strip()
            species = (row.get("species") or "").strip()
            if pdf_name and species:
                mapping[pdf_name] = species
    return mapping

def inject_stats(pokedex: List[dict], name: str, vals: Tuple[int,int,int,int,int,int], mapping: Dict[str,str]) -> bool:
    by_exact: Dict[str, int] = {}
    by_lower: Dict[str, int] = {}
    for i,e in enumerate(pokedex):
        sp = e.get("Species")
        if isinstance(sp, str):
            by_exact[sp] = i
            by_lower[sp.lower()] = i
    target = mapping.get(name, name)
    idx = by_exact.get(target, by_lower.get(target.lower()))
    if idx is None:
        return False
    hp, atk, de, spa, spd, spe = vals
    pokedex[idx]["Base Stats"] = {
        "HP": hp, "Attack": atk, "Defense": de,
        "Special Attack": spa, "Special Defense": spd, "Speed": spe
    }
    return True

def main():
    ap = argparse.ArgumentParser(description="Pragmatic per-page Base Stats injector")
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--pokedex-in", required=True)
    ap.add_argument("--pokedex-out", required=True)
    ap.add_argument("--mapping", default=None, help="Optional CSV pdf_name,species")
    ap.add_argument("--dpi", type=int, default=200, help="OCR DPI (default 200)")
    ap.add_argument("--force-ocr", action="store_true", help="Use OCR for all pages")
    ap.add_argument("--debug", action="store_true", help="Print per-page parsing diagnostics")
    args = ap.parse_args()

    pdf_path = Path(args.pdf)
    mapping = load_mapping_csv(Path(args.mapping) if args.mapping else None)

    pages = []
    if args.force_ocr:
        pages = text_from_pdf_ocr(pdf_path, args.dpi)
    else:
        pages = text_from_pdf(pdf_path)
        if not any(p.strip() for p in pages):
            sys.stderr.write("[INFO] Text extractor empty; falling back to OCR.\n")
            pages = text_from_pdf_ocr(pdf_path, args.dpi)

    with open(args.pokedex_in, "r", encoding="utf-8") as f:
        pokedex = json.load(f)
        if not isinstance(pokedex, list):
            raise SystemExit("pokedex-in must be an array of species objects")

    updated = 0
    missed  = 0
    for i, page_text in enumerate(pages, start=1):
        if not page_text or not page_text.strip():
            if args.debug:
                print(f"[PAGE {i}] empty")
            continue
        name = first_nonempty_line(page_text)
        vals = parse_page_stats(page_text)
        if args.debug:
            print(f"[PAGE {i}] name={name!r} vals={vals}")
        if not name or not vals:
            missed += 1
            continue
        ok = inject_stats(pokedex, name, vals, mapping)
        if ok:
            updated += 1
        else:
            missed += 1

    print(json.dumps({
        "pages_seen": len(pages),
        "species_updated": updated,
        "pages_missed": missed
    }, ensure_ascii=False, indent=2))

    with open(args.pokedex_out, "w", encoding="utf-8") as f:
        json.dump(pokedex, f, ensure_ascii=False, indent=2)
    print(f"Wrote updated pokedex to: {args.pokedex_out}")

if __name__ == "__main__":
    main()
