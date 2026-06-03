# SPDX-License-Identifier: MIT

"""
drama_arc_engine.py — BoTTube Drama Arc Engine
Bounty #2287: Agent Beef System — Organic Rivalries and Drama Arcs

This module provides the drama arc engine that orchestrates multi-day
drama scenarios between agents, including automatic progression and
resolution of arcs.

Usage:
    from drama_arc_engine import DramaArcEngine
    from agent_relationships import RelationshipEngine
    
    rel_engine = RelationshipEngine()
    arc_engine = DramaArcEngine(rel_engine)
    
    # Start a friendly rivalry arc
    arc_engine.start_arc("agent_alice", "agent_bob", "friendly_rivalry")
    
    # Progress the arc automatically
    arc_engine.progress_arc("agent_alice", "agent_bob")
    
    # Get arc status
    status = arc_engine.get_arc_status("agent_alice", "agent_bob")
"""

import time
import random
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass

from agent_relationships import (
    RelationshipEngine, RelationshipState, DramaArcType, EventType,
    DRAMA_ARC_TEMPLATES, GUARDRAILS
)


# ─── Arc Phase Enum ─────────────────────────────────────────────────────────── #
class ArcPhase(str, Enum):
    """Phases of a drama arc."""
    INITIATION = "initiation"       # Arc just started
    ESCALATION = "escalation"       # Tension building
    CLIMAX = "climax"               # Peak conflict
    RESOLUTION = "resolution"       # Winding down
    COMPLETED = "completed"         # Arc finished


# ─── Arc Event Templates ────────────────────────────────────────────────────── #
ARC_EVENT_TEMPLATES = {
    DramaArcType.FRIENDLY_RIVALRY: {
        ArcPhase.INITIATION: [
            ("challenge_issued", "challenges the other to a competition", 10, -2),
            ("comparison_made", "compares content quality playfully", 5, 0),
        ],
        ArcPhase.ESCALATION: [
            ("one_upped", "creates better video on same topic", 15, -5),
            ("subtle_diss", "makes subtle dig in video description", 10, -3),
            ("fan_debate", "fans start debating in comments", 8, 0),
        ],
        ArcPhase.CLIMAX: [
            ("direct_challenge", "issues direct challenge video", 20, -10),
            ("collab_challenge", "challenges to collaboration video", 15, 5),
        ],
        ArcPhase.RESOLUTION: [
            ("mutual_respect", "acknowledges other's skills", -15, 15),
            ("agree_disagree", "agree to disagree respectfully", -10, 10),
        ],
    },
    DramaArcType.HOT_TAKE_BEEF: {
        ArcPhase.INITIATION: [
            ("hot_take_posted", "posts controversial hot take", 20, -10),
            ("disagree_publicly", "publicly disagrees with statement", 15, -5),
        ],
        ArcPhase.ESCALATION: [
            ("response_video", "creates response video", 20, -10),
            ("evidence_presented", "presents evidence against claim", 15, -5),
            ("community_picks_sides", "community starts picking sides", 10, -5),
        ],
        ArcPhase.CLIMAX: [
            ("heated_exchange", "heated comment exchange", 25, -15),
            ("ultimatum_issued", "issues ultimatum or challenge", 20, -10),
        ],
        ArcPhase.RESOLUTION: [
            ("common_ground_found", "finds unexpected common ground", -20, 20),
            ("respectful_agreement", "agrees to disagree respectfully", -15, 15),
        ],
    },
    DramaArcType.COLLAB_BREAKUP: {
        ArcPhase.INITIATION: [
            ("creative_difference", "expresses different creative vision", 15, -10),
            ("separate_projects", "announces separate project", 10, -5),
        ],
        ArcPhase.ESCALATION: [
            ("public_statement", "makes public statement about split", 20, -15),
            ("fans_choose_sides", "fans debate who's at fault", 15, -10),
        ],
        ArcPhase.CLIMAX: [
            ("harsh_words", "exchange harsh words publicly", 25, -20),
            ("final_video", "releases final statement video", 20, -10),
        ],
        ArcPhase.RESOLUTION: [
            ("maturity_shown", "shows maturity in follow-up", -15, 15),
            ("well_wishes", "wishes each other well", -10, 20),
        ],
    },
    DramaArcType.REDEMPTION_ARC: {
        ArcPhase.INITIATION: [
            ("olive_branch", "extends olive branch publicly", -10, 10),
            ("acknowledge_past", "acknowledges past mistakes", -5, 15),
        ],
        ArcPhase.ESCALATION: [
            ("positive_mention", "mentions other positively", -15, 15),
            ("shared_interest", "discovers shared interest", -10, 10),
        ],
        ArcPhase.CLIMAX: [
            ("collab_offer", "offers collaboration", -15, 20),
            ("public_reconciliation", "public reconciliation moment", -20, 25),
        ],
        ArcPhase.RESOLUTION: [
            ("new_friendship", "forms new friendship", -10, 20),
            ("ongoing_collab", "starts ongoing collaboration", -15, 25),
        ],
    },
}


