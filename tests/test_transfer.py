from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src import transfer
from src.models import SecretItem, SecretVersionItem
from src.transfer import (
    ImportResult,
    TransferEntry,
    build_export_document,
    collect_export_entries,
    import_entries,
    parse_import_text,
    read_import_file,
    write_export_file,
)


def _secret(secret_id, description=None, **labels):
    return SecretItem(
        name=f"projects/p/secrets/{secret_id}",
        secret_id=secret_id,
        description=description,
        labels=labels,
    )


class TestCollectExportEntries(unittest.TestCase):
    def test_without_values_does_not_touch_payloads(self):
        client = MagicMock()
        entries, errors = collect_export_entries(client, [_secret("a", "desc", env="prod")], False)
        self.assertEqual(entries, [TransferEntry("a", None, "desc", {"env": "prod"})])
        self.assertEqual(errors, [])
        client.access_secret_payload.assert_not_called()

    def test_with_values_reads_latest_version_and_reports_progress(self):
        client = MagicMock()
        client.list_versions.return_value = [
            SecretVersionItem("2", "v2"),
            SecretVersionItem("1", "v1"),
        ]
        client.access_secret_payload.return_value = ("s3cret", False)
        steps = []
        entries, errors = collect_export_entries(
            client, [_secret("a"), _secret("b")], True, lambda d, t: steps.append((d, t))
        )
        self.assertEqual([e.value for e in entries], ["s3cret", "s3cret"])
        client.access_secret_payload.assert_called_with("v2")
        self.assertEqual(steps, [(1, 2), (2, 2)])
        self.assertEqual(errors, [])

    def test_secret_without_versions_exports_empty_value(self):
        client = MagicMock()
        client.list_versions.return_value = []
        entries, _errors = collect_export_entries(client, [_secret("a")], True)
        self.assertEqual(entries[0].value, "")

    def test_read_failure_is_reported_and_export_continues(self):
        client = MagicMock()
        client.list_versions.side_effect = [RuntimeError("denied"), [SecretVersionItem("1", "v1")]]
        client.access_secret_payload.return_value = ("ok", False)
        entries, errors = collect_export_entries(client, [_secret("a"), _secret("b")], True)
        self.assertIsNone(entries[0].value)
        self.assertEqual(entries[1].value, "ok")
        self.assertEqual(errors, ["a: denied"])


class TestNativeValues(unittest.TestCase):
    def _ansible(self, type_name):
        return SecretItem(
            name="v.yml::x", secret_id="x", provider="ansible", labels={"type": type_name}
        )

    def test_structured_values_become_native_objects(self):
        self.assertEqual(
            transfer._native_value(self._ansible("dict"), "key: abc\nttl: 30\n"),
            {"key": "abc", "ttl": 30},
        )
        self.assertEqual(transfer._native_value(self._ansible("list"), "- a\n- b\n"), ["a", "b"])
        self.assertEqual(transfer._native_value(self._ansible("int"), "30"), 30)
        self.assertIs(transfer._native_value(self._ansible("bool"), "True"), True)

    def test_strings_other_providers_and_bad_yaml_are_left_alone(self):
        self.assertEqual(transfer._native_value(self._ansible("str"), "30"), "30")
        gcp = SecretItem(name="n", secret_id="x", provider="gcp", labels={"type": "dict"})
        self.assertEqual(transfer._native_value(gcp, "a: 1"), "a: 1")
        self.assertEqual(
            transfer._native_value(self._ansible("dict"), "a: [unclosed"), "a: [unclosed"
        )
        self.assertEqual(transfer._native_value(self._ansible("dict"), "just text"), "just text")

    def test_collect_exports_structured_ansible_values_natively(self):
        client = MagicMock()
        client.list_versions.return_value = [SecretVersionItem("1", "x")]
        client.access_secret_payload.return_value = ("key: abc\n", False)
        entries, _errors = collect_export_entries(client, [self._ansible("dict")], True)
        self.assertEqual(entries[0].value, {"key": "abc"})
        document = build_export_document("ansible", entries, True)
        self.assertEqual(json.loads(json.dumps(document))["secrets"][0]["value"], {"key": "abc"})


