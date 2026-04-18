from pathlib import Path

class TemplateManager:
    @staticmethod
    def discover_templates(book_path):
        """Scannt nach lokalen Dateien im 'templates' Ordner UND nach Quarto-Extensions."""
        if not book_path:
            return ["Standard"]
            
        book_path = Path(book_path)
        templates = ["Standard"]
        
        # 1. Lokale Dateien (.typ, .tex)
        tpl_dir = book_path / "templates"
        if tpl_dir.exists():
            found = [f.name for f in tpl_dir.glob("*.*") if f.suffix in [".typ", ".tex"]]
            templates.extend(sorted(found))
            
        # 2. Quarto Extensions scannen
        ext_dir = book_path / "_extensions"
        if ext_dir.exists():
            for ext_file in ext_dir.rglob("_extension.yml"):
                # Der Name der Extension ist immer der Name des Ordners!
                ext_name = ext_file.parent.name
                templates.append(f"EXT: {ext_name}")
                
        return templates