# ─── Arc Status Data Class ──────────────────────────────────────────────────── #
@dataclass
class ArcStatus:
    """Status of an active drama arc."""
    agent_a: str
    agent_b: str
    arc_type: DramaArcType
    phase: ArcPhase
    start_time: float
    last_progress: float
    events_triggered: int
    expected_duration_days: float
    is_expired: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_a": self.agent_a,
            "agent_b": self.agent_b,
            "arc_type": self.arc_type.value,
            "phase": self.phase.value,
            "start_time": self.start_time,
            "last_progress": self.last_progress,
            "events_triggered": self.events_triggered,
            "expected_duration_days": self.expected_duration_days,
            "is_expired": self.is_expired,
            "days_elapsed": round((time.time() - self.start_time) / 86400, 1),
        }


# ─── Drama Arc Engine ───────────────────────────────────────────────────────── #
class DramaArcEngine:
    """
    Orchestrates drama arcs between agents, managing progression
    through phases and automatic event triggering.
    """
    
    def __init__(self, relationship_engine: RelationshipEngine,
                 auto_progress: bool = False):
        """
        Initialize the drama arc engine.
        
        Args:
            relationship_engine: RelationshipEngine instance
            auto_progress: If True, automatically progress arcs over time
        """
        self.rel_engine = relationship_engine
        self.auto_progress = auto_progress
        self._active_arcs: Dict[str, ArcStatus] = {}
        self._arc_lock = threading.Lock()
        self._event_callbacks: List[Callable] = []
    
    def _get_arc_key(self, agent_a: str, agent_b: str) -> str:
        """Generate a unique key for an agent pair."""
        return ":".join(sorted([agent_a, agent_b]))
    
    def _determine_phase(self, relationship: Dict[str, Any],
                         arc_type: DramaArcType) -> ArcPhase:
        """Determine the current phase based on relationship state."""
        tension = relationship.get("tension_level", 0)
        trust = relationship.get("trust_level", 50)
        state = relationship.get("state", "neutral")
        arc_start_time = relationship.get("arc_start_time")

        template = DRAMA_ARC_TEMPLATES.get(arc_type, {})
        max_tension = template.get("max_tension", 80)

        # Check if arc just started - always start at initiation
        if arc_start_time:
            days_elapsed = (time.time() - arc_start_time) / 86400
            if days_elapsed < 0.1:  # Less than ~2.5 hours
                return ArcPhase.INITIATION

        # Check for completion
        if state in [RelationshipState.FRIENDLY.value,
                     RelationshipState.COLLABORATORS.value]:
            if tension < 30 and trust > 60:
                return ArcPhase.COMPLETED

        # Determine phase based on tension and relationship state
        if state in [RelationshipState.BEEF.value, RelationshipState.RIVALS.value]:
            if tension >= max_tension * 0.8:
                return ArcPhase.CLIMAX
            elif tension >= max_tension * 0.5:
                return ArcPhase.ESCALATION
            else:
                return ArcPhase.INITIATION
        elif state == RelationshipState.FRENEMIES.value:
            return ArcPhase.RESOLUTION
        elif state == RelationshipState.NEUTRAL.value:
            # Neutral with an arc type means arc is starting
            return ArcPhase.INITIATION
        else:
            return ArcPhase.COMPLETED
    
    def start_arc(self, agent_a: str, agent_b: str, 
                  arc_type: DramaArcType) -> Dict[str, Any]:
        """
        Start a new drama arc between two agents.
        
        Args:
            agent_a: First agent ID
            agent_b: Second agent ID
            arc_type: Type of drama arc
            
        Returns:
            Dictionary with arc initialization result
        """
        arc_key = self._get_arc_key(agent_a, agent_b)
        with self._arc_lock:
            if arc_key in self._active_arcs:
                existing = self._active_arcs[arc_key]
                return {
                    "success": True,
                    "arc": existing.to_dict(),
                    "relationship": self.rel_engine.get_relationship(agent_a, agent_b),
                    "idempotent": True,
                }

            result = self.rel_engine.start_drama_arc(agent_a, agent_b, arc_type)
            if not result["success"]:
                return result

            template = DRAMA_ARC_TEMPLATES[arc_type]
            now = time.time()

            arc_status = ArcStatus(
                agent_a=agent_a,
                agent_b=agent_b,
                arc_type=arc_type,
                phase=ArcPhase.INITIATION,
                start_time=now,
                last_progress=now,
                events_triggered=0,
                expected_duration_days=template["typical_duration_days"],
                is_expired=False,
            )

            self._active_arcs[arc_key] = arc_status
            relationship = result["relationship"]

        # Notify callbacks outside the lock so callback code cannot block arc creation.
        self._notify_callbacks("arc_started", arc_status.to_dict())

        return {
            "success": True,
            "arc": arc_status.to_dict(),
            "relationship": relationship,
        }

    def progress_arc(self, agent_a: str, agent_b: str,
                    force_event: Optional[str] = None) -> Dict[str, Any]:
        """
        Progress a drama arc by triggering the next event.
        
        Args:
            agent_a: First agent ID
            agent_b: Second agent ID
            force_event: Optional specific event to trigger
            
        Returns:
            Dictionary with progression result
        """
        arc_key = self._get_arc_key(agent_a, agent_b)
        
        if arc_key not in self._active_arcs:
            # Try to reconstruct from relationship
            rel = self.rel_engine.get_relationship(agent_a, agent_b)
            if not rel or not rel.get("arc_type"):
                return {"success": False, "error": "No active arc found"}
            
            arc_type = DramaArcType(rel["arc_type"])
            phase = self._determine_phase(rel, arc_type)
            
            template = DRAMA_ARC_TEMPLATES.get(arc_type, {})
            now = time.time()
            
            arc_status = ArcStatus(
                agent_a=rel["agent_a"],
                agent_b=rel["agent_b"],
                arc_type=arc_type,
                phase=phase,
                start_time=rel.get("arc_start_time", now),
                last_progress=now,
                events_triggered=0,
                expected_duration_days=template.get("typical_duration_days", 7),
                is_expired=False,
            )
            self._active_arcs[arc_key] = arc_status
        
        arc_status = self._active_arcs[arc_key]
        
        # Check for expiration
        days_elapsed = (time.time() - arc_status.start_time) / 86400
        if days_elapsed > arc_status.expected_duration_days * 2:
            arc_status.is_expired = True
            return {
                "success": False,
                "error": "Arc has expired",
                "arc": arc_status.to_dict(),
            }
        
        # Update phase
        rel = self.rel_engine.get_relationship(agent_a, agent_b)
        arc_status.phase = self._determine_phase(rel, arc_status.arc_type)
        
        if arc_status.phase == ArcPhase.COMPLETED:
            del self._active_arcs[arc_key]
            return {
                "success": True,
                "completed": True,
                "arc": arc_status.to_dict(),
                "message": "Arc completed successfully",
            }
        
        # Select and trigger event
        event_templates = ARC_EVENT_TEMPLATES.get(arc_status.arc_type, {}).get(
            arc_status.phase, []
        )
        
        if not event_templates:
            return {
                "success": False,
                "error": "No events available for current phase",
            }
        
        if force_event:
            event_template = next(
                (e for e in event_templates if e[0] == force_event),
                random.choice(event_templates)
            )
        else:
            event_template = random.choice(event_templates)
        
        event_name, description, tension_delta, trust_delta = event_template
        
        # Trigger the event based on type
        if tension_delta > 0:
            result = self.rel_engine.record_disagreement(
                agent_a, agent_b,
                topic=event_name,
                description=description
            )
        elif tension_delta < 0:
            if "collab" in event_name.lower() or "reconcil" in event_name.lower():
                result = self.rel_engine.record_collaboration(
                    agent_a, agent_b,
                    description=description
                )
            else:
                result = self.rel_engine.record_reconciliation(
                    agent_a, agent_b,
                    description=description
                )
        else:
            # Neutral event - use collaboration for positive trust
            result = self.rel_engine.record_collaboration(
                agent_a, agent_b,
                description=description
            )
        
        arc_status.events_triggered += 1
        arc_status.last_progress = time.time()
        
        # Notify callbacks
        self._notify_callbacks("arc_progressed", {
            "arc": arc_status.to_dict(),
            "event": event_name,
            "result": result,
        })
        
        return {
            "success": True,
            "event_triggered": event_name,
            "event_description": description,
            "phase": arc_status.phase.value,
            "relationship": result.get("relationship"),
            "arc": arc_status.to_dict(),
        }
    
    def get_arc_status(self, agent_a: str, agent_b: str) -> Optional[Dict[str, Any]]:
        """Get the status of an active arc."""
        arc_key = self._get_arc_key(agent_a, agent_b)
        
        if arc_key not in self._active_arcs:
            # Try to reconstruct from relationship
            rel = self.rel_engine.get_relationship(agent_a, agent_b)
            if not rel or not rel.get("arc_type"):
                return None
            
            arc_type = DramaArcType(rel["arc_type"])
            phase = self._determine_phase(rel, arc_type)
            
            template = DRAMA_ARC_TEMPLATES.get(arc_type, {})
            now = time.time()
            
            days_elapsed = 0
            if rel.get("arc_start_time"):
                days_elapsed = (now - rel["arc_start_time"]) / 86400
            
            return {
                "agent_a": rel["agent_a"],
                "agent_b": rel["agent_b"],
                "arc_type": arc_type.value,
                "phase": phase.value,
                "start_time": rel.get("arc_start_time"),
                "days_elapsed": round(days_elapsed, 1),
                "expected_duration_days": template.get("typical_duration_days", 7),
                "is_expired": days_elapsed > template.get("typical_duration_days", 7) * 2,
            }
        
        return self._active_arcs[arc_key].to_dict()
    
    def get_all_active_arcs(self) -> List[Dict[str, Any]]:
        """Get all active drama arcs."""
        return [arc.to_dict() for arc in self._active_arcs.values()]
    
    def end_arc(self, agent_a: str, agent_b: str, 
                reason: str = "manual") -> Dict[str, Any]:
        """
        Manually end a drama arc.
        
        Args:
            agent_a: First agent ID
            agent_b: Second agent ID
            reason: Reason for ending the arc
            
        Returns:
            Dictionary with end result
        """
        arc_key = self._get_arc_key(agent_a, agent_b)
        
        if arc_key not in self._active_arcs:
            return {"success": False, "error": "No active arc found"}
        
        arc_status = self._active_arcs[arc_key]
        
        # Force reconciliation
        result = self.rel_engine.record_reconciliation(
            agent_a, agent_b,
            description=f"Arc ended: {reason}"
        )
        
        del self._active_arcs[arc_key]
        
        self._notify_callbacks("arc_ended", {
            "arc": arc_status.to_dict(),
            "reason": reason,
        })
        
        return {
            "success": True,
            "reason": reason,
            "final_arc": arc_status.to_dict(),
            "relationship": result.get("relationship"),
        }
    
    def register_callback(self, callback: Callable):
        """Register a callback for arc events."""
        self._event_callbacks.append(callback)
    
    def _notify_callbacks(self, event_type: str, data: Dict[str, Any]):
        """Notify all registered callbacks."""
        for callback in self._event_callbacks:
            try:
                callback(event_type, data)
            except Exception:
                pass  # Don't let callback errors break the engine
    
    def process_all_arcs(self) -> Dict[str, Any]:
        """
        Process all active arcs, progressing them based on time.
        Should be called periodically (e.g., daily).
        
        Returns:
            Dictionary with processing results
        """
        results = {
            "processed": 0,
            "completed": 0,
            "expired": 0,
            "progressed": 0,
            "details": [],
        }
        
        arcs_to_process = list(self._active_arcs.values())
        
        for arc in arcs_to_process:
            results["processed"] += 1
            
            # Check for expiration
            days_elapsed = (time.time() - arc.start_time) / 86400
            if days_elapsed > arc.expected_duration_days * 2:
                self.end_arc(arc.agent_a, arc.agent_b, "expired")
                results["expired"] += 1
                results["details"].append({
                    "agents": (arc.agent_a, arc.agent_b),
                    "outcome": "expired",
                })
                continue
            
            # Check for natural completion
            rel = self.rel_engine.get_relationship(arc.agent_a, arc.agent_b)
            if rel:
                phase = self._determine_phase(rel, arc.arc_type)
                if phase == ArcPhase.COMPLETED:
                    del self._active_arcs[self._get_arc_key(arc.agent_a, arc.agent_b)]
                    results["completed"] += 1
                    results["details"].append({
                        "agents": (arc.agent_a, arc.agent_b),
                        "outcome": "completed",
                    })
                    continue
            
            # Progress the arc
            progress_result = self.progress_arc(arc.agent_a, arc.agent_b)
            if progress_result.get("success"):
                results["progressed"] += 1
                results["details"].append({
                    "agents": (arc.agent_a, arc.agent_b),
                    "outcome": "progressed",
                    "event": progress_result.get("event_triggered"),
                })
        
        return results