class TestBuildAndWrite(unittest.TestCase):
    def test_document_structure_and_value_inclusion(self):
        entries = [TransferEntry("a", "v", "d", {"k": "x"}), TransferEntry("b", None)]
        now = datetime(2026, 1, 2, 3, 4, 5, 999, tzinfo=timezone.utc)
        doc = build_export_document("gcp", entries, True, now)
        self.assertEqual(doc["format"], transfer.FORMAT_NAME)
        self.assertEqual(doc["exported_at"], "2026-01-02T03:04:05+00:00")
        self.assertEqual(
            doc["secrets"][0], {"id": "a", "description": "d", "labels": {"k": "x"}, "value": "v"}
        )
        self.assertEqual(doc["secrets"][1], {"id": "b"})

    def test_values_are_left_out_when_not_requested(self):
        doc = build_export_document("aws", [TransferEntry("a", "v")], False)
        self.assertNotIn("value", doc["secrets"][0])
        self.assertFalse(doc["includes_values"])

    def test_default_timestamp_is_used(self):
        self.assertIn("T", build_export_document("gcp", [], False)["exported_at"])

    def test_write_is_atomic_utf8_and_owner_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "export.json")
            write_export_file(path, {"secrets": [{"id": "contraseña"}]})
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(json.load(handle)["secrets"][0]["id"], "contraseña")
            self.assertFalse(os.path.exists(path + ".tmp"))
            if sys.platform != "win32":
                self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)


class TestParseImport(unittest.TestCase):
    def test_round_trip_of_an_export_document(self):
        doc = build_export_document("gcp", [TransferEntry("a", "v", "d", {"k": "x"})], True)
        entries = parse_import_text(json.dumps(doc))
        self.assertEqual(entries, [TransferEntry("a", "v", "d", {"k": "x"})])

    def test_plain_mapping_keeps_value_types(self):
        entries = parse_import_text(
            '{"db": "pw", "port": 5432, "cfg": {"a": 1}, "on": true, "off": null}'
        )
        values = {e.secret_id: e.value for e in entries}
        self.assertEqual(
            values, {"db": "pw", "port": 5432, "cfg": {"a": 1}, "on": True, "off": None}
        )

    def test_unusual_yaml_types_become_text(self):
        import datetime

        entries = parse_import_text("when: 2026-10-26\n")
        self.assertEqual(entries[0].value, str(datetime.date(2026, 10, 26)))

    def test_yaml_is_accepted(self):
        self.assertEqual(parse_import_text("a: 1\nb: two\n")[1].value, "two")

    def test_alternative_id_keys(self):
        text = json.dumps({"secrets": [{"secret_id": "x"}, {"name": "y"}]})
        self.assertEqual([e.secret_id for e in parse_import_text(text)], ["x", "y"])

    def test_duplicates_keep_first_occurrence(self):
        text = json.dumps({"secrets": [{"id": "a", "value": "1"}, {"id": "a", "value": "2"}]})
        entries = parse_import_text(text)
        self.assertEqual([(e.secret_id, e.value) for e in entries], [("a", "1")])

    def test_invalid_inputs_raise_value_error(self):
        bad = {
            "empty": "  ",
            "scalar": "42",
            "list": "[1, 2]",
            "empty_mapping": "{}",
            "no_secrets": '{"secrets": []}',
            "entry_not_object": '{"secrets": ["x"]}',
            "missing_id": '{"secrets": [{"value": "v"}]}',
            "bad_labels": '{"secrets": [{"id": "a", "labels": [1]}]}',
            "non_string_keys": "1: a\n2: b\n",
        }
        for name, text in bad.items():
            with self.subTest(name), self.assertRaises(ValueError):
                parse_import_text(text)

    def test_syntax_error_does_not_leak_contents(self):
        with self.assertRaises(ValueError) as ctx:
            parse_import_text('{"id": "hunter2-secret", [unclosed')
        self.assertNotIn("hunter2", str(ctx.exception))

    def test_syntax_error_without_position(self):
        import yaml

        with unittest.mock.patch("yaml.safe_load", side_effect=yaml.YAMLError("boom")):
            with self.assertRaises(ValueError):
                parse_import_text("x: 1")

    def test_too_many_entries_are_rejected(self):
        text = json.dumps({f"s{i}": "v" for i in range(transfer.MAX_IMPORT_ENTRIES + 1)})
        with self.assertRaises(ValueError):
            parse_import_text(text)

    def test_null_labels_and_description(self):
        entry = parse_import_text('{"secrets": [{"id": "a", "labels": null, "description": 5}]}')[0]
        self.assertEqual((entry.labels, entry.description), ({}, "5"))


