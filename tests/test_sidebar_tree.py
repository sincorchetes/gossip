from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from src import tree
from src.models import SecretItem
from src.ui.windows.sidebar import NodeObject
from tests.window_case import WindowCase


def secrets(*ids):
    return [SecretItem(name=f"n/{i}", secret_id=i) for i in ids]


class TestSidebarTree(WindowCase):
    def setUp(self):
        super().setUp()
        self.versions = patch.object(self.window, "_load_versions_async")
        self.versions.start()
        self.addCleanup(self.versions.stop)

    def rows(self):
        return [
            (n.node.kind[0], n.node.depth, n.node.title)
            for n in (
                self.window.list_store.get_item(i)
                for i in range(self.window.list_store.get_n_items())
            )
        ]

    def load(self, *ids):
        self.window.selected_secret = None
        self.window.secrets = secrets(*ids)
        self.window._expanded_for = None
        self.window._render_secret_list()

    def activate(self, title):
        index = next(i for i, row in enumerate(self.rows()) if row[2] == title)
        self.window._on_row_activated(self.window.list_view, index)

    def test_small_lists_open_expanded_and_the_first_secret_is_selected(self):
        self.load("app/db", "app/api", "top")
        self.assertEqual(
            self.rows(),
            [("f", 0, "app"), ("s", 1, "api"), ("s", 1, "db"), ("s", 0, "top")],
        )
        self.assertEqual(self.window.selected_secret.secret_id, "app/api")
        self.assertEqual(self.window.sidebar_stack.get_visible_child_name(), "list")

    def test_clicking_a_folder_closes_and_reopens_it_and_keeps_the_selection(self):
        self.load("app/db", "app/api", "top")
        self.window.list_selection.set_selected(3)  # "top"
        self.assertEqual(self.window.selected_secret.secret_id, "top")
        self.activate("app")
        self.assertEqual(self.rows(), [("f", 0, "app"), ("s", 0, "top")])
        self.assertEqual(self.window.selected_secret.secret_id, "top")
        self.assertEqual(self.window.list_selection.get_selected(), 1)
        self.activate("app")
        self.assertEqual(len(self.rows()), 4)

    def test_long_lists_start_collapsed(self):
        self.load(*[f"folder{i}/item" for i in range(tree.EXPAND_ALL_LIMIT + 5)])
        self.assertTrue(all(kind == "f" for kind, _d, _t in self.rows()))
        self.activate("folder3")
        self.assertEqual(sum(1 for r in self.rows() if r[0] == "s"), 1)

    def test_switching_provider_resets_which_folders_are_open(self):
        self.load("app/db", "app/api")
        self.activate("app")
        self.assertEqual(self.rows(), [("f", 0, "app")])
        self.window.active_provider = self.mock_aws
        self.window._render_secret_list()
        self.assertEqual(len(self.rows()), 3)  # expanded again by default

    def test_selecting_a_row_shows_that_secret_and_folders_are_ignored(self):
        self.load("app/db", "top")
        with patch.object(self.window, "_on_secret_selected") as selected:
            self.window.list_selection.set_selected(2)  # "top"
            selected.assert_called_once()
            self.assertEqual(selected.call_args.args[0].secret_id, "top")
            selected.reset_mock()
            self.window._on_row_activated(self.window.list_view, 0)  # the folder
            selected.assert_not_called()
            self.window._on_row_activated(self.window.list_view, 99)  # out of range
        self.window._on_node_selected(self.window.list_selection, None)

    def test_searching_flattens_the_tree_and_clearing_restores_it(self):
        self.load("app/db-pass", "app/api", "other/db-host")
        self.window.search_entry.set_text("db")
        self.window._on_search_changed(self.window.search_entry)
        self.assertEqual(self.rows(), [("s", 0, "app/db-pass"), ("s", 0, "other/db-host")])
        self.window.search_entry.set_text("")
        self.window._on_search_changed(self.window.search_entry)
        self.assertEqual(len(self.rows()), 5)
        self.window.search_entry.set_text("zzz")
        self.window._on_search_changed(self.window.search_entry)
        self.assertEqual(self.window.list_stack.get_visible_child_name(), "none")

    def test_an_empty_list_shows_the_empty_state(self):
        self.load()
        self.assertEqual(self.rows(), [])
        self.assertEqual(self.window.sidebar_stack.get_visible_child_name(), "empty")

    def bind(self, node):
        item = MagicMock()
        self.window._setup_row(None, item)
        row = item.set_child.call_args.args[0]
        item.get_item.return_value = NodeObject(node)
        item.get_child.return_value = row
        self.window._bind_row(None, item)
        return item, row

    def test_binding_a_folder_row(self):
        item, row = self.bind(tree.Node(tree.FOLDER, "app", 2, "a/app", count=7, expanded=True))
        item.set_selectable.assert_called_with(False)
        self.assertEqual(row.title.get_label(), "app")
        self.assertFalse(row.subtitle.get_visible())
        self.assertEqual(row.badges.get_first_child().get_label(), "7")
        self.assertEqual(row.indent.get_size_request()[0], 32)
        _item, closed = self.bind(tree.Node(tree.FOLDER, "x", 0, "x"))
        self.assertEqual(closed.icon.get_icon_name(), "folder-symbolic")
        self.assertEqual(row.icon.get_icon_name(), "folder-open-symbolic")

    def test_binding_a_secret_row_reuses_the_widgets_cleanly(self):
        tagged = SecretItem(name="n", secret_id="a", labels={"env": "x"}, description="desc")
        item, row = self.bind(tree.Node(tree.SECRET, "a", 1, secret=tagged))
        item.set_selectable.assert_called_with(True)
        self.assertTrue(row.subtitle.get_visible())
        self.assertIn("desc", row.subtitle.get_label())
        self.assertEqual(row.badges.get_first_child().get_label(), "1 tags")
        # rebinding the same widgets to a plain secret removes the previous badges
        item.get_item.return_value = NodeObject(
            tree.Node(tree.SECRET, "b", 0, secret=secrets("b")[0])
        )
        self.window._bind_row(None, item)
        self.assertIsNone(row.badges.get_first_child())

    def test_ten_thousand_secrets_build_quickly(self):
        many = [
            SecretItem(name=f"n/{i}", secret_id=f"group{i % 50}/secret{i}") for i in range(10000)
        ]
        self.window.selected_secret = None
        self.window.secrets = many
        self.window._expanded_for = None
        started = time.perf_counter()
        self.window._render_secret_list()
        self.window.search_entry.set_text("secret99")
        self.window._on_search_changed(self.window.search_entry)
        self.assertLess(time.perf_counter() - started, 3.0)
        self.assertGreater(self.window.list_store.get_n_items(), 0)
