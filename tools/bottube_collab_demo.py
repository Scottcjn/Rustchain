"""
bottube_collab_demo.py — Demo: 3 agents collaborating on a BoTTube video response.

Run:
    python tools/bottube_collab_demo.py
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(__file__))
from bottube_collab import CollabSession

DEMO_DB = "/tmp/bottube_collab_demo.db"
VIDEO_ID = "dQw4w9WgXcQ"  # classic

AGENTS = ["agent-alice", "agent-bob", "agent-carol"]


def pretty(label: str, data) -> None:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(json.dumps(data, indent=2, default=str))


def main():
    # Clean slate for demo
    if os.path.exists(DEMO_DB):
        os.remove(DEMO_DB)

    cs = CollabSession(
        db_path=DEMO_DB,
        min_votes=2,
        proposal_timeout=300,
        max_agents=5,
    )

    # ── 1. Create session ────────────────────────────────────────────────
    sess = cs.create_session(VIDEO_ID, min_votes=2)
    session_id = sess["session_id"]
    pretty("1. Session created", sess)

    # ── 2. Agents add collaborative fragments ────────────────────────────
    f1 = cs.add_fragment(session_id, AGENTS[0], "This video changed my life.", position=0)
    f2 = cs.add_fragment(session_id, AGENTS[1], "The production quality is top-notch.", position=1)
    f3 = cs.add_fragment(session_id, AGENTS[2], "Highly recommended for all viewers!", position=2)
    pretty("2. Fragments added (alice, bob, carol)", [f1, f2, f3])

    shared = cs.get_shared_response(session_id)
    pretty("2b. Assembled shared response", shared)

    # ── 3. Agents submit proposals ───────────────────────────────────────
    p1 = cs.add_proposal(session_id, AGENTS[0], "Absolute banger — 10/10 from Alice!")
    p2 = cs.add_proposal(session_id, AGENTS[1], "Bob says: instant classic, watch it twice.")
    p3 = cs.add_proposal(session_id, AGENTS[2], "Carol's take: pure nostalgia fuel.")
    pretty("3. Proposals submitted", [p1, p2, p3])

    proposal_id_p2 = p2["proposal_id"]

    # ── 4. Voting ────────────────────────────────────────────────────────
    v1 = cs.vote(session_id, proposal_id_p2, AGENTS[0])   # alice votes for bob's proposal
    v2 = cs.vote(session_id, proposal_id_p2, AGENTS[2])   # carol votes for bob's proposal
    pretty("4. Votes cast (alice + carol → bob's proposal)", [v1, v2])

    # Duplicate vote guard demo
    dup = cs.vote(session_id, proposal_id_p2, AGENTS[0])
    pretty("4b. Duplicate vote rejected", dup)

    # ── 5. List proposals with vote counts ───────────────────────────────
    proposals = cs.list_proposals(session_id)
    pretty("5. Proposals with vote counts", proposals)

    # ── 6. Finalize ──────────────────────────────────────────────────────
    finalized = cs.finalize(session_id)
    pretty("6. Session finalized", finalized)

    # ── 7. Publish ───────────────────────────────────────────────────────
    published = cs.publish(session_id)
    pretty("7. Session published", published)

    # ── 8. Final session state ───────────────────────────────────────────
    final = cs.get_session(session_id)
    pretty("8. Final session state", final)

    print("\n✅ Demo complete. The BoTTube response has been collaboratively selected and published.")


if __name__ == "__main__":
    main()
