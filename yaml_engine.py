import re
import json
from pathlib import Path

# =============================================================================
# YAML ENGINE - QUARTO NATIVE FLATTENING & GUI STATE PRESERVATION
# =============================================================================

class QuartoYamlEngine:
    def __init__(self, book_path):
        self.book_path = Path(book_path)
        self.yaml_path = self.book_path / "_quarto.yml"
        self.gui_state_path = self.book_path / "bookconfig" / ".gui_state.json"

    # =========================================================================
    # 1. FRONTMATTER & METADATEN EXTRAKTION
    # =========================================================================
    def extract_title_from_md(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read(5000)
            
            title = None
            match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL | re.MULTILINE)
            if match:
                frontmatter = match.group(1)
                title_match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', frontmatter, re.MULTILINE)
                if title_match:
                    title = title_match.group(1).strip()
            
            if title:
                body = content[match.end():].strip() if match else content.strip()
                lines = [l.strip() for l in body.split('\n') if l.strip()]
                # NEU: Markiere Dateien, die NUR aus einer Überschrift bestehen, als Struktur-Knoten!
                if len(lines) == 1 and lines[0].startswith('#'):
                    return f"📁 {title}" 
                return title
            return None 
        except Exception:
            return None

    def build_title_registry(self):
        registry = {}
        for p in self.book_path.rglob("*.md"):
            # Ignoriere System- und Export-Ordner
            if not any(x.startswith(".") for x in p.parts) and "export" not in p.parts:
                rel_path = p.relative_to(self.book_path).as_posix()
                if rel_path == "index.md": continue
                title = self.extract_title_from_md(p)
                if title: registry[rel_path] = title
                else: registry[rel_path] = f"[FEHLT] {p.stem}"
        return registry

    # =========================================================================
    # 2. STRUKTUR LESEN (LÄDT DEN TIEFEN GUI-STATE ODER DEN FLACHEN FALLBACK)
    # =========================================================================
    def parse_chapters(self):
        # 1. Versuch: Lade die schöne, tiefe GUI-Struktur (falls aktuell)
        if self.gui_state_path.exists() and self.yaml_path.exists():
            if self.gui_state_path.stat().st_mtime >= self.yaml_path.stat().st_mtime:
                try:
                    with open(self.gui_state_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception:
                    pass

        # 2. Fallback: Wenn kein State existiert, parse die flache _quarto.yml
        if not self.yaml_path.exists(): return []
        try:
            with open(self.yaml_path, 'r', encoding='utf-8') as f:
                all_lines = f.read().splitlines()
        except Exception: return []
            
        start_idx = -1
        for i, l in enumerate(all_lines):
            if l.strip() == "chapters:" and not l.lstrip().startswith("-"):
                start_idx = i + 1
                break
        
        if start_idx == -1: return []
        
        data = []
        stack = [(0, data)] 
        
        for l in all_lines[start_idx:]:
            if not l.strip() or l.strip().startswith("#"): continue
            indent = len(l) - len(l.lstrip())
            if indent == 0 and not l.lstrip().startswith("-"): break 
            
            clean = l.strip()
            
            if clean.startswith("- part:"):
                val = clean.split(":", 1)[1].strip().strip('"\'')
                new_item = {"path": val, "children": []}
                while len(stack) > 1: stack.pop()
                stack[-1][1].append(new_item)
                continue

            elif clean == "chapters:":
                last_added = stack[-1][1][-1]
                stack.append((indent, last_added["children"]))
                continue

            elif clean.startswith("-"):
                val = clean[1:].strip().strip('"\'')
                if not val.endswith(".md"): continue
                new_item = {"path": val, "children": []}
                while len(stack) > 1 and indent <= stack[-1][0]:
                    stack.pop()
                stack[-1][1].append(new_item)

        return data

    # =========================================================================
    # 3. QUARTO FLATTENING LOGIK (MACHT QUARTO GLÜCKLICH)
    # =========================================================================
    def _flatten_to_files(self, items):
        """Holt alle Dateipfade aus beliebig tiefen Unterordnern für die flache Quarto-Liste."""
        flat = []
        for item in items:
            flat.append(item["path"])
            if item.get("children"):
                flat.extend(self._flatten_to_files(item["children"]))
        return flat

    def _generate_yaml_string(self, tree_data, base_indent="  "):
        """Generiert die streng auf 2 Ebenen limitierte Quarto-Struktur."""
        lines = []
        for item in tree_data:
            path = item["path"]
            children = item.get("children", [])
            
            if children:
                # Die Ankerdatei MUSS der Part-Wert sein, sonst gibt es Duplikate im IVZ!
                lines.append(f"{base_indent}- part: \"{path}\"")
                lines.append(f"{base_indent}  chapters:")
                
                # Alle Unterordner und deren Kinder rigoros flachklopfen
                flat_paths = self._flatten_to_files(children)
                for c_path in flat_paths:
                    lines.append(f"{base_indent}    - \"{c_path}\"")
            else:
                lines.append(f"{base_indent}- \"{path}\"")
                
        return "\n".join(lines)

    # =========================================================================
    # 4. YAML SCHREIBEN & EXPORT VERZEICHNIS
    # =========================================================================
    def save_chapters(self, tree_data, profile_name=None, save_gui_state=True): # <-- NEU
        if not self.yaml_path.exists(): 
            raise FileNotFoundError(f"Die Datei {self.yaml_path} existiert nicht.")

        # 1. TIEFEN GUI-STATE SPEICHERN (Nur wenn nicht im Render-Modus!)
        if save_gui_state: # <-- NEU
            self.gui_state_path.parent.mkdir(exist_ok=True)
            with open(self.gui_state_path, 'w', encoding='utf-8') as f:
                json.dump(tree_data, f, ensure_ascii=False, indent=4)

        # 2. _quarto.yml OPERIEREN
        # 1. TIEFEN GUI-STATE SPEICHERN, DAMIT DIE STRUKTUR IM STUDIO ERHALTEN BLEIBT
        self.gui_state_path.parent.mkdir(exist_ok=True)
        with open(self.gui_state_path, 'w', encoding='utf-8') as f:
            json.dump(tree_data, f, ensure_ascii=False, indent=4)

        # 2. _quarto.yml OPERIEREN
        with open(self.yaml_path, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()

        safe_profile = re.sub(r'[^a-zA-Z0-9_\-]', '_', profile_name) if profile_name else None

        # PASS 1: Dynamisches Setzen von output-dir und output-file (in export/ Ordner!)
        new_lines = []
        in_book = False
        in_project = False
        
        for line in lines:
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())
            
            if stripped == "project:":
                in_project = True
                new_lines.append(line)
                continue
            
            if in_project:
                if stripped.startswith("output-dir:"):
                    if safe_profile:
                        new_lines.append(f"  output-dir: export/_book_{safe_profile}")
                    else:
                        new_lines.append(f"  output-dir: export/_book")
                    continue
                if indent == 0 and stripped != "" and not stripped.startswith("#"):
                    in_project = False
                    
            if stripped == "book:":
                in_book = True
                new_lines.append(line)
                if safe_profile:
                    new_lines.append(f"  output-file: \"{safe_profile}\"")
                continue
            
            if in_book:
                if stripped.startswith("output-file:"):
                    continue 
                if indent == 0 and stripped != "" and not stripped.startswith("#"):
                    in_book = False
                    
            new_lines.append(line)
            
        lines = new_lines

        # PASS 2: Den chapters-Block ersetzen (mit dem flachen Quarto-Code!)
        out_lines = []
        in_chapters = False
        chapters_indent = -1
        chapters_found = False

        for line in lines:
            stripped = line.strip()

            if not in_chapters:
                if stripped == 'chapters:' and not line.lstrip().startswith('-'):
                    chapters_indent_str = line[:len(line) - len(line.lstrip())]
                    chapters_indent = len(chapters_indent_str)
                    in_chapters = True
                    chapters_found = True
                    
                    out_lines.append(line)
                    base_indent = chapters_indent_str + "  "
                    out_lines.append(f"{base_indent}- \"index.md\"")
                    
                    # Hier wird die abgeflachte YAML eingeklebt
                    new_yaml = self._generate_yaml_string(tree_data, base_indent=base_indent)
                    if new_yaml:
                        out_lines.append(new_yaml)
                    continue
                out_lines.append(line)
            else:
                if not stripped or stripped.startswith('#'): continue

                current_indent = len(line) - len(line.lstrip())
                if current_indent <= chapters_indent and not stripped.startswith('-'):
                    in_chapters = False
                    out_lines.append(line)

        if not chapters_found:
            raise ValueError("Konnte den Key 'chapters:' nicht finden! Prüfe deine _quarto.yml.")

        with open(self.yaml_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(out_lines) + "\n")