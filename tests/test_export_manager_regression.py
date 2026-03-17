from __future__ import annotations

from pathlib import Path

import export_manager
from export_manager import ExportManager


class _FakeStatus:
    def __init__(self):
        self.last = None

    def config(self, **kwargs):
        self.last = kwargs


class _FakeStudio:
    def __init__(self):
        self.current_book = object()
        self.root = object()
        self.available_templates = ["Standard"]
        self.last_export_options = {}
        self.status = _FakeStatus()
        self.logged = []
        self.preflight_calls = []
        self.save_calls = []

    def run_doctor_preflight(self, context_label, emit_success_log=False):
        self.preflight_calls.append((context_label, emit_success_log))
        return False, {"error_count": 1}

    def log(self, message, level="info"):
        self.logged.append((message, level))

    def persist_app_state(self):
        raise AssertionError("persist_app_state should not be called when preflight fails")

    def save_project(self, **kwargs):
        self.save_calls.append(kwargs)
        raise AssertionError("save_project should not be called when preflight fails")


def test_run_quarto_render_stops_immediately_on_doctor_preflight_failure() -> None:
    studio = _FakeStudio()
    manager = ExportManager(studio)

    manager.run_quarto_render()

    assert studio.preflight_calls == [("Render-Vorabcheck", False)]
    assert studio.save_calls == []
    assert any("Rendern abgebrochen" in message for message, _level in studio.logged)
    assert studio.status.last == {
        "text": "Render abgebrochen (Buch-Doktor-Befund)",
        "fg": "#e74c3c",
    }


