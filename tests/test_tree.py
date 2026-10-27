from __future__ import annotations

import unittest

from hypothesis import given, settings
from hypothesis import strategies as st

from src import tree
from src.models import SecretItem


def items(*ids, labels=None):
    return [SecretItem(name=f"n/{i}", secret_id=i, labels=labels or {}) for i in ids]


def titles(nodes):
    return [(n.kind[0], n.depth, n.title) for n in nodes]


class TestTree(unittest.TestCase):
    def test_flat_names_stay_flat_and_sorted(self):
        nodes = tree.build_nodes(items("b", "A", "c"), set())
        self.assertEqual(titles(nodes), [("s", 0, "A"), ("s", 0, "b"), ("s", 0, "c")])
        self.assertFalse(tree.has_folders(items("a", "b")))

    def test_slashes_make_folders_that_open_and_close(self):
        secrets = items("app/db", "app/prod/api", "app/prod/key", "root", "other/x")
        closed = tree.build_nodes(secrets, set())
        self.assertEqual(titles(closed), [("f", 0, "app"), ("f", 0, "other"), ("s", 0, "root")])
        self.assertEqual([n.count for n in closed if n.kind == "folder"], [3, 1])

        opened = tree.build_nodes(secrets, {"app", "app/prod"})
        self.assertEqual(
            titles(opened),
            [
                ("f", 0, "app"),
                ("f", 1, "prod"),
                ("s", 2, "api"),
                ("s", 2, "key"),
                ("s", 1, "db"),
                ("f", 0, "other"),
                ("s", 0, "root"),
            ],
        )
        self.assertTrue(opened[0].expanded and not opened[5].expanded)
        self.assertEqual(opened[1].path, "app/prod")
        self.assertEqual(opened[2].secret.secret_id, "app/prod/api")

    def test_a_search_lists_matches_flat_with_their_full_names(self):
        secrets = items("app/db-password", "app/api", "other/db-host")
        nodes = tree.build_nodes(secrets, set(), "db")
        self.assertEqual(titles(nodes), [("s", 0, "app/db-password"), ("s", 0, "other/db-host")])
        self.assertEqual(tree.build_nodes(secrets, set(), "nothing"), [])
        self.assertEqual(len(tree.build_nodes(secrets, set(), "   ")), 2)  # blank = no search

    def test_default_expansion_depends_on_the_size_of_the_list(self):
        small = items("a/b", "a/c/d")
        self.assertEqual(tree.default_expanded(small), {"a", "a/c"})
        big = items(*[f"f{i}/s" for i in range(tree.EXPAND_ALL_LIMIT + 1)])
        self.assertEqual(tree.default_expanded(big), set())

    def test_odd_names(self):
        nodes = tree.build_nodes(
            items("/lead/slash", "trail/", "//", "a//b"), {"lead", "trail", "a"}
        )
        self.assertTrue(all(n.title for n in nodes))
        self.assertEqual(len([n for n in nodes if n.kind == "secret"]), 4)

    @settings(max_examples=100, deadline=None)
    @given(
        st.lists(st.text(st.sampled_from("ab/c"), min_size=1, max_size=8), max_size=12, unique=True)
    )
    def test_every_secret_appears_exactly_once_when_everything_is_open(self, ids):
        secrets = items(*ids)
        nodes = tree.build_nodes(secrets, tree.folder_paths(secrets))
        shown = [n.secret.secret_id for n in nodes if n.kind == "secret"]
        self.assertEqual(sorted(shown), sorted(ids))


if __name__ == "__main__":
    unittest.main()
