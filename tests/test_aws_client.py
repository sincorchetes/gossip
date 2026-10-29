from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from src.providers.aws import AWSSecretClient


class TestAWSSecretClient(unittest.TestCase):
    def setUp(self):
        self.client = AWSSecretClient(profile_name="test-profile", region_name="eu-west-1")
        self.mock_sm_client = MagicMock()
        self.client._client = self.mock_sm_client

    def test_provider_properties(self):
        self.assertEqual(self.client.provider_id, "aws")
        self.assertEqual(self.client.display_name, "Amazon Web Services (AWS)")
        self.assertFalse(self.client.supports_version_toggling)
        self.assertFalse(self.client.supports_version_destroy)
        self.assertIn("test-profile", self.client.context_subtitle)
        self.assertIn("eu-west-1", self.client.context_subtitle)

    @patch.dict("os.environ", {"AWS_DEFAULT_REGION": "us-west-2", "AWS_PROFILE": "dev-profile"})
    def test_profile_and_region_detection_from_env(self):
        c = AWSSecretClient()
        self.assertEqual(c.region_name, "us-west-2")
        self.assertEqual(c.profile_name, "dev-profile")

    def test_list_secrets(self):
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "SecretList": [
                    {
                        "ARN": "arn:aws:secretsmanager:eu-west-1:123456789:secret:prod/app/db",
                        "Name": "prod/app/db",
                        "Description": "Production Database Credentials",
                        "CreatedDate": datetime(2026, 1, 1),
                        "LastChangedDate": datetime(2026, 1, 2),
                        "Tags": [{"Key": "Environment", "Value": "Production"}],
                        "ReplicationStatus": [{"Region": "us-east-1"}],
                        "KmsKeyId": "arn:aws:kms:eu-west-1:123456789:key/xxx",
                    }
                ]
            }
        ]
        self.mock_sm_client.get_paginator.return_value = paginator

        secrets = self.client.list_secrets()
        self.assertEqual(len(secrets), 1)
        self.assertEqual(secrets[0].secret_id, "prod/app/db")
        self.assertEqual(secrets[0].labels, {"Environment": "Production"})
        self.assertEqual(secrets[0].replication_type, "REPLICATED")
        self.assertEqual(secrets[0].locations, ["us-east-1"])

    def test_list_versions(self):
        self.mock_sm_client.list_secret_version_ids.return_value = {
            "Versions": [
                {
                    "VersionId": "v1-uuid",
                    "VersionStages": ["AWSCURRENT"],
                    "CreatedDate": datetime(2026, 1, 2),
                },
                {
                    "VersionId": "v0-uuid",
                    "VersionStages": ["AWSPREVIOUS"],
                    "CreatedDate": datetime(2026, 1, 1),
                },
            ]
        }

        versions = self.client.list_versions("prod/app/db")
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0].version_id, "v1-uuid")
        self.assertIn("AWSCURRENT", versions[0].stages)
        self.assertEqual(versions[1].version_id, "v0-uuid")
        self.assertIn("AWSPREVIOUS", versions[1].stages)

    def test_access_secret_payload_string(self):
        self.mock_sm_client.get_secret_value.return_value = {
            "SecretString": "my-aws-secret-string",
            "VersionId": "v1",
        }

        val, is_bin = self.client.access_secret_payload("prod/app/db")
        self.assertEqual(val, "my-aws-secret-string")
        self.assertFalse(is_bin)

    def test_access_secret_payload_binary(self):
        self.mock_sm_client.get_secret_value.return_value = {
            "SecretBinary": b"\x00\x01\x02\x03\x04",
            "VersionId": "v1",
        }

        val, is_bin = self.client.access_secret_payload("prod/app/db")
        self.assertTrue(is_bin)
        self.assertEqual(val, "base64:AAECAwQ=")

    def test_binary_secret_round_trips_through_an_edit(self):
        self.mock_sm_client.get_secret_value.return_value = {"SecretBinary": b"\x00\xff"}
        self.mock_sm_client.put_secret_value.return_value = {"VersionId": "v2"}
        self.client.add_secret_version("bin", "base64:AP8=")
        self.mock_sm_client.put_secret_value.assert_called_once_with(
            SecretId="bin", SecretBinary=b"\x00\xff"
        )
        with self.assertRaisesRegex(ValueError, "base64"):
            self.client.add_secret_version("bin", "base64:***")

    def test_text_secret_starting_with_the_prefix_stays_text(self):
        self.mock_sm_client.get_secret_value.return_value = {"SecretString": "base64:abc"}
        self.mock_sm_client.put_secret_value.return_value = {"VersionId": "v2"}
        self.client.add_secret_version("txt", "base64:xyz")
        self.mock_sm_client.put_secret_value.assert_called_once_with(
            SecretId="txt", SecretString="base64:xyz"
        )

    def test_create_secret(self):
        self.mock_sm_client.create_secret.return_value = {
            "ARN": "arn:aws:secretsmanager:eu-west-1:123456789:secret:new-sec",
            "Name": "new-sec",
        }

        sec = self.client.create_secret(
            secret_id="new-sec",
            payload_data="sec-value",
            description="New secret",
            labels={"tag1": "val1"},
        )
        self.assertEqual(sec.secret_id, "new-sec")
        self.mock_sm_client.create_secret.assert_called_once_with(
            Name="new-sec",
            Description="New secret",
            SecretString="sec-value",
            Tags=[{"Key": "tag1", "Value": "val1"}],
        )

    def test_add_secret_version(self):
        self.mock_sm_client.put_secret_value.return_value = {
            "VersionId": "new-version-uuid",
            "VersionStages": ["AWSCURRENT"],
        }

        v = self.client.add_secret_version("my-sec", "new-payload")
        self.assertEqual(v.version_id, "new-version-uuid")
        self.assertEqual(v.state, "AWSCURRENT")

    def test_delete_secret(self):
        self.client.delete_secret("my-sec", force=True)
        self.mock_sm_client.delete_secret.assert_called_once_with(
            SecretId="my-sec",
            ForceDeleteWithoutRecovery=True,
        )

    def test_toggle_and_destroy_not_supported(self):
        with self.assertRaises(NotImplementedError):
            self.client.toggle_version_state("v1", enable=False)
        with self.assertRaises(NotImplementedError):
            self.client.destroy_version("v1")

    def test_access_denied_exception_handling(self):
        self.mock_sm_client.get_secret_value.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Not authorized"}},
            "GetSecretValue",
        )
        with self.assertRaises(PermissionError):
            self.client.access_secret_payload("restricted-sec")

    def test_additional_properties_and_setters(self):
        self.assertEqual(self.client.provider, "aws")
        self.assertEqual(self.client.icon_name, "preferences-system-symbolic")
        self.assertIn("AWS", self.client.context_title)
        self.assertIn("AWS", self.client.context_btn_tooltip)
        self.assertIn("AWS", self.client.loading_message)
        self.assertIn("AWS", self.client.empty_message)
        self.assertIn("AWS", self.client.error_message)

        # Setters
        self.client.profile_name = "new-profile"
        self.assertEqual(self.client.profile_name, "new-profile")
        self.client.region_name = "us-west-2"
        self.assertEqual(self.client.region_name, "us-west-2")

        # set_context
        self.client.set_context("staging", "eu-central-1")
        self.assertEqual(self.client.profile_name, "staging")
        self.assertEqual(self.client.region_name, "eu-central-1")

    def test_open_context_dialog(self):
        parent = MagicMock()
        on_success = MagicMock()
        with patch("src.ui.dialogs.show_change_aws_context_dialog") as mock_dialog:
            self.client.open_context_dialog(parent, on_success)
            mock_dialog.assert_called_once()
            on_confirm_cb = mock_dialog.call_args[0][2]
            on_confirm_cb("prod-profile", "eu-west-3")
            self.assertEqual(self.client.profile_name, "prod-profile")
            self.assertEqual(self.client.region_name, "eu-west-3")
            on_success.assert_called_once()

    def test_list_available_profiles_and_regions(self):
        profiles = AWSSecretClient.list_available_profiles()
        self.assertIsInstance(profiles, list)
        self.assertTrue(len(profiles) >= 1)

        regions = AWSSecretClient.list_available_regions()
        self.assertIsInstance(regions, list)
        self.assertIn("us-east-1", regions)

    @patch("boto3.Session")
    def test_get_client_profile_not_found(self, mock_sess_cls):
        from botocore.exceptions import ProfileNotFound

        mock_sess_cls.side_effect = ProfileNotFound(profile="missing-prof")
        c = AWSSecretClient(profile_name="missing-prof")
        with self.assertRaises(RuntimeError):
            c._get_client()

    @patch("boto3.Session")
    def test_get_client_no_credentials_error(self, mock_sess_cls):
        from botocore.exceptions import NoCredentialsError

        mock_sess_cls.side_effect = NoCredentialsError()
        c = AWSSecretClient(profile_name="no-creds")
        with self.assertRaises(RuntimeError):
            c._get_client()

    def test_create_secret_with_kms_key(self):
        self.mock_sm_client.create_secret.return_value = {
            "ARN": "arn:aws:secretsmanager:eu-west-1:123:secret:kms-sec",
            "Name": "kms-sec",
        }
        sec = self.client.create_secret(
            secret_id="kms-sec",
            payload_data="data",
            kms_key_id="arn:aws:kms:eu-west-1:123:key/abc",
        )
        self.assertEqual(sec.secret_id, "kms-sec")
        self.mock_sm_client.create_secret.assert_called_with(
            Name="kms-sec",
            SecretString="data",
            KmsKeyId="arn:aws:kms:eu-west-1:123:key/abc",
        )

    def test_delete_secret_with_recovery_window(self):
        self.client.delete_secret("soft-delete-sec", force=False, recovery_days=14)
        self.mock_sm_client.delete_secret.assert_called_with(
            SecretId="soft-delete-sec",
            RecoveryWindowInDays=14,
        )

    def test_access_secret_payload_variants(self):
        # Format with @version
        self.mock_sm_client.get_secret_value.return_value = {"SecretString": "v123-val"}
        val, _ = self.client.access_secret_payload("my-secret@v123")
        self.assertEqual(val, "v123-val")
        self.mock_sm_client.get_secret_value.assert_called_with(
            SecretId="my-secret", VersionId="v123"
        )

        # Format with version_stage
        self.client.access_secret_payload("my-secret", version_stage="AWSPREVIOUS")
        self.mock_sm_client.get_secret_value.assert_called_with(
            SecretId="my-secret", VersionStage="AWSPREVIOUS"
        )

        # Empty secret
        self.mock_sm_client.get_secret_value.return_value = {}
        val, is_bin = self.client.access_secret_payload("empty-secret")
        self.assertEqual(val, "")
        self.assertFalse(is_bin)

    def test_access_secret_resource_not_found(self):
        self.mock_sm_client.get_secret_value.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            "GetSecretValue",
        )
        with self.assertRaises(FileNotFoundError):
            self.client.access_secret_payload("missing-secret")

    def test_client_operations_error_handling(self):
        # Create secret error
        self.mock_sm_client.create_secret.side_effect = ClientError(
            {"Error": {"Code": "InternalServiceError", "Message": "Internal AWS error"}},
            "CreateSecret",
        )
        with self.assertRaises(RuntimeError):
            self.client.create_secret("err-sec", "payload")

        # Add version error
        self.mock_sm_client.put_secret_value.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Not allowed"}},
            "PutSecretValue",
        )
        with self.assertRaises(PermissionError):
            self.client.add_secret_version("err-sec", "new-payload")

        # Delete secret error
        self.mock_sm_client.delete_secret.side_effect = ClientError(
            {"Error": {"Code": "InvalidRequestException", "Message": "Bad request"}},
            "DeleteSecret",
        )
        with self.assertRaises(RuntimeError):
            self.client.delete_secret("err-sec")

    @patch("boto3.Session")
    def test_get_client_default_profile(self, mock_sess_cls):
        mock_sess = MagicMock()
        mock_sess_cls.return_value = mock_sess
        c = AWSSecretClient(profile_name="default", region_name="us-east-1")
        c._get_client()
        mock_sess_cls.assert_called_with(region_name="us-east-1")

    def test_list_versions_pagination(self):
        resp1 = {
            "Versions": [
                {"VersionId": "v1", "VersionStages": ["AWSCURRENT"], "CreatedDate": datetime.now()}
            ],
            "NextToken": "page-2",
        }
        resp2 = {
            "Versions": [
                {"VersionId": "v2", "VersionStages": ["AWSPREVIOUS"], "CreatedDate": datetime.now()}
            ],
        }
        self.mock_sm_client.list_secret_version_ids.side_effect = [resp1, resp2]
        versions = self.client.list_versions("paginated-sec")
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0].version_id, "v1")
        self.assertEqual(versions[1].version_id, "v2")

    def test_errors_across_aws_methods(self):
        access_denied = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Not authorized"}},
            "Op",
        )
        generic_err = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Server error"}},
            "Op",
        )

        # list_secrets errors
        self.mock_sm_client.get_paginator.return_value.paginate.side_effect = access_denied
        with self.assertRaises(PermissionError):
            self.client.list_secrets()

        self.mock_sm_client.get_paginator.return_value.paginate.side_effect = generic_err
        with self.assertRaises(RuntimeError):
            self.client.list_secrets()

        # list_versions errors
        self.mock_sm_client.list_secret_version_ids.side_effect = access_denied
        with self.assertRaises(PermissionError):
            self.client.list_versions("sec")

        self.mock_sm_client.list_secret_version_ids.side_effect = generic_err
        with self.assertRaises(RuntimeError):
            self.client.list_versions("sec")

        # access_secret_payload errors
        self.mock_sm_client.get_secret_value.side_effect = access_denied
        with self.assertRaises(PermissionError):
            self.client.access_secret_payload("sec")

        self.mock_sm_client.get_secret_value.side_effect = generic_err
        with self.assertRaises(RuntimeError):
            self.client.access_secret_payload("sec")

        # create_secret access denied
        self.mock_sm_client.create_secret.side_effect = access_denied
        with self.assertRaises(PermissionError):
            self.client.create_secret("sec", "val")

        # add_secret_version generic error
        self.mock_sm_client.put_secret_value.side_effect = generic_err
        with self.assertRaises(RuntimeError):
            self.client.add_secret_version("sec", "val")

        # delete_secret access denied
        self.mock_sm_client.delete_secret.side_effect = access_denied
        with self.assertRaises(PermissionError):
            self.client.delete_secret("sec")

    def test_aws_client_100_percent_coverage(self):
        from botocore.exceptions import NoCredentialsError

        # 1. profile_name detection when _profile_name is None
        c = AWSSecretClient(profile_name="initial")
        c._profile_name = None
        with patch.object(AWSSecretClient, "detect_profile", return_value="detected-profile"):
            self.assertEqual(c.profile_name, "detected-profile")

        # 2. profile_name setter with same value (112->exit)
        c.profile_name = "detected-profile"
        self.assertEqual(c.profile_name, "detected-profile")

        # 3. region_name detection when _region_name is None
        c._region_name = None
        with patch.object(AWSSecretClient, "detect_region", return_value="us-detected-1"):
            self.assertEqual(c.region_name, "us-detected-1")

        # 4. region_name setter with same value (126->exit)
        c.region_name = "us-detected-1"
        self.assertEqual(c.region_name, "us-detected-1")

        # 5. detect_profile with default, non-default, and empty available profiles (146-150)
        with patch.dict("os.environ", {}, clear=True):
            with patch.object(
                AWSSecretClient, "list_available_profiles", return_value=["default", "staging"]
            ):
                self.assertEqual(AWSSecretClient.detect_profile(), "default")
            with patch.object(
                AWSSecretClient, "list_available_profiles", return_value=["staging", "prod"]
            ):
                self.assertEqual(AWSSecretClient.detect_profile(), "staging")
            with patch.object(AWSSecretClient, "list_available_profiles", return_value=[]):
                self.assertEqual(AWSSecretClient.detect_profile(), "default")

        # 6. detect_region when boto3 session region is None vs valid
        with patch.dict("os.environ", {}, clear=True):
            with patch("boto3.Session") as mock_sess:
                mock_sess.return_value.region_name = None
                self.assertEqual(AWSSecretClient.detect_region(), "us-east-1")
                mock_sess.return_value.region_name = "eu-west-1"
                self.assertEqual(AWSSecretClient.detect_region(), "eu-west-1")

        # 7. list_available_profiles when profiles is empty vs non-empty
        with patch("botocore.session.Session") as mock_bsess:
            mock_bsess.return_value.available_profiles = []
            self.assertEqual(AWSSecretClient.list_available_profiles(), ["default"])
            mock_bsess.return_value.available_profiles = ["dev", "prod"]
            self.assertEqual(AWSSecretClient.list_available_profiles(), ["dev", "prod"])

        # 8. list_available_profiles when exception is raised (177-178)
        with patch("botocore.session.Session", side_effect=Exception("Crash")):
            self.assertEqual(AWSSecretClient.list_available_profiles(), ["default"])

        # 9. list_available_regions when empty or exception (186->190, 188-190)
        with patch("boto3.Session") as mock_sess:
            mock_sess.return_value.get_available_regions.return_value = []
            regions = AWSSecretClient.list_available_regions()
            self.assertIn("us-east-1", regions)

        with patch("boto3.Session", side_effect=Exception("Crash")):
            regions = AWSSecretClient.list_available_regions()
            self.assertIn("us-east-1", regions)

        # 10. _get_client generic exception (219-220)
        c2 = AWSSecretClient(profile_name="broken")
        c2._client = None
        with patch("boto3.Session", side_effect=TypeError("Unexpected error")):
            with self.assertRaises(RuntimeError):
                c2._get_client()

        # 11. list_secrets with tag missing 'Key' (242->239)
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "SecretList": [
                    {
                        "Name": "tag-test",
                        "Tags": [{"Value": "val-without-key"}, {"Key": "k", "Value": "v"}],
                    }
                ]
            }
        ]
        self.mock_sm_client.get_paginator.return_value = paginator
        secrets = self.client.list_secrets()
        self.assertEqual(secrets[0].labels, {"k": "v"})

        # 12. list_secrets NoCredentialsError (269)
        self.mock_sm_client.get_paginator.return_value.paginate.side_effect = NoCredentialsError()
        with self.assertRaises(RuntimeError):
            self.client.list_secrets()

        # 13. access_secret_payload with @ and explicit version_id (354->357)
        self.mock_sm_client.get_secret_value.side_effect = None
        self.mock_sm_client.get_secret_value.return_value = {"SecretString": "val"}
        val, _ = self.client.access_secret_payload("mysec@v1", version_id="explicit_v2")
        self.mock_sm_client.get_secret_value.assert_called_with(
            SecretId="mysec", VersionId="explicit_v2"
        )

        # 14. create_secret with payload_data=None (401->403)
        self.mock_sm_client.create_secret.side_effect = None
        self.mock_sm_client.create_secret.return_value = {"ARN": "arn:sec"}
        item = self.client.create_secret("sec-nopayload", payload_data=None)
        self.assertEqual(item.secret_id, "sec-nopayload")