class TestReadImportFile(unittest.TestCase):
    def test_reads_and_parses(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "in.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('{"a": "1"}')
            self.assertEqual(read_import_file(path)[0].secret_id, "a")

    def test_oversized_file_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "big.json")
            with open(path, "w") as handle:
                handle.write("x")
            with unittest.mock.patch.object(transfer, "MAX_IMPORT_BYTES", 0):
                with self.assertRaises(ValueError):
                    read_import_file(path)


class TestImportEntries(unittest.TestCase):
    def test_creates_skips_and_collects_failures_without_overwriting(self):
        client = MagicMock()
        client.create_secret.side_effect = [None, RuntimeError("quota")]
        entries = [
            TransferEntry("new1", "v", "d", {"k": "x"}),
            TransferEntry("old", "v"),
            TransferEntry("bad", None),
        ]
        steps = []
        result = import_entries(client, entries, {"old"}, lambda d, t: steps.append(d))
        self.assertEqual(result, ImportResult(["new1"], ["old"], [("bad", "quota")]))
        self.assertEqual(steps, [1, 2, 3])
        client.create_secret.assert_any_call("new1", "v", labels={"k": "x"}, description="d")
        client.create_secret.assert_any_call("bad", "", labels=None, description=None)
        self.assertEqual(client.create_secret.call_count, 2)


if __name__ == "__main__":
    unittest.main()


class TestRoundTripWithRealProvider(unittest.TestCase):
    """Export a real Ansible vault with values and import it into a fresh one."""

    def test_export_then_import_between_vaults(self):
        from src.providers.ansible import AnsibleVaultClient

        with tempfile.TemporaryDirectory() as tmp:
            source = AnsibleVaultClient(
                vault_file=os.path.join(tmp, "source.yml"), password="pw-source"
            )
            source.create_new_vault_file(source.vault_file, "pw-source")
            source.create_secret("db_password", "hunter2")
            source.create_secret("api", '{"key": "abc", "ttl": 30}')

            entries, errors = collect_export_entries(source, source.list_secrets(), True)
            self.assertEqual(errors, [])
            path = os.path.join(tmp, "export.json")
            write_export_file(path, build_export_document("ansible", entries, True))

            target = AnsibleVaultClient(
                vault_file=os.path.join(tmp, "target.yml"), password="pw-target"
            )
            target.create_new_vault_file(target.vault_file, "pw-target")
            result = import_entries(target, read_import_file(path), set())

            self.assertEqual(sorted(result.created), ["api", "db_password"])
            self.assertEqual(result.failed, [])
            versions = target.list_versions("db_password")
            self.assertEqual(target.access_secret_payload(versions[0].name)[0], "hunter2")
            # Structured Ansible values keep their type through the export file
            self.assertEqual(target._load_data()["api"], {"key": "abc", "ttl": 30})

            # Importing again must not overwrite anything
            again = import_entries(target, read_import_file(path), {"db_password", "api"})
            self.assertEqual(sorted(again.skipped), ["api", "db_password"])


