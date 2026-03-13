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
        except (OSError, ValueError, TypeError):
            return None

    def build_title_registry(self):
        """Erstellt eine Liste aller .md Dateien mit ihren Titeln und Icons (nur im content-Ordner)."""
        registry = {}
        content_dir = self.book_path / "content"
        
        # Sicherstellen, dass der content-Ordner existiert, bevor wir suchen
        if not content_dir.exists():
            return registry
            
        for p in content_dir.rglob("*.md"):
            # Wir ignorieren nur noch versteckte Systemordner innerhalb von content
            if not any(x.startswith(".") for x in p.parts):
                # Der relative Pfad MUSS weiterhin ab book_path gebildet werden, 
                # da die _quarto.yml die Pfade inkl. "content/..." erwartet!
                rel_path = p.relative_to(self.book_path).as_posix()
                
                title = self.extract_title_from_md(p)
                if title: 
                    content_role = self.extract_content_role_from_md(p)
                    icons = []
                    if "required" in p.parts:
                        icons.append("📌")
                    if content_role == "outline":
                        icons.append("🧭")
                    if icons:
                        title = f"{' '.join(icons)} {title}"
                    registry[rel_path] = title
                else: 
                    registry[rel_path] = f"[FEHLT] {p.stem}"
        return registry

    def extract_content_role_from_md(self, filepath):
        """Liest content_role aus dem YAML-Frontmatter (z. B. outline/content)."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read(5000)

            match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL | re.MULTILINE)
            if match:
                frontmatter = match.group(1)
                role_match = re.search(r'^content_role:\s*["\']?(.*?)["\']?\s*$', frontmatter, re.MULTILINE)
                if role_match:
                    return role_match.group(1).strip().lower()
            return None
        except (OSError, ValueError, TypeError):
            return None

    def build_status_registry(self):
        """Erstellt eine Registry aller Dateistatus für den Filter in der GUI (nur im content-Ordner)."""
        registry = {}
        content_dir = self.book_path / "content"
        
        if not content_dir.exists():
            return registry
            
        for p in content_dir.rglob("*.md"):
            if not any(x.startswith(".") for x in p.parts):
                rel_path = p.relative_to(self.book_path).as_posix()
                registry[rel_path] = self.extract_status_from_md(p)
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
        except (OSError, ValueError, TypeError):
            return "ohne Eintrag"

    def ensure_required_frontmatter(self, filepath, fallback_title=None):
        """Ergänzt fehlende Pflichtfelder, ohne bestehendes Frontmatter-Formatting umzuschreiben."""

        def _yaml_quote(value):
            text = str(value)
            text = text.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{text}"'

        def _strip_outer_quotes(value):
            text = str(value).strip()
            if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
                return text[1:-1]
            return text

        filepath = Path(filepath)
        config_path = Path(__file__).parent / "studio_config.json"

        required_fields = {
            "title": "<filename>",
            "description": "<title>",
            "status": "bookstudio",
        }
        frontmatter_update_mode = "append_only"

        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as c_f:
                    config_data = json.load(c_f)
                    required_fields = config_data.get(
                        "frontmatter_requirements", required_fields
                    )
                    frontmatter_update_mode = str(
                        config_data.get("frontmatter_update_mode", frontmatter_update_mode)
                    ).strip().lower()
            except (OSError, ValueError, TypeError) as e:
                print(f"Fehler beim Lesen der studio_config.json: {e}")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            newline = "\r\n" if "\r\n" in content else "\n"

            # Gruppen: 1=BOM, 2=Frontmatter-Inhalt, 3=Body (unverändert)
            match = re.match(
                r'^(\uFEFF?)---\s*[\r\n]+(.*?)[\r\n]+---\s*[\r\n]*(.*)$',
                content,
                re.DOTALL,
            )

            keys_to_process = list(required_fields.keys())
            if "title" in keys_to_process:
                keys_to_process.remove("title")
                keys_to_process.insert(0, "title")

            if frontmatter_update_mode == "reserialize":
                if match:
                    bom = match.group(1)
                    frontmatter_str = match.group(2)
                    body = match.group(3)
                    try:
                        parsed_yaml = yaml.safe_load(frontmatter_str) or {}
                    except yaml.YAMLError:
                        return False
                else:
                    bom = ""
                    body = content.strip("\r\n")
                    parsed_yaml = {}

                changed = False
                for key in keys_to_process:
                    if key in parsed_yaml:
                        continue

                    config_val = required_fields[key]
                    if config_val == "<filename>":
                        val = fallback_title if fallback_title else filepath.stem
                    elif config_val == "<title>":
                        val = parsed_yaml.get(
                            "title", fallback_title if fallback_title else filepath.stem
                        )
                    else:
                        val = config_val
                    parsed_yaml[key] = val
                    changed = True

                if not changed:
                    return False

                dumped = yaml.safe_dump(
                    parsed_yaml,
                    sort_keys=False,
                    allow_unicode=True,
                    default_flow_style=False,
                ).rstrip("\r\n")
                new_content = f"{bom}---{newline}{dumped}{newline}---{newline}{body}"

                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                return True

            if match:
                bom = match.group(1)
                frontmatter_str = match.group(2)
                body = match.group(3)

                existing_keys = set()
                for line in frontmatter_str.splitlines():
                    key_match = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*:", line)
                    if key_match:
                        existing_keys.add(key_match.group(1))

                title_match = re.search(
                    r'^\s*title\s*:\s*(.*?)\s*$',
                    frontmatter_str,
                    flags=re.MULTILINE,
                )
                parsed_title = (
                    _strip_outer_quotes(title_match.group(1))
                    if title_match
                    else (fallback_title if fallback_title else filepath.stem)
                )

                additions = []
                for key in keys_to_process:
                    if key in existing_keys:
                        continue

                    config_val = required_fields[key]
                    if config_val == "<filename>":
                        val = fallback_title if fallback_title else filepath.stem
                    elif config_val == "<title>":
                        val = parsed_title
                    else:
                        val = config_val

                    additions.append(f"{key}: {_yaml_quote(val)}")
                    if key == "title":
                        parsed_title = str(val)

                if not additions:
                    return False

                updated_frontmatter = frontmatter_str.rstrip("\r\n")
                if updated_frontmatter:
                    updated_frontmatter += newline
                updated_frontmatter += newline.join(additions)

                new_content = (
                    f"{bom}---{newline}{updated_frontmatter}{newline}---{newline}{body}"
                )
            else:
                base_title = fallback_title if fallback_title else filepath.stem
                value_map = {}
                for key in keys_to_process:
                    config_val = required_fields[key]
                    if config_val == "<filename>":
                        value_map[key] = base_title
                    elif config_val == "<title>":
                        value_map[key] = value_map.get("title", base_title)
                    else:
                        value_map[key] = config_val

                fm_lines = [f"{key}: {_yaml_quote(value_map[key])}" for key in keys_to_process]
                body = content.lstrip("\r\n")
                new_content = f"---{newline}{newline.join(fm_lines)}{newline}---{newline}{body}"

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
            return True

        except (OSError, ValueError, TypeError) as e:
            print(f"Fehler beim Auto-Healing: {e}")
            return False
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

        # --- REQUIRED-FILE ORDERING ---
        # Extrahiert required-Dateien mit order-Frontmatter und setzt sie an Anfang/Ende.
        rest, front_required, end_required = self._apply_required_ordering(chapters)
        if front_required or end_required:
            # index.md aus rest entfernen, damit sie immer an Position 0 bleibt
            rest_without_index = [c for c in rest if c != "index.md"]
            chapters = ["index.md"] + front_required + rest_without_index + end_required
        # ------------------------------

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
            if "format" not in config:
                config["format"] = {}
            for fmt, options in extra_format_options.items():
                if fmt not in config["format"]:
                    config["format"][fmt] = {}
                for key, val in options.items():
                    config["format"][fmt][key] = val
        # ---------------------------------------------------------

        with open(self.yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, sort_keys=False, allow_unicode=True, indent=2)
            
        if save_gui_state:
            self._save_gui_state(tree_data)

    # =========================================================================
    # REQUIRED-FILE ORDERING
    # =========================================================================

    def parse_required_order(self, rel_path):
        """
        Liest das 'order'-Feld aus dem Frontmatter einer required-Datei.

        Gültige Werte:
          "1", "2", "3" …       → Anfang des Buchs (nach index.md), aufsteigend sortiert
          "END-1", "END-2" …  → Ende des Buchs, aufsteigend sortiert

        Rückgabe: (sort_key: int, group: 'front'|'end'|None)
        """
        if "required" not in Path(rel_path).parts:
            return None, None

        full_path = self.book_path / rel_path
        if not full_path.exists():
            return None, None

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read(800)
            match = re.match(r'^\uFEFF?---\s*[\r\n]+(.*?)[\r\n]+---', content, re.DOTALL)
            if not match:
                return None, None
            fm = yaml.safe_load(match.group(1)) or {}
            order_val = str(fm.get("order", "")).strip()
            if not order_val:
                return None, None

            end_match = re.match(r'^END-(\d+)$', order_val, re.IGNORECASE)
            if end_match:
                return int(end_match.group(1)), "end"
            if order_val.isdigit():
                return int(order_val), "front"
        except (OSError, yaml.YAMLError, ValueError):
            pass

        return None, None

    def get_required_order(self, rel_path):
        """Öffentliche API für die ORDER-Auswertung bei required-Dateien."""
        return self.parse_required_order(rel_path)

    def _apply_required_ordering(self, chapters):
        """
        Extrahiert required-Dateien mit 'order'-Frontmatter aus der Kapitelliste
        und gibt (bereinigte Liste, front-Pfade, end-Pfade) zurück.

        Nicht-geordnete required-Dateien bleiben an ihrer GUI-Position.
        PART-Einträge werden rekursiv bereinigt.
        """
        front = []  # (sort_key, path)
        end = []    # (sort_key, path)

        def remove_ordered(items):
            cleaned = []
            for item in items:
                if isinstance(item, str):
                    sort_key, group = self.parse_required_order(item)
                    if group == "front":
                        front.append((sort_key, item))
                    elif group == "end":
                        end.append((sort_key, item))
                    else:
                        cleaned.append(item)
                elif isinstance(item, dict) and "part" in item:
                    sub = remove_ordered(item.get("chapters", []))
                    cleaned.append({**item, "chapters": sub})
                else:
                    cleaned.append(item)
            return cleaned

        cleaned = remove_ordered(chapters)
        front.sort(key=lambda x: x[0])                    # "1" < "2" < "3" → vorne
        end.sort(key=lambda x: x[0], reverse=True)        # "3" > "2" > "1" → END-1 landet ganz am Ende
        return cleaned, [p for _, p in front], [p for _, p in end]

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
        except (OSError, TypeError, ValueError):
            pass

    def _load_gui_state(self):
        if self.gui_state_path.exists():
            try:
                with open(self.gui_state_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
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
    
    def generate_yaml_string(self, tree_data, base_indent="  "):
        return self._generate_yaml_string(tree_data, base_indent=base_indent)