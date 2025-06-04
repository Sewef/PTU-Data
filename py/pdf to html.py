import fitz  # PyMuPDF
import os
from pathlib import Path
from zipfile import ZipFile
import re
from html import escape

def extract_styled_text(page):
    """Extract text with font styles and structure."""
    html_lines = []
    blocks = page.get_text("dict")["blocks"]

    for block in blocks:
        for line in block.get("lines", []):
            line_text = ""
            for span in line["spans"]:
                text = escape(span["text"])
                if not text.strip():
                    continue
                if span.get("flags", 0) & 2:  # Bold
                    text = f"<b>{text}</b>"
                if span.get("flags", 0) & 1:  # Italic
                    text = f"<i>{text}</i>"
                line_text += text
            html_lines.append(f"<p>{line_text}</p>")
    return "\n".join(html_lines)

def extract_sections_rich(doc):
    """Split the document into sections by headings (trainer class names)."""
    all_html = []
    sections = {}
    current_section = "Introduction"
    current_content = []

    for page in doc:
        html = extract_styled_text(page)
        all_html.append(html)

        # Split by "Trainer Classes" + page number + section name
        matches = re.findall(r"Trainer Classes\s+\d+\s+([A-Z][A-Za-z ]+)", page.get_text())
        for match in matches:
            if current_content:
                sections[current_section] = "\n".join(current_content)
                current_content = []
            current_section = match.strip()

        current_content.append(html)

    sections[current_section] = "\n".join(current_content)
    return sections, "\n".join(all_html)

def wrap_html(title, body):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 20px; }}
    h1, h2, h3 {{ color: #2b3a42; }}
    b {{ font-weight: bold; }}
    i {{ font-style: italic; }}
  </style>
</head>
<body>
<h1>{title}</h1>
{body}
</body>
</html>
"""

def convert_pdf_to_html_with_style(pdf_path, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    doc = fitz.open(pdf_path)
    sections, full_html_body = extract_sections_rich(doc)

    # Full HTML file
    full_html_path = output_dir / "ptu_classes_full.html"
    with open(full_html_path, "w", encoding="utf-8") as f:
        f.write(wrap_html("PTU Trainer Classes", full_html_body))

    # Section files zipped
    zip_path = output_dir / "ptu_classes_pages.zip"
    with ZipFile(zip_path, 'w') as zipf:
        for title, html_content in sections.items():
            filename = f"{title.replace(' ', '_').lower()}.html"
            file_path = output_dir / filename
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(wrap_html(title, html_content))
            zipf.write(file_path, arcname=filename)

    print(f"✅ Full HTML: {full_html_path}")
    print(f"✅ Section ZIP: {zip_path}")

# Example usage
if __name__ == "__main__":
    convert_pdf_to_html_with_style("py/PTU classes clean.pdf", "styled_output")
