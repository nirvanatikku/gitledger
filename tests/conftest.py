"""Shared test fixtures."""

import json
import os
import tempfile

import pytest

from gitledger import Repo


@pytest.fixture
def tmp_repo(tmp_path):
    """Create a temporary GitLedger repository."""
    repo = Repo.init(tmp_path / "test-repo")
    yield repo
    repo.close()


@pytest.fixture
def populated_repo(tmp_repo):
    """A repo with several commits of structured data."""
    tmp_repo.write("agents/alpha/state.json", {
        "confidence_score": 0.85,
        "status": "active",
        "tasks_completed": 10,
    })
    tmp_repo.commit_event("agent-alpha", "state_initialized", ["agents/alpha/state.json"])

    tmp_repo.write("agents/alpha/state.json", {
        "confidence_score": 0.90,
        "status": "active",
        "tasks_completed": 12,
    })
    tmp_repo.commit_event("agent-alpha", "state_updated", ["agents/alpha/state.json"])

    tmp_repo.write("agents/alpha/beliefs.json", {
        "world_model": "stable",
        "risk_level": "low",
    })
    tmp_repo.commit_event("agent-alpha", "beliefs_updated", ["agents/alpha/beliefs.json"])

    tmp_repo.write("agents/alpha/state.json", {
        "confidence_score": 0.72,
        "status": "degraded",
        "tasks_completed": 13,
    })
    tmp_repo.commit_event("agent-alpha", "state_updated", ["agents/alpha/state.json"])

    tmp_repo.write("agents/beta/state.json", {
        "confidence_score": 0.95,
        "status": "active",
        "tasks_completed": 5,
    })
    tmp_repo.commit_event("agent-beta", "state_initialized", ["agents/beta/state.json"])

    tmp_repo.commit_checkpoint()

    return tmp_repo
