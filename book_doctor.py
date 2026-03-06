import os
from pathlib import Path

# ANSI Escape-Codes für ein bisschen Farbe im Terminal
class Colors:
    OK = '\033[92m'       # Grün
    WARN = '\033[93m'     # Gelb
    FAIL = '\033[91m'     # Rot
    RESET = '\033[0m'     # Zurücksetzen
    BOLD = '\033[1m'


def get_yml_chapters(yml_path):
    """Liest die Kapitel-Liste aus der _quarto.yml aus."""
    chapters = []
    in_chapters = False
    try:
        with open(yml_path, 'r', encoding='utf-8') as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith('chapters:'):
                    in_chapters = True
                    continue
                if in_chapters:
                    if stripped.startswith('-'):
                        val = stripped[1:].strip().strip('"\'')
                        if val.endswith('.md'):
                            chapters.append(val)
                    elif stripped and not stripped.startswith('#'):
                        in_chapters = False
    except Exception:
        pass
    return chapters


def check_book(book_dir):
    """Führt eine umfassende Diagnose für ein einzelnes Buch durch."""
    print(f"\n{Colors.BOLD}=== Diagnose für: {book_dir.name} ==={Colors.RESET}")
    
    errors = 0
    warnings = 0

    # 1. Check: Existiert die zentrale index.md?
    if not (book_dir / "index.md").exists():
        print(f"  {Colors.FAIL}[FEHLER]{Colors.RESET} Keine 'index.md' im Hauptverzeichnis gefunden.")
        errors += 1
    else:
        print(f"  {Colors.OK}[OK]{Colors.RESET} 'index.md' ist vorhanden.")

    # 2. Check: _quarto.yml vs. Festplatte (Der wichtigste neue Check!)
    yml_path = book_dir / "_quarto.yml"
    if not yml_path.exists():
        print(f"  {Colors.FAIL}[FEHLER]{Colors.RESET} Keine '_quarto.yml' gefunden.")
        errors += 1
    else:
        yml_files = get_yml_chapters(yml_path)
        
        # Physische MDs finden
        disk_files = []
        for path in book_dir.rglob("*.md"):
            if not any(part.startswith('.') or part in ['_book', '__pycache__'] for part in path.parts):
                disk_files.append(path.relative_to(book_dir).as_posix())

        # Geister-Dateien in der YML (Steht drin, existiert aber nicht)
        ghosts = [f for f in yml_files if f not in disk_files and f != "index.md"]
        for g in ghosts:
            print(f"  {Colors.FAIL}[FEHLER]{Colors.RESET} Geister-Eintrag in _quarto.yml! '{g}' existiert nicht physisch.")
            errors += 1
            
        # Vergessene Dateien (Liegen im Ordner, fehlen aber in der YML)
        forgotten = [f for f in disk_files if f not in yml_files and f != "index.md"]
        for f in forgotten:
            print(f"  {Colors.WARN}[WARNUNG]{Colors.RESET} Datei liegt im Ordner, fehlt aber in der _quarto.yml: '{f}'")
            warnings += 1

        if not ghosts and not forgotten:
            print(f"  {Colors.OK}[OK]{Colors.RESET} _quarto.yml und Ordnerstruktur sind zu 100% synchron.")

    # 3. Check: Haben alle .md Dateien ein Frontmatter?
    md_files = [f for f in book_dir.rglob("*.md") if not any(x in f.parts for x in ['.quarto', '.venv', '_book', '__pycache__'])]
    missing_fm = 0
    for md in md_files:
        try:
            with open(md, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if first_line != "---":
                    print(f"  {Colors.WARN}[WARNUNG]{Colors.RESET} Fehlendes Frontmatter in: {md.relative_to(book_dir)}")
                    warnings += 1
                    missing_fm += 1
        except Exception:
            print(f"  {Colors.FAIL}[FEHLER]{Colors.RESET} Datei konnte nicht gelesen werden: {md.name}")
            errors += 1
    
    if missing_fm == 0:
        print(f"  {Colors.OK}[OK]{Colors.RESET} Alle Markdown-Dateien haben ein YAML-Frontmatter.")

    # Fazit für das Buch
    print("-" * 40)
    if errors == 0 and warnings == 0:
        print(f"  {Colors.OK}Alles perfekt! Das Buch ist bereit für den Druck.{Colors.RESET}")
    else:
        print(f"  Ergebnis: {Colors.FAIL}{errors} Fehler{Colors.RESET}, {Colors.WARN}{warnings} Warnungen{Colors.RESET}")


def main():
    root_path = Path(__file__).parent
    books = [cfg.parent for cfg in root_path.rglob("_quarto.yml") if '.venv' not in cfg.parts]
    
    if not books:
        print("Keine Quarto-Bücher gefunden.")
        return

    print(f"Starte Buch-Doktor (YML-Modus)... Untersuche {len(books)} Projekt(e).")
    for book in books:
        check_book(book)
    print("\nDiagnose abgeschlossen.")


if __name__ == "__main__":
    main()