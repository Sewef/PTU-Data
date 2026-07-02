"""
Converts dataTable and moveTable structures from grouped format to simplified row format.

Input format:
{
  "columns": ["Group1_1", "Group1_2", "Group2_1"],
  "groups": [
    {
      "label": "Group1",
      "rows": [{"Group1_1": "val1", "Group1_2": "val2"}, ...]
    },
    {
      "label": "Group2",
      "rows": [{"Group2_1": "val3"}, ...]
    }
  ]
}

Output format:
{
  "type": "table",
  "rows": [
    [{"text": "Group1", "colspan": 2}, {"text": "Group2", "colspan": 1}],
    [{"text": "Col1"}, {"text": "Col2"}, {"text": "Col1"}],
    [{"text": "val1"}, {"text": "val2"}, {"text": "val3"}],
    ...
  ]
}
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List


def extract_column_base_name(column: str) -> str:
    """
    Extracts the base name from a column name.
    Example: "Rank 1 Moves_1" -> "Rank 1 Moves"
    """
    match = re.match(r"^(.*?)(?:_\d+)?$", column)
    return match.group(1) if match else column


def convert_table(table_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converts a table from grouped format to simplified row format.
    """
    if not table_data or "columns" not in table_data or "groups" not in table_data:
        return table_data
    
    columns = table_data["columns"]
    groups = table_data["groups"]
    
    if not groups:
        return table_data
    
    # Build mapping of columns to groups and determine which columns each group uses
    column_to_group = {}
    group_columns = {}  # group_label -> list of columns used by that group
    
    for group in groups:
        group_label = group.get("label", "")
        group_columns[group_label] = []
        
        # Find which columns this group actually uses by checking the data
        if group.get("rows"):
            # Get all keys used in the rows of this group
            used_keys = set()
            for row in group["rows"]:
                if isinstance(row, dict):
                    used_keys.update(row.keys())
            
            # Map these keys to the column order
            for col in columns:
                if col in used_keys:
                    column_to_group[col] = group_label
                    group_columns[group_label].append(col)
    
    # Detect if first row contains column headers
    # If the first row values match typical header patterns, it's a header row
    has_header_row = False
    for group in groups:
        if group.get("rows"):
            first_row = group["rows"][0]
            # Check if first row looks like headers (e.g., contains words like "Move", "Prerequisite", etc.)
            # or if values are simple short strings
            if first_row and isinstance(first_row, dict):
                values = [str(v).strip() for v in first_row.values() if v]
                if values:
                    # Heuristic: if all values are short (< 30 chars) and contain common header words
                    # or if columns don't match the group label pattern
                    header_words = ["move", "prerequisite", "name", "effect", "trainer", "class", "feature"]
                    has_keywords = any(any(word in val.lower() for word in header_words) for val in values)
                    all_short = all(len(val) < 30 for val in values)
                    
                    # Additional check: if columns are simple names without group prefix
                    simple_columns = not any("_" in col for col in columns)
                    
                    if (has_keywords or all_short) and not simple_columns:
                        has_header_row = True
                        break
    
    # Build header row with group labels and colspans
    group_header_row = []
    processed_groups = set()
    
    for col in columns:
        group_label = column_to_group.get(col)
        if group_label and group_label not in processed_groups:
            colspan = len(group_columns.get(group_label, []))
            if colspan > 0:
                group_header_row.append({
                    "text": group_label,
                    "colspan": colspan
                })
                processed_groups.add(group_label)
    
    # Build column header row
    column_header_row = []
    
    if has_header_row:
        # Use first row of each group as column headers
        for col in columns:
            group_label = column_to_group.get(col)
            if group_label:
                group = next((g for g in groups if g.get("label") == group_label), None)
                if group and group.get("rows"):
                    first_row = group["rows"][0]
                    col_name = first_row.get(col, "")
                    column_header_row.append({"text": str(col_name)})
    else:
        # Use column names directly
        for col in columns:
            if column_to_group.get(col):
                # Clean up column name (remove group prefix if present)
                col_display = col
                for group in groups:
                    group_label = group.get("label", "")
                    if col.startswith(group_label + "_"):
                        col_display = col[len(group_label) + 1:]
                        break
                column_header_row.append({"text": col_display})
    
    # Build data rows - collect data per column first, then transpose
    # This allows us to "compact" columns by moving data upwards
    column_data = {col: [] for col in columns}
    start_row_index = 1 if has_header_row else 0  # Skip first row if it's a header
    header_rows_count = 2  # Group row + column row
    
    for group in groups:
        rows = group.get("rows", [])
        group_label = group.get("label", "")
        group_cols = group_columns.get(group_label, [])
        
        # Collect data for each column in this group
        for row_data in rows[start_row_index:]:
            for col in group_cols:
                cell_value = row_data.get(col, "")
                column_data[col].append(str(cell_value))
    
    # Determine the maximum number of rows needed
    max_rows = max(len(data) for data in column_data.values()) if column_data else 0
    
    # Build data rows by transposing column data
    data_rows = []
    for row_idx in range(max_rows):
        data_row = []
        for col in columns:
            col_data = column_data.get(col, [])
            if row_idx < len(col_data):
                data_row.append({"text": col_data[row_idx]})
            else:
                data_row.append({"text": ""})
        
        # Only add row if it has some non-empty content
        if any(cell.get("text") for cell in data_row):
            data_rows.append(data_row)
    
    # Assemble final table structure
    result = {
        "type": "table",
        "headerRows": header_rows_count,
        "rows": [group_header_row, column_header_row] + data_rows
    }
    
    return result


def process_feature_recursively(obj: Any) -> Any:
    """
    Recursively processes a feature object, converting any dataTable or moveTable.
    """
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            if key in ("dataTable", "moveTable"):
                result[key] = convert_table(value)
            else:
                result[key] = process_feature_recursively(value)
        return result
    elif isinstance(obj, list):
        return [process_feature_recursively(item) for item in obj]
    else:
        return obj


def convert_features_file(input_path: Path, output_path: Path = None):
    """
    Converts all dataTable and moveTable in a features JSON file.
    """
    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}_converted{input_path.suffix}"
    
    print(f"Reading {input_path}...")
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("Converting tables...")
    converted_data = process_feature_recursively(data)
    
    print(f"Writing to {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(converted_data, f, indent=2, ensure_ascii=False)
    
    print("Done!")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Convert dataTable and moveTable structures to simplified format"
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Input JSON file to convert"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Output file path (default: input_converted.json)"
    )
    
    args = parser.parse_args()
    
    convert_features_file(args.input, args.output)


if __name__ == "__main__":
    main()
