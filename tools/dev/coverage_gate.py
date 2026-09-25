"""Abdeckungs-Gate je Bereich (Teil der Commit-Sperre).

Liest die Messdaten (``.coverage``) eines Testlaufs mit ``--cov`` und prüft
jeden Bereich gegen seine eigene Untergrenze. Getrennt, weil eine
Gesamtzahl die strengere Kern-Schwelle verwässern würde: Die Oberfläche
ist rund siebenmal so groß wie der Kern.

Schwellen sind Untergrenzen mit etwas Luft unter dem Ist-Stand (25.09.:
Kern 85 %, ui_qt 62 %). Steigt die Abdeckung, die Schwelle nachziehen —
nie senken, um einen Commit durchzubringen.

Aufruf von Hand nach ``pytest --cov``: ``python tools/dev/coverage_gate.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Bereich:
    name: str
    praefixe: tuple[str, ...]
    minimum: float


BEREICHE: tuple[Bereich, ...] = (
    Bereich(
        "Kern (Services + Parser)",
        (
            "services/",
            "app_config.py",
            "session_state.py",
            "frontmatter_parser.py",
            "quarto_block_parser.py",
        ),
        80.0,
    ),
    Bereich("Oberfläche (ui_qt)", ("ui_qt/",), 60.0),
)


@dataclass(frozen=True)
class Ergebnis:
    bereich: Bereich
    anweisungen: int
    getroffen: int

    @property
    def prozent(self) -> float:
        return 100.0 * self.getroffen / self.anweisungen if self.anweisungen else 0.0

    @property
    def ok(self) -> bool:
        return self.anweisungen > 0 and self.prozent + 1e-9 >= self.bereich.minimum


def _bereich_von(relpfad: str) -> Bereich | None:
    for bereich in BEREICHE:
        if any(relpfad == p or relpfad.startswith(p) for p in bereich.praefixe):
            return bereich
    return None


def messe(data_file: Path = ROOT / ".coverage") -> list[Ergebnis]:
    """Anweisungen/Treffer je Bereich aus den Messdaten."""
    import coverage

    cov = coverage.Coverage(data_file=str(data_file), config_file=str(ROOT / ".coveragerc"))
    cov.load()
    summen: dict[str, list[int]] = {b.name: [0, 0] for b in BEREICHE}
    for datei in cov.get_data().measured_files():
        try:
            rel = Path(datei).resolve().relative_to(ROOT).as_posix()
        except ValueError:
            continue
        bereich = _bereich_von(rel)
        if bereich is None:
            continue
        _, anweisungen, _, fehlend, _ = cov.analysis2(datei)
        summen[bereich.name][0] += len(anweisungen)
        summen[bereich.name][1] += len(anweisungen) - len(fehlend)
    return [Ergebnis(b, *summen[b.name]) for b in BEREICHE]


def bericht(ergebnisse: list[Ergebnis]) -> tuple[bool, str]:
    zeilen = ["Abdeckungs-Gate:"]
    for e in ergebnisse:
        marke = "ok " if e.ok else "ROT"
        zeilen.append(
            f"  {marke} {e.bereich.name}: {e.prozent:.1f} % "
            f"({e.getroffen}/{e.anweisungen}), Minimum {e.bereich.minimum:.0f} %"
        )
    return all(e.ok for e in ergebnisse), "\n".join(zeilen)


def main() -> int:
    data = ROOT / ".coverage"
    if not data.is_file():
        print("Abdeckungs-Gate: keine Messdaten (.coverage) — erst pytest --cov laufen lassen.")
        return 2
    ok, text = bericht(messe(data))
    print(text, flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
