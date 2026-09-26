import re
import shutil
import json
import logging
from pathlib import Path
import yaml

from chapter_title_render import (
    ensure_silent_chapter_frontmatter,
    maybe_inject_chapter_title,
    parse_frontmatter_yaml,
)
from heading_anchor_ascii import ensure_ascii_heading_ids
from list_markup_fixer import repariere_listen_markup
from recto_open import (
    RECTO_MARKER,
    docx_page_setup_from_reference,
    docx_reference_for_book,
    docx_section_break_block,
    is_docx_format,
    maybe_ensure_recto_open,
    ohne_eigenen_docx_abschnitt,
    should_open_on_recto,
)
from table_to_definition_list import wandle_breite_tabellen
from table_width_fixer import setze_spaltenbreiten

_LOG = logging.getLogger(__name__)

# B4 (Refactoring): Die komplette Fußnoten-Funktionalität wurde
# entfernt. Pandoc-konforme `[^1]`-Marker im Quell-Markdown werden
# unverändert weitergereicht — Quarto kümmert sich um die Auflösung.
# Die frühere `_namespace_local_footnotes` / `_inject_footnote_backlinks`
# / `_uses_harvester` / `FootnoteHarvester`-Logik existiert nicht mehr.


#: Der zentrierte Ein-Zeichen-Trenner des Aggregators. Erkannt wird er am
#: ``text-align: center`` im style-Attribut, nicht an der Klasse: ältere
#: Läufe schrieben den Div ohne ``.prompt-separator``, und beide Fassungen
#: liegen heute in denselben Büchern.
_PROMPT_SEPARATOR_DIV_RE = re.compile(
    r"^:{3,}[ \t]*\{[^}\n]*text-align:\s*center[^}\n]*\}[ \t]*\r?\n"
    r"[ \t]*(?P<glyph>\S[^\n]*?)[ \t]*\r?\n"
    r"[ \t]*:{3,}[ \t]*$",
    re.MULTILINE,
)


def _load_unnumbered_heading_levels(book_path: Path) -> frozenset[int]:
    """Read ``dialog_state.unnumbered_heading_levels`` from publish_meta.json."""
    meta_path = Path(book_path) / "publish_meta.json"
    if not meta_path.is_file():
        return frozenset()
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return frozenset()
    if not isinstance(data, dict):
        return frozenset()
    dialog_state = data.get("dialog_state")
    raw: object = []
    if isinstance(dialog_state, dict):
        raw = dialog_state.get("unnumbered_heading_levels", [])
    if not isinstance(raw, list):
        return frozenset()
    levels: set[int] = set()
    for item in raw:
        try:
            level = int(item)
        except (TypeError, ValueError):
            continue
        if 1 <= level <= 6:
            levels.add(level)
    return frozenset(levels)


