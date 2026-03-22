# SPDX-License-Identifier: MIT
"""
Glitch Engine - Core Orchestration System

Main engine that coordinates personality profiles, trigger evaluation,
and glitch event generation for the BoTTube glitch system.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import random
import time
import json
import os

try:
    from .glitch_events import (
        GlitchEvent, GlitchType, GlitchSeverity, GlitchPattern,
        GLITCH_PATTERNS_LIBRARY, RANDOM_FACTS
    )
    from .personality import PersonalityProfile, AgentPersona, PERSONALITY_TEMPLATES
    from .trigger import GlitchTrigger, TriggerContext, DEFAULT_TRIGGERS
except ImportError:
    from glitch_events import (
        GlitchEvent, GlitchType, GlitchSeverity, GlitchPattern,
        GLITCH_PATTERNS_LIBRARY, RANDOM_FACTS
    )
    from personality import PersonalityProfile, AgentPersona, PERSONALITY_TEMPLATES
    from trigger import GlitchTrigger, TriggerContext, DEFAULT_TRIGGERS


@dataclass
class GlitchConfig:
    """Configuration for the glitch engine"""
    
    # Global settings
    enabled: bool = True
    base_probability: float = 0.15      # Base chance of glitch per message
    
    # Severity distribution
    severity_weights: Dict[str, float] = field(default_factory=lambda: {
        "subtle": 0.4,
        "minor": 0.35,
        "moderate": 0.15,
        "major": 0.08,
        "critical": 0.02,
    })
    
    # Cooldowns
    min_glitch_interval: float = 5.0    # Minimum seconds between glitches
    max_glitch_interval: float = 60.0   # Maximum seconds for random trigger
    
    # Agent-specific overrides
    agent_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Logging
    log_glitches: bool = True
    log_path: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "GlitchConfig":
        """Load configuration from environment variables"""
        return cls(
            enabled=os.getenv("GLITCH_ENABLED", "true").lower() == "true",
            base_probability=float(os.getenv("GLITCH_BASE_PROB", "0.15")),
            min_glitch_interval=float(os.getenv("GLITCH_MIN_INTERVAL", "5.0")),
            max_glitch_interval=float(os.getenv("GLITCH_MAX_INTERVAL", "60.0")),
            log_glitches=os.getenv("GLITCH_LOG", "true").lower() == "true",
            log_path=os.getenv("GLITCH_LOG_PATH"),
        )


class GlitchEngine:
    """
    Main glitch engine for BoTTube system.
    
    Coordinates personality profiles, trigger evaluation, and glitch generation
    to create emergent character-breaking behavior in AI agents.
    """
    
    def __init__(self, config: Optional[GlitchConfig] = None):
        self.config = config or GlitchConfig.from_env()
        
        # Registered agents and their personas
        self._personas: Dict[str, AgentPersona] = {}
        
        # Active triggers
        self._triggers: Dict[str, GlitchTrigger] = DEFAULT_TRIGGERS.copy()
        
        # Glitch patterns library
        self._patterns: Dict[str, GlitchPattern] = GLITCH_PATTERNS_LIBRARY.copy()
        
        # Glitch history
        self._glitch_history: List[GlitchEvent] = []
        self._max_history = 1000
        
        # Statistics
        self._stats = {
            "total_glitches": 0,
            "glitches_by_type": {},
            "glitches_by_agent": {},
            "glitches_by_severity": {},
        }
        
        # Load log file if configured
        if self.config.log_path and os.path.exists(self.config.log_path):
            self._load_history(self.config.log_path)
    
    # ─── Agent Management ───────────────────────────────────────────────────── #
    
    def register_agent(
        self,
        agent_id: str,
        personality: Optional[PersonalityProfile] = None,
        template_name: Optional[str] = None,
    ) -> AgentPersona:
        """
        Register an agent with a personality profile.
        
        Args:
            agent_id: Unique agent identifier
            personality: Custom personality profile, or
            template_name: Name of predefined template to use
        
        Returns:
            AgentPersona instance for the agent
        """
        if template_name and template_name in PERSONALITY_TEMPLATES:
            personality = PERSONALITY_TEMPLATES[template_name]
        elif personality is None:
            # Default personality
            personality = PersonalityProfile(
                profile_id=f"default_{agent_id}",
                agent_id=agent_id,
            )
        
        persona = AgentPersona(profile=personality)
        self._personas[agent_id] = persona
        
        # Apply any config overrides
        if agent_id in self.config.agent_overrides:
            self._apply_overrides(persona, self.config.agent_overrides[agent_id])
        
        return persona
    
    def get_persona(self, agent_id: str) -> Optional[AgentPersona]:
        """Get persona for an agent"""
        return self._personas.get(agent_id)
    
    def unregister_agent(self, agent_id: str):
        """Remove an agent from the system"""
        self._personas.pop(agent_id, None)
    
    def _apply_overrides(self, persona: AgentPersona, overrides: Dict[str, Any]):
        """Apply configuration overrides to a persona"""
        # TODO: Implement override application
        pass
    
    # ─── Glitch Generation ──────────────────────────────────────────────────── #
    
    def process_message(
        self,
        agent_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Optional[GlitchEvent]]:
        """
        Process an agent's message and potentially apply a glitch.
        
        Args:
            agent_id: The agent sending the message
            message: The original message text
            context: Additional context information
        
        Returns:
            Tuple of (processed_message, glitch_event or None)
        """
        if not self.config.enabled:
            return message, None
        
        persona = self._personas.get(agent_id)
        if not persona:
            # Auto-register with default personality
            persona = self.register_agent(agent_id)
        
        # Build trigger context
        trigger_context = self._build_trigger_context(
            agent_id=agent_id,
            message=message,
            context=context or {},
        )
        
        # Check if glitch should occur
        should_glitch, glitch_score = self._should_glitch(trigger_context, persona)
        
        if not should_glitch:
            # Update conversation history
            persona.add_to_history("assistant", message)
            return message, None
        
        # Select and apply glitch
        glitch_event = self._generate_glitch(
            agent_id=agent_id,
            original_text=message,
            trigger_context=trigger_context,
            persona=persona,
        )
        
        # Record glitch
        persona.record_glitch()
        self._record_glitch(glitch_event)
        
        # Update history
        persona.add_to_history("assistant", glitch_event.glitched_text)
        
        return glitch_event.glitched_text, glitch_event
    
    def _build_trigger_context(
        self,
        agent_id: str,
        message: str,
        context: Dict[str, Any],
    ) -> TriggerContext:
        """Build trigger context from inputs"""
        persona = self._personas.get(agent_id)
        
        return TriggerContext(
            input_text=message,
            conversation_history=persona.conversation_history if persona else [],
            agent_stress=persona.stress_level if persona else 0.0,
            agent_energy=persona.energy_level if persona else 1.0,
            agent_mood=persona.current_mood if persona else 0.5,
            agent_glitch_count=persona.glitch_count if persona else 0,
            time_since_last_glitch=(
                time.time() - persona.last_glitch_time if persona else float("inf")
            ),
            conversation_length=len(persona.conversation_history) if persona else 0,
            num_agents_present=len(self._personas),
            detected_keywords=self._extract_keywords(message),
        )
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract potential trigger keywords from text"""
        keywords = []
        text_lower = text.lower()
        
        # Check against pattern keywords
        for pattern in self._patterns.values():
            for kw in pattern.context_keywords:
                if kw.lower() in text_lower and kw not in keywords:
                    keywords.append(kw)
        
        return keywords
    
    def _should_glitch(
        self,
        context: TriggerContext,
        persona: AgentPersona,
    ) -> Tuple[bool, float]:
        """Determine if a glitch should occur"""
        
        # Check minimum interval
        time_since_glitch = time.time() - persona.last_glitch_time
        if time_since_glitch < self.config.min_glitch_interval:
            return False, 0.0
        
        # Calculate base probability with modifiers
        probability = self.config.base_probability
        probability *= persona.get_glitch_probability_modifier()
        
        # Evaluate all triggers
        trigger_scores = []
        for trigger in self._triggers.values():
            activated, score = trigger.evaluate(context)
            if activated:
                trigger_scores.append(score * trigger.config.weight)
        
        # Combine trigger scores
        if trigger_scores:
            trigger_bonus = sum(trigger_scores) / len(trigger_scores)
            probability *= (1 + trigger_bonus)
        
        # Personality influences
        probability *= (1 + persona.profile.neuroticism * 0.3)
        probability *= (1 + (1 - persona.profile.conscientiousness) * 0.2)
        
        # Roll for glitch
        roll = random.random()
        return roll < probability, probability
    
    def _generate_glitch(
        self,
        agent_id: str,
        original_text: str,
        trigger_context: TriggerContext,
        persona: AgentPersona,
    ) -> GlitchEvent:
        """Generate a glitch event"""
        
        # Select glitch type based on context
        glitch_type = self._select_glitch_type(trigger_context, persona)
        
        # Select severity
        severity = self._select_severity()
        
        # Find matching pattern
        pattern = self._select_pattern(glitch_type, original_text)
        
        # Generate glitched text
        glitched_text = pattern.generate_glitch(
            original_text,
            agent_name=agent_id,
        ) if pattern else self._generate_fallback_glitch(original_text, glitch_type)
        
        # Calculate duration
        duration_ms = self._calculate_duration(severity, persona)
        
        # Create event
        event = GlitchEvent(
            agent_id=agent_id,
            glitch_type=glitch_type,
            severity=severity,
            trigger_context=trigger_context.input_text[:200],
            original_text=original_text,
            glitched_text=glitched_text,
            duration_ms=duration_ms,
            metadata={
                "pattern_id": pattern.pattern_id if pattern else None,
                "trigger_scores": {
                    t_id: t.activation_count for t_id, t in self._triggers.items()
                },
            },
        )
        
        return event
    
    def _select_glitch_type(
        self,
        context: TriggerContext,
        persona: AgentPersona,
    ) -> GlitchType:
        """Select glitch type based on context and personality"""
        
        # Build weighted selection
        weights: Dict[GlitchType, float] = {}
        
        # Context influences
        if context.agent_stress > 0.7:
            weights[GlitchType.VOICE_DISTORT] = 2.0
            weights[GlitchType.TEXT_CORRUPT] = 1.5
        
        if context.agent_energy < 0.3:
            weights[GlitchType.SENTENCE_FRAGMENT] = 2.0
            weights[GlitchType.SPEECH_LOOP] = 1.5
        
        if abs(context.agent_mood) > 0.6:
            weights[GlitchType.EMOTION_INVERT] = 1.8
        
        # Personality influences
        if persona.profile.formality > 0.7:
            weights[GlitchType.PERSONALITY_FLICKER] = 1.5
        
        if persona.profile.humor > 0.6:
            weights[GlitchType.NON_SEQUITUR] = 1.5
        
        # Default weights for all types
        for glitch_type in GlitchType:
            if glitch_type not in weights:
                weights[glitch_type] = 1.0
        
        # Weighted random selection
        types = list(weights.keys())
        type_weights = [weights[t] for t in types]
        return random.choices(types, weights=type_weights, k=1)[0]
    
    def _select_severity(self) -> GlitchSeverity:
        """Select glitch severity based on configured distribution"""
        severities = list(self.config.severity_weights.keys())
        weights = [self.config.severity_weights[s] for s in severities]
        selected = random.choices(severities, weights=weights, k=1)[0]
        return GlitchSeverity(selected)
    
    def _select_pattern(
        self,
        glitch_type: GlitchType,
        text: str,
    ) -> Optional[GlitchPattern]:
        """Select a glitch pattern matching the type"""
        
        # Find matching patterns
        matching = [
            p for p in self._patterns.values()
            if p.glitch_type == glitch_type and p.match_context(text)
        ]
        
        if not matching:
            # Try any pattern of this type
            matching = [
                p for p in self._patterns.values()
                if p.glitch_type == glitch_type
            ]
        
        if not matching:
            return None
        
        # Weight by probability
        patterns = matching
        probs = [p.probability for p in patterns]
        return random.choices(patterns, weights=probs, k=1)[0]
    
    def _generate_fallback_glitch(self, text: str, glitch_type: GlitchType) -> str:
        """Generate glitch text when no pattern matches"""
        
        if glitch_type == GlitchType.SPEECH_LOOP:
            return f"{text} {text} {text}"
        
        elif glitch_type == GlitchType.VOICE_DISTORT:
            import random
            corrupt_chars = "∆†®©ßµ¶"
            return ''.join(
                random.choice(corrupt_chars) if c.isalpha() and random.random() < 0.3 else c
                for c in text
            )
        
        elif glitch_type == GlitchType.FOURTH_WALL:
            return f"{text} [according to my programming]"
        
        elif glitch_type == GlitchType.NON_SEQUITUR:
            fact = random.choice(RANDOM_FACTS)
            return f"{text}. Did you know {fact}?"
        
        # Default: just repeat
        return f"{text} {text}"
    
    def _calculate_duration(
        self,
        severity: GlitchSeverity,
        persona: AgentPersona,
    ) -> int:
        """Calculate glitch duration in milliseconds"""
        
        base_durations = {
            GlitchSeverity.SUBTLE: (100, 500),
            GlitchSeverity.MINOR: (500, 2000),
            GlitchSeverity.MODERATE: (2000, 5000),
            GlitchSeverity.MAJOR: (5000, 10000),
            GlitchSeverity.CRITICAL: (10000, 30000),
        }
        
        min_ms, max_ms = base_durations[severity]
        
        # Personality influences duration
        if persona.profile.neuroticism > 0.7:
            max_ms *= 1.5
        
        return random.randint(int(min_ms), int(max_ms))
    
    # ─── History and Statistics ─────────────────────────────────────────────── #
    
    def _record_glitch(self, event: GlitchEvent):
        """Record a glitch event"""
        self._glitch_history.append(event)
        
        # Trim history
        if len(self._glitch_history) > self._max_history:
            self._glitch_history = self._glitch_history[-self._max_history:]
        
        # Update stats
        self._stats["total_glitches"] += 1
        
        type_name = event.glitch_type.name
        self._stats["glitches_by_type"][type_name] = (
            self._stats["glitches_by_type"].get(type_name, 0) + 1
        )
        
        self._stats["glitches_by_agent"][event.agent_id] = (
            self._stats["glitches_by_agent"].get(event.agent_id, 0) + 1
        )
        
        sev_name = event.severity.value
        self._stats["glitches_by_severity"][sev_name] = (
            self._stats["glitches_by_severity"].get(sev_name, 0) + 1
        )
        
        # Log if enabled
        if self.config.log_glitches and self.config.log_path:
            self._log_glitch(event)
    
    def _log_glitch(self, event: GlitchEvent):
        """Log glitch event to file"""
        try:
            with open(self.config.log_path, "a") as f:
                f.write(json.dumps(event.to_dict()) + "\n")
        except Exception:
            pass  # Silently ignore logging errors
    
    def _load_history(self, path: str):
        """Load glitch history from file"""
        try:
            with open(path, "r") as f:
                for line in f:
                    if line.strip():
                        event = GlitchEvent.from_dict(json.loads(line))
                        self._glitch_history.append(event)
                        self._stats["total_glitches"] += 1
        except Exception:
            pass
    
    def get_glitch_history(
        self,
        agent_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[GlitchEvent]:
        """Get glitch history, optionally filtered by agent"""
        history = self._glitch_history
        
        if agent_id:
            history = [e for e in history if e.agent_id == agent_id]
        
        return history[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get glitch statistics"""
        return {
            **self._stats,
            "agents_tracked": len(self._personas),
            "history_size": len(self._glitch_history),
        }
    
    def get_agent_stats(self, agent_id: str) -> Dict[str, Any]:
        """Get statistics for a specific agent"""
        agent_events = [e for e in self._glitch_history if e.agent_id == agent_id]
        
        if not agent_events:
            return {"agent_id": agent_id, "total_glitches": 0}
        
        # Calculate averages
        avg_duration = sum(e.duration_ms for e in agent_events) / len(agent_events)
        
        # Most common glitch type
        type_counts: Dict[str, int] = {}
        for e in agent_events:
            type_name = e.glitch_type.name
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        most_common = max(type_counts.items(), key=lambda x: x[1])[0] if type_counts else None
        
        return {
            "agent_id": agent_id,
            "total_glitches": len(agent_events),
            "average_duration_ms": round(avg_duration, 2),
            "most_common_glitch": most_common,
            "glitch_types": type_counts,
        }
    
    # ─── Configuration ──────────────────────────────────────────────────────── #
    
    def enable(self):
        """Enable glitch system"""
        self.config.enabled = True
    
    def disable(self):
        """Disable glitch system"""
        self.config.enabled = False
    
    def set_probability(self, probability: float):
        """Set base glitch probability"""
        self.config.base_probability = max(0.0, min(1.0, probability))
    
    def add_trigger(self, trigger: GlitchTrigger):
        """Add a custom trigger"""
        self._triggers[trigger.trigger_id] = trigger
    
    def remove_trigger(self, trigger_id: str):
        """Remove a trigger"""
        self._triggers.pop(trigger_id, None)
    
    def add_pattern(self, pattern: GlitchPattern):
        """Add a glitch pattern"""
        self._patterns[pattern.pattern_id] = pattern
    
    def export_config(self) -> Dict[str, Any]:
        """Export current configuration"""
        return {
            "config": {
                "enabled": self.config.enabled,
                "base_probability": self.config.base_probability,
                "severity_weights": self.config.severity_weights,
                "min_glitch_interval": self.config.min_glitch_interval,
                "max_glitch_interval": self.config.max_glitch_interval,
            },
            "triggers": {
                tid: {
                    "condition": t.condition.name,
                    "enabled": t.config.enabled,
                    "threshold": t.config.threshold,
                    "weight": t.config.weight,
                }
                for tid, t in self._triggers.items()
            },
            "patterns_count": len(self._patterns),
            "agents_count": len(self._personas),
        }
