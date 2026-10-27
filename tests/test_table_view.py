from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from src import audit
from src.models import SecretItem
from src.payload_view import parse_key_values
from tests.window_case import WindowCase


class TestParse(unittest.TestCase):
    def test_json_objects_become_rows(self):
        self.assertEqual(
            parse_key_values('{"user": "admin", "port": 5432, "tls": true, "o": {"a": 1}}'),
            {"user": "admin", "port": "5432", "tls": "true", "o": '{"a": 1}'},
        )

    def test_everything_else_is_plain_text(self):
        for text in ("hello", "", "[1, 2]", "{}", "42", '"str"', "{broken", "user: admin"):
            self.assertIsNone(parse_key_values(text), text)


def row_titles(window):
    titles, index = [], 0
    while (row := window.table_list.get_row_at_index(index)) is not None:
        titles.append(row.get_title())
        index += 1
    return titles


class TestTableView(WindowCase):
    def reveal(self, text):
        self.window.current_payload = text
        self.window.is_payload_revealed = True
        self.window._render_payload_text()

    def test_a_revealed_json_object_enables_the_table(self):
        self.assertFalse(self.window.table_btn.get_sensitive())
        self.reveal('{"user": "admin", "password": "p&ss<word>"}')
        self.assertTrue(self.window.table_btn.get_sensitive())
        self.assertEqual(row_titles(self.window), ["user", "password"])
        self.assertEqual(self.window.value_stack.get_visible_child_name(), "text")
        self.window.table_btn.set_active(True)
        self.assertEqual(self.window.value_stack.get_visible_child_name(), "table")

    def test_special_characters_are_shown_literally(self):
        self.reveal('{"k<>": "v&amp;"}')
        row = self.window.table_list.get_row_at_index(0)
        self.assertEqual(row.get_subtitle(), "v&amp;amp;")  # escaped once for markup

    def test_plain_text_and_hidden_values_have_no_table(self):
        self.reveal("just text")
        self.assertFalse(self.window.table_btn.get_sensitive())
        self.assertEqual(row_titles(self.window), [])
        self.reveal('{"a": "b"}')
        self.window.table_btn.set_active(True)
        self.window.is_payload_revealed = False
        self.window._render_payload_text()
        self.assertFalse(self.window.table_btn.get_active())
        self.assertFalse(self.window.table_btn.get_sensitive())
        self.assertEqual(self.window.value_stack.get_visible_child_name(), "text")
        self.assertEqual(row_titles(self.window), [])

    def test_copying_a_key_puts_only_that_value_on_the_clipboard_and_audits_the_field(self):
        self.window.selected_secret = SecretItem(name="n", secret_id="db")
        clipboard = MagicMock()
        display = MagicMock()
        display.get_clipboard.return_value = clipboard
        with (
            patch.dict(os.environ, {audit.ENV_VAR: "1"}),
            patch("gi.repository.Gdk.Display.get_default", return_value=display),
            patch("src.ui.windows.actions.secret_content") as content,
            patch("gi.repository.GLib.timeout_add_seconds", return_value=1),
            patch.object(self.window, "_show_toast"),
        ):
            self.window._on_copy_key("password", "p4ss")
        content.assert_called_once_with("p4ss")
        clipboard.set_content.assert_called_once_with(content.return_value)
        with open(audit.default_path(), encoding="utf-8") as handle:
            event = json.loads(handle.readline())
        self.assertEqual((event["action"], event["field"]), ("copy_key", "password"))
        self.assertNotIn("p4ss", json.dumps(event))


if __name__ == "__main__":
    unittest.main()
