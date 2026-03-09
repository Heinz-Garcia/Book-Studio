import re
from pathlib import Path

class FootnoteHarvester:
    def __init__(self, mode="endnotes", title="Anmerkungen"):
        """
        mode="endnotes": Ersetzt Fußnoten durch hochgestellte Zahlen (^[1]^) und baut ein festes Endnoten-Kapitel.
        mode="pandoc": Sammelt die Noten, belässt aber die Quarto-Syntax [^1] für klassische Fußnoten.
        """
        self.mode = mode
        self.title = title
        
        self.global_counter = 1
        self.harvested = [] # Speichert Tuples: (neue_id, text) für das finale Endnoten-Kapitel
        
        # --- NEU: Das 2-Pass-System (Globale Lexika) ---
        self.definitions = {} # Unser globales Lexikon: Speichert ALLE Quellen aus allen Dateien
        self.file_mapping = {} # Merkt sich, welche Quelle welche fortlaufende Nummer bekommen hat
        # -----------------------------------------------

    def extract_definitions(self, text):
        """PASS 1: Findet alle Fußnoten-Definitionen (egal wo sie stehen), speichert sie und entfernt sie aus dem Text."""
        
        # NEU: Wir suchen nach [^Label]: gefolgt von beliebigem Text bis zum nächsten [^Label]: oder Dateiende
        # Das (?=...) ist ein Lookahead. Wir suchen also bis vor die nächste Definition.
        pattern = re.compile(r'\[\^([^\]]+)\]:\s*(.*?)(?=\[\^[^\]]+\]:|$)', re.DOTALL)
        
        # 1. Alle Treffer ins Lexikon aufnehmen
        for match in pattern.finditer(text):
            note_id = match.group(1)
            note_content = match.group(2).strip()
            self.definitions[note_id] = note_content
            
        # 2. Die gefundenen Definitionen komplett aus dem Fließtext löschen
        clean_text = pattern.sub('', text)
        
        return clean_text.strip()

    def replace_markers(self, text):
        """PASS 2: Nutzt das globale Lexikon, um alle Verweise durch saubere Zahlen zu ersetzen."""
        def inline_repl(m):
            old_id = m.group(1)
            
            # Prüfen, ob wir die Quelle im weltweiten Lexikon gefunden haben
            if old_id in self.definitions:
                
                # Wenn diese Quelle noch keine Nummer hat, bekommt sie jetzt die nächste
                if old_id not in self.file_mapping:
                    self.file_mapping[old_id] = self.global_counter
                    self.harvested.append((self.global_counter, self.definitions[old_id]))
                    self.global_counter += 1
                
                new_id = self.file_mapping[old_id]
                
                # Konfigurierbares Ausgabeformat anwenden
                if self.mode == "endnotes":
                    return f"^[{new_id}]^" 
                else:
                    return f"[^{new_id}]"
                    
            # Falls die Quelle nicht existiert, belassen wir den Marker unberührt
            return m.group(0)

        # Sucht nach [^1] im Text und jagt es durch unsere Ersetzungs-Funktion
        clean_text = re.sub(r'\[\^([^\]]+)\]', inline_repl, text)
        return clean_text.strip()

    def generate_endnotes_file(self, export_path):
        """Generiert die fertige Endnoten.md Datei am Ende des Buchs."""
        if not self.harvested:
            return False
            
        with open(export_path, 'w', encoding='utf-8') as f:
            # YAML Frontmatter für das Kapitel
            f.write(f"---\ntitle: \"{self.title}\"\n---\n\n")
            
            for note_id, text in self.harvested:
                if self.mode == "endnotes":
                    f.write(f"**[{note_id}]** {text}\n\n")
                else:
                    f.write(f"[^{note_id}]: {text}\n\n")
                    
        return True