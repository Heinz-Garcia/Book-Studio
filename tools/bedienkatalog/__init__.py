"""Bedienkatalog: was Claude in Book Studio und GrammarGraph gefahrlos auslösen kann.

Erzeugt aus den Apps selbst, damit er nicht veraltet und keine zweite Ablage
neben dem Code entsteht (Nutzer, 14.10.2026, „Vibe Operating“):

* **Kommandozeilen** -- jede ``__main__.py`` unter ``tools/``; Beschreibung
  und Unterbefehle liest der Generator aus dem Code (AST, ohne Import).
* **Erklärte Funktionen** -- ein ``BEDIENUNG``-Literal (dict oder Liste von
  dicts) auf Modulebene, direkt neben der Funktion. Felder: ``vorgang``,
  ``aufruf``, ``bereich``, ``kostet``, ``aendert``, ``hinweis``. In einer
  ``__main__.py`` ergänzt es die Kommandozeile um diese Angaben.
* **Fensterwerkzeuge** -- GrammarGraph ``tools/*/.tool.json``, Book Studio
  ``plugins/*/plugin.json``.
* **Tests** -- ein Eintrag ist 🟢, wenn mindestens eine Testdatei sein Modul
  anspricht; sonst ⚪ (ungetestet).

Was nicht im Katalog steht, ist 🔴 -- nur von Hand.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

__all__ = ["Eintrag", "Fenster", "erzeuge_katalog", "sammle"]

#: Ordner ohne App-Code (Daten, Umgebungen, Ausgaben).
_AUSLASSEN = frozenset({
    ".git", ".venv", "venv", "__pycache__", "node_modules", "tests", "output", "projects",
    "production", "_trash", "scratchpad_test_out", "build", "dist", "export", "processed",
    "logs", "input", "mock_Input", "Publish", "pipelines", "profiles", "res", "resources",
    "templates", "shared", "agent-tools", "com",
})


@dataclass
class Eintrag:
    app: str
    vorgang: str
    aufruf: str
    modul: str
    bereich: str = "Kommandozeilen"
    kostet: bool = False
    aendert: bool = False
    hinweis: str = ""
    unterbefehle: list[tuple[str, str]] = field(default_factory=list)
    tests: int = 0


@dataclass
class Fenster:
    app: str
    name: str
    beschreibung: str
    paket: str


# ── Code lesen (AST, nichts wird importiert) ──────────────────────

def _python_dateien(wurzel: Path) -> list[Path]:
    dateien: list[Path] = []
    for pfad in wurzel.rglob("*.py"):
        teile = pfad.relative_to(wurzel).parts
        if any(t in _AUSLASSEN or t.startswith(("_Probe_", ".")) for t in teile[:-1]):
            continue
        dateien.append(pfad)
    return sorted(dateien)


def _baum(pfad: Path) -> ast.Module | None:
    try:
        return ast.parse(pfad.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
        return None


def _modulname(wurzel: Path, pfad: Path) -> str:
    rel = pfad.relative_to(wurzel).with_suffix("")
    teile = list(rel.parts)
    if teile[-1] in ("__main__", "__init__"):
        teile = teile[:-1]
    return ".".join(teile)


def _bedienung(baum: ast.Module) -> list[dict[str, Any]]:
    for knoten in baum.body:
        if isinstance(knoten, ast.Assign) and any(
            isinstance(z, ast.Name) and z.id == "BEDIENUNG" for z in knoten.targets
        ):
            try:
                wert = ast.literal_eval(knoten.value)
            except ValueError:
                return []
            liste = wert if isinstance(wert, list) else [wert]
            return [w for w in liste if isinstance(w, dict)]
    return []


def _erste_zeile(text: str | None) -> str:
    for zeile in (text or "").strip().splitlines():
        if zeile.strip():
            return zeile.strip().rstrip(".")
    return ""


def _klartext(text: str | None) -> str:
    """Erste Zeile, die beschreibt -- keine Aufrufzeile wie ``CLI: python -m …``."""
    for zeile in (text or "").strip().splitlines():
        z = zeile.strip()
        if not z or z.startswith(("``", "CLI", "Usage", "usage", "python ", "Aufruf")) or "python -m" in z:
            continue
        # Nur der erste Satz -- der Katalog ist eine Übersicht, keine Doku.
        satz = re.split(r"(?<=[a-zäöüß)])\.\s|:\s", z, maxsplit=1)[0]
        return satz.rstrip(".:")
    return ""


def _cli_infos(baum: ast.Module, paket_doc: str = "") -> tuple[str, list[tuple[str, str]]]:
    """(Beschreibung, [(Unterbefehl, Hilfe)]) aus argparse-Aufrufen und Docstrings."""
    beschreibung = _klartext(ast.get_docstring(baum)) or _klartext(paket_doc)
    unter: list[tuple[str, str]] = []
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.Call) or not isinstance(knoten.func, ast.Attribute):
            continue
        name = knoten.func.attr
        schluessel = {k.arg: k.value for k in knoten.keywords if k.arg}
        if name == "ArgumentParser":
            d = schluessel.get("description")
            if isinstance(d, ast.Constant) and isinstance(d.value, str) and _klartext(d.value):
                beschreibung = _klartext(d.value)
        elif name == "add_parser" and knoten.args and isinstance(knoten.args[0], ast.Constant):
            h = schluessel.get("help")
            hilfe = h.value if isinstance(h, ast.Constant) and isinstance(h.value, str) else ""
            unter.append((str(knoten.args[0].value), _erste_zeile(hilfe)))
    return beschreibung, unter


# ── Tests ─────────────────────────────────────────────────────────

def _testtexte(wurzel: Path) -> list[str]:
    texte = []
    for pfad in sorted((wurzel / "tests").rglob("*.py")) if (wurzel / "tests").is_dir() else []:
        try:
            texte.append(pfad.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return texte


def _testzahl(modul: str, testtexte: list[str]) -> int:
    """Testdateien, die *modul* ansprechen (Import in jeder üblichen Form oder Pfad)."""
    if not modul:
        return 0
    paket, _, letzter = modul.rpartition(".")
    muster = [
        re.compile(rf"\b(?:from|import)\s+{re.escape(modul)}\b"),
        re.compile(re.escape(modul.replace(".", "/"))),
    ]
    if paket:
        muster.append(re.compile(rf"\bfrom\s+{re.escape(paket)}\s+import\s+[^\n]*\b{re.escape(letzter)}\b"))
    return sum(1 for t in testtexte if any(m.search(t) for m in muster))


# ── Sammeln ───────────────────────────────────────────────────────

def _eintrag_aus(app: str, modul: str, angabe: dict[str, Any], vorlage: Eintrag | None = None) -> Eintrag:
    e = vorlage or Eintrag(app=app, vorgang="", aufruf="", modul=modul)
    e.vorgang = str(angabe.get("vorgang") or e.vorgang)
    e.aufruf = str(angabe.get("aufruf") or e.aufruf)
    e.bereich = str(angabe.get("bereich") or e.bereich)
    e.kostet = bool(angabe.get("kostet", e.kostet))
    e.aendert = bool(angabe.get("aendert", e.aendert))
    e.hinweis = str(angabe.get("hinweis") or e.hinweis)
    return e


def sammle(app: str, wurzel: Path) -> tuple[list[Eintrag], list[Fenster]]:
    """Alle Einträge und Fensterwerkzeuge einer App."""
    wurzel = Path(wurzel)
    testtexte = _testtexte(wurzel)
    eintraege: list[Eintrag] = []
    cli_pakete: set[str] = set()
    for pfad in _python_dateien(wurzel):
        baum = _baum(pfad)
        if baum is None:
            continue
        modul = _modulname(wurzel, pfad)
        angaben = _bedienung(baum)
        if pfad.name == "__main__.py" and modul.startswith("tools."):
            init = _baum(pfad.with_name("__init__.py")) if pfad.with_name("__init__.py").is_file() else None
            beschreibung, unter = _cli_infos(baum, ast.get_docstring(init) or "" if init else "")
            e = Eintrag(app=app, vorgang=beschreibung or modul, aufruf=f"python -m {modul}",
                        modul=modul, unterbefehle=unter)
            for angabe in angaben[:1]:
                _eintrag_aus(app, modul, angabe, e)
            eintraege.append(e)
            cli_pakete.add(modul.split(".")[1])
            angaben = angaben[1:]
        for angabe in angaben:
            eintraege.append(_eintrag_aus(app, modul, angabe))
    for e in eintraege:
        # Ein Paket-CLI (``tools.x``) zählt Tests auf alle seine Module.
        e.tests = _testzahl(e.modul, testtexte)
    return eintraege, _fenster(app, wurzel, cli_pakete)


def _fenster(app: str, wurzel: Path, cli_pakete: set[str]) -> list[Fenster]:
    fenster: list[Fenster] = []
    quellen = [(p, "name", "description") for p in sorted((wurzel / "tools").glob("*/.tool.json"))]
    quellen += [(p, "label", "description") for p in sorted((wurzel / "plugins").glob("*/plugin.json"))]
    for pfad, name_feld, text_feld in quellen:
        paket = pfad.parent.name
        if paket in cli_pakete:
            continue  # gibt es auch als Kommandozeile -- steht dort
        try:
            daten = json.loads(pfad.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(daten, dict):
            continue
        name = str(daten.get(name_feld) or daten.get("name") or paket).strip(" …").strip()
        fenster.append(Fenster(app, name, str(daten.get(text_feld) or ""), paket))
    return sorted(fenster, key=lambda f: f.name.casefold())


# ── Ausgabe ───────────────────────────────────────────────────────

_KOPF = """# Bedienkatalog — was Claude in beiden Apps auslösen kann

