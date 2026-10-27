from __future__ import annotations

import unittest

from src.diffing import (
    ADDED,
    CONTEXT,
    HEADER,
    HUNK,
    REMOVED,
    DiffLine,
    diff_payloads,
    normalize_payload,
)


class TestNormalizePayload(unittest.TestCase):
    def test_json_is_canonicalised(self):
        self.assertEqual(
            normalize_payload('{"b": 1,   "a": [1,2]}'),
            '{\n  "a": [\n    1,\n    2\n  ],\n  "b": 1\n}',
        )

    def test_invalid_json_and_plain_text_are_untouched(self):
        self.assertEqual(normalize_payload("{not json"), "{not json")
        self.assertEqual(normalize_payload("hunter2"), "hunter2")

    def test_non_ascii_is_preserved(self):
        self.assertIn("contraseña", normalize_payload('{"k": "contraseña"}'))


class TestDiffPayloads(unittest.TestCase):
    def test_identical_payloads_produce_no_diff(self):
        self.assertEqual(diff_payloads("same", "same", "v1", "v2"), [])

    def test_formatting_only_json_change_is_ignored(self):
        self.assertEqual(diff_payloads('{"a":1,"b":2}', '{\n "b": 2,\n "a": 1\n}', "v1", "v2"), [])

    def test_changed_line_is_reported_with_headers_and_hunk(self):
        lines = diff_payloads("user=admin\npass=old", "user=admin\npass=new", "v1", "v2")
        kinds = [line.kind for line in lines]
        self.assertEqual(kinds[:3], [HEADER, HEADER, HUNK])
        self.assertIn(DiffLine(REMOVED, "-pass=old"), lines)
        self.assertIn(DiffLine(ADDED, "+pass=new"), lines)
        self.assertIn(DiffLine(CONTEXT, " user=admin"), lines)

    def test_labels_appear_in_headers(self):
        lines = diff_payloads("a", "b", "Version 1", "Version 2")
        self.assertEqual(lines[0], DiffLine(HEADER, "--- Version 1"))
        self.assertEqual(lines[1], DiffLine(HEADER, "+++ Version 2"))

    def test_json_key_change_is_localised(self):
        lines = diff_payloads('{"a": 1, "b": 2}', '{"a": 1, "b": 3}', "v1", "v2")
        self.assertIn(DiffLine(REMOVED, '-  "b": 2'), lines)
        self.assertIn(DiffLine(ADDED, '+  "b": 3'), lines)


if __name__ == "__main__":
    unittest.main()
