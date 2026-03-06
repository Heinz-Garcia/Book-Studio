import time
import re
import os
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ANSI Colors für das Terminal
class Colors:
    OK = '\033[92m'
    WARN = '\033[93m'
    FAIL = '\033[91m'
    RESET = '\033[0m'
    CYAN = '\033[96m'

def clean_name(name):
    return re.sub(r'^\d+[_-]', '', name).replace('_', ' ').strip()

def check_and_add_frontmatter(file_path, is_meta=False):
    """Prüft und injiziert Frontmatter."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if content.strip().startswith('---'):
            if is_meta and "unnumbered: true" not in content:
                content = re.sub(r'^---\n', '---\nunnumbered: true\n', content, count=1)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            return
        
        title = clean_name(file_path.stem).title()
        meta_attr = "unnumbered: true\n" if is_meta else ""
        fm = f"---\ntitle: \"{title}\"\n{meta_attr}---\n\n"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(fm + content)
    except Exception:
        pass

def get_yml_chapters(yml_path):
    """Liest die Kapitel aus der _quarto.yml aus (ohne externe Bibliotheken)."""
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

def get_physical_mds(book_dir):
    """Findet alle .md Dateien im Ordner."""
    mds = []
    for path in book_dir.rglob("*.md"):
        # Ignoriere Systemordner
        if not any(part.startswith('.') or part in ['_book', '__pycache__'] for part in path.parts):
            mds.append(path.relative_to(book_dir).as_posix())
            
            # Frontmatter-Check direkt mitnehmen
            is_meta = True if path.parent.name in ['content', 'Ebene1'] else False
            check_and_add_frontmatter(path, is_meta)
    return mds

def validate_book(book_dir):
    """Gleicht die _quarto.yml mit den tatsächlichen Dateien ab."""
    yml_path = book_dir / "_quarto.yml"
    if not yml_path.exists():
        return

    print(f"\n{Colors.CYAN}=== Live-Check: {book_dir.name} ==={Colors.RESET}")
    
    yml_files = get_yml_chapters(yml_path)
    disk_files = get_physical_mds(book_dir)
    
    # Check 1: Geister-Dateien in der YML
    ghosts = [f for f in yml_files if f not in disk_files and f != "index.md"]
    if ghosts:
        for g in ghosts:
            print(f"  {Colors.FAIL}[FEHLER]{Colors.RESET} In _quarto.yml, aber fehlt auf Festplatte: {g}")
            
    # Check 2: Vergessene Dateien auf der Festplatte
    forgotten = [f for f in disk_files if f not in yml_files and f != "index.md"]
    if forgotten:
        for f in forgotten:
            print(f"  {Colors.WARN}[WARNUNG]{Colors.RESET} Datei existiert, fehlt aber in _quarto.yml: {f}")

    if not ghosts and not forgotten:
        print(f"  {Colors.OK}[OK]{Colors.RESET} _quarto.yml und Ordnerstruktur sind zu 100% synchron!")

class LiveAssistantHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_run = 0

    def on_any_event(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(('.md', '.yml')):
            now = time.time()
            if now - self.last_run < 1.0:
                return
            self.last_run = now

            paths = [event.src_path]
            if hasattr(event, 'dest_path'):
                paths.append(event.dest_path)

            for p_str in paths:
                if not p_str.endswith(('.md', '.yml')): continue
                path = Path(p_str)
                for parent in path.parents:
                    if (parent / "_quarto.yml").exists():
                        validate_book(parent)
                        break

if __name__ == "__main__":
    root_path = Path(__file__).parent
    
    print("\n" + "="*50)
    print("PIPELINE AKTIV: YML-COCKPIT MODUS")
    print("Sortiere deine Buchstruktur direkt in der _quarto.yml!")
    print("Watchdog warnt dich vor fehlenden oder toten Links.")
    print("="*50 + "\n")
    
    for config in root_path.rglob("_quarto.yml"):
        if '.venv' not in config.parts:
            validate_book(config.parent)
    
    observer = Observer()
    observer.schedule(LiveAssistantHandler(), str(root_path), recursive=True)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()