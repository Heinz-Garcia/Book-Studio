import argparse
import csv
import json
import logging
import os
import re
import shutil
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _resolve_path(value: str, base: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (base / path).resolve()
    return path


def _load_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return {}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sammelt Markdown-Dateien aus konfigurierten Quellordnern.")
    parser.add_argument("--config", default="studio_config.json", help="Pfad zur Konfigurationsdatei (Default: studio_config.json)")
    parser.add_argument("--sources", nargs="*", help="Optionale Quellordner-Overrides")
    parser.add_argument("--dest", help="Optionaler Zielordner-Override")
    return parser.parse_args()

def get_frontmatter_title(filepath):
    """Extrahiert den Titel aus dem YAML-Frontmatter."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(2000) 
            match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', content, re.MULTILINE)
            return match.group(1).strip() if match else "Kein Titel gefunden"
    except OSError as e:
        logging.error("Fehler beim Lesen von %s: %s", filepath, e)
        return "Lese-Fehler"


def main() -> int:
    args = _parse_args()
    project_root = _project_root()
    config_path = _resolve_path(args.config, project_root)
    config = _load_config(config_path)

    configured_sources = args.sources if args.sources else config.get("prep_sources", [])
    configured_dest = args.dest if args.dest else config.get("prep_dest_folder", "")

    if not configured_sources:
        print("❌ Keine Merge-Quellpfade konfiguriert. Bitte in Studio-Konfiguration 'prep_sources' setzen.")
        return 2
    if not configured_dest:
        print("❌ Kein Merge-Zielordner konfiguriert. Bitte in Studio-Konfiguration 'prep_dest_folder' setzen.")
        return 2

    sources = [_resolve_path(str(src), project_root) for src in configured_sources if str(src).strip()]
    dest_folder = _resolve_path(str(configured_dest), project_root)

    mapping_csv = dest_folder / "buch_struktur_mapping.csv"
    log_file = dest_folder / "migration.log"

    dest_folder.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        filename=str(log_file),
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
        encoding='utf-8'
    )

    data_rows = []

    print("🚀 Starte Prozess. Details werden in die Log-Datei geschrieben...")
    logging.info("=== NEUER MERGE-LAUF GESTARTET ===")

    for src in sources:
        if not src.exists() or not src.is_dir():
            logging.warning("Quellordner nicht gefunden und uebersprungen: %s", src)
            continue

        logging.info("Starte rekursive Durchsuchung von: %s", src)

        for root, _dirs, files in os.walk(src):
            for file in files:
                if file.endswith('.md'):
                    old_path = Path(root) / file
                    title = get_frontmatter_title(str(old_path))

                    base_name, ext = os.path.splitext(file)
                    target_name = file
                    target_path = dest_folder / target_name
                    counter = 1

                    while target_path.exists():
                        target_name = f"{base_name}_{counter}{ext}"
                        target_path = dest_folder / target_name
                        counter += 1

                    if target_name != file:
                        logging.info("Namenskonflikt gelöst: '%s' umbenannt in '%s'", file, target_name)

                    try:
                        shutil.copy2(old_path, target_path)
                        logging.info("Kopiert: %s -> %s", old_path, target_path)
                    except OSError as e:
                        logging.error("Fehler beim Kopieren von %s: %s", old_path, e)
                        continue

                    data_rows.append({
                        'DATEINAME_ZIEL': target_name,
                        'TITEL_FRONTMATTER': title,
                        'PFAD_QUELLE': str(old_path)
                    })

    logging.info("Erstelle Mapping-CSV...")
    with mapping_csv.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=['DATEINAME_ZIEL', 'TITEL_FRONTMATTER', 'PFAD_QUELLE'], delimiter=';')
        writer.writeheader()
        writer.writerows(data_rows)

    logging.info("=== LAUF BEENDET. %s Dateien verarbeitet. ===", len(data_rows))

    print(f"✅ Fertig! {len(data_rows)} .md-Dateien wurden gesammelt.")
    print(f"📂 Alle Dateien + CSV + Logbuch liegen hier: {dest_folder}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())