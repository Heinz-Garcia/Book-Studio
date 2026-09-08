"""PDF-Seitengeometrie in prüfbare Strukturen überführen (PyMuPDF).

Alles, was hier passiert, ist Messen — keine Bewertung. Die Regeln liegen in
``rules.py`` und sind dadurch ohne PDF testbar.

Tabellen werden NICHT über Linien erkannt: Typst setzt Tabellen im Buchsatz
meist ohne Rahmen, ``page.find_tables()`` findet dort nichts (verifiziert am
Andalusien-Druckbogen). Stattdessen werden Spalten über wiederkehrende
x-Startpositionen erkannt — genau das Merkmal, das eine Tabelle im Satz
ausmacht.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import fitz

# Word/Typst-Aufzählungszeichen inkl. der Private-Use-Glyphe aus SymbolMT.
# Der Halbgeviertstrich fehlt hier bewusst: als Markdown-Aufzaehlung
# tippt ihn niemand, und im Satz rutscht er durch den Umbruch
# regelmaessig an einen Zeilenanfang ("... nicht verlaesslich -
# Reserve mitbringen", S. 109 in einer Tabellenzelle geprueft).
_LISTENZEICHEN = {"", "•", "▪", "-", "*", "☐", "☑", "□", "»"}
_PUNKTFUEHRER = re.compile(r"\.{4,}\s*\d+\s*$", re.M)
# Beginnt die Zeile bereits mit einem Listenmarker, ist alles Weitere
# Listeninhalt -- inklusive Ankreuzkaestchen ("1. [ ] Vollmacht ...",
# S. 215 geprueft: sauber gesetzt) und Gedankenstrichen im Satz.
_ZEILE_IST_LISTE = re.compile(
    r"^\s*([-*+•☐☑□]|\d{1,3}[.)])\s*"
)
# Satzende, dann Strich, dann Text: ". - Pauschalreise:" -- das war im
# Markdown eine Liste, die mangels Leerzeile nicht erkannt wurde und nun
# mitten im Absatz steht. Ein Gedankenstrich ohne vorangehendes Satzende
# ("Mangel - unverzueglich melden") faellt bewusst nicht darunter.
# Nur der Bindestrich: ein Autor tippt als Aufzaehlung "-", niemals den
# typografischen Halbgeviertstrich "–". Der steht in "...ueber Dritte? –
# Fuer Lufttransporte..." voellig zu Recht (S. 191, geprueft).
_LISTE_IM_FLIESSTEXT = re.compile(r"[.:!?]\s+-\s+\S")


@dataclass(frozen=True)
class Ueberschrift:
    seite: int
    text: str
    groesse: float
    zeilen: int
    ebene: int | None = None


@dataclass(frozen=True)
class Tabelle:
    index: int
    seite_von: int
    seite_bis: int
    spaltenbreiten_pt: list[float]
    schriftgroesse_pt: float
    max_zeilen_je_zelle: int
    #: Median der gesetzten Zeilenbreite in der Tabellenregion. Das
    #: aussagekraeftigste Mass -- Fliesstext liegt bei rund 270 pt, eine
    #: brauchbare Tabelle bei 130, eine zerfaserte bei 39 (S. 6).
    median_zeilenbreite_pt: float = 0.0
    anteil_kurze_zeilen: float = 0.0


@dataclass(frozen=True)
class Listenzeile:
    seite: int
    zeichen: str
    abstand_vom_rand_pt: float
    am_zeilenanfang: bool
    kontext: str


@dataclass
class Dokument:
    pfad: str
    seiten: int
    breite_pt: float
    hoehe_pt: float
    ueberschriften: list[Ueberschrift] = field(default_factory=list)
    tabellen: list[Tabelle] = field(default_factory=list)
    listenzeilen: list[Listenzeile] = field(default_factory=list)
    ivz_seiten: int = 0
    ivz_eintraege: int = 0
    grundschrift_pt: float = 0.0


def _grundschrift(doc: fitz.Document) -> float:
    """Die Schriftgröße mit dem meisten Text ist der Fließtext."""
    zaehler: Counter = Counter()
    for seite in doc:
        for block in seite.get_text("dict")["blocks"]:
            for zeile in block.get("lines", []):
                for span in zeile.get("spans", []):
                    if span["text"].strip():
                        zaehler[round(span["size"], 1)] += len(span["text"])
    return zaehler.most_common(1)[0][0] if zaehler else 0.0


def _linker_satzrand(doc: fitz.Document, stichprobe: int = 40) -> float:
    """Linker Rand des Satzspiegels als häufigster Zeilenanfang."""
    zaehler: Counter = Counter()
    schritt = max(1, doc.page_count // stichprobe)
    for i in range(0, doc.page_count, schritt):
        for block in doc[i].get_text("dict")["blocks"]:
            for zeile in block.get("lines", []):
                zaehler[round(zeile["bbox"][0])] += 1
    return float(zaehler.most_common(1)[0][0]) if zaehler else 0.0


def _outline_ebenen(doc: fitz.Document) -> dict[str, int]:
    """Überschriftentext -> Ebene aus der PDF-Gliederung."""
    ebenen: dict[str, int] = {}
    for eintrag in doc.get_toc():
        ebene, titel = eintrag[0], eintrag[1]
        ebenen.setdefault(titel.strip()[:80], ebene)
    return ebenen


def _ivz_umfang(doc: fitz.Document, max_pruefen: int = 30) -> tuple[int, int]:
    """Gedrucktes Inhaltsverzeichnis über Punktführer-Zeilen erkennen."""
    seiten = 0
    eintraege = 0
    for i in range(min(max_pruefen, doc.page_count)):
        treffer = _PUNKTFUEHRER.findall(doc[i].get_text())
        if treffer:
            seiten += 1
            eintraege += len(treffer)
        elif seiten:
            break  # IVZ ist zu Ende
    return seiten, eintraege


def zaehle_visuelle_zeilen(oberkanten: list[float],
                           toleranz: float = 2.0) -> int:
    """Wie viele Zeilen sieht der Leser?

    PyMuPDF liefert jedes einzeln positionierte Wort als eigenes
    ``line``-Objekt. Im Blocksatz gesetzte Überschriften zerfallen dadurch in
    ein Objekt je Wort: Auf S. 295 des Andalusien-Buches meldete der Detektor
    sechs Zeilen für die zweizeilige Überschrift »1. Sofortmaßnahmen am Ort
    (erste 15 Minuten)«, weil deren Wortabstände auf das Vierfache gedehnt
    waren. Gezählt wird deshalb nach Oberkante -- was auf gleicher Höhe
    steht, ist eine Zeile.
    """
    gruppen: list[float] = []
    for y in sorted(oberkanten):
        if not gruppen or y - gruppen[-1] > toleranz:
            gruppen.append(y)
    return len(gruppen)


def _ueberschriften(doc: fitz.Document, grundschrift: float,
                    ebenen: dict[str, int],
                    ivz_bis_seite: int = 0) -> list[Ueberschrift]:
    """Blöcke, die größer als der Fließtext gesetzt sind, sind Überschriften.

    Die Seiten des gedruckten Inhaltsverzeichnisses werden übersprungen: Dort
    stehen dieselben Titel noch einmal, oft umbrochen -- als "Überschrift über
    drei Zeilen" gemeldet wären das reine Falschmeldungen. Das IVZ hat mit
    ``inhaltsverzeichnis_zu_lang`` seine eigene Regel.
    """
    out: list[Ueberschrift] = []
    for nr, seite in enumerate(doc, start=1):
        if nr <= ivz_bis_seite:
            continue
        for block in seite.get_text("dict")["blocks"]:
            zeilen = block.get("lines", [])
            if not zeilen:
                continue
            # NUR die einleitenden GROSSEN Zeilen sind die Ueberschrift.
            # Ein PDF-Block enthaelt oft Ueberschrift UND nachfolgenden
            # Fliesstext; wer den ganzen Block nimmt, misst Ueberschriften
            # von 200 Zeichen ("Kurzantwort Bei einer Pauschalreise ist der
            # Reiseveranstalter ...") und zaehlt deren Zeilen dem Titel zu.
            kopfzeilen = []
            for zeile in zeilen:
                zeilen_spans = [s for s in zeile.get("spans", []) if s["text"].strip()]
                if not zeilen_spans:
                    break
                if round(max(s["size"] for s in zeilen_spans), 1) <= grundschrift + 0.4:
                    break  # ab hier beginnt der Fliesstext
                kopfzeilen.append((round(zeile["bbox"][1], 1), zeilen_spans))
            if not kopfzeilen:
                continue
            spans = [s for _y, zs in kopfzeilen for s in zs]
            groesse = round(max(s["size"] for s in spans), 1)
            text = re.sub(r"\s+", " ", " ".join(s["text"] for s in spans)).strip()
            if not text:
                continue
            out.append(Ueberschrift(
                seite=nr, text=text, groesse=groesse,
                zeilen=zaehle_visuelle_zeilen([y for y, _zs in kopfzeilen]),
                ebene=ebenen.get(text[:80]),
            ))
    return out


def _satzbreite_linien(seite: fitz.Page, satzbreite: float) -> list[float]:
    """y-Positionen satzbreiter Waagerechten -- die Kopflinie jeder Tabelle.

    Typst setzt Buchtabellen ohne Rahmen, aber MIT einer Linie unter der
    Kopfzeile. ``find_tables()`` findet sie trotzdem nicht (weder mit
    ``strategy="lines"``, das 0 Tabellen meldet, noch sinnvoll mit
    ``strategy="text"``, das die ganze Seite zur Tabelle erklaert). Die
    Linie selbst ist dagegen ein eindeutiger, im PDF vorhandener Anker.

    Abgegrenzt gegen die zentrierten Prompt-Trenner, die nur rund die halbe
    Satzbreite messen.
    """
    out: list[float] = []
    for zeichnung in seite.get_drawings():
        rect = zeichnung["rect"]
        if abs(rect.height) < 2.5 and rect.width >= satzbreite * 0.8:
            out.append(float(rect.y0))
    return sorted(out)


def _tabellenregion(seite: fitz.Page, satzbreite: float,
                    luecke_pt: float = 26.0):
    """Zeilen einer Tabellenregion und ihre gesetzten Breiten.

    Zwei Sackgassen liegen hinter dieser Fassung, beide am Andalusien-Buch
    verifiziert:

    * Filter "kleiner als die Grundschrift" -- traf den Word-Satz (Tabellen
      8,5 pt), im Typst-Satz stehen Tabellen auf 11 pt. Meldete dort NULL
      Tabellen, obwohl S. 6 vierspaltig 41 pt ueberlief.
    * Spalten ueber x-Positionen clustern -- warf auf S. 28 nummerierte
      Liste, Aufzaehlung und echte Tabelle zusammen und meldete auf S. 6
      sechs statt vier Spalten.

    Deshalb wird die Spaltenzahl nur noch grob geschaetzt und NICHT bewertet.
    Bewertet wird die gesetzte Zeilenbreite: Fliesstext liegt bei rund
    270 pt, eine brauchbare Tabelle bei 130, eine zerfaserte bei 39.
    Das misst direkt, was stoert -- "die Spalte fasst kein Wort mehr".
    """
    linien = [
        float(z["rect"].y0) for z in seite.get_drawings()
        if abs(z["rect"].height) < 2.5 and z["rect"].width >= satzbreite * 0.8
    ]
    if not linien:
        return None

    zeilen = []
    for block in seite.get_text("dict")["blocks"]:
        for zeile in block.get("lines", []):
            spans = [s for s in zeile.get("spans", []) if s["text"].strip()]
            if spans:
                zeilen.append((zeile["bbox"][1], zeile["bbox"][0],
                               zeile["bbox"][2] - zeile["bbox"][0], spans))
    zeilen.sort()

    beste = None
    for linie_y in sorted(linien):
        region = []
        vorige_y = None
        for y, x0, breite, spans in zeilen:
            if y < linie_y - 30.0:
                continue
            if vorige_y is not None and y - vorige_y > luecke_pt:
                break
            region.append((x0, breite, spans))
            vorige_y = y
        if len(region) < 6:
            continue
        breiten = sorted(b for _, b, _ in region)
        median = breiten[len(breiten) // 2]
        kurz = sum(1 for b in breiten if b < 60.0) / len(breiten)
        alle = [s for _, _, spans in region for s in spans]
        groesse = round(Counter(s["size"] for s in alle).most_common(1)[0][0], 1)
        starts = sorted({round(x0 / 12) * 12 for x0, _, _ in region})
        if beste is None or median < beste[0]:
            beste = (float(median), groesse, float(kurz), len(starts), len(region))
    return beste


def _tabellen(doc: fitz.Document, grundschrift: float,
              satzbreite: float = 283.0) -> list[Tabelle]:
    """Tabellenseiten finden und ueber Seiten hinweg buendeln."""
    treffer = []
    for nr, seite in enumerate(doc, start=1):
        erg = _tabellenregion(seite, satzbreite)
        if erg:
            treffer.append((nr, *erg))

    out: list[Tabelle] = []
    idx = 0
    i = 0
    while i < len(treffer):
        nr, median, groesse, kurz, spalten, _zeilen = treffer[i]
        von = bis = nr
        j = i + 1
        # Folgeseiten mit aehnlich schmalem Satz gehoeren zur selben Tabelle
        while j < len(treffer) and treffer[j][0] == bis + 1:
            bis = treffer[j][0]
            median = min(median, treffer[j][1])
            kurz = max(kurz, treffer[j][3])
            j += 1
        idx += 1
        out.append(Tabelle(
            index=idx, seite_von=von, seite_bis=bis,
            spaltenbreiten_pt=[], schriftgroesse_pt=groesse,
            max_zeilen_je_zelle=0,
            median_zeilenbreite_pt=median,
            anteil_kurze_zeilen=kurz,
        ))
        i = j
    return out


def _listenzeilen(doc: fitz.Document, satzrand: float,
                  toleranz_pt: float = 3.0) -> list[Listenzeile]:
    """Aufzählungszeichen einsammeln und prüfen, ob sie die Zeile eröffnen."""
    out: list[Listenzeile] = []
    for nr, seite in enumerate(doc, start=1):
        for block in seite.get_text("dict")["blocks"]:
            for zeile in block.get("lines", []):
                spans = [s for s in zeile.get("spans", []) if s["text"].strip()]
                if not spans:
                    continue
                volltext = "".join(s["text"] for s in spans)
                if _ZEILE_IST_LISTE.match(volltext):
                    continue
                treffer_fliesstext = _LISTE_IM_FLIESSTEXT.search(volltext)
                if treffer_fliesstext:
                    out.append(Listenzeile(
                        seite=nr, zeichen="-",
                        abstand_vom_rand_pt=float(treffer_fliesstext.start()),
                        am_zeilenanfang=False,
                        kontext=re.sub(r"\s+", " ", volltext).strip(),
                    ))
                    continue
                # Eine Zeile, die NUR aus einem Strich besteht, ist ein
                # Platzhalter in einer Tabellenzelle ("kein Eintrag"), kein
                # verungluecktes Listenzeichen. (Falschmeldung an S. 809 der
                # Andalusien-Druckfahne, dort Spalte "Verfahrensfuehrende Stelle".)
                if volltext.strip() in {"-", "–", "—"}:
                    continue
                for pos, span in enumerate(spans):
                    zeichen = span["text"].strip()[:1]
                    if zeichen not in _LISTENZEICHEN:
                        continue
                    # Ein Gedankenstrich mitten im Satz ist kein Listenzeichen.
                    if zeichen in {"-", "–"} and pos > 0:
                        continue
                    abstand = span["bbox"][0] - satzrand
                    am_anfang = pos == 0 and abstand <= toleranz_pt + 24
                    out.append(Listenzeile(
                        seite=nr, zeichen=zeichen,
                        abstand_vom_rand_pt=abstand,
                        am_zeilenanfang=am_anfang,
                        kontext=re.sub(r"\s+", " ", volltext).strip(),
                    ))
                    break
    return out


def lade_dokument(pdf_pfad: str | Path) -> Dokument:
    """PDF öffnen und alle für die Regeln nötigen Messwerte erheben."""
    pfad = Path(pdf_pfad).expanduser().resolve()
    doc = fitz.open(pfad)
    try:
        grundschrift = _grundschrift(doc)
        satzrand = _linker_satzrand(doc)
        ebenen = _outline_ebenen(doc)
        ivz_seiten, ivz_eintraege = _ivz_umfang(doc)
        return Dokument(
            pfad=str(pfad),
            seiten=doc.page_count,
            breite_pt=doc[0].rect.width,
            hoehe_pt=doc[0].rect.height,
            grundschrift_pt=grundschrift,
            ueberschriften=_ueberschriften(
                doc, grundschrift, ebenen, ivz_bis_seite=ivz_seiten + 1,
            ),
            tabellen=_tabellen(doc, grundschrift),
            listenzeilen=_listenzeilen(doc, satzrand),
            ivz_seiten=ivz_seiten,
            ivz_eintraege=ivz_eintraege,
        )
    finally:
        doc.close()
