import json
from collections import OrderedDict
from shutil import copy2
from pathlib import Path

IN_PATH = Path(r"c:\GitHub\PTU-Data\ptu\data\moves\moves_9g.json")
BACKUP_PATH = IN_PATH.with_suffix(".json.bak")

def reorder_entry(entry: OrderedDict) -> OrderedDict:
    # If entry is not mapping, return as-is
    if not isinstance(entry, OrderedDict):
        return entry
    keys_to_move = ["Set-Up Effect", "Resolution Effect"]
    have = {k: entry[k] for k in keys_to_move if k in entry}
    new = OrderedDict()
    moved = set()

    for k, v in entry.items():
        if k in keys_to_move:
            # skip here; we'll insert these before Contest Type
            continue
        if k == "Contest Type":
            # insert the moved keys (in order) before Contest Type
            for mk in keys_to_move:
                if mk in have and mk not in moved:
                    new[mk] = have[mk]
                    moved.add(mk)
            new[k] = v
        else:
            new[k] = v

    # if Contest Type wasn't present, but the keys exist, append them at the end
    for mk in keys_to_move:
        if mk in have and mk not in moved:
            new[mk] = have[mk]

    return new

def main():
    if not IN_PATH.exists():
        print("Input file not found:", IN_PATH)
        return

    # backup
    # copy2(IN_PATH, BACKUP_PATH)

    with IN_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f, object_pairs_hook=OrderedDict)

    changed = 0
    for name, entry in list(data.items()):
        if isinstance(entry, dict):
            entry_od = OrderedDict(entry)
            reordered = reorder_entry(entry_od)
            if list(reordered.keys()) != list(entry_od.keys()):
                data[name] = reordered
                changed += 1

    with IN_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"Done. Entries changed: {changed}.")

if __name__ == "__main__":
    main()