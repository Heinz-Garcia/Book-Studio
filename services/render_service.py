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

Phase 2 / Schritt 2.3c-Mini: Die *Render-Thread-Orchestrierung* (Pre-
Log, Subprocess-Aufruf, Pfad-Auswahl abort/success/failure, Finalize-
Log) ist als synchrone pure Funktion in `execute_render(...)` in
diesem Service. Der eigentliche Subprocess-Aufruf (`_run_safe_render`)
bleibt in `ExportManager` — er ist System-Concern (Pfad zum Skript,
Working-Directory, Env-Variablen) und ist bereits durch 2.3b
(argv-Bau) entkoppelt. Threading (Tk-Lifecycle) bleibt ebenfalls im
Exporter, der die Service-Methode in einen `Thread` einpackt.

Diese Aufteilung folgt Single-Responsibility: Service orchestriert,
Exporter fuehrt aus und hostet das Tk-Lifecycle.

Phase 2 / Schritt 2.3c: Die Subprocess-Logik (`_run_safe_render`)
ist als Methode `RenderService.run_safe_render(...)` in den Service
gewandert. Der Service kapselt das Subprocess-Lifecycle (Popen,
stdout-Streaming, Abbruch-Erkennung, returncode) ueber injizierte
Callbacks und ein `popen_factory`-Argument. Tests koennen den
Subprocess durch ein `MockPopen` ersetzen (monkeypatch auf
`popen_factory`).

Die Threading-Huelle bleibt im `ExportManager` (UI-Lifecycle).
Konkrete Service-Methode:
- `run_safe_render(target_fmt, profile_name, extra_format_options,
  book, safe_script, executable, on_log_line, on_colon_warning,
  should_abort_on_colon_warning, has_structural_colon_occurrences,
  on_abort_requested, popen_factory, popen_killer) -> (rc, aborted)`

Verweise:
- .doc/refactoring-master.md, Batch B8 (Stub-Definition)
- .doc/Refactoring_part2.md, Schritt 2.3 (Migration; aufgeteilt in 2.3a + 2.3b + 2.3c-Mini)
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Optional


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
SAFE_RENDER_ARG_ARCHIVE_DIR = "--archive-dir"


# Log-Status-Werte, die `execute_render` an die `finalize_render_log`-
# Callback weitergibt.
RENDER_STATUS_SUCCESS = "success"
RENDER_STATUS_FAILED = "failed"
RENDER_STATUS_ABORTED_ON_COLON = "aborted_on_first_colon_warning"


# Returncode-Werte, die `run_safe_render` an den Aufrufer liefert.
SAFE_RENDER_RC_MISSING_SCRIPT = 2
SAFE_RENDER_RC_STREAM_ERROR = 3


# Callback-Typen, die `execute_render` als Dependency bekommt.
# - `log_cb(message, level)`: Log-Nachricht ins Studio
# - `after_cb(delay, callable)`: Tk-Schedule (UI-Thread)
# - `on_failure(returncode)`: Fehler-Pfad-Handler im Aufrufer
#   (Farbwert ist UI-Konzern, lebt im Aufrufer).
# - `run_safe_render_cb(target_fmt, profile_name, extra_format_options) -> (returncode, aborted)`
# - `finalize_render_log_cb(status, primary_returncode=None, fallback_returncode=None)`
# - `handle_render_success_cb(target_fmt)`: Post-Render-Erfolgs-Pfad
LogCb = Callable[[str, str], None]
AfterCb = Callable[[int, Callable[[], None]], None]
RunSafeRenderCb = Callable[..., tuple]
FinalizeRenderLogCb = Callable[..., None]
HandleRenderSuccessCb = Callable[[str], None]

