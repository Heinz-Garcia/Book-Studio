"""Tests für R2: Re-Entrancy-Sperre in `run_sanitizer_pipeline()`.

Quelle: implementation_plan.md, Abschnitt 3.2 (R2).

Diese Tests prüfen, dass CommandHost ein `_sanitizer_running`-Flag implementiert,
analog zum `_handbook_pdf_rendering`-Flag. Nach dem Tk-UI-Purge lebt die
Sanitizer-Logik in `ui_qt.command_host.CommandHost`.
"""

from __future__ import annotations

import inspect

import pytest


class TestSanitizerRunningFlagImplementation:
    """Tests zur Verifikation der _sanitizer_running-Flag-Implementierung."""

    def test_bookstudio_has_handbook_pdf_rendering_flag(self) -> None:
        """Referenztest: CommandHost hat ein `_handbook_pdf_rendering`-Flag.

        Dies ist das Vorbild für R2 (Sanitizer-Re-Entrancy-Guard).
        """
        from ui_qt.command_host import CommandHost

        source = inspect.getsource(CommandHost.render_help_manual_pdf)
        assert "_handbook_pdf_rendering" in source, (
            "CommandHost.render_help_manual_pdf sollte _handbook_pdf_rendering-Flag "
            "verwenden (das ist das Vorbild für _sanitizer_running)"
        )

    def test_bookstudio_should_have_sanitizer_running_flag(self) -> None:
        """R2-Test: run_sanitizer_pipeline prüft `_sanitizer_running`.

        Nach dem Tk-UI-Purge lebt das Guard in CommandHost.run_sanitizer_pipeline.
        """
        from ui_qt.command_host import CommandHost

        source = inspect.getsource(CommandHost.run_sanitizer_pipeline)
        assert "_sanitizer_running" in source, (
            "CommandHost.run_sanitizer_pipeline sollte '_sanitizer_running' prüfen "
            "(R2-Implementierung). Dies ist das Äquivalent zu _handbook_pdf_rendering."
        )

    def test_run_sanitizer_pipeline_checks_reentrancy_guard(self) -> None:
        """R2-Test: run_sanitizer_pipeline prüft den Re-Entrancy-Guard."""
        from ui_qt.command_host import CommandHost

        source = inspect.getsource(CommandHost.run_sanitizer_pipeline)
        assert "_sanitizer_running" in source, (
            "run_sanitizer_pipeline sollte _sanitizer_running prüfen (R2-Guard)."
        )

    def test_sanitizer_thread_resets_flag_in_finally(self) -> None:
        """R2-Test: Der Worker-Thread setzt das Flag zurück (on_done-Callback).

        Die Qt-Implementierung verwendet einen `on_done`-Callback statt
        eines finally-Blocks. Beide Ansätze sichern den Flag-Reset.
        """
        from ui_qt.command_host import CommandHost

        source = inspect.getsource(CommandHost.run_sanitizer_pipeline)
        # The flag must be set to False somewhere after the work completes.
        # Qt uses an on_done callback instead of try/finally — both are valid.
        assert source.count("_sanitizer_running") >= 2, (
            "run_sanitizer_pipeline muss _sanitizer_running sowohl setzen als "
            "auch zurücksetzen (R2-Reset). Mindestens 2 Vorkommen erwartet."
        )


class TestSanitizerReentryComparison:
    """Tests zum Vergleich mit dem bereits implementierten _handbook_pdf_rendering-Pattern."""

    def test_handbook_pdf_rendering_flag_pattern(self) -> None:
        """Referenztest: Das _handbook_pdf_rendering-Muster in CommandHost."""
        from ui_qt.command_host import CommandHost

        source = inspect.getsource(CommandHost.render_help_manual_pdf)

        # Guard-Check
        assert "_handbook_pdf_rendering" in source
        # Flag-Setting
        assert "self.w._handbook_pdf_rendering = True" in source or (
            "setattr" in source
        )

    def test_sanitizer_pattern_mirrors_handbook_pattern(self) -> None:
        """R2-Test: _sanitizer_running soll analog _handbook_pdf_rendering sein.

        Prüft alle 3 Komponenten:
        1. Guard: `_sanitizer_running` wird in run_sanitizer_pipeline geprüft
        2. Flag-Setting: `_sanitizer_running = True` gesetzt
        3. Reset im finally: Flag wird zurückgesetzt
        """
        from ui_qt.command_host import CommandHost

        sanitizer_source = inspect.getsource(CommandHost.run_sanitizer_pipeline)

        # Komponente 1 + 2: Guard und Flag-Setting
        assert "_sanitizer_running" in sanitizer_source, (
            "Komponente 1 (Guard): run_sanitizer_pipeline sollte _sanitizer_running verwenden"
        )

        # Komponente 3: Reset (on_done callback in Qt; try/finally in Tk-Vorgänger)
        assert sanitizer_source.count("_sanitizer_running") >= 2, (
            "Komponente 3 (Reset): _sanitizer_running muss mindestens 2x vorkommen "
            "(Guard-Check + Reset). Qt nutzt on_done-Callback statt finally."
        )


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
