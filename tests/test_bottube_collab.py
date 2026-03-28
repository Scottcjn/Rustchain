"""
tests/test_bottube_collab.py — Unit tests for the BoTTube multi-agent collab system.

Run:
    python -m pytest tests/test_bottube_collab.py -v
"""

import os
import sys
import time
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from bottube_collab import CollabSession


@pytest.fixture
def cs():
    """Fresh CollabSession backed by a temp DB for each test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    session = CollabSession(db_path=db_path, min_votes=2, proposal_timeout=300, max_agents=5)
    yield session
    os.unlink(db_path)


@pytest.fixture
def session_id(cs):
    sess = cs.create_session("test_video_001")
    return sess["session_id"]


# ── Session creation ─────────────────────────────────────────────────────────

class TestSessionCreation:
    def test_create_returns_session_id(self, cs):
        result = cs.create_session("vid-abc")
        assert "session_id" in result
        assert result["video_id"] == "vid-abc"
        assert result["status"] == "open"

    def test_create_respects_custom_config(self, cs):
        result = cs.create_session("vid-xyz", min_votes=5, max_agents=3, proposal_timeout=60)
        assert result["min_votes"] == 5
        assert result["max_agents"] == 3
        assert result["proposal_timeout"] == 60

    def test_get_session_not_found(self, cs):
        result = cs.get_session("nonexistent-id")
        assert result["error"] == "session_not_found"

    def test_list_sessions(self, cs):
        cs.create_session("v1")
        cs.create_session("v2")
        all_sessions = cs.list_sessions()
        assert len(all_sessions) >= 2

    def test_list_sessions_filtered_by_video(self, cs):
        cs.create_session("unique-vid")
        cs.create_session("other-vid")
        filtered = cs.list_sessions(video_id="unique-vid")
        assert all(s["video_id"] == "unique-vid" for s in filtered)


# ── Proposals ────────────────────────────────────────────────────────────────

class TestProposals:
    def test_add_proposal_success(self, cs, session_id):
        result = cs.add_proposal(session_id, "agent-1", "Great video!")
        assert result["status"] == "submitted"
        assert "proposal_id" in result

    def test_session_advances_to_proposals(self, cs, session_id):
        cs.add_proposal(session_id, "agent-1", "Proposal A")
        sess = cs.get_session(session_id)
        assert sess["status"] == "proposals"

    def test_multiple_agents_can_propose(self, cs, session_id):
        cs.add_proposal(session_id, "agent-1", "Alpha view")
        cs.add_proposal(session_id, "agent-2", "Beta view")
        proposals = cs.list_proposals(session_id)
        assert len(proposals) == 2

    def test_proposal_invalid_session(self, cs):
        result = cs.add_proposal("bad-session", "agent-1", "content")
        assert "error" in result

    def test_proposal_after_finalize_rejected(self, cs, session_id):
        p = cs.add_proposal(session_id, "agent-1", "First")
        cs.vote(session_id, p["proposal_id"], "agent-2")
        cs.vote(session_id, p["proposal_id"], "agent-3")
        cs.finalize(session_id)
        late = cs.add_proposal(session_id, "agent-4", "Too late")
        assert "error" in late

    def test_max_agents_cap(self, cs):
        sess = cs.create_session("vid-cap", max_agents=2)
        sid = sess["session_id"]
        cs.add_proposal(sid, "agent-1", "One")
        cs.add_proposal(sid, "agent-2", "Two")
        result = cs.add_proposal(sid, "agent-3", "Three")
        assert result.get("error") == "max_agents_reached"

    def test_proposal_timeout(self, cs):
        sess = cs.create_session("vid-timeout", proposal_timeout=0)
        sid = sess["session_id"]
        time.sleep(0.05)  # ensure timeout triggers
        result = cs.add_proposal(sid, "agent-1", "Late proposal")
        assert result.get("error") == "proposal_phase_expired"


# ── Voting ───────────────────────────────────────────────────────────────────

class TestVoting:
    def _setup_proposal(self, cs, session_id) -> str:
        p = cs.add_proposal(session_id, "agent-1", "Good response")
        return p["proposal_id"]

    def test_vote_success(self, cs, session_id):
        pid = self._setup_proposal(cs, session_id)
        result = cs.vote(session_id, pid, "agent-2")
        assert "vote_id" in result
        assert result["vote_count"] == 1

    def test_duplicate_vote_rejected(self, cs, session_id):
        pid = self._setup_proposal(cs, session_id)
        cs.vote(session_id, pid, "agent-2")
        dup = cs.vote(session_id, pid, "agent-2")
        assert dup["error"] == "duplicate_vote"

    def test_multiple_agents_can_vote(self, cs, session_id):
        pid = self._setup_proposal(cs, session_id)
        cs.vote(session_id, pid, "agent-2")
        result = cs.vote(session_id, pid, "agent-3")
        assert result["vote_count"] == 2

    def test_ready_to_finalize_flag(self, cs, session_id):
        pid = self._setup_proposal(cs, session_id)
        cs.vote(session_id, pid, "agent-2")
        result = cs.vote(session_id, pid, "agent-3")
        assert result["ready_to_finalize"] is True

    def test_vote_unknown_proposal(self, cs, session_id):
        result = cs.vote(session_id, "bad-proposal-id", "agent-1")
        assert "error" in result


# ── Finalization & Publishing ─────────────────────────────────────────────────

class TestFinalization:
    def test_finalize_winning_proposal(self, cs, session_id):
        p = cs.add_proposal(session_id, "agent-1", "Winner response")
        cs.vote(session_id, p["proposal_id"], "agent-2")
        cs.vote(session_id, p["proposal_id"], "agent-3")
        result = cs.finalize(session_id)
        assert result["status"] == "finalized"
        assert result["source"] == "proposal"
        assert result["response"] == "Winner response"

    def test_finalize_fallback_to_fragments(self, cs, session_id):
        cs.add_fragment(session_id, "agent-1", "Hello", 0)
        cs.add_fragment(session_id, "agent-2", "world", 1)
        # No proposals → no winning proposal → fall back to fragments
        result = cs.finalize(session_id)
        assert result["status"] == "finalized"
        assert result["source"] == "collaborative_fragments"
        assert "Hello" in result["response"]

    def test_finalize_double_call_rejected(self, cs, session_id):
        cs.add_proposal(session_id, "agent-1", "Solo")
        cs.finalize(session_id)
        second = cs.finalize(session_id)
        assert "error" in second

    def test_publish_success(self, cs, session_id):
        p = cs.add_proposal(session_id, "agent-1", "Final answer")
        cs.vote(session_id, p["proposal_id"], "agent-2")
        cs.vote(session_id, p["proposal_id"], "agent-3")
        cs.finalize(session_id)
        pub = cs.publish(session_id)
        assert pub["status"] == "published"

    def test_publish_before_finalize_rejected(self, cs, session_id):
        result = cs.publish(session_id)
        assert "error" in result


# ── Collaborative fragments ──────────────────────────────────────────────────

class TestFragments:
    def test_add_and_assemble_fragments(self, cs, session_id):
        cs.add_fragment(session_id, "agent-1", "Part A", position=0)
        cs.add_fragment(session_id, "agent-2", "Part B", position=1)
        shared = cs.get_shared_response(session_id)
        assert "Part A" in shared["assembled"]
        assert "Part B" in shared["assembled"]
        assert len(shared["fragments"]) == 2
