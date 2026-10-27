from __future__ import annotations

import json
import sys
import unittest
from unittest.mock import MagicMock, patch

import gi

gi.require_version("Adw", "1")
from gi.repository import Adw

from src import state
from src.i18n import get_current_language, set_language
from src.main import main
from tests.window_case import WindowCase


class TestStateUi(unittest.TestCase):
    def test_only_valid_values_are_kept(self):
        with open(state.state_path(), "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "ui": {
                        "theme": "blue",
                        "language": "fr",
                        "width": 10,
                        "height": True,
                        "maximized": "yes",
                    }
                },
                handle,
            )
        self.assertEqual(state.load()["ui"], {})
        with open(state.state_path(), "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "ui": {
                        "theme": "dark",
                        "language": "en",
                        "width": 1400,
                        "height": 900,
                        "maximized": True,
                    }
                },
                handle,
            )
        self.assertEqual(
            state.load()["ui"],
            {"theme": "dark", "language": "en", "width": 1400, "height": 900, "maximized": True},
        )
        with open(state.state_path(), "w", encoding="utf-8") as handle:
            json.dump({"ui": "oops"}, handle)
        self.assertEqual(state.load()["ui"], {})

    def test_updates_merge_and_never_disturb_the_rest(self):
        state.save("aws", {"aws": {"profile": "dev"}}, {"aws": [{"profile": "dev"}]})
        state.update_ui(theme="dark")
        state.update_ui(width=1500, height=950, maximized=False)
        loaded = state.load()
        self.assertEqual(
            loaded["ui"], {"theme": "dark", "width": 1500, "height": 950, "maximized": False}
        )
        self.assertEqual(
            (loaded["provider"], loaded["contexts"]["aws"]), ("aws", {"profile": "dev"})
        )
        self.assertEqual(loaded["recents"], {"aws": [{"profile": "dev"}]})
        state.save("gcp", {})  # saving the context keeps the interface preferences
        self.assertEqual(state.load()["ui"]["theme"], "dark")

    def test_update_works_on_a_fresh_install(self):
        state.update_ui(language="en")
        self.assertEqual(state.load()["ui"], {"language": "en"})
        self.assertIsNone(state.load()["provider"])


class TestLaunchUsesSavedPreferences(unittest.TestCase):
    def launch(self, *argv):
        with (
            patch("src.ui.app.run_app", return_value=0) as run,
            patch.dict("os.environ", {"DISPLAY": ":0"}),
            patch.object(sys, "argv", ["gossip", *argv]),
        ):
            main()
        return run.call_args.kwargs

    def tearDown(self):
        set_language("es")

    def test_saved_size_and_maximized_state_are_used(self):
        state.update_ui(width=1500, height=900, maximized=True)
        kwargs = self.launch()
        self.assertEqual(
            (kwargs["width"], kwargs["height"], kwargs["maximized"]), (1500, 900, True)
        )

    def test_command_line_wins(self):
        state.update_ui(width=1500, height=900)
        kwargs = self.launch("--width", "1000", "--height", "700")
        self.assertEqual((kwargs["width"], kwargs["height"]), (1000, 700))

    def test_defaults_without_saved_state(self):
        kwargs = self.launch()
        self.assertEqual(
            (kwargs["width"], kwargs["height"], kwargs["maximized"]), (1280, 820, False)
        )

    def test_saved_language_is_used_unless_given(self):
        state.update_ui(language="en")
        self.launch()
        self.assertEqual(get_current_language(), "en")
        self.launch("--lang", "es")
        self.assertEqual(get_current_language(), "es")


class TestWindowPersists(WindowCase):
    def test_toggling_the_theme_is_remembered(self):
        manager = MagicMock()
        manager.get_dark.return_value = True
        with patch.object(Adw.StyleManager, "get_default", return_value=manager):
            self.window._toggle_theme(None)
            self.assertEqual(state.load()["ui"]["theme"], "light")
            manager.get_dark.return_value = False
            self.window._toggle_theme(None)
        self.assertEqual(state.load()["ui"]["theme"], "dark")

    def test_toggling_the_language_is_remembered(self):
        set_language("es")
        self.addCleanup(set_language, "es")
        with patch.object(self.window, "_update_ui_texts", create=True):
            self.window._toggle_language(None)
        self.assertEqual(state.load()["ui"]["language"], "en")

    def test_closing_saves_the_size_or_the_maximized_flag(self):
        with (
            patch.object(self.window, "is_maximized", return_value=False),
            patch.object(self.window, "get_width", return_value=1111),
            patch.object(self.window, "get_height", return_value=777),
        ):
            self.assertFalse(self.window._save_window_state())
        self.assertEqual(state.load()["ui"], {"maximized": False, "width": 1111, "height": 777})
        with patch.object(self.window, "is_maximized", return_value=True):
            self.window._save_window_state()
        self.assertEqual(
            state.load()["ui"], {"maximized": True, "width": 1111, "height": 777}
        )  # the last normal size is kept


class TestApplicationRestoresTheme(unittest.TestCase):
    def test_saved_scheme_is_applied_at_startup(self):
        from src.ui.app import GossipApplication

        app = GossipApplication()
        manager = MagicMock()
        with patch.object(Adw.StyleManager, "get_default", return_value=manager):
            app._apply_saved_theme()
            manager.set_color_scheme.assert_not_called()
            state.update_ui(theme="dark")
            app._apply_saved_theme()
            manager.set_color_scheme.assert_called_with(Adw.ColorScheme.FORCE_DARK)
            state.update_ui(theme="light")
            app._apply_saved_theme()
            manager.set_color_scheme.assert_called_with(Adw.ColorScheme.FORCE_LIGHT)


if __name__ == "__main__":
    unittest.main()
