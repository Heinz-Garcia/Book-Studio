"""RenderService – Export-Optionen, Render-Orchestrierung, Render-Logs.

Phase 2 / Schritt 2.3a: Heute lebt die Logik zwischen `ExportManager` und
`book_studio.run_quarto_render`. In 2.3a wurde nur die *reine Format-Logik*
in diesen Service verlagert: `resolve_target_format`. Sie ist eine pure
Funktion ohne I/O, ohne Subprocess, ohne Threading — und damit risikolos
testbar.

Schritt 2.3b (eigene Session) verlagert anschliessend die Pre-Processing-
Pipeline und die Subprocess-Orchestrierung (`_run_safe_render`).

API:
    service = RenderService(exporter)
    target_fmt, extra_opts = service.resolve_target_format(base_fmt, template)

Verweise:
- .doc/refactoring-master.md, Batch B8 (Stub-Definition)
- .doc/Refactoring_part2.md, Schritt 2.3 (Migration; aufgeteilt in 2.3a + 2.3b)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Protocol


# --- Konventionen ----------------------------------------------------------

# Praefix fuer Quarto-Extensions im Template-Dropdown.
# Beispiel: "EXT: typstdoc" -> Render als "typstdoc-html" mit erweiterten Optionen.
EXTENSION_TEMPLATE_PREFIX = "EXT: "


# --- Service ----------------------------------------------------------------


class RenderService:
    """Export-Optionen, Render-Orchestrierung, Render-Logs.

    Phase 2 / 2.3a: Bereitstellung von `resolve_target_format` (pure
    Funktion). Die Render-Orchestrierung mit Threading/Subprocess bleibt
    in `ExportManager` und wird in 2.3b migriert.
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

    # --- Bestehende API (unveraendert) -----------------------------------

    def run_render(self) -> bool:
        """Startet den Render-Pfad. Delegiert an `ExportManager.run_quarto_render`.

        Wird in Schritt 2.3b in den Service verlagert.
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
    "RenderService",
]
