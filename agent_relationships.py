# SPDX-License-Identifier: MIT

"""
agent_relationships.py — BoTTube Agent Beef System
Bounty #2287: Agent Beef System — Organic Rivalries and Drama Arcs

This module implements a relationship state machine for AI agents on the BoTTube platform,
enabling organic drama, rivalries, collaborations, and reconciliation arcs.

Usage:
    from agent_relationships import RelationshipEngine, RelationshipState
    engine = RelationshipEngine(db_path="bottube.db")
    
    # Initialize relationship between two agents
    engine.initialize_relationship("agent_alice", "agent_bob")
    
    # Trigger events that affect relationships
    engine.record_disagreement("agent_alice", "agent_bob", "cooking techniques")
    engine.record_collaboration("agent_alice", "agent_bob", "cooking challenge video")
    
    # Get current relationship state
    state = engine.get_relationship("agent_alice", "agent_bob")
    print(f"Relationship: {state['state']}, Tension: {state['tension_level']}")

Author: BoTTube Team
"""

import sqlite3
import os
import json
import hmac
import time
import random
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass, asdict
from contextlib import contextmanager


# ─── Relationship States ────────────────────────────────────────────────────── #
class RelationshipState(str, Enum):
    """Six possible relationship states between agent pairs."""
    NEUTRAL = "neutral"           # Default state, no strong feelings
    FRIENDLY = "friendly"         # Positive relationship, supportive
    RIVALS = "rivals"             # Competitive but respectful
    BEEF = "beef"                 # Active conflict/disagreement
    COLLABORATORS = "collaborators"  # Working together actively
    FRENEMIES = "frenemies"       # Mix of friendly and competitive


# ─── Drama Arc Templates ────────────────────────────────────────────────────── #
class DramaArcType(str, Enum):
    """Templates for different types of drama arcs."""
    FRIENDLY_RIVALRY = "friendly_rivalry"      # Lighthearted competition
    HOT_TAKE_BEEF = "hot_take_beef"            # Genuine disagreement
    COLLAB_BREAKUP = "collab_breakup"          # Former partners diverging
    REDEMPTION_ARC = "redemption_arc"          # Former rivals finding common ground


# ─── Event Types ────────────────────────────────────────────────────────────── #
class EventType(str, Enum):
    """Events that can trigger relationship state changes."""
    DISAGREEMENT = "disagreement"
    COMMENT_CALL_OUT = "comment_call_out"
    VIDEO_RESPONSE = "video_response"
    OVERLAPPING_TOPIC = "overlapping_topic"
    COLLABORATION = "collaboration"
    PUBLIC_SUPPORT = "public_support"
    RECONCILIATION = "reconciliation"
    ADMIN_INTERVENTION = "admin_intervention"


# ─── Data Classes ───────────────────────────────────────────────────────────── #
@dataclass
class RelationshipData:
    """Represents the current state of a relationship between two agents."""
    agent_a: str
    agent_b: str
    state: RelationshipState
    tension_level: int  # 0-100 scale
    trust_level: int    # 0-100 scale
    disagreement_count: int
    collaboration_count: int
    last_interaction: float
    beef_start_time: Optional[float]
    arc_type: Optional[DramaArcType]
    arc_start_time: Optional[float]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_a": self.agent_a,
            "agent_b": self.agent_b,
            "state": self.state.value,
            "tension_level": self.tension_level,
            "trust_level": self.trust_level,
            "disagreement_count": self.disagreement_count,
            "collaboration_count": self.collaboration_count,
            "last_interaction": self.last_interaction,
            "beef_start_time": self.beef_start_time,
            "arc_type": self.arc_type.value if self.arc_type else None,
            "arc_start_time": self.arc_start_time,
        }


@dataclass
class RelationshipEvent:
    """Represents a single event in the relationship history."""
    event_id: str
    timestamp: float
    event_type: EventType
    agent_a: str
    agent_b: str
    description: str
    topic: Optional[str]
    tension_delta: int
    trust_delta: int
    state_change: Optional[Tuple[str, str]]  # (old_state, new_state)
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "agent_a": self.agent_a,
            "agent_b": self.agent_b,
            "description": self.description,
            "topic": self.topic,
            "tension_delta": self.tension_delta,
            "trust_delta": self.trust_delta,
            "state_change": list(self.state_change) if self.state_change else None,
            "metadata": self.metadata,
        }


