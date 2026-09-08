"""Satzprüfung: reine Regellogik über bereits extrahierte Seitendaten.

Bewusst frei von PyMuPDF und Dateizugriff — damit jede Regel ohne PDF
testbar ist. Das Auslesen des PDF steckt in ``extract.py``, die Ausgabe in
``report.py``.

Schwellen stammen aus dem Satzspiegel des Projekts, nicht aus dem Bauch:
57 Zeichen je Zeile bei 33 Zeilen je Seite ist die Vorgabe, gegen die die
Texte geschrieben werden. Eine Spalte, die keine 12 Zeichen trägt, kann
kein Wort mehr aufnehmen und zerlegt jeden Eintrag in Fragmente.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Literal

from .konfiguration import lies_werte

Schwere = Literal["hoch", "mittel", "niedrig"]


@dataclass(frozen=True)
class Befund:
    """Ein einzelner Satzmangel, maschinenlesbar und stabil adressierbar."""

    regel: str
    schwere: Schwere
    seite: int              # 1-basiert, wie im PDF-Betrachter
    titel: str              # kurze, menschenlesbare Zusammenfassung
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def kennung(self) -> str:
        """Stabile Adresse für spätere Autokorrektur (Regel + Ort)."""
        anker = str(self.details.get("anker", "")).strip()
        return f"{self.regel}:{self.seite}:{anker}" if anker else f"{self.regel}:{self.seite}"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["kennung"] = self.kennung
        return data


# ── Schwellenwerte ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class Schwellen:
    """Alles, was eine Regel auslöst — an einer Stelle, damit ein späterer
    Autokorrektur-Lauf dieselben Werte benutzt wie der Bericht.

    Die Werte stehen in ``schwellen.toml`` neben diesem Modul, nicht hier:
    Ab wann eine Überschrift zu lang ist, ist eine Setzerentscheidung.
    Deshalb tragen die Felder bewusst keine Vorgabewerte -- sonst gäbe es
    die Zahlen zweimal, und die im Code gewönne im Zweifel.
    """

    ueberschrift_max_zeilen: int
    spalte_min_zeichen: int
    tabelle_max_seiten: int
    ivz_max_seiten: int
    zelle_max_zeilen: int
    groessen_toleranz_pt: float


#: Mitgelieferte Schwellwerte. Ein Lauf kann eine andere Datei bekommen.
STANDARD_DATEI = Path(__file__).with_name("schwellen.toml")

_FELDER: dict[str, type] = {
    "ueberschrift_max_zeilen": int,
    "spalte_min_zeichen": int,
    "tabelle_max_seiten": int,
    "ivz_max_seiten": int,
    "zelle_max_zeilen": int,
    "groessen_toleranz_pt": float,
}


def lade_schwellen(datei: Path | None = None) -> Schwellen:
    """Schwellwerte aus TOML lesen (Voreinstellung: ``schwellen.toml``)."""
    return Schwellen(**lies_werte(datei or STANDARD_DATEI, _FELDER))


STANDARD = lade_schwellen()


def zeichen_pro_punkt(schriftgroesse_pt: float) -> float:
    """Grobe Zeichenbreite einer Serifenschrift: rund 0,48 × Schriftgröße.

    Reicht für die Frage "passt hier überhaupt ein Wort hinein" — für den
    exakten Umbruch wäre die Schriftmetrik nötig, die aber nichts an der
    Aussage ändert: 70 pt bei 8,5 pt Schrift sind rund 17 Zeichen.
    """
    return max(1.0, schriftgroesse_pt * 0.48)


# ── Regeln ──────────────────────────────────────────────────────────────

def pruefe_ueberschrift_zeilen(ueberschriften, s: Schwellen = STANDARD) -> list[Befund]:
    """Überschriften, die über mehrere Zeilen laufen, weil die Schrift zu groß ist."""
    out: list[Befund] = []
    for u in ueberschriften:
        if u.zeilen > s.ueberschrift_max_zeilen:
            out.append(Befund(
                regel="ueberschrift_zu_lang",
                schwere="mittel" if u.zeilen == s.ueberschrift_max_zeilen + 1 else "hoch",
                seite=u.seite,
                titel=f"Überschrift läuft über {u.zeilen} Zeilen: „{u.text[:60]}“",
                details={
                    "anker": u.text[:40], "zeilen": u.zeilen,
                    "schriftgroesse_pt": u.groesse, "ebene": u.ebene,
                    "vorschlag": "Schriftgröße dieser Ebene senken oder Überschrift kürzen",
                },
            ))
    return out


def pruefe_ueberschrift_hierarchie(ueberschriften, s: Schwellen = STANDARD) -> list[Befund]:
    """Ebene N darf nicht prominenter gesetzt sein als Ebene N-1.

    Verglichen wird die je Ebene *typische* (häufigste) Schriftgröße, nicht
    einzelne Vorkommen — sonst meldet jede Ausnahme einen Fehler.
    """
    nach_ebene: dict[int, list[float]] = {}
    beispiel: dict[int, Any] = {}
    for u in ueberschriften:
        if u.ebene:
            nach_ebene.setdefault(u.ebene, []).append(u.groesse)
            beispiel.setdefault(u.ebene, u)
    typisch = {
        lvl: max(set(gr), key=gr.count) for lvl, gr in nach_ebene.items()
    }
    out: list[Befund] = []
    for lvl in sorted(typisch):
        eltern = lvl - 1
        if eltern not in typisch:
            continue
        if typisch[lvl] > typisch[eltern] + s.groessen_toleranz_pt:
            u = beispiel[lvl]
            out.append(Befund(
                regel="ueberschrift_hierarchie_invertiert",
                schwere="hoch",
                seite=u.seite,
                titel=(f"Ebene {lvl} ist größer gesetzt ({typisch[lvl]:.1f} pt) "
                       f"als Ebene {eltern} ({typisch[eltern]:.1f} pt)"),
                details={
                    "anker": f"ebene{lvl}", "ebene": lvl, "ebene_eltern": eltern,
                    "groesse_pt": typisch[lvl], "groesse_eltern_pt": typisch[eltern],
                    "vorschlag": f"Schriftgröße Ebene {lvl} unter {typisch[eltern]:.1f} pt setzen",
                },
            ))
    return out


def pruefe_tabellen(tabellen, s: Schwellen = STANDARD) -> list[Befund]:
    """Zu schmal gesetzte und ueber zu viele Seiten laufende Tabellen.

    Bewertet wird die MEDIAN-ZEILENBREITE, nicht die Spaltenzahl: Am
    Andalusien-Buch gemessen liegt Fliesstext bei rund 270 pt, eine
    brauchbare Tabelle bei 130 und eine zerfaserte bei 39 (S. 6, wo
    "Universitario" zu "Universi-tario" bricht). Die Spaltensegmentierung
    war dagegen unzuverlaessig -- sie meldete auf S. 6 sechs statt vier
    Spalten -- und wird deshalb nicht mehr bewertet.
    """
    out: list[Befund] = []
    for t in tabellen:
        min_breite = s.spalte_min_zeichen * zeichen_pro_punkt(t.schriftgroesse_pt)
        if 0 < t.median_zeilenbreite_pt < min_breite:
            zeichen = t.median_zeilenbreite_pt / zeichen_pro_punkt(t.schriftgroesse_pt)
            out.append(Befund(
                regel="tabelle_zu_schmal",
                schwere="hoch" if zeichen < 8 else "mittel",
                seite=t.seite_von,
                titel=(f"Tabelle im Mittel nur {t.median_zeilenbreite_pt:.0f} pt breit "
                       f"gesetzt (rund {zeichen:.0f} Zeichen) — die Eintraege "
                       f"zerfallen in Silben"),
                details={
                    "anker": f"tab{t.index}",
                    "median_zeilenbreite_pt": round(t.median_zeilenbreite_pt, 1),
                    "zeichen_geschaetzt": round(zeichen),
                    "anteil_kurze_zeilen": round(t.anteil_kurze_zeilen, 2),
                    "schriftgroesse_pt": t.schriftgroesse_pt,
                    "vorschlag": ("Spaltenzahl reduzieren, Tabellenschrift verkleinern "
                                  "oder in eine Definitionsliste wandeln"),
                },
            ))
        seiten = t.seite_bis - t.seite_von + 1
        if seiten > s.tabelle_max_seiten:
            out.append(Befund(
                regel="tabelle_zu_lang",
                schwere="mittel",
                seite=t.seite_von,
                titel=f"Tabelle laeuft ueber {seiten} Seiten (S. {t.seite_von}–{t.seite_bis})",
                details={
                    "anker": f"tab{t.index}", "seiten": seiten,
                    "seite_von": t.seite_von, "seite_bis": t.seite_bis,
                    "vorschlag": "In mehrere Tabellen mit eigener Zwischenueberschrift teilen",
                },
            ))
    return out


def pruefe_listen(listenzeilen, s: Schwellen = STANDARD) -> list[Befund]:
    """Aufzählungs- oder Checkbox-Zeichen, die nicht am Zeilenanfang stehen.

    Typischer Satzfehler: Das Markup wurde nicht als Liste erkannt, das
    Zeichen landet mitten im Fließtext.
    """
    out: list[Befund] = []
    for z in listenzeilen:
        if not z.am_zeilenanfang:
            out.append(Befund(
                regel="listenzeichen_mitten_im_satz",
                schwere="hoch",
                seite=z.seite,
                titel=f"Aufzählungszeichen steht mitten in der Zeile: „{z.kontext[:60]}“",
                details={
                    "anker": z.kontext[:40], "zeichen": z.zeichen,
                    "abstand_vom_rand_pt": round(z.abstand_vom_rand_pt, 1),
                    "vorschlag": "Leerzeile vor der Liste im Markdown ergänzen",
                },
            ))
    return out


def pruefe_inhaltsverzeichnis(ivz_seiten: int, eintraege: int,
                              s: Schwellen = STANDARD) -> list[Befund]:
    """Ein IVZ über viele Seiten heißt meist: zu viele Ebenen aufgenommen."""
    if ivz_seiten <= s.ivz_max_seiten:
        return []
    return [Befund(
        regel="inhaltsverzeichnis_zu_lang",
        schwere="mittel",
        seite=1,
        titel=f"Inhaltsverzeichnis umfasst {ivz_seiten} Seiten ({eintraege} Einträge)",
        details={
            "anker": "ivz", "seiten": ivz_seiten, "eintraege": eintraege,
            "vorschlag": ("toc-depth senken, damit Fragen und Zwischenüberschriften "
                          "nicht im Verzeichnis landen"),
        },
    )]


def alle_regeln(daten, s: Schwellen = STANDARD) -> list[Befund]:
    """Alle Regeln auf ein extrahiertes Dokument anwenden."""
    befunde: list[Befund] = []
    befunde += pruefe_ueberschrift_zeilen(daten.ueberschriften, s)
    befunde += pruefe_ueberschrift_hierarchie(daten.ueberschriften, s)
    befunde += pruefe_tabellen(daten.tabellen, s)
    befunde += pruefe_listen(daten.listenzeilen, s)
    befunde += pruefe_inhaltsverzeichnis(daten.ivz_seiten, daten.ivz_eintraege, s)
    rang = {"hoch": 0, "mittel": 1, "niedrig": 2}
    befunde.sort(key=lambda b: (rang[b.schwere], b.seite))
    return befunde
