"""The window's state, without any GTK: which provider, secret, versions and value are shown.

Keeping it in one plain object means the rules that matter for secrets (a value only lives while
it is revealed, a slow reply can never show under the wrong secret) can be tested without a
display, and the mixins that draw the interface only read and update this object.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional

from src.models import SecretItem, SecretVersionItem

if TYPE_CHECKING:
    from src.providers import BaseSecretProvider

REVEAL = "reveal"
COPY = "copy"

IGNORED = "ignored"
FAILED = "failed"
LOADED = "loaded"


@dataclass
class PayloadReply:
    """What to do with an answer to a value request.

    Attributes:
        kind: IGNORED (stale or from another provider), FAILED or LOADED.
        copy: Text to put on the clipboard (the user asked to copy), if any.
        revealed: Whether the value is now shown (and therefore kept in memory).
        intent: What the user asked for (REVEAL or COPY), if anything.
    """

    kind: str
    copy: Optional[str] = None
    revealed: bool = False
    intent: Optional[str] = None


@dataclass
class WindowState:
    """Everything the main window needs to remember between redraws."""

    providers: Dict[str, "BaseSecretProvider"]
    active_provider: "BaseSecretProvider"
    secrets: List[SecretItem] = field(default_factory=list)
    selected_secret: Optional[SecretItem] = None
    current_versions: List[SecretVersionItem] = field(default_factory=list)
    current_payload: Optional[str] = None
    is_payload_revealed: bool = False
    payload_request_id: int = 0
    payload_pending: Optional[str] = None

    # -- provider and selection
    @property
    def provider_id(self) -> str:
        """Identifier of the active provider."""
        return self.active_provider.provider_id

    def switch_provider(self, provider_id: str) -> None:
        """Make another provider active and drop everything that belonged to the previous one."""
        self.active_provider = self.providers[provider_id]
        self.secrets = []
        self.selected_secret = None
        self.current_versions = []
        self.forget_payload()

    def select_secret(self, secret: SecretItem) -> None:
        """Select a secret; its value is forgotten and fetched again only on demand."""
        self.selected_secret = secret
        self.forget_payload()

    def is_selected(self, secret_name: str) -> bool:
        """True when ``secret_name`` is the selected secret."""
        return self.selected_secret is not None and self.selected_secret.name == secret_name

    # -- the value
    def forget_payload(self) -> None:
        """Drop the value and invalidate in-flight requests so late replies are ignored."""
        self.payload_request_id += 1
        self.payload_pending = None
        self.current_payload = None
        self.is_payload_revealed = False

    def hide_payload(self) -> None:
        """Hide the value and remove it from memory (without cancelling requests)."""
        self.is_payload_revealed = False
        self.current_payload = None

    def start_payload_request(self, intent: Optional[str] = None) -> int:
        """Register a request for the value and return its id.

        Args:
            intent: REVEAL or COPY when the user asked for it; None keeps the pending intent.
        """
        if intent is not None:
            self.payload_pending = intent
        self.payload_request_id += 1
        return self.payload_request_id

    def receive_payload(
        self,
        payload: Optional[str],
        error: Optional[str],
        provider_id: str,
        request_id: Optional[int] = None,
    ) -> PayloadReply:
        """Apply an answer to a value request.

        Answers from another provider or from a request that has been superseded (another
        secret, version or request was chosen meanwhile) are ignored.
        """
        if provider_id != self.provider_id:
            return PayloadReply(IGNORED)
        if request_id is not None and request_id != self.payload_request_id:
            return PayloadReply(IGNORED)

        intent, self.payload_pending = self.payload_pending, None
        if error:
            self.current_payload = None
            self.is_payload_revealed = False
            return PayloadReply(FAILED)

        self.current_payload = payload
        to_copy = None
        if intent == REVEAL:
            self.is_payload_revealed = True
        elif intent == COPY and payload:
            to_copy = payload
        if not self.is_payload_revealed:
            self.current_payload = None  # fetched only to copy it: do not keep it
        return PayloadReply(LOADED, copy=to_copy, revealed=self.is_payload_revealed, intent=intent)
