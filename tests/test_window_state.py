"""The window's state rules, tested without GTK."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from src.models import SecretItem, SecretVersionItem
from src.ui.windows import state as ws


def make_state():
    providers = {}
    for provider_id in ("gcp", "aws"):
        provider = MagicMock()
        provider.provider_id = provider_id
        providers[provider_id] = provider
    return ws.WindowState(providers=providers, active_provider=providers["gcp"])


def secret(name="s"):
    return SecretItem(name=name, secret_id=name)


class TestSelection(unittest.TestCase):
    def test_selecting_forgets_the_previous_value_and_invalidates_requests(self):
        state = make_state()
        state.current_payload = "old"
        state.is_payload_revealed = True
        state.payload_pending = ws.REVEAL
        before = state.payload_request_id
        state.select_secret(secret("a"))
        self.assertEqual(state.selected_secret.name, "a")
        self.assertIsNone(state.current_payload)
        self.assertFalse(state.is_payload_revealed)
        self.assertIsNone(state.payload_pending)
        self.assertGreater(state.payload_request_id, before)
        self.assertTrue(state.is_selected("a"))
        self.assertFalse(state.is_selected("b"))

    def test_nothing_is_selected_at_first(self):
        self.assertFalse(make_state().is_selected("a"))

    def test_switching_provider_drops_everything_of_the_previous_one(self):
        state = make_state()
        state.secrets = [secret()]
        state.select_secret(secret())
        state.current_versions = [SecretVersionItem(version_id="1", name="v")]
        state.current_payload = "x"
        state.switch_provider("aws")
        self.assertEqual(state.provider_id, "aws")
        self.assertEqual((state.secrets, state.current_versions), ([], []))
        self.assertIsNone(state.selected_secret)
        self.assertIsNone(state.current_payload)


class TestPayloadRules(unittest.TestCase):
    def test_a_value_is_only_kept_while_it_is_revealed(self):
        state = make_state()
        request = state.start_payload_request(ws.COPY)
        reply = state.receive_payload("secret", None, "gcp", request)
        self.assertEqual((reply.kind, reply.copy, reply.revealed), (ws.LOADED, "secret", False))
        self.assertIsNone(state.current_payload)  # fetched only to copy: not kept

        request = state.start_payload_request(ws.REVEAL)
        reply = state.receive_payload("secret", None, "gcp", request)
        self.assertEqual((reply.kind, reply.copy, reply.revealed), (ws.LOADED, None, True))
        self.assertEqual(state.current_payload, "secret")
        self.assertEqual(reply.intent, ws.REVEAL)
        state.hide_payload()
        self.assertEqual((state.current_payload, state.is_payload_revealed), (None, False))

    def test_a_slow_reply_never_shows_under_another_secret(self):
        state = make_state()
        state.select_secret(secret("first"))
        slow = state.start_payload_request(ws.REVEAL)
        state.select_secret(secret("second"))  # the user moved on
        reply = state.receive_payload("FIRST-VALUE", None, "gcp", slow)
        self.assertEqual(reply.kind, ws.IGNORED)
        self.assertIsNone(state.current_payload)

    def test_a_newer_request_supersedes_an_older_one(self):
        state = make_state()
        old = state.start_payload_request(ws.REVEAL)
        new = state.start_payload_request(ws.REVEAL)
        self.assertEqual(state.receive_payload("old", None, "gcp", old).kind, ws.IGNORED)
        self.assertEqual(state.receive_payload("new", None, "gcp", new).kind, ws.LOADED)
        self.assertEqual(state.current_payload, "new")

    def test_replies_for_another_provider_are_ignored(self):
        state = make_state()
        request = state.start_payload_request(ws.REVEAL)
        self.assertEqual(state.receive_payload("v", None, "aws", request).kind, ws.IGNORED)
        self.assertEqual(state.payload_pending, ws.REVEAL)  # still waiting for the right one

    def test_errors_clear_the_value(self):
        state = make_state()
        state.current_payload = "old"
        state.is_payload_revealed = True
        request = state.start_payload_request(ws.REVEAL)
        reply = state.receive_payload(None, "denied", "gcp", request)
        self.assertEqual(reply.kind, ws.FAILED)
        self.assertEqual((state.current_payload, state.is_payload_revealed), (None, False))
        self.assertIsNone(state.payload_pending)

    def test_a_reply_without_a_request_id_is_accepted_and_empty_copies_copy_nothing(self):
        state = make_state()
        state.payload_pending = ws.COPY
        reply = state.receive_payload("", None, "gcp")
        self.assertEqual((reply.kind, reply.copy), (ws.LOADED, None))

    def test_starting_a_request_without_an_intent_keeps_the_pending_one(self):
        state = make_state()
        state.payload_pending = ws.REVEAL
        state.start_payload_request()
        self.assertEqual(state.payload_pending, ws.REVEAL)


if __name__ == "__main__":
    unittest.main()