if __name__ == "__main__":
    unittest.main()


class TestAwsCreateConflict(unittest.TestCase):
    def test_existing_secret_is_a_conflict(self):
        from src.exceptions import SecretConflictError

        client = AWSSecretClient(profile_name="p", region_name="eu-west-1")
        client._client = MagicMock()
        client._client.create_secret.side_effect = ClientError(
            {"Error": {"Code": "ResourceExistsException", "Message": "exists"}}, "CreateSecret"
        )
        with self.assertRaises(SecretConflictError):
            client.create_secret("dup", "x")


class TestAWSUpdateMetadataError(unittest.TestCase):
    def test_client_error_is_translated(self):
        from src.exceptions import PermissionDeniedError

        client = AWSSecretClient(profile_name="p", region_name="eu-west-1")
        client._client = MagicMock()
        client._client.describe_secret.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "no"}}, "DescribeSecret"
        )
        with self.assertRaises(PermissionDeniedError):
            client.update_metadata("sec", {"a": "b"}, None)

    def test_removed_tags_without_changed_tags(self):
        client = AWSSecretClient(profile_name="p", region_name="eu-west-1")
        client._client = MagicMock()
        client._client.describe_secret.return_value = {"Tags": [{"Key": "old", "Value": "1"}]}
        client.update_metadata("sec", {}, None)
        client._client.untag_resource.assert_called_once()
        client._client.tag_resource.assert_not_called()

    def test_changed_tags_without_removed_tags(self):
        client = AWSSecretClient(profile_name="p", region_name="eu-west-1")
        client._client = MagicMock()
        client._client.describe_secret.return_value = {"Tags": []}
        client.update_metadata("sec", {"a": "b"}, None)
        client._client.tag_resource.assert_called_once()
        client._client.untag_resource.assert_not_called()
