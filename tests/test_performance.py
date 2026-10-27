"""Loose upper bounds that catch an accidental slowdown (for example quadratic loops).

The limits are an order of magnitude above what a normal machine needs, so they only fail when
something is genuinely wrong, not because a CI runner is busy.
"""

from __future__ import annotations

import subprocess
import sys
import time
import unittest

from src import tree
from src.models import SecretItem
from src.search import matches_query

COUNT = 10_000


def many(count: int = COUNT):
    return [
        SecretItem(
            name=f"projects/p/secrets/team{i % 40}/app{i % 300}/key{i}",
            secret_id=f"team{i % 40}/app{i % 300}/key{i}",
            description="Production credentials" if i % 7 == 0 else None,
            labels={"env": "prod" if i % 2 else "dev"},
        )
        for i in range(count)
    ]


class TestLargeLists(unittest.TestCase):
    def timed(self, call, limit):
        start = time.perf_counter()
        result = call()
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, limit, f"took {elapsed:.2f}s (limit {limit}s)")
        return result

    def test_building_the_tree_of_ten_thousand_secrets(self):
        secrets = many()
        nodes = self.timed(lambda: tree.build_nodes(secrets, set()), 3)
        self.assertTrue(nodes)
        everything = tree.folder_paths(secrets)
        flat = self.timed(lambda: tree.build_nodes(secrets, everything), 3)
        self.assertGreaterEqual(len(flat), COUNT)

    def test_searching_ten_thousand_secrets(self):
        secrets = many()
        found = self.timed(lambda: tree.build_nodes(secrets, set(), "label:env=prod key9"), 3)
        self.assertTrue(found)
        hits = self.timed(lambda: [s for s in secrets if matches_query(s, "-dev app5")], 3)
        self.assertTrue(hits)


class TestStartup(unittest.TestCase):
    def test_help_does_not_import_the_cloud_clients(self):
        """--help must stay instant: no provider SDK may be imported just to print it."""
        code = (
            "import sys; sys.argv=['gossip','--help']\n"
            "from src.main import _build_parser\n"
            "_build_parser()\n"
            "heavy=[m for m in ('boto3','botocore','google.cloud','azure.identity','kubernetes') if m in sys.modules]\n"
            "print(','.join(heavy))"
        )
        start = time.perf_counter()
        out = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=True, timeout=60
        )
        self.assertEqual(out.stdout.strip(), "", "heavy SDKs imported by the parser")
        self.assertLess(time.perf_counter() - start, 15)


if __name__ == "__main__":
    unittest.main()
