import re

class FootnoteHarvester:
    def __init__(self, mode="endnotes", title="Anmerkungen", use_typst_links=False):
        """
        mode="endnotes": Ersetzt Fußnoten durch hochgestellte Zahlen und baut ein Endnoten-Kapitel.
          use_typst_links=True: erzeugt Typst-native #link/<#label>-Anker (klickbare PDF-Links).
        mode="pandoc": Sammelt die Noten, belässt aber die Quarto-Syntax [^1] für klassische Fußnoten.
        mode="footnotes" wird nicht hier verarbeitet; in diesem Modus lässt der PreProcessor den Fußnoten-Text unverändert.
        """
        self.mode = mode
        self.title = title
        self.use_typst_links = use_typst_links

        self.global_counter = 1
        self.harvested = [] # Speichert Tuples: (neue_id, text) für das finale Endnoten-Kapitel

        # --- Das 2-Pass-System (Globale Lexika) ---
        self.definitions = {} # Globales Lexikon: (file_key, label) -> Inhalt
        self.file_mapping = {} # (file_key, label) -> fortlaufende Nummer
        self.orphan_warnings = [] # Verwaiste Marker ohne Definition: (file_key, label)
        self._ref_anchors = {} # new_id -> [back-link-anchor, ...] für Typst-Rücksprünge
        # -------------------------------------------

    def _parse_definition_start(self, line):
        """Erkennt den Start einer Fußnoten-Definition mit optional leichter Einrückung."""
        return re.match(r'^\s{0,3}\[\^([^\]]+)\]:\s?(.*)$', line)

    def extract_definitions(self, text, file_key=""):
        """PASS 1: Findet alle Fußnoten-Definitionen, speichert sie datei-scoped und entfernt sie aus dem Text.
        
        file_key: eindeutiger Bezeichner der Quelldatei (z.B. Pfad als String).
        So können [^1] in Datei A und [^1] in Datei B als verschiedene Fußnoten behandelt werden.
        """
        lines = text.splitlines(keepends=True)
        clean_parts = []
        active_label = None
        active_content_parts = []

        def flush_active_definition():
            nonlocal active_label, active_content_parts
            if active_label is None:
                return
            note_content = "".join(active_content_parts).strip()
            self.definitions[(file_key, active_label)] = note_content
            active_label = None
            active_content_parts = []

        for line in lines:
            start_match = self._parse_definition_start(line)
            if start_match:
                flush_active_definition()
                active_label = start_match.group(1)
                first_content = start_match.group(2)
                active_content_parts.append(first_content)
                if line.endswith("\n"):
                    active_content_parts.append("\n")
                continue

            if active_label is not None:
                # Pandoc-kompatibel: Fortsetzungszeilen sind eingerückt oder leer.
                if line.strip() == "" or line.startswith((" ", "\t")):
                    active_content_parts.append(line)
                    continue

                flush_active_definition()

            clean_parts.append(line)

        flush_active_definition()
        clean_text = "".join(clean_parts)
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
                    if self.use_typst_links:
                        ref_count = len(self._ref_anchors.get(new_id, [])) + 1
                        ref_anchor = f"fnref-{new_id}-{ref_count}"
                        self._ref_anchors.setdefault(new_id, []).append(ref_anchor)
                        return (
                            f"`#label(\"{ref_anchor}\")`{{=typst}}"
                            f"`#super[#link(<fn-{new_id}>)[{new_id}]]`{{=typst}}"
                        )
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
                    if self.use_typst_links:
                        anchors = self._ref_anchors.get(note_id, [])
                        if len(anchors) == 1:
                            backlink_str = f" `#link(<{anchors[0]}>)[↩]`{{=typst}}"
                        elif len(anchors) > 1:
                            parts = [f"`#link(<{a}>)[↩{i+1}]`{{=typst}}" for i, a in enumerate(anchors)]
                            backlink_str = " " + " ".join(parts)
                        else:
                            backlink_str = ""
                        f.write(f"`#label(\"fn-{note_id}\")`{{=typst}}**[{note_id}]** {text}{backlink_str}\n\n")
                    else:
                        f.write(f"**[{note_id}]** {text}\n\n")
                else:
                    f.write(f"[^{note_id}]: {text}\n\n")
                    
        return True