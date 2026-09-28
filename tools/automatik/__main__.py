"""Automatik (Book-Studio-Seite) von der Kommandozeile -- für GG als Unterprozess.

    # Was der Startdialog anbieten kann (Formatvorlagen, Skeleton-Profile)
    python -m tools.automatik optionen

    # Vorab-Prüfung des BS-Teils eines Profils; Exit 0 = keine Lücken
    python -m tools.automatik pruefe --profil production/runs/<uuid>/automatik.json

    # BS-Teil ausführen: Handoff → Übernahme → Studio-Kette → DOCX; Exit 0 = DOCX da
    python -m tools.automatik lauf --profil production/runs/<uuid>/automatik.json

    # Nacharbeit am Ende: Dialog (fehlende Ressourcen, Formate, Vorlagen, DOCX neu)
    python -m tools.automatik nacharbeit --profil production/runs/<uuid>/automatik.json
    # ... oder nur die offenen Punkte als JSON
    python -m tools.automatik nacharbeit --profil ... --json

    # Zeichengrenze fuer Verzeichniseintraege; mit --titel wird jeder Titel gemessen
    python -m tools.automatik ivz --doclayout Reisefuehrer_Andalusien --titel titel.json

Das Ergebnis ist immer ein JSON-Objekt auf stdout (UTF-8), damit GG es ohne
Textraten lesen kann. ``lauf`` schreibt seinen Verlauf zeilenweise nach
stderr (``[stufe] meldung``) -- GG nimmt ihn ins Automatik-Log auf.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path

from services.automatik import (
    AutomatikError,
    fuehre_bs_teil_aus,
    optionen,
    pruefe_bs,
    read_automatik,
)

#: Book-Studio-Wurzel (``python -m tools.automatik`` läuft von dort).
_WURZEL = Path(__file__).resolve().parent.parent.parent


#: Wohin das Ergebnis-JSON geht: das stdout beim Aufruf von :func:`main`.
#: Waehrend des Laufs zeigt ``sys.stdout`` auf stderr (siehe ``main``).
_KANAL = None


def _ausgeben(daten: dict) -> None:
    kanal = _KANAL or sys.stdout
    text = json.dumps(daten, ensure_ascii=False, indent=2) + "\n"
    kanal.buffer.write(text.encode("utf-8"))
    kanal.flush()


def _log(meldung: str, stufe: str = "info") -> None:
    sys.stderr.buffer.write(f"[{stufe}] {meldung}\n".encode())
    sys.stderr.flush()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m tools.automatik",
        description="Automatik GG-Batch → DOCX: Auswahllisten, Vorab-Prüfung und Lauf (BS-Teil).",
    )
    unter = p.add_subparsers(dest="befehl", required=True)
    unter.add_parser("optionen", help="Formatvorlagen und Skeleton-Profile als JSON")
    pruefe = unter.add_parser("pruefe", help="BS-Teil eines Automatik-Profils prüfen")
    pruefe.add_argument("--profil", required=True, help="Pfad zu automatik.json")
    lauf = unter.add_parser("lauf", help="Handoff ohne Oberfläche bis zur DOCX führen")
    lauf.add_argument("--profil", required=True, help="Pfad zu automatik.json")
    nach = unter.add_parser("nacharbeit", help="Offene Punkte nach dem Lauf (Dialog oder --json)")
    nach.add_argument("--profil", required=True, help="Pfad zu automatik.json")
    nach.add_argument("--json", action="store_true", help="Nur die offenen Punkte als JSON ausgeben")
    ivz = unter.add_parser(
        "ivz", help="Zeichengrenze fuer Verzeichniseintraege einer Formatvorlage (und zu lange Titel)"
    )
    ivz.add_argument("--doclayout", required=True, help="Name der Formatvorlage")
    ivz.add_argument(
        "--titel",
        default="",
        help='JSON-Datei mit [[ebene, "Titel"], ...] (oder "-" fuer stdin); gemessen wird jeder Titel',
    )
    return p


def _ivz(layout: str, titel_quelle: str) -> int:
    """``{layout, satzbreite_mm, zeichen, ebenen, zu_lang[]}`` -- gemessen mit der echten Schrift."""
    from tools.doclayout.ivz import grenzen, zu_lange_titel
    from tools.doclayout.library import load_layout
    from tools.doclayout.schema import LayoutError

    try:
        definition = load_layout(layout)
    except LayoutError as exc:
        _ausgeben({"fehler": str(exc)})
        return 1
    titel: list[tuple[int, str]] = []
    if titel_quelle:
        if titel_quelle == "-":
            roh = sys.stdin.buffer.read().decode("utf-8-sig")
        else:
            roh = Path(titel_quelle).read_text(encoding="utf-8-sig")
        titel = [(int(e), str(t)) for e, t in json.loads(roh or "[]")]
    _ausgeben({**grenzen(definition).als_dict(), "zu_lang": zu_lange_titel(definition, titel)})
    return 0


def _buch_und_docx(profil: dict, lauf_ordner: Path) -> tuple[Path | None, str]:
    """Buchordner aus ``band_run.json`` (BS-Zone), DOCX aus dem Ergebnis des Laufs."""
    from services.band_run import read_band_run

    docx = ""
    ergebnis = lauf_ordner / "automatik_ergebnis.json"
    try:
        daten = json.loads(ergebnis.read_text(encoding="utf-8"))
        docx = str(daten.get("docx") or "")
    except (OSError, ValueError):
        pass
    try:
        band = read_band_run(profil["production_uuid"], repo=_WURZEL) or {}
    except (OSError, ValueError):
        band = {}
    buch = str((band.get("paths") or {}).get("book") or "")
    return (Path(buch) if buch else None), docx


def _nacharbeit(profil: dict, profil_pfad: Path, *, nur_json: bool) -> int:
    from services.nacharbeit import offene_punkte
    from tools.skeleton.herkunft import bibliothek

    lauf_ordner = Path(profil_pfad).resolve().parent
    buch, docx = _buch_und_docx(profil, lauf_ordner)
    if buch is None or not buch.is_dir():
        _ausgeben({"fehler": "Kein Buchprojekt zu diesem Lauf (band_run.json ohne paths.book)."})
        return 1
    layout = str(profil["bs"]["doclayout"])
    skeleton = str(profil["bs"].get("skeleton_profil") or "")
    if nur_json:
        _ausgeben({"docx": docx, **offene_punkte(
            buch, layout_name=layout, library_root=bibliothek(_WURZEL), skeleton_profil=skeleton
        )})
        return 0
    from ui_qt.dialogs.automatik_nacharbeit_dialog import open_nacharbeit_dialog

    open_nacharbeit_dialog(
        book=buch, layout_name=layout, docx=docx, lauf_ordner=lauf_ordner,
        library_root=bibliothek(_WURZEL), skeleton_profil=skeleton,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """stdout gehoert allein dem Ergebnis-JSON -- GG liest es als Ganzes.

    Was eine Bibliothek unterwegs nach stdout schreibt (PyMuPDF meldet
    Fehler dort), ginge sonst in das JSON und GG laese „kein Ergebnis“ --
    gefunden am Ende-zu-Ende-Test nach dem Verzeichnis-Fuellen (2026-09-28).
    Waehrend des Laufs zeigt ``sys.stdout`` deshalb auf stderr (ins Log).
    """
    global _KANAL
    _KANAL = sys.stdout
    try:
        with contextlib.redirect_stdout(sys.stderr):
            return _main(argv)
    finally:
        _KANAL = None


def _main(argv: list[str] | None) -> int:
    args = build_parser().parse_args(argv)
    if args.befehl == "optionen":
        _ausgeben(optionen(_WURZEL))
        return 0
    if args.befehl == "ivz":
        return _ivz(args.doclayout, args.titel)
    try:
        profil = read_automatik(args.profil)
    except AutomatikError as exc:
        if args.befehl == "lauf":
            _ausgeben({"status": "abgebrochen", "meldung": str(exc), "warnungen": [], "stufen": []})
        else:
            _ausgeben({"luecken": [str(exc)], "warnungen": []})
        return 1
    if args.befehl == "nacharbeit":
        return _nacharbeit(profil, Path(args.profil), nur_json=args.json)
    if args.befehl == "lauf":
        ergebnis = fuehre_bs_teil_aus(profil, _WURZEL, log=_log)
        _ausgeben(ergebnis)
        return 0 if ergebnis["status"] == "ok" else 1
    ergebnis = pruefe_bs(profil, _WURZEL)
    _ausgeben(ergebnis)
    return 1 if ergebnis["luecken"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
