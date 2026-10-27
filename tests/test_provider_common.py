from __future__ import annotations

import unittest

from src.providers import common


class TestSplitVersion(unittest.TestCase):
    def test_numeric_suffix_is_split_and_an_explicit_version_wins(self):
        self.assertEqual(common.split_numeric_version("app/db@3"), ("app/db", "3"))
        self.assertEqual(common.split_numeric_version("app/db@3", "7"), ("app/db", "7"))
        self.assertEqual(common.split_numeric_version("/a/b@3", "5"), ("/a/b", "5"))

    def test_other_names_are_left_alone(self):
        self.assertEqual(common.split_numeric_version("a@b"), ("a@b", None))
        self.assertEqual(common.split_numeric_version("app/db"), ("app/db", None))
        self.assertEqual(common.split_numeric_version("app/db", "2"), ("app/db", "2"))
        self.assertEqual(common.split_numeric_version("a@1@x"), ("a@1@x", None))


class TestParseTime(unittest.TestCase):
    def test_nanoseconds_and_plain_seconds(self):
        parsed = common.parse_rfc3339("2026-03-01T10:20:30.123456789Z")
        self.assertEqual((parsed.year, parsed.minute, parsed.microsecond), (2026, 20, 123456))
        self.assertEqual(common.parse_rfc3339("2026-03-01T10:20:30Z").second, 30)

    def test_empty_zero_and_garbage_give_none(self):
        for value in ("", None, "0001-01-01T00:00:00Z", "garbage"):
            self.assertIsNone(common.parse_rfc3339(value), value)


class TestKeyValues(unittest.TestCase):
    def test_json_objects(self):
        self.assertEqual(common.parse_json_object('{"a": 1}'), {"a": 1})
        for text in ("{}", "[1]", "42", "plain", "", '"s"'):
            self.assertIsNone(common.parse_json_object(text), text)

    def test_formatting(self):
        self.assertEqual(common.format_key_values({"value": "plain"}), "plain")
        self.assertEqual(
            common.format_key_values({"a": "1", "b": "2"}), '{\n  "a": "1",\n  "b": "2"\n}'
        )
        # a text that looks like an object stays wrapped, so editing it does not restructure it
        wrapped = common.format_key_values({"value": '{"a": "1"}'})
        self.assertEqual(common.parse_json_object(wrapped), {"value": '{"a": "1"}'})
        self.assertEqual(common.format_key_values({"value": 5}), '{\n  "value": 5\n}')


if __name__ == "__main__":
    unittest.main()
