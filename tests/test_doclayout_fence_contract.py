"""Book Studio und GrammarGraph lesen dieselben ``:::``-Blöcke — noch.

Beide Programme müssen wissen, welche Fenced-Div-Klassen in einem Text
vorkommen: GrammarGraph, um beim Export zu melden, was es geschrieben hat;
Book Studio, um zu prüfen, wofür eine Vorlage fehlt. Die vier
Klassen-Regexe sind in beiden Projekten zeichengleich, und die
Code-Fence-Erkennung ist zweimal gebaut — hier über
``quarto_block_parser`` (die SSOT dieses Repos), dort als eigene kleine
Zustandsmaschine.

Zusammenlegen lässt sich das nicht: Es sind zwei eigenständig ausgelieferte
Programme, und eine Abhängigkeit vom jeweils anderen Repo will keines von
beiden. Was bleibt, ist die Übereinkunft messbar zu machen. Läuft eine Seite
weg, sagt es dieser Test — statt dass es Monate später an einem Absatz
auffällt, der in der ``.docx`` unformatiert blieb.

Ohne GrammarGraph daneben wird übersprungen: Der Test prüft eine Beziehung
zwischen zwei Projekten, nicht dieses hier.
"""

from __future__ import annotations

import importlib.util
import os
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Optional

import pytest

from tools.doclayout.usage import scan_text_detailed


def _grammargraph_wurzel() -> Optional[Path]:
    """Wo GrammarGraph liegt -- als Geschwisterordner oder per Umgebung."""
    aus_umgebung = os.environ.get("GRAMMARGRAPH_ROOT")
    kandidaten = [Path(aus_umgebung)] if aus_umgebung else []
    kandidaten.append(Path(__file__).resolve().parent.parent.parent / "GrammarGraph")
    for pfad in kandidaten:
        if (pfad / "src" / "core" / "emitted_classes.py").is_file():
            return pfad
    return None


def _lade_gegenseite() -> Optional[ModuleType]:
    """Laedt ``emitted_classes`` ueber den Dateipfad.

    Bewusst nicht ueber ``sys.path``: Das Modul kommt mit nichts als
    ``re`` und ``pathlib`` aus, und den Suchpfad dieses Testlaufs um ein
    fremdes Projekt zu erweitern haette Nebenwirkungen, die niemand hier
    ueberblickt.
    """
    wurzel = _grammargraph_wurzel()
    if wurzel is None:
        return None
    ziel = wurzel / "src" / "core" / "emitted_classes.py"
    spec = importlib.util.spec_from_file_location("_gg_emitted_classes", ziel)
    if spec is None or spec.loader is None:
        return None
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


_GEGENSEITE = _lade_gegenseite()

braucht_grammargraph = pytest.mark.skipif(
    _GEGENSEITE is None,
    reason="GrammarGraph liegt nicht daneben (GRAMMARGRAPH_ROOT setzen)",
)


#: Die Faelle, auf die es ankommt -- jeder einer, an dem sich zwei
#: Umsetzungen unterscheiden koennen.
FAELLE = {
    "einfache Klasse": "::: {.prompt}\nText\n:::\n",
    "Kurzform ohne Klammern": "::: prompt\nText\n:::\n",
    "Klammern ohne Punkt": "::: {prompt}\nText\n:::\n",
    "mehrere Klassen": "::: {.a .b}\nText\n:::\n",
    "im Codeblock": "```\n::: {.prompt}\n```\n",
    "verschachtelte Fences": "```\n~~~\n::: {.prompt}\n~~~\n```\n",
    "Tilde-Fence": "~~~\n::: {.prompt}\n~~~\n",
    "vier Doppelpunkte": ":::: {.aussen}\n::: {.innen}\n:::\n::::\n",
    "Attribut mit ID": '::: {#x .prompt key="v"}\nT\n:::\n',
    "eingerueckt": "  ::: {.prompt}\n  T\n  :::\n",
    "Fence in einer Liste": "- ```\n  ::: {.prompt}\n  ```\n",
    "mehrfach dieselbe Klasse": "::: {.p}\nA\n:::\n::: {.p}\nB\n:::\n",
    "leerer Text": "",
    "nur schliessende Zeile": ":::\n",
    "Bindestrich im Namen": "::: {.prompt-separator}\nT\n:::\n",
}


def _book_studio(text: str) -> tuple[dict[str, int], dict[str, int]]:
    gueltig, kaputt = scan_text_detailed(text)
    return dict(Counter(gueltig)), dict(Counter(kaputt))


def _grammargraph(text: str) -> tuple[dict[str, int], dict[str, int]]:
    assert _GEGENSEITE is not None
    return (
        _GEGENSEITE.scan_markdown(text),
        _GEGENSEITE.scan_markdown_malformed(text),
    )


@braucht_grammargraph
@pytest.mark.parametrize("name", sorted(FAELLE))
def test_beide_seiten_lesen_dasselbe(name: str):
    """Dieselbe Eingabe, dasselbe Ergebnis -- gueltige wie unbrauchbare Namen."""
    text = FAELLE[name]
    assert _book_studio(text) == _grammargraph(text), (
        f"»{name}«: Book Studio und GrammarGraph zaehlen verschieden. "
        "Eine der beiden Umsetzungen ist geaendert worden; die andere muss "
        "nachziehen, sonst fehlt spaeter eine Vorlage fuer einen Block, den "
        "es laut Export gar nicht gibt."
    )


@braucht_grammargraph
def test_die_klassen_regexe_sind_woertlich_gleich():
    """Der eigentliche Zwilling -- vier Ausdruecke, zweimal aufgeschrieben.

    Solange sie zeichengleich sind, ist die Doppelung nur Redundanz. Weicht
    einer ab, ist sie ein Fehler mit zwei Wahrheiten.
    """
    import tools.doclayout.usage as hier

    for name in ("_FENCE_RE", "_CLASS_RE", "_BARE_RE", "_BRACED_NO_DOT_RE"):
        meiner = getattr(hier, name)
        seiner = getattr(_GEGENSEITE, name, None)
        assert seiner is not None, f"{name} gibt es drueben nicht mehr"
        assert meiner.pattern == seiner.pattern, (
            f"{name} laeuft auseinander:\n"
            f"  Book Studio  : {meiner.pattern}\n"
            f"  GrammarGraph : {seiner.pattern}"
        )


def test_der_vertrag_wird_ueberhaupt_geprueft():
    """Ohne diesen Test faellt nicht auf, dass der Abgleich still uebersprungen wird."""
    if _GEGENSEITE is None:
        pytest.skip("GrammarGraph liegt nicht daneben -- der Abgleich entfaellt")
    assert hasattr(_GEGENSEITE, "scan_markdown")
    assert hasattr(_GEGENSEITE, "scan_markdown_malformed")
