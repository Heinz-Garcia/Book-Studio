"""Tests für tools.publish_readiness."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.publish_readiness.analysis import build_readiness_report, enrich_analysis, save_readiness_report
from tools.publish_readiness.taxonomy import (
    CONTRACT_IDS,
    classify_message,
    covered_contract_ids,
    missing_contract_ids,
)


# Repräsentative Doktor-/Preflight-Texte je Quality-Contract-Satz (#1–20).
_CONTRACT_SAMPLES: dict[int, str] = {
    1: "❌ Root: 'index.md' fehlt komplett!",
    2: "❌ Geister-Datei: 'Kapitel' (kap.md) existiert nicht.",
    3: "❌ Frontmatter-Fehler: 'Kapitel' (kap.md) hat gar keinen YAML Titel.",
    4: "❌ FRONTMATTER DEFEKT in 'Kapitel': Die '---' Blöcke umschließen den Bereich nicht sauber.",
    5: "❌ LEERES FRONTMATTER in 'Kapitel': Der YAML-Block ist leer.",
    6: "❌ FEHLENDES FELD in 'Kapitel': Das Pflichtfeld 'title' fehlt im Frontmatter.",
    7: "❌ YAML-CRASH in 'Kapitel': Quarto wird hier abbrechen!",
    8: "❌ VERSTECKTER TRENNSTRICH in 'Kapitel': Quarto stürzt bei '---' im Text ab.",
    9: "❌ FENCED-DIV FEHLER: Öffnender :::-Marker ohne passenden Abschluss. in 'Kapitel'",
    10: "Hinweis: [BOX: prompt] noch nicht konvertiert",
    11: "Zitation [@Key] wird beim Render aufgelöst",
    12: "❌ FRAGILER BILDPFAD in 'Kapitel' (kap.md): Bildpfad 'img/x.png' ist relativ zur Datei",
    13: "🖼 Fehlende Bildreferenz: img/fehlt.png",
    14: "Hinweis: order' ist ein String — Pre-Processor wandelt um",
    15: "[safe-render] Hinweis: book.author fehlte – Platzhalter gesetzt",
    16: "ℹ️ 3 Dateien liegen im linken Pool und werden nicht gerendert — das ist in Ordnung.",
    17: "Hinweis: buch_master.md liegt im Buch-Root (GrammarGraph-Payload)",
    18: "Import: Inline-SVG in Kapitel extrahiert",
    19: "❌ FENCED-DIV FEHLER: … in 'Kapitel' (nach Pre-Processing)",
    20: "Hinweis: gui_state weicht von _quarto.yml ab",
}


def test_taxonomy_covers_all_quality_contract_ids():
    assert missing_contract_ids() == frozenset()
    assert covered_contract_ids() == CONTRACT_IDS


def test_classify_every_contract_sample_maps_to_its_id():
    for contract_id, message in _CONTRACT_SAMPLES.items():
        meta = classify_message(message)
        assert meta["contract_id"] == contract_id, (
            f"#{contract_id} erwartet für {message!r}, got {meta}"
        )


def test_classify_fragile_image_path():
    meta = classify_message("❌ FRAGILER BILDPFAD in 'Kapitel' (kap.md): ...")
    assert meta["owner"] == "GG"
    assert meta["fix_lane"] == "grammargraph_export"
    assert meta["severity"] == "blocker"
    assert meta["contract_id"] == 12


def test_classify_fenced_div_uses_sanitizer_lane():
    meta = classify_message(
        "❌ FENCED-DIV FEHLER: Öffnender :::-Marker ohne passenden Abschluss."
    )
    assert meta["contract_id"] == 9
    assert meta["fix_lane"] == "sanitizer"


def test_classify_unmatched_error_icon_is_blocker():
    meta = classify_message("❌ Unbekannter Render-Abbruch in kapitel.md")
    assert meta["severity"] == "blocker"
    assert meta["contract_id"] == 0


def test_classify_box_marker_from_quality_contract():
    meta = classify_message("Hinweis: [BOX: prompt] noch nicht konvertiert")
    assert meta["owner"] == "GG"
    assert meta["severity"] == "warning"
    assert meta["contract_id"] == 10


def test_enrich_analysis_groups_by_path():
    analysis = {
        "is_healthy": False,
        "error_count": 1,
        "warning_count": 0,
        "issues_by_path": {
            "kap.md": ["❌ FRAGILER BILDPFAD in 'Kapitel' (kap.md): img/x.png"],
        },
        "issue_details_by_path": {
            "kap.md": [
                {"message": "❌ FRAGILER BILDPFAD in 'Kapitel' (kap.md): img/x.png", "line_number": 5},
            ],
        },
    }
    enriched = enrich_analysis(analysis)
    assert len(enriched) == 1
    assert enriched[0]["owner"] == "GG"
    assert enriched[0]["line_number"] == 5


def test_enrich_analysis_includes_warnings_without_path():
    analysis = {
        "is_healthy": True,
        "error_count": 0,
        "warning_count": 1,
        "issues_by_path": {},
        "warnings": ["ℹ️ 3 Dateien liegen im linken Pool und werden nicht gerendert — das ist in Ordnung."],
    }
    enriched = enrich_analysis(analysis)
    assert len(enriched) == 1
    assert enriched[0]["severity"] == "info"
    assert enriched[0]["path"] == "—"


def test_save_readiness_report(tmp_path):
    book = tmp_path / "book"
    book.mkdir()
    report = build_readiness_report(
        {"is_healthy": True, "error_count": 0, "warning_count": 0, "issues_by_path": {}},
        context_label="Test",
        book_path=book,
    )
    path = save_readiness_report(book, report)
    assert path.is_file()
    assert path.parent.name == "reports"


# ---------------------------------------------------------------------------
# Ein Blocker bleibt ein Blocker
# ---------------------------------------------------------------------------
#
# Regression: Die Info-Pruefung stand vor der Blocker-Pruefung und testete auf
# das *Teilwort* "info". Jede unklassifizierte Fehlermeldung, in der "Info"
# oder "Information" vorkam, wurde damit zum blossen Hinweis heruntergestuft --
# in einem Werkzeug, das vor der Veroeffentlichung Blocker zeigen soll,
# verschwand der Befund aus genau der Liste, die man abarbeitet.


@pytest.mark.parametrize(
    "meldung, erwartet",
    [
        ("\u274c Datei-Info nicht lesbar", "blocker"),
        ("\u26d4 Infobox ohne Abschluss", "blocker"),
        ("\u274c Rendern fehlgeschlagen: Informationen fehlen", "blocker"),
        ("\u274c Kapitel bricht den Satz", "blocker"),
        ("\u2139\ufe0f Nur ein Hinweis", "info"),
        ("Info: nur zur Kenntnis", "info"),
        ("Etwas anderes", "warning"),
    ],
)
def test_error_icon_beats_the_word_info(meldung, erwartet):
    from tools.publish_readiness.taxonomy import classify_message

    assert classify_message(meldung)["severity"] == erwartet
