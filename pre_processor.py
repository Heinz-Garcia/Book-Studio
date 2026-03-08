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

    def prepare_render_environment(self, tree_data):
        if self.processed_dir.exists():
            shutil.rmtree(self.processed_dir)
        self.processed_dir.mkdir(parents=True)

        # --- DER MAGISCHE PANDOC FIX ---
        # Wir stellen sicher, dass index.md ZWINGEND mit Leerzeilen endet.
        # Fehlen diese, klebt Quarto die Dateien zusammen, zerreißt den YAML-Block
        # des nächsten Kapitels und lässt Pandoc bei Markdown-Zitaten (>) abstürzen!
        index_path = self.book_path / "index.md"
        if index_path.exists():
            with open(index_path, 'r', encoding='utf-8') as f:
                idx_content = f.read()
            if not idx_content.endswith('\n\n'):
                with open(index_path, 'a', encoding='utf-8') as f:
                    f.write('\n\n')
        # -------------------------------

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
        if not src.exists(): return dest
        
        with open(src, 'r', encoding='utf-8') as f:
            content = f.read()
            
        frontmatter, body = self._extract_parts(content)
        
        body = re.sub(r'^(#\s+.*)$', r'', body, count=1, flags=re.MULTILINE)
        body = self.harvester.process_text(body)
        
        with open(dest, 'w', encoding='utf-8') as f:
            # FIX: Jede Datei MUSS mit einem sauberen Cut (Leerzeilen) enden!
            f.write(frontmatter + body.rstrip() + "\n\n")
        return dest

    def _process_host_file(self, node):
        src = self.book_path / node["path"]
        dest = self.processed_dir / node["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not src.exists(): return dest
        
        with open(src, 'r', encoding='utf-8') as f:
            content = f.read()
            
        frontmatter, body = self._extract_parts(content)
        
        body = re.sub(r'^(#\s+.*)$', r'', body, count=1, flags=re.MULTILINE)
        body = self.harvester.process_text(body)
        
        with open(dest, 'w', encoding='utf-8') as f:
            # FIX: Jede Datei MUSS mit einem sauberen Cut (Leerzeilen) enden!
            f.write(frontmatter + body.rstrip() + "\n\n")
        return dest

    def _amalgamate_children(self, children, host_dest, offset):
        for child in children:
            src = self.book_path / child["path"]
            if src.exists():
                with open(src, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                _, body = self._extract_parts(content)
                body = self.harvester.process_text(body)
                
                def shift_heading(m):
                    return f"{'#' * (len(m.group(1)) + offset)}{m.group(2)}"
                
                body = re.sub(r'^(#+)(\s+.*)$', shift_heading, body, flags=re.MULTILINE)
                
                with open(host_dest, 'a', encoding='utf-8') as f:
                    # FIX: Auch zusammengeführte Kapitel brauchen harte Umbrüche
                    f.write(f"\n\n\n{body.strip()}\n\n")
            
            if child.get("children"):
                self._amalgamate_children(child["children"], host_dest, offset + 1)
                