def test_candidate_registry_paths_for_processed_file_maps_to_content(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()

    class Studio:
        current_book = book

    manager = ExportManager(Studio())

    abs_file = book / "processed" / "content" / "required" / "pladoyer.md"
    candidates = manager.candidate_registry_paths_for_error_file(abs_file)

    assert candidates == [
        "processed/content/required/pladoyer.md",
        "content/required/pladoyer.md",
    ]


def test_resolve_error_file_title_prefers_registry_title_for_processed_path(tmp_path: Path) -> None:
    book = tmp_path / "book"
    (book / "processed" / "content" / "required").mkdir(parents=True)
    abs_file = book / "processed" / "content" / "required" / "pladoyer.md"
    abs_file.write_text("# Fallback", encoding="utf-8")

    class Studio:
        current_book = book
        title_registry = {"content/required/pladoyer.md": "Plädoyer Titel"}
        yaml_engine = None

    manager = ExportManager(Studio())

    title, shown_path = manager.resolve_error_file_title(abs_file)

    assert title == "Plädoyer Titel"
    assert shown_path == "content/required/pladoyer.md"


def test_run_quarto_render_logs_affected_title_for_error_line(tmp_path: Path, monkeypatch) -> None:
    book = tmp_path / "book"
    (book / "processed" / "content" / "required").mkdir(parents=True)
    error_file = (book / "processed" / "content" / "required" / "pladoyer.md").resolve()
    error_file.write_text("# Dummy", encoding="utf-8")

    class Root:
        def after(self, _delay, callback):
            callback()

    class Status:
        def __init__(self):
            self.last = None

        def config(self, **kwargs):
            self.last = kwargs

    class YamlEngine:
        def save_chapters(self, *_args, **_kwargs):
            return None

        def extract_title_from_md(self, _path):
            return "Fallback Titel"

    class Studio:
        def __init__(self):
            self.current_book = book
            self.root = Root()
            self.available_templates = ["Standard"]
            self.last_export_options = {}
            self.status = Status()
            self.logged = []
            self.current_profile_name = "default"
            self.yaml_engine = YamlEngine()
            self.title_registry = {"content/required/pladoyer.md": "Plädoyer Titel"}

        def run_doctor_preflight(self, _context_label, emit_success_log=False):
            return True, {"error_count": 0, "emit_success_log": emit_success_log}

        def persist_app_state(self):
            return None

        def save_project(self, **_kwargs):
            return True

        def get_tree_data_for_engine(self):
            return []

        def log(self, message, level="info"):
            self.logged.append((message, level))

    class FakePreProcessor:
        def __init__(self, *_args, **_kwargs):
            self.harvester = type("Harvester", (), {"orphan_warnings": []})()

        def prepare_render_environment(self, tree):
            return tree

    class FakePopen:
        def __init__(self, *_args, **_kwargs):
            self.stdout = [f"ERROR: In file {error_file}\n"]
            self.returncode = 1

        def wait(self):
            return self.returncode

    class ImmediateThread:
        def __init__(self, target, daemon=False):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    monkeypatch.setattr(export_manager.ExportDialog, "ask", staticmethod(lambda *_args, **_kwargs: {
        "format": "typst",
        "footnote_mode": "none",
        "template": "Standard",
    }))
    monkeypatch.setattr(export_manager, "PreProcessor", FakePreProcessor)
    monkeypatch.setattr(export_manager.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(export_manager.threading, "Thread", ImmediateThread)

    studio = Studio()
    manager = ExportManager(studio)

    manager.run_quarto_render()

    assert any(
        "Betroffener Titel: Plädoyer Titel [content/required/pladoyer.md]" in message
        and level == "error"
        for message, level in studio.logged
    )


def test_collect_processed_fenced_div_hits_reports_source_file_and_line(tmp_path: Path) -> None:
    book = tmp_path / "book"
    processed_file = book / "processed" / "content" / "required" / "kapitel.md"
    processed_file.parent.mkdir(parents=True, exist_ok=True)
    processed_file.write_text(
        "---\n"
        "title: Kapitel\n"
        "---\n\n"
        "Text\n"
        "::: {.callout-note}\n"
        "Inhalt\n"
        ":::\n",
        encoding="utf-8",
    )

    class Studio:
        current_book = book
        title_registry = {"content/required/kapitel.md": "Kapitel"}

    manager = ExportManager(Studio())

    findings = manager.collect_processed_fenced_div_hits(
        [{"path": "processed/content/required/kapitel.md", "children": []}]
    )

    assert findings == []


def test_collect_processed_fenced_div_hits_flags_unclosed_opening(tmp_path: Path) -> None:
    book = tmp_path / "book"
    processed_file = book / "processed" / "content" / "kapitel.md"
    processed_file.parent.mkdir(parents=True, exist_ok=True)
    processed_file.write_text(
        "Text\n"
        "::: {.callout-note}\n"
        "Inhalt ohne Ende\n",
        encoding="utf-8",
    )

    class Studio:
        current_book = book
        title_registry = {"content/kapitel.md": "Kapitel"}

    manager = ExportManager(Studio())

    findings = manager.collect_processed_fenced_div_hits(
        [{"path": "processed/content/kapitel.md", "children": []}]
    )

    assert len(findings) == 1
    assert findings[0]["source_path"] == "content/kapitel.md"
    assert findings[0]["line_number"] == 2
    assert findings[0]["issue_kind"] == "unclosed-open"


def test_build_processed_label_occurrences_collects_label_locations(tmp_path: Path) -> None:
    book = tmp_path / "book"
    processed_file = book / "processed" / "content" / "chapter.md"
    processed_file.parent.mkdir(parents=True, exist_ok=True)
    processed_file.write_text(
        "Text @AlphaRef[S. 10]\n"
        "Noch ein Verweis @AlphaRef\n"
        "Anderer Verweis @BetaRef\n",
        encoding="utf-8",
    )

    class Studio:
        current_book = book
        title_registry = {"content/chapter.md": "Chapter"}

    manager = ExportManager(Studio())

    occurrences = manager.build_processed_label_occurrences(
        [{"path": "processed/content/chapter.md", "children": []}]
    )

    assert occurrences["AlphaRef"] == [
        ("content/chapter.md", 1),
        ("content/chapter.md", 2),
    ]
    assert occurrences["BetaRef"] == [("content/chapter.md", 3)]


def test_run_quarto_render_aborts_on_first_processed_preflight_error(tmp_path: Path, monkeypatch) -> None:
    book = tmp_path / "book"
    bad_processed = book / "processed" / "content" / "chapter.md"
    bad_processed.parent.mkdir(parents=True, exist_ok=True)
    bad_processed.write_text("::: {.callout-note}\nUnclosed\n", encoding="utf-8")

    class Root:
        def after(self, _delay, callback):
            callback()

    class Status:
        def __init__(self):
            self.last = None

        def config(self, **kwargs):
            self.last = kwargs

    class YamlEngine:
        def save_chapters(self, *_args, **_kwargs):
            return None

    class Studio:
        def __init__(self):
            self.current_book = book
            self.root = Root()
            self.available_templates = ["Standard"]
            self.last_export_options = {}
            self.status = Status()
            self.logged = []
            self.current_profile_name = "default"
            self.yaml_engine = YamlEngine()
            self.title_registry = {"content/chapter.md": "Chapter"}

        def run_doctor_preflight(self, _context_label, emit_success_log=False):
            return True, {"error_count": 0, "emit_success_log": emit_success_log}

        def persist_app_state(self):
            return None

        def save_project(self, **_kwargs):
            return True

        def get_tree_data_for_engine(self):
            return []

        def log(self, message, level="info"):
            self.logged.append((message, level))

    class FakePreProcessor:
        def __init__(self, *_args, **_kwargs):
            self.harvester = type("Harvester", (), {"orphan_warnings": []})()

        def prepare_render_environment(self, _tree):
            return [{"path": "processed/content/chapter.md", "children": []}]

    class GuardPopen:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("quarto must not start when preflight error exists")

    monkeypatch.setattr(export_manager.ExportDialog, "ask", staticmethod(lambda *_args, **_kwargs: {
        "format": "typst",
        "footnote_mode": "none",
        "template": "Standard",
    }))
    monkeypatch.setattr(export_manager, "PreProcessor", FakePreProcessor)
    monkeypatch.setattr(export_manager.subprocess, "Popen", GuardPopen)

    studio = Studio()
    manager = ExportManager(studio)

    manager.run_quarto_render()

    assert any("defekter ':::'-Block" in message for message, _level in studio.logged)
    assert studio.status.last == {
        "text": "Render abgebrochen (erster Preflight-Fehler)",
        "fg": "#e74c3c",
    }


def test_log_processed_fenced_div_hits_does_not_abort_when_config_disabled(tmp_path: Path) -> None:
    book = tmp_path / "book"
    processed_file = book / "processed" / "content" / "chapter.md"
    processed_file.parent.mkdir(parents=True, exist_ok=True)
    processed_file.write_text(
        "Text\n"
        "::: {.callout-note}\n"
        "Inhalt ohne Ende\n",
        encoding="utf-8",
    )

    class Studio:
        current_book = book
        title_registry = {"content/chapter.md": "Chapter"}

        def __init__(self):
            self.logged = []

        def log(self, message, level="info"):
            self.logged.append((message, level))

        def read_config(self):
            return {"abort_on_first_preflight_error": False}

    studio = Studio()
    manager = ExportManager(studio)

    should_abort = manager.log_processed_fenced_div_hits(
        [{"path": "processed/content/chapter.md", "children": []}]
    )

    assert should_abort is False
    assert any("defekter ':::'-Block" in message for message, _level in studio.logged)


def test_log_render_line_emits_missing_label_hints_for_backtick_format(tmp_path: Path) -> None:
    book = tmp_path / "book"

    class Studio:
        current_book = book
        title_registry = {"content/chapter.md": "Chapter"}

        def __init__(self):
            self.logged = []

        def log(self, message, level="info"):
            self.logged.append((message, level))

    studio = Studio()
    manager = ExportManager(studio)
    manager._processed_label_occurrences = {
        "AlphaRef": [("content/chapter.md", 42)],
    }

    manager._log_render_line("error: label `<AlphaRef>` does not exist in the document")

    assert any("Fehlendes Label <AlphaRef>" in message for message, _level in studio.logged)
    assert any("[content/chapter.md] L42" in message for message, _level in studio.logged)


def test_log_render_line_emits_source_hint_for_raw_valid_colon_warning(tmp_path: Path) -> None:
    book = tmp_path / "book"

    class Studio:
        current_book = book
        title_registry = {"content/chapter.md": "Chapter"}

        def __init__(self):
            self.logged = []

        def log(self, message, level="info"):
            self.logged.append((message, level))

    studio = Studio()
    manager = ExportManager(studio)
    manager._processed_colon_occurrences = [
        ("content/chapter.md", 23),
        ("content/chapter.md", 41),
    ]

    manager._log_render_line("The following string was found in the document: :::")

    assert any("Früher Treffer für ':::': keine strukturellen Defekte erkannt" in message for message, _level in studio.logged)
    assert any("👉 KLICK: [content/chapter.md] L23" in message for message, _level in studio.logged)


def test_log_render_line_emits_source_hint_for_structural_colon_warning(tmp_path: Path) -> None:
    book = tmp_path / "book"

    class Studio:
        current_book = book
        title_registry = {"content/chapter.md": "Chapter"}

        def __init__(self):
            self.logged = []

        def log(self, message, level="info"):
            self.logged.append((message, level))

    studio = Studio()
    manager = ExportManager(studio)
    manager._processed_colon_occurrences = [
        {
            "source_path": "content/chapter.md",
            "line_number": 23,
            "issue_kind": "unclosed-open",
            "is_structural": True,
        }
    ]

    manager._log_render_line("The following string was found in the document: :::")

    assert any("Früher Treffer für ':::': strukturell auffällige Stelle(n):" in message for message, _level in studio.logged)
    assert any("👉 KLICK: [content/chapter.md] L23" in message for message, _level in studio.logged)


def test_should_abort_on_first_render_colon_warning_uses_config_value(tmp_path: Path) -> None:
    book = tmp_path / "book"

    class Studio:
        current_book = book

        def read_config(self):
            return {"abort_on_first_render_colon_warning": True}

    manager = ExportManager(Studio())

    assert manager.should_abort_on_first_render_colon_warning() is True


def test_should_enable_footnote_backlinks_uses_config_value(tmp_path: Path) -> None:
    book = tmp_path / "book"

    class Studio:
        current_book = book

        def read_config(self):
            return {"enable_footnote_backlinks": False}

    manager = ExportManager(Studio())

    assert manager.should_enable_footnote_backlinks() is False


def test_is_raw_colon_warning_line_detects_quarto_warning_line() -> None:
    class Studio:
        current_book = None

    manager = ExportManager(Studio())

    assert manager.is_raw_colon_warning_line("The following string was found in the document: :::") is True
    assert manager.is_raw_colon_warning_line("INFO: something else") is False


def test_run_quarto_render_writes_detailed_render_log_file(tmp_path: Path, monkeypatch) -> None:
    book = tmp_path / "book"
    (book / "export").mkdir(parents=True, exist_ok=True)

    class Root:
        def after(self, _delay, callback):
            callback()

    class Status:
        def __init__(self):
            self.last = None

        def config(self, **kwargs):
            self.last = kwargs

    class YamlEngine:
        def save_chapters(self, *_args, **_kwargs):
            return None

    class Studio:
        def __init__(self):
            self.current_book = book
            self.root = Root()
            self.available_templates = ["Standard"]
            self.last_export_options = {}
            self.status = Status()
            self.logged = []
            self.current_profile_name = "default"
            self.yaml_engine = YamlEngine()
            self.title_registry = {}

        def run_doctor_preflight(self, _context_label, emit_success_log=False):
            return True, {"error_count": 0, "emit_success_log": emit_success_log}

        def persist_app_state(self):
            return None

        def save_project(self, **_kwargs):
            return True

        def get_tree_data_for_engine(self):
            return []

        def log(self, message, level="info"):
            self.logged.append((message, level))

    class FakePreProcessor:
        def __init__(self, *_args, **_kwargs):
            self.harvester = type("Harvester", (), {"orphan_warnings": []})()

        def prepare_render_environment(self, tree):
            return tree

    class FakePopen:
        def __init__(self, *_args, **_kwargs):
            self.stdout = ["quarto: render started\n", "quarto: render done\n"]
            self.returncode = 0

        def wait(self):
            return self.returncode

    class ImmediateThread:
        def __init__(self, target, daemon=False):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    monkeypatch.setattr(export_manager.ExportDialog, "ask", staticmethod(lambda *_args, **_kwargs: {
        "format": "typst",
        "footnote_mode": "endnotes",
        "template": "Standard",
    }))
    monkeypatch.setattr(export_manager, "PreProcessor", FakePreProcessor)
    monkeypatch.setattr(export_manager.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(export_manager.threading, "Thread", ImmediateThread)

    studio = Studio()
    manager = ExportManager(studio)

    manager.run_quarto_render()

    log_dir = book / "export" / "render_logs"
    log_files = list(log_dir.glob("render_*.log"))
    assert len(log_files) == 1
    content = log_files[0].read_text(encoding="utf-8")
    assert "=== Quarto Book Studio Render Log ===" in content
    assert "safe_command=" in content
    assert "quarto: render started" in content
    assert "quarto: render done" in content
    assert "status=success" in content
    assert "primary_returncode=0" in content