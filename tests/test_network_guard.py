from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from azure.core.exceptions import ServiceRequestError, ServiceResponseError
from botocore.exceptions import ConnectTimeoutError, EndpointConnectionError, ReadTimeoutError

from src.exceptions import ProviderOperationError
from src.i18n import set_language
from src.providers import AWSSecretClient, AzureSecretClient, SSMClient, errors


class TestGuard(unittest.TestCase):
    def setUp(self):
        set_language("en")
        self.addCleanup(set_language, "es")

    def test_only_listed_methods_are_wrapped_and_the_cause_is_kept(self):
        @errors.guard_network("x", "Service X", (TimeoutError,), "slow")
        class Thing:
            def slow(self):
                raise TimeoutError("took too long")

            def other(self):
                raise TimeoutError("untouched")

            def fine(self, value):
                return value

        thing = Thing()
        with self.assertRaises(ProviderOperationError) as ctx:
            thing.slow()
        self.assertIn("Service X did not answer in time", str(ctx.exception))
        self.assertIn("took too long", str(ctx.exception))
        self.assertIsInstance(ctx.exception.original_error, TimeoutError)
        with self.assertRaises(TimeoutError):
            thing.other()
        self.assertEqual(Thing.slow.__name__, "slow")

    def test_methods_not_defined_on_the_class_are_ignored(self):
        @errors.guard_network("x", "X", (OSError,), "missing")
        class Empty:
            pass

        self.assertFalse(hasattr(Empty, "missing"))


class TestAws(unittest.TestCase):
    def setUp(self):
        set_language("en")
        self.addCleanup(set_language, "es")

    def test_clients_get_timeouts_and_retries(self):
        client = AWSSecretClient(profile_name="default", region_name="eu-west-1")
        with patch("boto3.Session") as session:
            client._get_client()
        config = session.return_value.client.call_args.kwargs["config"]
        self.assertEqual(config.connect_timeout, errors.CONNECT_TIMEOUT)
        self.assertEqual(config.read_timeout, errors.READ_TIMEOUT)
        self.assertEqual(config.retries["max_attempts"], errors.RETRIES)

    def test_every_operation_reports_unreachable_servers(self):
        for cls, name in ((AWSSecretClient, "AWS"), (SSMClient, "Parameter Store")):
            client = cls(profile_name="p", region_name="r")
            sdk = MagicMock()
            client._client = sdk
            for failure in (
                ConnectTimeoutError(endpoint_url="https://x"),
                ReadTimeoutError(endpoint_url="https://x"),
                EndpointConnectionError(endpoint_url="https://x"),
            ):
                sdk.get_paginator.side_effect = failure
                sdk.get_secret_value.side_effect = failure
                sdk.get_parameter.side_effect = failure
                sdk.delete_secret.side_effect = failure
                sdk.delete_parameter.side_effect = failure
                with self.assertRaisesRegex(ProviderOperationError, "did not answer in time"):
                    client.list_secrets()
                with self.assertRaisesRegex(ProviderOperationError, name):
                    client.access_secret_payload("s")
                with self.assertRaises(ProviderOperationError):
                    client.delete_secret("s")


class TestAzure(unittest.TestCase):
    def setUp(self):
        set_language("en")
        self.addCleanup(set_language, "es")

    def test_secret_client_gets_timeouts(self):
        client = AzureSecretClient(vault_name="kv")
        with (
            patch("src.providers.azure.DefaultAzureCredential"),
            patch("src.providers.azure.SecretClient") as secret_client,
        ):
            client._get_client()
        kwargs = secret_client.call_args.kwargs
        self.assertEqual(kwargs["connection_timeout"], errors.CONNECT_TIMEOUT)
        self.assertEqual(kwargs["read_timeout"], errors.READ_TIMEOUT)
        self.assertEqual(kwargs["retry_total"], errors.RETRIES)

    def test_unreachable_vault_is_reported(self):
        client = AzureSecretClient(vault_name="kv")
        sdk = MagicMock()
        client._client = sdk
        for failure in (ServiceRequestError("no route"), ServiceResponseError("read timed out")):
            sdk.list_properties_of_secrets.side_effect = failure
            sdk.get_secret.side_effect = failure
            with self.assertRaisesRegex(ProviderOperationError, "Azure Key Vault did not answer"):
                client.list_secrets()
            with self.assertRaises(ProviderOperationError):
                client.access_secret_payload("s")


if __name__ == "__main__":
    unittest.main()