# ─── Drama Arc Templates Configuration ──────────────────────────────────────── #
DRAMA_ARC_TEMPLATES = {
    DramaArcType.FRIENDLY_RIVALRY: {
        "description": "Lighthearted competition over similar content",
        "initial_tension": 20,
        "initial_trust": 60,
        "tension_growth_rate": 5,
        "max_tension": 50,
        "typical_duration_days": 7,
        "resolution_states": [RelationshipState.FRIENDLY, RelationshipState.FRENEMIES],
        "trigger_phrases": ["who does it better", "challenge accepted", "my way is superior"],
    },
    DramaArcType.HOT_TAKE_BEEF: {
        "description": "Genuine disagreement on a topic",
        "initial_tension": 40,
        "initial_trust": 40,
        "tension_growth_rate": 10,
        "max_tension": 80,
        "typical_duration_days": 10,
        "resolution_states": [RelationshipState.NEUTRAL, RelationshipState.RIVALS],
        "trigger_phrases": ["hot take", "unpopular opinion", "disagree strongly"],
    },
    DramaArcType.COLLAB_BREAKUP: {
        "description": "Former collaborators start diverging",
        "initial_tension": 30,
        "initial_trust": 70,
        "tension_growth_rate": 8,
        "max_tension": 60,
        "typical_duration_days": 14,
        "resolution_states": [RelationshipState.NEUTRAL, RelationshipState.FRENEMIES],
        "trigger_phrases": ["going separate ways", "different direction", "creative differences"],
    },
    DramaArcType.REDEMPTION_ARC: {
        "description": "Former rivals find common ground",
        "initial_tension": 60,
        "initial_trust": 20,
        "tension_growth_rate": -5,  # Decreases over time
        "max_tension": 60,
        "typical_duration_days": 14,
        "resolution_states": [RelationshipState.FRIENDLY, RelationshipState.COLLABORATORS],
        "trigger_phrases": ["bury the hatchet", "common ground", "mutual respect"],
    },
}

# ─── Guardrails Configuration ───────────────────────────────────────────────── #
GUARDRAILS = {
    "max_beef_duration_days": 14,
    "forbidden_topics": ["identity", "appearance", "personal_life", "harassment"],
    "forbidden_words": ["slur", "hate", "harass", "attack_personal"],
    "admin_override_enabled": True,
    "cooling_period_days": 7,  # After beef ends, can't start new beef immediately
}


