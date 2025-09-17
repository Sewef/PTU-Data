#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Transform embedded HTML <table> blocks inside Feature "Effect" strings
into structured arrays + _display config for your front-end renderAsTable.

Usage:
  python transform_features_tables.py --input features_core.json --output features_core_transformed.json
  python transform_features_tables.py --inplace features_core.json
"""
import json, re, html, argparse, sys
from html.parser import HTMLParser
from copy import deepcopy

class _SimpleTableParser(HTMLParser):
    """Parse a single <table>..</table> snippet into (headers, rows)."""
    def __init__(self):
        super().__init__()
        self.in_table=False
        self.in_tr=False
        self.in_thead=False
        self.current_cell=None
        self.current_row=[]
        self.row_had_th=False
        self.headers=[]
        self.rows=[]
    def handle_starttag(self, tag, attrs):
        if tag=='table':
            self.in_table=True
        if not self.in_table: return
        if tag=='thead':
            self.in_thead=True
        if tag=='tr':
            self.in_tr=True
            self.current_row=[]
            self.row_had_th=False
        if tag in ('th','td'):
            self.current_cell=[]
            if tag=='th':
                self.row_had_th=True
        if tag=='br' and self.current_cell is not None:
            self.current_cell.append('\n')
    def handle_endtag(self, tag):
        if not self.in_table: return
        if tag in ('th','td'):
            txt=''.join(self.current_cell).strip() if self.current_cell is not None else ''
            self.current_row.append(html.unescape(txt))
            self.current_cell=None
        if tag=='tr' and self.in_tr:
            if self.in_thead or (self.row_had_th and not self.headers):
                self.headers=self.current_row
            else:
                self.rows.append(self.current_row)
            self.in_tr=False
        if tag=='thead':
            self.in_thead=False
        if tag=='table':
            self.in_table=False
    def handle_data(self, data):
        if self.current_cell is not None:
            self.current_cell.append(data)
    def feed_table(self, html_snippet):
        self.__init__()
        self.feed(html_snippet)
        if not self.headers:
            maxlen=max((len(r) for r in self.rows), default=0)
            self.headers=[f"Column {i+1}" for i in range(maxlen)]
        norm=[]
        for r in self.rows:
            rr=r[:len(self.headers)] + ['']*(len(self.headers)-len(r))
            norm.append(rr)
        self.rows=norm
        return self.headers, self.rows

def _parse_tables_from_html(html_text):
    tables = re.findall(r'(<table\b.*?</table>)', html_text, flags=re.I|re.S)
    out=[]
    parser=_SimpleTableParser()
    for t in tables:
        headers, rows = parser.feed_table(t)
        out.append({'html': t, 'headers': headers, 'rows': rows})
    return out

def _propose_property_name(headers, existing_keys):
    """Heuristic: longest common suffix of headers (e.g. 'Moves'), add 'by Rank' if relevant."""
    import re
    tokenized=[h.strip().split() for h in headers if isinstance(h,str)]
    if not tokenized:
        base="Table"
    else:
        minlen=min(len(t) for t in tokenized)
        suffix=[]
        for i in range(1, minlen+1):
            wset={t[-i] for t in tokenized}
            if len(wset)==1:
                suffix.insert(0, tokenized[0][-i])
            else:
                break
        if suffix:
            base=" ".join(suffix)
            if any(re.search(r'\bRank\b', h, re.I) for h in headers) and not re.search(r'\bRank\b', base, re.I):
                base=f"{base} by Rank"
        else:
            base="Table"
    name=base
    i=2
    while name in existing_keys:
        name=f"{base} ({i})"; i+=1
    return name

def _transform_feature(feat):
    effect=feat.get("Effect")
    if not isinstance(effect,str) or '<table' not in effect:
        return False
    tables = _parse_tables_from_html(effect)
    if not tables:
        return False
    display = deepcopy(feat.get("_display") or {})
    new_props=[]
    new_effect = effect
    for t in tables:
        headers, rows = t['headers'], t['rows']
        arr=[{headers[i]: r[i] for i in range(len(headers))} for r in rows]
        prop_name=_propose_property_name(headers, set(feat.keys()) | set(new_props))
        feat[prop_name]=arr
        display[prop_name]={
            "type":"table",
            "rowPerField": False,
            "columns": headers,
            "columnWidths": ["16ch"]*len(headers)
        }
        new_props.append(prop_name)
        new_effect = new_effect.replace(t['html'], '')
    new_effect = re.sub(r'<div[^>]*>\s*</div>', '', new_effect, flags=re.I)
    new_effect = re.sub(r'<br\s*/?>', '\n', new_effect, flags=re.I)
    new_effect = re.sub(r'<[^>]+>', '', new_effect)
    new_effect = re.sub(r'[ \t]+', ' ', new_effect)
    new_effect = re.sub(r' *\n *', '\n', new_effect).strip()
    if new_props:
        list_phrase = " and ".join([f"'{p}'" for p in new_props])
        add = f" See the {list_phrase} " + ("tables." if len(new_props)>1 else "table.")
        if new_effect and not re.search(r'[.!?]$', new_effect):
            new_effect += "."
        new_effect += add
    feat["Effect"]=new_effect
    feat["_display"]=display
    return True

def transform_json(doc):
    modified=0
    for cat, obj in (doc.items() if isinstance(doc, dict) else []):
        if not isinstance(obj, dict): continue
        for br in obj.get("branches", []):
            feats = br.get("features", [])
            for feat in feats:
                if isinstance(feat, dict) and _transform_feature(feat):
                    modified+=1
    return modified, doc

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", "-i", required=True, help="Path to features_core.json")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", "-o", help="Write transformed JSON to this path")
    group.add_argument("--inplace", action="store_true", help="Modify the input file in place")
    args = ap.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
      doc = json.load(f)

    modified, new_doc = transform_json(doc)
    if modified == 0:
        print("No features with <table> found. Nothing changed.")
    else:
        print(f"Transformed {modified} feature(s).")

    dest = args.input if args.inplace else args.output
    if not dest:
        print("No output destination provided.", file=sys.stderr)
        sys.exit(2)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(new_doc, f, ensure_ascii=False, indent=2)
    print(f"Wrote: {dest}")

if __name__ == "__main__":
    main()