> **Erzeugt** am {datum} von `python -m tools.bedienkatalog` aus dem Code beider
> Apps — nicht von Hand bearbeiten. Angaben zu 💶/⚠️/Hinweisen stehen als
> `BEDIENUNG` direkt neben der jeweiligen Funktion.

Gilt für „Vibe Operating“: Du sagst, was passieren soll; Claude führt es aus —
über die Funktionen der Apps, nicht über eigene Skripte.

## Ampel

| Zeichen | Bedeutung | Was du von Claude erwarten kannst |
|---|---|---|
| 🟢 | **erprobt** — Funktion mit Tests, von Claude direkt aufrufbar | Claude nennt die Funktion und führt sie aus |
| ⚪ | **ungetestet** — Funktion vorhanden, aber ohne Tests | nur mit deinem Okay; Kandidat für Tests |
| 🟡 | **nur Oberfläche** — gibt es nur als Fenster in der App | Claude leitet dich an oder schlägt eine Funktion vor |
| 🔴 | **nur von Hand** — alles, was hier **nicht** steht | einmalig, mit Sicherung, Prüfung und deinem Okay |

Zusatzzeichen: 💶 kostet Geld (LLM-Aufrufe) · ⚠️ verändert oder entfernt Daten.
Beides nur nach deinem ausdrücklichen Ja.

