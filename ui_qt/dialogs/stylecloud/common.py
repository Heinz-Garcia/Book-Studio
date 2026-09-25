"""Gemeinsame Hilfen von ``ui_qt.dialogs.stylecloud_dialog`` und seinen Mixins."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QWidget,
)

from tools.stylecloud.generator import (
    StylecloudDependencyError,
    StylecloudOptions,
    generate_stylecloud,
)
from tools.stylecloud.noun_filter import SpacyNounFilterError


class _GenerateWorker(QThread):
    """Runs ``generate_stylecloud`` off the UI thread."""

    progress = Signal(int, str)
    succeeded = Signal(object)
    failed = Signal(str, str)  # kind, message

    def __init__(self, options: StylecloudOptions, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._options = options

    def run(self) -> None:
        try:

            def _cb(percent: int, message: str) -> None:
                self.progress.emit(percent, message)

            path = generate_stylecloud(self._options, progress=_cb)
            self.succeeded.emit(path)
        except StylecloudDependencyError as exc:
            self.failed.emit("dependency", str(exc))
        except SpacyNounFilterError as exc:
            self.failed.emit("spacy", str(exc))
        except ValueError as exc:
            self.failed.emit("value", str(exc))
        except OSError as exc:
            self.failed.emit("os", str(exc))
        except RuntimeError as exc:
            self.failed.emit("runtime", str(exc))
        except Exception as exc:  # pragma: no cover - unexpected library errors
            self.failed.emit("runtime", str(exc))


def _set_combo_by_data(combo: QComboBox, value: object) -> bool:
    """Select combo item whose userData equals *value* (tuple/list tolerant)."""
    normalized = tuple(value) if isinstance(value, list) else value
    for index in range(combo.count()):
        data = combo.itemData(index)
        if data == normalized:
            combo.setCurrentIndex(index)
            return True
        if isinstance(data, tuple) and isinstance(normalized, tuple) and data == normalized:
            combo.setCurrentIndex(index)
            return True
    return False


_VCENTER = Qt.AlignmentFlag.AlignVCenter


def resolve_stylecloud_handoff_png(
    *,
    last_output: Path | str | None,
    output_field: str | None,
) -> Path | None:
    """Resolve PNG for KDP handoff: last generated file, else output path field."""
    candidates: list[Path] = []
    if last_output is not None and str(last_output).strip():
        candidates.append(Path(str(last_output)).expanduser())
    if output_field and str(output_field).strip():
        candidates.append(Path(str(output_field).strip()).expanduser())
    seen: set[str] = set()
    for raw in candidates:
        try:
            path = raw.resolve()
        except OSError:
            continue
        key = str(path).casefold()
        if key in seen:
            continue
        seen.add(key)
        if path.is_file() and path.suffix.casefold() in {".png", ".jpg", ".jpeg", ".webp"}:
            return path
    return None
