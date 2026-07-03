"""Tests fuer Phase 2 / Schritt 2.5a: BackupService.

Deckt die *reinen Daten-Pfade* der Sanitizer-Pipeline ab:
- Pfad-Aufloesung (Default, custom)
- Zeitstempel-Berechnung
- End-Pfad-Konstruktion
- Wrapper fuer `BackupManager` (create_structure_backup, get_sanitizer_backup_dir)

Schreib-Operationen (`shutil.copytree`), UI-Calls (`messagebox`,
`self.log`, `self.root.after`) und Threading bleiben in
`book_studio.run_sanitizer_pipeline` (Schritt 2.5b).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from subprocess import PIPE, STDOUT
from types import SimpleNamespace

import pytest

from services.backup_service import (
    BackupService,
    SANITIZER_BACKUP_DIR_NAME_TEMPLATE,
    SANITIZER_BACKUP_DIR_PREFIX,
    SANITIZER_BACKUP_TIMESTAMP_FMT,
    default_sanitizer_backup_dir,
)


# --- Helpers ---------------------------------------------------------------


def _make_studio(current_book=None, backup_mgr=None) -> SimpleNamespace:
    return SimpleNamespace(
        current_book=current_book,
        backup_mgr=backup_mgr,
    )


# --- resolve_backup_base_dir ---------------------------------------------


def test_resolve_returns_none_when_no_current_book():
    """Ohne aktives Buch ist die Aufloesung `None`."""
    assert BackupService.resolve_backup_base_dir(None, None) is None
    assert BackupService.resolve_backup_base_dir(None, "C:/foo") is None


def test_resolve_uses_custom_path_when_provided():
    """Ein nicht-leerer Custom-Pfad ueberschreibt den Default."""
    book = Path("C:/books/my_book")
    result = BackupService.resolve_backup_base_dir(book, "D:/backups")
    assert result == Path("D:/backups")


def test_resolve_uses_custom_path_with_surrounding_whitespace():
    """Whitespace um `custom_path` wird getrimmt."""
    book = Path("C:/books/my_book")
    result = BackupService.resolve_backup_base_dir(book, "  D:/backups  ")
    assert result == Path("D:/backups")


def test_resolve_falls_back_to_default_for_empty_custom_path():
    """Ein leerer oder whitespace-only Custom-Pfad faellt auf den Default zurueck."""
    book = Path("C:/books/my_book")
    expected = book.parent / f"{SANITIZER_BACKUP_DIR_PREFIX}{book.name}"
    assert BackupService.resolve_backup_base_dir(book, "") == expected
    assert BackupService.resolve_backup_base_dir(book, "   ") == expected


def test_resolve_falls_back_to_default_for_none_custom_path():
    """`None` als Custom-Pfad nimmt den Default."""
    book = Path("C:/books/my_book")
    expected = book.parent / f"{SANITIZER_BACKUP_DIR_PREFIX}{book.name}"
    assert BackupService.resolve_backup_base_dir(book, None) == expected


def test_resolve_falls_back_to_default_for_non_string_custom_path():
    """Wenn `custom_path` kein String ist (defensiv), faellt die Logik auf Default zurueck."""
    book = Path("C:/books/my_book")
    expected = book.parent / f"{SANITIZER_BACKUP_DIR_PREFIX}{book.name}"
    # Defensive: ein Aufrufer koennte versehentlich einen Nicht-String reichen.
    assert BackupService.resolve_backup_base_dir(book, 123) == expected  # type: ignore[arg-type]


# --- default_sanitizer_backup_dir_for ------------------------------------


def test_default_dir_uses_book_parent_and_name():
    book = Path("C:/books/my_book")
    result = BackupService.default_sanitizer_backup_dir_for(book)
    assert result == Path("C:/books/_Sanitizer_Backups_my_book")


def test_default_dir_handles_unix_path():
    book = Path("/home/u/proj/Band_A")
    result = BackupService.default_sanitizer_backup_dir_for(book)
    assert result == Path("/home/u/proj/_Sanitizer_Backups_Band_A")


# --- compute_backup_timestamp --------------------------------------------


def test_compute_timestamp_uses_injected_now():
    """Mit injiziertem `now` ist die Funktion deterministisch."""
    fixed = datetime(2026, 7, 3, 17, 55)  # 03.07.2026 17:55
    result = BackupService.compute_backup_timestamp(fixed)
    assert result == "030726_1755"


def test_compute_timestamp_format_constant_matches():
    """Das Format-String-Format-Konstante und der tatsaechliche Output sind konsistent."""
    fixed = datetime(2026, 12, 31, 23, 59)
    expected = fixed.strftime(SANITIZER_BACKUP_TIMESTAMP_FMT)
    assert BackupService.compute_backup_timestamp(fixed) == expected


def test_compute_timestamp_without_now_uses_datetime_now(monkeypatch):
    """Ohne Injektion wird `datetime.now()` aufgerufen."""
    sentinel = datetime(2026, 1, 2, 3, 4)

    class _StubDatetime:
        @classmethod
        def now(cls):
            return sentinel

    import services.backup_service as bs
    monkeypatch.setattr(bs, "datetime", _StubDatetime)
    assert BackupService.compute_backup_timestamp() == "020126_0304"


# --- build_backup_path ---------------------------------------------------


def test_build_backup_path_joins_base_dir_and_template():
    base = Path("C:/backups")
    ts = "030726_1755"
    result = BackupService.build_backup_path(base, ts)
    assert result == Path("C:/backups/sanitizer_backup_030726_1755")


def test_build_backup_path_uses_template_constant():
    """Der End-Ordnername folgt exakt dem SANITIZER_BACKUP_DIR_NAME_TEMPLATE."""
    base = Path("C:/backups")
    ts = "x"
    expected_name = SANITIZER_BACKUP_DIR_NAME_TEMPLATE.format(timestamp=ts)
    assert BackupService.build_backup_path(base, ts).name == expected_name


def test_build_backup_path_accepts_empty_timestamp():
    """Ein leerer Timestamp erzeugt einen End-Pfad mit dem Praefix
    `sanitizer_backup_` (nicht validiert)."""
    base = Path("C:/backups")
    result = BackupService.build_backup_path(base, "")
    assert result == Path("C:/backups/sanitizer_backup_")


# --- Konstanten ----------------------------------------------------------


def test_constants_have_expected_values():
    """Sanity-Check: Konstanten haben die Werte, die das Studio erwartet."""
    assert SANITIZER_BACKUP_DIR_PREFIX == "_Sanitizer_Backups_"
    assert SANITIZER_BACKUP_TIMESTAMP_FMT == "%d%m%y_%H%M"
    assert SANITIZER_BACKUP_DIR_NAME_TEMPLATE == "sanitizer_backup_{timestamp}"


# --- Wrapper: create_structure_backup ------------------------------------


def test_create_structure_backup_returns_empty_when_no_backup_mgr():
    studio = _make_studio(backup_mgr=None)
    svc = BackupService(studio)
    assert svc.create_structure_backup([{"a": 1}]) == ""


def test_create_structure_backup_delegates_to_backup_mgr():
    captured = {}

    def fake_create(tree_data):
        captured["tree_data"] = tree_data
        return "BACKUP_NAME_42"

    studio = _make_studio(backup_mgr=SimpleNamespace(create_structure_backup=fake_create))
    svc = BackupService(studio)
    result = svc.create_structure_backup([{"x": "y"}])
    assert result == "BACKUP_NAME_42"
    assert captured["tree_data"] == [{"x": "y"}]


# --- Wrapper: get_sanitizer_backup_dir ----------------------------------


def test_get_sanitizer_backup_dir_returns_none_when_no_current_book():
    studio = _make_studio(current_book=None)
    svc = BackupService(studio)
    assert svc.get_sanitizer_backup_dir() is None


def test_get_sanitizer_backup_dir_uses_default():
    book = Path("C:/books/Alpha")
    studio = _make_studio(current_book=book)
    svc = BackupService(studio)
    expected = book.parent / f"{SANITIZER_BACKUP_DIR_PREFIX}{book.name}"
    assert svc.get_sanitizer_backup_dir() == expected


# --- Modul-Level-Helper -------------------------------------------------


def test_module_level_default_helper_none():
    assert default_sanitizer_backup_dir(None) is None


def test_module_level_default_helper_returns_dir():
    book = Path("C:/books/Alpha")
    expected = book.parent / f"{SANITIZER_BACKUP_DIR_PREFIX}{book.name}"
    assert default_sanitizer_backup_dir(book) == expected


# --- create_physical_backup (Phase 2 / Schritt 2.5b) ---------------------


def test_create_physical_backup_copies_content_dir(tmp_path):
    content = tmp_path / "content"
    content.mkdir()
    (content / "kap.md").write_text("# X", encoding="utf-8")
    (content / "sub").mkdir()
    (content / "sub" / "deep.md").write_text("# Y", encoding="utf-8")

    base = tmp_path / "backups"
    target = base / "sanitizer_backup_030726_1755"

    result, err = BackupService.create_physical_backup(content, base, target)
    assert err is None
    assert result == target
    assert target.exists()
    assert (target / "kap.md").read_text(encoding="utf-8") == "# X"
    assert (target / "sub" / "deep.md").read_text(encoding="utf-8") == "# Y"
    assert base.exists()


def test_create_physical_backup_creates_parent_dirs(tmp_path):
    content = tmp_path / "content"
    content.mkdir()
    (content / "a.md").write_text("a", encoding="utf-8")
    base = tmp_path / "deep" / "nested" / "backups"  # existiert nicht
    target = base / "snap"

    result, err = BackupService.create_physical_backup(content, base, target)
    assert err is None
    assert result == target
    assert target.exists()
    assert base.exists()


def test_create_physical_backup_returns_error_when_content_missing(tmp_path):
    content = tmp_path / "missing_content"  # nicht angelegt
    base = tmp_path / "backups"
    target = base / "snap"
    result, err = BackupService.create_physical_backup(content, base, target)
    assert result is None
    assert err is not None
    assert "content" in err.lower()


def test_create_physical_backup_returns_error_when_content_is_file(tmp_path):
    content = tmp_path / "not_a_dir.md"
    content.write_text("x", encoding="utf-8")
    base = tmp_path / "backups"
    target = base / "snap"
    result, err = BackupService.create_physical_backup(content, base, target)
    assert result is None
    assert err is not None
    assert "content" in err.lower()


def test_create_physical_backup_handles_string_paths(tmp_path):
    content = tmp_path / "content"
    content.mkdir()
    (content / "x.md").write_text("a", encoding="utf-8")
    base = tmp_path / "backups"
    target = base / "snap"

    # Strings statt Path-Objekte
    result, err = BackupService.create_physical_backup(
        str(content), str(base), str(target)
    )
    assert err is None
    assert Path(result) == target
    assert (target / "x.md").read_text(encoding="utf-8") == "a"


def test_create_physical_backup_existing_target_raises_oserror(tmp_path):
    content = tmp_path / "content"
    content.mkdir()
    (content / "x.md").write_text("a", encoding="utf-8")
    base = tmp_path / "backups"
    base.mkdir()
    target = base / "snap"
    target.mkdir()  # existiert bereits -> shutil.Error oder FileExistsError

    result, err = BackupService.create_physical_backup(content, base, target)
    assert result is None
    assert err is not None


# --- Phase 4: Sanitizer-Subprocess ------------------------------------------


class _MockSanitizerPopen:
    """Mock fuer subprocess.Popen im Sanitizer-Pfad."""

    def __init__(self, lines, returncode=0):
        self.stdout = iter(lines)
        self.returncode = returncode
        self.waited = False
        self.kwargs = {}

    def wait(self):
        self.waited = True


def _popen_factory(lines, returncode=0):
    """Factory, die _MockSanitizerPopen baut und Instanzen sammelt."""
    instances = []

    def _factory(*args, **kwargs):
        proc = _MockSanitizerPopen(lines, returncode=returncode)
        proc.kwargs = kwargs
        instances.append(proc)
        return proc

    _factory.instances = instances  # type: ignore[attr-defined]
    return _factory


def test_build_sanitizer_command_minimal(tmp_path):
    """build_sanitizer_command liefert [executable, script, book]."""
    cmd = BackupService.build_sanitizer_command(
        executable=tmp_path / "python.exe",
        book=tmp_path / "my-book",
    )
    assert cmd[0] == str(tmp_path / "python.exe")
    assert cmd[1] == "Sanitizer.py"
    assert cmd[2] == str(tmp_path / "my-book")


def test_build_sanitizer_command_custom_script(tmp_path):
    """Der Skript-Name ist ueberschreibbar."""
    cmd = BackupService.build_sanitizer_command(
        executable=tmp_path / "python.exe",
        book=tmp_path,
        script_name="Custom.py",
    )
    assert cmd[1] == "Custom.py"


def test_run_sanitizer_subprocess_streams_lines(tmp_path):
    """Nicht-leere Zeilen landen in on_log_line."""
    popen = _popen_factory(["line 1\n", "\n", "  \n", "line 2\n"], returncode=0)
    log_lines = []

    rc = BackupService.run_sanitizer_subprocess(
        book=tmp_path,
        on_log_line=log_lines.append,
        popen_factory=popen,
    )

    assert rc == 0
    assert log_lines == ["line 1", "line 2"]
    assert popen.instances[0].waited is True


def test_run_sanitizer_subprocess_passes_cwd(tmp_path):
    """cwd-Argument wird an popen_factory weitergereicht."""
    popen = _popen_factory([], returncode=0)
    cwd = tmp_path / "work"

    BackupService.run_sanitizer_subprocess(
        book=tmp_path,
        on_log_line=lambda _l: None,
        cwd=cwd,
        popen_factory=popen,
    )

    kwargs = popen.instances[0].kwargs
    assert kwargs.get("cwd") == str(cwd)
    # Popen-spezifische kwargs muessen ebenfalls gesetzt sein.
    assert kwargs.get("stdout") == PIPE
    assert kwargs.get("stderr") == STDOUT
    assert kwargs.get("text") is True
    assert kwargs.get("bufsize") == 1


def test_run_sanitizer_subprocess_handles_none_stdout(tmp_path):
    """Subprocess ohne .stdout wird ohne Crash akzeptiert."""
    proc = SimpleNamespace(stdout=None, returncode=0)
    proc.wait = lambda: setattr(proc, "waited", True)

    rc = BackupService.run_sanitizer_subprocess(
        book=tmp_path,
        on_log_line=lambda _l: None,
        popen_factory=lambda *a, **k: proc,
    )
    assert rc == 0


def test_run_sanitizer_subprocess_returns_returncode(tmp_path):
    """Der returncode des Subprocess wird 1:1 zurueckgegeben."""
    popen = _popen_factory([], returncode=7)
    rc = BackupService.run_sanitizer_subprocess(
        book=tmp_path,
        on_log_line=lambda _l: None,
        popen_factory=popen,
    )
    assert rc == 7


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
