"""Regression: QuartoConfigEditor Abbrechen mit Dirty-Check."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from quarto_config_editor import QuartoConfigEditor


def _make_editor_stub(*, is_dirty: bool):
    editor = MagicMock()
    editor._dirty_controller = MagicMock()
    editor._dirty_controller.is_dirty = is_dirty
    editor._refresh_dirty_state = MagicMock()
    editor._dirty_controller.stop_polling = MagicMock()
    editor.destroy = MagicMock()
    return editor


def test_cancel_closes_immediately_when_clean():
    editor = _make_editor_stub(is_dirty=False)

    QuartoConfigEditor._cancel(editor)

    editor._refresh_dirty_state.assert_called_once()
    editor._dirty_controller.stop_polling.assert_called_once()
    editor.destroy.assert_called_once()


@patch("quarto_config_editor.confirm_discard_changes", return_value=False)
def test_cancel_aborts_when_user_declines_discard(mock_confirm):
    editor = _make_editor_stub(is_dirty=True)

    QuartoConfigEditor._cancel(editor)

    mock_confirm.assert_called_once()
    editor.destroy.assert_not_called()


@patch("quarto_config_editor.confirm_discard_changes", return_value=True)
def test_cancel_closes_when_user_confirms_discard(mock_confirm):
    editor = _make_editor_stub(is_dirty=True)

    QuartoConfigEditor._cancel(editor)

    mock_confirm.assert_called_once()
    editor._dirty_controller.stop_polling.assert_called_once()
    editor.destroy.assert_called_once()