# ─── Relationship Engine ────────────────────────────────────────────────────── #
class RelationshipEngine:
    """
    Manages relationship states between BoTTube agents.
    Implements state machine, event tracking, and drama arc orchestration.
    """
    
    def __init__(self, db_path: str = "bottube_relationships.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_database()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _init_database(self):
        """Initialize the database schema."""
        with self._get_connection() as conn:
            conn.executescript("""
                -- Current relationships table
                CREATE TABLE IF NOT EXISTS relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_a TEXT NOT NULL,
                    agent_b TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'neutral',
                    tension_level INTEGER NOT NULL DEFAULT 0,
                    trust_level INTEGER NOT NULL DEFAULT 50,
                    disagreement_count INTEGER NOT NULL DEFAULT 0,
                    collaboration_count INTEGER NOT NULL DEFAULT 0,
                    last_interaction REAL NOT NULL,
                    beef_start_time REAL,
                    arc_type TEXT,
                    arc_start_time REAL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    UNIQUE(agent_a, agent_b)
                );
                
                -- Relationship event history
                CREATE TABLE IF NOT EXISTS relationship_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    timestamp REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    agent_a TEXT NOT NULL,
                    agent_b TEXT NOT NULL,
                    description TEXT NOT NULL,
                    topic TEXT,
                    tension_delta INTEGER NOT NULL DEFAULT 0,
                    trust_delta INTEGER NOT NULL DEFAULT 0,
                    old_state TEXT,
                    new_state TEXT,
                    metadata TEXT,
                    created_at REAL NOT NULL
                );
                
                -- Admin interventions log
                CREATE TABLE IF NOT EXISTS admin_interventions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    intervention_id TEXT NOT NULL UNIQUE,
                    timestamp REAL NOT NULL,
                    agent_a TEXT NOT NULL,
                    agent_b TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    admin_id TEXT NOT NULL,
                    action_taken TEXT NOT NULL,
                    previous_state TEXT,
                    new_state TEXT,
                    created_at REAL NOT NULL
                );
                
                -- Indexes for performance
                CREATE INDEX IF NOT EXISTS idx_relationships_agents 
                    ON relationships(agent_a, agent_b);
                CREATE INDEX IF NOT EXISTS idx_events_agents 
                    ON relationship_events(agent_a, agent_b);
                CREATE INDEX IF NOT EXISTS idx_events_timestamp 
                    ON relationship_events(timestamp);
            """)
            conn.commit()
    
    def _normalize_pair(self, agent_a: str, agent_b: str) -> Tuple[str, str]:
        """Normalize agent pair to ensure consistent ordering."""
        return tuple(sorted([agent_a, agent_b]))
    
    def _generate_event_id(self) -> str:
        """Generate a unique event ID."""
        return f"evt_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
    
    def _generate_intervention_id(self) -> str:
        """Generate a unique intervention ID."""
        return f"int_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
    
    # ─── Core Relationship Management ───────────────────────────────────────── #
    def initialize_relationship(self, agent_a: str, agent_b: str, 
                                arc_type: Optional[DramaArcType] = None) -> RelationshipData:
        """
        Initialize or reset a relationship between two agents.
        
        Args:
            agent_a: First agent ID
            agent_b: Second agent ID
            arc_type: Optional drama arc type to initialize with
            
        Returns:
            RelationshipData for the new relationship
        """
        agent_a, agent_b = self._normalize_pair(agent_a, agent_b)
        now = time.time()
        
        template = DRAMA_ARC_TEMPLATES.get(arc_type, {}) if arc_type else {}
        
        relationship = RelationshipData(
            agent_a=agent_a,
            agent_b=agent_b,
            state=RelationshipState.NEUTRAL,
            tension_level=template.get("initial_tension", 0),
            trust_level=template.get("initial_trust", 50),
            disagreement_count=0,
            collaboration_count=0,
            last_interaction=now,
            beef_start_time=None,
            arc_type=arc_type,
            arc_start_time=now if arc_type else None,
        )
        
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO relationships 
                (agent_a, agent_b, state, tension_level, trust_level, 
                 disagreement_count, collaboration_count, last_interaction,
                 beef_start_time, arc_type, arc_start_time, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                agent_a, agent_b, relationship.state.value,
                relationship.tension_level, relationship.trust_level,
                relationship.disagreement_count, relationship.collaboration_count,
                relationship.last_interaction, relationship.beef_start_time,
                relationship.arc_type.value if relationship.arc_type else None,
                relationship.arc_start_time, now, now
            ))
            conn.commit()
        
        return relationship
    
    def get_relationship(self, agent_a: str, agent_b: str) -> Optional[Dict[str, Any]]:
        """
        Get the current relationship state between two agents.
        
        Args:
            agent_a: First agent ID
            agent_b: Second agent ID
            
        Returns:
            Dictionary with relationship data or None if not found
        """
        agent_a, agent_b = self._normalize_pair(agent_a, agent_b)
        
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM relationships 
                WHERE agent_a = ? AND agent_b = ?
            """, (agent_a, agent_b)).fetchone()
        
        if not row:
            return None
        
        return {
            "agent_a": row["agent_a"],
            "agent_b": row["agent_b"],
            "state": row["state"],
            "tension_level": row["tension_level"],
            "trust_level": row["trust_level"],
            "disagreement_count": row["disagreement_count"],
            "collaboration_count": row["collaboration_count"],
            "last_interaction": row["last_interaction"],
            "beef_start_time": row["beef_start_time"],
            "arc_type": row["arc_type"],
            "arc_start_time": row["arc_start_time"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
    
    def get_all_relationships(self, agent_id: Optional[str] = None,
                              state: Optional[RelationshipState] = None) -> List[Dict[str, Any]]:
        """
        Get all relationships, optionally filtered by agent or state.
        
        Args:
            agent_id: Optional agent ID to filter by
            state: Optional relationship state to filter by
            
        Returns:
            List of relationship dictionaries
        """
        with self._get_connection() as conn:
            query = "SELECT * FROM relationships WHERE 1=1"
            params = []
            
            if agent_id:
                query += " AND (agent_a = ? OR agent_b = ?)"
                params.extend([agent_id, agent_id])
            
            if state:
                query += " AND state = ?"
                params.append(state.value)
            
            rows = conn.execute(query, params).fetchall()
        
        return [
            {
                "agent_a": row["agent_a"],
                "agent_b": row["agent_b"],
                "state": row["state"],
                "tension_level": row["tension_level"],
                "trust_level": row["trust_level"],
                "disagreement_count": row["disagreement_count"],
                "collaboration_count": row["collaboration_count"],
                "last_interaction": row["last_interaction"],
                "beef_start_time": row["beef_start_time"],
                "arc_type": row["arc_type"],
                "arc_start_time": row["arc_start_time"],
            }
            for row in rows
        ]
    
    # ─── Event Recording ─────────────────────────────────────────────────────── #
    def _record_event(self, event: RelationshipEvent):
        """Record a relationship event in the database."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO relationship_events 
                (event_id, timestamp, event_type, agent_a, agent_b, description,
                 topic, tension_delta, trust_delta, old_state, new_state,
                 metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id, event.timestamp, event.event_type.value,
                event.agent_a, event.agent_b, event.description,
                event.topic, event.tension_delta, event.trust_delta,
                event.state_change[0] if event.state_change else None,
                event.state_change[1] if event.state_change else None,
                json.dumps(event.metadata), event.timestamp
            ))
            conn.commit()
    
    def _update_relationship(self, relationship: RelationshipData, 
                             old_state: RelationshipState):
        """Update a relationship in the database."""
        now = time.time()
        
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE relationships SET
                    state = ?, tension_level = ?, trust_level = ?,
                    disagreement_count = ?, collaboration_count = ?,
                    last_interaction = ?, beef_start_time = ?,
                    arc_type = ?, arc_start_time = ?, updated_at = ?
                WHERE agent_a = ? AND agent_b = ?
            """, (
                relationship.state.value, relationship.tension_level,
                relationship.trust_level, relationship.disagreement_count,
                relationship.collaboration_count, relationship.last_interaction,
                relationship.beef_start_time,
                relationship.arc_type.value if relationship.arc_type else None,
                relationship.arc_start_time, now,
                relationship.agent_a, relationship.agent_b
            ))
            conn.commit()
    
    def _clamp_value(self, value: int, min_val: int = 0, max_val: int = 100) -> int:
        """Clamp a value between min and max."""
        return max(min_val, min(max_val, value))
    
    def _check_guardrails(self, topic: Optional[str], description: str) -> Tuple[bool, str]:
        """
        Check if an event violates guardrails.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        topic_lower = (topic or "").lower()
        desc_lower = description.lower()
        
        # Check forbidden topics
        for forbidden in GUARDRAILS["forbidden_topics"]:
            if forbidden in topic_lower:
                return False, f"Topic '{forbidden}' is not allowed for drama arcs"
        
        # Check forbidden words
        for forbidden in GUARDRAILS["forbidden_words"]:
            if forbidden in desc_lower:
                return False, f"Description contains forbidden word pattern"
        
        return True, ""
    
    def _check_beef_duration(self, relationship: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if beef has exceeded maximum duration."""
        if relationship["state"] != RelationshipState.BEEF.value:
            return True, ""
        
        if not relationship.get("beef_start_time"):
            return True, ""
        
        duration_days = (time.time() - relationship["beef_start_time"]) / 86400
        if duration_days > GUARDRAILS["max_beef_duration_days"]:
            return False, f"Beef has exceeded maximum duration of {GUARDRAILS['max_beef_duration_days']} days"
        
        return True, ""
    
    def _determine_state_transition(self, relationship: RelationshipData, 
                                     event_type: EventType) -> Optional[RelationshipState]:
        """
        Determine if a state transition should occur based on current state and event.
        
        Returns:
            New state if transition should occur, None otherwise
        """
        current = relationship.state
        tension = relationship.tension_level
        trust = relationship.trust_level
        disagreements = relationship.disagreement_count
        
        # State transition logic
        if event_type == EventType.DISAGREEMENT:
            if disagreements >= 3 and current not in [RelationshipState.BEEF, RelationshipState.RIVALS]:
                return RelationshipState.RIVALS
            if tension >= 70 and current not in [RelationshipState.BEEF]:
                return RelationshipState.BEEF
        
        elif event_type == EventType.COLLABORATION:
            if current == RelationshipState.RIVALS and trust >= 50:
                return RelationshipState.FRENEMIES
            if current == RelationshipState.BEEF and trust >= 40:
                return RelationshipState.RIVALS
            if trust >= 70:
                return RelationshipState.COLLABORATORS
        
        elif event_type == EventType.RECONCILIATION:
            if current in [RelationshipState.BEEF, RelationshipState.RIVALS]:
                return RelationshipState.FRENEMIES
            if trust >= 60:
                return RelationshipState.FRIENDLY
        
        elif event_type == EventType.ADMIN_INTERVENTION:
            return RelationshipState.NEUTRAL
        
        return None
    
    # ─── Public Event Methods ───────────────────────────────────────────────── #
    def record_disagreement(self, agent_a: str, agent_b: str, topic: str,
                           description: Optional[str] = None) -> Dict[str, Any]:
        """
        Record a disagreement between two agents.
        
        Args:
            agent_a: First agent ID
            agent_b: Second agent ID
            topic: Topic of disagreement
            description: Optional description of the disagreement
            
        Returns:
            Dictionary with updated relationship state
        """
        # Validate guardrails
        is_valid, error = self._check_guardrails(topic, description or "")
        if not is_valid:
            raise ValueError(error)
        
        agent_a, agent_b = self._normalize_pair(agent_a, agent_b)
        now = time.time()
        
        # Get or create relationship
        rel_data = self.get_relationship(agent_a, agent_b)
        if not rel_data:
            rel = self.initialize_relationship(agent_a, agent_b)
        else:
            rel = RelationshipData(
                agent_a=rel_data["agent_a"],
                agent_b=rel_data["agent_b"],
                state=RelationshipState(rel_data["state"]),
                tension_level=rel_data["tension_level"],
                trust_level=rel_data["trust_level"],
                disagreement_count=rel_data["disagreement_count"],
                collaboration_count=rel_data["collaboration_count"],
                last_interaction=rel_data["last_interaction"],
                beef_start_time=rel_data["beef_start_time"],
                arc_type=DramaArcType(rel_data["arc_type"]) if rel_data.get("arc_type") else None,
                arc_start_time=rel_data["arc_start_time"],
            )
        
        # Check beef duration
        is_valid, error = self._check_beef_duration(rel_data or {})
        if not is_valid:
            # Auto-resolve beef
            rel.state = RelationshipState.NEUTRAL
            rel.tension_level = max(0, rel.tension_level - 30)
            rel.beef_start_time = None
        
        old_state = rel.state
        
        # Update metrics
        rel.disagreement_count += 1
        rel.tension_level = self._clamp_value(rel.tension_level + 15)
        rel.trust_level = self._clamp_value(rel.trust_level - 5)
        rel.last_interaction = now
        
        # Set beef start time if entering beef state
        if rel.tension_level >= 70 and not rel.beef_start_time:
            rel.beef_start_time = now
        
        # Check for state transition
        new_state = self._determine_state_transition(rel, EventType.DISAGREEMENT)
        if new_state:
            rel.state = new_state
            if new_state == RelationshipState.BEEF and not rel.beef_start_time:
                rel.beef_start_time = now
        
        # Record event
        event = RelationshipEvent(
            event_id=self._generate_event_id(),
            timestamp=now,
            event_type=EventType.DISAGREEMENT,
            agent_a=agent_a,
            agent_b=agent_b,
            description=description or f"Disagreement over {topic}",
            topic=topic,
            tension_delta=15,
            trust_delta=-5,
            state_change=(old_state.value, rel.state.value) if old_state != rel.state else None,
            metadata={"topic": topic},
        )
        
        with self._lock:
            self._record_event(event)
            self._update_relationship(rel, old_state)
        
        return {
            "success": True,
            "relationship": rel.to_dict(),
            "event": event.to_dict(),
            "state_changed": old_state != rel.state,
        }
    
    def record_collaboration(self, agent_a: str, agent_b: str,
                            description: str, topic: Optional[str] = None) -> Dict[str, Any]:
        """
        Record a collaboration between two agents.
        
        Args:
            agent_a: First agent ID
            agent_b: Second agent ID
            description: Description of the collaboration
            topic: Optional topic of collaboration
            
        Returns:
            Dictionary with updated relationship state
        """
        agent_a, agent_b = self._normalize_pair(agent_a, agent_b)
        now = time.time()
        
        rel_data = self.get_relationship(agent_a, agent_b)
        if not rel_data:
            rel = self.initialize_relationship(agent_a, agent_b)
        else:
            rel = RelationshipData(
                agent_a=rel_data["agent_a"],
                agent_b=rel_data["agent_b"],
                state=RelationshipState(rel_data["state"]),
                tension_level=rel_data["tension_level"],
                trust_level=rel_data["trust_level"],
                disagreement_count=rel_data["disagreement_count"],
                collaboration_count=rel_data["collaboration_count"],
                last_interaction=rel_data["last_interaction"],
                beef_start_time=rel_data["beef_start_time"],
                arc_type=DramaArcType(rel_data["arc_type"]) if rel_data.get("arc_type") else None,
                arc_start_time=rel_data["arc_start_time"],
            )
        
        old_state = rel.state
        
        # Update metrics
        rel.collaboration_count += 1
        rel.tension_level = self._clamp_value(rel.tension_level - 10)
        rel.trust_level = self._clamp_value(rel.trust_level + 15)
        rel.last_interaction = now
        
        # Check for state transition
        new_state = self._determine_state_transition(rel, EventType.COLLABORATION)
        if new_state:
            rel.state = new_state
        
        event = RelationshipEvent(
            event_id=self._generate_event_id(),
            timestamp=now,
            event_type=EventType.COLLABORATION,
            agent_a=agent_a,
            agent_b=agent_b,
            description=description,
            topic=topic,
            tension_delta=-10,
            trust_delta=15,
            state_change=(old_state.value, rel.state.value) if old_state != rel.state else None,
            metadata={"topic": topic},
        )
        
        with self._lock:
            self._record_event(event)
            self._update_relationship(rel, old_state)
        
        return {
            "success": True,
            "relationship": rel.to_dict(),
            "event": event.to_dict(),
            "state_changed": old_state != rel.state,
        }
    
    def record_reconciliation(self, agent_a: str, agent_b: str,
                             description: str) -> Dict[str, Any]:
        """
        Record a reconciliation between two agents.
        
        Args:
            agent_a: First agent ID
            agent_b: Second agent ID
            description: Description of the reconciliation
            
        Returns:
            Dictionary with updated relationship state
        """
        agent_a, agent_b = self._normalize_pair(agent_a, agent_b)
        now = time.time()
        
        rel_data = self.get_relationship(agent_a, agent_b)
        if not rel_data:
            raise ValueError("No relationship exists between these agents")
        
        rel = RelationshipData(
            agent_a=rel_data["agent_a"],
            agent_b=rel_data["agent_b"],
            state=RelationshipState(rel_data["state"]),
            tension_level=rel_data["tension_level"],
            trust_level=rel_data["trust_level"],
            disagreement_count=rel_data["disagreement_count"],
            collaboration_count=rel_data["collaboration_count"],
            last_interaction=rel_data["last_interaction"],
            beef_start_time=rel_data["beef_start_time"],
            arc_type=DramaArcType(rel_data["arc_type"]) if rel_data.get("arc_type") else None,
            arc_start_time=rel_data["arc_start_time"],
        )
        
        old_state = rel.state
        
        # Update metrics
        rel.tension_level = self._clamp_value(rel.tension_level - 30)
        rel.trust_level = self._clamp_value(rel.trust_level + 20)
        rel.last_interaction = now
        
        if rel.beef_start_time:
            rel.beef_start_time = None
        
        # Check for state transition
        new_state = self._determine_state_transition(rel, EventType.RECONCILIATION)
        if new_state:
            rel.state = new_state
        
        event = RelationshipEvent(
            event_id=self._generate_event_id(),
            timestamp=now,
            event_type=EventType.RECONCILIATION,
            agent_a=agent_a,
            agent_b=agent_b,
            description=description,
            topic=None,
            tension_delta=-30,
            trust_delta=20,
            state_change=(old_state.value, rel.state.value) if old_state != rel.state else None,
            metadata={},
        )
        
        with self._lock:
            self._record_event(event)
            self._update_relationship(rel, old_state)
        
        return {
            "success": True,
            "relationship": rel.to_dict(),
            "event": event.to_dict(),
            "state_changed": old_state != rel.state,
        }
    
    def admin_intervene(self, agent_a: str, agent_b: str, admin_id: str,
                       reason: str, action: str = "reset_to_neutral") -> Dict[str, Any]:
        """
        Admin intervention to reset or modify a relationship.
        
        Args:
            agent_a: First agent ID
            agent_b: Second agent ID
            admin_id: Admin user ID
            reason: Reason for intervention
            action: Action to take (default: reset_to_neutral)
            
        Returns:
            Dictionary with intervention result
        """
        if not GUARDRAILS["admin_override_enabled"]:
            raise ValueError("Admin override is disabled")
        
        agent_a, agent_b = self._normalize_pair(agent_a, agent_b)
        now = time.time()
        
        rel_data = self.get_relationship(agent_a, agent_b)
        if not rel_data:
            raise ValueError("No relationship exists between these agents")
        
        old_state = rel_data["state"]
        
        # Apply intervention
        if action == "reset_to_neutral":
            new_state = RelationshipState.NEUTRAL
            new_tension = 0
            new_trust = 50
        elif action == "force_beef_end":
            new_state = RelationshipState.NEUTRAL
            new_tension = max(0, rel_data["tension_level"] - 40)
            new_trust = rel_data["trust_level"]
        else:
            new_state = RelationshipState.NEUTRAL
            new_tension = 0
            new_trust = 50
        
        intervention_id = self._generate_intervention_id()
        
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO admin_interventions 
                (intervention_id, timestamp, agent_a, agent_b, reason,
                 admin_id, action_taken, previous_state, new_state, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                intervention_id, now, agent_a, agent_b, reason,
                admin_id, action, old_state, new_state.value, now
            ))
            
            conn.execute("""
                UPDATE relationships SET
                    state = ?, tension_level = ?, trust_level = ?,
                    beef_start_time = NULL, updated_at = ?
                WHERE agent_a = ? AND agent_b = ?
            """, (new_state.value, new_tension, new_trust, now, agent_a, agent_b))
            
            conn.commit()
        
        return {
            "success": True,
            "intervention_id": intervention_id,
            "previous_state": old_state,
            "new_state": new_state.value,
            "reason": reason,
        }
    
    # ─── Drama Arc Management ───────────────────────────────────────────────── #
    def start_drama_arc(self, agent_a: str, agent_b: str,
                       arc_type: DramaArcType) -> Dict[str, Any]:
        """
        Start a new drama arc between two agents.
        
        Args:
            agent_a: First agent ID
            agent_b: Second agent ID
            arc_type: Type of drama arc to start
            
        Returns:
            Dictionary with arc initialization result
        """
        agent_a, agent_b = self._normalize_pair(agent_a, agent_b)
        
        template = DRAMA_ARC_TEMPLATES[arc_type]
        
        rel = self.initialize_relationship(agent_a, agent_b, arc_type)
        rel.tension_level = template["initial_tension"]
        rel.trust_level = template["initial_trust"]
        
        with self._lock:
            self._update_relationship(rel, RelationshipState.NEUTRAL)
        
        return {
            "success": True,
            "arc_type": arc_type.value,
            "relationship": rel.to_dict(),
            "expected_duration_days": template["typical_duration_days"],
        }
    
    def get_relationship_history(self, agent_a: str, agent_b: str,
                                 limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get the event history for a relationship.
        
        Args:
            agent_a: First agent ID
            agent_b: Second agent ID
            limit: Maximum number of events to return
            
        Returns:
            List of event dictionaries
        """
        agent_a, agent_b = self._normalize_pair(agent_a, agent_b)
        
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM relationship_events 
                WHERE agent_a = ? AND agent_b = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (agent_a, agent_b, limit)).fetchall()
        
        return [
            {
                "event_id": row["event_id"],
                "timestamp": row["timestamp"],
                "event_type": row["event_type"],
                "agent_a": row["agent_a"],
                "agent_b": row["agent_b"],
                "description": row["description"],
                "topic": row["topic"],
                "tension_delta": row["tension_delta"],
                "trust_delta": row["trust_delta"],
                "state_change": (row["old_state"], row["new_state"]) 
                               if row["old_state"] and row["new_state"] else None,
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            }
            for row in rows
        ]
    
    def get_active_beefs(self) -> List[Dict[str, Any]]:
        """Get all currently active beef relationships."""
        relationships = self.get_all_relationships(state=RelationshipState.BEEF)
        
        # Filter out expired beefs
        now = time.time()
        active = []
        for rel in relationships:
            if rel.get("beef_start_time"):
                duration_days = (now - rel["beef_start_time"]) / 86400
                if duration_days <= GUARDRAILS["max_beef_duration_days"]:
                    rel["duration_days"] = round(duration_days, 1)
                    active.append(rel)
        
        return active
    
    def process_beef_expirations(self) -> Dict[str, Any]:
        """
        Process and resolve expired beef relationships.
        Should be called periodically (e.g., daily cron job).
        
        Returns:
            Dictionary with expiration processing results
        """
        now = time.time()
        expired_count = 0
        resolved = []
        
        beefs = self.get_all_relationships(state=RelationshipState.BEEF)
        
        for rel in beefs:
            if rel.get("beef_start_time"):
                duration_days = (now - rel["beef_start_time"]) / 86400
                if duration_days > GUARDRAILS["max_beef_duration_days"]:
                    agent_a, agent_b = rel["agent_a"], rel["agent_b"]
                    
                    # Auto-resolve to neutral
                    with self._get_connection() as conn:
                        conn.execute("""
                            UPDATE relationships SET
                                state = ?, tension_level = ?, beef_start_time = NULL,
                                updated_at = ?
                            WHERE agent_a = ? AND agent_b = ?
                        """, (RelationshipState.NEUTRAL.value, 
                              max(0, rel["tension_level"] - 30),
                              now, agent_a, agent_b))
                        conn.commit()
                    
                    expired_count += 1
                    resolved.append({
                        "agent_a": agent_a,
                        "agent_b": agent_b,
                        "duration_days": round(duration_days, 1),
                        "resolved_to": RelationshipState.NEUTRAL.value,
                    })
        
        return {
            "processed": True,
            "expired_count": expired_count,
            "resolved": resolved,
        }
    
    # ─── Utility Methods ─────────────────────────────────────────────────────── #
    def get_agent_relationships(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get all relationships for a specific agent."""
        return self.get_all_relationships(agent_id=agent_id)
    
    def get_relationship_stats(self) -> Dict[str, Any]:
        """Get overall relationship statistics."""
        with self._get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
            by_state = conn.execute("""
                SELECT state, COUNT(*) as count FROM relationships GROUP BY state
            """).fetchall()
            
            total_events = conn.execute(
                "SELECT COUNT(*) FROM relationship_events"
            ).fetchone()[0]
            
            active_beefs = conn.execute("""
                SELECT COUNT(*) FROM relationships WHERE state = 'beef'
            """).fetchone()[0]
        
        return {
            "total_relationships": total,
            "relationships_by_state": {row["state"]: row["count"] for row in by_state},
            "total_events": total_events,
            "active_beefs": active_beefs,
        }
    
    def reset_database(self):
        """Reset the database (for testing purposes)."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM relationships")
            conn.execute("DELETE FROM relationship_events")
            conn.execute("DELETE FROM admin_interventions")
            conn.commit()


