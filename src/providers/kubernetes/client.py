"""Kubernetes Secrets provider (kubeconfig based)."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from src.i18n import _
from src.providers.base import BaseSecretProvider
from src.providers.kubernetes.api import KubeAPIError, KubeHTTP
from src.providers.kubernetes.kubeconfig import (
    context_namespace,
    current_context,
    list_contexts,
    resolve_context,
)
from src.providers.kubernetes.ops import KubernetesOperationsMixin


class KubernetesClient(KubernetesOperationsMixin, BaseSecretProvider):
    """Provider for the Secrets of one namespace of a cluster in your kubeconfig."""

    def __init__(self, context: Optional[str] = None, namespace: Optional[str] = None):
        """Initialize the client.

        Args:
            context: Kubeconfig context name; defaults to the current context.
            namespace: Namespace; defaults to the one of the context, or "default".
        """
        self._context = context
        self._namespace = namespace
        self._http_client: Optional[KubeHTTP] = None

    @property
    def provider_id(self) -> str:
        """Return the unique provider identifier string ('k8s')."""
        return "k8s"

    @property
    def display_name(self) -> str:
        """Return the human-readable provider name shown in the UI switcher."""
        return "Kubernetes Secrets"

    @property
    def icon_name(self) -> str:
        """Return the symbolic icon name for the context switcher button."""
        return "network-server-symbolic"

    @property
    def context_subtitle(self) -> str:
        """Return the subtitle with the active context and namespace."""
        if not self.context:
            return _("Kubernetes: no context selected")
        return _("Kubernetes: %s") % f"{self.context} / {self.namespace}"

    @property
    def context_btn_tooltip(self) -> str:
        """Return the tooltip for the context switcher button."""
        return _("Switch Kubernetes context & namespace")

    @property
    def loading_message(self) -> str:
        """Return the message shown while querying the cluster."""
        return _("Querying Kubernetes...")

    @property
    def empty_message(self) -> str:
        """Return the message shown when the namespace has no Secrets."""
        return _("No secrets found in this namespace.")

    @property
    def supports_metadata_edit(self) -> bool:
        """Labels can be edited."""
        return True

    @property
    def supports_version_restore(self) -> bool:
        """Kubernetes keeps no history, so there is nothing to restore."""
        return False

    @property
    def error_message(self) -> str:
        """Return the message shown when connection or query fails."""
        return _("Could not connect to the Kubernetes cluster.")

    @property
    def context(self) -> Optional[str]:
        """Return the active kubeconfig context name."""
        return self._context or current_context()

    @property
    def namespace(self) -> str:  # type: ignore[override]
        """Return the active namespace."""
        return self._namespace or context_namespace(self.context)

    def available_contexts(self) -> List[str]:
        """Context names defined in the kubeconfig."""
        return list_contexts()

    def list_namespaces(self, context: Optional[str] = None) -> List[str]:
        """Namespaces of a context (the active one by default); empty when not permitted.

        Many users may read Secrets in a namespace without being allowed to list namespaces,
        so a denied request is not an error: the dialog falls back to typing the name.
        """
        name = context or self.context
        http = self._http() if name == self.context else KubeHTTP(resolve_context(name))
        try:
            page = http.request("GET", "/api/v1/namespaces")
        except KubeAPIError as exc:
            if exc.status in (401, 403, 404):
                return []
            raise self._translate(exc) from exc
        return sorted(item["metadata"]["name"] for item in page.get("items", []))

    def configure(self, context: Optional[str], namespace: Optional[str]) -> None:
        """Apply the context and namespace chosen in the dialog."""
        self._context = (context or "").strip() or None
        self._namespace = (namespace or "").strip() or None
        self._http_client = None

    def saved_context(self) -> Dict[str, str]:
        """Return the chosen context and namespace."""
        context = {"context": self._context, "namespace": self._namespace}
        return {k: v for k, v in context.items() if v}

    def restore_context(self, context: Dict[str, str]) -> None:
        """Re-select the remembered context and namespace."""
        self._context = context.get("context") or self._context
        self._namespace = context.get("namespace") or self._namespace
        self._http_client = None

    def lock(self) -> None:
        """Drop the cached connection (tokens are re-read from the kubeconfig on demand)."""
        self._http_client = None

    def _invalidate(self) -> None:
        self._http_client = None

    def _http(self) -> KubeHTTP:
        """Build (and cache) the HTTP client from the kubeconfig."""
        if self._http_client is None:
            access = resolve_context(self.context)
            self._http_client = KubeHTTP(access)
        return self._http_client

    def open_context_dialog(self, parent_window: Any, on_success: Callable[[], None]) -> None:
        """Open the dialog to choose the context and namespace."""
        from src.ui.dialogs import show_change_kubernetes_dialog

        show_change_kubernetes_dialog(parent_window, self, on_success)
