import json

def parse_tsv_to_json(tsv_text: str):
    lines = tsv_text.strip().splitlines()
    headers = lines[0].split('\t')

    entries = []
    for line in lines[1:]:
        if not line.strip():
            continue  # ignore empty lines
        values = line.split('\t')
        entry = {headers[i]: values[i].strip() if i < len(values) else "" for i in range(len(headers))}
        entries.append(entry)

    return entries

if __name__ == "__main__":
    import pyperclip

    # Récupère depuis le presse-papiers (ou tu peux le lire depuis un fichier)
    tsv_input = pyperclip.paste()

    data = parse_tsv_to_json(tsv_input)
    output = json.dumps(data, indent=2, ensure_ascii=False)
    pyperclip.copy(output)
    print(output)
