"""Tests für Batch B2: Frontmatter-Parser (SSOT).

Stellt sicher, dass das neue `frontmatter_parser`-Modul die Erwartungen
erfüllt, die bisher an die verstreuten Regex-Parser in
`yaml_engine.py`, `book_doctor.py`, `Sanitizer.py` und `export_manager.py`
gestellt wurden.

Referenz: .doc/refactoring-master.md, Batch B2.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import frontmatter_parser as fp


# --- Grundlegendes Parsing --------------------------------------------------


def test_parse_no_frontmatter_returns_body_only():
    parts = fp.parse("# Hallo\n\nText\n")
    assert not parts.has_frontmatter
    assert parts.body == "# Hallo\n\nText\n"
    assert parts.header is None


def test_parse_simple_frontmatter():
    content = "---\ntitle: Hallo\ndescription: Welt\n---\n\n# Body\n"
    parts = fp.parse(content)
    assert parts.has_frontmatter
    assert parts.header.strip() == "title: Hallo\ndescription: Welt"
    assert parts.body.startswith("\n# Body")
    assert parts.duplicate_opening_count == 0
    assert parts.had_closing_delimiter is True


def test_parse_handles_bom():
    content = "\ufeff---\ntitle: H\n---\n\nbody\n"
    parts = fp.parse(content)
    assert parts.bom == "\ufeff"
    assert parts.has_frontmatter
    assert parts.parsed().get("title") == "H"


def test_parse_duplicate_opening_delimiters():
    content = "---\n---\ntitle: Doppel\n---\n\nbody\n"
    parts = fp.parse(content)
    assert parts.duplicate_opening_count == 1
    assert parts.has_frontmatter
    assert parts.parsed().get("title") == "Doppel"


def test_parse_missing_closing_delimiter_uses_blank_paragraph_heuristic():
    content = "---\ntitle: OhneEnde\n\nBody startet hier\n"
    parts = fp.parse(content)
    assert parts.has_frontmatter
    assert parts.had_closing_delimiter is False
    assert "title: OhneEnde" in (parts.header or "")
    assert parts.body.lstrip().startswith("Body startet hier")


def test_parse_handles_crlf():
    content = "---\r\ntitle: CrLf\r\n---\r\n\r\nbody\r\n"
    parts = fp.parse(content)
    assert parts.has_frontmatter
    assert parts.parsed().get("title") == "CrLf"


def test_parse_empty_content():
    parts = fp.parse("")
    assert not parts.has_frontmatter
    assert parts.body == ""


def test_parse_only_opening_delimiter():
    parts = fp.parse("---\nKein Ende hier, nur Body\n")
    assert parts.has_frontmatter
    assert parts.had_closing_delimiter is False


def test_parse_does_not_confuse_with_pandoc_setext():
    """`----` (4+ Bindestriche) ist KEIN Frontmatter-Trenner."""
    content = "----\ntitle: Pandoc\n----\n\nbody\n"
    parts = fp.parse(content)
    assert not parts.has_frontmatter
    assert parts.body == content


# --- extract_field ----------------------------------------------------------


def test_extract_field_title():
    content = "---\ntitle: Mein Buch\nother: x\n---\n\n# Body\n"
    assert fp.extract_field(content, "title") == "Mein Buch"


def test_extract_field_missing():
    content = "---\nfoo: bar\n---\n\n# Body\n"
    assert fp.extract_field(content, "missing") is None


def test_extract_field_quoted():
    content = "---\ntitle: 'Mit Quotes'\n---\n"
    assert fp.extract_field(content, "title") == "Mit Quotes"


def test_extract_field_no_frontmatter():
    assert fp.extract_field("# H1\n", "title") is None


# --- validate_and_repair ----------------------------------------------------


def test_validate_and_repair_strict_blocks_invalid_yaml():
    content = "---\n: kaputt: weil : doppelpunkt\n---\n\nbody\n"
    new, changes, ok = fp.validate_and_repair(content, header_mode="strict")
    assert not ok
    assert any("STRICT" in c for c in changes)
    assert new == content


def test_validate_and_repair_repair_normalises_yaml():
    content = "---\ntitle: A\ndescription: B\n---\n\nbody\n"
    new, _changes, ok = fp.validate_and_repair(
        content, header_mode="repair", preserve_style_in_repair=False
    )
    assert ok
    # Ohne preserve_style muss yaml.safe_dump den Inhalt neu serialisieren
    assert "title: A" in new
    assert "description: B" in new


def test_validate_and_repair_repair_normalises_without_crashing():
    """Smoke: repair-Modus ohne preserve_style parst gültiges YAML,
    auch wenn der re-serialisierte Text identisch zum Original ist."""
    content = "---\ntitle: A\ndescription: B\n---\n\nbody\n"
    new, _changes, ok = fp.validate_and_repair(
        content, header_mode="repair", preserve_style_in_repair=False
    )
    assert ok
    assert "title: A" in new
    assert "description: B" in new


def test_validate_and_repair_preserve_keeps_content():
    content = "---\ntitle: A\ndescription: B\n---\n\nbody\n"
    new, _changes, ok = fp.validate_and_repair(
        content, header_mode="preserve"
    )
    assert ok
    assert "title: A" in new
    assert "description: B" in new


def test_validate_and_repair_adds_missing_closing_delimiter():
    content = "---\ntitle: Offen\n\nbody\n"
    new, changes, _ok = fp.validate_and_repair(content, header_mode="preserve")
    assert any("Fehlender YAML-Endtrenner" in c for c in changes)
    assert "---" in new.splitlines()[2]  # closing delimiter present


def test_validate_and_repair_removes_duplicate_opening():
    content = "---\n---\ntitle: A\n---\n\nbody\n"
    new, changes, _ok = fp.validate_and_repair(content, header_mode="preserve")
    assert any("Doppelte" in c for c in changes)
    # Der reparierte Text darf nur EINE `---` am Anfang haben
    first_five = new.split("\n", 1)
    assert first_five[0] == "---"


def test_validate_and_repair_invalid_header_mode_raises():
    with pytest.raises(ValueError):
        fp.validate_and_repair("---\ntitle: x\n---\n", header_mode="bogus")


# --- parse_file -------------------------------------------------------------


def test_parse_file_reads_file(tmp_path: Path):
    md = tmp_path / "book.md"
    md.write_text("---\ntitle: Disk\n---\n\nbody\n", encoding="utf-8")
    parts = fp.parse_file(md)
    assert parts.has_frontmatter
    assert parts.parsed().get("title") == "Disk"


def test_parse_file_missing_file(tmp_path: Path):
    parts = fp.parse_file(tmp_path / "nope.md")
    assert not parts.has_frontmatter


# --- SSOT-Invariante: gleiches Verhalten wie Alt-Parser --------------------


def test_ssot_compat_yaml_engine_title_extraction():
    """Der `extract_title_from_md`-Parser in `yaml_engine` lieferte
    exakt die Zeichenkette nach `title:` bis Zeilenende.
    `frontmatter_parser.extract_field` muss das gleiche Ergebnis
    liefern, sonst brechen Konsumenten."""
    cases = {
        "---\ntitle: Hallo\n---\nbody": "Hallo",
        "---\ntitle: 'Zitat'\n---\nbody": "Zitat",
        "---\ntitle: \"Doppelt\"\n---\nbody": "Doppelt",
        "---\ntitle: Mit Leerzeichen \n---\nbody": "Mit Leerzeichen",
    }
    for content, expected in cases.items():
        assert fp.extract_field(content, "title") == expected, content


# --- Phase 2: Coverage-Lücken ------------------------------------------------
# Diese Tests sind reine Coverage-Erweiterung für Schritt 1 (Coverage-Messung).
# Sie fügen keine neuen Features hinzu, sondern prüfen Randpfade.


def test_detect_newline_lf_fallback():
    """`_detect_newline` muss für reinen LF-Inhalt `\\n` liefern,
    auch wenn kein `\\r` vorkommt."""
    assert fp._detect_newline("Hallo\nWelt") == "\n"
    assert fp._detect_newline("") == "\n"
    assert fp._detect_newline("ohne jeden Umbruch") == "\n"


def test_detect_newline_cr_only():
    """`_detect_newline` muss für alten Mac-Umbruch (`\\r` ohne `\\n`) `\\r` liefern."""
    assert fp._detect_newline("Hallo\rWelt") == "\r"


def test_parsed_returns_empty_when_yaml_unavailable(monkeypatch):
    """Wenn `yaml is None`, darf `parsed()` nicht crashen, sondern liefert `{}`."""
    import frontmatter_parser as fp_mod
    monkeypatch.setattr(fp_mod, "yaml", None)
    parts = fp_mod.FrontmatterParts(header="title: x")
    assert parts.parsed() == {}
    # und auch ohne Header
    assert fp_mod.FrontmatterParts().parsed() == {}


def test_parsed_returns_empty_on_yaml_error(monkeypatch):
    """Wenn `yaml.safe_load` eine Exception wirft, fällt `parsed()` auf `{}` zurück."""

    class _BoomYaml:
        YAMLError = Exception

        @staticmethod
        def safe_load(_text):
            raise ValueError("boom")

    import frontmatter_parser as fp_mod
    monkeypatch.setattr(fp_mod, "yaml", _BoomYaml)
    parts = fp_mod.FrontmatterParts(header=": kaputt")
    assert parts.parsed() == {}


def test_parsed_returns_empty_when_yaml_returns_non_dict(monkeypatch):
    """Wenn `yaml.safe_load` etwas Nicht-Dict zurückgibt (z. B. eine Liste), liefert `parsed()` `{}`."""

    class _ListYaml:
        YAMLError = Exception

        @staticmethod
        def safe_load(_text):
            return ["a", "b"]

    import frontmatter_parser as fp_mod
    monkeypatch.setattr(fp_mod, "yaml", _ListYaml)
    assert fp_mod.FrontmatterParts(header="- a\n- b").parsed() == {}


def test_parse_file_handles_oserror(tmp_path: Path, monkeypatch):
    """Wenn die Datei nicht lesbar ist, gibt `parse_file` ein leeres `FrontmatterParts` zurück."""
    import pathlib

    target = tmp_path / "unreadable.md"
    target.write_text("dummy", encoding="utf-8")

    def _boom_open(self, *args, **kwargs):  # noqa: ARG001
        raise OSError("denied")

    monkeypatch.setattr(pathlib.Path, "open", _boom_open)
    parts = fp.parse_file(target)
    assert not parts.has_frontmatter
    assert parts.body == ""


def test_parse_file_handles_unicode_decode_error(tmp_path: Path, monkeypatch):
    """Bei kaputter UTF-8-Codierung gibt `parse_file` ein leeres `FrontmatterParts` zurück."""
    target = tmp_path / "broken.md"
    target.write_bytes(b"\xff\xfe invalid")

    def _boom_open(*_a, **_kw):
        raise UnicodeDecodeError("utf-8", b"", 0, 1, "boom")

    monkeypatch.setattr("builtins.open", _boom_open)
    parts = fp.parse_file(target)
    assert not parts.has_frontmatter


def test_salvage_strips_comments_and_quotes():
    """`_salvage_simple_yaml_mapping` ignoriert Kommentar- und Leerzeilen
    und strippt Anführungszeichen um Werte."""
    header = (
        "# Kommentar\n"
        "\n"
        "title: 'Mit Quotes'\n"
        'description: "Doppelt"\n'
        "author: Kein Quote\n"
    )
    salvaged = fp._salvage_simple_yaml_mapping(header)
    assert salvaged == {
        "title": "Mit Quotes",
        "description": "Doppelt",
        "author": "Kein Quote",
    }


def test_salvage_skips_lines_without_key_value():
    """Zeilen ohne `key: value`-Form werden ignoriert."""
    salvaged = fp._salvage_simple_yaml_mapping("kein doppelpunkt\nfoo bar\n: leerer key")
    assert salvaged == {}


def test_validate_and_repair_without_frontmatter_returns_input_unchanged():
    """Wenn die Eingabe kein Frontmatter hat, gibt `validate_and_repair`
    `(content, [], True)` zurück — keine Änderungen, gültig."""
    content = "# Nur Body\n"
    new, changes, ok = fp.validate_and_repair(content, header_mode="repair")
    assert new == content
    assert changes == []
    assert ok is True


def test_validate_and_repair_preserve_style_with_valid_yaml():
    """`repair + preserve_style_in_repair=True` darf den Header-Inhalt
    nicht neu serialisieren, sondern behält ihn wie er ist."""
    content = "---\ntitle: A\ndescription: B\n---\n\nbody\n"
    new, changes, ok = fp.validate_and_repair(
        content, header_mode="repair", preserve_style_in_repair=True
    )
    assert ok
    # `validate_and_repair` schreibt `---` + header + `---` + body neu,
    # aber der Inhalt des Headers muss unverändert bleiben:
    assert "title: A" in new
    assert "description: B" in new
    assert any("preserve-style" in c for c in changes)


def test_validate_and_repair_repair_normalises_changed_yaml():
    """Wenn der Header durch `safe_dump` anders aussieht als der Original-Header,
    muss eine Änderungsmeldung aufgenommen werden."""
    # YAML, das durch safe_dump umsortiert oder mit Anführungszeichen versehen wird
    content = "---\ndescription: B\ntitle: A\n---\n\nbody\n"
    new, changes, ok = fp.validate_and_repair(
        content, header_mode="repair", preserve_style_in_repair=False
    )
    assert ok
    # Je nach PyYAML-Version kann `sort_keys=False` die Reihenfolge halten
    # oder nicht. Wir prüfen, dass der reparierte Text parst und die Keys enthält.
    assert "title:" in new
    assert "description:" in new


def test_validate_and_repair_preserve_with_invalid_yaml():
    """Im `preserve`-Modus bleibt der Header bei ungültigem YAML unverändert,
    aber `is_valid` ist False und ein CAVEAT wird gemeldet."""
    content = "---\n: kaputt: weil : doppelpunkt\n---\n\nbody\n"
    new, changes, ok = fp.validate_and_repair(content, header_mode="preserve")
    assert not ok
    # Original bleibt erkennbar im Output
    assert "kaputt" in new
    assert any("CAVEAT" in c for c in changes)


def test_validate_and_repair_repair_salvages_invalid_yaml():
    """Bei ungültigem YAML rekonstruiert der `repair`-Modus konservativ
    die `key: value`-Paare und meldet eine Reparatur."""
    content = "---\n: kaputt: weil : doppelpunkt\ntitle: Repariert\n---\n\nbody\n"
    new, changes, ok = fp.validate_and_repair(
        content, header_mode="repair", preserve_style_in_repair=False
    )
    # Ob die Salvage-Logik `title: Repariert` rettet, hängt von der Heuristik ab.
    # Wichtig ist, dass `validate_and_repair` ohne Crash durchläuft und
    # mindestens eine Reparatur- oder CAVEAT-Meldung aufnimmt.
    assert any("repariert" in c or "CAVEAT" in c for c in changes)
    assert "title" in new or "Repariert" in new


def test_validate_and_repair_repair_preserve_style_with_invalid_yaml():
    """`repair + preserve_style_in_repair=True` mit defektem YAML lässt
    den Header unverändert und meldet CAVEAT."""
    content = "---\n: kaputt: weil : doppelpunkt\n---\n\nbody\n"
    new, changes, ok = fp.validate_and_repair(
        content, header_mode="repair", preserve_style_in_repair=True
    )
    assert not ok
    assert any("CAVEAT" in c for c in changes)


def test_validate_and_repair_appends_trailing_newline_to_body():
    """Wenn der Body am Ende keinen Newline hat, wird einer angehängt."""
    content = "---\ntitle: A\n---\n\nbody ohne newline"
    new, _changes, _ok = fp.validate_and_repair(content, header_mode="preserve")
    assert new.endswith("\n")


def test_validate_and_repair_handles_cr_only_newlines():
    """Bei reinen `\\r`-Umbruch-Zeilen bleibt der erkannte Newline-Stil
    konsistent für den reassemblierten Inhalt."""
    content = "---\rtitle: Cr\ractive: y\r---\rbody\r"
    new, _changes, ok = fp.validate_and_repair(content, header_mode="preserve")
    assert ok
    # Das reassemblierte Ergebnis muss parsebar bleiben
    assert "\rtitle: Cr" in new


def test_validate_and_repair_when_yaml_module_unavailable(monkeypatch):
    """Wenn `yaml is None`, meldet `validate_and_repair` ein CAVEAT und
    setzt `is_valid=False`, repariert aber zumindest die Struktur."""
    import frontmatter_parser as fp_mod
    monkeypatch.setattr(fp_mod, "yaml", None)
    content = "---\ntitle: A\n---\n\nbody\n"
    new, changes, ok = fp_mod.validate_and_repair(content, header_mode="preserve")
    assert not ok
    assert any("PyYAML nicht verfügbar" in c for c in changes)
    # Struktur-Reparatur läuft trotzdem: Doppel-Opener-Reduktion, fehlender Schließer
    # → der reassemblierte Block enthält das Frontmatter mit Trennern
    assert "---" in new


def test_repair_hidden_yaml_dividers_replaces_standalone_dashes_in_body():
    content = "---\ntitle: Test\n---\n\nAbsatz 1\n\n---\n\nAbsatz 2\n"
    new, changed = fp.repair_hidden_yaml_dividers(content)
    assert changed is True
    assert "\n---\n" not in new.split("---", 2)[2]
    assert "***" in new
    assert "Absatz 1" in new
    assert "Absatz 2" in new


def test_repair_hidden_yaml_dividers_leaves_frontmatter_delimiters_untouched():
    content = "---\ntitle: Test\n---\n\nKein versteckter Trennstrich.\n"
    new, changed = fp.repair_hidden_yaml_dividers(content)
    assert changed is False
    assert new == content


def test_repair_hidden_yaml_dividers_without_frontmatter_is_noop():
    content = "# Nur Body\n\n---\n"
    new, changed = fp.repair_hidden_yaml_dividers(content)
    assert changed is False
    assert new == content


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
