import os
import csv
import re

# --- KONFIGURATION ---
target_folder = r'C:\Users\Daniel\Documents\Python\IFJN\_tmp_Diabetes_Generat\cleaned'
csv_file = os.path.join(target_folder, 'buch_struktur_final.csv')

def get_frontmatter_title(filepath):
    """Extrahiert den Titel aus dem YAML-Frontmatter."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(2000) 
            match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', content, re.MULTILINE)
            return match.group(1).strip() if match else "Kein Titel"
    except Exception as e:
        return "Lese-Fehler"

data_rows = []

print("📂 Lese Dateien im Zielordner...")

# os.listdir schaut NUR in die oberste Ebene (ignoriert den 'duplicates' Ordner)
for file in os.listdir(target_folder):
    if file.endswith('.md'):
        full_path = os.path.join(target_folder, file)
        title = get_frontmatter_title(full_path)
        
        data_rows.append({
            'DATEINAME': file,
            'TITEL_FRONTMATTER': title
        })

# CSV schreiben
with open(csv_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['DATEINAME', 'TITEL_FRONTMATTER'], delimiter=';')
    writer.writeheader()
    writer.writerows(data_rows)

print(f"✅ Fertig! {len(data_rows)} Dateien indexiert.")
print(f"📄 Die CSV liegt hier: {csv_file}")