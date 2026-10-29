from __future__ import annotations

import os
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import google.auth.exceptions
from google.api_core.exceptions import NotFound, PermissionDenied
from google.cloud import secretmanager_v1

from src.exceptions import PermissionDeniedError, ResourceNotFoundError
from src.models import SecretItem, SecretVersionItem
from src.providers.gcp import GCPSecretClient


class TestGCPSecretClient(unittest.TestCase):
    def setUp(self):
        self.client = GCPSecretClient(project_id="test-project")
        self.mock_sm_client = MagicMock()
        self.client._client = self.mock_sm_client

    def test_provider_properties(self):
        self.assertEqual(self.client.provider_id, "gcp")
        self.assertEqual(self.client.display_name, "Google Cloud (GCP)")
        self.assertTrue(self.client.supports_version_toggling)
        self.assertTrue(self.client.supports_version_destroy)
        self.assertIn("test-project", self.client.context_subtitle)

    @patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT": "env-project"})
    def test_project_id_from_env(self):
        c = GCPSecretClient()
        self.assertEqual(c.project_id, "env-project")

    def test_list_secrets(self):
        mock_secret = MagicMock()
        mock_secret.name = "projects/test-project/secrets/my-secret"
        mock_secret.replication.automatic = True
        mock_secret.replication.user_managed = None
        mock_secret.labels = {"env": "prod"}
        mock_secret.create_time = datetime(2026, 1, 1, 12, 0, 0)

        self.mock_sm_client.list_secrets.return_value = [mock_secret]

        secrets = self.client.list_secrets()
        self.assertEqual(len(secrets), 1)
        self.assertIsInstance(secrets[0], SecretItem)
        self.assertEqual(secrets[0].secret_id, "my-secret")
        self.assertEqual(secrets[0].labels, {"env": "prod"})
        self.assertEqual(secrets[0].replication_type, "AUTOMATIC")

    def test_list_secrets_user_managed_replication(self):
        mock_secret = MagicMock()
        mock_secret.name = "projects/test-project/secrets/rep-sec"
        mock_secret.replication.automatic = False
        replica = MagicMock()
        replica.location = "europe-west1"
        mock_secret.replication.user_managed.replicas = [replica]
        mock_secret.labels = {}
        mock_secret.create_time = None

        self.mock_sm_client.list_secrets.return_value = [mock_secret]
        secrets = self.client.list_secrets()
        self.assertEqual(secrets[0].replication_type, "USER_MANAGED")
        self.assertEqual(secrets[0].locations, ["europe-west1"])

    def test_list_secrets_no_project_raises_value_error(self):
        self.client._project_id = None
        with patch.object(self.client, "detect_project_id", return_value=None):
            with self.assertRaises(ValueError):
                self.client.list_secrets(project_id="")

    def test_create_secret_no_project_raises_value_error(self):
        self.client._project_id = None
        with patch.object(self.client, "detect_project_id", return_value=None):
            with self.assertRaises(ValueError):
                self.client.create_secret(secret_id="s", payload_data="p", project_id="")

    def test_list_versions(self):
        mock_v1 = MagicMock()
        mock_v1.name = "projects/test-project/secrets/my-secret/versions/1"
        mock_v1.state = secretmanager_v1.SecretVersion.State.ENABLED
        mock_v1.create_time = datetime(2026, 1, 1, 12, 0, 0)
        mock_v1.destroy_time = None

        mock_v2 = MagicMock()
        mock_v2.name = "projects/test-project/secrets/my-secret/versions/2"
        mock_v2.state = secretmanager_v1.SecretVersion.State.DISABLED
        mock_v2.create_time = datetime(2026, 1, 2, 12, 0, 0)
        mock_v2.destroy_time = None

        self.mock_sm_client.list_secret_versions.return_value = [mock_v2, mock_v1]

        versions = self.client.list_versions("projects/test-project/secrets/my-secret")
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0].version_id, "2")
        self.assertEqual(versions[0].state, "DISABLED")
        self.assertEqual(versions[1].version_id, "1")
        self.assertEqual(versions[1].state, "ENABLED")

    def test_access_secret_payload_utf8(self):
        mock_response = MagicMock()
        mock_response.payload.data = b"super-secret-password-123"
        self.mock_sm_client.access_secret_version.return_value = mock_response

        payload, is_binary = self.client.access_secret_payload(
            "projects/test-project/secrets/s/versions/1"
        )
        self.assertEqual(payload, "super-secret-password-123")
        self.assertFalse(is_binary)

    def test_access_secret_payload_binary(self):
        mock_response = MagicMock()
        # Invalid UTF-8 bytes
        mock_response.payload.data = b"\x80\x81\x82\x83\xff"
        self.mock_sm_client.access_secret_version.return_value = mock_response

        payload, is_binary = self.client.access_secret_payload(
            "projects/test-project/secrets/s/versions/1"
        )
        self.assertTrue(is_binary)
        self.assertIn("Datos binarios", payload)

    def test_create_secret_and_version(self):
        mock_created = MagicMock()
        mock_created.name = "projects/test-project/secrets/new-sec"
        mock_created.labels = {"app": "gossip"}
        mock_created.replication.automatic = True
        mock_created.replication.user_managed = None
        mock_created.create_time = datetime.now()

        self.mock_sm_client.create_secret.return_value = mock_created

        mock_version = MagicMock()
        mock_version.name = "projects/test-project/secrets/new-sec/versions/1"
        mock_version.state = secretmanager_v1.SecretVersion.State.ENABLED.value
        mock_version.create_time = None
        mock_version.destroy_time = None
        self.mock_sm_client.add_secret_version.return_value = mock_version

        secret = self.client.create_secret(
            secret_id="new-sec",
            payload_data="initial-val",
            labels={"app": "gossip"},
        )
        self.assertEqual(secret.secret_id, "new-sec")
        self.mock_sm_client.create_secret.assert_called_once()
        self.mock_sm_client.add_secret_version.assert_called_once()

    def test_toggle_version_state(self):
        mock_version = MagicMock()
        mock_version.name = "projects/test-project/secrets/s/versions/1"
        mock_version.state = secretmanager_v1.SecretVersion.State.DISABLED.value
        mock_version.create_time = None
        mock_version.destroy_time = None
        self.mock_sm_client.disable_secret_version.return_value = mock_version

        mock_version_enabled = MagicMock()
        mock_version_enabled.name = "projects/test-project/secrets/s/versions/1"
        mock_version_enabled.state = secretmanager_v1.SecretVersion.State.ENABLED.value
        mock_version_enabled.create_time = None
        mock_version_enabled.destroy_time = None
        self.mock_sm_client.enable_secret_version.return_value = mock_version_enabled

        v_item = SecretVersionItem(
            version_id="1",
            name="projects/test-project/secrets/s/versions/1",
            state="ENABLED",
        )
        self.client.toggle_version_state(v_item, enable=False)
        self.mock_sm_client.disable_secret_version.assert_called_with(
            request={"name": "projects/test-project/secrets/s/versions/1"}
        )

        self.client.toggle_version_state("projects/test-project/secrets/s/versions/1", enable=True)
        self.mock_sm_client.enable_secret_version.assert_called_with(
            request={"name": "projects/test-project/secrets/s/versions/1"}
        )

    def test_destroy_version(self):
        mock_version = MagicMock()
        mock_version.name = "projects/test-project/secrets/s/versions/1"
        mock_version.state = secretmanager_v1.SecretVersion.State.DESTROYED.value
        mock_version.create_time = None
        mock_version.destroy_time = None
        self.mock_sm_client.destroy_secret_version.return_value = mock_version

        self.client.destroy_version("projects/test-project/secrets/s/versions/1")
        self.mock_sm_client.destroy_secret_version.assert_called_with(
            request={"name": "projects/test-project/secrets/s/versions/1"}
        )

    def test_delete_secret(self):
        self.client.delete_secret("projects/test-project/secrets/my-secret")
        self.mock_sm_client.delete_secret.assert_called_with(
            request={"name": "projects/test-project/secrets/my-secret"}
        )

    def test_not_found_error_mapped(self):
        self.mock_sm_client.access_secret_version.side_effect = NotFound("Secret not found")
        with self.assertRaises(ResourceNotFoundError):
            self.client.access_secret_payload("projects/test-project/secrets/invalid/versions/1")

    def test_permission_denied_mapped(self):
        self.mock_sm_client.list_secrets.side_effect = PermissionDenied("Access denied")
        with self.assertRaises(PermissionDeniedError):
            self.client.list_secrets()

    def test_property_getters_and_context_dialog(self):
        self.assertEqual(self.client.provider, "gcp")
        self.assertEqual(self.client.icon_name, "network-workgroup-symbolic")
        self.assertIn("GCP", self.client.context_title)
        self.assertIn("GCP", self.client.context_btn_tooltip)
        self.assertIn("GCP", self.client.loading_message)
        self.assertIn("GCP", self.client.empty_message)
        self.assertIn("Google Cloud", self.client.error_message)

        parent = MagicMock()
        on_success = MagicMock()
        with patch("src.ui.dialogs.show_change_project_dialog") as mock_dialog:
            self.client.open_context_dialog(parent, on_success)
            mock_dialog.assert_called_once()
            # Simulate confirming
            on_confirm_cb = mock_dialog.call_args[0][2]
            on_confirm_cb("new-switched-project")
            self.assertEqual(self.client.project_id, "new-switched-project")
            on_success.assert_called_once()

    def test_parse_timestamp_variants(self):
        from src.providers.gcp import _parse_timestamp

        now = datetime.now()
        self.assertIsNone(_parse_timestamp(None))
        self.assertEqual(_parse_timestamp(now), now)

        mock_ts = MagicMock()
        mock_ts.ToDatetime.return_value = now
        del mock_ts.to_datetime
        self.assertEqual(_parse_timestamp(mock_ts), now)

        mock_ts2 = MagicMock()
        del mock_ts2.ToDatetime
        mock_ts2.to_datetime.return_value = now
        self.assertEqual(_parse_timestamp(mock_ts2), now)

    @patch.dict("os.environ", {"GCLOUD_PROJECT": "gcloud-env-proj"})
    def test_detect_project_id_gcloud_var(self):
        self.assertEqual(GCPSecretClient.detect_project_id(), "gcloud-env-proj")

    @patch.dict("os.environ", {"CLOUDSDK_CORE_PROJECT": "cloudsdk-proj"}, clear=True)
    def test_detect_project_id_cloudsdk_var(self):
        self.assertEqual(GCPSecretClient.detect_project_id(), "cloudsdk-proj")

    def test_detect_project_id_from_gcloud_config_file(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = os.path.join(tmpdir, ".config", "gcloud")
            os.makedirs(os.path.join(config_dir, "configurations"), exist_ok=True)
            with open(os.path.join(config_dir, "active_config"), "w") as f:
                f.write("my-profile")
            with open(os.path.join(config_dir, "configurations", "config_my-profile"), "w") as f:
                f.write("[core]\nproject = ini-file-project\n")

            with patch("os.path.expanduser", return_value=config_dir):
                with patch.dict("os.environ", {}, clear=True):
                    proj = GCPSecretClient.detect_project_id()
                    self.assertEqual(proj, "ini-file-project")

    @patch(
        "google.auth.default",
        side_effect=google.auth.exceptions.DefaultCredentialsError("No creds"),
    )
    def test_initialize_client_default_creds_error(self, mock_auth):
        client = GCPSecretClient(project_id="test-p")
        with self.assertRaises(RuntimeError) as ctx:
            client.initialize_client()
        self.assertIn("gcloud auth application-default login", str(ctx.exception))

    @patch("google.auth.default", side_effect=google.auth.exceptions.GoogleAuthError("Auth failed"))
    def test_initialize_client_google_auth_error(self, mock_auth):
        client = GCPSecretClient(project_id="test-p")
        with self.assertRaises(RuntimeError) as ctx:
            client.initialize_client()
        self.assertIn("Error de autenticación", str(ctx.exception))

    def test_delete_secret_with_short_name(self):
        self.client.delete_secret("short-secret-id")
        self.mock_sm_client.delete_secret.assert_called_with(
            request={"name": "projects/test-project/secrets/short-secret-id"}
        )

    @patch("google.auth.transport.requests.AuthorizedSession")
    def test_list_available_projects_success(self, mock_auth_session_cls):
        mock_session = MagicMock()
        mock_auth_session_cls.return_value = mock_session

        resp1 = MagicMock()
        resp1.status_code = 200
        resp1.json.return_value = {
            "projects": [
                {"projectId": "alpha-proj", "name": "Alpha", "lifecycleState": "ACTIVE"},
                {
                    "projectId": "deleted-proj",
                    "name": "Deleted",
                    "lifecycleState": "DELETE_REQUESTED",
                },
            ],
            "nextPageToken": "token-123",
        }

        resp2 = MagicMock()
        resp2.status_code = 200
        resp2.json.return_value = {
            "projects": [
                {"projectId": "beta-proj", "name": "Beta", "lifecycleState": "ACTIVE"},
            ]
        }

        mock_session.get.side_effect = [resp1, resp2]

        projects = self.client.list_available_projects()
        self.assertEqual(len(projects), 2)
        self.assertEqual(projects[0].project_id, "alpha-proj")
        self.assertEqual(projects[1].project_id, "beta-proj")

    @patch("google.auth.transport.requests.AuthorizedSession")
    def test_list_available_projects_error(self, mock_auth_session_cls):
        mock_session = MagicMock()
        mock_auth_session_cls.return_value = mock_session
        resp = MagicMock()
        resp.status_code = 403
        resp.text = "Forbidden"
        mock_session.get.return_value = resp

    def test_exceptions_and_error_handling_in_all_methods(self):
        from google.api_core.exceptions import GoogleAPICallError

        # list_secrets NotFound and GoogleAPICallError
        self.mock_sm_client.list_secrets.side_effect = NotFound("Project not found")
        with self.assertRaises(ResourceNotFoundError):
            self.client.list_secrets()

        self.mock_sm_client.list_secrets.side_effect = GoogleAPICallError("Generic call error")
        with self.assertRaises(Exception):
            self.client.list_secrets()

        # list_versions exceptions
        self.mock_sm_client.list_secret_versions.side_effect = PermissionDenied("No access")
        with self.assertRaises(PermissionDeniedError):
            self.client.list_versions("projects/p/secrets/s")

        self.mock_sm_client.list_secret_versions.side_effect = NotFound("Secret not found")
        with self.assertRaises(ResourceNotFoundError):
            self.client.list_versions("projects/p/secrets/s")

        self.mock_sm_client.list_secret_versions.side_effect = GoogleAPICallError("API error")
        with self.assertRaises(Exception):
            self.client.list_versions("projects/p/secrets/s")

        # access_secret_payload exceptions
        self.mock_sm_client.access_secret_version.side_effect = NotFound("Version not found")
        with self.assertRaises(ResourceNotFoundError):
            self.client.access_secret_payload("projects/p/secrets/s/versions/1")

        self.mock_sm_client.access_secret_version.side_effect = GoogleAPICallError("API error")
        with self.assertRaises(Exception):
            self.client.access_secret_payload("projects/p/secrets/s/versions/1")

        # create_secret GoogleAPICallError
        self.mock_sm_client.create_secret.side_effect = GoogleAPICallError("Create failed")
        with self.assertRaises(Exception):
            self.client.create_secret(secret_id="s", payload_data="p")

        # add_secret_version exceptions
        self.mock_sm_client.add_secret_version.side_effect = PermissionDenied("Deny add")
        with self.assertRaises(PermissionError):
            self.client.add_secret_version("s", "payload")

        self.mock_sm_client.add_secret_version.side_effect = GoogleAPICallError("Add failed")
        with self.assertRaises(RuntimeError):
            self.client.add_secret_version("s", "payload")

        # toggle_version_state exceptions
        self.mock_sm_client.disable_secret_version.side_effect = PermissionDenied("Deny disable")
        with self.assertRaises(PermissionError):
            self.client.toggle_version_state("projects/p/secrets/s/versions/1", False)

        self.mock_sm_client.disable_secret_version.side_effect = GoogleAPICallError(
            "Disable failed"
        )
        with self.assertRaises(RuntimeError):
            self.client.toggle_version_state("projects/p/secrets/s/versions/1", False)

        # destroy_version exceptions
        self.mock_sm_client.destroy_secret_version.side_effect = PermissionDenied("Deny destroy")
        with self.assertRaises(PermissionError):
            self.client.destroy_version("projects/p/secrets/s/versions/1")

        self.mock_sm_client.destroy_secret_version.side_effect = GoogleAPICallError("Destroy error")
        with self.assertRaises(RuntimeError):
            self.client.destroy_version("projects/p/secrets/s/versions/1")

    def test_detect_project_id_default_auth_fallback(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("os.path.exists", return_value=False):
                with patch("google.auth.default", return_value=(MagicMock(), "auth-fallback-proj")):
                    self.assertEqual(GCPSecretClient.detect_project_id(), "auth-fallback-proj")

    def test_gcp_client_100_percent_coverage(self):
        from google.api_core.exceptions import GoogleAPICallError

        from src.providers.gcp import _parse_timestamp

        # 1. _parse_timestamp with object having no timestamp methods (line 30)
        self.assertIsNone(_parse_timestamp("not_a_valid_timestamp_obj"))

        # 2. initialize_client detects project and sets _client (lines 118-119, 130-131)
        c = GCPSecretClient(project_id=None)
        mock_creds = MagicMock()
        with patch("google.auth.default", return_value=(mock_creds, "auto-detected-proj")):
            with patch(
                "src.providers.gcp.secretmanager_v1.SecretManagerServiceClient"
            ) as mock_sm_cls:
                self.assertIsNotNone(c.initialize_client())
                self.assertEqual(c.project_id, "auto-detected-proj")
                mock_sm_cls.assert_called_once_with(credentials=mock_creds)

        # 2b. initialize_client when _project_id is already set (118->130)
        c_preset = GCPSecretClient(project_id="already-preset")
        with patch("google.auth.default", return_value=(mock_creds, "detected-ignored")):
            with patch("src.providers.gcp.secretmanager_v1.SecretManagerServiceClient"):
                c_preset.initialize_client()
                self.assertEqual(c_preset.project_id, "already-preset")

        # 3. detect_project_id config file branches (160->163, 168->176, 170->176, 172-173, 178->183, 180-183)
        with patch.dict("os.environ", {}, clear=True):
            # ADC returns project=None (178->183)
            with patch("os.path.exists", return_value=False):
                with patch("google.auth.default", return_value=(mock_creds, None)):
                    self.assertIsNone(GCPSecretClient.detect_project_id())

            # Empty active_config and parser without core/project
            with patch(
                "os.path.exists",
                side_effect=lambda p: "active_config" in p or "config_default" in p,
            ):
                with patch("builtins.open", unittest.mock.mock_open(read_data="   ")):
                    with patch("configparser.ConfigParser") as mock_cp:
                        mock_cp.return_value.has_option.return_value = False
                        with patch("google.auth.default", side_effect=Exception("No ADC")):
                            self.assertIsNone(GCPSecretClient.detect_project_id())

            # Config file where project is blank string
            with patch("os.path.exists", side_effect=lambda p: "config_default" in p):
                with patch("configparser.ConfigParser") as mock_cp:
                    mock_cp.return_value.has_option.return_value = True
                    mock_cp.return_value.get.return_value = "   "
                    with patch("google.auth.default", side_effect=Exception("No ADC")):
                        self.assertIsNone(GCPSecretClient.detect_project_id())

            # Exception reading config
            with patch("os.path.exists", side_effect=PermissionError("Access denied")):
                with patch("google.auth.default", side_effect=Exception("No ADC")):
                    self.assertIsNone(GCPSecretClient.detect_project_id())

        # 4. list_secrets with replica automatic=False and user_managed=None (208->212)
        mock_sec = MagicMock()
        mock_sec.name = "projects/test-project/secrets/no-repl"
        mock_sec.replication.automatic = False
        mock_sec.replication.user_managed = None
        mock_sec.labels = {}
        mock_sec.create_time = None
        self.mock_sm_client.list_secrets.return_value = [mock_sec]
        secrets = self.client.list_secrets()
        self.assertEqual(secrets[0].replication_type, "AUTOMATIC")

        # 5. list_versions with non-integer version ID (269-270)
        mock_ver = MagicMock()
        mock_ver.name = "projects/test-project/secrets/my-sec/versions/custom-str"
        mock_ver.state = 1
        mock_ver.create_time = None
        mock_ver.destroy_time = None
        self.mock_sm_client.list_secret_versions.return_value = [mock_ver]
        versions = self.client.list_versions("projects/test-project/secrets/my-sec")
        self.assertEqual(versions[0].version_id, "custom-str")

        # 6. access_secret_payload PermissionDenied (303)
        self.mock_sm_client.access_secret_version.side_effect = PermissionDenied("No accessor role")
        with self.assertRaises(PermissionDeniedError):
            self.client.access_secret_payload("projects/test-project/secrets/my-sec/versions/1")

        # 7. create_secret without payload_data (349->352) and PermissionDenied (361)
        mock_created = MagicMock()
        mock_created.name = "projects/test-project/secrets/empty-sec"
        mock_created.labels = {}
        mock_created.create_time = None
        self.mock_sm_client.create_secret.side_effect = None
        self.mock_sm_client.create_secret.return_value = mock_created
        sec_item = self.client.create_secret("empty-sec", payload_data=None)
        self.assertEqual(sec_item.secret_id, "empty-sec")

        self.mock_sm_client.create_secret.side_effect = PermissionDenied("Admin required")
        with self.assertRaises(PermissionError):
            self.client.create_secret("failed-sec", payload_data="val")

        # 8. enable_secret_version PermissionDenied and GoogleAPICallError (412-415)
        self.mock_sm_client.enable_secret_version.side_effect = PermissionDenied("Cannot enable")
        with self.assertRaises(PermissionError):
            self.client.enable_secret_version("projects/test-project/secrets/s/versions/1")

        self.mock_sm_client.enable_secret_version.side_effect = GoogleAPICallError(
            "Enable API error"
        )
        with self.assertRaises(RuntimeError):
            self.client.enable_secret_version("projects/test-project/secrets/s/versions/1")

        # 9. delete_secret PermissionDenied and GoogleAPICallError (463-471)
        self.mock_sm_client.delete_secret.side_effect = PermissionDenied("Cannot delete")
        with self.assertRaises(PermissionDeniedError):
            self.client.delete_secret("my-sec")

        self.mock_sm_client.delete_secret.side_effect = GoogleAPICallError("Delete API error")
        with self.assertRaises(Exception):
            self.client.delete_secret("my-sec")

        # 10. list_available_projects status_code != 200 (486) and general exception (510-511)
        with patch("google.auth.transport.requests.AuthorizedSession") as mock_as:
            mock_resp = MagicMock(status_code=403, text="Forbidden")
            mock_as.return_value.get.return_value = mock_resp
            with self.assertRaises(RuntimeError) as cm:
                self.client.list_available_projects()
            self.assertIn("No fue posible consultar los proyectos de GCP", str(cm.exception))


class TestGCPVersionNamePaths(unittest.TestCase):
    def setUp(self):
        self.client = GCPSecretClient(project_id="test-project")
        self.mock_sm_client = MagicMock()
        self.client._client = self.mock_sm_client

    def test_list_versions_with_short_secret_name(self):
        self.mock_sm_client.list_secret_versions.return_value = []
        self.client.list_versions("my-secret")
        request = self.mock_sm_client.list_secret_versions.call_args.kwargs["request"]
        self.assertEqual(request.parent, "projects/test-project/secrets/my-secret")

    def test_access_payload_with_version_on_full_name(self):
        response = MagicMock()
        response.payload.data = b"v3"
        self.mock_sm_client.access_secret_version.return_value = response
        payload, _ = self.client.access_secret_payload("projects/test-project/secrets/s", "3")
        self.assertEqual(payload, "v3")
        request = self.mock_sm_client.access_secret_version.call_args.kwargs["request"]
        self.assertEqual(request.name, "projects/test-project/secrets/s/versions/3")

    def test_access_payload_full_name_without_version_uses_latest(self):
        response = MagicMock()
        response.payload.data = b"latest"
        self.mock_sm_client.access_secret_version.return_value = response
        self.client.access_secret_payload("projects/test-project/secrets/s")
        request = self.mock_sm_client.access_secret_version.call_args.kwargs["request"]
        self.assertEqual(request.name, "projects/test-project/secrets/s/versions/latest")

    def test_add_secret_version_with_full_name(self):
        version = MagicMock()
        version.name = "projects/test-project/secrets/s/versions/3"
        version.state = secretmanager_v1.SecretVersion.State.ENABLED
        version.create_time = None
        version.destroy_time = None
        self.mock_sm_client.add_secret_version.return_value = version
        self.client.add_secret_version("projects/test-project/secrets/s", "payload")
        request = self.mock_sm_client.add_secret_version.call_args.kwargs["request"]
        self.assertEqual(request["parent"], "projects/test-project/secrets/s")


class TestGCPUpdateMetadata(unittest.TestCase):
    def setUp(self):
        self.client = GCPSecretClient(project_id="test-project")
        self.mock_sm_client = MagicMock()
        self.client._client = self.mock_sm_client

    def test_update_metadata_short_name(self):
        self.client.update_metadata("my-secret", {"env": "prod"}, None)
        request = self.mock_sm_client.update_secret.call_args.kwargs["request"]
        self.assertEqual(request["secret"]["name"], "projects/test-project/secrets/my-secret")

    def test_update_metadata_permission_denied(self):
        self.mock_sm_client.update_secret.side_effect = PermissionDenied("denied")
        with self.assertRaises(PermissionDeniedError):
            self.client.update_metadata("my-secret", {}, None)

    def test_update_metadata_not_found(self):
        self.mock_sm_client.update_secret.side_effect = NotFound("missing")
        with self.assertRaises(ResourceNotFoundError):
            self.client.update_metadata("my-secret", {}, None)

    def test_update_metadata_api_error(self):
        from google.api_core.exceptions import GoogleAPICallError

        from src.exceptions import ProviderError

        self.mock_sm_client.update_secret.side_effect = GoogleAPICallError("boom")
        with self.assertRaises(ProviderError):
            self.client.update_metadata("my-secret", {}, None)


if __name__ == "__main__":
    unittest.main()
