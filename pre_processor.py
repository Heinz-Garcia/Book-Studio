import re
import shutil
from pathlib import Path
import yaml

# B4 (Refactoring): Die komplette Fußnoten-Funktionalität wurde
# entfernt. Pandoc-konforme `[^1]`-Marker im Quell-Markdown werden
# unverändert weitergereicht — Quarto kümmert sich um die Auflösung.
# Die frühere `_namespace_local_footnotes` / `_inject_footnote_backlinks`
# / `_uses_harvester` / `FootnoteHarvester`-Logik existiert nicht mehr.


class PreProcessor:
    def __init__(self, book_path, output_format="typst"):
        """Bereitet ein Quarto-Buch für den Render vor.

        Vor B4 wurden hier `footnote_mode` und `enable_footnote_backlinks`
        entgegengenommen. Beide Parameter wurden entfernt — das gesamte
        Fußnoten-Harvesting/Endnoten-System ist stillgelegt.
        """
        self.book_path = Path(book_path)
        self.processed_dir = self.book_path / "processed"
        self.output_format = str(output_format) if output_format else "typst"

    def _extract_parts(self, content):
        """Trennt Frontmatter extrem robust vom Text ab, selbst bei Windows-BOMs."""
        match = re.match(r'^\uFEFF?---\s*[\r\n]+(.*?)[\r\n]+---\s*[\r\n]*', content, re.DOTALL)
        if match:
            return match.group(0), content[match.end():]
        return "", content

    def _sanitize_frontmatter_for_render(self, frontmatter):
        """Entfernt nicht-numerisches `order` im processed-Klon (Quarto verlangt Number)."""
        if not frontmatter:
            return frontmatter

        match = re.match(
            r'^(\uFEFF?)---\s*[\r\n]+(.*?)[\r\n]+---\s*[\r\n]*$',
            frontmatter,
            re.DOTALL,
        )
        if not match:
            return frontmatter

        bom = match.group(1)
        frontmatter_body = match.group(2)
        newline = "\r\n" if "\r\n" in frontmatter else "\n"

        try:
            parsed = yaml.safe_load(frontmatter_body) or {}
        except yaml.YAMLError:
            return frontmatter

        order_val = parsed.get("order")
        if order_val is None:
            return frontmatter

        is_numeric_order = False
        if isinstance(order_val, (int, float)):
            is_numeric_order = True
        elif isinstance(order_val, str) and re.fullmatch(r"\d+", order_val.strip()):
            is_numeric_order = True

        if is_numeric_order:
            return frontmatter

        parsed.pop("order", None)
        dumped = yaml.safe_dump(
            parsed,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        ).rstrip("\r\n")

        return f"{bom}---{newline}{dumped}{newline}---{newline}"

    def _prune_unused_footnote_definitions(self, text):
        """B4-Stub: Vorher entfernte diese Methode ungenutzte Fußnoten-
        Definitionen. Mit der Abschaltung der Fußnoten-Verarbeitung ist
        sie ein No-op — bleibt aber als stabile API für externe Importer
        erhalten."""
        return text

    # =========================================================================
    # NEU: DER WASCHGANG FÜR KAPUTTE MARKDOWN-SYNTAX
    # =========================================================================
    def _sanitize_markdown(self, text):
        """Repariert alte Boxen und übersetzt @-Zitationen absolut verlustfrei in echte Fußnoten."""
        
        # 1. Boxen reparieren: :::: \[BOX: Titel\] Inhalt ::: -> Quarto Callout
        text = re.sub(
            r':{3,4}\s*\\?\[BOX:\s*(.*?)\\?\](.*?):{3,4}', 
            r'::: {.callout-note title="\1"}\n\2\n:::', 
            text, 
            flags=re.DOTALL
        )
        
        # 1b. Übrig gebliebene eklige 4er-Doppelpunkte auf saubere 3er kürzen
        text = re.sub(r'^::::\s*$', r':::', text, flags=re.MULTILINE)
        
        # 2. @-ZITATIONEN ROBUST IN FUSSNOTEN UMWANDELN
        # Ziel: Auch Varianten wie [@Key, S. 331] oder [vgl. @Key1; @Key2] sicher abfangen.

        # A) Definitionszeilen mit Klammernotation normalisieren:
        #    [@Key, S. 331]: Text  ->  [^Key]: Text
        text = re.sub(
            r'^([ \t]*)\[@([a-zA-Z0-9_-]+)(?:[^\]]*)\]:',
            r'\1[^\2]:',
            text,
            flags=re.MULTILINE,
        )

        # B) Definitionszeilen ohne Klammern normalisieren:
        #    @Key: Text -> [^Key]: Text
        text = re.sub(
            r'^([ \t]*)@([a-zA-Z0-9_-]+):',
            r'\1[^\2]:',
            text,
            flags=re.MULTILINE,
        )

        # C) Klammer-Zitationsgruppen in Marker umwandeln:
        #    [@Key, S. 331] -> [^Key]
        #    [vgl. @A; @B]  -> [^A][^B]
        def _replace_citation_group(match):
            group_content = match.group(1)
            labels = re.findall(r'@([a-zA-Z0-9_-]+)', group_content)
            if not labels:
                return match.group(0)
            unique_labels = []
            seen = set()
            for label in labels:
                if label in seen:
                    continue
                seen.add(label)
                unique_labels.append(label)
            return ''.join(f'[^{label}]' for label in unique_labels)

        text = re.sub(r'\[([^\]\n]*@[^\]\n]*)\]', _replace_citation_group, text)

        # D) Bare @Label-Verweise im Fließtext umwandeln (ohne E-Mail/Teilwörter zu beschädigen)
        #    Beispiel: "... (siehe @Key)" -> "... (siehe [^Key])"
        text = re.sub(r'(?<![\w\[\^])@([a-zA-Z0-9_-]+)', r'[^\1]', text)
        
        return text
    # =========================================================================

    def _gather_all_definitions(self, nodes):
        """B4-Stub: Vorher wurden hier in einem Pass 1 alle Dateien
        vorab eingelesen, um das globale Footnote-Lexikon zu füllen.
        Mit der Abschaltung der Fußnoten-Verarbeitung ist diese Methode
        ein No-op. Sie bleibt als stabile API für externe Importer
        erhalten.
        """
        return

    def prepare_render_environment(self, tree_data):
        if self.processed_dir.exists():
            shutil.rmtree(self.processed_dir)
        self.processed_dir.mkdir(parents=True)

        # --- DER MAGISCHE PANDOC FIX ---
        index_path = self.book_path / "index.md"
        if index_path.exists():
            with open(index_path, 'r', encoding='utf-8') as f:
                idx_content = f.read()
            if not idx_content.endswith('\n\n'):
                with open(index_path, 'a', encoding='utf-8') as f:
                    f.write('\n\n')
        # -------------------------------

        # === PASS 1: jetzt No-op (B4 — Footnote-Harvesting entfernt) ===
        self._gather_all_definitions(tree_data)

        # === PASS 2: DATEIEN SCHREIBEN UND VERWEISE SETZEN ===
        processed_tree = []

        for root_node in tree_data:
            if root_node.get("children"):
                self._process_part_file(root_node)

                new_part = {
                    "title": root_node["title"],
                    "path": f"processed/{root_node['path']}",
                    "children": []
                }

                for chapter_node in root_node["children"]:
                    chapter_dest = self._process_host_file(chapter_node)

                    new_chapter = {
                        "title": chapter_node["title"],
                        "path": f"processed/{chapter_node['path']}",
                        "children": []
                    }
                    new_part["children"].append(new_chapter)

                    if chapter_node.get("children"):
                        self._amalgamate_children(chapter_node["children"], chapter_dest, offset=1)

                processed_tree.append(new_part)
            else:
                self._process_host_file(root_node)

                new_chapter = {
                    "title": root_node["title"],
                    "path": f"processed/{root_node['path']}",
                    "children": []
                }
                processed_tree.append(new_chapter)

        # B4: Endnoten-Generierung entfernt.

        return processed_tree

    def _process_part_file(self, node):
        src = self.book_path / node["path"]
        dest = self.processed_dir / node["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not src.exists():
            return dest

        with open(src, 'r', encoding='utf-8') as f:
            content = f.read()

        frontmatter, body = self._extract_parts(content)
        frontmatter = self._sanitize_frontmatter_for_render(frontmatter)

        # 1. Text waschen (Box-Reparatur, @-Zitation → [^Key])
        body = self._sanitize_markdown(body)

        # 2. H1 bereinigen
        body = re.sub(r'^(#\s+.*)$', r'', body, count=1, flags=re.MULTILINE)

        # B4: Footnote-Harvesting-Block entfernt (war 3+5).

        with open(dest, 'w', encoding='utf-8') as f:
            f.write(frontmatter + body.rstrip() + "\n\n")

        # Companion-SVGs in processed/ kopieren
        self._copy_companion_svgs(src, dest)

        return dest

    def _process_host_file(self, node):
        src = self.book_path / node["path"]
        dest = self.processed_dir / node["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not src.exists():
            return dest

        with open(src, 'r', encoding='utf-8') as f:
            content = f.read()

        frontmatter, body = self._extract_parts(content)
        frontmatter = self._sanitize_frontmatter_for_render(frontmatter)

        # 1. Text waschen (Box-Reparatur, @-Zitation → [^Key])
        body = self._sanitize_markdown(body)

        # 2. H1 bereinigen
        body = re.sub(r'^(#\s+.*)$', r'', body, count=1, flags=re.MULTILINE)

        # B4: Footnote-Harvesting-Block entfernt (war 3+5).

        with open(dest, 'w', encoding='utf-8') as f:
            f.write(frontmatter + body.rstrip() + "\n\n")

        # Companion-SVGs in processed/ kopieren
        self._copy_companion_svgs(src, dest)

        return dest

    def _copy_companion_svgs(self, src: Path, dest: Path) -> None:
        """Kopiere ``svg_*.svg``-Dateien aus dem Quell-Verzeichnis
        neben die verarbeitete .md-Datei in ``processed/``."""
        src_dir = src.parent
        dst_dir = dest.parent
        if src_dir == dst_dir:
            return
        for svg in src_dir.glob("svg_*.svg"):
            dst_file = dst_dir / svg.name
            if not dst_file.exists():
                try:
                    shutil.copy2(svg, dst_file)
                except Exception:
                    pass

    def _amalgamate_children(self, children, host_dest, offset):
        for child in children:
            src = self.book_path / child["path"]
            if src.exists():
                with open(src, 'r', encoding='utf-8') as f:
                    content = f.read()

                _, body = self._extract_parts(content)

                # 1. Text waschen (Box-Reparatur, @-Zitation → [^Key])
                body = self._sanitize_markdown(body)

                # B4: Footnote-Harvesting-Block entfernt (war 2).

                # 2. Überschriften einrücken
                def shift_heading(m):
                    return f"{'#' * (len(m.group(1)) + offset)}{m.group(2)}"

                body = re.sub(r'^(#+)(\s+.*)$', shift_heading, body, flags=re.MULTILINE)

                with open(host_dest, 'a', encoding='utf-8') as f:
                    f.write(f"\n\n\n{body.strip()}\n\n")

            if child.get("children"):
                self._amalgamate_children(child["children"], host_dest, offset + 1)