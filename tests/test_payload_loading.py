from __future__ import annotations

from unittest.mock import MagicMock, patch

from gi.repository import Gtk

from src.i18n import _
from src.models import SecretItem, SecretVersionItem
from tests.window_case import WindowCase


class DummySyncThread:
    def __init__(self, target, *args, **kwargs):
        self.target = target

    def start(self):
        self.target()


def _text(window):
    buffer = window.text_buffer
    return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)


class PayloadCase(WindowCase):
    def setUp(self):
        super().setUp()
        self.window.current_versions = [
            SecretVersionItem(version_id="2", name="s/versions/2"),
            SecretVersionItem(version_id="1", name="s/versions/1"),
        ]
        self.window.version_dropdown.set_model(Gtk.StringList.new(["Version 2", "Version 1"]))
        self.window.version_dropdown.set_selected(0)
        self.window.copy_val_btn.set_sensitive(True)

    def _sync(self):
        return (
            patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)),
            patch("threading.Thread", side_effect=DummySyncThread),
        )


class TestStaleReplies(PayloadCase):
    def test_reply_for_a_previous_request_is_ignored(self):
        self.window._load_payload_async("s/versions/2")
        stale_id = self.window._payload_request_id
        self.window._load_payload_async("s/versions/1")

        self.window._payload_pending = "reveal"
        self.window._on_payload_loaded("OLD-SECRET", False, None, "gcp", stale_id)

        self.assertIsNone(self.window.current_payload)
        self.assertFalse(self.window.is_payload_revealed)

    def test_reply_after_selecting_another_secret_is_ignored(self):
        self.window._payload_pending = "reveal"
        self.window._load_payload_async("s/versions/2")
        request_id = self.window._payload_request_id

        with patch.object(self.window, "_load_versions_async"):
            self.window._on_secret_selected(
                SecretItem(name="projects/p/secrets/other", secret_id="other")
            )

        self.window._on_payload_loaded("FIRST-SECRETS-VALUE", False, None, "gcp", request_id)
        self.assertIsNone(self.window.current_payload)
        self.assertNotIn("FIRST-SECRETS-VALUE", _text(self.window))

    def test_error_reply_for_stale_request_does_not_overwrite_the_view(self):
        self.window._load_payload_async("s/versions/2")
        stale_id = self.window._payload_request_id
        self.window._reset_payload()
        self.window._on_payload_loaded(None, False, "boom", "gcp", stale_id)
        self.assertNotIn("boom", _text(self.window))

    def test_current_request_is_applied(self):
        self.window._payload_pending = "reveal"
        self.window._load_payload_async("s/versions/2")
        self.window._on_payload_loaded("fresh", False, None, "gcp", self.window._payload_request_id)
        self.assertEqual(self.window.current_payload, "fresh")

    def test_reply_from_a_different_provider_is_ignored(self):
        self.window._payload_pending = "reveal"
        self.window._on_payload_loaded("x", False, None, "aws")
        self.assertIsNone(self.window.current_payload)


class TestLazyLoading(PayloadCase):
    def test_value_is_not_fetched_until_requested(self):
        self.window._reset_payload()
        self.mock_gcp.access_secret_payload.assert_not_called()
        self.assertIsNone(self.window.current_payload)
        self.assertIn("•", _text(self.window))

    def test_reveal_fetches_the_selected_version(self):
        self.window.version_dropdown.set_selected(1)
        self.mock_gcp.access_secret_payload.return_value = ("older", False)
        sync = self._sync()
        with sync[0], sync[1]:
            self.window._on_toggle_reveal(None)
        self.mock_gcp.access_secret_payload.assert_called_once_with("s/versions/1")
        self.assertEqual(_text(self.window), "older")

    def test_copy_fetches_copies_and_does_not_keep_the_value(self):
        self.mock_gcp.access_secret_payload.return_value = ("copied-secret", False)
        clipboard = MagicMock()
        display = MagicMock()
        display.get_clipboard.return_value = clipboard
        sync = self._sync()
        with (
            sync[0],
            sync[1],
            patch("gi.repository.Gdk.Display.get_default", return_value=display),
            patch("src.ui.windows.actions.secret_content") as content,
        ):
            self.window._on_copy_payload(None)
        content.assert_called_once_with("copied-secret")
        clipboard.set_content.assert_called_once_with(content.return_value)
        self.assertIsNone(self.window.current_payload)
        self.assertFalse(self.window.is_payload_revealed)

    def test_copy_when_revealed_uses_the_loaded_value_and_keeps_it(self):
        self.window.current_payload = "shown"
        self.window.is_payload_revealed = True
        clipboard = MagicMock()
        display = MagicMock()
        display.get_clipboard.return_value = clipboard
        with (
            patch("gi.repository.Gdk.Display.get_default", return_value=display),
            patch("src.ui.windows.actions.secret_content") as content,
        ):
            self.window._on_copy_payload(None)
        content.assert_called_once_with("shown")
        clipboard.set_content.assert_called_once_with(content.return_value)
        self.mock_gcp.access_secret_payload.assert_not_called()
        self.assertEqual(self.window.current_payload, "shown")

    def test_copying_an_empty_secret_copies_nothing(self):
        self.window.current_payload = ""
        with patch("gi.repository.Gdk.Display.get_default") as display:
            self.window._on_copy_payload(None)
        display.assert_not_called()

    def test_fetch_error_is_shown_and_nothing_is_kept(self):
        self.mock_gcp.access_secret_payload.side_effect = RuntimeError("denied")
        sync = self._sync()
        with sync[0], sync[1]:
            self.window._on_toggle_reveal(None)
        self.assertIn("denied", _text(self.window))
        self.assertIsNone(self.window.current_payload)
        self.assertFalse(self.window.is_payload_revealed)

    def test_request_without_versions_does_nothing(self):
        self.window.current_versions = []
        self.window._request_payload("reveal")
        self.assertIsNone(self.window._payload_pending)

    def test_versions_loaded_resets_value_and_enables_copy(self):
        self.window.selected_secret = SecretItem(name="s", secret_id="s")
        self.window.current_payload = "leftover"
        self.window.is_payload_revealed = True
        self.window._on_versions_loaded(self.window.current_versions, None, "s", "gcp")
        self.assertIsNone(self.window.current_payload)
        self.assertTrue(self.window.copy_val_btn.get_sensitive())

    def test_versions_loaded_without_versions_disables_copy(self):
        self.window.selected_secret = SecretItem(name="s", secret_id="s")
        self.window._on_versions_loaded([], None, "s", "gcp")
        self.assertFalse(self.window.copy_val_btn.get_sensitive())
        self.assertEqual(_text(self.window), _("[No active versions]"))
