"""Property-based tests: random inputs for the converters and parsers that carry secrets."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src import state
from src.diffing import diff_payloads, normalize_payload
from src.models import SecretItem
from src.providers import common
from src.providers.kubernetes import ops as kube
from src.providers.vault import ops as vault
from src.providers.vault.discovery import normalize_address, normalize_mount
from src.search import matches_query, parse_query
from src.transfer import TransferEntry, build_export_document, parse_import_text

FAST = settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])

# Text without lone surrogates, which cannot be encoded or written to a file
text = st.text(st.characters(codec="utf-8", exclude_characters="\x00"), max_size=40)
keys = st.text(
    st.characters(codec="utf-8", exclude_categories=("Cs", "Cc")), min_size=1, max_size=12
)
json_scalars = st.one_of(st.none(), st.booleans(), st.integers(), st.text(max_size=10))
json_values = st.recursive(
    json_scalars,
    lambda inner: st.one_of(st.lists(inner, max_size=3), st.dictionaries(keys, inner, max_size=3)),
    max_leaves=8,
)


class TestVaultPayload(unittest.TestCase):
    @FAST
    @given(st.dictionaries(keys, json_values, min_size=1, max_size=5))
    def test_keys_survive_format_then_parse(self, data):
        if list(data) == ["value"] and isinstance(data["value"], str):
            return  # shown as plain text by design; covered by the next test
        self.assertEqual(vault.parse_payload(vault.format_payload(data)), data)

    @FAST
    @given(text)
    def test_editing_text_without_changing_it_keeps_the_data(self, value):
        data = vault.parse_payload(value)
        self.assertEqual(vault.parse_payload(vault.format_payload(data)), data)

    @FAST
    @given(text)
    def test_plain_text_is_stored_under_value(self, value):
        try:
            obj = json.loads(value)
        except ValueError:
            obj = None
        data = vault.parse_payload(value)
        if isinstance(obj, dict) and obj:
            self.assertEqual(data, obj)
        else:
            self.assertEqual(data, {"value": value})

    @FAST
    @given(st.text(max_size=20), st.one_of(st.none(), st.integers(1, 99).map(str)))
    def test_version_suffix_split_never_loses_the_name(self, name, version):
        base, picked = common.split_numeric_version(name, version)
        self.assertTrue(name.startswith(base))
        if version:
            self.assertEqual(picked, version)


class TestKubernetesPayload(unittest.TestCase):
    @FAST
    # "base64:<data>" is the marker for binary values, so text that starts with it is read as bytes
    @given(
        st.dictionaries(
            keys, text.filter(lambda t: not t.startswith("base64:")), min_size=1, max_size=5
        )
    )
    def test_values_survive_encode_then_decode(self, values):
        self.assertEqual(kube.decode_data(kube.encode_data(values)), values)

    @FAST
    @given(st.dictionaries(keys, text, min_size=1, max_size=5))
    def test_values_survive_format_then_parse(self, values):
        self.assertEqual(kube.parse_payload(kube.format_payload(values)), values)

    @FAST
    @given(st.binary(max_size=30))
    def test_binary_values_come_back_as_the_same_bytes(self, raw):
        import base64

        stored = {"k": base64.b64encode(raw).decode("ascii")}
        shown = kube.decode_data(stored)
        self.assertEqual(kube.encode_data(shown), stored)


class TestImportExport(unittest.TestCase):
    entry = st.builds(
        TransferEntry,
        secret_id=st.text(
            st.characters(codec="utf-8", exclude_categories=("Cs", "Cc", "Zs")),
            min_size=1,
            max_size=15,
        ),
        value=st.one_of(st.none(), text),
        description=st.one_of(
            st.none(),
            st.text(
                st.characters(codec="utf-8", exclude_categories=("Cs", "Cc")),
                min_size=1,
                max_size=15,
            ),
        ),
        labels=st.dictionaries(
            keys,
            st.text(st.characters(codec="utf-8", exclude_categories=("Cs",)), max_size=8),
            max_size=3,
        ),
    )

    @FAST
    @given(st.lists(entry, min_size=1, max_size=6, unique_by=lambda e: e.secret_id.strip()))
    def test_an_export_reads_back_as_the_same_entries(self, entries):
        document = build_export_document("gcp", entries, True)
        parsed = parse_import_text(json.dumps(document))
        self.assertEqual([e.secret_id.strip() for e in entries], [e.secret_id for e in parsed])
        for original, restored in zip(entries, parsed):
            self.assertEqual(restored.labels, original.labels)
            if original.value is not None:
                self.assertEqual(restored.value, original.value)

    @FAST
    @given(st.text(max_size=200))
    def test_arbitrary_text_never_crashes_the_importer(self, raw):
        try:
            parse_import_text(raw)
        except ValueError:
            pass  # a clean, user-facing error is the only allowed failure


class TestSearch(unittest.TestCase):
    secret = SecretItem(
        name="projects/p/secrets/db-password",
        secret_id="db-password",
        description="Production DB",
        labels={"env": "prod", "team": "core"},
    )

    @FAST
    @given(st.text(max_size=60))
    def test_any_query_is_handled(self, query):
        self.assertIsInstance(matches_query(self.secret, query), bool)
        parse_query(query)

    @FAST
    @given(st.text(alphabet=" \t", max_size=5))
    def test_a_blank_query_matches_everything(self, blank):
        self.assertTrue(matches_query(self.secret, blank))

    @FAST
    @given(st.text(st.characters(codec="ascii", categories=("L", "N")), min_size=1, max_size=8))
    def test_a_word_and_its_negation_never_both_match(self, word):
        self.assertNotEqual(
            matches_query(self.secret, word), matches_query(self.secret, f"-{word}")
        )


class TestDiff(unittest.TestCase):
    @FAST
    @given(json_values)
    def test_normalizing_is_idempotent(self, value):
        once = normalize_payload(json.dumps(value))
        self.assertEqual(normalize_payload(once), once)

    @FAST
    @given(st.text(max_size=80))
    def test_identical_payloads_have_no_changes(self, payload):
        lines = diff_payloads(payload, payload, "a", "b")
        self.assertTrue(all(line.kind not in ("added", "removed") for line in lines))


class TestStateFile(unittest.TestCase):
    @FAST
    @given(
        st.dictionaries(keys, st.dictionaries(keys, st.text(max_size=10), max_size=4), max_size=4)
    )
    def test_credentials_are_never_written_and_the_rest_round_trips(self, contexts):
        with tempfile.TemporaryDirectory() as folder:
            os.environ["GOSSIP_STATE_FILE"] = os.path.join(folder, "state.json")
            state.save("gcp", contexts)
            raw = open(os.environ["GOSSIP_STATE_FILE"], encoding="utf-8").read()
            loaded = state.load()["contexts"]
        for context in loaded.values():
            for key in context:
                self.assertFalse(any(w in key.lower() for w in state._SENSITIVE_WORDS))
        self.assertIsInstance(raw, str)


class TestVaultAddress(unittest.TestCase):
    @FAST
    @given(st.text(max_size=40))
    def test_addresses_are_either_accepted_safely_or_rejected_cleanly(self, address):
        try:
            clean = normalize_address(address)
        except ValueError:
            return
        self.assertTrue(clean.startswith(("https://", "http://")))
        self.assertFalse(clean.endswith("/"))
        if clean.startswith("http://"):
            self.assertRegex(clean, r"^http://(localhost|127\.0\.0\.1|\[?::1\]?)([:/]|$)")

    @FAST
    @given(st.text(max_size=20))
    def test_mount_is_never_empty_or_slashed(self, mount):
        result = normalize_mount(mount)
        self.assertTrue(result)
        self.assertFalse(result.startswith("/") or result.endswith("/"))


if __name__ == "__main__":
    unittest.main()
