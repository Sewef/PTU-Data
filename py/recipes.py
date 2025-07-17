import json
import pyperclip


def extract_recipes(data, parent=None):
    recipes = []

    if isinstance(data, dict) and 'name' in data:
        # Séparer "name" et les autres champs
        name_value = data['name']
        other_fields = {k: v for k, v in data.items() if k != 'name'}

        # Extraire les sous-recettes en premier
        for v in other_fields.values():
            if isinstance(v, dict) and 'name' in v:
                recipes.extend(extract_recipes(v, parent=name_value))

        # Puis créer l’objet courant, avec "name" en premier
        entry = {'name': name_value}
        for k, v in other_fields.items():
            if not (isinstance(v, dict) and 'name' in v):
                entry[k] = v
        recipes.append(entry)

    elif isinstance(data, dict):
        for value in data.values():
            recipes.extend(extract_recipes(value, parent=parent))

    return recipes

# Exemple d'utilisation :
if __name__ == "__main__":
    # Remplace cette ligne par ton JSON réel
    json_input = '''{
            "name": "Signature Technique Modifications",
            "Cone, Line, Burst, and Blast Moves": {
              "name": "Cone, Line, Burst, and Blast Moves",
              "Scattershot – Agility Training": "Instead of the Move’s normal range, it has a range of 4m, 3 Targets.",
              "Shock and Awe – Inspired Training": "Foes targeted by the Move take a -2 penalty to Save Checks and a -1 Penalty to Evasion until the end of the user’s next turn.",
              "Vicious Storm – Brutal Training": "The Move gains the Smite keyword. Applicable to Damaging Moves only."
            },
            "Single Target Moves": {
              "name": "Single Target Moves",
              "Guarding Strike – Inspired Training": "If this Move hits, the user gains +5 Damage Reduction against the target of the attack until the end of their next turn.",
              "Unbalancing Blow – Brutal Training": "Whether the Move hits or misses, the target becomes Vulnerable until the next time they are hit by a Damaging Attack or one full round has passed, whichever comes first.",
              "Reliable Attack – Focused Training": "If the Move misses its target, its Frequency is not spent and the user may immediately make a Struggle Attack as a Free Action. Cannot be applied to Moves with the Smite keyword."
            },
            "Damaging Moves": {
              "name": "Damaging Moves",
              "Alternative Energy – Focused Training": "Switch the Class of the Move from Physical to Special or vice versa.",
              "Bloodied Speed – Agility Training": "This Move may be used as Priority (Advanced) if the user has less than half of their maximum Hit Points.",
              "Double Down – Brutal Training": "The Move gains the Double Strike keyword. Effects and Effect-Ranges may be triggered only once (but either roll may trigger the effect). This may only be applied to Moves with a Damage Base of 4 or less, and may not be applied to Moves whose Damage Base change upon certain conditions (such as Fury Cutter or Ice Ball) or moves with Special-Case Damage (such as Night Shade)."
            },
            "Status Moves": {
              "name": "Status Moves",
              "Burst of Motivation – Inspired Training": "After this Move is Resolved, the user may increase any Stats with negative Combat Stages by up to +2 Combat Stages (but this cannot put Combat Stages above +0 CS total).",
              "Supreme Concentration – Focused Training": "This Move may be used even if the user is Paralyzed, Flinched, Enraged, or has failed their Confusion Save Check.",
              "Double Curse – Agility Training": "The user may target an additional foe with this Attack. This may be applied only to 1-Target Moves."
            }
          }'''

    data = json.loads(json_input)
    result = extract_recipes(data)
    result = json.dumps(result, indent=2, ensure_ascii=False)

    # Affichage formaté
    from pprint import pprint
    pprint(result)
    pyperclip.copy(result)