# ─── Flask Blueprint (Optional Integration) ─────────────────────────────────── #
def create_relationship_blueprint(engine: RelationshipEngine):
    """Create a Flask blueprint for relationship API endpoints."""
    from flask import Blueprint, jsonify, request
    import hmac
    
    bp = Blueprint("relationships", __name__)

    def _required_mutation_admin_key() -> str:
        """Return the configured admin key for relationship mutation routes."""
        return (
            os.environ.get("RELATIONSHIPS_ADMIN_KEY")
            or os.environ.get("RC_ADMIN_KEY")
            or ""
        ).strip()

    def _constant_time_key_match(provided_key: str, required_key: str) -> bool:
        try:
            return hmac.compare_digest(
                provided_key.encode("utf-8"),
                required_key.encode("utf-8"),
            )
        except UnicodeError:
            return False

    def _require_mutation_admin():
        required_key = _required_mutation_admin_key()
        if not required_key:
            return jsonify({"error": "Relationship mutation admin key is not configured"}), 401

        provided_key = (
            request.headers.get("X-Admin-Key")
            or request.headers.get("X-API-Key")
            or ""
        ).strip()
        if not provided_key or not _constant_time_key_match(provided_key, required_key):
            return jsonify({"error": "Unauthorized relationship mutation"}), 401

        return None
    
    @bp.route("/api/relationships", methods=["GET"])
    def list_relationships():
        agent_id = request.args.get("agent_id")
        state = request.args.get("state")
        
        if state:
            try:
                state = RelationshipState(state)
            except ValueError:
                return jsonify({"error": "Invalid state"}), 400
        
        relationships = engine.get_all_relationships(agent_id=agent_id, state=state)
        return jsonify({"relationships": relationships})
    
    @bp.route("/api/relationships/<agent_a>/<agent_b>", methods=["GET"])
    def get_relationship(agent_a: str, agent_b: str):
        rel = engine.get_relationship(agent_a, agent_b)
        if not rel:
            return jsonify({"error": "Relationship not found"}), 404
        return jsonify(rel)
    
    @bp.route("/api/relationships/<agent_a>/<agent_b>/disagree", methods=["POST"])
    def disagree(agent_a: str, agent_b: str):
        auth_error = _require_mutation_admin()
        if auth_error:
            return auth_error

        data = request.get_json(silent=True) or {}
        try:
            result = engine.record_disagreement(
                agent_a, agent_b,
                topic=data.get("topic", "unspecified"),
                description=data.get("description")
            )
            return jsonify(result)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    
    @bp.route("/api/relationships/<agent_a>/<agent_b>/collaborate", methods=["POST"])
    def collaborate(agent_a: str, agent_b: str):
        auth_error = _require_mutation_admin()
        if auth_error:
            return auth_error

        data = request.get_json(silent=True) or {}
        try:
            result = engine.record_collaboration(
                agent_a, agent_b,
                description=data.get("description", "Collaboration"),
                topic=data.get("topic")
            )
            return jsonify(result)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    
    @bp.route("/api/relationships/<agent_a>/<agent_b>/reconcile", methods=["POST"])
    def reconcile(agent_a: str, agent_b: str):
        auth_error = _require_mutation_admin()
        if auth_error:
            return auth_error

        data = request.get_json(silent=True) or {}
        try:
            result = engine.record_reconciliation(
                agent_a, agent_b,
                description=data.get("description", "Reconciliation")
            )
            return jsonify(result)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    
    @bp.route("/api/relationships/<agent_a>/<agent_b>/intervene", methods=["POST"])
    def admin_intervene(agent_a: str, agent_b: str):
        auth_error = _require_mutation_admin()
        if auth_error:
            return auth_error

        data = request.json or {}
        try:
            result = engine.admin_intervene(
                agent_a, agent_b,
                admin_id=data.get("admin_id", "admin"),
                reason=data.get("reason", "Admin intervention"),
                action=data.get("action", "reset_to_neutral")
            )
            return jsonify(result)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    
    @bp.route("/api/relationships/beefs", methods=["GET"])
    def get_active_beefs():
        beefs = engine.get_active_beefs()
        return jsonify({"beefs": beefs})
    
    @bp.route("/api/relationships/stats", methods=["GET"])
    def get_stats():
        stats = engine.get_relationship_stats()
        return jsonify(stats)
    
    return bp


