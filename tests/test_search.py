from __future__ import annotations

import unittest

from src.models import SecretItem
from src.search import matches_query, parse_query


def _secret(secret_id="db_password", description="Database credentials", **labels):
    return SecretItem(
        name=f"projects/p/secrets/{secret_id}",
        secret_id=secret_id,
        description=description,
        labels=labels,
    )


class TestParseQuery(unittest.TestCase):
    def test_splits_words_exclusions_and_labels(self):
        self.assertEqual(
            parse_query("DB -legacy label:Env=Prod tag:tier"),
            (["db"], ["legacy"], [("env", "prod"), ("tier", None)]),
        )

    def test_ignores_empty_label_and_lone_dash(self):
        self.assertEqual(parse_query("label: - tag:"), ([], [], []))

    def test_empty_query(self):
        self.assertEqual(parse_query("   "), ([], [], []))


class TestMatchesQuery(unittest.TestCase):
    def test_empty_query_matches_everything(self):
        self.assertTrue(matches_query(_secret(), ""))
        self.assertTrue(matches_query(_secret(), "   "))

    def test_matches_name_description_and_labels(self):
        secret = _secret(tier="backend")
        for query in ("db", "credentials", "backend", "TIER"):
            self.assertTrue(matches_query(secret, query), query)
        self.assertFalse(matches_query(secret, "nonexistent_term"))

    def test_all_words_must_match_in_any_order(self):
        secret = _secret(tier="backend")
        self.assertTrue(matches_query(secret, "backend db"))
        self.assertFalse(matches_query(secret, "db frontend"))

    def test_words_may_match_different_fields(self):
        self.assertTrue(matches_query(_secret(), "password database"))

    def test_exclusion(self):
        secret = _secret(env="legacy")
        self.assertFalse(matches_query(secret, "db -legacy"))
        self.assertTrue(matches_query(secret, "db -staging"))

    def test_label_key_filter(self):
        secret = _secret(env="prod")
        self.assertTrue(matches_query(secret, "label:env"))
        self.assertTrue(matches_query(secret, "tag:ENV"))
        self.assertFalse(matches_query(secret, "label:tier"))

    def test_label_value_filter_is_exact(self):
        secret = _secret(env="prod")
        self.assertTrue(matches_query(secret, "label:env=prod"))
        self.assertTrue(matches_query(secret, "label:env=PROD"))
        self.assertFalse(matches_query(secret, "label:env=pro"))
        self.assertFalse(matches_query(secret, "label:env=staging"))

    def test_label_filter_combined_with_words(self):
        self.assertTrue(matches_query(_secret(env="prod"), "db label:env=prod"))
        self.assertFalse(matches_query(_secret("api_key", "x", env="prod"), "db label:env=prod"))

    def test_missing_description_is_handled(self):
        secret = SecretItem(name="n", secret_id="only_name", description=None)
        self.assertTrue(matches_query(secret, "only"))


if __name__ == "__main__":
    unittest.main()
