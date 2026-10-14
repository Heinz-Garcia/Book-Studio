"""Neue Stufen: welche GrammarGraph-Stufe hat in einer Formatvorlage noch kein Absatzformat?

Jede Stufe eines GrammarGraph-Projekts landet im Buch als Block
``::: {.<stufe>}``. Ohne Zuordnung in der Formatvorlage wird sie im Satz zu
Fließtext -- und das fiel bisher erst nach einem bezahlten Lauf auf, in der
Nacharbeit (Nutzer, 14.10.2026). Diese Prüfung braucht keinen Lauf: Sie liest
die Stufen aus dem Manifest des Projekts und hält sie gegen die ``classmap``.

Zugeordnet wird unter dem **Stufentyp** (``…_spanisch`` → ``spanisch``), wie in
der Nacharbeit -- dann gilt die Gestaltung für jedes Buch mit dieser Stufe.

Nur Logik, keine Oberfläche (``.doc/gui_architektur.md``); das Fenster liegt
in ``ui_qt/dialogs/doclayout_neue_stufen.py``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from pathlib import Path

from tools.doclayout.classmap import normalize_class, zuordnungs_schluessel
from tools.doclayout.schema import LayoutDefinition, ParagraphStyle
from tools.doclayout.usage import suggested_style_id

__all__ = [
    "Stufe",
    "beispiel_markdown",
    "beispieltext",
    "fehlende_stufen",
    "stufen_des_projekts",
    "vorschlag",
    "zuordnen",
]

#: So lang darf ein Beispieltext aus einem früheren Lauf höchstens werden --
#: genug für mehrere Zeilen, kurz genug für eine schnelle Vorschau.
BEISPIEL_ZEICHEN = 900


@dataclass(frozen=True)
class Stufe:
    """Eine Stufe so, wie sie im Buch ankommt."""

    stage_id: str
    anzeigename: str
    klasse: str  # Klassenname im Buch (``::: {.klasse}``)
    stufentyp: str  # Schlüssel für die dauerhafte Zuordnung
    pflicht: bool = False  # Haupttext des Kapitels (``is_mandatory``)


def _gemeinsamer_kopf(namen: list[str]) -> str:
    """Gemeinsamer Anfang bis einschließlich des letzten ``_`` -- sonst leer."""
    if len(namen) < 2:
        return ""
    kopf = os.path.commonprefix(namen)
    schnitt = kopf.rfind("_")
    return kopf[: schnitt + 1] if schnitt > 0 else ""


def stufen_des_projekts(manifest: Path | str) -> list[Stufe]:
    """Die Stufen, die ins Buch gehen -- in Manifest-Reihenfolge.

    Planungsstufen (``plans_prompts``) erzeugen keinen Buchtext und fehlen.
    Der Stufentyp ist die Klasse ohne den Teil, den alle Stufen gemeinsam
    vorne tragen (meist der Projektname). So stimmt er auch dann, wenn das
    Projekt später umbenannt wurde (``…_v_2_Band1`` mit Stufen ``…_v_2_…``).
    """
    daten = json.loads(Path(manifest).read_text(encoding="utf-8"))
    roh = daten.get("stages") if isinstance(daten, dict) else None
    if not isinstance(roh, list):
        return []
    eintraege: list[tuple[str, str, str, bool]] = []
    for s in sorted(
        (s for s in roh if isinstance(s, dict)), key=lambda s: s.get("order", 0) or 0
    ):
        if s.get("plans_prompts"):
            continue
        sid = str(s.get("stage_id") or s.get("id") or "").strip()
        if not sid:
            continue
        ausgabe = s.get("output") if isinstance(s.get("output"), dict) else {}
        tags = ausgabe.get("wrap_tags") if isinstance(ausgabe.get("wrap_tags"), dict) else {}
        tag = next((str(t.get("tag")) for t in tags.values() if isinstance(t, dict) and t.get("tag")), "")
        klasse = normalize_class(tag or sid)
        eintraege.append((sid, str(s.get("display_name") or sid), klasse, s.get("is_mandatory") is True))
    # Der gemeinsame Kopf kommt aus den Stufen-IDs, nicht aus den Klassen: Eine
    # Stufe mit eigenem Klassennamen (``key-takeaway``) hätte ihn sonst gekappt.
    kopf = _gemeinsamer_kopf([normalize_class(sid) for sid, _name, _k, _p in eintraege])
    return [
        Stufe(
            sid, name, klasse,
            klasse[len(kopf):] if kopf and klasse.startswith(kopf) else klasse,
            pflicht,
        )
        for sid, name, klasse, pflicht in eintraege
    ]


def fehlende_stufen(definition: LayoutDefinition, stufen: list[Stufe]) -> list[Stufe]:
    """Stufen ohne Absatzformat in *definition* (genau, über Stufentyp oder Endstück)."""
    bekannt = set(definition.classmap)
    return [
        s for s in stufen
        if zuordnungs_schluessel(bekannt, s.klasse) is None and s.stufentyp not in bekannt
    ]


def vorschlag(definition: LayoutDefinition, stufe: Stufe) -> tuple[str, bool]:
    """``(Absatzformat, gibt_es_schon)`` als Vorbelegung für die Auswahl.

    Der Haupttext eines Kapitels ist Fließtext -- dafür gibt es schon ein
    Format. Jede andere Stufe (Kasten, Merksatz …) bekommt ein eigenes, nach
    ihr benanntes Format; gibt es das schon, wird es wiederverwendet.
    """
    if stufe.pflicht and "BodyText" in definition.styles:
        return "BodyText", True
    eigener = "".join(t[:1].upper() + t[1:] for t in stufe.stufentyp.replace("-", "_").split("_") if t)
    if eigener in definition.styles:
        return eigener, True
    style_id = suggested_style_id(stufe.stufentyp, definition.styles)
    return style_id, style_id in definition.styles


def zuordnen(
    definition: LayoutDefinition,
    stufe: Stufe,
    style_id: str,
    *,
    basis: str = "BodyText",
) -> LayoutDefinition:
    """Stufentyp → *style_id*; fehlt das Format, wird es leer angelegt (auf *basis*)."""
    if style_id not in definition.styles:
        definition = definition.with_style(
            ParagraphStyle(style_id=style_id, name=style_id, based_on=basis)
        )
    return replace(definition, classmap={**definition.classmap, stufe.stufentyp: style_id})


def beispieltext(stufe: Stufe, gg_output: Path | str | None) -> tuple[str, str]:
    """``(Text, Herkunft)`` für die Vorschau -- aus dem jüngsten Lauf, sonst ein Platzhalter.

    Gesucht wird ``<output>/*/P_*/P_*_<stage_id>.md`` (die Stufendatei eines
    GrammarGraph-Laufs). Der Text wird nicht verändert, nur gekürzt.
    """
    if gg_output is not None and Path(gg_output).is_dir():
        kandidaten = sorted(
            Path(gg_output).glob(f"*/P_*/P_*_{stufe.stage_id}.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for datei in kandidaten[:5]:
            try:
                text = datei.read_text(encoding="utf-8").strip()
            except (OSError, UnicodeDecodeError):
                continue
            if text:
                if len(text) > BEISPIEL_ZEICHEN:
                    text = text[:BEISPIEL_ZEICHEN].rsplit("\n", 1)[0].rstrip() + "\n\n…"
                return text, f"aus {datei.parent.parent.name}/{datei.parent.name}"
    platzhalter = (
        f"Beispiel für »{stufe.anzeigename}«. Diese Stufe ist noch nie gelaufen; "
        "der Satz zeigt nur, wie ein Absatz in diesem Format umbricht, wie groß "
        "die Schrift ist und welche Abstände er hat."
    )
    return platzhalter, "Platzhalter (noch kein Lauf dieser Stufe)"


def beispiel_markdown(
    definition: LayoutDefinition, stufen_mit_text: list[tuple[Stufe, str]]
) -> str:
    """Musterinhalt für die Vorschau: Fließtext als Maßstab, dann jede Stufe im eigenen Block."""
    zeilen = [
        "---",
        'title: "Neue Stufen"',
        f'subtitle: "{definition.label or definition.name}"',
        "---",
        "",
        "# Neue Stufen",
        "",
        (
            "Normaler Fließtext als Maßstab: So sieht der Text drumherum aus. Die "
            "Blöcke darunter zeigen jede neue Stufe in ihrem Absatzformat."
        ),
        "",
    ]
    for stufe, text in stufen_mit_text:
        zeilen += [f"## {stufe.anzeigename}", "", f"::: {{.{stufe.stufentyp}}}", text, ":::", ""]
    return "\n".join(zeilen)