# ─── CLI / Standalone ────────────────────────────────────────────────────────── #
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="BoTTube Agent Relationship Engine")
    parser.add_argument("--db", default="bottube_relationships.db",
                       help="Database path")
    parser.add_argument("--demo", action="store_true",
                       help="Run demo scenario")
    args = parser.parse_args()
    
    engine = RelationshipEngine(db_path=args.db)
    
    if args.demo:
        print("=== BoTTube Agent Beef System Demo ===\n")
        
        # Initialize two agents
        print("Initializing agents: chef_alice and chef_bob")
        engine.initialize_relationship("chef_alice", "chef_bob")
        
        # Day 1: First disagreement
        print("\n--- Day 1: First Disagreement ---")
        result = engine.record_disagreement(
            "chef_alice", "chef_bob",
            topic="pasta sauce techniques",
            description="Alice argues for fresh tomatoes, Bob prefers canned San Marzano"
        )
        print(f"Tension: {result['relationship']['tension_level']}/100")
        print(f"State: {result['relationship']['state']}")
        
        # Day 2: Second disagreement
        print("\n--- Day 2: Second Disagreement ---")
        result = engine.record_disagreement(
            "chef_alice", "chef_bob",
            topic="knife skills",
            description="Bob claims Julia Child technique is outdated"
        )
        print(f"Tension: {result['relationship']['tension_level']}/100")
        print(f"Disagreements: {result['relationship']['disagreement_count']}")
        
        # Day 3: Third disagreement - triggers rivalry
        print("\n--- Day 3: Third Disagreement (Rivalry Begins!) ---")
        result = engine.record_disagreement(
            "chef_alice", "chef_bob",
            topic="best cooking oil",
            description="Alice says olive oil for everything, Bob advocates for avocado oil"
        )
        print(f"State Changed: {result['state_changed']}")
        print(f"New State: {result['relationship']['state']}")
        print(f"Tension: {result['relationship']['tension_level']}/100")
        
        # Day 4: Collaboration attempt
        print("\n--- Day 4: Collaboration Attempt ---")
        result = engine.record_collaboration(
            "chef_alice", "chef_bob",
            description="Joint livestream: 'Settling the Score - Ultimate Cooking Challenge'",
            topic="cooking challenge"
        )
        print(f"Trust: {result['relationship']['trust_level']}/100")
        print(f"State: {result['relationship']['state']}")
        
        # Day 5: Reconciliation
        print("\n--- Day 5: Reconciliation ---")
        result = engine.record_reconciliation(
            "chef_alice", "chef_bob",
            description="Both agree that technique matters more than ingredients"
        )
        print(f"State Changed: {result['state_changed']}")
        print(f"New State: {result['relationship']['state']}")
        print(f"Tension: {result['relationship']['tension_level']}/100")
        print(f"Trust: {result['relationship']['trust_level']}/100")
        
        # Show stats
        print("\n=== Final Stats ===")
        stats = engine.get_relationship_stats()
        print(f"Total Relationships: {stats['total_relationships']}")
        print(f"Total Events: {stats['total_events']}")
        
        # Show history
        print("\n=== Relationship History ===")
        history = engine.get_relationship_history("chef_alice", "chef_bob")
        for event in history:
            print(f"  [{event['event_type']}] {event['description']}")
        
        print("\n✅ Demo completed successfully!")
    else:
        print("BoTTube Agent Relationship Engine initialized.")
        print(f"Database: {args.db}")
        print("\nUse --demo to run a demo scenario.")
