from __future__ import annotations

import unittest
from unittest.mock import patch

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src import state
from src.i18n import set_language
from src.models import SecretItem, SecretVersionItem
from src.ui.dialogs import CompareTarget, show_compare_secrets_dialog
from tests.test_window import DummySyncThread
from tests.window_case import WindowCase

SYNC = (
    patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)),
    patch("threading.Thread", side_effect=DummySyncThread),
)


def buffer_text(win):
    buffer = win.diff_buffer
    return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)


class TestDialog(unittest.TestCase):
    def setUp(self):
        set_language("en")
        self.addCleanup(set_language, "es")
        self.secrets = [
            SecretItem(name="n/db", secret_id="db"),
            SecretItem(name="n/api", secret_id="api"),
        ]
        self.target = CompareTarget(
            "Prod", lambda: self.secrets, lambda secret: f"value of {secret.secret_id}\n"
        )

    def open(self, targets=None, fetch_current=lambda: "value of db\n"):
        with SYNC[0], SYNC[1], patch.object(Adw.Window, "present"):
            return show_compare_secrets_dialog(
                Gtk.Window(), "AWS / db", fetch_current, targets or [self.target]
            )

    def rows(self, win):
        titles, index = [], 0
        while (row := win.secret_list.get_row_at_index(index)) is not None:
            titles.append((row.get_title(), row.get_mapped()))
            index += 1
        return [t for t, _ in titles]

    def test_the_secrets_of_the_first_place_are_listed(self):
        win = self.open()
        self.assertEqual(self.rows(win), ["db", "api"])
        self.assertFalse(win.compare_btn.get_sensitive())

    def test_comparing_shows_the_diff_and_counts_changes(self):
        win = self.open(fetch_current=lambda: "old\n")
        win.secret_list.select_row(win.secret_list.get_row_at_index(1))
        self.assertTrue(win.compare_btn.get_sensitive())
        with SYNC[0], SYNC[1]:
            win.compare_btn.emit("clicked")
        self.assertIn("-old", buffer_text(win))
        self.assertIn("+value of api", buffer_text(win))
        self.assertEqual(win.status_label.get_label(), "1 added, 1 removed")

    def test_identical_values_are_reported(self):
        win = self.open()
        win.secret_list.select_row(win.secret_list.get_row_at_index(0))
        with SYNC[0], SYNC[1]:
            win.compare_btn.emit("clicked")
        self.assertEqual(win.status_label.get_label(), "The two values are identical")

    def test_errors_listing_or_comparing_are_shown(self):
        def broken():
            raise RuntimeError("no access")

        win = self.open([CompareTarget("Bad", broken, lambda s: "")])
        self.assertIn("no access", win.status_label.get_label())

        win = self.open(fetch_current=broken)
        win.secret_list.select_row(win.secret_list.get_row_at_index(0))
        with SYNC[0], SYNC[1]:
            win.compare_btn.emit("clicked")
        self.assertIn("no access", win.status_label.get_label())

    def test_changing_the_place_reloads_and_stale_answers_are_ignored(self):
        other = CompareTarget(
            "Staging", lambda: [SecretItem(name="x", secret_id="only")], lambda s: ""
        )
        win = self.open([self.target, other])
        with SYNC[0], SYNC[1]:
            win.target_row.set_selected(1)
        self.assertEqual(self.rows(win), ["only"])

        pending = []
        with (
            patch(
                "gi.repository.GLib.idle_add", side_effect=lambda fn, *a: pending.append((fn, a))
            ),
            patch("threading.Thread", side_effect=DummySyncThread),
            patch.object(Adw.Window, "present"),
        ):
            win = show_compare_secrets_dialog(Gtk.Window(), "x", lambda: "", [self.target, other])
            win.target_row.set_selected(1)
        for fn, args in pending:
            fn(*args)
        self.assertEqual(self.rows(win), ["only"])

    def test_the_filter_hides_non_matching_secrets_and_closing_clears_the_diff(self):
        win = self.open()
        win.search.set_text("ap")
        win.search.emit("search-changed")
        visible = [win.secret_list.get_row_at_index(i).get_child_visible() for i in range(2)]
        self.assertEqual(visible, [False, True])  # only "api" contains "ap"
        win.diff_buffer.set_text("secret")
        win.emit("close-request")
        self.assertEqual(buffer_text(win), "")

    def test_nothing_happens_without_a_selection_or_places(self):
        win = self.open(targets=[])
        win.compare_btn.emit("clicked")
        self.assertFalse(win.compare_btn.get_sensitive())


class TestWindowFlow(WindowCase):
    def setUp(self):
        super().setUp()
        set_language("en")
        self.addCleanup(set_language, "es")
        self.secret = SecretItem(name="projects/p/secrets/db", secret_id="db")
        self.window.selected_secret = self.secret

    def test_targets_cover_every_provider_and_their_recent_contexts(self):
        self.mock_gcp.saved_context.return_value = {"project": "now"}
        for provider in self.window.providers.values():
            provider.display_name = provider.display_name or provider.provider_id
        state.save(
            "gcp",
            {},
            {"gcp": [{"project": "now"}, {"project": "old"}], "ansible": [{"vault_file": "x"}]},
        )
        targets = self.window._compare_targets()
        labels = [t.label for t in targets]
        self.assertEqual(
            len([name for name in labels if "Ansible" in name]), 1
        )  # never a second vault file
        self.assertTrue(any("project=old" in name for name in labels))
        self.assertFalse(
            any("project=now" in name for name in labels)
        )  # the current one is not repeated

    def test_the_target_reads_the_latest_value_of_a_secret(self):
        provider = self.mock_gcp
        provider.list_versions.return_value = [
            SecretVersionItem(version_id="3", name="s/versions/3")
        ]
        provider.access_secret_payload.return_value = ("latest", False)
        target = self.window._compare_targets()[0]
        self.assertEqual(target.fetch_value(self.secret), "latest")
        provider.access_secret_payload.assert_called_with("s/versions/3")
        provider.list_versions.return_value = []
        self.assertEqual(target.fetch_value(self.secret), "")
        self.assertIs(target.list_secrets, provider.list_secrets)

    def test_the_button_opens_the_dialog_for_the_selected_secret(self):
        self.window.active_provider = self.mock_gcp
        self.mock_gcp.list_versions.return_value = [SecretVersionItem(version_id="1", name="v1")]
        self.mock_gcp.access_secret_payload.return_value = ("cur", False)
        with patch.object(self.window.dialogs, "compare_secrets") as show:
            self.window._on_compare_with_other(None)
            args = show.call_args.args
            self.assertIn("db", args[1])
            self.assertEqual(args[2](), "cur")
            self.assertGreaterEqual(len(args[3]), 1)
            self.window.selected_secret = None
            show.reset_mock()
            self.window._on_compare_with_other(None)
            show.assert_not_called()


if __name__ == "__main__":
    unittest.main()