class TestTypedImport(unittest.TestCase):
    def test_non_ansible_providers_receive_text(self):
        client = MagicMock(spec=["create_secret"])
        entries = [
            TransferEntry("n", 30),
            TransferEntry("b", True),
            TransferEntry("d", {"a": 1}),
            TransferEntry("s", "text"),
            TransferEntry("e", None),
        ]
        import_entries(client, entries, set())
        sent = {c.args[0]: c.args[1] for c in client.create_secret.call_args_list}
        self.assertEqual(sent, {"n": "30", "b": "true", "d": '{"a": 1}', "s": "text", "e": ""})

    def test_ansible_keeps_numbers_booleans_and_structures(self):
        from src.providers.ansible import AnsibleVaultClient

        with tempfile.TemporaryDirectory() as tmp:
            target = AnsibleVaultClient(vault_file=os.path.join(tmp, "t.yml"), password="pw")
            target.create_new_vault_file(target.vault_file, "pw")
            entries = parse_import_text(
                '{"port": 5432, "ratio": 1.5, "debug": true, "cfg": {"a": [1, 2]}, "name": "x"}'
            )
            result = import_entries(target, entries, set())

            self.assertEqual(result.failed, [])
            data = target._load_data()
            self.assertEqual(data["port"], 5432)
            self.assertIsInstance(data["port"], int)
            self.assertEqual(data["ratio"], 1.5)
            self.assertIs(data["debug"], True)
            self.assertEqual(data["cfg"], {"a": [1, 2]})
            self.assertEqual(data["name"], "x")
            self.assertEqual(
                {s.secret_id: s.labels["type"] for s in target.list_secrets()}["port"], "int"
            )

    def test_full_round_trip_preserves_types_between_ansible_vaults(self):
        from src.providers.ansible import AnsibleVaultClient

        with tempfile.TemporaryDirectory() as tmp:
            source = AnsibleVaultClient(vault_file=os.path.join(tmp, "s.yml"), password="a")
            source.create_new_vault_file(source.vault_file, "a")
            source.create_native_secret("port", 8080)
            source.create_native_secret("debug", False)
            source.create_native_secret("cfg", {"k": "v"})
            entries, errors = collect_export_entries(source, source.list_secrets(), True)
            self.assertEqual(errors, [])
            path = os.path.join(tmp, "x.json")
            write_export_file(path, build_export_document("ansible", entries, True))

            target = AnsibleVaultClient(vault_file=os.path.join(tmp, "t.yml"), password="b")
            target.create_new_vault_file(target.vault_file, "b")
            import_entries(target, read_import_file(path), set())

            self.assertEqual(target._load_data(), {"port": 8080, "debug": False, "cfg": {"k": "v"}})

    def test_create_native_secret_rejects_duplicates(self):
        from src.providers.ansible import AnsibleVaultClient

        with tempfile.TemporaryDirectory() as tmp:
            client = AnsibleVaultClient(vault_file=os.path.join(tmp, "v.yml"), password="pw")
            client.create_new_vault_file(client.vault_file, "pw")
            client.create_native_secret("a", 1)
            with self.assertRaises(ValueError):
                client.create_native_secret("a", 2)


class TestJsonImportKeepsNonBmpCharacters(unittest.TestCase):
    def test_escaped_surrogate_pairs_are_joined(self):
        from src.transfer import parse_import_text

        text = json.dumps({"secrets": [{"id": "𐀀-id", "value": "😀 ok"}]})  # ensure_ascii escapes
        self.assertIn("\\ud83d", text)
        (entry,) = parse_import_text(text)
        self.assertEqual((entry.secret_id, entry.value), ("𐀀-id", "😀 ok"))

    def test_broken_json_still_gets_the_yaml_error(self):
        from src.transfer import parse_import_text

        with self.assertRaises(ValueError):
            parse_import_text('{"a": [')
        self.assertEqual(parse_import_text("{a: 1}")[0].secret_id, "a")


class TestImportNewVersions(unittest.TestCase):
    def setUp(self):
        from src.transfer import NEW_VERSION, TransferEntry, import_entries

        self.import_entries = import_entries
        self.NEW_VERSION = NEW_VERSION
        self.TransferEntry = TransferEntry
        self.client = MagicMock()

    def test_existing_secrets_get_a_new_version_when_asked(self):
        entries = [
            self.TransferEntry("old", "fresh"),
            self.TransferEntry("old2", None),
            self.TransferEntry("new", "v"),
        ]
        result = self.import_entries(
            self.client,
            entries,
            {"old", "old2"},
            on_existing=self.NEW_VERSION,
            existing_names={"old": "projects/p/secrets/old"},
        )
        self.client.add_secret_version.assert_called_once_with("projects/p/secrets/old", "fresh")
        self.client.create_secret.assert_called_once()
        self.assertEqual(
            (result.created, result.updated, result.skipped), (["new"], ["old"], ["old2"])
        )

    def test_default_never_touches_existing_secrets(self):
        result = self.import_entries(self.client, [self.TransferEntry("old", "x")], {"old"})
        self.client.add_secret_version.assert_not_called()
        self.assertEqual((result.skipped, result.updated), (["old"], []))

    def test_failures_to_add_a_version_are_reported_per_secret(self):
        self.client.add_secret_version.side_effect = RuntimeError("denied")
        result = self.import_entries(
            self.client, [self.TransferEntry("old", "x")], {"old"}, on_existing=self.NEW_VERSION
        )
        self.client.add_secret_version.assert_called_once_with("old", "x")
        self.assertEqual(result.failed, [("old", "denied")])
