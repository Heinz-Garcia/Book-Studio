import os
import shutil
import csv
import re
import logging
from datetime import datetime

# --- KONFIGURATION ---
# Trage hier deine tatsächlichen Pfade ein
sources = [
    r'C:\Users\Daniel\Documents\Python\IFJN\Baende\Stoffwechselgesundheit\Ich_frage_nur_(src)_(PANDOC_clean.01.03)\src', 
    r'C:\Users\Daniel\Documents\Python\IFJN\Baende\Stoffwechselgesundheit\Ich_frage_nur_(src)\src', 
    r'C:\Users\Daniel\Documents\Python\IFJN\Baende\Stoffwechselgesundheit\Ich_frage_nur_(src.bk2)'
]
dest_folder = r'C:\Users\Daniel\Documents\Python\IFJN\_tmp_Diabetes_Generat'

# Dateien, die im Zielordner generiert werden
mapping_csv = os.path.join(dest_folder, 'buch_struktur_mapping.csv')
log_file = os.path.join(dest_folder, 'migration.log')

# Zielordner erstellen, falls nicht vorhanden
os.makedirs(dest_folder, exist_ok=True)

# --- LOGGING SETUP ---
# Erstellt ein detailliertes Logbuch mit Zeitstempeln
logging.basicConfig(
    filename=log_file, 
    level=logging.INFO, 
    format='%(asctime)s | %(levelname)s | %(message)s',
    encoding='utf-8'
)

def get_frontmatter_title(filepath):
    """Extrahiert den Titel aus dem YAML-Frontmatter."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(2000) 
            match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', content, re.MULTILINE)
            return match.group(1).strip() if match else "Kein Titel gefunden"
    except Exception as e:
        logging.error(f"Fehler beim Lesen von {filepath}: {e}")
        return "Lese-Fehler"

data_rows = []

print("🚀 Starte Prozess. Details werden in die Log-Datei geschrieben...")
logging.info("=== NEUER MERGE-LAUF GESTARTET ===")

for src in sources:
    if not os.path.exists(src):
        logging.warning(f"Quellordner nicht gefunden und uebersprungen: {src}")
        continue
        
    logging.info(f"Starte rekursive Durchsuchung von: {src}")
    
    # os.walk iteriert rekursiv durch alle Verzeichnisse und Unterverzeichnisse
    for root, dirs, files in os.walk(src):
        for file in files:
            if file.endswith('.md'):
                old_path = os.path.join(root, file)
                title = get_frontmatter_title(old_path)
                
                # Duplikat-Check und neuer Dateiname
                base_name, ext = os.path.splitext(file)
                target_name = file
                target_path = os.path.join(dest_folder, target_name)
                counter = 1
                
                while os.path.exists(target_path):
                    target_name = f"{base_name}_{counter}{ext}"
                    target_path = os.path.join(dest_folder, target_name)
                    counter += 1
                
                if target_name != file:
                    logging.info(f"Namenskonflikt gelöst: '{file}' umbenannt in '{target_name}'")
                
                # Kopieren
                try:
                    shutil.copy2(old_path, target_path)
                    logging.info(f"Kopiert: {old_path} -> {target_path}")
                except Exception as e:
                    logging.error(f"Fehler beim Kopieren von {old_path}: {e}")
                    continue
                
                # Mapping für die CSV speichern
                data_rows.append({
                    'DATEINAME_ZIEL': target_name,
                    'TITEL_FRONTMATTER': title,
                    'PFAD_QUELLE': old_path
                })

# --- CSV SCHREIBEN ---
logging.info("Erstelle Mapping-CSV...")
with open(mapping_csv, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['DATEINAME_ZIEL', 'TITEL_FRONTMATTER', 'PFAD_QUELLE'], delimiter=';')
    writer.writeheader()
    writer.writerows(data_rows)

logging.info(f"=== LAUF BEENDET. {len(data_rows)} Dateien verarbeitet. ===")

print(f"✅ Fertig! {len(data_rows)} .md-Dateien wurden gesammelt.")
print(f"📂 Alle Dateien + CSV + Logbuch liegen hier: {dest_folder}")