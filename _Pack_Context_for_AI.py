import fnmatch
import subprocess
import platform
from pathlib import Path
from datetime import datetime


def load_gitignore_rules(root_dir: Path) -> dict[str, set[str]]:
    gitignore_path = root_dir / '.gitignore'
    if not gitignore_path.exists():
        return {
            'dir_names': set(),
            'root_dirs': set(),
            'file_names': set(),
            'relative_files': set(),
            'file_patterns': set(),
            'root_patterns': set(),
        }

    rules = {
        'dir_names': set(),
        'root_dirs': set(),
        'file_names': set(),
        'relative_files': set(),
        'file_patterns': set(),
        'root_patterns': set(),
    }

    for raw_line in gitignore_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or line.startswith('!'):
            continue

        anchored_to_root = line.startswith('/')

        normalized = line.strip('/')
        if raw_line.rstrip().endswith('/') and normalized:
            if anchored_to_root:
                rules['root_dirs'].add(normalized)
            else:
                rules['dir_names'].add(Path(normalized).name)
            continue

        if not normalized:
            continue

        if any(token in line for token in ('*', '?', '[')):
            if anchored_to_root or '/' in normalized:
                rules['root_patterns'].add(normalized)
            else:
                rules['file_patterns'].add(normalized)
            continue

        if anchored_to_root or '/' in normalized:
            rules['relative_files'].add(normalized)
        else:
            rules['file_names'].add(normalized)

    return rules


def is_in_ignored_dir(path: Path, root_dir: Path, dir_names: set[str], root_dirs: set[str]) -> bool:
    rel_path = path.relative_to(root_dir).as_posix()

    if any(dir_name in path.relative_to(root_dir).parts for dir_name in dir_names):
        return True

    for root_dir_rule in root_dirs:
        prefix = f"{root_dir_rule.rstrip('/')}/"
        if rel_path.startswith(prefix):
            return True

    return False


def is_gitignored_file(
    path: Path,
    root_dir: Path,
    file_names: set[str],
    relative_files: set[str],
    file_patterns: set[str],
    root_patterns: set[str],
) -> bool:
    rel_path = path.relative_to(root_dir).as_posix()

    if path.name in file_names or rel_path in relative_files:
        return True

    for pattern in file_patterns:
        if fnmatch.fnmatch(path.name, pattern) or fnmatch.fnmatch(rel_path, pattern):
            return True

    for pattern in root_patterns:
        if fnmatch.fnmatch(rel_path, pattern):
            return True

    return False


def build_context():
    root_dir = Path(__file__).parent
    output_file = root_dir / "_AI_CONTEXT.md"
    gitignore_rules = load_gitignore_rules(root_dir)
    
    # 1. SMARTE ERKENNUNG: Ignorierte Ordner und Dateien
    ignore_dirs = {'.venv', '_book', '.backups', '.git', 'bookconfig', 'export', 'processed', 'tools', 'tests'}
    ignore_dirs.update(gitignore_rules['dir_names'])
    valid_extensions = {'.py'}
    ignore_files = {Path(__file__).name, '.gui_state.json', 'tasks.json', 'test.py', 'smoke_tests.py'}

    # 2. SAMMEL-PHASE: Zuerst alle relevanten Dateien finden
    files_to_pack = []
    for path in root_dir.rglob('*'):
        if not path.is_file():
            continue
        
        # Check: Liegt die Datei in einem ignorierten Ordner?
        if is_in_ignored_dir(path, root_dir, ignore_dirs, gitignore_rules['root_dirs']):
            continue

        if is_gitignored_file(
            path,
            root_dir,
            gitignore_rules['file_names'],
            gitignore_rules['relative_files'],
            gitignore_rules['file_patterns'],
            gitignore_rules['root_patterns'],
        ):
            continue
            
        # Check: Ist es ein relevanter Code-Typ und nicht auf der Blacklist?
        if path.suffix in valid_extensions and path.name not in ignore_files:
            files_to_pack.append(path)
            
    # Alphabetisch sortieren für eine saubere Liste
    files_to_pack.sort()

    # 3. SCHREIB-PHASE: Datei erstellen
    with open(output_file, 'w', encoding='utf-8') as out:
        # --- HEADER ---
        out.write("# PROJEKT-KONTEXT: BOOK STUDIO\n")
        out.write(f"Generiert am: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n")
        
        # --- DAS NEUE INHALTSVERZEICHNIS ---
        out.write("## 🗂️ GEPACKTE DATEIEN (Inhaltsverzeichnis)\n")
        out.write("Folgende Dateien wurden in diesem Kontext gebündelt:\n\n")
        
        if not files_to_pack:
            out.write("> ⚠️ Keine passenden Dateien gefunden.\n")
        else:
            for path in files_to_pack:
                rel_path = path.relative_to(root_dir).as_posix()
                out.write(f"- `{rel_path}`\n")
                
        out.write("\n---\n\n")

        # --- DATEI-INHALTE ---
        count = 0
        for path in files_to_pack:
            rel_path = path.relative_to(root_dir).as_posix()
            lang = path.suffix.replace('.', '')
            if lang == 'yml':
                lang = 'yaml'
            
            out.write(f"\n\n{'='*70}\n")
            out.write(f"📁 FILE: {rel_path}\n")
            out.write(f"{'='*70}\n\n")
            
            out.write(f"```{lang}\n")
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    out.write(f.read())
                count += 1
            except (OSError, UnicodeDecodeError) as e:
                out.write(f"# FEHLER BEIM LESEN DER DATEI: {e}\n")
            out.write("\n```\n")

    print(f"✅ Kontext erfolgreich gebündelt! {count} Dateien verarbeitet.")
    print(f"👉 Dateiname: {output_file.name}")

    # === NEU: EXPLORER ÖFFNEN UND DATEI MARKIEREN ===
    try:
        if platform.system() == "Windows":
            subprocess.Popen(f'explorer /select,"{output_file.resolve()}"')
        elif platform.system() == "Darwin": # macOS
            subprocess.Popen(["open", "-R", str(output_file.resolve())])
        else: # Linux
            subprocess.Popen(["xdg-open", str(output_file.parent.resolve())])
    except (OSError, subprocess.SubprocessError) as e:
        print(f"⚠️ Konnte Explorer nicht automatisch öffnen: {e}")

if __name__ == "__main__":
    build_context()