from pathlib import Path

class TemplateManager:
    @staticmethod
    def discover_templates(book_path):
        """Scannt den 'templates' Ordner nach .typ (Typst) und .tex (LaTeX) Dateien."""
        if not book_path:
            return ["Standard"]
            
        tpl_dir = Path(book_path) / "templates"
        if not tpl_dir.exists():
            return ["Standard"]
            
        # Wir suchen nach Typst-Vorlagen (.typ) und LaTeX-Vorlagen (.tex)
        found = [f.name for f in tpl_dir.glob("*.*") if f.suffix in [".typ", ".tex"]]
        return ["Standard"] + sorted(found)
    