import re

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
        
        # --- Das 2-Pass-System (Globale Lexika) ---
        self.definitions = {} # Globales Lexikon: (file_key, label) -> Inhalt
        self.file_mapping = {} # (file_key, label) -> fortlaufende Nummer
        self.orphan_warnings = [] # Verwaiste Marker ohne Definition: (file_key, label)
        # -------------------------------------------

    def extract_definitions(self, text, file_key=""):
        """PASS 1: Findet alle Fußnoten-Definitionen, speichert sie datei-scoped und entfernt sie aus dem Text.
        
        file_key: eindeutiger Bezeichner der Quelldatei (z.B. Pfad als String).
        So können [^1] in Datei A und [^1] in Datei B als verschiedene Fußnoten behandelt werden.
        """
        # Definitionen müssen am Zeilenanfang stehen ([^Label]:).
        # \Z statt $ verhindert, dass die letzte Definition Body-Text nach sich "auffrißt".
        pattern = re.compile(r'^\[\^([^\]]+)\]:\s*(.*?)(?=^\[\^[^\]]+\]:|\Z)', re.DOTALL | re.MULTILINE)
        
        # 1. Alle Treffer ins Lexikon aufnehmen — Key ist (file_key, label)
        for match in pattern.finditer(text):
            note_id = match.group(1)
            note_content = match.group(2).strip()
            self.definitions[(file_key, note_id)] = note_content
            
        # 2. Die gefundenen Definitionen komplett aus dem Fließtext löschen
        clean_text = pattern.sub('', text)
        
        return clean_text.strip()

    def replace_markers(self, text, file_key=""):
        """PASS 2: Nutzt das globale Lexikon, um alle Verweise durch saubere fortlaufende Zahlen zu ersetzen.
        
        file_key: muss derselbe Wert sein wie beim zugehörigen extract_definitions-Aufruf,
        damit Marker korrekt ihrer datei-scoped Definition zugeordnet werden.
        """
        def inline_repl(m):
            old_id = m.group(1)
            scoped_key = (file_key, old_id)
            
            # Prüfen, ob wir die Quelle im datei-scoped Lexikon gefunden haben
            if scoped_key in self.definitions:
                
                # Wenn diese Quelle noch keine globale Nummer hat, bekommt sie jetzt die nächste
                if scoped_key not in self.file_mapping:
                    self.file_mapping[scoped_key] = self.global_counter
                    self.harvested.append((self.global_counter, self.definitions[scoped_key]))
                    self.global_counter += 1
                
                new_id = self.file_mapping[scoped_key]
                
                # Konfigurierbares Ausgabeformat anwenden
                if self.mode == "endnotes":
                    return f"^[{new_id}]^" 
                else:
                    return f"[^{new_id}]"
                    
            # Falls die Quelle nicht im Lexikon existiert, Marker unberührt lassen
            # Marker ohne Definition: als verwaist merken und unberührt lassen
            if (file_key, old_id) not in self.orphan_warnings:
                self.orphan_warnings.append((file_key, old_id))
            return m.group(0)

        # Sucht nach [^Label] im Text und jagt es durch die Ersetzungs-Funktion
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