"""
Script pour ajouter le support du changement de thème à tous les fichiers HTML
"""
import os
import re

# Dossiers à traiter
folders = [
    'ptu/ptuhomebrew',
    'ptu/ptucommunity',
    'ptu/ptucore'
]

# Fichiers à exclure (déjà modifiés)
exclude_files = ['index.html', 'header.html']

# Nouveaux éléments à ajouter
theme_script = '  <!-- Theme script must load before body to prevent flash -->\n  <script src="/ptu/js/theme-switcher.js"></script>\n\n'
bootstrap_css = '  <link rel="stylesheet" href="/ptu/css/bootstrap.min.css">\n'

def update_html_file(filepath):
    """Mise à jour d'un fichier HTML pour ajouter le support du thème"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Vérifier si déjà modifié
    if 'theme-switcher.js' in content and 'bootstrap.min.css' in content:
        print(f"  [SKIP] {filepath} - already updated")
        return False
    
    # Pattern pour trouver la section head
    # On cherche la balise <head> suivie de charset et viewport
    pattern = r'(<head>\s*<meta charset="UTF-8" />\s*<meta name="viewport" content="width=device-width, initial-scale=1">\s*(?:<title>.*?</title>\s*)?)'
    
    def replacement(match):
        return match.group(1) + '\n' + theme_script
    
    new_content = content
    
    # Ajouter le script du thème
    if 'theme-switcher.js' not in new_content:
        new_content = re.sub(pattern, replacement, new_content, flags=re.DOTALL)
    
    # Ajouter bootstrap.min.css avant style.css si absent
    if 'bootstrap.min.css' not in new_content:
        new_content = new_content.replace(
            '<link rel="stylesheet" href="/ptu/css/style.css">',
            '  <link rel="stylesheet" href="/ptu/css/bootstrap.min.css">\n  <link rel="stylesheet" href="/ptu/css/style.css">'
        )
    
    # Écrire le fichier modifié
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"  [OK] {filepath} - updated")
    return True

def main():
    total_updated = 0
    
    for folder in folders:
        print(f"\nProcessing folder: {folder}")
        
        # Lister tous les fichiers HTML
        for filename in os.listdir(folder):
            if filename.endswith('.html') and filename not in exclude_files:
                filepath = os.path.join(folder, filename)
                if os.path.isfile(filepath):
                    if update_html_file(filepath):
                        total_updated += 1
    
    print(f"\n✓ Total files updated: {total_updated}")

if __name__ == '__main__':
    main()
