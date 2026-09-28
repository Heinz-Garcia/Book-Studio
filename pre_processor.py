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
from recto_open import (
    RECTO_MARKER,
    docx_page_setup_from_reference,
    docx_reference_for_book,
    docx_section_break_block,
    is_docx_format,
    maybe_ensure_recto_open,
    ohne_eigenen_docx_abschnitt,
    should_open_on_recto,
    strip_manual_recto_breaks,
)
from render_text_prep import bereite_markdown_vor, ohne_erste_h1

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


#: Titelei-Klassen und ihre Schriftgroesse im Typst-Satz (relativ zur
#: Grundschrift). Das DOCX-Gegenstueck sind die Formate ``Titelei-*`` der
#: Layouts (tools/doclayout/library).
TITELEI_TYPST_GROESSE = {
    "titelei-autor": "1.2em",
    "titelei-titel": "2.4em",
    "titelei-zusatz": "1em",
}
_TITELEI_DIV_RE = re.compile(
    r"^:{3,}[ \t]*\{\.(?P<klasse>titelei-autor|titelei-titel|titelei-zusatz)\}[ \t]*\r?\n"
    r"(?P<inhalt>.*?)\r?\n:{3,}[ \t]*$",
    re.MULTILINE | re.DOTALL,
)

#: Formatieranweisung ``text-align: center`` an einem Div (mit oder ohne Klasse).
_ZENTRIERT_AUF_RE = re.compile(r"^:{3,}[ \t]*\{[^}\n]*text-align:\s*center[^}\n]*\}[ \t]*$")
_DIV_AUF_RE = re.compile(r"^:{3,}[ \t]*\S")
_DIV_ZU_RE = re.compile(r"^:{3,}[ \t]*$")
_CODEZAUN_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})")


def zentriere_fuer_typst(text):
    """Zentrierte Divs in ``#align(center)[`` ... ``]`` fassen (Raw-Typst).

    Quartos Typst-Writer verwirft das ``style``-Attribut. Der Inhalt bleibt
    Markdown; nur Anfang und Ende des Divs werden zu Raw-Typst-Klammern --
    verschachtelte Divs und Codebloecke werden mitgezaehlt, nicht geraten.
    Das DOCX-Gegenstueck ist das Hilfsformat ``Zentriert`` (classmap.lua).
    """
    zeilen = text.split("\n")
    stapel = []  # je offenem Div: zentriert?
    zaun = ""
    for i, zeile in enumerate(zeilen):
        if zaun:
            if zeile.lstrip().startswith(zaun):
                zaun = ""
            continue
        treffer = _CODEZAUN_RE.match(zeile)
        if treffer:
            zaun = treffer.group(1)
            continue
        if _ZENTRIERT_AUF_RE.match(zeile):
            stapel.append(True)
            zeilen[i] = "```{=typst}\n#align(center)[\n```\n"
        elif _DIV_ZU_RE.match(zeile):
            if stapel and stapel.pop():
                zeilen[i] = "\n```{=typst}\n]\n```"
        elif _DIV_AUF_RE.match(zeile):
            stapel.append(False)
    return "\n".join(zeilen)


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

    def _rewrite_titelei(self, text):
        """Titelei-Divs (``::: {.titelei-titel}`` ...) fuer Typst zentriert setzen.

        Quartos Typst-Writer wirft die Klasse weg (siehe
        :meth:`_rewrite_prompt_separators`). Der Inhalt bleibt Markdown; nur
        Anfang und Ende des Divs werden zu Raw-Typst-Klammern. Der DOCX-Satz
        sieht die Klassen unveraendert und bildet sie auf Absatzformate ab --
        so haben beide Formate dieselben Titelseiten aus derselben Quelle.
        """
        if not str(self.output_format or "").lower().startswith("typst"):
            return text

        def _ersetze(match):
            groesse = TITELEI_TYPST_GROESSE[match.group("klasse")]
            inhalt = match.group("inhalt").strip("\n")
            return (
                "```{=typst}\n"
                f"#align(center)[#text(size: {groesse})[\n"
                "```\n\n"
                + inhalt
                + "\n\n```{=typst}\n]]\n```"
            )

        return _TITELEI_DIV_RE.sub(_ersetze, text)

    def _sanitize_markdown(self, text):
        """Repariert alte Boxen und übersetzt @-Zitationen absolut verlustfrei in echte Fußnoten."""
        # 0. Trenner zuerst: danach ist er ein Raw-Block und keine der
        #    folgenden Div-/Zitations-Regeln fasst ihn mehr an.
        text = self._rewrite_prompt_separators(text)

        # 0b. Titelei (Schmutztitel/Haupttitel) ebenfalls nur fuer Typst:
        #     dieselben Klassen-Divs wie im DOCX, dort ueber Absatzformate.
        text = self._rewrite_titelei(text)

        # 0c. Uebrige Formatieranweisung text-align: center (mehrzeilig, also
        #     kein Trenner): zentriert setzen statt stillschweigend linksbuendig.
        if str(self.output_format or "").lower().startswith("typst"):
            text = zentriere_fuer_typst(text)

        # 1. Alles Formatneutrale (Listen, Kaestchen, breite Tabellen,
        #    Spaltenbreiten, [BOX:]-Kaesten, @-Zitationen) -- SSOT mit dem
        #    DOCX-Satz, siehe render_text_prep.py. Laeuft NACH den
        #    Typst-Schritten, damit Trenner und Titelei bereits Raw-Bloecke
        #    sind und keine Regel sie mehr anfasst.
        text = bereite_markdown_vor(text)

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
        body = ohne_erste_h1(body)

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
        body = ohne_erste_h1(body)

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

                # 0. Manuelle Rechts-Umbrueche (odd) an Anfang/Ende weg: Ein
                # Unterkapitel steht im Fluss seines Kapitels. Bis 2026-09-26
                # blieben sie hier stehen (nur Kapitel wurden bereinigt) und
                # erzeugten Leerseiten mitten im Kapitel. Umbrueche im Text
                # selbst bleiben, wie bei Kapiteln.
                body = strip_manual_recto_breaks(body)

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
