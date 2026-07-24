import yaml
import re
import json
import logging
from pathlib import Path

from frontmatter_requirements import (
    load_frontmatter_settings,
    ordered_frontmatter_keys,
    resolve_frontmatter_placeholder,
)
from frontmatter_parser import (
    extract_field as fm_extract_field,
    parse_file as fm_parse_file,
    repair_hidden_yaml_dividers as fm_repair_hidden_yaml_dividers,
)
from quarto_block_parser import (
    repair_orphan_fenced_div_closes as qb_repair_orphan_fenced_div_closes,
)
from markdown_asset_scanner import (
    repair_fragile_relative_image_refs as mas_repair_fragile_relative_image_refs,
)
from page_required import is_page_required

logger = logging.getLogger(__name__)

# Anzeige-Label in title_registry/Pool/Baum, wenn eine .md-Datei kein
# `title:`-Frontmatter und keine `# Ueberschrift` hat. Bewusst NICHT
# "[FEHLT]" (liest sich wie "Datei fehlt", obwohl die Datei inkl. Inhalt
# vollstaendig vorhanden ist -- nur der Titel konnte nicht extrahiert werden).
MISSING_TITLE_LABEL = "[Kein Titel]"


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
                content = f.read(5000)  # Nur den Anfang lesen

            # 1. Suche in YAML Frontmatter (B2/SSOT)
            title = fm_extract_field(content, "title")
            if title:
                return title

            # 2. Suche nach erster # Überschrift
            h1_match = re.search(r'^#\s+(.*)$', content, re.MULTILINE)
            if h1_match:
                return h1_match.group(1).strip()

            return None
        except (OSError, ValueError, TypeError):
            return None

    def build_title_registry(self):
        """Erstellt eine Liste aller .md Dateien mit ihren Titeln und Icons.

        Durchsucht `content/` (rekursiv, wie von `_quarto.yml` referenziert)
        UND die Buch-Wurzel selbst (nicht rekursiv, außer `index.md` keine
        Unterordner): externe Zulieferer (z. B. GrammarGraph) legen ihren
        Nutzinhalt oft als lose .md-Datei direkt im Buchordner ab statt unter
        `content/`; ohne diesen zweiten Scan taucht so eine Datei nie im
        Pool der nicht zugeordneten Kapitel auf.
        """
        registry = {}
        content_dir = self.book_path / "content"

        if content_dir.exists():
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
                        try:
                            md_text = p.read_text(encoding="utf-8")
                        except OSError:
                            md_text = None
                        if is_page_required(rel_path=rel_path, content=md_text):
                            icons.append("📌")
                        if content_role == "outline":
                            icons.append("🧭")
                        if icons:
                            title = f"{' '.join(icons)} {title}"
                        registry[rel_path] = title
                    else:
                        registry[rel_path] = f"{MISSING_TITLE_LABEL} {p.stem}"

        for p in self.book_path.glob("*.md"):
            rel_path = p.name
            if rel_path in registry:
                continue
            title = self.extract_title_from_md(p)
            registry[rel_path] = title if title else f"{MISSING_TITLE_LABEL} {p.stem}"

        return registry

    def extract_content_role_from_md(self, filepath):
        """Liest content_role aus dem YAML-Frontmatter (z. B. outline/content)."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read(5000)

            role = fm_extract_field(content, "content_role")
            if role:
                return role.lower()
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

            status = fm_extract_field(content, "status")
            if status:
                return status
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
        required_fields, frontmatter_update_mode = load_frontmatter_settings()

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

            keys_to_process = ordered_frontmatter_keys(required_fields)

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

                value_map = {str(k): str(v) for k, v in parsed_yaml.items()}
                changed = False
                for key in keys_to_process:
                    if key in parsed_yaml:
                        continue

                    val = resolve_frontmatter_placeholder(
                        required_fields[key],
                        filepath=filepath,
                        body=body,
                        parsed_yaml=parsed_yaml,
                        value_map=value_map,
                        fallback_title=fallback_title,
                    )
                    parsed_yaml[key] = val
                    value_map[key] = str(val)
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
                value_map = {"title": parsed_title} if "title" in existing_keys else {}

                additions = []
                for key in keys_to_process:
                    if key in existing_keys:
                        continue

                    val = resolve_frontmatter_placeholder(
                        required_fields[key],
                        filepath=filepath,
                        body=body,
                        parsed_yaml={},
                        value_map=value_map,
                        fallback_title=fallback_title,
                    )
                    value_map[key] = str(val)
                    additions.append(f"{key}: {_yaml_quote(val)}")

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
                body = content.lstrip("\r\n")
                value_map: dict[str, str] = {}
                for key in keys_to_process:
                    val = resolve_frontmatter_placeholder(
                        required_fields[key],
                        filepath=filepath,
                        body=body,
                        parsed_yaml={},
                        value_map=value_map,
                        fallback_title=fallback_title,
                    )
                    value_map[key] = str(val)

                fm_lines = [
                    f"{key}: {_yaml_quote(value_map[key])}" for key in keys_to_process
                ]
                new_content = f"---{newline}{newline.join(fm_lines)}{newline}---{newline}{body}"

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
            return True

        except (OSError, ValueError, TypeError) as e:
            logger.warning("Fehler beim Auto-Healing für %s: %s", filepath, e)
            return False

    def heal_frontmatter_for_paths(self, used_paths, title_registry=None):
        """Ergänzt Frontmatter für index.md und alle Buch-Kapitel (explizite Heal-Aktion)."""
        title_registry = title_registry or {}
        healed: list[str] = []
        ordered_paths = list(dict.fromkeys(["index.md", *list(used_paths or [])]))

        for rel_path in ordered_paths:
            if not str(rel_path).lower().endswith(".md"):
                continue
            full_path = self.book_path / rel_path
            if not full_path.exists():
                continue

            fallback_title = title_registry.get(rel_path, Path(rel_path).stem)
            if isinstance(fallback_title, str):
                fallback_title = fallback_title.replace(f"{MISSING_TITLE_LABEL} ", "")

            if self.ensure_required_frontmatter(full_path, fallback_title):
                healed.append(rel_path)

        return healed

    def prepare_file_for_render(self, filepath, fallback_title=None):
        """Auto-Healing vor Render: Pflicht-Frontmatter, versteckte ``---``,
        verwaiste ``:::`` und render-fragile relative Bildpfade."""
        filepath = Path(filepath)
        changes = []

        if self.ensure_required_frontmatter(filepath, fallback_title):
            changes.append("Pflicht-Frontmatter ergänzt")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            new_content, repaired = fm_repair_hidden_yaml_dividers(content)
            if repaired:
                content = new_content
                changes.append("Versteckte '---' im Text durch '***' ersetzt")

            new_content, removed_orphan_lines = qb_repair_orphan_fenced_div_closes(content)
            if removed_orphan_lines:
                content = new_content
                locs = ", ".join(f"L{n}" for n in removed_orphan_lines)
                changes.append(
                    f"Verwaiste schließende ':::'-Marker entfernt ({locs})"
                )

            new_content, image_changes = mas_repair_fragile_relative_image_refs(
                content, filepath.parent, self.book_path
            )
            if image_changes:
                content = new_content
                changes.extend(image_changes)

            if repaired or removed_orphan_lines or image_changes:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
        except (OSError, ValueError, TypeError) as e:
            logger.warning("Fehler beim Render-Auto-Healing für %s: %s", filepath, e)

        return changes

    def prepare_book_for_render(self, used_paths, title_registry=None):
        """Bereitet alle relevanten Markdown-Dateien vor dem Render-Preflight vor."""
        title_registry = title_registry or {}
        ordered_paths = list(dict.fromkeys(["index.md", *list(used_paths or [])]))
        results = []

        for rel_path in ordered_paths:
            if not str(rel_path).lower().endswith(".md"):
                continue
            full_path = self.book_path / rel_path
            if not full_path.exists():
                continue

            fallback_title = title_registry.get(rel_path, Path(rel_path).stem)
            if isinstance(fallback_title, str):
                fallback_title = fallback_title.replace(f"{MISSING_TITLE_LABEL} ", "")

            file_changes = self.prepare_file_for_render(full_path, fallback_title)
            if file_changes:
                results.append((rel_path, file_changes))

        return results

    # =========================================================================
    # QUARTO YAML PARSING & SAVING
    # =========================================================================

    def _load_quarto_yml(self):
        if not self.yaml_path.exists():
            return {"project": {"type": "book"}, "book": {"chapters": []}}
        with open(self.yaml_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    def _is_gui_state_fresh(self):
        """B-Fix (Code-Review 2026-07-03): `.gui_state.json` ist nur ein
        Cache des zuletzt von der GUI gespeicherten Baums. Vorher wurde er
        bedingungslos bevorzugt, auch wenn `_quarto.yml` zwischenzeitlich
        manuell bearbeitet oder frisch (re-)importiert wurde – manuelle
        Aenderungen verschwanden dadurch unsichtbar. Der Cache gilt nur
        noch als gueltig, wenn er nicht AELTER ist als `_quarto.yml`.
        """
        if not self.gui_state_path.exists():
            return False
        if not self.yaml_path.exists():
            return True
        try:
            return self.gui_state_path.stat().st_mtime >= self.yaml_path.stat().st_mtime
        except OSError:
            return False

    def parse_chapters(self):
        """Konvertiert die Quarto-YAML Liste in das interne Tree-Format der GUI."""
        # 1. Versuche zuerst, den letzten GUI-Zustand (geöffnete Ordner etc.)
        #    zu laden – aber nur, wenn er nicht durch eine neuere
        #    `_quarto.yml` bereits ueberholt ist.
        if self._is_gui_state_fresh():
            gui_state = self._load_gui_state()
            if gui_state:
                return gui_state

        # 2. Falls kein (aktueller) GUI-State da ist, lade direkt aus der _quarto.yml
        config = self._load_quarto_yml()
        chapters = config.get("book", {}).get("chapters", [])

        def convert(items):
            res = []
            for item in items:
                if isinstance(item, str):
                    res.append({
                        "path": item,
                        "title": self._resolve_title_for_path(item),
                        "children": [],
                    })
                elif isinstance(item, dict):
                    # Quarto Parts/Chapters Logik
                    part_title = item.get("part") or item.get("text")
                    sub = item.get("chapters", [])
                    if part_title:
                        res.append({
                            "path": f"PART:{part_title}",
                            "title": part_title,
                            "children": convert(sub),
                        })
                    else:
                        # Einfache Datei mit Meta-Daten. Quarto erlaubt u.a.
                        # {"file": "x.qmd"} oder {"href": "x.qmd", "text": "..."}.
                        # B-Fix (Code-Review 2026-07-03): der vorherige Fallback
                        # `list(item.values())[0]` haengt von der Dict-
                        # Reihenfolge im YAML ab - bei z. B.
                        # {"text": "...", "href": "x.qmd"} wurde faelschlich
                        # der Titel statt des Pfads gezogen. Bekannte
                        # Schluessel ("file"/"href") haben jetzt Vorrang.
                        file_path = item.get("file") or item.get("href")
                        if not file_path:
                            string_values = [v for v in item.values() if isinstance(v, str)]
                            file_path = string_values[0] if string_values else ""
                        res.append({
                            "path": file_path,
                            "title": self._resolve_title_for_path(file_path),
                            "children": [],
                        })
            return res

        return convert(chapters)

    def _resolve_title_for_path(self, rel_path):
        """Ermittelt einen Anzeige-Titel fuer *rel_path*, wenn `parse_chapters`
        direkt aus der `_quarto.yml` konvertiert (kein GUI-State-Cache).

        B-Fix (Code-Review 2026-07-03): `convert()` lieferte hier zuvor
        GAR KEIN `title`-Feld. Das blieb lange unbemerkt, weil `.gui_state
        .json` (das IMMER Titel enthaelt) bislang bedingungslos bevorzugt
        wurde. Seit dieser Cache jetzt auf Aktualitaet geprueft wird (siehe
        `_is_gui_state_fresh`), kann dieser Zweig haeufiger greifen -
        Konsumenten wie `pre_processor.py` (`root_node["title"]`) brauchen
        das Feld zwingend.
        """
        if not rel_path:
            return ""
        try:
            extracted = self.extract_title_from_md(self.book_path / rel_path)
        except (OSError, RuntimeError, TypeError, ValueError, AttributeError):
            extracted = None
        if extracted:
            return str(extracted)
        return Path(rel_path).stem

    def save_chapters(self, tree_data, profile_name=None, save_gui_state=True, extra_format_options=None):
        """Speichert die Baum-Struktur in _quarto.yml und injiziert Templates/Profile."""
        config = self._load_quarto_yml()
        # B-Fix (Code-Review 2026-07-03): eine von Hand bearbeitete
        # `_quarto.yml`, der die Top-Level-Schluessel `project`/`book`
        # fehlen, fuehrte weiter unten zu einem KeyError bei
        # `config["book"]["chapters"] = ...` bzw. `config["project"][...]`.
        if not isinstance(config, dict):
            config = {}
        config.setdefault("project", {"type": "book"})
        if not isinstance(config.get("project"), dict):
            config["project"] = {"type": "book"}
        config.setdefault("book", {})
        if not isinstance(config.get("book"), dict):
            config["book"] = {}

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

        Eligibility: Frontmatter ``required: true`` (SSOT). Legacy-Fallback:
        Datei unter ``content/required/`` ohne explizites ``required: false``.

        Rückgabe: (sort_key: int, group: 'front'|'end'|None)
        """
        full_path = self.book_path / rel_path
        content = None
        if full_path.exists():
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read(12000)
            except OSError as error:
                logger.warning("ORDER-Frontmatter konnte nicht gelesen werden (%s): %s", rel_path, error)
                return None, None

        if not is_page_required(rel_path=str(rel_path), content=content):
            return None, None
        if not content:
            return None, None

        try:
            match = re.search(r'^\s*\uFEFF?---\s*[\r\n]+(.*?)[\r\n]+---', content, re.DOTALL | re.MULTILINE)
            if not match:
                return None, None
            fm = yaml.safe_load(match.group(1)) or {}
            order_val = str(fm.get("order", "")).strip().strip('"\'')
            if not order_val:
                return None, None

            end_match = re.match(r'^END\s*-\s*(\d+)$', order_val, re.IGNORECASE)
            if end_match:
                return int(end_match.group(1)), "end"
            if re.match(r'^\d+$', order_val):
                return int(order_val), "front"
        except (OSError, yaml.YAMLError, ValueError) as error:
            logger.warning("ORDER-Frontmatter konnte nicht gelesen werden (%s): %s", rel_path, error)

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
        except (OSError, TypeError, ValueError) as error:
            logger.warning("GUI-State konnte nicht gespeichert werden (%s): %s", self.gui_state_path, error)

    def _load_gui_state(self):
        if self.gui_state_path.exists():
            try:
                with open(self.gui_state_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
                logger.warning("GUI-State konnte nicht geladen werden (%s): %s", self.gui_state_path, error)
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