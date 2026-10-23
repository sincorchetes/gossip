from __future__ import annotations

import unittest
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.models import SecretItem, SecretVersionItem
from src.providers.base import BaseSecretProvider


class DummyProvider(BaseSecretProvider):
    @property
    def provider_id(self) -> str:
        return "dummy"

    @property
    def display_name(self) -> str:
        return "Dummy Cloud"

    @property
    def icon_name(self) -> str:
        return "dummy-icon"

    @property
    def context_title(self) -> str:
        return "Dummy Workspace"

    @property
    def context_subtitle(self) -> str:
        return "Workspace: default"

    @property
    def context_btn_tooltip(self) -> str:
        return "Switch Workspace"

    @property
    def loading_message(self) -> str:
        return "Querying Dummy Cloud..."

    @property
    def empty_message(self) -> str:
        return "No dummy secrets"

    @property
    def error_message(self) -> str:
        return "Connection failed"

    @property
    def supports_version_toggling(self) -> bool:
        return True

    @property
    def supports_version_destroy(self) -> bool:
        return False

    def list_secrets(self) -> List[SecretItem]:
        return []

    def list_versions(self, secret_name: str) -> List[SecretVersionItem]:
        return []

    def access_secret_payload(self, version_name: str) -> Tuple[Optional[str], bool]:
        return ("dummy-value", False)

    def create_secret(
        self,
        secret_id: str,
        payload_data: str,
        labels: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
    ) -> SecretItem:
        return SecretItem(name=f"dummy/{secret_id}", secret_id=secret_id)

    def add_secret_version(self, secret_name: str, payload_data: str) -> str:
        return "dummy/v2"

    def delete_secret(self, secret_name: str) -> None:
        pass

    def toggle_version_state(self, version_name: str, enable: bool) -> None:
        pass

    def destroy_version(self, version_name: str) -> None:
        pass

    def open_context_dialog(self, parent_window: Any, on_success: Callable[[], None]) -> None:
        on_success()


class TestBaseProvider(unittest.TestCase):
    def test_cannot_instantiate_abstract_base_class(self):
        with self.assertRaises(TypeError):
            BaseSecretProvider()  # type: ignore

    def test_concrete_subclass_contract(self):
        dummy = DummyProvider()
        self.assertIsInstance(dummy, BaseSecretProvider)
        self.assertEqual(dummy.provider_id, "dummy")
        self.assertEqual(dummy.display_name, "Dummy Cloud")
        self.assertTrue(dummy.supports_version_toggling)
        self.assertFalse(dummy.supports_version_destroy)
        self.assertEqual(dummy.list_secrets(), [])
        self.assertEqual(dummy.access_secret_payload("v1"), ("dummy-value", False))


if __name__ == "__main__":
    unittest.main()
