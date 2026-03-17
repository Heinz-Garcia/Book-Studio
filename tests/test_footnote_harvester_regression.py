from footnote_harvester import FootnoteHarvester


def test_extract_definitions_is_linear_and_preserves_body_text() -> None:
    harvester = FootnoteHarvester(mode="endnotes")
    text = (
        "Einleitung\n"
        "[^a]: Erste Notiz\n"
        "  zweite Zeile\n"
        "\n"
        "Weiterer Text\n"
        "[^b]: Zweite Notiz\n"
        "Schluss\n"
    )

    cleaned = harvester.extract_definitions(text, file_key="content/a.md")

    assert "[^a]:" not in cleaned
    assert "[^b]:" not in cleaned
    assert "Einleitung" in cleaned
    assert "Weiterer Text" in cleaned
    assert "Schluss" in cleaned
    assert harvester.definitions[("content/a.md", "a")] == "Erste Notiz\n  zweite Zeile"
    assert harvester.definitions[("content/a.md", "b")] == "Zweite Notiz"


def test_extract_definitions_accepts_lightly_indented_definition() -> None:
    harvester = FootnoteHarvester(mode="endnotes")
    text = "Text\n [^x]: Leicht eingerückt\nMehr Text\n"

    cleaned = harvester.extract_definitions(text, file_key="content/b.md")

    assert "[^x]:" not in cleaned
    assert "Text" in cleaned
    assert "Mehr Text" in cleaned
    assert harvester.definitions[("content/b.md", "x")] == "Leicht eingerückt"
