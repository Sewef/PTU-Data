"""
Extracts HTML tables from keywords and abilities JSON files and converts them to structured JSON format.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from html.parser import HTMLParser


class TableParser(HTMLParser):
    """Parser to extract table data from HTML."""
    
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_thead = False
        self.in_tbody = False
        self.in_tr = False
        self.in_th = False
        self.in_td = False
        self.current_row = []
        self.header_rows = []
        self.data_rows = []
        self.current_cell = ""
        self.current_attrs = {}
        
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        if tag == "table":
            self.in_table = True
        elif tag == "thead":
            self.in_thead = True
        elif tag == "tbody":
            self.in_tbody = True
        elif tag == "tr":
            self.in_tr = True
            self.current_row = []
        elif tag == "th":
            self.in_th = True
            self.current_cell = ""
            self.current_attrs = attrs_dict
        elif tag == "td":
            self.in_td = True
            self.current_cell = ""
            self.current_attrs = attrs_dict
    
    def handle_endtag(self, tag):
        if tag == "table":
            self.in_table = False
        elif tag == "thead":
            self.in_thead = False
        elif tag == "tbody":
            self.in_tbody = False
        elif tag == "tr":
            self.in_tr = False
            if self.current_row:
                if self.in_thead:
                    self.header_rows.append(self.current_row)
                else:
                    self.data_rows.append(self.current_row)
            self.current_row = []
        elif tag == "th":
            self.in_th = False
            cell_data = {"text": self.current_cell.strip()}
            
            # Add colspan/rowspan if present
            if "colspan" in self.current_attrs:
                cell_data["colspan"] = int(self.current_attrs["colspan"])
            if "rowspan" in self.current_attrs:
                cell_data["rowspan"] = int(self.current_attrs["rowspan"])
                
            self.current_row.append(cell_data)
            self.current_cell = ""
            self.current_attrs = {}
        elif tag == "td":
            self.in_td = False
            cell_data = {"text": self.current_cell.strip()}
            
            # Add colspan/rowspan if present
            if "colspan" in self.current_attrs:
                cell_data["colspan"] = int(self.current_attrs["colspan"])
            if "rowspan" in self.current_attrs:
                cell_data["rowspan"] = int(self.current_attrs["rowspan"])
                
            self.current_row.append(cell_data)
            self.current_cell = ""
            self.current_attrs = {}
    
    def handle_data(self, data):
        if self.in_th or self.in_td:
            self.current_cell += data
    
    def get_table_data(self) -> Optional[Dict[str, Any]]:
        """Returns the parsed table data in our standard format."""
        if not self.header_rows and not self.data_rows:
            return None
        
        return {
            "type": "table",
            "headerRows": 1,
            "rows": self.header_rows + self.data_rows
        }


def extract_table_from_html(html_text: str) -> Optional[Dict[str, Any]]:
    """Extract table data from HTML string."""
    parser = TableParser()
    try:
        parser.feed(html_text)
        return parser.get_table_data()
    except Exception as e:
        print(f"Error parsing HTML: {e}")
        return None


def process_keyword_value(keyword_value: Any, keyword_name: str) -> Dict[str, Any]:
    """
    Process a keyword value, extracting any table and returning cleaned structure.
    
    Args:
        keyword_value: Can be a string (original format) or dict (already processed)
        keyword_name: Name of the keyword
        
    Returns:
        dict: Keyword object with Description and optionally table
    """
    # If already processed (dict with Description), update it
    if isinstance(keyword_value, dict):
        result = keyword_value.copy()

        if isinstance(result.get("Description"), str):
            result["Description"] = re.sub(r'\s*\{\{table:[^}]+\}\}\s*', ' ', result["Description"]).strip()
        
        # Ensure headerRows is set in table if present
        if "table" in result and isinstance(result["table"], dict):
            if result["table"].get("type") == "table":
                result["table"]["headerRows"] = 1
        
        return result
    
    # Original processing for string values
    value = str(keyword_value)
    
    # Check if there's a table in the value
    if "<table" not in value:
        return {"Description": value}
    
    # Extract the table HTML
    table_match = re.search(r'<table.*?</table>', value, re.DOTALL | re.IGNORECASE)
    if not table_match:
        return {"Description": value}
    
    table_html = table_match.group(0)
    
    # Parse the table
    table_data = extract_table_from_html(table_html)
    
    if not table_data:
        return {"Description": value}
    
    # Find the collapse div that contains the table
    collapse_pattern = r'<button[^>]*data-bs-toggle="collapse"[^>]*>.*?</button>\s*<div[^>]*class="collapse[^"]*"[^>]*>.*?</div>'
    
    # Try to find and extract the entire collapsible section
    collapse_match = re.search(collapse_pattern, value, re.DOTALL | re.IGNORECASE)
    
    if collapse_match:
        # Replace the entire collapsible section with a table reference
        cleaned_text = value[:collapse_match.start()] + f'{{{{table:{keyword_name}}}}}' + value[collapse_match.end():]
        cleaned_text = cleaned_text.strip()
    else:
        # Fallback: just replace the table
        cleaned_text = value.replace(table_html, f'{{{{table:{keyword_name}}}}}').strip()
    
    result = {"Description": cleaned_text}
    if table_data:
        result["table"] = table_data
    
    return result


def process_keywords_file(input_path: Path, output_path: Path = None):
    """
    Process a keywords JSON file, extracting tables and creating a clean structure.
    """
    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}_converted{input_path.suffix}"
    
    print(f"Reading {input_path}...")
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("Processing keywords...")
    converted_data = {}
    tables_data = {}
    
    for keyword_name, keyword_value in data.items():
        keyword_obj = process_keyword_value(keyword_value, keyword_name)
        
        if "table" in keyword_obj:
            tables_data[keyword_name] = keyword_obj["table"]
            print(f"  ✓ Processed table for: {keyword_name}")
        
        converted_data[keyword_name] = keyword_obj
    
    print(f"Writing to {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(converted_data, f, indent=2, ensure_ascii=False)
    
    # Also save a separate tables file for reference
    tables_path = output_path.parent / f"{output_path.stem}_tables.json"
    with open(tables_path, 'w', encoding='utf-8') as f:
        json.dump(tables_data, f, indent=2, ensure_ascii=False)
    
    print(f"Tables saved to: {tables_path}")
    print("Done!")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Extract tables from keywords/abilities JSON files"
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Input JSON file to process"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Output file path (default: input_converted.json)"
    )
    
    args = parser.parse_args()
    
    process_keywords_file(args.input, args.output)


if __name__ == "__main__":
    main()
