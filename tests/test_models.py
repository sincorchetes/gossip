from __future__ import annotations

from datetime import datetime
import unittest

from src.models import (
    AnsibleVaultItem,
    AWSContextItem,
    AzureVaultItem,
    GCPProjectItem,
    SecretItem,
    SecretVersionItem,
)


class TestModels(unittest.TestCase):
    def test_secret_version_display_state_gcp(self):
        v_enabled = SecretVersionItem(
            version_id="1",
            name="projects/test/secrets/sec1/versions/1",
            state="ENABLED",
        )
        self.assertIn(v_enabled.display_state, ("Enabled", "Habilitada", "Habilitado"))

        v_disabled = SecretVersionItem(
            version_id="2",
            name="projects/test/secrets/sec1/versions/2",
            state="STATE_DISABLED",
        )
        self.assertIn(v_disabled.display_state, ("Disabled", "Deshabilitada", "Deshabilitado"))

        v_destroyed = SecretVersionItem(
            version_id="3",
            name="projects/test/secrets/sec1/versions/3",
            state="DESTROYED",
        )
        self.assertIn(v_destroyed.display_state, ("Destroyed", "Destruida", "Destruido"))

        v_custom = SecretVersionItem(
            version_id="4",
            name="projects/test/secrets/sec1/versions/4",
            state="UNKNOWN_STATE",
        )
        self.assertEqual(v_custom.display_state, "UNKNOWN_STATE")


    def test_secret_version_display_state_aws(self):
        v_current = SecretVersionItem(
            version_id="uuid-1",
            name="arn:aws:secretsmanager:eu-west-1:123456789:secret:my-secret",
            stages=["AWSCURRENT"],
        )
        self.assertIn(v_current.display_state, ("Current", "Actual"))

        v_current_tagged = SecretVersionItem(
            version_id="uuid-2",
            name="arn:aws:secretsmanager:eu-west-1:123456789:secret:my-secret",
            stages=["AWSCURRENT", "PROD"],
        )
        self.assertTrue("PROD" in v_current_tagged.display_state)

        v_previous = SecretVersionItem(
            version_id="uuid-3",
            name="arn:aws:secretsmanager:eu-west-1:123456789:secret:my-secret",
            stages=["AWSPREVIOUS"],
        )
        self.assertIn(v_previous.display_state, ("Previous", "Anterior"))

        v_custom = SecretVersionItem(
            version_id="uuid-4",
            name="arn:aws:secretsmanager:eu-west-1:123456789:secret:my-secret",
            stages=["STAGING", "DEV"],
        )
        self.assertEqual(v_custom.display_state, "STAGING, DEV")

    def test_secret_item_replication_summary(self):
        s_auto = SecretItem(
            name="projects/p/secrets/s1",
            secret_id="s1",
            replication_type="AUTOMATIC",
        )
        self.assertIn(s_auto.replication_summary, ("Automatic", "Automática"))

        s_single = SecretItem(
            name="projects/p/secrets/s2",
            secret_id="s2",
            replication_type="SINGLE_REGION",
        )
        self.assertIn(s_single.replication_summary, ("Single region", "Región única"))

        s_replicated = SecretItem(
            name="projects/p/secrets/s3",
            secret_id="s3",
            locations=["europe-west1", "europe-west3"],
        )
        self.assertTrue("europe-west1" in s_replicated.replication_summary)

        s_user_managed = SecretItem(
            name="projects/p/secrets/s4",
            secret_id="s4",
            replication_type="USER_MANAGED",
        )
        self.assertIn(s_user_managed.replication_summary, ("User managed", "Definida por el usuario", "Gestionado por usuario"))

    def test_context_and_vault_items(self):
        gcp_proj = GCPProjectItem(project_id="my-proj", name="My Project", lifecycle_state="ACTIVE")
        self.assertEqual(gcp_proj.project_id, "my-proj")
        self.assertEqual(gcp_proj.name, "My Project")

        aws_ctx = AWSContextItem(profile="production", region="eu-west-1")
        self.assertEqual(aws_ctx.profile, "production")
        self.assertEqual(aws_ctx.region, "eu-west-1")

        azure_vault = AzureVaultItem(name="my-kv", vault_uri="https://my-kv.vault.azure.net", location="westeurope")
        self.assertEqual(azure_vault.name, "my-kv")
        self.assertEqual(azure_vault.location, "westeurope")

        ansible_vault = AnsibleVaultItem(file_path="/tmp/vault.yml", has_password=True, is_encrypted=True)
        self.assertEqual(ansible_vault.file_path, "/tmp/vault.yml")
        self.assertTrue(ansible_vault.has_password)


if __name__ == "__main__":
    unittest.main()
