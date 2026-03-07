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
        self.harvested = [] # Speichert Tuples: (neue_id, text)

    def process_text(self, text):
        """Findet Fußnoten, entfernt sie aus dem Text und nummeriert die Marker global um."""
        definitions = {}
        
        # 1. Alle Fußnoten-Definitionen am Ende des Textes finden und herausschneiden
        # Sucht nach dem Muster [^irgendwas]: ... 
        parts = re.split(r'^\[\^([^\]]+)\]:\s*', text, flags=re.MULTILINE)
        clean_text = parts[0] # Der eigentliche Fließtext ohne die Definitionen am Ende
        
        for i in range(1, len(parts), 2):
            note_id = parts[i]
            note_content = parts[i+1].strip()
            definitions[note_id] = note_content

        # 2. Ersetzen der Inline-Marker im Fließtext
        file_mapping = {}
        def inline_repl(m):
            old_id = m.group(1)
            # Nur ersetzen, wenn wir die Definition unten auch gefunden haben
            if old_id in definitions:
                # Wurde diese Fußnote in DIESER Datei schon umnummeriert?
                if old_id not in file_mapping:
                    file_mapping[old_id] = self.global_counter
                    self.harvested.append((self.global_counter, definitions[old_id]))
                    self.global_counter += 1
                
                new_id = file_mapping[old_id]
                
                # Konfigurierbares Ausgabeformat anwenden
                if self.mode == "endnotes":
                    # Pandoc Superscript Syntax: ^[1]^ (Wird in Word/PDF hochgestellt gerendert)
                    return f"^[{new_id}]^" 
                else:
                    # Klassische Pandoc Syntax (als Fußnote auf der Seite)
                    return f"[^{new_id}]"
            return m.group(0)

        # Sucht nach [^1] im Text und jagt es durch unsere Ersetzungs-Funktion
        clean_text = re.sub(r'\[\^([^\]]+)\]', inline_repl, clean_text)
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
                    # Ein reiner, harter Texteintrag für den Verlag
                    f.write(f"**[{note_id}]** {text}\n\n")
                else:
                    # Pandoc Syntax
                    f.write(f"[^{note_id}]: {text}\n\n")
        return True