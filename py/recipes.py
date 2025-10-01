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

        # Puis créer l'objet courant, avec "name" en premier
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
            "name": "Chef Recipes",
            "Tasty Snacks": {
              "name": "Tasty Snacks",
              "Prerequisites": "Chef",
              "Cost": "$100",
              "Effect": "You create a Salty Surprise, Spicy Wrap, Sour Candy, Dry Wafer, Bitter Treat, or Sweet Confection."
            },
            "Salty Surprise": {
              "name": "Salty Surprise",
              "Effect": "The user may trade in this Snack's Digestion Buff when being hit by an attack to gain 5 Temporary Hit Points. If the user likes Salty Flavors, they gain 10 Temporary Hit Points Instead. If the user dislikes Salty Food, they become Enraged."
            },
            "Spicy Wrap": {
              "name": "Spicy Wrap",
              "Effect": "The user may trade in this Snack's Digestion Buff when making a Physical attack to deal +5 additional Damage. If the user prefers Spicy Food, it deals +10 additional Damage instead. If the user dislikes Spicy Food, they become Enraged."
            },
            "Sour Candy": {
              "name": "Sour Candy",
              "Effect": "The user may trade in this Snack's Digestion Buff when being hit by a Physical Attack to increase their Damage Reduction by +5 against that attack. If the user prefers Sour Food, they gain +10 Damage Reduction instead. If the user dislikes Sour Food, they become Enraged."
            },
            "Dry Wafer": {
              "name": "Dry Wafer",
              "Effect": "The user may trade in this Snack's Digestion Buff when making a Special attack to deal +5 additional Damage. If the user prefers Dry Food, it deals +10 additional Damage instead. If the user dislikes Dry Food, they become Enraged."
            },
            "Bitter Treat": {
              "name": "Bitter Treat",
              "Effect": "The user may trade in this Snack's Digestion Buff when being hit by a Special Attack to increase their Damage Reduction by +5 against that attack. If the user prefers Bitter Food, they gain +10 Damage Reduction instead. If the user dislikes Bitter Food, they become Enraged."
            },
            "Sweet Confection": {
              "name": "Sweet Confection",
              "Effect": "The user may trade in this Snack's Digestion Buff to gain +4 Evasion until the end of their next turn. If the user prefers Sweet Food, they gain +4 Accuracy as well. If the user dislikes Sweet Food, they become Enraged."
            },
            "Meal Planner": {
              "name": "Meal Planner",
              "Prerequisites": "Chef",
              "Effect": "You may create the following items, based on your Intuition Rank",
              "\n» Novice": "“Enriched Water” for $40",
              "\n» Adept": "“Super Soda Pop” for $65",
              "\n» Expert": "“Sparkling Lemonade” for $125",
              "\n» Master": "“MooMoo Milk” for $250"
            },
            "Hearty Meal": {
              "name": "Hearty Meal",
              "Prerequisites": "Hits the Spot",
              "Ingredients": "x2 Tiny Mushrooms; or x1 Big Mushroom; or x1 Balm Mushroom, or x2 Power Herbs, White Herbs, or Mental Herbs",
              "Effect": "You create up to five Hearty Meals, which may be consumed by Trainers as an Extended Action. When consumed, that Trainer gains +2 to their Max AP until the end of their next extended rest. A Trainer may only be under the effect of one Hearty Meal at a time. Hearty Meals not consumed within 20 minutes of being created lose all flavor and all effect."
            },
            "Bait Mixer": {
              "name": "Bait Mixer",
              "Prerequisites": "Culinary Appreciation",
              "Cost": "$150 or Honey.",
              "Effect": "You may create Bait. For $50 more, you may create Bait as Super Bait or Vile Bait instead. Super Bait works like regular Bait, but you may add your Intuition Rank to 1d20 Rolls made to attract Pokémon. Vile Bait works like regular Bait, but Pokémon that eat it are Poisoned."
            },
            "Preserves": {
              "name": "Preserves",
              "Prerequisites": "Accentuated Taste",
              "Ingredients": "$50, any Berry, Herb, or Mushroom",
              "Effect": "The user creates x2 Units of Preserves from the Berry, Herb, or Mushroom. Preserves have the same effect as the consumable from which they were made."
            },
            "Leftovers": {
              "name": "Leftovers",
              "Prerequisites": "Complex Aftertaste",
              "Cost": "$100",
              "Effect": "You create Leftovers."
            },
            "Vitamins": {
              "name": "Vitamins",
              "Prerequisites": "Dietician",
              "Effect": "You create an HP Up, Protein, Iron, Calcium, Zinc, or Carbos for $2450, or Stat Suppressants for $200."
            }
          }'''

    data = json.loads(json_input)
    result = extract_recipes(data)
    result = json.dumps(result, indent=2, ensure_ascii=False)

    # Affichage formaté
    from pprint import pprint
    pprint(result)
    pyperclip.copy(result)
