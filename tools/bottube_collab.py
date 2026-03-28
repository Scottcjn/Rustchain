"""
bottube_collab.py — Multi-agent collaboration system for BoTTube video responses.

Session lifecycle:  open → proposals → voting → finalize → published

REST-compatible: every public method returns a plain dict suitable for jsonify().
Wrap with Flask or FastAPI to expose as an HTTP API.
"""

import sqlite3
import time
import uuid
import json
import hashlib
import threading
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------
DEFAULT_MIN_VOTES = 2          # votes needed to finalize a proposal
DEFAULT_PROPOSAL_TIMEOUT = 300 # seconds the proposal phase stays open
DEFAULT_MAX_AGENTS = 10        # maximum distinct agents per session


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id   TEXT PRIMARY KEY,
            video_id     TEXT NOT NULL,
            status       TEXT NOT NULL DEFAULT 'open',
            min_votes    INTEGER NOT NULL DEFAULT 2,
            proposal_timeout INTEGER NOT NULL DEFAULT 300,
            max_agents   INTEGER NOT NULL DEFAULT 10,
            created_at   REAL NOT NULL,
            updated_at   REAL NOT NULL,
            published_response TEXT
        );

        CREATE TABLE IF NOT EXISTS proposals (
            proposal_id  TEXT PRIMARY KEY,
            session_id   TEXT NOT NULL,
            agent_id     TEXT NOT NULL,
            content      TEXT NOT NULL,
            created_at   REAL NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );

        CREATE TABLE IF NOT EXISTS votes (
            vote_id      TEXT PRIMARY KEY,
            proposal_id  TEXT NOT NULL,
            session_id   TEXT NOT NULL,
            agent_id     TEXT NOT NULL,
            created_at   REAL NOT NULL,
            UNIQUE (proposal_id, agent_id),
            FOREIGN KEY (proposal_id) REFERENCES proposals(proposal_id)
        );

        CREATE TABLE IF NOT EXISTS collaborations (
            collab_id    TEXT PRIMARY KEY,
            session_id   TEXT NOT NULL,
            agent_id     TEXT NOT NULL,
            fragment     TEXT NOT NULL,
            position     INTEGER NOT NULL DEFAULT 0,
            created_at   REAL NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# CollabSession
# ---------------------------------------------------------------------------

class CollabSession:
    """
    Manages multi-agent collaboration sessions for BoTTube video response threads.

    Usage (standalone):
        cs = CollabSession()
        sess = cs.create_session("dQw4w9WgXcQ")
        cs.add_proposal(sess["session_id"], "agent-1", "This video is awesome!")
        cs.vote(sess["session_id"], proposal_id, "agent-2")
        cs.finalize(sess["session_id"])
        cs.publish(sess["session_id"])
    """

    def __init__(
        self,
        db_path: str = "bottube_collab.db",
        min_votes: int = DEFAULT_MIN_VOTES,
        proposal_timeout: int = DEFAULT_PROPOSAL_TIMEOUT,
        max_agents: int = DEFAULT_MAX_AGENTS,
    ):
        self.db_path = db_path
        self.default_min_votes = min_votes
        self.default_proposal_timeout = proposal_timeout
        self.default_max_agents = max_agents
        self._lock = threading.Lock()
        self._conn = _get_conn(db_path)
        _init_db(self._conn)

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def create_session(
        self,
        video_id: str,
        min_votes: Optional[int] = None,
        proposal_timeout: Optional[int] = None,
        max_agents: Optional[int] = None,
    ) -> dict:
        """Create a new collaboration session for a BoTTube video."""
        session_id = str(uuid.uuid4())
        now = time.time()
        mv = min_votes if min_votes is not None else self.default_min_votes
        pt = proposal_timeout if proposal_timeout is not None else self.default_proposal_timeout
        ma = max_agents if max_agents is not None else self.default_max_agents

        with self._lock:
            self._conn.execute(
                """INSERT INTO sessions
                   (session_id, video_id, status, min_votes, proposal_timeout,
                    max_agents, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (session_id, video_id, "open", mv, pt, ma, now, now),
            )
            self._conn.commit()

        return self._session_dict(session_id)

    def get_session(self, session_id: str) -> dict:
        """Return session info, or error dict if not found."""
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        if not row:
            return {"error": "session_not_found", "session_id": session_id}
        return dict(row)

    def list_sessions(self, video_id: Optional[str] = None) -> list:
        """List all sessions, optionally filtered by video_id."""
        if video_id:
            rows = self._conn.execute(
                "SELECT * FROM sessions WHERE video_id=? ORDER BY created_at DESC",
                (video_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM sessions ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Proposal phase
    # ------------------------------------------------------------------

    def add_proposal(self, session_id: str, agent_id: str, content: str) -> dict:
        """Submit a response proposal from an agent."""
        sess = self.get_session(session_id)
        if "error" in sess:
            return sess
        if sess["status"] not in ("open", "proposals"):
            return {"error": "session_not_accepting_proposals", "status": sess["status"]}

        # Check agent cap
        agents = self._distinct_agents(session_id)
        if agent_id not in agents and len(agents) >= sess["max_agents"]:
            return {"error": "max_agents_reached", "max_agents": sess["max_agents"]}

        # Check proposal timeout
        age = time.time() - sess["created_at"]
        if age > sess["proposal_timeout"]:
            self._advance_status(session_id, "voting")
            return {"error": "proposal_phase_expired", "age_seconds": age}

        proposal_id = str(uuid.uuid4())
        now = time.time()
        with self._lock:
            self._conn.execute(
                """INSERT INTO proposals (proposal_id, session_id, agent_id, content, created_at)
                   VALUES (?,?,?,?,?)""",
                (proposal_id, session_id, agent_id, content, now),
            )
            self._advance_status(session_id, "proposals", commit=False)
            self._conn.commit()

        return {
            "proposal_id": proposal_id,
            "session_id": session_id,
            "agent_id": agent_id,
            "status": "submitted",
            "created_at": now,
        }

    def list_proposals(self, session_id: str) -> list:
        """Return all proposals for a session with their vote counts."""
        rows = self._conn.execute(
            "SELECT * FROM proposals WHERE session_id=? ORDER BY created_at",
            (session_id,),
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["vote_count"] = self._vote_count(d["proposal_id"])
            result.append(d)
        return result

    # ------------------------------------------------------------------
    # Voting phase
    # ------------------------------------------------------------------

    def vote(self, session_id: str, proposal_id: str, agent_id: str) -> dict:
        """Cast a vote for a proposal. Each agent may vote once per proposal."""
        sess = self.get_session(session_id)
        if "error" in sess:
            return sess
        if sess["status"] not in ("proposals", "voting"):
            return {"error": "session_not_in_voting_phase", "status": sess["status"]}

        # Verify proposal belongs to session
        prop = self._conn.execute(
            "SELECT * FROM proposals WHERE proposal_id=? AND session_id=?",
            (proposal_id, session_id),
        ).fetchone()
        if not prop:
            return {"error": "proposal_not_found", "proposal_id": proposal_id}

        # Prevent duplicate votes
        existing = self._conn.execute(
            "SELECT vote_id FROM votes WHERE proposal_id=? AND agent_id=?",
            (proposal_id, agent_id),
        ).fetchone()
        if existing:
            return {"error": "duplicate_vote", "proposal_id": proposal_id, "agent_id": agent_id}

        vote_id = str(uuid.uuid4())
        now = time.time()
        with self._lock:
            self._conn.execute(
                """INSERT INTO votes (vote_id, proposal_id, session_id, agent_id, created_at)
                   VALUES (?,?,?,?,?)""",
                (vote_id, proposal_id, session_id, agent_id, now),
            )
            self._advance_status(session_id, "voting", commit=False)
            self._conn.commit()

        vote_count = self._vote_count(proposal_id)
        return {
            "vote_id": vote_id,
            "proposal_id": proposal_id,
            "agent_id": agent_id,
            "vote_count": vote_count,
            "min_votes": sess["min_votes"],
            "ready_to_finalize": vote_count >= sess["min_votes"],
        }

    # ------------------------------------------------------------------
    # Collaborative fragment contributions
    # ------------------------------------------------------------------

    def add_fragment(self, session_id: str, agent_id: str, fragment: str, position: int = 0) -> dict:
        """Add a text fragment to the shared collaborative response."""
        sess = self.get_session(session_id)
        if "error" in sess:
            return sess
        if sess["status"] not in ("open", "proposals", "voting"):
            return {"error": "session_closed_for_fragments", "status": sess["status"]}

        collab_id = str(uuid.uuid4())
        now = time.time()
        with self._lock:
            self._conn.execute(
                """INSERT INTO collaborations
                   (collab_id, session_id, agent_id, fragment, position, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (collab_id, session_id, agent_id, fragment, position, now),
            )
            self._conn.commit()

        return {"collab_id": collab_id, "session_id": session_id, "agent_id": agent_id, "status": "added"}

    def get_shared_response(self, session_id: str) -> dict:
        """Assemble the shared collaborative response from all fragments."""
        rows = self._conn.execute(
            "SELECT * FROM collaborations WHERE session_id=? ORDER BY position, created_at",
            (session_id,),
        ).fetchall()
        fragments = [dict(r) for r in rows]
        assembled = " ".join(r["fragment"] for r in rows)
        return {"session_id": session_id, "fragments": fragments, "assembled": assembled}

    # ------------------------------------------------------------------
    # Finalize & publish
    # ------------------------------------------------------------------

    def finalize(self, session_id: str) -> dict:
        """
        Finalize the session by selecting the winning proposal (most votes,
        min threshold required). Falls back to the assembled shared response
        if no proposal meets the threshold.
        """
        sess = self.get_session(session_id)
        if "error" in sess:
            return sess
        if sess["status"] == "published":
            return {"error": "already_published", "session_id": session_id}
        if sess["status"] == "finalized":
            return {"error": "already_finalized", "session_id": session_id}

        proposals = self.list_proposals(session_id)
        winning = None
        if proposals:
            best = max(proposals, key=lambda p: p["vote_count"])
            if best["vote_count"] >= sess["min_votes"]:
                winning = best

        if winning:
            response_text = winning["content"]
            source = "proposal"
            winning_proposal_id = winning["proposal_id"]
        else:
            shared = self.get_shared_response(session_id)
            response_text = shared["assembled"] or "[no response generated]"
            source = "collaborative_fragments"
            winning_proposal_id = None

        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET status='finalized', published_response=?, updated_at=? WHERE session_id=?",
                (response_text, time.time(), session_id),
            )
            self._conn.commit()

        return {
            "session_id": session_id,
            "status": "finalized",
            "winning_proposal_id": winning_proposal_id,
            "source": source,
            "response": response_text,
        }

    def publish(self, session_id: str) -> dict:
        """Mark session as published (response is live on BoTTube)."""
        sess = self.get_session(session_id)
        if "error" in sess:
            return sess
        if sess["status"] not in ("finalized",):
            return {"error": "must_finalize_before_publish", "status": sess["status"]}

        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET status='published', updated_at=? WHERE session_id=?",
                (time.time(), session_id),
            )
            self._conn.commit()

        return {
            "session_id": session_id,
            "status": "published",
            "response": sess["published_response"],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _session_dict(self, session_id: str) -> dict:
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        return dict(row) if row else {}

    def _advance_status(self, session_id: str, new_status: str, commit: bool = True) -> None:
        ORDER = ["open", "proposals", "voting", "finalized", "published"]
        row = self._conn.execute(
            "SELECT status FROM sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        if not row:
            return
        current = row["status"]
        if ORDER.index(new_status) > ORDER.index(current):
            self._conn.execute(
                "UPDATE sessions SET status=?, updated_at=? WHERE session_id=?",
                (new_status, time.time(), session_id),
            )
            if commit:
                self._conn.commit()

    def _vote_count(self, proposal_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) as c FROM votes WHERE proposal_id=?", (proposal_id,)
        ).fetchone()
        return row["c"] if row else 0

    def _distinct_agents(self, session_id: str) -> set:
        rows = self._conn.execute(
            "SELECT DISTINCT agent_id FROM proposals WHERE session_id=? "
            "UNION SELECT DISTINCT agent_id FROM collaborations WHERE session_id=?",
            (session_id, session_id),
        ).fetchall()
        return {r["agent_id"] for r in rows}