## Regeln

1. Claude bedient nur über 🟢-Funktionen und sagt dabei, welche es benutzt.
2. Fehlt eine Funktion, sagt Claude das und bietet an: einmalig von Hand (🔴)
   **oder** als Funktion bauen (wird danach 🟢).
3. Wird ein 🔴-Vorgang ein zweites Mal gebraucht, wird er zur Funktion.
4. 💶 und ⚠️ immer erst nach deinem Ja; vor einer vollen Testsuite Bescheid geben.
"""

_BEREICHE = (
    "Buchprojekte und Bücher", "Läufe und Automatik", "Prüfen, Vergleichen, Berichte",
    "Satz, Layout, Export", "Kommandozeilen",
)


def _zelle(text: str) -> str:
    return str(text or "").replace("|", "\\|").replace("\n", " ").strip()


def _zeile(e: Eintrag) -> str:
    stand = "🟢" if e.tests else "⚪"
    marken = ("💶 " if e.kostet else "") + ("⚠️ " if e.aendert else "")
    aufruf = f"`{e.aufruf}`" if e.aufruf else ""
    unter = ", ".join(f"`{n}`" for n, _h in e.unterbefehle)
    hinweis = e.hinweis
    if unter:
        hinweis = (f"Unterbefehle: {unter}. " + hinweis).strip()
    tests = f"{e.tests} Testdatei(en)" if e.tests else "keine Tests"
    return (
        f"| {_zelle(marken + e.vorgang)} | {e.app} | {aufruf} | {stand} | "
        f"{_zelle(hinweis)} ({tests}) |"
    )


def erzeuge_katalog(apps: list[tuple[str, Path]], *, datum: datetime | None = None) -> str:
    """Markdown des Katalogs für *apps* = [(Kürzel, Repo-Wurzel), …]."""
    alle: list[Eintrag] = []
    fenster: list[Fenster] = []
    for kuerzel, wurzel in apps:
        e, f = sammle(kuerzel, wurzel)
        alle += e
        fenster += f
    stand = datum or datetime.now().astimezone()
    teile = [_KOPF.format(datum=stand.strftime("%d.%m.%Y %H:%M"))]
    bereiche = list(_BEREICHE) + sorted({e.bereich for e in alle} - set(_BEREICHE))
    for bereich in bereiche:
        zeilen = sorted((e for e in alle if e.bereich == bereich),
                        key=lambda e: (not e.tests, e.app, e.vorgang.casefold()))
        if not zeilen:
            continue
        teile += [
            f"\n## {bereich}\n",
            "| Vorgang | App | Aufruf | Stand | Hinweis |",
            "|---|---|---|---|---|",
            *(_zeile(e) for e in zeilen),
        ]
    if fenster:
        teile += [
            "\n## Nur als Fenster (🟡)\n",
            "| Werkzeug | App | Beschreibung |",
            "|---|---|---|",
            *(f"| {_zelle(f.name)} | {f.app} | {_zelle(f.beschreibung)} |" for f in fenster),
        ]
    gruen = sum(1 for e in alle if e.tests)
    teile.append(
        f"\n---\n\n**Summe:** {gruen} erprobt (🟢) · {len(alle) - gruen} ungetestet (⚪) · "
        f"{len(fenster)} nur als Fenster (🟡). Alles Übrige: 🔴 nur von Hand.\n"
    )
    return "\n".join(teile)
