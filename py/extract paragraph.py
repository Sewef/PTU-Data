KEYWORDS = [
    "Prerequisites:", "Trigger:", "Effect:", "Target:", "Note:"
]

def line_starts_with_keyword(line):
    if line.startswith("[") and line.endswith("]"):
        return False
    for kw in KEYWORDS:
        if line.startswith(kw):
            return kw
    return None

def format_text_to_md(text):
    lines = text.splitlines()
    md_lines = []
    buffer = []
    inside_section = False  # Track if inside a section title block

    def flush_buffer():
        if not buffer:
            return
        paragraph = " ".join(line.strip() for line in buffer)
        md_lines.append(paragraph)
        md_lines.append("")
        buffer.clear()

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if not line:
            flush_buffer()
            inside_section = False
            i += 1
            continue

        # Lines with brackets - level 2 titles, keep brackets
        if line.startswith("[") and line.endswith("]"):
            flush_buffer()
            md_lines.append(f"{line}")
            md_lines.append("")
            inside_section = False
            i += 1
            continue

        # Check if line starts with a keyword, return the matched keyword or None
        kw = line_starts_with_keyword(line)
        if kw:
            flush_buffer()
            # Bold only the keyword part (the kw), keep rest as is
            rest = line[len(kw):].strip()
            if rest:
                md_lines.append(f"**{kw}** {rest}")
            else:
                md_lines.append(f"**{kw}**")
            md_lines.append("")
            inside_section = False
            i += 1
            continue

        # Titles level 3 - short, no colon, Title Case, and not inside section
        if (":" not in line) and (line == line.title()) and len(line.split()) <= 4:
            flush_buffer()
            md_lines.append(f"### {line}")
            md_lines.append("")
            inside_section = True
            i += 1
            continue

        # Normal text lines to buffer
        buffer.append(line)
        i += 1

    flush_buffer()
    return "\n".join(md_lines)


# Exemple d'utilisation avec ton texte :
text = """Ace Trainer
[Class]
Prerequisites: Novice Command
Drain 1 AP – Extended Action
Trigger: You spend at least half an hour training your Pokémon
Effect: For each Pokémon that has been trained during this time, choose a Stat besides HP; that Stat becomes
Trained until an Extended Rest is taken. The default State of Trained Stats is +1 Combat Stages instead of 0. A
Pokémon may have only one Trained Stat at a time.
Note: Just to clarify, this Feature Drains 1 AP per training session, not per Pokémon. So train as many as you can
to get the most out of this Feature!
Perseverance
Prerequisites: Ace Trainer
1 AP – Free Action
Trigger: Your Pokémon gains an Injury
Effect: The target instead does not gain an Injury.
Perseverance may activate only once per Scene per
target.
Elite Trainer
Prerequisites: Ace Trainer
Static
Effect: Choose Agility Training, Brutal Training,
Focused Training, or Inspired Training. You gain
the chosen Feature, even if you do not meet the
prerequisites. When training, you may apply up to two
different [Training] Features on each of your Pokémon.
If you already have all of these Features, instead pick
another Feature for which you qualify.
Critical Moment
[Orders]
Prerequisites: Elite Trainer, Adept Command
Scene x2 – Standard Action
Target: Your Pokemon with [Training] Features applied
Effect: The bonuses from your Pokemon's [Training]
are tripled until the end of your next turn.
Top Percentage
Prerequisites: Ace Trainer, Expert Command
At-Will – Free Action
Trigger: Your Pokémon levels up to a Level evenly
divisible by 5
Effect: Your Pokémon gains an extra Tutor Point.
Top Percentage may be used on a single Pokémon a
maximum of 4 times. Once a Pokémon has gained 4
Tutor Points in this way, increase each of that Pokémon's
Base Stats by +1.
Signature Technique
Prerequisites: Elite Trainer, Expert Command
At-Will – Extended Action
Target: Your Pokémon with at least 2 Tutor Points
remaining
Effect: The target loses 2 Tutor Points. Choose one
Move on the Target's Move List. That Move becomes
the target's Signature Technique, and you may apply
one of the modifications on the next page to the Move.
The Move being modified must fit the category of the
modification, and you must have the associated Training
Feature to apply a modification. A Pokémon may only
have one Signature Technique at a time. If you choose
to teach a Pokémon a different Signature Technique, the
old one is lost, and 1 Tutor Point is refunded. 1 Tutor
Point is also refunded if the Pokémon ever forgets a
Signature Technique Move.
Note: Be sure to give a cool name to your Pokémon's
Signature Technique!
Champ in the Making
Prerequisites: 4 Ace Trainer Features, Master Command
Drain 1 AP – Free Action
Trigger: You use Ace Trainer to give Pokémon Trained
Stats
Effect: Choose two Trained Stats for each Pokémon
instead of one. A Pokémon may only have two Trained
Stats this way."""

md_text = format_text_to_md(text)
print(md_text)

with open("sortie.md", "w", encoding="utf-8") as f:
        f.write(md_text)