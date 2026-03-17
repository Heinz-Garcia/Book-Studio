import re
import shutil
from pathlib import Path
import hashlib
import yaml
from footnote_harvester import FootnoteHarvester

class PreProcessor:
    def __init__(self, book_path, footnote_mode="endnotes", enable_footnote_backlinks=True, output_format="typst"):
        self.book_path = Path(book_path)
        self.processed_dir = self.book_path / "processed"
        self.footnote_mode = footnote_mode
        self.enable_footnote_backlinks = bool(enable_footnote_backlinks)
        self.output_format = str(output_format) if output_format else "typst"
        _use_typst_links = (
            footnote_mode == "endnotes"
            and "typst" in self.output_format.lower()
        )
        self.harvester = FootnoteHarvester(
            mode=footnote_mode,
            title="Anmerkungen",
            use_typst_links=_use_typst_links,
        )

    def _uses_harvester(self):
        return self.footnote_mode in {"endnotes", "pandoc"}

    def _namespace_local_footnotes(self, text, source_path):
        if self.footnote_mode != "footnotes":
            return text

        path_text = str(source_path).replace("\\", "/")
        prefix = re.sub(r"[^A-Za-z0-9_]+", "_", Path(path_text).stem).strip("_") or "note"
        digest = hashlib.sha1(path_text.encode("utf-8")).hexdigest()[:8]
        namespace = f"{prefix}_{digest}"

        def replace_definition(match):
            label = match.group(1)
            return f"[^{namespace}_{label}]:"

        def replace_marker(match):
            label = match.group(1)
            return f"[^{namespace}_{label}]"

        text = re.sub(r'\[\^([^\]]+)\]:', replace_definition, text)
        text = re.sub(r'\[\^([^\]]+)\](?!:)', replace_marker, text)
        return text

    def _footnote_anchor_id(self, label, index):
        safe_label = re.sub(r"[^A-Za-z0-9_-]+", "-", str(label)).strip("-") or "note"
        return f"fnref-{safe_label}-{index}"

    def _inject_footnote_backlinks(self, text):
        if self.footnote_mode != "footnotes" or not self.enable_footnote_backlinks:
            return text

        ref_counts = {}
        ref_targets = {}

        def replace_marker(match):
            label = match.group(1)
            next_index = ref_counts.get(label, 0) + 1
            ref_counts[label] = next_index
            anchor_id = self._footnote_anchor_id(label, next_index)
            ref_targets.setdefault(label, []).append(anchor_id)
            return f"[]{{#{anchor_id}}}[^{label}]"

        text = re.sub(r'\[\^([^\]]+)\](?!:)', replace_marker, text)

        definition_pattern = re.compile(
            r'^\[\^([^\]]+)\]:\s*(.*?)(?=^\[\^[^\]]+\]:|\Z)',
            re.DOTALL | re.MULTILINE,
        )

        def replace_definition(match):
            label = match.group(1)
            body = match.group(2).rstrip()
            targets = ref_targets.get(label, [])
            if not targets:
                return match.group(0)
            if len(targets) == 1:
                backlink_text = f" [↩](#{targets[0]})"
            else:
                backlink_parts = [f"[↩{i + 1}](#{target})" for i, target in enumerate(targets)]
                backlink_text = " " + " ".join(backlink_parts)
            return f"[^{label}]: {body}{backlink_text}\n"

        text = definition_pattern.sub(replace_definition, text)
        return text

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
        """Entfernt ungenutzte Fußnoten-Definitionen im footnotes-Modus aus dem processed-Text."""
        if self.footnote_mode != "footnotes":
            return text

        definition_pattern = re.compile(
            r'^\[\^([^\]]+)\]:\s*(.*?)(?=^\[\^[^\]]+\]:|\Z)',
            re.DOTALL | re.MULTILINE,
        )
        matches = list(definition_pattern.finditer(text))
        if not matches:
            return text

        used_labels = set(re.findall(r'\[\^([^\]]+)\](?!:)', text))

        parts = []
        cursor = 0
        for match in matches:
            start, end = match.span()
            parts.append(text[cursor:start])
            label = match.group(1)
            if label in used_labels:
                parts.append(match.group(0))
            cursor = end
        parts.append(text[cursor:])

        return ''.join(parts).strip()

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
        """
        PASS 1: Liest alle Dateien heimlich vorab ein, bereinigt sie (Waschgang) 
        und füllt das globale Lexikon im FootnoteHarvester.
        """
        if not self._uses_harvester():
            return
        for node in nodes:
            if not node["path"].startswith("PART:"):
                path = self.book_path / node["path"]
                if path.exists() and path.is_file():
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    _, body = self._extract_parts(content)
                    body = self._sanitize_markdown(body)
                    body = self._namespace_local_footnotes(body, path)
                    
                    # Füllt das Lexikon (datei-scoped), ohne den Text schon zu verändern
                    self.harvester.extract_definitions(body, file_key=str(path))
                    
            if node.get("children"):
                self._gather_all_definitions(node["children"])

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

        # === PASS 1: ALLE QUELLEN SAMMELN (Globales Lexikon füllen) ===
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

        # Ganz am Ende die gesammelten Endnoten generieren
        if self._uses_harvester() and self.harvester.harvested:
            endnotes_filename = "Endnoten.md"
            endnotes_dest = self.processed_dir / endnotes_filename
            self.harvester.generate_endnotes_file(endnotes_dest)
            
            processed_tree.append({
                "title": self.harvester.title,
                "path": f"processed/{endnotes_filename}",
                "children": []
            })

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
        
        # 1. Text waschen
        body = self._sanitize_markdown(body)
        body = self._namespace_local_footnotes(body, src)
        body = self._inject_footnote_backlinks(body)
        
        # 2. H1 bereinigen
        body = re.sub(r'^(#\s+.*)$', r'', body, count=1, flags=re.MULTILINE)
        
        # 3. Lexikon anwenden (Definitionen entfernen, Marker ersetzen) — datei-scoped
        if self._uses_harvester():
            body = self.harvester.extract_definitions(body, file_key=str(src))
            body = self.harvester.replace_markers(body, file_key=str(src))
        else:
            body = self._prune_unused_footnote_definitions(body)
        
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(frontmatter + body.rstrip() + "\n\n")
            
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
        
        # 1. Text waschen
        body = self._sanitize_markdown(body)
        body = self._namespace_local_footnotes(body, src)
        body = self._inject_footnote_backlinks(body)
        
        # 2. H1 bereinigen
        body = re.sub(r'^(#\s+.*)$', r'', body, count=1, flags=re.MULTILINE)
        
        # 3. Lexikon anwenden — datei-scoped
        if self._uses_harvester():
            body = self.harvester.extract_definitions(body, file_key=str(src))
            body = self.harvester.replace_markers(body, file_key=str(src))
        else:
            body = self._prune_unused_footnote_definitions(body)
        
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(frontmatter + body.rstrip() + "\n\n")
            
        return dest

    def _amalgamate_children(self, children, host_dest, offset):
        for child in children:
            src = self.book_path / child["path"]
            if src.exists():
                with open(src, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                _, body = self._extract_parts(content)
                
                # 1. Text waschen
                body = self._sanitize_markdown(body)
                body = self._namespace_local_footnotes(body, src)
                body = self._inject_footnote_backlinks(body)
                
                # 2. Lexikon anwenden — datei-scoped
                if self._uses_harvester():
                    body = self.harvester.extract_definitions(body, file_key=str(src))
                    body = self.harvester.replace_markers(body, file_key=str(src))
                else:
                    body = self._prune_unused_footnote_definitions(body)
                
                # 3. Überschriften einrücken
                def shift_heading(m):
                    return f"{'#' * (len(m.group(1)) + offset)}{m.group(2)}"
                
                body = re.sub(r'^(#+)(\s+.*)$', shift_heading, body, flags=re.MULTILINE)
                
                with open(host_dest, 'a', encoding='utf-8') as f:
                    f.write(f"\n\n\n{body.strip()}\n\n")
            
            if child.get("children"):
                self._amalgamate_children(child["children"], host_dest, offset + 1)