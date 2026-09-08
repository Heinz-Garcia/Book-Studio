"""Iterationsbericht — menschenlesbar und maschinenlesbar."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .schleife import Ergebnis

SCHEMA_VERSION = 1


def als_json(ergebnis: Ergebnis, buch: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "erzeugt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "buch": buch,
        "vorlage": str(ergebnis.vorlage) if ergebnis.vorlage else "",
        "iterationen_gesamt": len(ergebnis.iterationen),
        "beste_iteration": ergebnis.bester_index,
        "abbruchgrund": ergebnis.abbruchgrund,
        "ergebnis_groessen": {
            "ueberschriften_pt": dict(sorted(ergebnis.bester.groessen.ueberschriften.items())),
            "tabelle_pt": ergebnis.bester.groessen.tabelle,
        },
        "iterationen": [
            {
                "nummer": it.nummer,
                "ueberschriften_pt": dict(sorted(it.groessen.ueberschriften.items())),
                "tabelle_pt": it.groessen.tabelle,
                "befunde_gesamt": it.befunde_gesamt,
                "nach_regel": it.nach_regel,
                "seiten": it.seiten,
                "dauer_sek": round(it.dauer_sek, 1),
                "bemerkung": it.bemerkung,
            }
            for it in ergebnis.iterationen
        ],
    }


def als_markdown(ergebnis: Ergebnis, buch: str) -> str:
    z = [f"# Satz-Regelkreis — {buch}", ""]
    if not ergebnis.iterationen:
        return "\n".join(z + ["Keine Iteration gelaufen.", ""])

    erste, bester = ergebnis.iterationen[0], ergebnis.bester
    z += [
        f"**{len(ergebnis.iterationen)} Iterationen** · Abbruch: {ergebnis.abbruchgrund}",
        f"· beste war Nr. {bester.nummer}",
        "",
        f"Befunde: **{erste.befunde_gesamt} → {bester.befunde_gesamt}**",
        "",
        "| # | Überschriften | Tabelle | Befunde | Seiten | Dauer | Schritt |",
        "|---:|---|---|---:|---:|---:|---|",
    ]
    for it in ergebnis.iterationen:
        h = " / ".join(f"{pt:g}" for _, pt in sorted(it.groessen.ueberschriften.items())) or "—"
        t = f"{it.groessen.tabelle:g}" if it.groessen.tabelle is not None else "—"
        marke = " ⬅" if it.nummer == ergebnis.bester_index else ""
        befunde = it.befunde_gesamt if it.befunde_gesamt >= 0 else "Fehler"
        z.append(
            f"| {it.nummer}{marke} | {h} | {t} | {befunde} | {it.seiten} | "
            f"{it.dauer_sek:.0f}s | {it.bemerkung or '—'} |"
        )
    z += ["", "## Befunde je Regel", "", "| Regel | " +
          " | ".join(str(it.nummer) for it in ergebnis.iterationen) + " |",
          "|---|" + "---:|" * len(ergebnis.iterationen)]
    regeln = sorted({r for it in ergebnis.iterationen for r in it.nach_regel})
    for r in regeln:
        z.append(f"| `{r}` | " +
                 " | ".join(str(it.nach_regel.get(r, 0)) for it in ergebnis.iterationen) + " |")
    z += [
        "",
        "## Ergebnis",
        "",
        f"Formatvorlage: `{ergebnis.vorlage}`",
        "",
        "```",
        bester.groessen.als_text(),
        "```",
        "",
        "Die Vorlage trägt diesen Stand — nicht den der letzten Iteration.",
        "",
    ]
    return "\n".join(z)


def schreibe(ergebnis: Ergebnis, buch: str, ziel_ohne_endung: Path) -> tuple[Path, Path]:
    ziel_ohne_endung.parent.mkdir(parents=True, exist_ok=True)
    md = ziel_ohne_endung.with_suffix(".md")
    js = ziel_ohne_endung.with_suffix(".json")
    md.write_text(als_markdown(ergebnis, buch), encoding="utf-8")
    js.write_text(json.dumps(als_json(ergebnis, buch), indent=2, ensure_ascii=False),
                  encoding="utf-8")
    return md, js
