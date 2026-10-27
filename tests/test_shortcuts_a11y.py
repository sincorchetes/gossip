from __future__ import annotations

import unittest
from unittest.mock import patch

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src.i18n import set_language
from src.ui.a11y import label_icon_buttons
from src.ui.windows.shortcuts import shortcut_table
from tests.window_case import WindowCase


def accessible_label(widget):
    return widget.get_accessible_role() is not None and widget.get_tooltip_text()


class TestLabelIconButtons(unittest.TestCase):
    def test_only_buttons_without_text_are_named(self):
        box = Gtk.Box()
        icon_only = Gtk.Button(icon_name="edit-copy-symbolic", tooltip_text="Copy it")
        with_text = Gtk.Button(label="Copy", tooltip_text="Copy to the clipboard")
        no_tooltip = Gtk.Button(icon_name="edit-copy-symbolic")
        toggle = Gtk.ToggleButton(icon_name="view-list-symbolic", tooltip_text="Table")
        menu = Gtk.MenuButton(icon_name="open-menu-symbolic", tooltip_text="Menu")
        nested = Gtk.Box()
        deep = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="Add")
        nested.append(deep)
        for child in (icon_only, with_text, no_tooltip, toggle, menu, nested):
            box.append(child)
        self.assertEqual(label_icon_buttons(box), 4)  # icon_only, toggle, menu, deep
        self.assertEqual(label_icon_buttons(Gtk.Label()), 0)

    def test_the_main_window_icon_buttons_are_named(self):
        class Case(WindowCase):
            def runTest(self):
                pass

        case = Case()
        case.setUp()
        try:
            # theme, language, about, refresh, transfer, read-only, copy name, edit, delete...
            self.assertGreater(label_icon_buttons(case.window), 8)
        finally:
            case.tearDown()


class TestShortcuts(WindowCase):
    def setUp(self):
        super().setUp()
        set_language("en")
        self.addCleanup(set_language, "es")

    def test_every_listed_shortcut_has_a_description(self):
        table = shortcut_table()
        self.assertGreaterEqual(len(table), 8)
        for accel, text in table:
            self.assertTrue(Gtk.ShortcutTrigger.parse_string(accel), accel)
            self.assertTrue(text)

    def test_registered_shortcuts_call_the_matching_actions(self):
        expectations = {
            "<Primary>n": "_on_create_secret_clicked",
            "F5": "_load_secrets_async",
            "<Primary>r": "_load_secrets_async",
            "<Primary><Shift>r": "_on_toggle_reveal",
            "<Primary><Shift>c": "_on_copy_payload",
            "<Primary>e": "_on_edit_metadata_clicked",
            "<Primary>Delete": "_on_delete_secret_clicked",
        }
        registered = dict(self.window._shortcut_actions())
        self.assertTrue(set(expectations) <= set(registered))
        for accel, method in expectations.items():
            with patch.object(self.window, method) as target:
                registered[accel]()
            target.assert_called_once()

    def test_every_accelerator_in_the_table_is_registered_or_handled_elsewhere(self):
        registered = {accel for accel, _h in self.window._shortcut_actions()}
        listed = {accel for accel, _t in shortcut_table()}
        self.assertEqual(listed - registered, {"<Primary>f"})  # Ctrl+F is the sidebar's

    def test_the_controller_is_installed_and_f1_shows_the_dialog(self):
        self.assertIsNotNone(self.window._shortcut_controller)
        with patch.object(Adw.MessageDialog, "present"):
            dialog = self.window._show_shortcuts_dialog()
        body = dialog.get_body()
        for _accel, text in shortcut_table():
            self.assertIn(text, body)
        self.assertEqual(dialog.get_heading(), "Keyboard shortcuts")


if __name__ == "__main__":
    unittest.main()
