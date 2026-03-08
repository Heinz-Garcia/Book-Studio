import yaml
import re
import json
from pathlib import Path

class QuartoYamlEngine:
    def __init__(self, book_path):
        self.book_path = Path(book_path)
        self.yaml_path = self.book_path / "_quarto.yml"
        self.gui_state_path = self.book_path / "bookconfig" / ".gui_state.json"

    # =========================================================================
    # TITEL- & STATUS-EXTRAKTION (REGISTRY)
    # =========================================================================

    def extract_title_from_md(self, filepath):
        """Liest den Titel aus dem YAML-Frontmatter oder der ersten H1-Überschrift."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read(5000) # Nur den Anfang lesen
            
            # 1. Suche in YAML Frontmatter
            match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL | re.MULTILINE)
            if match:
                frontmatter = match.group(1)
                t_match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', frontmatter, re.MULTILINE)
                if t_match:
                    return t_match.group(1).strip()
            
            # 2. Suche nach erster # Überschrift
            h1_match = re.search(r'^#\s+(.*)$', content, re.MULTILINE)
            if h1_match:
                return h1_match.group(1).strip()
            
            return None
        except Exception:
            return None

    def build_title_registry(self):
        """Erstellt eine Liste aller .md Dateien mit ihren Titeln und Icons."""
        registry = {}
        for p in self.book_path.rglob("*.md"):
            # Ignoriere System- und Export-Ordner
            if not any(x.startswith(".") for x in p.parts) and "export" not in p.parts:
                rel_path = p.relative_to(self.book_path).as_posix()
                if rel_path == "index.md": continue
                
                title = self.extract_title_from_md(p)
                if title: 
                    # --- ICON LOGIK: Schöner Pin für Dateien im "required" Ordner ---
                    if "required" in p.parts:
                        title = f"📌 {title}" 
                    registry[rel_path] = title
                else: 
                    registry[rel_path] = f"[FEHLT] {p.stem}"
        return registry

    def extract_status_from_md(self, filepath):
        """Liest den Status aus dem YAML-Frontmatter (status: "...") aus."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read(5000)
            
            match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL | re.MULTILINE)
            if match:
                frontmatter = match.group(1)
                status_match = re.search(r'^status:\s*["\']?(.*?)["\']?\s*$', frontmatter, re.MULTILINE)
                if status_match:
                    return status_match.group(1).strip()
            return "ohne Eintrag"
        except Exception:
            return "ohne Eintrag"

    def build_status_registry(self):
        """Erstellt eine Registry aller Dateistatus für den Filter in der GUI."""
        registry = {}
        for p in self.book_path.rglob("*.md"):
            if not any(x.startswith(".") for x in p.parts) and "export" not in p.parts:
                rel_path = p.relative_to(self.book_path).as_posix()
                if rel_path == "index.md": continue
                registry[rel_path] = self.extract_status_from_md(p)
        return registry

    # =========================================================================
    # QUARTO YAML PARSING & SAVING
    # =========================================================================

    def _load_quarto_yml(self):
        if not self.yaml_path.exists():
            return {"project": {"type": "book"}, "book": {"chapters": []}}
        with open(self.yaml_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    def parse_chapters(self):
        """Konvertiert die Quarto-YAML Liste in das interne Tree-Format der GUI."""
        # 1. Versuche zuerst, den letzten GUI-Zustand (geöffnete Ordner etc.) zu laden
        gui_state = self._load_gui_state()
        if gui_state:
            return gui_state
            
        # 2. Falls kein GUI-State da ist, lade direkt aus der _quarto.yml
        config = self._load_quarto_yml()
        chapters = config.get("book", {}).get("chapters", [])
        
        def convert(items):
            res = []
            for item in items:
                if isinstance(item, str):
                    res.append({"path": item, "children": []})
                elif isinstance(item, dict):
                    # Quarto Parts/Chapters Logik
                    part_title = item.get("part") or item.get("text")
                    sub = item.get("chapters", [])
                    if part_title:
                        res.append({"path": f"PART:{part_title}", "children": convert(sub)})
                    else:
                        # Einfache Datei mit Meta-Daten
                        file_path = list(item.values())[0] if not item.get("file") else item.get("file")
                        res.append({"path": file_path, "children": []})
            return res
            
        return convert(chapters)

    def save_chapters(self, tree_data, profile_name=None, save_gui_state=True, extra_format_options=None):
        """Speichert die Baum-Struktur in _quarto.yml und injiziert Templates/Profile."""
        config = self._load_quarto_yml()
        
        # 1. Kapitel aus dem Tree konvertieren
        chapters = self._tree_to_quarto_list(tree_data)
        
        # --- FIX: index.md IMMER als erste Datei hinzufügen ---
        if "index.md" not in chapters:
            if (self.book_path / "index.md").exists():
                chapters.insert(0, "index.md")
            else:
                # Falls die Datei gar nicht existiert, erstellen wir eine minimale Version
                with open(self.book_path / "index.md", "w", encoding="utf-8") as f:
                    f.write("---\ntitle: Einleitung\n---\n\nWillkommen zu meinem Buch.")
                chapters.insert(0, "index.md")
        # -------------------------------------------------------

        config["book"]["chapters"] = chapters
        
        # ... (Rest der Funktion bleibt gleich) ...
        
        # Ausgabe-Ordner basierend auf Profil anpassen
        if profile_name:
            safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', profile_name)
            config["project"]["output-dir"] = f"export/_book_{safe_name}"
        else:
            config["project"]["output-dir"] = "export/_book"

        # --- NEU: ZUSATZOPTIONEN (Templates etc.) INJIZIEREN ---
        if extra_format_options:
            if "format" not in config: config["format"] = {}
            for fmt, options in extra_format_options.items():
                if fmt not in config["format"]: config["format"][fmt] = {}
                for key, val in options.items():
                    config["format"][fmt][key] = val
        # ---------------------------------------------------------

        with open(self.yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, sort_keys=False, allow_unicode=True, indent=2)
            
        if save_gui_state:
            self._save_gui_state(tree_data)

    def _tree_to_quarto_list(self, tree_data):
        """Hilfsfunktion: Wandelt den GUI-Baum zurück in Quarto-Syntax."""
        res = []
        for item in tree_data:
            path = item["path"]
            if path.startswith("PART:"):
                res.append({
                    "part": path.replace("PART:", ""),
                    "chapters": self._tree_to_quarto_list(item["children"])
                })
            else:
                # --- DER WINDOWS-FIX ---
                # Wandelt alle Backslashes zwingend in Forward-Slashes um
                safe_path = path.replace("\\", "/")
                res.append(safe_path)
        return res

    # =========================================================================
    # GUI STATE (Sichert geöffnete Ordner & genaue GUI Struktur)
    # =========================================================================

    def _save_gui_state(self, tree_data):
        try:
            self.gui_state_path.parent.mkdir(exist_ok=True)
            with open(self.gui_state_path, 'w', encoding='utf-8') as f:
                json.dump(tree_data, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    def _load_gui_state(self):
        if self.gui_state_path.exists():
            try:
                with open(self.gui_state_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return None
        return None
    
    def _generate_yaml_string(self, tree_data, base_indent="  "):
        """Hilfsfunktion für den Preview-Inspektor."""
        lines = []
        for item in tree_data:
            path = item["path"]
            if path.startswith("PART:"):
                lines.append(f"{base_indent}- part: {path.replace('PART:', '')}")
                lines.append(f"{base_indent}  chapters:")
                if item.get("children"):
                    lines.append(self._generate_yaml_string(item["children"], base_indent + "    "))
            else:
                lines.append(f"{base_indent}- {path}")
        return "\n".join(lines)