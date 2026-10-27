from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

from src.i18n import set_language
from src.providers.ssm import SSMClient


def error(code: str, message: str = "boom") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": message}}, "Op")


class TestSSMClient(unittest.TestCase):
    def setUp(self):
        set_language("en")
        self.addCleanup(set_language, "es")
        self.client = SSMClient(profile_name="dev", region_name="eu-west-1")
        self.ssm = MagicMock()
        self.client._client = self.ssm

    def test_properties(self):
        c = self.client
        self.assertEqual((c.provider_id, c.provider), ("ssm", "ssm"))
        self.assertIn("Parameter Store", c.display_name)
        self.assertIn("eu-west-1", c.context_subtitle)
        for text in (c.context_btn_tooltip, c.loading_message, c.empty_message):
            self.assertTrue(text)
        self.assertEqual(c._service_name, "ssm")
        self.assertFalse(c.supports_version_toggling)

    def test_list_secrets(self):
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "Parameters": [
                    {"Name": "/b", "Type": "String"},
                    {
                        "Name": "/A",
                        "Type": "SecureString",
                        "Tier": "Standard",
                        "Description": "d",
                        "KeyId": "alias/x",
                        "LastModifiedDate": datetime(2026, 1, 1),
                    },
                ]
            }
        ]
        self.ssm.get_paginator.return_value = paginator
        items = self.client.list_secrets()
        self.assertEqual([i.secret_id for i in items], ["/A", "/b"])
        self.assertEqual(items[0].labels, {"type": "SecureString", "tier": "Standard"})
        self.assertEqual((items[0].provider, items[0].kms_key_id), ("ssm", "alias/x"))

    def test_list_versions(self):
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Parameters": [{"Version": 1, "Labels": ["prod"]}, {"Version": 2}]}
        ]
        self.ssm.get_paginator.return_value = paginator
        versions = self.client.list_versions("/a@1")
        self.assertEqual([v.version_id for v in versions], ["2", "1"])
        self.assertEqual(versions[0].stages, ["AWSCURRENT"])
        self.assertEqual(versions[1].stages, ["prod"])
        self.assertEqual(versions[0].name, "/a@2")
        self.assertEqual(paginator.paginate.call_args.kwargs["Name"], "/a")
        paginator.paginate.return_value = [{"Parameters": []}]
        self.assertEqual(self.client.list_versions("/a"), [])

    def test_access_payload(self):
        self.ssm.get_parameter.return_value = {"Parameter": {"Value": "s3"}}
        self.assertEqual(self.client.access_secret_payload("/a"), ("s3", False))
        self.ssm.get_parameter.assert_called_with(Name="/a", WithDecryption=True)
        self.client.access_secret_payload("/a@4")
        self.ssm.get_parameter.assert_called_with(Name="/a:4", WithDecryption=True)

    def test_create_secret(self):
        item = self.client.create_secret("/n", "v", labels={"env": "p"}, description="desc")
        params = self.ssm.put_parameter.call_args.kwargs
        self.assertEqual(params["Type"], "SecureString")
        self.assertFalse(params["Overwrite"])
        self.assertEqual(params["Tags"], [{"Key": "env", "Value": "p"}])
        self.assertEqual(params["Description"], "desc")
        self.assertEqual((item.provider, item.labels["env"]), ("ssm", "p"))
        self.client.create_secret("/m", "v")
        self.assertNotIn("Tags", self.ssm.put_parameter.call_args.kwargs)

    def test_create_conflict(self):
        self.ssm.put_parameter.side_effect = error("ParameterAlreadyExists")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.client.create_secret("/n", "v")

    def test_add_version_keeps_type(self):
        self.ssm.get_parameter.return_value = {"Parameter": {"Type": "String"}}
        self.ssm.put_parameter.return_value = {"Version": 7}
        version = self.client.add_secret_version("/n@2", "x")
        self.assertEqual((version.version_id, version.name), ("7", "/n@7"))
        self.assertEqual(self.ssm.put_parameter.call_args.kwargs["Type"], "String")
        self.assertTrue(self.ssm.put_parameter.call_args.kwargs["Overwrite"])

    def test_delete(self):
        self.client.delete_secret("/n@1")
        self.ssm.delete_parameter.assert_called_once_with(Name="/n")

    def test_errors_are_translated(self):
        self.ssm.get_parameter.side_effect = error("AccessDeniedException")
        with self.assertRaises(PermissionError):
            self.client.access_secret_payload("/a")
        self.ssm.get_parameter.side_effect = error("ParameterNotFound")
        with self.assertRaises(FileNotFoundError):
            self.client.access_secret_payload("/a")
        self.ssm.get_parameter.side_effect = error("Throttling", "slow down")
        with self.assertRaisesRegex(RuntimeError, "slow down"):
            self.client.access_secret_payload("/a")
        self.ssm.get_paginator.side_effect = error("AccessDeniedException")
        with self.assertRaises(PermissionError):
            self.client.list_secrets()
        with self.assertRaises(PermissionError):
            self.client.list_versions("/a")
        self.ssm.delete_parameter.side_effect = error("ParameterNotFound")
        with self.assertRaises(FileNotFoundError):
            self.client.delete_secret("/a")
        self.ssm.get_parameter.side_effect = error("ParameterNotFound")
        with self.assertRaises(FileNotFoundError):
            self.client.add_secret_version("/a", "x")
        self.ssm.put_parameter.side_effect = error("Throttling")
        with self.assertRaises(RuntimeError):
            self.client.create_secret("/a", "x")


if __name__ == "__main__":
    unittest.main()
