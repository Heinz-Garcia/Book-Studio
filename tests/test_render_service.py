"""Tests fuer Phase 2 / Schritt 2.3a: RenderService.resolve_target_format.

Stellt sicher, dass die Format-Aufloesung (Extension-Branch, lokales
Template, Standard-Template) korrekt funktioniert. Dies ist eine pure
Funktion ohne I/O, ohne Subprocess, ohne Tk — daher risikolos testbar.

Diese Tests wurden hinzugefuegt, als die Inline-Logik in
`ExportManager.run_quarto_render` durch `RenderService.resolve_target_format`
ersetzt wurde.
"""

from __future__ import annotations

import pytest

from services.render_service import (
    EXTENSION_TEMPLATE_PREFIX,
    RenderService,
)


# --- Konstanten ------------------------------------------------------------


def test_extension_template_prefix_is_export_with_trailing_space():
    """Der Prefix muss `EXT: ` sein (mit Trailing-Space), weil ihn der
    `TemplateManager` exakt so ausgibt."""
    assert EXTENSION_TEMPLATE_PREFIX == "EXT: "


# --- Standard-Template -----------------------------------------------------


def test_resolve_target_format_standard_template_returns_base():
    """`Standard`-Template: keine Extra-Optionen, Zielformat = `base_fmt`."""
    target, extra = RenderService.resolve_target_format("html", "Standard")
    assert target == "html"
    assert extra is None


def test_resolve_target_format_standard_with_typst():
    target, extra = RenderService.resolve_target_format("typst", "Standard")
    assert target == "typst"
    assert extra is None


def test_resolve_target_format_standard_with_pdf():
    target, extra = RenderService.resolve_target_format("pdf", "Standard")
    assert target == "pdf"
    assert extra is None


# --- Lokales Template ------------------------------------------------------


def test_resolve_target_format_local_template():
    """Lokales Template: `extra_opts[base_fmt]['template']` zeigt auf
    `templates/{template}`."""
    target, extra = RenderService.resolve_target_format("html", "book.typst")
    assert target == "html"
    assert extra == {"html": {"template": "templates/book.typst"}}


def test_resolve_target_format_local_template_typst():
    target, extra = RenderService.resolve_target_format("typst", "minimal.typst")
    assert target == "typst"
    assert extra == {"typst": {"template": "templates/minimal.typst"}}


# --- Quarto-Extension ------------------------------------------------------


def test_resolve_target_format_extension_typstdoc():
    """`EXT: typstdoc` mit `base_fmt='html'` wird zu `typstdoc-html`."""
    target, extra = RenderService.resolve_target_format("html", "EXT: typstdoc")
    assert target == "typstdoc-html"
    assert extra == {
        "typstdoc-html": {
            "toc": True,
            "toc-depth": 3,
            "number-sections": True,
            "section-numbering": "1.1.1",
        }
    }


def test_resolve_target_format_extension_with_typst_base():
    target, extra = RenderService.resolve_target_format("typst", "EXT: typstdoc")
    assert target == "typstdoc-typst"
    assert extra is not None
    assert "typstdoc-typst" in extra
    assert extra["typstdoc-typst"]["toc"] is True


def test_resolve_target_format_extension_extra_options_complete():
    """Die injizierten Optionen enthalten alle vier erwarteten Schluessel."""
    _, extra = RenderService.resolve_target_format("html", "EXT: anyext")
    assert extra is not None
    fmt_opts = extra[next(iter(extra))]
    assert set(fmt_opts.keys()) == {"toc", "toc-depth", "number-sections", "section-numbering"}


def test_resolve_target_format_extension_strips_prefix():
    """Whitespace um den Extension-Namen wird getrimmt."""
    target, _ = RenderService.resolve_target_format("html", "EXT:   myext  ")
    assert target == "myext-html"


# --- Edge-Cases / Fehlerpfade ---------------------------------------------


def test_resolve_target_format_empty_base_raises():
    """Leerer `base_fmt` ist ein Aufrufer-Fehler."""
    with pytest.raises(ValueError):
        RenderService.resolve_target_format("", "Standard")


def test_resolve_target_format_extension_with_empty_name_raises():
    """`EXT: ` ohne Name ist ein Aufrufer-Fehler (Extension kann nicht
    konstruiert werden)."""
    with pytest.raises(ValueError):
        RenderService.resolve_target_format("html", "EXT: ")


def test_resolve_target_format_extension_only_whitespace_raises():
    """`EXT:    ` (nur Whitespace) ist ebenfalls ein Fehler."""
    with pytest.raises(ValueError):
        RenderService.resolve_target_format("html", "EXT:    ")


def test_resolve_target_format_none_template_treated_as_standard():
    """`None` als Template wird als `'Standard'` behandelt — robuster
    Aufrufer-Schutz."""
    target, extra = RenderService.resolve_target_format("html", None)  # type: ignore[arg-type]
    assert target == "html"
    assert extra is None


def test_resolve_target_format_extension_does_not_match_local():
    """Wenn der Template-Name mit `EXT: ` beginnt, NICHT in den
    `local template`-Branch fallen."""
    target, extra = RenderService.resolve_target_format("html", "EXT: x")
    assert target == "x-html"
    assert "template" not in extra[target]  # nicht im local-template-Format


# --- Rueckwaertskompatibilitaet: Service-Instanz + run_render-stub --------


def test_run_render_delegates_to_exporter():
    """Der `run_render`-Stub delegiert weiterhin an `ExportManager`."""
    called = []

    class _FakeExporter:
        def run_quarto_render(self):
            called.append(True)
            return True

    svc = RenderService(_FakeExporter())
    assert svc.run_render() is True
    assert called == [True]


def test_run_render_returns_false_when_method_missing():
    svc = RenderService(object())
    assert svc.run_render() is False


def test_run_render_coerces_truthy_result_to_bool():
    """Auch wenn der Exporter einen Truthy-Nicht-Bool zurueckgibt, ist das
    Ergebnis ein `bool`."""
    called = []

    class _FakeExporter:
        def run_quarto_render(self):
            called.append(True)
            return "ok"

    svc = RenderService(_FakeExporter())
    assert svc.run_render() is True
    assert isinstance(svc.run_render(), bool)


def test_get_render_log_dir_via_exporter():
    from pathlib import Path

    expected = Path("/var/log/render")

    class _FakeExporter:
        def get_render_log_dir(self):
            return expected

    svc = RenderService(_FakeExporter())
    assert svc.get_render_log_dir() == expected


def test_get_render_log_dir_returns_none_when_missing():
    svc = RenderService(object())
    assert svc.get_render_log_dir() is None


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
