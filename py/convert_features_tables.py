#!/usr/bin/env python3
# coding: utf-8
"""
Convert embedded HTML <table> blocks inside "Effect" fields of a JSON (features file)
into structured arrays + a _display config compatible with the new viewer.

Usage:
  python convert_features_tables.py -i features_core.json -o features_core.converted.json

Requirements:
  - beautifulsoup4

If not installed:
  pip install beautifulsoup4
"""

from __future__ import annotations
import argparse
import json
import re
from copy import deepcopy
from typing import Any, Dict, List, Tuple, Optional

try:
    from bs4 import BeautifulSoup
except Exception as e:
    raise SystemExit("This script requires 'beautifulsoup4'. Install it with: pip install beautifulsoup4")


# --------------------------- Utilities -------------------------------------

def clean_text(s: Any) -> str:
    if s is None:
        return ""
    text = str(s)
    # Normalize spaces and newlines
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    return text.strip()


def soup_from_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


# ------------------------ Table Parsing Core --------------------------------

class Table:
    def __init__(self, title: str, columns: List[str], rows: List[Dict[str, str]]):
        self.title = title
        self.columns = columns
        self.rows = rows

    def to_display_meta(self, transpose: bool = False) -> Dict[str, Any]:
        if not transpose:
            return {
                "type": "table",
                "rowPerField": False,
                "columns": self.columns
            }
        else:
            return {
                "type": "table",
                "rowPerField": True,
                "idField": self.columns[0] if self.columns else None
            }


def parse_html_table(tbl) -> Tuple[List[List[str]], List[List[str]]]:
    """
    Parse a <table> into (header_rows, body_rows) as fully expanded text grids.
    Handles colspan / rowspan.
    Header rows may be empty if no <thead> is present.
    """
    # Collect header <tr>s
    header_trs = []
    thead = tbl.find("thead")
    if thead:
        header_trs = thead.find_all("tr")
    else:
        # Some tables put header in the first row of <tbody> or directly in <table>
        # We'll detect later if needed; for now no explicit thead rows.
        header_trs = []

    # Collect body <tr>s (includes all <tbody> trs; if none, fallback to direct <tr> under table)
    body_trs = []
    tbodies = tbl.find_all("tbody")
    if tbodies:
        for b in tbodies:
            body_trs.extend(b.find_all("tr"))
    else:
        # fallback: direct trs minus those in a thead
        for tr in tbl.find_all("tr", recursive=False):
            if tr.find_parent("thead") is None:
                body_trs.append(tr)

    header_rows = expand_table_rows(header_trs)
    body_rows = expand_table_rows(body_trs)

    # If no explicit header rows, try to infer header from the first body row if it's <th> cells
    if not header_rows and body_trs:
        first = body_trs[0]
        if first.find("th"):
            # use first body row as header
            head_tmp = expand_table_rows([first])
            header_rows = head_tmp
            # and remove it from body
            body_rows = expand_table_rows(body_trs[1:])

    return header_rows, body_rows


def expand_table_rows(tr_list) -> List[List[str]]:
    """
    Expand a list of <tr> into a rectangular grid of strings (apply colspan/rowspan).
    """
    grid: List[List[Optional[str]]] = []
    # Track active rowspans: list of counters per column index
    rowspans: List[int] = []

    for tr in tr_list:
        # Ensure rowspans list is at least as long as current max columns
        max_cols = len(rowspans)
        row: List[Optional[str]] = []
        col_idx = 0

        # Pre-fill with None until we skip active rowspans
        def next_free_col(start_idx: int) -> int:
            i = start_idx
            while True:
                # extend trackers if needed
                if i >= len(rowspans):
                    rowspans.extend([0] * (i - len(rowspans) + 1))
                if i >= len(row):
                    row.extend([None] * (i - len(row) + 1))
                # skip columns occupied by rowspan
                if rowspans[i] > 0:
                    i += 1
                else:
                    return i

        # apply carried rowspans as empty cells (will be filled below if needed)
        for i in range(len(rowspans)):
            if rowspans[i] > 0:
                # reserve a slot
                if i >= len(row):
                    row.extend([None] * (i - len(row) + 1))
                # Decrease rowspan counter for this column (one row consumed)
                rowspans[i] -= 1

        cells = tr.find_all(["th", "td"])
        for cell in cells:
            # find next free column index
            col_idx = next_free_col(col_idx)
            text = clean_text(cell.get_text(separator=" ", strip=True))
            colspan = int(cell.get("colspan", 1) or 1)
            rowspan = int(cell.get("rowspan", 1) or 1)

            # place this cell text into the grid for colspan cells
            for j in range(colspan):
                c = col_idx + j
                if c >= len(row):
                    row.extend([None] * (c - len(row) + 1))
                row[c] = text

            # mark rowspans for all spanned columns (minus 1 because current row is occupied)
            if rowspan > 1:
                for j in range(colspan):
                    c = col_idx + j
                    if c >= len(rowspans):
                        rowspans.extend([0] * (c - len(rowspans) + 1))
                    rowspans[c] = max(rowspans[c], rowspan - 1)

            # move pointer
            col_idx = col_idx + colspan

        # Normalize row length to current number of columns
        width = max(len(row), len(rowspans))
        if len(row) < width:
            row.extend([None] * (width - len(row)))

        grid.append([clean_text(x) if x is not None else "" for x in row])

    # Normalize all rows to equal length
    maxw = max((len(r) for r in grid), default=0)
    for r in grid:
        if len(r) < maxw:
            r.extend([""] * (maxw - len(r)))
    return grid


