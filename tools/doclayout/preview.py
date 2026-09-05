"""Echte Vorschau: die Definition wird tatsaechlich gesetzt, nicht nachgeahmt.

    Definition -> reference.docx + classmap.lua -> Pandoc -> .docx
                                                -> LibreOffice -> .pdf

Eine nachgebaute Qt-Vorschau waere schneller, aber sie zeigte, was Qt aus den
Werten macht -- nicht, was ein Textprogramm daraus macht. Genau in dieser
Luecke sitzen die Fehler, die man in einer Vorlage sucht: ein Rahmen, der
anders bemassen wird, ein ``keepNext``, das die Seite umbricht, eine Farbe, die
im Kasten anders wirkt als im Farbwaehler. Der Umweg kostet ein paar Sekunden
und ist die einzige Antwort, die etwas wert ist.

Gesetzt wird von LibreOffice. Die Vorschau zeigt damit die Writer-Fassung der
Vorlage -- fuer die eigene Arbeit die richtige Auskunft, und fuer eine ``.docx``
auf einem fremden Rechner mit Word eine gute Naeherung, keine Zusicherung.

GUI-frei mit Absicht (siehe ``.doc/gui_architektur.md``): der Qt-Dialog ruft
:func:`render_preview` auf und zeigt die zurueckgegebene PDF an.
"""

from __future__ import annotations

import itertools
import logging
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tools.doclayout.classmap import write_lua_filter
from tools.doclayout.process import run_hidden
from tools.doclayout.schema import LayoutDefinition, LayoutError
from tools.doclayout.targets.docx import build_reference_docx, find_pandoc
from tools.doclayout.uno_bridge import (
    convert_with_indexes,
    document_has_index,
    profile_dir,
)

#: Wie lange auf Pandoc bzw. LibreOffice gewartet wird, bevor abgebrochen wird.
PANDOC_TIMEOUT_S = 60
SOFFICE_TIMEOUT_S = 120

_LOG = logging.getLogger(__name__)

#: Es setzt immer nur einer. Vorschau und Buchsatz laufen in verschiedenen
#: Faeden, benutzen aber dasselbe LibreOffice-Benutzerprofil (eines je Prozess,
#: siehe ``uno_bridge.profile_dir``). Zwei gleichzeitige Laeufe sperrten es sich
#: gegenseitig -- mit dem Fehlerbild, das dieses Programm am schlechtesten
#: meldet: kein Fenster, keine Ausgabe, keine PDF.
#:
#: Der Wartende zahlt dafuer mit Zeit. Das ist der guenstigere Preis: Ein
#: Vorschaulauf, der hinter einem Buchsatz ansteht, kommt spaet; einer, der
#: mitten hinein laeuft, kommt womoeglich gar nicht.
_CONVERT_LOCK = threading.Lock()


class PreviewError(LayoutError):
    """Die Vorschau konnte nicht erzeugt werden."""


@dataclass
class PreviewResult:
    """Ergebnis eines Vorschaulaufs."""

    docx: Path
    pdf: Optional[Path]
    markdown: Path
    note: str = ""

    @property
    def complete(self) -> bool:
        """Wahr, wenn auch die PDF entstanden ist."""
        return self.pdf is not None and self.pdf.is_file()


