import pdfplumber
import sys
import os

def clean_text(text):
    """
    Respecte les sauts de paragraphes (indiqués par double retour à la ligne)
    mais fusionne les lignes à l'intérieur des paragraphes.
    """
    if not text:
        return ""

    # Séparer en paragraphes (double retour à la ligne)
    raw_paragraphs = text.split("\n\n")
    cleaned_paragraphs = []

    for para in raw_paragraphs:
        # Supprimer les \n internes au paragraphe et nettoyer les espaces
        lines = para.splitlines()
        merged = " ".join(line.strip() for line in lines if line.strip())
        if merged:
            cleaned_paragraphs.append(merged)

    return "\n\n".join(cleaned_paragraphs)

def extract_text_from_pdf(pdf_path, output_txt="output.txt"):
    if not os.path.isfile(pdf_path):
        print(f"Fichier introuvable : {pdf_path}")
        return

    with pdfplumber.open(pdf_path) as pdf, open(output_txt, "w", encoding="utf-8") as out_file:
        for i, page in enumerate(pdf.pages, start=1):
            width = page.width
            height = page.height

            # Définir les deux colonnes
            left_bbox = (0, 0, width / 2, height)
            right_bbox = (width / 2, 0, width, height)

            left_text_raw = page.within_bbox(left_bbox).extract_text()
            right_text_raw = page.within_bbox(right_bbox).extract_text()

            left_text = clean_text(left_text_raw or "")
            right_text = clean_text(right_text_raw or "")

            # Concaténer les colonnes comme en lecture naturelle
            full_text = f"--- Page {i} ---\n{left_text}\n\n{right_text}\n\n"
            out_file.write(full_text)

    print(f"Extraction terminée. Texte propre enregistré dans {output_txt}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Utilisation : python extract_pdf_columns.py chemin/vers/fichier.pdf")
    else:
        input_pdf = sys.argv[1]
        output_txt = os.path.splitext(input_pdf)[0] + ".txt"
        extract_text_from_pdf(input_pdf, output_txt)
