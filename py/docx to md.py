from docx import Document
import re

def is_heading(paragraph):
    # Détecte si le paragraphe est un titre et son niveau
    style = paragraph.style.name.lower()
    if style.startswith("heading"):
        # Exemple de style: "Heading 1", "Heading 2"
        level = int(re.findall(r'\d+', style)[0])
        return level
    return 0

def para_to_markdown(paragraph):
    level = is_heading(paragraph)
    text = ""
    # Gestion du gras/italique par run
    for run in paragraph.runs:
        run_text = run.text
        if run.bold:
            run_text = f"**{run_text}**"
        if run.italic:
            run_text = f"*{run_text}*"
        text += run_text

    if level > 0:
        return f"{'#' * level} {text.strip()}"
    else:
        return text.strip()

def extract_docx_to_md(filepath):
    doc = Document(filepath)
    md_lines = []
    for para in doc.paragraphs:
        md_lines.append(para_to_markdown(para))
    return "\n\n".join(md_lines)

if __name__ == "__main__":
    path = "Classes.docx"
    md_text = extract_docx_to_md(path)
    print(md_text)


    with open("sortie2.md", "w", encoding="utf-8") as f:
            f.write(md_text)