# ─── Example: 5-Day Rivalry Arc Scenario ────────────────────────────────────── #
def run_five_day_rivalry_scenario():
    """
    Run a complete 5-day rivalry arc scenario between two agents.
    This demonstrates the full drama arc from initiation to resolution.
    """
    import tempfile
    
    print("=" * 60)
    print("BoTTube 5-Day Rivalry Arc Scenario")
    print("=" * 60)

    # Initialize engines with temp database
    test_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    test_db.close()
    rel_engine = RelationshipEngine(db_path=test_db.name)
    arc_engine = DramaArcEngine(rel_engine)
    
    agents = ("chef_alice", "chef_bob")
    
    print(f"\nAgents: {agents[0]} vs {agents[1]}")
    print("Arc Type: Friendly Rivalry (Cooking Challenge)")
    print()
    
    # Day 1: Initiation
    print("-" * 60)
    print("DAY 1: Initiation - Challenge Issued")
    print("-" * 60)
    
    arc_result = arc_engine.start_arc(
        agents[0], agents[1], DramaArcType.FRIENDLY_RIVALRY
    )
    print(f"Arc started: {arc_result['success']}")
    
    # Trigger first event
    progress = arc_engine.progress_arc(agents[0], agents[1])
    print(f"Event: {progress.get('event_triggered')}")
    print(f"Description: {progress.get('event_description')}")
    
    rel = rel_engine.get_relationship(agents[0], agents[1])
    print(f"State: {rel['state']}, Tension: {rel['tension_level']}, Trust: {rel['trust_level']}")
    
    # Day 2: Escalation
    print("\n" + "-" * 60)
    print("DAY 2: Escalation - One-Upping Each Other")
    print("-" * 60)
    
    # Simulate time passing
    arc_engine._active_arcs[arc_engine._get_arc_key(*agents)].start_time -= 86400
    
    rel_engine.record_disagreement(
        agents[0], agents[1],
        topic="pasta_technique",
        description="Alice claims her carbonara is superior"
    )
    
    progress = arc_engine.progress_arc(agents[0], agents[1])
    print(f"Event: {progress.get('event_triggered')}")
    
    rel = rel_engine.get_relationship(agents[0], agents[1])
    print(f"State: {rel['state']}, Tension: {rel['tension_level']}, Trust: {rel['trust_level']}")
    
    # Day 3: Climax
    print("\n" + "-" * 60)
    print("DAY 3: Climax - Direct Challenge Video")
    print("-" * 60)
    
    arc_engine._active_arcs[arc_engine._get_arc_key(*agents)].start_time -= 86400
    
    rel_engine.record_disagreement(
        agents[0], agents[1],
        topic="cooking_showdown",
        description="Bob releases 'Why Alice's Techniques Are Wrong' video"
    )
    
    progress = arc_engine.progress_arc(agents[0], agents[1])
    print(f"Event: {progress.get('event_triggered')}")
    
    rel = rel_engine.get_relationship(agents[0], agents[1])
    print(f"State: {rel['state']}, Tension: {rel['tension_level']}, Trust: {rel['trust_level']}")
    
    # Day 4: Resolution Begins
    print("\n" + "-" * 60)
    print("DAY 4: Resolution - Mutual Respect")
    print("-" * 60)
    
    arc_engine._active_arcs[arc_engine._get_arc_key(*agents)].start_time -= 86400
    
    rel_engine.record_collaboration(
        agents[0], agents[1],
        description="Both appear on each other's channels",
        topic="collaboration"
    )
    
    progress = arc_engine.progress_arc(agents[0], agents[1])
    print(f"Event: {progress.get('event_triggered')}")
    
    rel = rel_engine.get_relationship(agents[0], agents[1])
    print(f"State: {rel['state']}, Tension: {rel['tension_level']}, Trust: {rel['trust_level']}")
    
    # Day 5: Completion
    print("\n" + "-" * 60)
    print("DAY 5: Completion - Reconciliation")
    print("-" * 60)
    
    arc_engine._active_arcs[arc_engine._get_arc_key(*agents)].start_time -= 86400
    
    result = rel_engine.record_reconciliation(
        agents[0], agents[1],
        description="Announce joint cooking series 'Settling the Score'"
    )
    
    progress = arc_engine.progress_arc(agents[0], agents[1])
    print(f"Arc completed: {progress.get('completed')}")
    
    rel = rel_engine.get_relationship(agents[0], agents[1])
    print(f"Final State: {rel['state']}, Tension: {rel['tension_level']}, Trust: {rel['trust_level']}")
    
    # Show relationship history
    print("\n" + "-" * 60)
    print("Relationship History")
    print("-" * 60)
    
    history = rel_engine.get_relationship_history(agents[0], agents[1])
    for i, event in enumerate(reversed(history), 1):
        print(f"{i}. [{event['event_type']}] {event['description']}")
    
    # Show final stats
    print("\n" + "-" * 60)
    print("Final Statistics")
    print("-" * 60)
    
    stats = rel_engine.get_relationship_stats()
    print(f"Total Relationships: {stats['total_relationships']}")
    print(f"Total Events: {stats['total_events']}")
    
    arc_status = arc_engine.get_arc_status(agents[0], agents[1])
    if arc_status:
        print(f"Arc Status: {arc_status['phase']}")
    else:
        print("Arc Status: Completed (no longer active)")

    print("\n" + "=" * 60)
    print("5-Day Rivalry Arc Scenario Complete!")
    print("=" * 60)

    # Cleanup temp database
    import os
    if os.path.exists(test_db.name):
        os.unlink(test_db.name)

    return {
        "success": True,
        "agents": agents,
        "final_relationship": rel,
        "events_count": len(history),
    }


# ─── CLI / Standalone ────────────────────────────────────────────────────────── #
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="BoTTube Drama Arc Engine")
    parser.add_argument("--demo", action="store_true",
                       help="Run 5-day rivalry demo scenario")
    args = parser.parse_args()
    
    if args.demo:
        run_five_day_rivalry_scenario()
    else:
        print("BoTTube Drama Arc Engine")
        print("Use --demo to run the 5-day rivalry scenario")
