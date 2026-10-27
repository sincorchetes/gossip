"""Every provider must behave the same way for the operations the interface relies on.

The same scenarios run against an in-memory stand-in of each backend, going through the
calls the window and the exporter make (list, list_versions, access_secret_payload with
the version name, create, add version, delete).
"""

from __future__ import annotations

import unittest

from src.exceptions import (
    PermissionDeniedError,
    ResourceNotFoundError,
    SecretConflictError,
)
from src.i18n import set_language
from tests.contract_fakes import HARNESSES

NAME = "contract-secret"
TEXT = "pässwörd ñ ✓ with spaces"


class ProviderContract:
    """Scenarios shared by every provider; subclasses bind a harness."""

    harness_class: type

    def setUp(self):
        set_language("en")
        self.addCleanup(set_language, "es")
        self.harness = self.harness_class()
        self.addCleanup(self.harness.cleanup)
        self.provider = self.harness.make()

    def read(self, name: str = NAME) -> str:
        """Read the current value the way the interface and the exporter do."""
        secret = next(s for s in self.provider.list_secrets() if s.secret_id == name)
        versions = self.provider.list_versions(secret.name)
        return self.provider.access_secret_payload(versions[0].name)[0]

    def test_a_created_secret_is_listed_and_readable(self):
        self.provider.create_secret(NAME, TEXT)
        self.assertIn(NAME, [s.secret_id for s in self.provider.list_secrets()])
        self.assertEqual(self.read(), TEXT)

    def test_creating_twice_is_a_conflict_and_keeps_the_original(self):
        self.provider.create_secret(NAME, "first")
        with self.assertRaises(SecretConflictError):
            self.provider.create_secret(NAME, "second")
        self.assertEqual(self.read(), "first")

    def test_a_new_version_becomes_the_current_value(self):
        self.provider.create_secret(NAME, "one")
        self.provider.add_secret_version(NAME, "two")
        self.assertEqual(self.read(), "two")

    def test_deleting_removes_the_secret(self):
        self.provider.create_secret(NAME, "bye")
        secret = next(s for s in self.provider.list_secrets() if s.secret_id == NAME)
        self.provider.delete_secret(secret.name)
        self.assertNotIn(NAME, [s.secret_id for s in self.provider.list_secrets()])

    def test_reading_a_missing_secret_is_not_found(self):
        with self.assertRaises(ResourceNotFoundError):
            self.provider.access_secret_payload("does-not-exist")

    def test_listing_without_permission_is_a_domain_permission_error(self):
        if not self.harness.supports_denial:
            self.skipTest("this backend has no permission model")
        self.harness.deny()
        with self.assertRaises(PermissionDeniedError):
            self.provider.list_secrets()
        with self.assertRaises(PermissionDeniedError):
            self.provider.access_secret_payload(NAME)

    def test_labels_can_be_edited_where_the_provider_supports_it(self):
        if not self.provider.supports_metadata_edit:
            self.skipTest("this provider cannot edit metadata")
        self.provider.create_secret(NAME, "x", labels={"env": "dev", "old": "1"})
        secret = next(s for s in self.provider.list_secrets() if s.secret_id == NAME)
        labels, _description = self.provider.load_metadata(secret)
        self.assertEqual(labels, {"env": "dev", "old": "1"})

        description = "edited" if self.provider.supports_description_edit else None
        self.provider.update_metadata(secret.name, {"env": "prod", "team": "core"}, description)

        secret = next(s for s in self.provider.list_secrets() if s.secret_id == NAME)
        labels, shown = self.provider.load_metadata(secret)
        self.assertEqual(labels, {"env": "prod", "team": "core"})
        if description:
            self.assertEqual(shown, description)
        self.assertEqual(self.read(), "x")  # editing metadata never touches the value

    def test_the_provider_describes_itself(self):
        provider = self.provider
        self.assertEqual(provider.provider_id, self.harness.provider_id)
        for text in (
            provider.display_name,
            provider.context_subtitle,
            provider.context_btn_tooltip,
            provider.loading_message,
            provider.empty_message,
            provider.error_message,
            provider.icon_name,
        ):
            self.assertTrue(text)
        self.assertEqual(provider.saved_context.__self__, provider)
        self.assertIsInstance(provider.saved_context(), dict)
        provider.lock()


def _bind(harness_class: type) -> type:
    return type(
        f"Test{harness_class.__name__.removesuffix('Harness')}Contract",
        (ProviderContract, unittest.TestCase),
        {"harness_class": harness_class},
    )


for _harness in HARNESSES:
    _cls = _bind(_harness)
    globals()[_cls.__name__] = _cls
del _harness, _cls


if __name__ == "__main__":
    unittest.main()