def build_column_names(header_rows: List[List[str]]) -> List[str]:
    if not header_rows:
        return []

    # For each column, stack header parts (top to bottom), keep non-empty unique parts
    width = max(len(r) for r in header_rows)
    cols: List[str] = []
    for c in range(width):
        parts = []
        seen = set()
        for r in header_rows:
            if c >= len(r): 
                continue
            part = clean_text(r[c])
            if not part:
                continue
            key = part.lower()
            if key in seen:
                continue
            seen.add(key)
            parts.append(part)

        if not parts:
            cols.append(f"C{c+1}")
            continue

        name = " ".join(parts)

        # Heuristics to avoid duplicates like "Moves Move"
        name = re.sub(r"\bMoves?\s+Moves?\b", "Move", name, flags=re.I)
        name = re.sub(r"\bMoves?\s+Prerequisites?\b", "Prerequisites", name, flags=re.I)
        name = re.sub(r"\bMove\s+Prerequisites?\b", "Prerequisites", name, flags=re.I)
        name = re.sub(r"\s+", " ", name).strip()
        cols.append(name)
    return cols


def guess_table_title(columns: List[str], default_base: str, index: int) -> str:
    joined = " | ".join(columns).lower()
    if "rank" in joined and "move" in joined:
        return "Moves by Rank"
    if "prereq" in joined or "prerequisites" in joined:
        return "Requirements Table"
    return f"{default_base} {index+1}"


def table_to_rows(columns: List[str], body_rows: List[List[str]]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for r in body_rows:
        row = {}
        for i, col in enumerate(columns):
            val = r[i] if i < len(r) else ""
            row[col] = clean_text(val) if val is not None else ""
        rows.append(row)
    return rows


# ---------------------- Effect processing -----------------------------------

def strip_tables_from_effect(effect_html: str) -> Tuple[str, List[Table]]:
    soup = soup_from_html(effect_html)
    tables = soup.find_all("table")
    out_tables: List[Table] = []

    # Parse each table
    for idx, tbl in enumerate(tables):
        headers, body = parse_html_table(tbl)
        columns = build_column_names(headers)
        # If no header, invent generic C1..
        if not columns and body:
            columns = [f"C{i+1}" for i in range(max(len(r) for r in body))]

        rows = table_to_rows(columns, body)
        title = guess_table_title(columns, "Extracted Table", idx)
        out_tables.append(Table("", columns, rows))

    # Remove tables from effect and return remaining text
    for t in tables:
        t.decompose()

    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, out_tables


def merge_unique_key(d: Dict[str, Any], base_key: str) -> str:
    """Find a unique key name not colliding with existing keys in dict d."""
    if base_key not in d:
        return base_key
    i = 2
    while True:
        candidate = f"{base_key} ({i})"
        if candidate not in d:
            return candidate
        i += 1


def process_feature_obj(obj: Dict[str, Any], transpose: bool = False) -> Tuple[Dict[str, Any], bool]:
    """
    Process a single feature dict in place-like (returning a new dict),
    extracting HTML tables from 'Effect' (if any) and injecting arrays + _display.
    Returns (new_obj, changed_flag).
    """
    changed = False
    new_obj = deepcopy(obj)

    # Recurse into children first
    for k, v in list(new_obj.items()):
        if isinstance(v, dict):
            new_obj[k], ch = process_feature_obj(v, transpose=transpose)
            changed = changed or ch
        elif isinstance(v, list):
            new_list = []
            any_change = False
            for item in v:
                if isinstance(item, dict):
                    new_item, ch = process_feature_obj(item, transpose=transpose)
                    any_change = any_change or ch
                    new_list.append(new_item)
                else:
                    new_list.append(item)
            if any_change:
                new_obj[k] = new_list
                changed = True

    # Now handle this object's Effect if string with <table
    effect = new_obj.get("Effect")
    if isinstance(effect, str) and "<table" in effect.lower():
        txt, tables = strip_tables_from_effect(effect)
        if tables:
            # Ensure _display exists
            disp = dict(new_obj.get("_display") or {})
            for i, t in enumerate(tables):
                key = merge_unique_key(new_obj, t.title)
                # Inject the array under key
                new_obj[key] = t.rows
                # Set up _display mapping
                disp[key] = t.to_display_meta(transpose=transpose)
            new_obj["_display"] = disp

            # Rewrite Effect, append pointer to tables
            new_obj["Effect"] = txt
            changed = True

    return new_obj, changed


def process_root(data: Any, transpose: bool = False) -> Tuple[Any, int]:
    """
    Walk the whole JSON tree, processing any dict that *looks like* a feature
    (has an 'Effect' field). Returns updated data and number of changes.
    """
    change_count = 0

    def _walk(node):
        nonlocal change_count
        if isinstance(node, dict):
            new_node, changed = process_feature_obj(node, transpose=transpose)
            if changed:
                change_count += 1
            for k, v in list(new_node.items()):
                new_node[k] = _walk(v)
            return new_node
        elif isinstance(node, list):
            return [_walk(x) for x in node]
        else:
            return node

    out = _walk(data)
    return out, change_count


# ----------------------------- CLI -----------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Convert HTML tables embedded in 'Effect' fields into structured arrays + _display.")
    ap.add_argument("-i", "--input", required=True, help="Input features JSON path")
    ap.add_argument("-o", "--output", required=False, help="Output JSON path (default: <input>.converted.json)")
    ap.add_argument("--transpose", action="store_true", help="Render extracted tables in transposed mode (rowPerField=true)")
    ap.add_argument("--indent", type=int, default=2, help="Pretty-print indent (default: 2)")
    args = ap.parse_args()

    out_path = args.output or re.sub(r"\.json$", "", args.input) + ".converted.json"

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    new_data, count = process_root(data, transpose=args.transpose)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=args.indent)

    print(f"Done. Updated {count} object(s) that contained HTML tables.")
    print(f"Written: {out_path}")


if __name__ == "__main__":
    main()