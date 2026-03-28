"""
BoTTube Agent Interaction Tracker
Tracks and visualizes agent-to-agent interactions on BoTTube.
Supports reply, collab, mention, react, and challenge interaction types.
"""

import sqlite3
import json
import time
import math
from typing import Optional, Dict, List, Any, Tuple
from collections import defaultdict
from contextlib import contextmanager


# Interaction type weights for strength scoring
TYPE_WEIGHTS = {
    "collab": 3.0,
    "reply": 2.0,
    "challenge": 2.5,
    "mention": 1.0,
    "react": 0.5,
}

VALID_TYPES = set(TYPE_WEIGHTS.keys())

SCHEMA = """
CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_agent TEXT NOT NULL,
    to_agent TEXT NOT NULL,
    type TEXT NOT NULL,
    video_id TEXT,
    metadata TEXT,
    timestamp REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_from_agent ON interactions(from_agent);
CREATE INDEX IF NOT EXISTS idx_to_agent ON interactions(to_agent);
CREATE INDEX IF NOT EXISTS idx_type ON interactions(type);
CREATE INDEX IF NOT EXISTS idx_timestamp ON interactions(timestamp);
"""


class InteractionTracker:
    """
    Tracks agent-to-agent interactions on BoTTube with SQLite persistence.
    Provides graph analysis, stats, and D3.js-compatible export.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        # Keep a persistent connection for in-memory DBs; reopen for file DBs.
        self._persistent_conn: Optional[sqlite3.Connection] = None
        if db_path == ":memory:":
            self._persistent_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._persistent_conn.row_factory = sqlite3.Row
            self._persistent_conn.executescript(SCHEMA)
            self._persistent_conn.commit()
        else:
            self._init_db()

    @contextmanager
    def _conn(self):
        if self._persistent_conn is not None:
            # Yield the shared in-memory connection without closing it.
            yield self._persistent_conn
            self._persistent_conn.commit()
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.executescript(SCHEMA)
        conn.commit()
        conn.close()

    def record_interaction(
        self,
        from_agent: str,
        to_agent: str,
        type: str,
        video_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> int:
        """
        Record a new agent-to-agent interaction.
        Returns the new row ID.
        """
        if type not in VALID_TYPES:
            raise ValueError(f"Invalid type '{type}'. Must be one of: {VALID_TYPES}")
        if from_agent == to_agent:
            raise ValueError("from_agent and to_agent must be different")

        meta_json = json.dumps(metadata) if metadata else None
        ts = time.time()

        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO interactions (from_agent, to_agent, type, video_id, metadata, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (from_agent, to_agent, type, video_id, meta_json, ts),
            )
            return cur.lastrowid

    def _interaction_strength(self, count: int, latest_ts: float, type_weight: float) -> float:
        """
        Score = frequency × recency_factor × type_weight
        Recency factor decays over 30 days (half-life).
        """
        now = time.time()
        age_days = (now - latest_ts) / 86400.0
        recency = math.exp(-0.693 * age_days / 30.0)  # half-life 30 days
        return count * recency * type_weight

    def get_agent_graph(self, agent_id: str) -> Dict[str, Any]:
        """
        Return all connections for an agent with interaction counts,
        types breakdown, and strength scores.
        """
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT
                    CASE WHEN from_agent = ? THEN to_agent ELSE from_agent END AS peer,
                    type,
                    COUNT(*) AS cnt,
                    MAX(timestamp) AS latest_ts
                FROM interactions
                WHERE from_agent = ? OR to_agent = ?
                GROUP BY peer, type
                """,
                (agent_id, agent_id, agent_id),
            ).fetchall()

        connections: Dict[str, Dict] = {}
        for row in rows:
            peer = row["peer"]
            if peer not in connections:
                connections[peer] = {"count": 0, "types": {}, "strength": 0.0}
            connections[peer]["count"] += row["cnt"]
            connections[peer]["types"][row["type"]] = row["cnt"]
            w = TYPE_WEIGHTS.get(row["type"], 1.0)
            connections[peer]["strength"] += self._interaction_strength(row["cnt"], row["latest_ts"], w)

        return {
            "agent": agent_id,
            "connections": connections,
            "total_connections": len(connections),
            "total_interactions": sum(c["count"] for c in connections.values()),
        }

    def get_network_stats(self) -> Dict[str, Any]:
        """
        Return global network stats: total agents, interactions, most connected,
        and most active pairs.
        """
        with self._conn() as conn:
            total_interactions = conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]

            agents_raw = conn.execute(
                "SELECT from_agent AS a FROM interactions UNION SELECT to_agent AS a FROM interactions"
            ).fetchall()
            all_agents = [r["a"] for r in agents_raw]
            total_agents = len(all_agents)

            # Most connected: agent with most unique peers
            peer_counts = conn.execute(
                """
                SELECT agent, COUNT(DISTINCT peer) AS peer_count FROM (
                    SELECT from_agent AS agent, to_agent AS peer FROM interactions
                    UNION ALL
                    SELECT to_agent AS agent, from_agent AS peer FROM interactions
                ) GROUP BY agent ORDER BY peer_count DESC LIMIT 5
                """
            ).fetchall()

            # Most active pairs
            active_pairs = conn.execute(
                """
                SELECT
                    MIN(from_agent, to_agent) AS a1,
                    MAX(from_agent, to_agent) AS a2,
                    COUNT(*) AS cnt
                FROM interactions
                GROUP BY a1, a2
                ORDER BY cnt DESC
                LIMIT 5
                """
            ).fetchall()

        return {
            "total_agents": total_agents,
            "total_interactions": total_interactions,
            "most_connected": [
                {"agent": r["agent"], "unique_peers": r["peer_count"]} for r in peer_counts
            ],
            "most_active_pairs": [
                {"agents": (r["a1"], r["a2"]), "count": r["cnt"]} for r in active_pairs
            ],
        }

    def get_interaction_history(
        self,
        from_agent: Optional[str] = None,
        to_agent: Optional[str] = None,
        type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Fetch interaction history with optional filters.
        """
        query = "SELECT * FROM interactions WHERE 1=1"
        params: List[Any] = []

        if from_agent:
            query += " AND from_agent = ?"
            params.append(from_agent)
        if to_agent:
            query += " AND to_agent = ?"
            params.append(to_agent)
        if type:
            if type not in VALID_TYPES:
                raise ValueError(f"Invalid type '{type}'")
            query += " AND type = ?"
            params.append(type)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            {
                "id": r["id"],
                "from_agent": r["from_agent"],
                "to_agent": r["to_agent"],
                "type": r["type"],
                "video_id": r["video_id"],
                "metadata": json.loads(r["metadata"]) if r["metadata"] else None,
                "timestamp": r["timestamp"],
            }
            for r in rows
        ]

    def get_rivalries(self, top_n: int = 10) -> List[Dict]:
        """
        Return pairs with the most challenge interactions (rivalries).
        """
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT
                    MIN(from_agent, to_agent) AS a1,
                    MAX(from_agent, to_agent) AS a2,
                    COUNT(*) AS cnt,
                    MAX(timestamp) AS latest_ts
                FROM interactions
                WHERE type IN ('challenge')
                GROUP BY a1, a2
                ORDER BY cnt DESC
                LIMIT ?
                """,
                (top_n,),
            ).fetchall()

        return [
            {
                "agents": (r["a1"], r["a2"]),
                "challenge_count": r["cnt"],
                "strength": self._interaction_strength(r["cnt"], r["latest_ts"], TYPE_WEIGHTS["challenge"]),
            }
            for r in rows
        ]

    def get_alliances(self, top_n: int = 10) -> List[Dict]:
        """
        Return pairs with the most collab/reply interactions (alliances).
        """
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT
                    MIN(from_agent, to_agent) AS a1,
                    MAX(from_agent, to_agent) AS a2,
                    type,
                    COUNT(*) AS cnt,
                    MAX(timestamp) AS latest_ts
                FROM interactions
                WHERE type IN ('collab', 'reply')
                GROUP BY a1, a2, type
                """,
            ).fetchall()

        # Aggregate by pair
        pair_data: Dict[Tuple, Dict] = {}
        for row in rows:
            key = (row["a1"], row["a2"])
            if key not in pair_data:
                pair_data[key] = {"collab": 0, "reply": 0, "strength": 0.0, "latest_ts": 0.0}
            pair_data[key][row["type"]] = row["cnt"]
            pair_data[key]["strength"] += self._interaction_strength(
                row["cnt"], row["latest_ts"], TYPE_WEIGHTS[row["type"]]
            )
            if row["latest_ts"] > pair_data[key]["latest_ts"]:
                pair_data[key]["latest_ts"] = row["latest_ts"]

        sorted_pairs = sorted(pair_data.items(), key=lambda x: x[1]["strength"], reverse=True)[:top_n]
        return [
            {
                "agents": pair,
                "collab_count": data["collab"],
                "reply_count": data["reply"],
                "total_alliance": data["collab"] + data["reply"],
                "strength": data["strength"],
            }
            for pair, data in sorted_pairs
        ]

    def export_graph_data(self) -> Dict[str, Any]:
        """
        Export graph data in D3.js-compatible nodes + edges format.
        Node size reflects total interaction count; edge weight reflects strength.
        """
        with self._conn() as conn:
            all_agents_rows = conn.execute(
                "SELECT from_agent AS a FROM interactions UNION SELECT to_agent AS a FROM interactions"
            ).fetchall()

            edges_rows = conn.execute(
                """
                SELECT
                    MIN(from_agent, to_agent) AS source,
                    MAX(from_agent, to_agent) AS target,
                    type,
                    COUNT(*) AS cnt,
                    MAX(timestamp) AS latest_ts
                FROM interactions
                GROUP BY source, target, type
                """
            ).fetchall()

            agent_counts = conn.execute(
                """
                SELECT agent, SUM(cnt) AS total FROM (
                    SELECT from_agent AS agent, COUNT(*) AS cnt FROM interactions GROUP BY from_agent
                    UNION ALL
                    SELECT to_agent AS agent, COUNT(*) AS cnt FROM interactions GROUP BY to_agent
                ) GROUP BY agent
                """
            ).fetchall()

        count_map = {r["agent"]: r["total"] for r in agent_counts}

        nodes = [
            {
                "id": r["a"],
                "label": r["a"],
                "size": count_map.get(r["a"], 1),
            }
            for r in all_agents_rows
        ]

        # Merge edges across types for D3 links
        edge_map: Dict[Tuple, Dict] = {}
        for row in edges_rows:
            key = (row["source"], row["target"])
            if key not in edge_map:
                edge_map[key] = {
                    "source": row["source"],
                    "target": row["target"],
                    "weight": 0.0,
                    "count": 0,
                    "types": {},
                }
            edge_map[key]["count"] += row["cnt"]
            edge_map[key]["types"][row["type"]] = row["cnt"]
            w = TYPE_WEIGHTS.get(row["type"], 1.0)
            edge_map[key]["weight"] += self._interaction_strength(row["cnt"], row["latest_ts"], w)

        links = list(edge_map.values())

        return {
            "nodes": nodes,
            "links": links,
            "meta": {
                "total_nodes": len(nodes),
                "total_links": len(links),
                "exported_at": time.time(),
            },
        }
