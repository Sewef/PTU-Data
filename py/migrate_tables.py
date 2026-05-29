#!/usr/bin/env python3
"""
Migrer la structure des tableaux dans les fichiers JSON de features.
De : clé "" avec _display
À : structure hiérarchique moveTable/abilityTable/etc avec groups
"""

import json
import re
from pathlib import Path


def migrate_table_structure(obj):
    """
    Transforme une clé vide "" avec _display en structure hiérarchique.
    Traite UNIQUEMENT ce niveau, pas récursivement.
    """
    if not isinstance(obj, dict):
        return obj

    # Vérifier si c'est une table plate qui doit être migrée
    if "" in obj and "_display" in obj:
        display_meta = obj.get("_display", {})
        table_data = obj[""]

        # Déterminer le nom de la table
        table_name = infer_table_name(obj)

        # Transformer le tableau
        table_obj = transform_flat_table_to_hierarchical(
            table_data, 
            display_meta, 
            table_name
        )

        # Reconstruire l'objet sans la clé vide et _display
        result = {k: v for k, v in obj.items() if k not in ("", "_display")}
        if table_obj:
            result[table_name] = table_obj
        return result
    else:
        return obj


def infer_table_name(obj):
    """
    Détermine un nom approprié pour la table basé sur le contexte.
    """
    # Regarder les colonnes pour déduire le type
    display_meta = obj.get("_display", {})
    table_meta = display_meta.get("", {})
    columns = table_meta.get("columns", [])
    
    col_str = " ".join(str(c).lower() for c in columns)
    
    if "move" in col_str:
        return "moveTable"
    elif "ability" in col_str:
        return "abilityTable"
    else:
        return "dataTable"


def transform_flat_table_to_hierarchical(rows, display_meta, table_name):
    """
    Transforme un tableau plat (format colonne_1, colonne_2, etc.)
    en structure hiérarchique avec groups.
    """
    if not isinstance(rows, list) or len(rows) == 0:
        return None

    # Extraire les métadonnées d'affichage
    table_meta = display_meta.get("", {})
    if not isinstance(table_meta, dict):
        return None

    columns = table_meta.get("columns", [])
    if not columns:
        return None

    merge_columns = table_meta.get("mergeColumns", False)
    group_labels = table_meta.get("groupLabels", {})

    if not merge_columns:
        # Si pas de merge, retourner juste les lignes comme-is
        return {
            "columns": columns,
            "groups": [{
                "label": "Items",
                "rows": rows
            }]
        }

    # Parser les colonnes pour identifier les groupes
    groups_order = []
    seen_bases = set()

    for col in columns:
        # Regex : "Rank 1 Moves_1" → ("Rank 1 Moves", "1")
        match = re.match(r"^(.*?)(?:_(\d+))$", col)
        group_base = match.group(1).strip() if match else col.strip()
        
        if group_base not in seen_bases:
            groups_order.append(group_base)
            seen_bases.add(group_base)

    # Construire la structure hiérarchique
    groups = []

    for group_base in groups_order:
        # Colonnes de ce groupe
        group_cols = [col for col in columns 
                      if re.match(f"^{re.escape(group_base)}(?:_\\d+)?$", col)]

        # Extraire les rows pour ce groupe
        group_rows = []
        for row_obj in rows:
            if not isinstance(row_obj, dict):
                continue

            # Créer une ligne pour ce groupe
            new_row = {}
            for col in group_cols:
                if col in row_obj:
                    new_row[col] = row_obj[col]

            # Ne pas ajouter les lignes complètement vides
            if any(v for v in new_row.values()):
                group_rows.append(new_row)

        if group_rows:
            label = group_labels.get(group_base, group_base)
            groups.append({
                "label": label,
                "rows": group_rows
            })

    if not groups:
        return None

    return {
        "columns": columns,
        "groups": groups
    }


def migrate_obj_recursive(obj):
    """
    Traverse récursivement un objet et migre TOUS les niveaux.
    """
    if not isinstance(obj, dict):
        return obj

    # Étape 1 : Migrer les tables au niveau actuel
    obj = migrate_table_structure(obj)

    # Étape 2 : Appliquer récursivement sur toutes les valeurs
    result = {}
    for key, value in obj.items():
        if isinstance(value, dict):
            result[key] = migrate_obj_recursive(value)
        elif isinstance(value, list):
            result[key] = [
                migrate_obj_recursive(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value

    return result


def process_file(filepath):
    """Migre un fichier JSON de features."""
    print(f"Processing {filepath}...")

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Migrer toute la structure récursivement
    migrated = migrate_obj_recursive(data)

    # Écrire le résultat avec UTF-8 explicite
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(migrated, f, ensure_ascii=False, indent=2, default=str)

    print(f"✓ {filepath} migré avec succès")


if __name__ == "__main__":
    # Fichiers à migrer
    files_to_migrate = [
        "ptu/data/features/features_core.json",
        "ptu/data/features/features_homebrew.json",
        "ptu/data/features/features_community.json",
    ]

    base_path = Path(__file__).parent.parent

    for file_rel in files_to_migrate:
        filepath = base_path / file_rel
        if filepath.exists():
            process_file(filepath)
        else:
            print(f"⚠ {filepath} non trouvé")

    print("\n✓ Migration terminée!")