# Callback-Typen, die `run_safe_render` (Schritt 2.3c) als Dependency bekommt.
# - `popen_factory(cmd, **kwargs)`: Subprocess-Erzeuger (testbar via monkeypatch).
# - `on_log_line(line)`: UI-Callback fuer eine gelesene Subprocess-Zeile.
# - `on_colon_warning(line) -> bool`: True, wenn die Zeile ein ':::'-Warnhinweis ist
#   (Exiter-spezifisch, in der Regel Heuristik auf raw stderr/stdout).
# - `should_abort_on_colon_warning() -> bool`: UI-/Config-Schalter.
# - `has_structural_colon_occurrences() -> bool`: Buch-Doctor-Resultat, ob ueberhaupt
#   ':::' im verarbeiteten Baum vorkommt.
# - `on_abort_requested()`: UI-Callback bei Abbruch durch ':::'-Warnung.
# - `is_log_colon_warning_hint_emitted() -> bool / set_log_colon_warning_hint(bool)`: Hint-Flag.
# - `popen_killer(proc)`: Optional - bricht den Subprocess ab (z. B. proc.terminate()).
PopenFactory = Callable[..., Any]
OnLogLine = Callable[[str], None]
OnColonWarningCheck = Callable[[str], bool]
OnAbortRequested = Callable[[], None]
HasStructuralColons = Callable[[], bool]
PopenKiller = Callable[[Any], None]


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

    def __init__(self, exporter: Any = None):
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
            # Prefix-Stripping (nicht str.replace, das ALLE Vorkommen ersetzt
            # und Extension-Namen korrumpiert, die den Prefix wiederholen).
            ext_name = template[len(EXTENSION_TEMPLATE_PREFIX):].strip()
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
            # Template-Namen gegen Pfad-Traversal absichern: nur alphanumerische
            # Zeichen, Unterstrich, Bindestrich und Punkt erlauben (kein "/",
            # "..", Laufwerksbuchstaben etc.), analog zu sanitize_profile_name.
            if not re.fullmatch(r"[A-Za-z0-9_.\-]+", template):
                raise ValueError(
                    f"Ungültiger Template-Name (Path-Traversal-Risiko): {template!r}"
                )
            extra_opts = {base_fmt: {"template": f"templates/{template}"}}
            return base_fmt, extra_opts

        return base_fmt, None

    @staticmethod
    def merge_extra_format_options(
        base: Optional[dict[str, dict[str, Any]]],
        overlay: Optional[dict[str, dict[str, Any]]],
    ) -> Optional[dict[str, dict[str, Any]]]:
        """Führt zwei extra_format_options-Dicts zusammen (overlay gewinnt pro Schlüssel)."""
        if not overlay:
            return base
        if not base:
            return {fmt: dict(opts) for fmt, opts in overlay.items()}
        merged: dict[str, dict[str, Any]] = {
            fmt: dict(opts) if isinstance(opts, dict) else opts
            for fmt, opts in base.items()
        }
        for fmt, opts in overlay.items():
            if not isinstance(opts, dict):
                merged[fmt] = opts
                continue
            bucket = merged.setdefault(fmt, {})
            if isinstance(bucket, dict):
                bucket.update(opts)
            else:
                merged[fmt] = dict(opts)
        return merged

    @staticmethod
    def apply_layout_profile(
        extra_opts: Optional[dict[str, dict[str, Any]]],
        *,
        target_fmt: str,
        layout_profile: str,
        linestretch: float,
    ) -> dict[str, dict[str, Any]]:
        """Hängt Layout-Profil-Optionen an extra_format_options an."""
        from tools.layout_profiles.catalog import build_layout_format_options

        layout_opts = build_layout_format_options(
            layout_profile,
            target_fmt,
            linestretch=linestretch,
        )
        return RenderService.merge_extra_format_options(extra_opts, layout_opts) or layout_opts

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
        archive_dir: Optional[Path] = None,
    ) -> list:
        """Baut die argv-Liste fuer den sicheren Render-Subprocess.

        Aufbau:
        `[executable, str(safe_script), str(book), "--to", target_fmt]`
        plus optional `--profile-name <name>`,
        `--extra-format-options-json <json>` und `--archive-dir <path>`.

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
        if archive_dir:
            cmd.extend([SAFE_RENDER_ARG_ARCHIVE_DIR, str(archive_dir)])
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

    # --- Render-Orchestrierung (Phase 2 / 2.3c-Mini) -------------------

    @staticmethod
    def execute_render(
        target_fmt: str,
        profile_name: Optional[str],
        extra_format_options: Optional[dict],
        run_safe_render: RunSafeRenderCb,
        finalize_render_log: FinalizeRenderLogCb,
        handle_render_success: HandleRenderSuccessCb,
        log_cb: LogCb,
        after_cb: AfterCb,
        on_failure: Callable[[int], None],
    ) -> tuple[int, bool]:
        """Orchestriert einen Render-Lauf synchron.

        Die Methode ist *rein deterministisch* (kein Subprocess, kein
        Threading, kein Tk). Sie ruft die uebergebenen Callbacks in
        einer festen Reihenfolge auf:

        1. Pre-Log ueber `after_cb(0, ...)` ("Render startet ueber
           sichere temporaere Kopie ...").
        2. `run_safe_render(target_fmt, profile_name, extra_format_options)`
           -> `(returncode, aborted_on_colon_warning)`.
        3. Wenn `aborted_on_colon_warning`:
           `finalize_render_log("aborted_on_first_colon_warning", ...)`
           und Rueckkehr.
        4. Wenn `returncode == 0`:
           `finalize_render_log("success", ...)` und
           `handle_render_success(target_fmt)`.
        5. Sonst: `finalize_render_log("failed", ...)` plus
           `on_failure(returncode)` (im Aufrufer wird dort der
           Fehler-Log und Status-Bar-Update gemacht; Farbwert ist
           UI-Konzern und lebt im Aufrufer).

        Die Methode gibt `(returncode, aborted_on_colon_warning)` an
        den Aufrufer zurueck. Der Aufrufer (typisch `ExportManager`)
        wrappt diesen Aufruf in einen Thread.

        Parameter:
        - `target_fmt`: das aufgeloeste Render-Format (z. B. "html")
        - `profile_name`: optionales Quarto-Profil
        - `extra_format_options`: optionale Format-Optionen
        - `run_safe_render`: Callable, das den Subprocess ausfuehrt
          und `(returncode, aborted)` liefert.
        - `finalize_render_log`: Callable zum Finalisieren des
          Render-Log-Files.
        - `handle_render_success`: Callable fuer den Post-Render-
          Erfolgs-Pfad (Datei oeffnen, Clipboard, etc.).
        - `log_cb`, `after_cb`: UI-Callbacks.
        - `on_failure`: Callable, das im Failure-Pfad aufgerufen wird.
          Hier lebt das Wissen ueber den passenden Status-Farbwert.
        """
        after_cb(0, lambda: log_cb(
            "🛡️ Render startet über sichere temporäre Kopie (processed + ORDER-kompatibel).",
            "dim",
        ))

        return_code, aborted_on_colon_warning = run_safe_render(
            target_fmt,
            profile_name=profile_name,
            extra_format_options=extra_format_options,
        )

        if aborted_on_colon_warning:
            finalize_render_log(
                RENDER_STATUS_ABORTED_ON_COLON, primary_returncode=return_code
            )
            return return_code, aborted_on_colon_warning

        if return_code == 0:
            finalize_render_log(RENDER_STATUS_SUCCESS, primary_returncode=return_code)
            handle_render_success(target_fmt)
            return return_code, aborted_on_colon_warning

        finalize_render_log(RENDER_STATUS_FAILED, primary_returncode=return_code)
        after_cb(0, lambda: log_cb(f"❌ FEHLER: Code {return_code}", "error"))
        on_failure(return_code)
        return return_code, aborted_on_colon_warning

    # --- Render-Artifact-Aufloesung (Phase 2 / 2.3c voll) -------------

    @staticmethod
    def build_render_out_dir(book: Path, profile_name: Optional[str]) -> Path:
        """Berechnet das Render-Output-Verzeichnis.

        `book / 'export' / '_book_<safe_profile>'` oder
        `book / 'export' / '_book'` wenn kein Profil gesetzt ist.
        `profile_name` wird auf `[A-Za-z0-9_-]` sanitiert; alle
        anderen Zeichen werden zu `_`.
        """
        if not isinstance(book, Path):
            book = Path(book)
        if profile_name:
            safe_profile = re.sub(r"[^a-zA-Z0-9_\-]", "_", profile_name)
            out_dir_name = f"_book_{safe_profile}"
        else:
            out_dir_name = "_book"
        return book / "export" / out_dir_name

    # Suffix-Whitelist fuer `pick_latest_artifact` (analog zu
    # `export_manager.ExportManager._ALLOWED_RENDER_SUFFIXES`, Bug R3:
    # nur bekannte Render-Ergebnisse duerfen ausgewaehlt/geoeffnet werden).
    ALLOWED_RENDER_SUFFIXES: dict[str, set] = {
        "typst": {".pdf", ".typ"},
        "pdf": {".pdf"},
        "html": {".html"},
        "epub": {".epub"},
        "docx": {".docx"},
    }
    DEFAULT_ALLOWED_SUFFIXES: set = {".pdf", ".html", ".epub", ".docx"}

    @classmethod
    def pick_latest_artifact(cls, dir_path: Optional[Path], fmt: str) -> Optional[Path]:
        """Waehlt die zuletzt geaenderte Datei in `dir_path`, deren Suffix
        in der Whitelist fuer `fmt` enthalten ist (`None`, falls keine
        passt oder `dir_path` nicht existiert).

        Fuer Archiv-Ordner (`tools.publish_map.store.snapshot_render_dir`)
        gedacht, die mehrere zeitstempel-benannte Artefakte enthalten
        koennen - im Unterschied zu `export_manager._pick_rendered_artifact`,
        das nur eine Datei pro festem Pfad erwartet und alphabetisch waehlt.
        """
        if not dir_path or not Path(dir_path).is_dir():
            return None
        allowed = cls.ALLOWED_RENDER_SUFFIXES.get(
            (fmt or "").lower(), cls.DEFAULT_ALLOWED_SUFFIXES
        )
        candidates = [
            p for p in Path(dir_path).iterdir()
            if p.is_file() and p.suffix.lower() in allowed
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda p: p.stat().st_mtime)

    @staticmethod
    def open_rendered_artifact(path: str, *, system_name: Optional[str] = None) -> None:
        """Plattform-spezifisches Oeffnen einer gerenderten Datei.

        Args:
            path: Absoluter Pfad zur Datei.
            system_name: Optional - 'Windows', 'Darwin' oder
                'Linux'. Default: `platform.system()`. Testbar via
                Injektion.

        Raises:
            subprocess.SubprocessError: bei nicht-erkanntem OS.
        """
        if system_name is None:
            import platform as _platform
            system_name = _platform.system()
        if system_name == "Windows":
            os.startfile(path)  # noqa: S606
        elif system_name == "Darwin":
            subprocess.call(("open", path))
        else:
            subprocess.call(("xdg-open", path))

    # --- Subprocess-Wrapper (Phase 2 / 2.3c) -----------------------------

    def run_safe_render(
        self,
        target_fmt: str,
        profile_name: Optional[str],
        extra_format_options: Optional[dict],
        book: Path,
        safe_script: Path,
        executable: Optional[str] = None,
        on_log_line: Optional[OnLogLine] = None,
        on_colon_warning: Optional[OnColonWarningCheck] = None,
        should_abort_on_colon_warning: Optional[Callable[[], bool]] = None,
        has_structural_colon_occurrences: Optional[HasStructuralColons] = None,
        on_abort_requested: Optional[OnAbortRequested] = None,
        popen_factory: Optional[PopenFactory] = None,
        popen_killer: Optional[PopenKiller] = None,
        on_safe_command_built: Optional[Callable[[list], None]] = None,
        archive_dir: Optional[Path] = None,
    ) -> tuple:
        """Kapselt den Subprocess-Aufruf von `quarto_render_safe.py`.

        Verhalten (1:1 wie die bisherige Inline-Variante im `ExportManager`):

        1. Pruefe, ob `safe_script` existiert. Wenn nicht: Log via
           `on_log_line` (Level "error") und Rueckgabe
           `(SAFE_RENDER_RC_MISSING_SCRIPT, False)`.
        2. Baue die argv-Liste via `build_safe_render_command`.
        3. Starte den Subprocess ueber `popen_factory` (Default:
           `subprocess.Popen`). Es wird erwartet, dass die Factory
           ein Objekt mit `.stdout` (Iterator von Strings) und
           `.returncode` / `.wait()` liefert.
        4. Iteriere zeilenweise ueber `proc.stdout`. Fuer jede Zeile:
           - Bei nicht-leerer Zeile: `on_log_line(line)`.
           - Wenn `on_colon_warning(line) and should_abort_on_colon_warning()
             and has_structural_colon_occurrences()`:
             `on_abort_requested()`, `popen_killer(proc)`,
             `aborted = True`, break.
        5. `proc.wait()`, Rueckgabe `(returncode, aborted)`.

        Die Methode ist **nicht** Tk-frei - `on_log_line`,
        `on_colon_warning` etc. sind typischerweise UI-Callbacks. Die
        Subprocess-Erzeugung selbst ist ueber `popen_factory` injiziert
        und damit im Test monkeypatch-bar.

        Rueckgabe: `(returncode: int, aborted_on_colon_warning: bool)`.
        """
        if on_log_line is None:
            def on_log_line(_line):
                return None
        if on_colon_warning is None:
            def on_colon_warning(_line):
                return False
        if should_abort_on_colon_warning is None:
            def should_abort_on_colon_warning():
                return False
        if has_structural_colon_occurrences is None:
            def has_structural_colon_occurrences():
                return False
        if on_abort_requested is None:
            def on_abort_requested():
                return None
        if popen_factory is None:
            popen_factory = subprocess.Popen
        if popen_killer is None:
            def popen_killer(proc):
                proc.terminate()
        if executable is None:
            executable = sys.executable

        if not Path(safe_script).exists():
            on_log_line(
                "❌ Fallback-Skript nicht gefunden: quarto_render_safe.py"
            )
            return SAFE_RENDER_RC_MISSING_SCRIPT, False

        cmd = self.build_safe_render_command(
            executable=executable,
            safe_script=Path(safe_script),
            book=Path(book),
            target_fmt=target_fmt,
            profile_name=profile_name,
            extra_format_options=extra_format_options,
            archive_dir=archive_dir,
        )
        if on_safe_command_built is not None:
            try:
                on_safe_command_built(cmd)
            except Exception as exc:
                # B-Fix (Code-Review 2026-07-03): Fehler im (optionalen,
                # meist testgetriebenen) Hook wurden bisher komplett
                # verschluckt. Jetzt zumindest ueber `on_log_line` sichtbar,
                # ohne den eigentlichen Render-Ablauf zu unterbrechen.
                if on_log_line is not None:
                    try:
                        on_log_line(f"⚠️ on_safe_command_built-Hook fehlgeschlagen: {exc}")
                    except Exception:
                        pass

        proc = popen_factory(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        aborted_on_colon_warning = False
        stream_error = False
        # B-Fix (Code-Review 2026-07-03): das Lesen von `proc.stdout` kann
        # (z. B. bei Encoding-/Pipe-Fehlern) eine Exception werfen. Vorher
        # lief das ungeschuetzt: die Exception haette `proc.wait()` nie
        # erreicht und einen Zombie-/verwaisten Subprozess hinterlassen.
        # `try/finally` stellt sicher, dass der Prozess in JEDEM Fall
        # beendet und abgewartet wird; `SAFE_RENDER_RC_STREAM_ERROR` wird
        # jetzt tatsaechlich zurueckgegeben statt nur deklariert zu sein.
        try:
            stdout = getattr(proc, "stdout", None)
            if stdout is not None:
                for raw_line in stdout:
                    stripped = raw_line.rstrip() if isinstance(raw_line, str) else raw_line
                    if stripped:
                        on_log_line(stripped)
                        if (
                            on_colon_warning(stripped)
                            and should_abort_on_colon_warning()
                            and has_structural_colon_occurrences()
                        ):
                            aborted_on_colon_warning = True
                            try:
                                popen_killer(proc)
                            except OSError:
                                pass
                            on_abort_requested()
                            break
        except (OSError, ValueError) as exc:
            stream_error = True
            on_log_line(f"❌ Fehler beim Lesen der Render-Ausgabe: {exc}")
            try:
                popen_killer(proc)
            except OSError:
                pass
        finally:
            if hasattr(proc, "wait"):
                try:
                    proc.wait()
                except OSError:
                    pass

        if stream_error:
            return SAFE_RENDER_RC_STREAM_ERROR, aborted_on_colon_warning
        return getattr(proc, "returncode", 0), aborted_on_colon_warning

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
    "RENDER_STATUS_ABORTED_ON_COLON",
    "RENDER_STATUS_FAILED",
    "RENDER_STATUS_SUCCESS",
    "SAFE_RENDER_ARG_ARCHIVE_DIR",
    "SAFE_RENDER_ARG_EXTRA_OPTS",
    "SAFE_RENDER_ARG_PROFILE",
    "SAFE_RENDER_ARG_TO",
    "SAFE_RENDER_RC_MISSING_SCRIPT",
    "SAFE_RENDER_RC_STREAM_ERROR",
    "RenderService",
]
