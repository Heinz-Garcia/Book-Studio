"""RenderService – Export-Optionen, Render-Orchestrierung, Render-Logs.

Phase 2 / Schritt 2.3a: Heute lebt die Logik zwischen `ExportManager` und
`book_studio.run_quarto_render`. In 2.3a wurde nur die *reine Format-Logik*
in diesen Service verlagert: `resolve_target_format`. Sie ist eine pure
Funktion ohne I/O, ohne Subprocess, ohne Threading — und damit risikolos
testbar.

Phase 2 / Schritt 2.3b (konservativ): Nur die *reinen Helper-Funktionen*
der Render- und Log-Logik sind in diesen Service verlagert. Die
Subprocess-Orchestrierung (`_run_safe_render`), das Threading, die
Tk-Schedule-Calls und das Pre-Processing auf einer Temp-Kopie bleiben
in `ExportManager`. Die Trennung ist bewusst risikoreduziert — Live-
Render-Pfade sollen in einer einzigen Refactoring-Session NICHT
angefasst werden.

Konkrete pure Funktionen in 2.3b:
- `build_render_log_path(book_root, target_fmt, now=None) -> Path`
- `sanitize_filename_part(s) -> str`
- `build_safe_render_command(executable, safe_script, book, target_fmt, profile_name, extra_format_options) -> list[str]`
- `extract_processed_source_path(rel_path) -> str`
- `iter_tree_paths(tree_data) -> Iterator[str]` (pure Generator-Funktion)

Verweise:
- .doc/refactoring-master.md, Batch B8 (Stub-Definition)
- .doc/Refactoring_part2.md, Schritt 2.3 (Migration; aufgeteilt in 2.3a + 2.3b)
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional


# --- Konventionen ----------------------------------------------------------

# Praefix fuer Quarto-Extensions im Template-Dropdown.
# Beispiel: "EXT: typstdoc" -> Render als "typstdoc-html" mit erweiterten Optionen.
EXTENSION_TEMPLATE_PREFIX = "EXT: "

# Verzeichnis-Layout fuer Render-Logs: `<book_root>/export/render_logs`.
RENDER_LOG_DIR_PARTS = ("export", "render_logs")

# Praefix fuer Log-Dateinamen.
RENDER_LOG_FILE_PREFIX = "render_"

# Zeitstempel-Format fuer Render-Log-Dateinamen.
RENDER_LOG_TIMESTAMP_FMT = "%Y%m%d_%H%M%S"

# Default-Name fuer den Log-Endung-Slot, falls `target_fmt` fehlt.
RENDER_LOG_DEFAULT_FMT_SLUG = "unknown"

# Praefix im "processed/"-Baum, das bei Issue-Logs in den Source-Pfad
# zurueckgemappt wird.
PROCESSED_TREE_PREFIX = "processed/"

# Argument-Namen fuer `quarto_render_safe.py` (B6-Subprocess-Schnittstelle).
SAFE_RENDER_ARG_TO = "--to"
SAFE_RENDER_ARG_PROFILE = "--profile-name"
SAFE_RENDER_ARG_EXTRA_OPTS = "--extra-format-options-json"


# --- Service ----------------------------------------------------------------


class RenderService:
    """Export-Optionen, Render-Orchestrierung, Render-Logs.

    Phase 2 / 2.3a: Bereitstellung von `resolve_target_format` (pure
    Funktion).
    Phase 2 / 2.3b: Bereitstellung der *reinen Helper* (Log-Pfad,
    Sanitisierung, Subprocess-Argv, processed-Mapping, Tree-Iteration).
    Die Render-Orchestrierung mit Threading/Subprocess bleibt in
    `ExportManager`.
    """

    def __init__(self, exporter: Any):
        self._exporter = exporter

    # --- Format-Aufloesung ----------------------------------------------

    @staticmethod
    def resolve_target_format(
        base_fmt: str, template: str
    ) -> tuple[str, Optional[dict]]:
        """Loest das eigentliche Quarto-Zielformat und optionale Format-Optionen auf.

        Drei Faelle:
        1. **Quarto-Extension** (`template` startet mit `"EXT: "`):
           Zielformat wird zu `"{ext_name}-{base_fmt}"` umgesetzt und es
           werden typische Buch-Features (TOC, Nummerierung) als
           `extra_opts[target_fmt]` injiziert.
        2. **Lokales Template** (`template` ungleich `"Standard"`, kein EXT-Prefix):
           `extra_opts[base_fmt]["template"]` zeigt auf `templates/{template}`.
        3. **Standard-Template** (`template == "Standard"`):
           Keine Extra-Optionen; `extra_opts` ist `None`.

        Diese Funktion ist *pur*: kein I/O, keine Subprocess-Aufrufe,
        keine Status- oder Log-Aufrufe. Damit ist sie risikolos testbar.
        """
        if not base_fmt:
            raise ValueError("base_fmt darf nicht leer sein")
        if template is None:
            template = "Standard"

        if template.startswith(EXTENSION_TEMPLATE_PREFIX):
            ext_name = template.replace(EXTENSION_TEMPLATE_PREFIX, "").strip()
            if not ext_name:
                raise ValueError(
                    f"Extension-Template ohne Namen: {template!r}"
                )
            target_fmt = f"{ext_name}-{base_fmt}"
            extra_opts = {
                target_fmt: {
                    "toc": True,
                    "toc-depth": 3,
                    "number-sections": True,
                    "section-numbering": "1.1.1",
                }
            }
            return target_fmt, extra_opts

        if template != "Standard":
            extra_opts = {base_fmt: {"template": f"templates/{template}"}}
            return base_fmt, extra_opts

        return base_fmt, None

    # --- Render-Log-Pfad (Phase 2 / 2.3b) -------------------------------

    @staticmethod
    def build_render_log_path(
        book_root: Path, target_fmt: str, now: Optional[datetime] = None
    ) -> Path:
        """Berechnet den Pfad der Render-Log-Datei.

        Layout: `<book_root>/export/render_logs/render_<timestamp>_<safe_fmt>.log`.
        `target_fmt` wird ueber `sanitize_filename_part` sanitiert.
        `now` ist nur fuer Tests injizierbar.

        Die Funktion ist *pur* und fuehrt *kein* I/O aus (sie legt das
        Verzeichnis nicht an). Verzeichnis-Erstellung und Datei-Open
        bleiben Aufgabe des Studios.
        """
        moment = now if now is not None else datetime.now()
        timestamp = moment.strftime(RENDER_LOG_TIMESTAMP_FMT)
        safe_fmt = RenderService.sanitize_filename_part(
            str(target_fmt or RENDER_LOG_DEFAULT_FMT_SLUG)
        )
        log_dir = Path(book_root) / Path(*RENDER_LOG_DIR_PARTS)
        return log_dir / f"{RENDER_LOG_FILE_PREFIX}{timestamp}_{safe_fmt}.log"

    @staticmethod
    def sanitize_filename_part(s: str) -> str:
        """Ersetzt alle nicht-alphanumerischen Zeichen (ausser `._-`)
        durch `_`. Wird fuer Log-Dateinamen und vergleichbare Slots
        verwendet.
        """
        return re.sub(r"[^A-Za-z0-9._-]", "_", s or "")

    # --- Safe-Render-Command (Phase 2 / 2.3b) ---------------------------

    @staticmethod
    def build_safe_render_command(
        executable: str,
        safe_script: Path,
        book: Path,
        target_fmt: str,
        profile_name: Optional[str] = None,
        extra_format_options: Optional[dict] = None,
    ) -> list:
        """Baut die argv-Liste fuer den sicheren Render-Subprocess.

        Aufbau:
        `[executable, str(safe_script), str(book), "--to", target_fmt]`
        plus optional `--profile-name <name>` und
        `--extra-format-options-json <json>`.

        Die Funktion ist *pur* (kein Subprocess-Aufruf, kein I/O).
        `extra_format_options` wird via `json.dumps(..., ensure_ascii=False,
        separators=(",", ":"))` in einen String umgewandelt.
        """
        import json as _json

        cmd = [
            str(executable),
            str(safe_script),
            str(book),
            SAFE_RENDER_ARG_TO,
            str(target_fmt),
        ]
        if profile_name:
            cmd.extend([SAFE_RENDER_ARG_PROFILE, str(profile_name)])
        if extra_format_options:
            cmd.extend([
                SAFE_RENDER_ARG_EXTRA_OPTS,
                _json.dumps(extra_format_options, ensure_ascii=False, separators=(",", ":")),
            ])
        return cmd

    # --- Processed-Tree-Mapping (Phase 2 / 2.3b) -----------------------

    @staticmethod
    def extract_processed_source_path(rel_path: str) -> str:
        """Mappt einen Pfad aus dem `processed/`-Baum auf den Source-Pfad.

        `"processed/foo/bar.md" -> "foo/bar.md"`. Sonst bleibt der Pfad
        unveraendert. `None` und Nicht-Strings werden defensiv behandelt
        (leerer String zurueckgegeben).
        """
        if not isinstance(rel_path, str):
            return ""
        if rel_path.startswith(PROCESSED_TREE_PREFIX):
            return rel_path[len(PROCESSED_TREE_PREFIX):]
        return rel_path

    @staticmethod
    def iter_tree_paths(tree_data: Optional[Iterable[dict]]) -> Iterator[str]:
        """Iteriert rekursiv durch einen Tree und liefert die `path`-Eintraege.

        Erwartet wird das `_get_tree_data_for_engine`-Format:
        `{"path": "foo.md", "children": [...]}`-Eintraege.
        `path` darf fehlen oder kein String sein; solche Eintraege
        werden uebersprungen. Children-Listen werden rekursiv
        durchlaufen. `None` und leere Iterables ergeben einen
        leeren Iterator.
        """
        if not tree_data:
            return
        for item in tree_data:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            if isinstance(path, str):
                yield path
            children = item.get("children") or []
            if children:
                yield from RenderService.iter_tree_paths(children)

    # --- Bestehende API (unveraendert) -----------------------------------

    def run_render(self) -> bool:
        """Startet den Render-Pfad. Delegiert an `ExportManager.run_quarto_render`.

        Wird in einer spaeteren Session in den Service verlagert.
        """
        run = getattr(self._exporter, "run_quarto_render", None)
        return bool(run()) if callable(run) else False

    def get_render_log_dir(self) -> Optional[Path]:
        """Liefert das Render-Log-Verzeichnis des Exporters, falls vorhanden."""
        get = getattr(self._exporter, "get_render_log_dir", None)
        if callable(get):
            return get()
        return None


__all__ = [
    "EXTENSION_TEMPLATE_PREFIX",
    "PROCESSED_TREE_PREFIX",
    "RENDER_LOG_DIR_PARTS",
    "RENDER_LOG_FILE_PREFIX",
    "RENDER_LOG_TIMESTAMP_FMT",
    "RENDER_LOG_DEFAULT_FMT_SLUG",
    "SAFE_RENDER_ARG_EXTRA_OPTS",
    "SAFE_RENDER_ARG_PROFILE",
    "SAFE_RENDER_ARG_TO",
    "RenderService",
]
