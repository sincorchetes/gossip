from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src import age
from src.i18n import set_language
from src.models import SecretItem
from tests.window_case import WindowCase

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


def secret(days_ago=None, created=None, tz=True):
    moment = None if days_ago is None else NOW - timedelta(days=days_ago)
    if moment is not None and not tz:
        moment = moment.replace(tzinfo=None)
    return SecretItem(name="n", secret_id="s", last_changed_date=moment, create_time=created)


class TestAge(unittest.TestCase):
    def test_threshold_setting(self):
        for raw, expected in ((None, 90), ("", 90), ("30", 30), ("0", 0), ("-5", 0), ("soon", 90)):
            env = {} if raw is None else {age.STALE_ENV: raw}
            with patch.dict(os.environ, env, clear=True):
                self.assertEqual(age.stale_days(), expected, raw)

    def test_age_prefers_the_last_change_and_handles_naive_dates(self):
        self.assertEqual(age.age_days(secret(10), NOW), 10)
        created = NOW - timedelta(days=40)
        self.assertEqual(age.age_days(secret(None, created=created), NOW), 40)
        self.assertEqual(age.age_days(secret(10, tz=False), NOW), 10)
        self.assertEqual(age.age_days(secret(10), NOW.replace(tzinfo=None)), 10)
        self.assertIsNone(age.age_days(secret(None), NOW))
        self.assertEqual(age.age_days(secret(-3), NOW), 0)  # clocks ahead never give negatives
        self.assertGreaterEqual(age.age_days(secret(1)), 0)  # default reference: now

    def test_stale_means_at_or_over_the_threshold(self):
        with patch.dict(os.environ, {age.STALE_ENV: "90"}):
            self.assertFalse(age.is_stale(secret(89), NOW))
            self.assertTrue(age.is_stale(secret(90), NOW))
            self.assertFalse(age.is_stale(secret(None), NOW))
        with patch.dict(os.environ, {age.STALE_ENV: "0"}):
            self.assertFalse(age.is_stale(secret(4000), NOW))


class TestUi(WindowCase):
    def setUp(self):
        super().setUp()
        set_language("en")
        self.addCleanup(set_language, "es")

    def badges(self, secret):
        """Bind a row for the secret and return the texts of its badges."""
        from unittest.mock import MagicMock

        from src import tree
        from src.ui.windows.sidebar import NodeObject

        item = MagicMock()
        self.window._setup_row(None, item)
        row = item.set_child.call_args.args[0]
        item.get_item.return_value = NodeObject(
            tree.Node(tree.SECRET, secret.secret_id, secret=secret)
        )
        item.get_child.return_value = row
        self.window._bind_row(None, item)
        texts, child = [], row.badges.get_first_child()
        while child is not None:
            texts.append(child.get_label())
            child = child.get_next_sibling()
        return texts

    def test_old_secrets_get_a_pill_and_recent_ones_do_not(self):
        old = SecretItem(
            name="old",
            secret_id="old",
            last_changed_date=datetime.now(timezone.utc) - timedelta(days=200),
        )
        new = SecretItem(
            name="new",
            secret_id="new",
            last_changed_date=datetime.now(timezone.utc) - timedelta(days=2),
        )
        with patch.dict(os.environ, {age.STALE_ENV: "90"}):
            self.assertIn("200 d", self.badges(old))
            self.assertFalse([t for t in self.badges(new) if t.endswith(" d")])

    def test_the_flag_can_be_turned_off(self):
        old = SecretItem(
            name="old",
            secret_id="old",
            last_changed_date=datetime.now(timezone.utc) - timedelta(days=500),
        )
        with patch.dict(os.environ, {age.STALE_ENV: "0"}):
            self.assertFalse([t for t in self.badges(old) if t.endswith(" d")])

    def test_the_detail_shows_how_long_ago_it_changed(self):
        self.window.selected_secret = SecretItem(
            name="n",
            secret_id="s",
            create_time=datetime.now(timezone.utc) - timedelta(days=300),
            last_changed_date=datetime.now(timezone.utc) - timedelta(days=12),
        )
        self.window._update_detail_labels()
        self.assertIn("changed 12 days ago", self.window.row_created.get_subtitle())


class TestFlag(unittest.TestCase):
    def test_flag_sets_the_environment(self):
        from src.main import main

        with (
            patch("src.ui.app.run_app", return_value=0),
            patch.dict(os.environ, {"DISPLAY": ":0"}),
            patch.object(sys, "argv", ["gossip", "--stale-days", "45"]),
        ):
            os.environ.pop(age.STALE_ENV, None)
            main()
            self.assertEqual(os.environ[age.STALE_ENV], "45")
            os.environ.pop(age.STALE_ENV, None)


if __name__ == "__main__":
    unittest.main()
