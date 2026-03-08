import os
import subprocess
import platform
from pathlib import Path
from datetime import datetime

def build_context():
    root_dir = Path(__file__).parent
    output_file = root_dir / "_AI_CONTEXT.md"
    
    # 1. SMARTE ERKENNUNG: Ignorierte Ordner und Dateien
    ignore_dirs = {'.venv', '_book', '.backups', '.git', 'bookconfig', 'export', 'processed', '__pycache__', '.quarto'}
    valid_extensions = {'.py', '.yml', '.yaml', '.json'}
    ignore_files = {output_file.name, Path(__file__).name, '.gui_state.json', 'tasks.json'}

    # 2. SAMMEL-PHASE: Zuerst alle relevanten Dateien finden
    files_to_pack = []
    for path in root_dir.rglob('*'):
        if not path.is_file():
            continue
        
        # Check: Liegt die Datei in einem ignorierten Ordner?
        if any(ignored in path.parts for ignored in ignore_dirs):
            continue
            
        # Check: Ist es ein relevanter Code-Typ und nicht auf der Blacklist?
        if path.suffix in valid_extensions and path.name not in ignore_files:
            files_to_pack.append(path)
            
    # Alphabetisch sortieren für eine saubere Liste
    files_to_pack.sort()

    # 3. SCHREIB-PHASE: Datei erstellen
    with open(output_file, 'w', encoding='utf-8') as out:
        # --- HEADER ---
        out.write(f"# PROJEKT-KONTEXT: BOOK STUDIO\n")
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
            if lang == 'yml': lang = 'yaml'
            
            out.write(f"\n\n{'='*70}\n")
            out.write(f"📁 FILE: {rel_path}\n")
            out.write(f"{'='*70}\n\n")
            
            out.write(f"```{lang}\n")
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    out.write(f.read())
                count += 1
            except Exception as e:
                out.write(f"# FEHLER BEIM LESEN DER DATEI: {e}\n")
            out.write(f"\n```\n")

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
    except Exception as e:
        print(f"⚠️ Konnte Explorer nicht automatisch öffnen: {e}")

if __name__ == "__main__":
    build_context()