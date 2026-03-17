import argparse
import csv
import json
import os
import re
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
    parser = argparse.ArgumentParser(description="Erzeugt eine finale CSV-Übersicht aus einem Zielordner.")
    parser.add_argument("--config", default="studio_config.json", help="Pfad zur Konfigurationsdatei (Default: studio_config.json)")
    parser.add_argument("--target", help="Optionaler Zielordner-Override")
    return parser.parse_args()

def get_frontmatter_title(filepath):
    """Extrahiert den Titel aus dem YAML-Frontmatter."""
    try:
        with open(filepath, 'r', encoding='utf-8') as source_file:
            content = source_file.read(2000)
            match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', content, re.MULTILINE)
            return match.group(1).strip() if match else "Kein Titel"
    except (OSError, ValueError, TypeError):
        return "Lese-Fehler"

def main() -> int:
    args = _parse_args()
    project_root = _project_root()
    config_path = _resolve_path(args.config, project_root)
    config = _load_config(config_path)

    configured_target = args.target if args.target else config.get("indexer_target_folder", "")
    if not configured_target:
        print("❌ Kein Indexer-Zielordner konfiguriert. Bitte in Studio-Konfiguration 'indexer_target_folder' setzen.")
        return 2

    target_folder = _resolve_path(str(configured_target), project_root)
    if not target_folder.exists() or not target_folder.is_dir():
        print(f"❌ Indexer-Zielordner existiert nicht: {target_folder}")
        return 2

    csv_file = target_folder / 'buch_struktur_final.csv'
    data_rows = []

    print("📂 Lese Dateien im Zielordner...")

    for file in os.listdir(target_folder):
        if file.endswith('.md'):
            full_path = target_folder / file
            title = get_frontmatter_title(str(full_path))

            data_rows.append({
                'DATEINAME': file,
                'TITEL_FRONTMATTER': title
            })

    with csv_file.open('w', newline='', encoding='utf-8') as csv_handle:
        writer = csv.DictWriter(csv_handle, fieldnames=['DATEINAME', 'TITEL_FRONTMATTER'], delimiter=';')
        writer.writeheader()
        writer.writerows(data_rows)

    print(f"✅ Fertig! {len(data_rows)} Dateien indexiert.")
    print(f"📄 Die CSV liegt hier: {csv_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())