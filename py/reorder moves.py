import json

def restructure_moves(input_path, output_path):
    with open(input_path, "r", encoding="utf-8") as f:
        moves = json.load(f)

    output = {}
    for move in moves:
        name = move.pop("Name", None)
        if name:
            output[name] = move

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

# Example usage:
restructure_moves("ptu/data/moves_homebrew.json", "ptu/data/moves_homebrew.json")
