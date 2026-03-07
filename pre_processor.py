import re
import shutil
from pathlib import Path
from footnote_harvester import FootnoteHarvester

# =============================================================================
# DER MASCHINENRAUM - PHYSISCHE AMALGAMIERUNG & FOOTNOTE HARVESTING
# =============================================================================

class PreProcessor:
    # NEU: Wir erlauben der GUI, den Modus als Parameter (footnote_mode) zu übergeben
    def __init__(self, book_path, footnote_mode="endnotes"):
        self.book_path = Path(book_path)
        self.processed_dir = self.book_path / "processed"
        
        # Der Harvester nutzt jetzt den Modus, den die GUI ihm diktiert!
        self.harvester = FootnoteHarvester(mode=footnote_mode, title="Anmerkungen")

    def prepare_render_environment(self, tree_data):
        if self.processed_dir.exists():
            shutil.rmtree(self.processed_dir)
        self.processed_dir.mkdir(parents=True)

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

        # --- NEU: ENDNOTEN-KAPITEL AM ENDE ANFÜGEN ---
        if self.harvester.harvested:
            endnotes_filename = "Endnoten.md"
            endnotes_dest = self.processed_dir / endnotes_filename
            self.harvester.generate_endnotes_file(endnotes_dest)
            
            # Quarto mitteilen, dass es ein brandneues Kapitel ganz am Ende gibt!
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
            
        match = re.search(r'^---\s*\n.*?\n---\s*\n', content, re.DOTALL)
        frontmatter = match.group(0) if match else ""
        body = content[match.end():] if match else content
        
        body = re.sub(r'^(#\s+.*)$', r'', body, count=1, flags=re.MULTILINE)
        body = self.harvester.process_text(body) # <-- HARVESTER
        
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(frontmatter + body)
        return dest

    def _process_host_file(self, node):
        src = self.book_path / node["path"]
        dest = self.processed_dir / node["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not src.exists(): return dest
        
        with open(src, 'r', encoding='utf-8') as f:
            content = f.read()
            
        match = re.search(r'^---\s*\n.*?\n---\s*\n', content, re.DOTALL)
        frontmatter = match.group(0) if match else ""
        body = content[match.end():] if match else content
        
        body = re.sub(r'^(#\s+.*)$', r'', body, count=1, flags=re.MULTILINE)
        body = self.harvester.process_text(body) # <-- HARVESTER
        
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(frontmatter + body)
        return dest

    def _amalgamate_children(self, children, host_dest, offset):
        for child in children:
            src = self.book_path / child["path"]
            if src.exists():
                with open(src, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                match = re.search(r'^---\s*\n.*?\n---\s*\n', content, re.DOTALL)
                body = content[match.end():] if match else content
                
                body = self.harvester.process_text(body) # <-- HARVESTER
                
                def shift_heading(m):
                    hashes = m.group(1)
                    text = m.group(2)
                    new_hashes = '#' * (len(hashes) + offset)
                    return f"{new_hashes}{text}"
                
                body = re.sub(r'^(#+)(\s+.*)$', shift_heading, body, flags=re.MULTILINE)
                
                with open(host_dest, 'a', encoding='utf-8') as f:
                    f.write(f"\n\n\n")
                    f.write(body.strip() + "\n")
            
            if child.get("children"):
                self._amalgamate_children(child["children"], host_dest, offset + 1)