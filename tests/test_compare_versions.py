from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.diffing import ADDED, REMOVED, DiffLine
from src.i18n import _
from src.models import SecretVersionItem
from src.ui.dialogs import compare
from src.ui.dialogs.compare import _render_diff, _version_label, show_compare_versions_dialog
from tests.window_case import WindowCase


class DummySyncThread:
    def __init__(self, target, *args, **kwargs):
        self.target = target

    def start(self):
        self.target()


def _versions():
    return [
        SecretVersionItem(version_id="2", name="s/versions/2"),
        SecretVersionItem(version_id="1", name="s/versions/1", state="DISABLED"),
    ]


class TestCompareDialog(WindowCase):
    def _open(self, payloads):
        fetch = MagicMock(side_effect=lambda name: payloads[name])
        with patch.object(compare.Gtk.Window, "present"):
            win = show_compare_versions_dialog(self.window, _versions(), fetch)
        return win, fetch

    def _compare(self, win):
        with (
            patch("threading.Thread", side_effect=DummySyncThread),
            patch.object(compare.GLib, "idle_add", side_effect=lambda f, *a: f(*a)),
        ):
            win.compare_btn.emit("clicked")

    def test_defaults_compare_previous_with_latest(self):
        win, _fetch = self._open({})
        self.assertEqual(win.to_dropdown.get_selected(), 0)
        self.assertEqual(win.from_dropdown.get_selected(), 1)

    def test_shows_added_and_removed_lines(self):
        win, fetch = self._open(
            {"s/versions/1": "user=a\npass=old", "s/versions/2": "user=a\npass=new"}
        )
        self._compare(win)
        text = win.diff_buffer.get_text(
            win.diff_buffer.get_start_iter(), win.diff_buffer.get_end_iter(), False
        )
        self.assertIn("-pass=old", text)
        self.assertIn("+pass=new", text)
        self.assertEqual(win.status_label.get_label(), _("%d added, %d removed") % (1, 1))
        self.assertTrue(win.compare_btn.get_sensitive())
        self.assertEqual(fetch.call_count, 2)

    def test_identical_versions_report_no_differences(self):
        win, _fetch = self._open({"s/versions/1": "same", "s/versions/2": "same"})
        self._compare(win)
        self.assertEqual(win.status_label.get_label(), _("No differences between these versions"))

    def test_selecting_the_same_version_twice_is_rejected(self):
        win, fetch = self._open({})
        win.from_dropdown.set_selected(0)
        self._compare(win)
        self.assertEqual(win.status_label.get_label(), _("Select two different versions"))
        fetch.assert_not_called()

    def test_fetch_error_is_reported(self):
        fetch = MagicMock(side_effect=RuntimeError("boom"))
        with patch.object(compare.Gtk.Window, "present"):
            win = show_compare_versions_dialog(self.window, _versions(), fetch)
        self._compare(win)
        self.assertIn("boom", win.status_label.get_label())
        self.assertTrue(win.compare_btn.get_sensitive())

    def test_closing_clears_displayed_values(self):
        win, _fetch = self._open({"s/versions/1": "a", "s/versions/2": "b"})
        self._compare(win)
        self.assertNotEqual(win.diff_buffer.get_char_count(), 0)
        win.emit("close-request")
        self.assertEqual(win.diff_buffer.get_char_count(), 0)

    def test_single_version_still_builds_dialog(self):
        with patch.object(compare.Gtk.Window, "present"):
            win = show_compare_versions_dialog(self.window, _versions()[:1], MagicMock())
        self.assertEqual(win.from_dropdown.get_selected(), 0)
        self._compare(win)
        self.assertEqual(win.status_label.get_label(), _("Select two different versions"))


class TestRenderDiff(WindowCase):
    def test_tags_are_applied_per_line_kind(self):
        win_buffer = compare.Gtk.TextBuffer()
        for kind in (ADDED, REMOVED):
            win_buffer.create_tag(kind)
        _render_diff(
            win_buffer, [DiffLine(ADDED, "+new"), DiffLine(REMOVED, "-old"), DiffLine("odd", "?")]
        )
        start = win_buffer.get_iter_at_offset(1)
        self.assertTrue(start.has_tag(win_buffer.get_tag_table().lookup(ADDED)))
        self.assertTrue(
            win_buffer.get_iter_at_offset(7).has_tag(win_buffer.get_tag_table().lookup(REMOVED))
        )

    def test_version_label_includes_state(self):
        self.assertIn(f"({_('Disabled')})", _version_label(_versions()[1]))


class TestWindowIntegration(WindowCase):
    def test_compare_button_enabled_only_with_two_or_more_versions(self):
        self.window._render_versions_list(_versions()[:1])
        self.assertFalse(self.window.compare_btn.get_sensitive())
        self.window._render_versions_list(_versions())
        self.assertTrue(self.window.compare_btn.get_sensitive())

    def test_clicking_compare_opens_dialog_with_provider_payload_fetcher(self):
        self.window.current_versions = _versions()
        self.mock_gcp.access_secret_payload.return_value = ("value", False)
        with patch.object(self.window.dialogs, "compare_versions") as mock_show:
            self.window._on_compare_versions(None)
        parent, versions, fetch = mock_show.call_args[0]
        self.assertIs(parent, self.window)
        self.assertEqual(fetch("s/versions/2"), "value")
        self.assertIs(self.window._compare_dialog, mock_show.return_value)

    def test_compare_requires_two_versions(self):
        self.window.current_versions = _versions()[:1]
        with patch.object(self.window.dialogs, "compare_versions") as mock_show:
            self.window._on_compare_versions(None)
        mock_show.assert_not_called()

    def test_idle_lock_closes_open_compare_dialog(self):
        dialog = MagicMock()
        self.window._compare_dialog = dialog
        with patch("gi.repository.Gdk.Display.get_default", return_value=None):
            self.window._lock_after_idle()
        dialog.close.assert_called_once()
        self.assertIsNone(self.window._compare_dialog)


if __name__ == "__main__":
    unittest.main()
