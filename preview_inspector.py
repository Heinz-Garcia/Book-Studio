import tkinter as tk
from tkinter import ttk
from ui_theme import COLORS, FONTS, center_on_parent, style_code_text, style_dialog

class PreviewInspector(tk.Toplevel):
    def __init__(self, parent, tree_data, yaml_engine):
        super().__init__(parent)
        self.title("🔍 Struktur-Preview & Offset-Matrix")
        center_on_parent(self, parent, 900, 700)
        
        # Modal machen (blockiert Hauptfenster, bis es geschlossen wird)
        self.transient(parent)
        self.grab_set()
        
        self.tree_data = tree_data
        self.yaml_engine = yaml_engine
        
        self.setup_ui()
        self.generate_report()
        
    def setup_ui(self):
        style_dialog(self)
        # Header
        header = tk.Frame(self, bg=COLORS["panel_dark"], pady=10)
        header.pack(fill=tk.X)
        tk.Label(header, text="ARCHITEKTUR-INSPEKTOR (NUR LESEN)", fg="white", bg=COLORS["panel_dark"], font=FONTS["title_large"]).pack()
        
        # Textfeld für den Report
        self.txt = tk.Text(self, wrap="word")
        style_code_text(self.txt)
        self.txt.pack(fill=tk.BOTH, expand=True)
        
        # Footer
        footer = ttk.Frame(self, padding=(0, 10))
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Button(footer, text="Schließen", style="Tool.TButton", command=self.destroy).pack()
        
    def generate_report(self):
        report = []
        
        # TEIL 1: YAML OUTPUT
        report.append("="*70)
        report.append("1. QUARTO YAML OUTPUT (Die flache Liste für _quarto.yml)")
        report.append("="*70)
        report.append("So wird der 'chapters:' Block nach dem Flachklopfen aussehen:\n")
        
        yaml_str = self.yaml_engine.generate_yaml_string(self.tree_data, base_indent="  ")
        report.append(yaml_str if yaml_str else "  [Leer - Baum enthält keine Struktur]")
        
        # TEIL 2: OFFSET MATRIX
        report.append("\n\n" + "="*70)
        report.append("2. OFFSET-MATRIX (Der Amalgamierungs-Plan für den Export)")
        report.append("="*70)
        report.append("So müssen die Markdown-Dateien physisch im 'export'-Ordner angepasst")
        report.append("werden, damit Quarto die Hierarchien im Inhaltsverzeichnis korrekt baut.\n")
        
        self._build_offset_matrix(self.tree_data, current_level=0, report=report)
        
        self.txt.insert(tk.END, "\n".join(report))
        self.txt.config(state="disabled") # Read-only, damit man nicht versehentlich tippt
        
    def _build_offset_matrix(self, data, current_level, report):
        for item in data:
            title = item["title"]
            path = item["path"]
            children = item.get("children", [])
            
            # Visuelle Einrückung für den Report
            indent_str = "    " * current_level
            
            # Wie viele Rauten müssen VOR die bestehenden Rauten in der Datei?
            offset_str = f"+{current_level}"
            
            # Beispiel, was mit einer H1 (#) passieren wird:
            h1_transformation = "#" + ("#" * current_level)
            
            report.append(f"{indent_str}📄 {title}")
            report.append(f"{indent_str}   Pfad  : {path}")
            report.append(f"{indent_str}   Ebene : {current_level} (Offset {offset_str})")
            report.append(f"{indent_str}   Aktion: Aus jedem '#' in der Datei muss ein '{h1_transformation}' werden.\n")
            
            if children:
                self._build_offset_matrix(children, current_level + 1, report)