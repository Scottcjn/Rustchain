from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools import bottube_collab_demo as demo


class FakeCollabSession:
    instances: list["FakeCollabSession"] = []

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.calls: list[tuple] = []
        FakeCollabSession.instances.append(self)

    def create_session(self, video_id: str, *, min_votes: int) -> dict:
        self.calls.append(("create_session", video_id, min_votes))
        return {"session_id": "session-1", "video_id": video_id, "min_votes": min_votes}

    def add_fragment(self, session_id: str, agent_id: str, fragment: str, *, position: int) -> dict:
        self.calls.append(("add_fragment", session_id, agent_id, fragment, position))
        return {"session_id": session_id, "agent_id": agent_id, "fragment": fragment, "position": position}

    def get_shared_response(self, session_id: str) -> dict:
        self.calls.append(("get_shared_response", session_id))
        return {"session_id": session_id, "response": "assembled response"}

    def add_proposal(self, session_id: str, agent_id: str, content: str) -> dict:
        self.calls.append(("add_proposal", session_id, agent_id, content))
        proposal_number = sum(1 for call in self.calls if call[0] == "add_proposal")
        return {"proposal_id": f"proposal-{proposal_number}", "agent_id": agent_id, "content": content}

    def vote(self, session_id: str, proposal_id: str, agent_id: str) -> dict:
        self.calls.append(("vote", session_id, proposal_id, agent_id))
        if agent_id == demo.AGENTS[0] and self.calls.count(("vote", session_id, proposal_id, agent_id)) > 1:
            return {"error": "duplicate_vote", "agent_id": agent_id}
        return {"proposal_id": proposal_id, "agent_id": agent_id, "status": "accepted"}

    def list_proposals(self, session_id: str) -> list[dict]:
        self.calls.append(("list_proposals", session_id))
        return [{"proposal_id": "proposal-2", "vote_count": 2}]

    def finalize(self, session_id: str) -> dict:
        self.calls.append(("finalize", session_id))
        return {"session_id": session_id, "status": "finalized"}

    def publish(self, session_id: str) -> dict:
        self.calls.append(("publish", session_id))
        return {"session_id": session_id, "status": "published"}

    def get_session(self, session_id: str) -> dict:
        self.calls.append(("get_session", session_id))
        return {"session_id": session_id, "status": "published"}


def test_demo_constants_identify_three_agents_and_classic_video() -> None:
    assert demo.VIDEO_ID == "dQw4w9WgXcQ"
    assert demo.AGENTS == ["agent-alice", "agent-bob", "agent-carol"]
    assert demo.DEMO_DB.endswith("bottube_collab_demo.db")


def test_pretty_prints_label_and_json_payload(capsys) -> None:
    demo.pretty("sample label", {"answer": 42, "items": ["a", "b"]})

    output = capsys.readouterr().out

    assert "sample label" in output
    assert "=" * 60 in output
    assert json.loads(output[output.index("{") :]) == {"answer": 42, "items": ["a", "b"]}


def test_main_runs_full_collaboration_flow_without_real_demo_db(monkeypatch, capsys) -> None:
    pretty_calls: list[tuple[str, object]] = []
    removed_paths: list[str] = []
    FakeCollabSession.instances = []

    monkeypatch.setattr(demo.os.path, "exists", lambda path: path == demo.DEMO_DB)
    monkeypatch.setattr(demo.os, "remove", removed_paths.append)
    monkeypatch.setattr(demo, "CollabSession", FakeCollabSession)
    monkeypatch.setattr(demo, "pretty", lambda label, data: pretty_calls.append((label, data)))

    demo.main()

    assert removed_paths == [demo.DEMO_DB]
    assert len(FakeCollabSession.instances) == 1
    session = FakeCollabSession.instances[0]
    assert session.kwargs == {
        "db_path": demo.DEMO_DB,
        "min_votes": 2,
        "proposal_timeout": 300,
        "max_agents": 5,
    }
    assert [call[0] for call in session.calls] == [
        "create_session",
        "add_fragment",
        "add_fragment",
        "add_fragment",
        "get_shared_response",
        "add_proposal",
        "add_proposal",
        "add_proposal",
        "vote",
        "vote",
        "vote",
        "list_proposals",
        "finalize",
        "publish",
        "get_session",
    ]
    assert session.calls[0] == ("create_session", demo.VIDEO_ID, 2)
    assert session.calls[8:11] == [
        ("vote", "session-1", "proposal-2", demo.AGENTS[0]),
        ("vote", "session-1", "proposal-2", demo.AGENTS[2]),
        ("vote", "session-1", "proposal-2", demo.AGENTS[0]),
    ]

    labels = [label for label, _ in pretty_calls]
    assert labels == [
        "1. Session created",
        "2. Fragments added (alice, bob, carol)",
        "2b. Assembled shared response",
        "3. Proposals submitted",
        "4. Votes cast (alice + carol \u2192 bob's proposal)",
        "4b. Duplicate vote rejected",
        "5. Proposals with vote counts",
        "6. Session finalized",
        "7. Session published",
        "8. Final session state",
    ]
    assert "Demo complete" in capsys.readouterr().out