class PreProcessor:
    def __init__(self, book_path, output_format="typst"):
        """Bereitet ein Quarto-Buch für den Render vor.

        Vor B4 wurden hier `footnote_mode` und `enable_footnote_backlinks`
        entgegengenommen. Beide Parameter wurden entfernt — das gesamte
        Fußnoten-Harvesting/Endnoten-System ist stillgelegt.
        """
        self.book_path = Path(book_path)
        self.processed_dir = self.book_path / "processed"
        self.output_format = str(output_format) if output_format else "typst"
        # Buchweite Eindeutigkeit fuer generierte Typst-Labels/Pandoc-Header-IDs
        # (Kapitel-Labels + ASCII-IDs gegen Umlaut-Sprungmarken-Bug, siehe
        # heading_anchor_ascii.py). Quartos crossref macht IDs buchglobal
        # sichtbar (nicht nur pro Datei), daher EIN Set fuer den ganzen Lauf.
        self._used_heading_ids: set = set()
        self._unnumbered_heading_levels = _load_unnumbered_heading_levels(self.book_path)

    def _ensure_heading_ids(self, body: str) -> str:
        return ensure_ascii_heading_ids(
            body,
            used_ids=self._used_heading_ids,
            unnumbered_levels=self._unnumbered_heading_levels,
        )

    def _extract_parts(self, content):
        """Trennt Frontmatter extrem robust vom Text ab, selbst bei Windows-BOMs."""
        match = re.match(r'^\uFEFF?---\s*[\r\n]+(.*?)[\r\n]+---\s*[\r\n]*', content, re.DOTALL)
        if match:
            return match.group(0), content[match.end():]
        return "", content

    def _sanitize_frontmatter_for_render(self, frontmatter):
        """Entfernt nicht-numerisches `order` im processed-Klon (Quarto verlangt Number)."""
        if not frontmatter:
            return frontmatter

        match = re.match(
            r'^(\uFEFF?)---\s*[\r\n]+(.*?)[\r\n]+---\s*[\r\n]*$',
            frontmatter,
            re.DOTALL,
        )
        if not match:
            return frontmatter

        bom = match.group(1)
        frontmatter_body = match.group(2)
        newline = "\r\n" if "\r\n" in frontmatter else "\n"

        try:
            parsed = yaml.safe_load(frontmatter_body) or {}
        except yaml.YAMLError:
            return frontmatter

        order_val = parsed.get("order")
        if order_val is None:
            return frontmatter

        # Quarto-Schema verlangt `order` als Number. Book-Studio speichert
        # Positionen oft als String ("10", "END-50"): Zahlen-Strings → int,
        # bereits numerisch → unverändert, sonst (END-*) → Feld entfernen.
        if isinstance(order_val, bool):
            parsed.pop("order", None)
        elif isinstance(order_val, (int, float)):
            return frontmatter
        elif isinstance(order_val, str) and re.fullmatch(r"\d+", order_val.strip()):
            parsed["order"] = int(order_val.strip())
        else:
            parsed.pop("order", None)

        dumped = yaml.safe_dump(
            parsed,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        ).rstrip("\r\n")

        return f"{bom}---{newline}{dumped}{newline}---{newline}"

    def _prune_unused_footnote_definitions(self, text):
        """B4-Stub: Vorher entfernte diese Methode ungenutzte Fußnoten-
        Definitionen. Mit der Abschaltung der Fußnoten-Verarbeitung ist
        sie ein No-op — bleibt aber als stabile API für externe Importer
        erhalten."""
        return text

    # =========================================================================
    # NEU: DER WASCHGANG FÜR KAPUTTE MARKDOWN-SYNTAX
    # =========================================================================
    def _rewrite_prompt_separators(self, text):
        """Zentriert den ◈-Trenner zwischen Fachtext und nächster Frage.

        Der Aggregator liefert ihn als Fenced Div mit einem HTML-``style``:

            ::: {.prompt-separator style="text-align: center;"}
            ◈
            :::

        Quartos Typst-Writer wertet davon **nichts** aus — weder die Klasse
        noch das ``style``-Attribut überleben; im .typ steht am Ende ein
        nacktes ``#block[◈]``. Das Zeichen erscheint deshalb linksbündig
        und in Grundschriftgröße, obwohl die Quelle etwas anderes sagt.
        Zentrieren lässt sich das im Typst-Layer allein nicht mehr, weil
        dort die Information fehlt, dass dieser Block ein Trenner war.

        Deshalb wird der Div hier — und nur für Typst — durch einen
        Raw-Block ersetzt, der die Satzfunktion aus ``typst-show.typ``
        aufruft. Für DOCX bleibt alles unangetastet: dort bildet
        ``classmap.lua`` die Klasse auf ein Absatzformat ab, und ein
        Raw-Typst-Block wäre dort ersatzlos verloren.
        """
        if not str(self.output_format or "").lower().startswith("typst"):
            return text

        def _ersetze(match):
            glyph = match.group("glyph").strip()
            # Eckige Klammern würden die Typst-Content-Klammer sprengen.
            # Ein Trenner enthält keine — falls doch, bleibt der Div stehen,
            # statt kaputten Typst-Code zu erzeugen.
            if not glyph or "[" in glyph or "]" in glyph:
                return match.group(0)
            return (
                "```{=typst}\n"
                "#bs-prompt-separator[" + glyph + "]\n"
                "```"
            )

        return _PROMPT_SEPARATOR_DIV_RE.sub(_ersetze, text)

    def _sanitize_markdown(self, text):
        """Repariert alte Boxen und übersetzt @-Zitationen absolut verlustfrei in echte Fußnoten."""
        # 0. Trenner zuerst: danach ist er ein Raw-Block und keine der
        #    folgenden Div-/Zitations-Regeln fasst ihn mehr an.
        text = self._rewrite_prompt_separators(text)

        # 0b. Leerzeile vor Listen, die einen Absatz unterbrechen. Pandoc
        #     laesst eine Liste einen Absatz nicht unterbrechen; ohne die
        #     Leerzeile wird die Aufzaehlungszeile zur Fortsetzung des
        #     Absatzes und der Bindestrich steht mitten im gesetzten Text.
        #     Am Andalusien-Buch: 174 Stellen in der Quelle, 294 Befunde im
        #     Druck-PDF. Laeuft NACH _rewrite_prompt_separators, damit der
        #     Trenner-Div bereits Raw-Block ist, und ist idempotent -- ein
        #     erneuter Render aendert nichts mehr.
        #     Zusaetzlich werden ``☐``-Zeilen zu echten Listeneintraegen:
        #     das Kaestchen allein ist fuer Pandoc Fliesstext, die Zeilen
        #     werden sonst zu einem Absatz zusammengezogen (S. 347 der
        #     Andalusien-Druckfahne: 15 Kaestchen als Textwand).
        text, _reparaturen = repariere_listen_markup(text)

        # 0c. Tabellen, die als Tabelle nicht mehr tragen, in Definitions-
        #     listen wandeln. Laeuft VOR der Spaltenverteilung: was hier
        #     zum Absatz wird, braucht keine Spaltenbreite mehr, und was
        #     Tabelle bleibt, bekommt sie anschliessend proportional.
        #     Am Andalusien-Buch nachgemessen: alle 130 Tabellen verlangen
        #     mehr Breite, als die Seite hat -- die schmalste hat eine
        #     Zelle mit 40 Zeichen, der Median 108, bei 53 Zeichen
        #     Satzbreite. Keine Spaltenverteilung loest einen solchen
        #     Mangel; kleiner setzen macht die Tabelle nur unlesbar.
        #     Kein Zellinhalt geht verloren (1858 von 1858 wiedergefunden),
        #     die Wortfolge innerhalb der Zellen bleibt unveraendert.
        text, _definitionslisten = wandle_breite_tabellen(text)

        # 0d. Spaltenbreiten der verbliebenen Pipe-Tabellen ableiten.
        #     Pandoc liest sie aus der Strichzahl der Trennzeile; bei
        #     gleich langen Trennern verteilt Typst gleichmaessig, und
        #     "951 29 00 00" bekommt so viel Platz wie ein ganzer Satz.
        #     Aendert ausschliesslich Bindestriche, kein Wort.
        text, _spalten = setze_spaltenbreiten(text)
        
        # 1. Boxen reparieren: :::: \[BOX: Titel\] Inhalt ::: -> Quarto Callout
        text = re.sub(
            r':{3,4}\s*\\?\[BOX:\s*(.*?)\\?\](.*?):{3,4}', 
            r'::: {.callout-note title="\1"}\n\2\n:::', 
            text, 
            flags=re.DOTALL
        )
        
        # 1b. Übrig gebliebene eklige 4er-Doppelpunkte auf saubere 3er kürzen
        text = re.sub(r'^::::\s*$', r':::', text, flags=re.MULTILINE)
        
        # 2. @-ZITATIONEN ROBUST IN FUSSNOTEN UMWANDELN
        # Ziel: Auch Varianten wie [@Key, S. 331] oder [vgl. @Key1; @Key2] sicher abfangen.

        # A) Definitionszeilen mit Klammernotation normalisieren:
        #    [@Key, S. 331]: Text  ->  [^Key]: Text
        text = re.sub(
            r'^([ \t]*)\[@([a-zA-Z0-9_-]+)(?:[^\]]*)\]:',
            r'\1[^\2]:',
            text,
            flags=re.MULTILINE,
        )

        # B) Definitionszeilen ohne Klammern normalisieren:
        #    @Key: Text -> [^Key]: Text
        text = re.sub(
            r'^([ \t]*)@([a-zA-Z0-9_-]+):',
            r'\1[^\2]:',
            text,
            flags=re.MULTILINE,
        )

        # C) Klammer-Zitationsgruppen in Marker umwandeln:
        #    [@Key, S. 331] -> [^Key]
        #    [vgl. @A; @B]  -> [^A][^B]
        def _replace_citation_group(match):
            group_content = match.group(1)
            labels = re.findall(r'@([a-zA-Z0-9_-]+)', group_content)
            if not labels:
                return match.group(0)
            unique_labels = []
            seen = set()
            for label in labels:
                if label in seen:
                    continue
                seen.add(label)
                unique_labels.append(label)
            return ''.join(f'[^{label}]' for label in unique_labels)

        text = re.sub(r'\[([^\]\n]*@[^\]\n]*)\]', _replace_citation_group, text)

        # D) Bare @Label-Verweise im Fließtext umwandeln (ohne E-Mail/Teilwörter zu beschädigen)
        #    Beispiel: "... (siehe @Key)" -> "... (siehe [^Key])"
        text = re.sub(r'(?<![\w\[\^])@([a-zA-Z0-9_-]+)', r'[^\1]', text)
        
        return text
    # =========================================================================

    def _gather_all_definitions(self, nodes):
        """B4-Stub: Vorher wurden hier in einem Pass 1 alle Dateien
        vorab eingelesen, um das globale Footnote-Lexikon zu füllen.
        Mit der Abschaltung der Fußnoten-Verarbeitung ist diese Methode
        ein No-op. Sie bleibt als stabile API für externe Importer
        erhalten.
        """
        return

    def prepare_render_environment(self, tree_data):
        if self.processed_dir.exists():
            shutil.rmtree(self.processed_dir)
        self.processed_dir.mkdir(parents=True)

        index_path = self.book_path / "index.md"
        # Ein frueher angehaengter DOCX-Abschnittsblock kommt zuerst weg: Bei
        # DOCX wird er unten mit der aktuellen Seiteneinrichtung neu gesetzt,
        # bei jedem anderen Format gehoert er nicht hinein. Bis 2026-09-26
        # blieb er im Original stehen (prepare-only) und verhinderte jede
        # Aktualisierung.
        if index_path.exists():
            alt = index_path.read_text(encoding='utf-8')
            bereinigt = ohne_eigenen_docx_abschnitt(alt)
            if bereinigt != alt:
                index_path.write_text(bereinigt, encoding='utf-8')

        # --- DER MAGISCHE PANDOC FIX ---
        if index_path.exists():
            with open(index_path, 'r', encoding='utf-8') as f:
                idx_content = f.read()
            if not idx_content.endswith('\n\n'):
                with open(index_path, 'a', encoding='utf-8') as f:
                    f.write('\n\n')
        # -------------------------------

        # DOCX-Recto: jede Einheit schliesst ihren Abschnitt am Ende (siehe
        # recto_open). Einheiten sammeln, Abschluss erst nach Amalgamierung.
        docx_units: list[tuple[Path, str]] = []
        if is_docx_format(self.output_format):
            reference = docx_reference_for_book(self.book_path)
            self._docx_section_refs, self._docx_page_setup = (
                docx_page_setup_from_reference(reference) if reference else ("", "")
            )
            if index_path.exists():
                docx_units.append((index_path, "index.md"))

        # === PASS 1: jetzt No-op (B4 — Footnote-Harvesting entfernt) ===
        self._gather_all_definitions(tree_data)

        # === PASS 2: DATEIEN SCHREIBEN UND VERWEISE SETZEN ===
        processed_tree = []

        for root_node in tree_data:
            # B-Fix (Code-Review 2026-07-03): frueher entschied allein
            # `root_node.get("children")`, ob ein Knoten als "Part"
            # behandelt wurde. Echte Parts erkennt man aber am virtuellen
            # Pfad "PART:<Titel>" (keine reale Datei, siehe
            # `yaml_engine._tree_to_quarto_list`). Ein regulaeres Kapitel
            # MIT eigenen Unterkapiteln hat einen echten Datei-Pfad und
            # wurde vorher faelschlich in die Part-Logik geschickt: seine
            # Unterkapitel wurden dabei als eigenstaendige Chapters neben
            # dem Hauptkapitel gefuehrt, statt (wie bei einem normalen
            # verschachtelten Kapitel vorgesehen) inline in dessen Datei
            # amalgamiert zu werden.
            is_part_node = str(root_node.get("path", "")).startswith("PART:")

            if is_part_node:
                part_dest = self._process_part_file(root_node)
                docx_units.append((part_dest, str(root_node.get("path") or "")))

                new_part = {
                    "title": root_node["title"],
                    "path": f"processed/{root_node['path']}",
                    "children": []
                }

                for chapter_node in root_node.get("children", []):
                    chapter_dest = self._process_host_file(chapter_node)

                    new_chapter = {
                        "title": chapter_node["title"],
                        "path": f"processed/{chapter_node['path']}",
                        "children": []
                    }
                    new_part["children"].append(new_chapter)

                    if chapter_node.get("children"):
                        self._amalgamate_children(chapter_node["children"], chapter_dest, offset=1)
                    docx_units.append((chapter_dest, str(chapter_node.get("path") or "")))

                processed_tree.append(new_part)
            else:
                chapter_dest = self._process_host_file(root_node)

                new_chapter = {
                    "title": root_node["title"],
                    "path": f"processed/{root_node['path']}",
                    "children": []
                }
                processed_tree.append(new_chapter)

                if root_node.get("children"):
                    self._amalgamate_children(root_node["children"], chapter_dest, offset=1)
                docx_units.append((chapter_dest, str(root_node.get("path") or "")))

        self._close_docx_sections(docx_units)

        # B4: Endnoten-Generierung entfernt.

        return processed_tree

    def _close_docx_sections(self, units):
        """DOCX: Abschnittsende nach jeder Einheit (``oddPage`` = beginnt rechts).

        Die letzte Einheit wird nur bei Recto abgeschlossen -- sonst schliesst
        der End-``sectPr`` der Vorlage sie, ohne leere Schlussseite.
        """
        existing = [(Path(dest), rel) for dest, rel in units if dest and Path(dest).is_file()]
        for idx, (dest, rel_path) in enumerate(existing):
            content = dest.read_text(encoding='utf-8')
            if RECTO_MARKER in content[-600:]:
                continue  # schon abgeschlossen (idempotent, z. B. index.md)
            frontmatter, _body = self._extract_parts(content)
            recto = rel_path != "index.md" and should_open_on_recto(
                parse_frontmatter_yaml(frontmatter), rel_path=rel_path
            )
            if idx == len(existing) - 1 and not recto:
                continue
            block = docx_section_break_block(
                recto_start=recto,
                page_setup_xml=getattr(self, "_docx_page_setup", ""),
                refs_xml=getattr(self, "_docx_section_refs", ""),
            )
            with open(dest, 'a', encoding='utf-8') as f:
                f.write(block)

    def _process_part_file(self, node):
        src = self.book_path / node["path"]
        dest = self.processed_dir / node["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not src.exists():
            return dest

        with open(src, 'r', encoding='utf-8') as f:
            content = f.read()

        frontmatter, body = self._extract_parts(content)
        frontmatter = self._sanitize_frontmatter_for_render(frontmatter)
        rel_path = str(node.get("path") or "")
        frontmatter = ensure_silent_chapter_frontmatter(frontmatter, rel_path=rel_path)

        # 1. Text waschen (Box-Reparatur, @-Zitation → [^Key])
        body = self._sanitize_markdown(body)

        # 2. H1 bereinigen (Body-H1 würde mit YAML-title konkurrieren)
        body = re.sub(r'^(#\s+.*)$', r'', body, count=1, flags=re.MULTILINE)

        # 2b. ASCII-IDs fuer Level 2–6 Ueberschriften (Workaround Typst-PDF-
        # Named-Destination-Bug bei Umlauten, siehe heading_anchor_ascii.py)
        body = self._ensure_heading_ids(body)

        # 2c. Recto (rechte Öffnung) — vor Titel-Injection; strippt manuelle
        # Typst-to:"odd"-Blöcke, damit nichts doppelt wird.
        body = maybe_ensure_recto_open(
            frontmatter,
            body,
            output_format=self.output_format,
            rel_path=rel_path,
        )

        # 3. Sichtbare Kapitelüberschrift nur bei Opt-in (Typst)
        body = maybe_inject_chapter_title(
            frontmatter,
            body,
            node_title=str(node.get("title") or ""),
            output_format=self.output_format,
            rel_path=rel_path,
            used_ids=self._used_heading_ids,
        )

        # B4: Footnote-Harvesting-Block entfernt (war 3+5).

        with open(dest, 'w', encoding='utf-8') as f:
            f.write(frontmatter + body.rstrip() + "\n\n")

        # Companion-SVGs in processed/ kopieren
        self._copy_companion_svgs(src, dest)

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
        frontmatter = self._sanitize_frontmatter_for_render(frontmatter)
        rel_path = str(node.get("path") or "")
        frontmatter = ensure_silent_chapter_frontmatter(frontmatter, rel_path=rel_path)

        # 1. Text waschen (Box-Reparatur, @-Zitation → [^Key])
        body = self._sanitize_markdown(body)

        # 2. H1 bereinigen (Body-H1 würde mit YAML-title konkurrieren)
        body = re.sub(r'^(#\s+.*)$', r'', body, count=1, flags=re.MULTILINE)

        # 2b. ASCII-IDs fuer Level 2–6 Ueberschriften (Workaround Typst-PDF-
        # Named-Destination-Bug bei Umlauten, siehe heading_anchor_ascii.py)
        body = self._ensure_heading_ids(body)

        # 2c. Recto (rechte Öffnung) — vor Titel-Injection; strippt manuelle
        # Typst-to:"odd"-Blöcke, damit nichts doppelt wird.
        body = maybe_ensure_recto_open(
            frontmatter,
            body,
            output_format=self.output_format,
            rel_path=rel_path,
        )

        # 3. Sichtbare Kapitelüberschrift nur bei Opt-in (Typst)
        body = maybe_inject_chapter_title(
            frontmatter,
            body,
            node_title=str(node.get("title") or ""),
            output_format=self.output_format,
            rel_path=rel_path,
            used_ids=self._used_heading_ids,
        )

        # B4: Footnote-Harvesting-Block entfernt (war 3+5).

        with open(dest, 'w', encoding='utf-8') as f:
            f.write(frontmatter + body.rstrip() + "\n\n")

        # Companion-SVGs in processed/ kopieren
        self._copy_companion_svgs(src, dest)

        return dest

    def _copy_companion_svgs(self, src: Path, dest: Path) -> None:
        """Kopiere ``svg_*.svg``-Dateien aus dem Quell-Verzeichnis
        neben die verarbeitete .md-Datei in ``processed/``."""
        src_dir = src.parent
        dst_dir = dest.parent
        if src_dir == dst_dir:
            return
        for svg in src_dir.glob("svg_*.svg"):
            dst_file = dst_dir / svg.name
            if not dst_file.exists():
                try:
                    shutil.copy2(svg, dst_file)
                except OSError as exc:
                    # Nicht still: sonst fehlt das Bild später im Render ohne Hinweis.
                    _LOG.warning("Begleit-SVG nicht kopiert: %s → %s (%s)", svg, dst_file, exc)

    def _amalgamate_children(self, children, host_dest, offset):
        # offset: Rekursionstiefe (API); Heading-Shift liegt in den Quellen.
        _ = offset
        for child in children:
            src = self.book_path / child["path"]
            if src.exists():
                with open(src, 'r', encoding='utf-8') as f:
                    content = f.read()

                _, body = self._extract_parts(content)

                # 1. Text waschen (Box-Reparatur, @-Zitation → [^Key])
                body = self._sanitize_markdown(body)

                # 1b. ASCII-IDs fuer Level 2–6 Ueberschriften (Workaround
                # Typst-PDF-Named-Destination-Bug bei Umlauten, siehe
                # heading_anchor_ascii.py) — hier landen die eigentlichen
                # Fragen-Ueberschriften der amalgamierten Kapitel.
                body = self._ensure_heading_ids(body)

                # B4: Footnote-Harvesting-Block entfernt (war 2).
                # Überschriften-Shift entfernt: Quellen sind bereits eingerückt.

                with open(host_dest, 'a', encoding='utf-8') as f:
                    f.write(f"\n\n\n{body.strip()}\n\n")

            if child.get("children"):
                self._amalgamate_children(child["children"], host_dest, 0)
