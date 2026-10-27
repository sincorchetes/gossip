"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def isolated_state_file(tmp_path, monkeypatch):
    """Keep the remembered-context file of the real user out of every test."""
    monkeypatch.setenv("GOSSIP_STATE_FILE", os.path.join(tmp_path, "state.json"))