def find_soffice(explicit: Optional[str] = None) -> Optional[str]:
    """Sucht LibreOffice -- ohne es gibt es nur die ``.docx``, keine PDF.

    Wie bei :func:`~tools.doclayout.targets.docx.find_pandoc` gilt ein
    ausdruecklich genannter Pfad allein.
    """
    if explicit:
        return explicit if Path(explicit).is_file() else None

    candidates = [
        shutil.which("soffice"),
        shutil.which("soffice.exe"),
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/usr/bin/soffice",
        "/usr/local/bin/soffice",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


#: Verzeichnis-Ueberschrift je Sprache. Nur was hier steht, wird uebersetzt --
#: bei allem anderen bleibt Pandocs eigene Vorgabe stehen, statt zu raten.
TOC_TITLES = {
    "de": "Inhaltsverzeichnis",
    "en": "Table of Contents",
    "fr": "Table des matieres",
    "es": "Indice",
    "it": "Indice",
    "nl": "Inhoudsopgave",
}


def toc_title_for(language: str) -> Optional[str]:
    """Verzeichnis-Ueberschrift zu einem Sprachkuerzel (``de-DE`` -> ``de``)."""
    primary = (language or "").strip().replace("_", "-").split("-")[0].lower()
    return TOC_TITLES.get(primary)


def build_sample_markdown(definition: LayoutDefinition) -> str:
    """Musterinhalt, der genau die Formate dieses Layouts ausuebt.

    Der Text wird aus der ``classmap`` abgeleitet statt fest verdrahtet: wer
    eine eigene Klasse ergaenzt, sieht sie sofort in der Vorschau, statt sich
    zu fragen, warum sich nichts tut.
    """
    lines: list[str] = [
        "---",
        'title: "Vorschau"',
        f'subtitle: "{definition.label or definition.name}"',
        'author: "Book Studio"',
        "---",
        "",
        "# Kapitelüberschrift (Ebene 1)",
        "",
        "Fließtext im Grundschriftgrad. Er zeigt Zeilenabstand, Absatzabstand "
        "und Silbentrennung -- Eigenschaften, die sich erst über mehrere Zeilen "
        "beurteilen lassen, weshalb dieser Absatz absichtlich etwas länger ist "
        "als für eine Attrappe nötig wäre.",
        "",
    ]

    for cls, style_id in sorted(definition.classmap.items()):
        style = definition.styles.get(style_id)
        label = style.display_name if style else style_id
        lines += [
            f"::: {{.{cls}}}",
            f"Beispiel für »{label}« — Klasse `.{cls}`. Auch dieser Satz ist "
            f"lang genug, um zu zeigen, wie der Umbruch innerhalb des Formats "
            f"aussieht.",
            ":::",
            "",
        ]

    lines += [
        "## Abschnitt (Ebene 2)",
        "",
        "### Unterabschnitt (Ebene 3)",
        "",
        "- Erster Aufzählungspunkt",
        "- Zweiter Aufzählungspunkt",
        "",
        "> Ein Zitat zeigt das Format für eingerückte Blöcke.",
        "",
        "| Spalte A | Spalte B |",
        "|---|---|",
        "| Wert | Ein längerer Wert zum Prüfen des Umbruchs |",
        "",
    ]
    return "\n".join(lines)


def render_preview(
    definition: LayoutDefinition,
    work_dir: Path | str,
    *,
    sample_markdown: Optional[str] = None,
    pandoc: Optional[str] = None,
    soffice: Optional[str] = None,
    to_pdf: bool = True,
) -> PreviewResult:
    """Setzt einen Musterinhalt mit *definition* und gibt die Ergebnisse zurueck.

    Fehlt LibreOffice, entsteht nur die ``.docx``; ``PreviewResult.note`` sagt
    dann warum. Das ist kein Fehlerfall -- die Datei laesst sich oeffnen, nur
    eben nicht im Fenster anzeigen.
    """
    problems = definition.validate()
    if problems:
        raise PreviewError("Layout ist nicht erzeugbar:\n  - " + "\n  - ".join(problems))

    executable = find_pandoc(pandoc)
    if not executable and pandoc:
        raise PreviewError(f"Pandoc liegt nicht unter dem angegebenen Pfad: {pandoc}")
    if not executable:
        raise PreviewError(
            "Pandoc wurde nicht gefunden -- ohne das laesst sich nichts setzen. "
            "Es liegt auch der Quarto-Installation bei."
        )

    root = Path(work_dir)
    root.mkdir(parents=True, exist_ok=True)

    reference = build_reference_docx(definition, root / "reference.docx", pandoc=pandoc)
    lua = write_lua_filter(definition, root / "classmap.lua")

    markdown = root / "vorschau.md"
    markdown.write_text(
        sample_markdown if sample_markdown is not None else build_sample_markdown(definition),
        encoding="utf-8",
        newline="\n",
    )

    docx = root / "vorschau.docx"
    language = (definition.typography.language or "de-DE").strip()
    command = [
        executable,
        "--from", "markdown",
        "--to", "docx",
        f"--reference-doc={reference}",
        f"--lua-filter={lua}",
        "--toc",
        "--metadata", f"lang={language}",
        "--output", str(docx),
        str(markdown),
    ]
    # ``lang`` allein genuegt nicht: der DOCX-Writer uebersetzt die
    # Verzeichnis-Ueberschrift nicht mit, sondern liest ``toc-title``. Ohne den
    # Eintrag stuende in einer deutschen Vorlage "Table of Contents" -- eine
    # Ueberschrift, die im fertigen Buch nie vorkommt und beim Beurteilen der
    # Vorlage nur ablenkt.
    toc_title = toc_title_for(language)
    if toc_title:
        command[-3:-3] = ["--metadata", f"toc-title={toc_title}"]
    try:
        result = run_hidden(
            command, capture_output=True, timeout=PANDOC_TIMEOUT_S, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise PreviewError(f"Pandoc antwortet nicht ({PANDOC_TIMEOUT_S}s).") from exc
    except OSError as exc:
        raise PreviewError(f"Pandoc nicht ausfuehrbar: {exc}") from exc

    if result.returncode != 0 or not docx.is_file():
        detail = (result.stderr or b"").decode("utf-8", "replace").strip()
        raise PreviewError(f"Pandoc konnte die Vorschau nicht setzen:\n{detail}")

    if not to_pdf:
        return PreviewResult(docx=docx, pdf=None, markdown=markdown, note="PDF nicht angefordert.")

    converter = find_soffice(soffice)
    if not converter:
        note = (
            f"LibreOffice liegt nicht unter dem angegebenen Pfad: {soffice}"
            if soffice
            else (
                "LibreOffice wurde nicht gefunden -- die Vorschau kann nur als "
                ".docx erzeugt werden. Zum Anzeigen im Fenster wird es gebraucht."
            )
        )
        return PreviewResult(docx=docx, pdf=None, markdown=markdown, note=note)

    pdf, grund = _convert_to_pdf(converter, docx, root)
    if pdf is None:
        return PreviewResult(docx=docx, pdf=None, markdown=markdown, note=grund)
    return PreviewResult(docx=docx, pdf=pdf, markdown=markdown)


#: Laufende Nummer der Vorschau-PDF. Jeder Lauf schreibt unter eigenem Namen,
#: damit nie die gerade angezeigte Datei geloescht werden muss (Windows haelt
#: sie offen, solange ``QtPdf`` sie zeigt).
_LAUFNUMMER = itertools.count(1)


def _alte_vorschauen_entfernen(
    out_dir: Path, *, behalten: Path, stamm: str = "vorschau"
) -> None:
    """Raeumt PDFs frueherer Laeufe weg -- soweit sie freigegeben sind.

    Fehlschlaege werden uebergangen: Eine noch angezeigte Datei zu behalten ist
    kein Problem, sie kostet ein paar Kilobyte bis zum Schliessen des Editors.
    Sie loeschen zu **wollen** war der Fehler, der die Vorschau lahmlegte.
    """
    for alt in out_dir.glob(f"{stamm}_*.pdf"):
        if alt == behalten:
            continue
        try:
            alt.unlink()
        except OSError:
            continue


def _convert_to_pdf(
    converter: str, docx: Path, out_dir: Path
) -> tuple[Optional[Path], str]:
    """DOCX -> PDF ueber LibreOffice; liefert ``(PDF, Grund des Scheiterns)``.

    **Zwei Wege, in dieser Reihenfolge.** Steckt im Dokument ein Verzeichnisfeld,
    wird LibreOffice ferngesteuert (``uno_bridge``), damit das Verzeichnis vor
    dem Export aufgebaut wird -- ``--convert-to pdf`` tut das nicht, und in der
    PDF stand dann die Ueberschrift "Inhaltsverzeichnis" mit nichts darunter.
    Geht dabei irgendetwas schief, uebernimmt der Direktweg. Der Rueckfall ist
    kein Fehler und wird auch nicht als solcher gemeldet: Schlimmstenfalls ist
    das Ergebnis so gut wie vorher, nie schlechter.

    Ein eigenes Benutzerprofil (``-env:UserInstallation``) verhindert, dass der
    Aufruf an einer bereits laufenden LibreOffice-Instanz scheitert -- sonst
    beendet sich der Prozess sofort, ohne etwas zu schreiben. Es liegt an einem
    **kurzen** Pfad, nicht unter ``out_dir``: Ab etwa 147 Zeichen beendet sich
    LibreOffice kommentarlos mit ``0xC0000409`` (siehe
    ``uno_bridge.profile_dir`` -- dort steht auch, warum das die Vorschau selbst
    nie getroffen hat).

    **Jeder Lauf bekommt einen eigenen Dateinamen.** Das ist keine Ordnungsliebe,
    sondern Notwehr gegen Windows: Die angezeigte PDF haelt ``QtPdf`` offen,
    solange sie im Fenster steht. Ein fester Name hiesse, genau diese Datei vor
    jedem Lauf loeschen zu muessen -- und das scheitert dann mit ``WinError 32``
    ("wird von einem anderen Prozess verwendet"). Die Vorschau blieb danach ganz
    aus.

    Der Umweg ueber einen frischen Namen loest zugleich das Problem, dessen
    wegen ueberhaupt geloescht wurde: Eine liegengebliebene PDF war nicht von
    einer frisch gesetzten zu unterscheiden, und ein Absturz von LibreOffice
    endete damit, dass die Vorschau das alte Blatt als aktuell anzeigte. Da der
    Name jetzt neu ist, kann eine vorhandene Datei nur aus **diesem** Lauf
    stammen -- ohne dass jemand etwas loeschen muss, das gerade angesehen wird.

    Der Grund des Scheiterns wird durchgereicht statt verworfen. Vorher stand
    dort pauschal "laeuft evtl. schon eine Instanz" -- also ausgerechnet die
    Ursache, die das eigene Profil ausschliesst; wer dem nachging, suchte an
    der falschen Stelle.
    """
    with _CONVERT_LOCK:
        return _convert_to_pdf_locked(converter, docx, out_dir)


def _convert_to_pdf_locked(
    converter: str, docx: Path, out_dir: Path
) -> tuple[Optional[Path], str]:
    """Der eigentliche Lauf -- nur mit gehaltener :data:`_CONVERT_LOCK`."""
    # Der endgueltige Name steht vorab fest -- beide Wege schreiben dorthin.
    ziel = out_dir / f"{docx.stem}_{next(_LAUFNUMMER)}.pdf"

    # Erster Weg: LibreOffice fernsteuern, damit die Verzeichnisse aufgebaut
    # werden. Nur wenn ueberhaupt eines im Dokument steckt -- sonst hat der
    # Umweg keinen Vorteil und nur zusaetzliche Fehlerquellen.
    hinweis_uno = ""
    if document_has_index(docx):
        gelungen, hinweis_uno = convert_with_indexes(converter, docx, ziel)
        if gelungen:
            _alte_vorschauen_entfernen(out_dir, behalten=ziel, stamm=docx.stem)
            return ziel, ""
        _LOG.info("UNO-Weg nicht moeglich, weiche auf den Direktweg aus: %s", hinweis_uno)

    # LibreOffice benennt sein Ergebnis nach der Eingabe; dieser Name ist
    # transient und wird nie angezeigt, laesst sich also immer loeschen.
    roh = out_dir / f"{docx.stem}.pdf"
    try:
        roh.unlink(missing_ok=True)
    except OSError as exc:
        return None, (
            f"Die Vorschau-PDF des letzten Laufs liess sich nicht ersetzen "
            f"({exc}). Ist sie noch in einem anderen Programm geoeffnet?"
        )

    # Das Profil liegt bewusst **nicht** unter ``out_dir``: Dort wurde der Pfad
    # zu lang und LibreOffice beendete sich kommentarlos (siehe
    # ``uno_bridge.profile_dir``).
    profil_pfad = profile_dir()
    profile = profil_pfad.resolve().as_uri()
    command = [
        converter,
        f"-env:UserInstallation={profile}",
        "--headless",
        "--norestore",
        "--convert-to", "pdf",
        "--outdir", str(out_dir),
        str(docx),
    ]
    try:
        result = run_hidden(
            command,
            capture_output=True,
            timeout=SOFFICE_TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, f"LibreOffice antwortet nicht ({SOFFICE_TIMEOUT_S}s)."
    except OSError as exc:
        return None, f"LibreOffice nicht ausfuehrbar ({converter}): {exc}"

    # Erst die Datei, dann der Rueckgabewert: Manche LibreOffice-Fassungen
    # melden einen Wert ungleich null und haben trotzdem sauber gesetzt. Da der
    # Rohname oben verschwunden ist, kann eine vorhandene Datei nur aus diesem
    # Lauf stammen -- sie ist damit die verlaesslichere Auskunft.
    if roh.is_file():
        try:
            roh.replace(ziel)
        except OSError:
            # Umbenennen misslungen -- dann eben unter dem Rohnamen. Er ist in
            # diesem Fall frisch, nur der naechste Lauf wird es schwerer haben.
            ziel = roh
        _alte_vorschauen_entfernen(out_dir, behalten=ziel, stamm=docx.stem)
        return ziel, ""

    detail = (result.stderr or b"").decode("utf-8", "replace").strip()
    grund = f"LibreOffice hat keine PDF geliefert (Rueckgabewert {result.returncode})."
    if detail:
        grund += f" {detail}"
    else:
        grund += (
            " Ohne Meldung bricht LibreOffice meist am eigenen Benutzerprofil ab; "
            f"der Pfad dorthin lautet: {profil_pfad}"
        )
    if hinweis_uno:
        grund += f" (Auch der Weg ueber die Fernsteuerung ging nicht: {hinweis_uno})"
    return None, grund


__all__ = [
    "PANDOC_TIMEOUT_S",
    "SOFFICE_TIMEOUT_S",
    "PreviewError",
    "PreviewResult",
    "build_sample_markdown",
    "find_soffice",
    "render_preview",
]
