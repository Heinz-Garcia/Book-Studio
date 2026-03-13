import re
import shutil
from pathlib import Path
from footnote_harvester import FootnoteHarvester

class PreProcessor:
    def __init__(self, book_path, footnote_mode="endnotes"):
        self.book_path = Path(book_path)
        self.processed_dir = self.book_path / "processed"
        self.harvester = FootnoteHarvester(mode=footnote_mode, title="Anmerkungen")

    def _extract_parts(self, content):
        """Trennt Frontmatter extrem robust vom Text ab, selbst bei Windows-BOMs."""
        match = re.match(r'^\uFEFF?---\s*[\r\n]+(.*?)[\r\n]+---\s*[\r\n]*', content, re.DOTALL)
        if match:
            return match.group(0), content[match.end():]
        return "", content

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
        
        # 2. @-ZITATIONEN IN FUSSNOTEN UMWANDELN (Absolut robust!)
        # Schritt A: Definitionen (egal ob Zeilenanfang oder Leerzeichen davor)
        # Wir zwingen ein \n davor, damit sie für den Harvester immer sauber auf einer neuen Zeile stehen!
        text = re.sub(r'(^|\s)@([a-zA-Z0-9_-]+):', r'\1\n[^\2]:', text)
        
        # Schritt B: Verweise im Text (mit Leerzeichen, Klammern oder am Zeilenanfang)
        text = re.sub(r'(^|\s|\(|\[)@([a-zA-Z0-9_-]+)', r'\1[^\2]', text)
        
        return text
    # =========================================================================

    def _gather_all_definitions(self, nodes):
        """
        PASS 1: Liest alle Dateien heimlich vorab ein, bereinigt sie (Waschgang) 
        und füllt das globale Lexikon im FootnoteHarvester.
        """
        for node in nodes:
            if not node["path"].startswith("PART:"):
                path = self.book_path / node["path"]
                if path.exists() and path.is_file():
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    _, body = self._extract_parts(content)
                    body = self._sanitize_markdown(body)
                    
                    # Füllt das Lexikon, ohne den Text schon zu verändern
                    self.harvester.extract_definitions(body)
                    
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
        if self.harvester.harvested:
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
        
        # 1. Text waschen
        body = self._sanitize_markdown(body)
        
        # 2. H1 bereinigen
        body = re.sub(r'^(#\s+.*)$', r'', body, count=1, flags=re.MULTILINE)
        
        # 3. Lexikon anwenden (Zuerst alte Definitionen unten abschneiden, dann Marker im Text ersetzen)
        body = self.harvester.extract_definitions(body)
        body = self.harvester.replace_markers(body)
        
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
        
        # 1. Text waschen
        body = self._sanitize_markdown(body)
        
        # 2. H1 bereinigen
        body = re.sub(r'^(#\s+.*)$', r'', body, count=1, flags=re.MULTILINE)
        
        # 3. Lexikon anwenden
        body = self.harvester.extract_definitions(body)
        body = self.harvester.replace_markers(body)
        
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
                
                # 2. Lexikon anwenden
                body = self.harvester.extract_definitions(body)
                body = self.harvester.replace_markers(body)
                
                # 3. Überschriften einrücken
                def shift_heading(m):
                    return f"{'#' * (len(m.group(1)) + offset)}{m.group(2)}"
                
                body = re.sub(r'^(#+)(\s+.*)$', shift_heading, body, flags=re.MULTILINE)
                
                with open(host_dest, 'a', encoding='utf-8') as f:
                    f.write(f"\n\n\n{body.strip()}\n\n")
            
            if child.get("children"):
                self._amalgamate_children(child["children"], host_dest, offset + 1)