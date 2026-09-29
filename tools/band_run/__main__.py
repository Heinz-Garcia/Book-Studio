"""Band-Lauf-Objekt von der Kommandozeile -- für GG als Unterprozess.

    # GG meldet seinen Stand (JSON auf stdin)
    echo {"stage": "C", "detail": "Lauf läuft", "gates": {...}} | python -m tools.band_run gg --uuid <uuid>

Eingabe (stdin, UTF-8): ``stage`` (A–F), ``detail``, optional ``artifacts``
(dict), ``gates`` (nur A–F), ``paths`` (nur ``gg_project``/``delivery``).
Geschrieben wird mit ``writer="gg"`` -- die Zonen- und Lock-Regeln von
``services.band_run.update_band_run`` gelten unverändert. Ausgabe: JSON
``{"ok": true}`` oder ``{"ok": false, "fehler": "…"}``; Exit 0 / 1.

    # GG legt nach der Lieferung den Handoff an (JSON auf stdin)
    echo {"delivery_path": "…", "gg_project": "…", "project_slug": "…", "detail": "…"} | python -m tools.band_run handoff --uuid <uuid>

Eine Schreiblogik für den Handoff: ``services.handoff.write_pending_handoff``
(Lock, ``band_run``, Marker -- in dieser Reihenfolge). Vorher schrieb GG den
Marker mit einer Schema-Kopie selbst, ohne Lock und ohne Lauf-Objekt
(Prüfbericht 2026-09-29). Ausgabe: ``{"ok": true, "handoff": {…}}``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from services.band_run import BandRunError, update_band_run

#: Book-Studio-Wurzel (``python -m tools.band_run`` läuft von dort).
_WURZEL = Path(__file__).resolve().parent.parent.parent

_GG_STUFEN = frozenset("ABCDEF")


def _ausgeben(daten: dict) -> None:
    sys.stdout.buffer.write((json.dumps(daten, ensure_ascii=False) + "\n").encode("utf-8"))
    sys.stdout.flush()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m tools.band_run", description="Band-Lauf-Objekt schreiben.")
    unter = p.add_subparsers(dest="befehl", required=True)
    gg = unter.add_parser("gg", help="GG-Zone, GG-Gates (A–F) und GG-Pfade schreiben (JSON auf stdin)")
    gg.add_argument("--uuid", required=True, help="Production-UUID")
    ho = unter.add_parser("handoff", help="Pending-Handoff nach einer GG-Lieferung anlegen (JSON auf stdin)")
    ho.add_argument("--uuid", required=True, help="Production-UUID")
    return p


def schreibe_handoff(uuid: str, eingabe: dict, *, repo: Path = _WURZEL) -> dict:
    """GG-Handoff über die BS-SSOT; Rückgabe ``{"ok": …, "handoff"?|"fehler"?}``."""
    from services.handoff import DEFAULT_TIMEOUT_HOURS, HandoffError, write_pending_handoff

    lieferung = str(eingabe.get("delivery_path") or "").strip()
    if not lieferung:
        return {"ok": False, "fehler": "delivery_path fehlt."}
    try:
        stunden = float(eingabe.get("timeout_hours") or DEFAULT_TIMEOUT_HOURS)
        daten = write_pending_handoff(
            uuid,
            delivery_path=Path(lieferung),
            repo=repo,
            gg_project=str(eingabe.get("gg_project") or "") or None,
            project_slug=str(eingabe.get("project_slug") or ""),
            created_by="gg",
            timeout_hours=stunden,
            detail=str(eingabe.get("detail") or ""),
        )
    except (HandoffError, BandRunError, OSError, TypeError, ValueError) as exc:
        return {"ok": False, "fehler": str(exc)}
    from services.handoff import handoff_path

    return {"ok": True, "handoff": daten, "pfad": str(handoff_path(uuid, repo=repo))}


def schreibe_gg(uuid: str, eingabe: dict, *, repo: Path = _WURZEL) -> dict:
    """GG-Stand übernehmen; Rückgabe ``{"ok": …, "fehler"?: …}``."""
    stufe = str(eingabe.get("stage") or "").strip().upper()
    if stufe not in _GG_STUFEN:
        return {"ok": False, "fehler": f"stage {stufe!r} ist keine GG-Stufe (A–F)."}
    zone: dict = {"stage": stufe, "detail": str(eingabe.get("detail") or "")}
    if isinstance(eingabe.get("artifacts"), dict):
        zone["artifacts"] = eingabe["artifacts"]
    gates = eingabe.get("gates") if isinstance(eingabe.get("gates"), dict) else None
    pfade = eingabe.get("paths") if isinstance(eingabe.get("paths"), dict) else None
    try:
        update_band_run(
            uuid,
            writer="gg",
            repo=repo,
            zone_gg=zone,
            gates_patch=gates or None,
            paths_patch=pfade or None,
            current_stage=stufe,
        )
    except (BandRunError, OSError) as exc:
        return {"ok": False, "fehler": str(exc)}
    return {"ok": True}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        eingabe = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _ausgeben({"ok": False, "fehler": f"Eingabe kein JSON: {exc}"})
        return 1
    if not isinstance(eingabe, dict):
        _ausgeben({"ok": False, "fehler": "Eingabe muss ein JSON-Objekt sein."})
        return 1
    if args.befehl == "handoff":
        ergebnis = schreibe_handoff(args.uuid, eingabe)
    else:
        ergebnis = schreibe_gg(args.uuid, eingabe)
    _ausgeben(ergebnis)
    return 0 if ergebnis["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
