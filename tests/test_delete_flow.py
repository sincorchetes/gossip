from __future__ import annotations

from unittest.mock import patch

from src.i18n import set_language
from src.models import SecretItem
from tests.test_window import DummySyncThread
from tests.window_case import WindowCase


class TestAwsDeleteFlow(WindowCase):
    def setUp(self):
        super().setUp()
        set_language("en")
        self.addCleanup(set_language, "es")

    def delete(self, **confirm_kwargs):
        self.window.active_provider = self.mock_aws
        self.mock_aws.provider_id = "aws"
        self.window.selected_secret = SecretItem(name="arn:x", secret_id="prod/db")
        with (
            patch.object(self.window.dialogs, "confirm_delete") as dialog,
            patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)),
            patch("threading.Thread", side_effect=DummySyncThread),
            patch.object(self.window, "_show_toast") as toast,
            patch.object(self.window, "_load_secrets_async"),
        ):
            self.window._on_delete_secret_clicked()
            dialog.call_args[0][2](**confirm_kwargs)
        return toast

    def test_default_deletion_keeps_the_recovery_window(self):
        toast = self.delete()
        self.mock_aws.delete_secret.assert_called_once_with("arn:x")
        self.assertIn("recoverable", toast.call_args.args[0])

    def test_immediate_deletion_is_explicit(self):
        toast = self.delete(immediate=True)
        self.mock_aws.delete_secret.assert_called_once_with("arn:x", force=True)
        self.assertIn("permanently", toast.call_args.args[0])
