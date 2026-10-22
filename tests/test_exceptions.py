from __future__ import annotations

import unittest

from src.exceptions import (
    AuthenticationError,
    ConfigurationError,
    GossipError,
    PermissionDeniedError,
    ProviderError,
    ResourceNotFoundError,
    SecretConflictError,
)


class TestExceptions(unittest.TestCase):
    def test_hierarchy(self):
        root_err = GossipError("Base error")
        self.assertIsInstance(root_err, Exception)

        orig = ValueError("Low-level network failure")
        prov_err = ProviderError("Operation failed", provider="aws", original_error=orig)
        self.assertIsInstance(prov_err, GossipError)
        self.assertEqual(prov_err.provider, "aws")
        self.assertEqual(prov_err.original_error, orig)

    def test_derived_provider_exceptions(self):
        auth_err = AuthenticationError("Auth missing", provider="gcp")
        self.assertIsInstance(auth_err, ProviderError)
        self.assertIsInstance(auth_err, GossipError)
        self.assertEqual(auth_err.provider, "gcp")

        perm_err = PermissionDeniedError("Denied", provider="azure")
        self.assertIsInstance(perm_err, ProviderError)

        not_found_err = ResourceNotFoundError("Secret not found", provider="aws")
        self.assertIsInstance(not_found_err, ProviderError)

        conflict_err = SecretConflictError("Already exists", provider="ansible")
        self.assertIsInstance(conflict_err, ProviderError)

        config_err = ConfigurationError("Vault not set", provider="ansible")
        self.assertIsInstance(config_err, ProviderError)


if __name__ == "__main__":
    unittest.main()
