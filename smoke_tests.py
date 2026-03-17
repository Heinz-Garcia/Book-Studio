from __future__ import annotations

import argparse
import importlib
import shutil
import subprocess
import sys
import tempfile
import tkinter as tk
from pathlib import Path


def _ok(message: str):
    print(f"✅ {message}")


def _fail(message: str):
    print(f"❌ {message}")


def run_non_gui_smoke(project_root: Path) -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []

    def record(name: str, passed: bool, detail: str = ""):
        results.append((name, passed, detail))

    critical_files = [
        project_root / "version.txt",
        project_root / "studio_config.json",
        project_root / "book_studio.py",
        project_root / "yaml_engine.py",
    ]
    missing = [str(p.relative_to(project_root)) for p in critical_files if not p.exists()]
    if missing:
        record("Dateien vorhanden", False, f"Fehlen: {', '.join(missing)}")
    else:
        record("Dateien vorhanden", True)

    modules = [
        "yaml_engine",
        "search_filter",
        "markdown_asset_scanner",
        "dialog_dirty_utils",
        "unmanned_trigger",
    ]
    import_errors = []
    for module_name in modules:
        try:
            importlib.import_module(module_name)
        except (ImportError, AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:  # Smoke: nur Importstabilität
            import_errors.append(f"{module_name}: {exc}")

    if import_errors:
        record("Modul-Imports", False, " | ".join(import_errors))
    else:
        record("Modul-Imports", True)

    try:
        from yaml_engine import QuartoYamlEngine

        book_path = project_root / "Band_Dummy"
        engine = QuartoYamlEngine(book_path)
        registry = engine.build_title_registry()
        if not isinstance(registry, dict):
            raise TypeError("build_title_registry() liefert kein dict")
        status_registry = engine.build_status_registry()
        if not isinstance(status_registry, dict):
            raise TypeError("build_status_registry() liefert kein dict")
        record("YAML-Engine Kernpfade", True)
    except (OSError, RuntimeError, TypeError, ValueError, ImportError, AttributeError) as exc:
        record("YAML-Engine Kernpfade", False, str(exc))

    try:
        from book_doctor import BookDoctor

        book_path = project_root / "Band_Dummy"
        doctor = BookDoctor(book_path, {})
        healthy, report = doctor.check_health([], 0)
        if not isinstance(healthy, bool) or not isinstance(report, str):
            raise TypeError("BookDoctor.check_health() Rückgabetyp unerwartet")
        record("Book-Doctor Basislauf", True)
    except (OSError, RuntimeError, TypeError, ValueError, ImportError, AttributeError) as exc:
        record("Book-Doctor Basislauf", False, str(exc))

    try:
        from dialog_dirty_utils import DirtyStateController

        class FakeWindow:
            def __init__(self):
                self.current_title = ""

            def title(self, text: str):
                self.current_title = text

            def after(self, *_args, **_kwargs):
                return 1

            def after_cancel(self, *_args, **_kwargs):
                return None

        fake = FakeWindow()
        controller = DirtyStateController(fake, "Test")
        controller.capture_initial({"a": 1})
        controller.refresh({"a": 1})
        if controller.is_dirty:
            raise AssertionError("Controller sollte clean sein")
        controller.refresh({"a": 2})
        if not controller.is_dirty:
            raise AssertionError("Controller sollte dirty sein")
        if fake.current_title != "Test *":
            raise AssertionError("Titel-Marker fehlt")
        record("DirtyStateController Kernlogik", True)
    except (RuntimeError, TypeError, ValueError, ImportError, AttributeError) as exc:
        record("DirtyStateController Kernlogik", False, str(exc))

    try:
        from yaml_engine import QuartoYamlEngine

        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            md = tmp_root / "sample.md"
            md.write_text("# Hallo", encoding="utf-8")
            engine = QuartoYamlEngine(tmp_root)
            changed = engine.ensure_required_frontmatter(md, fallback_title="Hallo")
            content = md.read_text(encoding="utf-8")
            if not changed and "title:" not in content:
                raise AssertionError("Frontmatter wurde nicht ergänzt")
            if "description:" not in content:
                raise AssertionError("description fehlt nach Ergänzung")
        record("Frontmatter-Ergänzung", True)
    except (OSError, RuntimeError, TypeError, ValueError, ImportError, AttributeError) as exc:
        record("Frontmatter-Ergänzung", False, str(exc))

    try:
        source_book = project_root / "Band_Dummy"
        if not source_book.exists():
            raise FileNotFoundError("Band_Dummy fehlt")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            book_copy = tmp_root / "Band_Dummy"
            shutil.copytree(source_book, book_copy)

            render_proc = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "quarto_render_safe.py"),
                    str(book_copy),
                    "--to",
                    "typst",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if render_proc.returncode != 0:
                detail = (render_proc.stderr or render_proc.stdout or "Render fehlgeschlagen").strip()
                raise RuntimeError(detail)

        record("Buch-Generierung (Quarto Render)", True)
    except (FileNotFoundError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
        record("Buch-Generierung (Quarto Render)", False, str(exc))

    return results


def run_gui_smoke(project_root: Path) -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []

    def record(name: str, passed: bool, detail: str = ""):
        results.append((name, passed, detail))

    try:
        root = tk.Tk()
        root.withdraw()
    except (RuntimeError, TypeError, OSError, tk.TclError) as exc:
        return [("GUI-Initialisierung", False, str(exc))]

    try:
        from export_dialog import ExportDialog

        dialog = ExportDialog(root, templates=["Standard"], initial={"format": "typst", "template": "Standard", "footnote_mode": "endnotes"})
        dialog.update_idletasks()
        dialog.destroy()
        record("ExportDialog öffnet", True)
    except (RuntimeError, TypeError, OSError, ImportError, AttributeError, tk.TclError) as exc:
        record("ExportDialog öffnet", False, str(exc))

    try:
        from quarto_config_editor import QuartoConfigEditor

        yaml_path = project_root / "Band_Dummy" / "_quarto.yml"
        dialog = QuartoConfigEditor(root, yaml_path=yaml_path)
        dialog.update_idletasks()
        dialog.destroy()
        record("QuartoConfigEditor öffnet", True)
    except (RuntimeError, TypeError, OSError, ImportError, AttributeError, tk.TclError) as exc:
        record("QuartoConfigEditor öffnet", False, str(exc))

    try:
        from sanitizer_config_editor import SanitizerConfigEditor

        config_path = project_root / "sanitizer_config.toml"
        dialog = SanitizerConfigEditor(root, config_path=config_path)
        dialog.update_idletasks()
        dialog.destroy()
        record("SanitizerConfigEditor öffnet", True)
    except (RuntimeError, TypeError, OSError, ImportError, AttributeError, tk.TclError) as exc:
        record("SanitizerConfigEditor öffnet", False, str(exc))

    try:
        from app_config_editor import AppConfigEditor

        config_path = project_root / "studio_config.json"
        dialog = AppConfigEditor(root, config_path=config_path)
        dialog.update_idletasks()
        dialog.destroy()
        record("AppConfigEditor öffnet", True)
    except (RuntimeError, TypeError, OSError, ImportError, AttributeError, tk.TclError) as exc:
        record("AppConfigEditor öffnet", False, str(exc))

    root.destroy()
    return results


def print_summary(results: list[tuple[str, bool, str]]) -> int:
    failed = 0
    for name, passed, detail in results:
        if passed:
            _ok(name)
        else:
            failed += 1
            _fail(f"{name}: {detail}")

    total = len(results)
    print("-" * 60)
    print(f"Smoke-Tests: {total - failed}/{total} erfolgreich")
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-Tests für Book Studio")
    parser.add_argument("--gui", action="store_true", help="zusätzliche GUI-Dialog-Smoke-Tests ausführen")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    results = run_non_gui_smoke(project_root)
    if args.gui:
        results.extend(run_gui_smoke(project_root))

    failed = print_summary(results)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
