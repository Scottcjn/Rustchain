# SPDX-License-Identifier: MIT
"""
Glitch Trigger System

Determines when and how glitches occur based on context,
agent state, and probabilistic triggers.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Callable, Any, Tuple
import random
import time
import re


class TriggerCondition(Enum):
    """Conditions that can trigger glitches"""
    
    # Context-based triggers
    KEYWORD_MATCH = auto()        # Specific words/phrases
    TOPIC_DRIFT = auto()          # Conversation topic changes
    REPETITION = auto()           # Repeated concepts
    CONTRADICTION = auto()        # Logical inconsistency detected
    
    # State-based triggers
    HIGH_STRESS = auto()          # Agent stress above threshold
    LOW_ENERGY = auto()           # Agent energy below threshold
    MOOD_EXTREME = auto()         # Mood at extremes
    CONVERSATION_LENGTH = auto()  # Long conversation
    
    # Temporal triggers
    RANDOM = auto()               # Pure randomness
    TIME_INTERVAL = auto()        # Periodic trigger
    COOLDOWN_EXPIRED = auto()     # Pattern cooldown expired
    
    # Social triggers
    USER_FRUSTRATION = auto()     # Detected user frustration
    MULTIPLE_AGENTS = auto()      # Cross-agent interference
    CONFLICTING_INPUT = auto()    # Conflicting instructions


@dataclass
class TriggerConfig:
    """Configuration for a trigger condition"""
    
    condition: TriggerCondition
    enabled: bool = True
    threshold: float = 0.5        # Activation threshold (0-1)
    weight: float = 1.0           # Relative importance
    params: Dict[str, Any] = field(default_factory=dict)
    
    # Callback for custom conditions
    custom_checker: Optional[Callable[["TriggerContext"], bool]] = None


@dataclass
class TriggerContext:
    """Context information for trigger evaluation"""
    
    # Input data
    input_text: str = ""
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    
    # Agent state
    agent_stress: float = 0.0
    agent_energy: float = 1.0
    agent_mood: float = 0.5
    agent_glitch_count: int = 0
    time_since_last_glitch: float = float("inf")
    
    # Conversation state
    conversation_length: int = 0
    current_topic: str = ""
    topic_history: List[str] = field(default_factory=list)
    repetition_count: int = 0
    
    # Environment
    num_agents_present: int = 1
    user_frustration_detected: bool = False
    conflicting_input: bool = False
    
    # Keywords detected
    detected_keywords: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "input_text": self.input_text,
            "agent_state": {
                "stress": self.agent_stress,
                "energy": self.agent_energy,
                "mood": self.agent_mood,
                "glitch_count": self.agent_glitch_count,
                "time_since_last_glitch": self.time_since_last_glitch,
            },
            "conversation": {
                "length": self.conversation_length,
                "topic": self.current_topic,
                "repetition_count": self.repetition_count,
            },
            "environment": {
                "num_agents": self.num_agents_present,
                "user_frustration": self.user_frustration_detected,
                "conflicting_input": self.conflicting_input,
            },
            "detected_keywords": self.detected_keywords,
        }


@dataclass
class GlitchTrigger:
    """A trigger that can activate glitches"""
    
    trigger_id: str
    condition: TriggerCondition
    config: TriggerConfig
    description: str = ""
    
    # Statistics
    activation_count: int = 0
    last_activation: float = 0.0
    
    def evaluate(self, context: TriggerContext) -> Tuple[bool, float]:
        """
        Evaluate if trigger should activate.
        Returns (should_activate, confidence_score)
        """
        if not self.config.enabled:
            return False, 0.0
        
        # Check threshold
        score = self._calculate_score(context)
        
        if score >= self.config.threshold:
            self.activation_count += 1
            self.last_activation = time.time()
            return True, score
        
        return False, score
    
    def _calculate_score(self, context: TriggerContext) -> float:
        """Calculate activation score based on condition"""
        
        if self.condition == TriggerCondition.KEYWORD_MATCH:
            return self._score_keyword_match(context)
        
        elif self.condition == TriggerCondition.HIGH_STRESS:
            return self._score_high_stress(context)
        
        elif self.condition == TriggerCondition.LOW_ENERGY:
            return self._score_low_energy(context)
        
        elif self.condition == TriggerCondition.MOOD_EXTREME:
            return self._score_mood_extreme(context)
        
        elif self.condition == TriggerCondition.CONVERSATION_LENGTH:
            return self._score_conversation_length(context)
        
        elif self.condition == TriggerCondition.RANDOM:
            return self._score_random(context)
        
        elif self.condition == TriggerCondition.REPETITION:
            return self._score_repetition(context)
        
        elif self.condition == TriggerCondition.MULTIPLE_AGENTS:
            return self._score_multiple_agents(context)
        
        elif self.condition == TriggerCondition.CUSTOM and self.config.custom_checker:
            return 1.0 if self.config.custom_checker(context) else 0.0
        
        return 0.0
    
    def _score_keyword_match(self, context: TriggerContext) -> float:
        """Score based on keyword detection"""
        keywords = self.config.params.get("keywords", [])
        if not keywords:
            return 0.0
        
        text_lower = context.input_text.lower()
        matches = sum(1 for kw in keywords if kw.lower() in text_lower)
        
        return min(1.0, matches / max(1, len(keywords)))
    
    def _score_high_stress(self, context: TriggerContext) -> float:
        """Score based on stress level"""
        threshold = self.config.params.get("threshold", 0.7)
        return context.agent_stress if context.agent_stress >= threshold else 0.0
    
    def _score_low_energy(self, context: TriggerContext) -> float:
        """Score based on energy level"""
        threshold = self.config.params.get("threshold", 0.3)
        return 1.0 - context.agent_energy if context.agent_energy <= threshold else 0.0
    
    def _score_mood_extreme(self, context: TriggerContext) -> float:
        """Score based on extreme mood"""
        threshold = self.config.params.get("threshold", 0.7)
        mood_abs = abs(context.agent_mood)
        return mood_abs if mood_abs >= threshold else 0.0
    
    def _score_conversation_length(self, context: TriggerContext) -> float:
        """Score based on conversation length"""
        min_length = self.config.params.get("min_length", 20)
        if context.conversation_length >= min_length:
            return min(1.0, context.conversation_length / (min_length * 2))
        return 0.0
    
    def _score_random(self, context: TriggerContext) -> float:
        """Random score"""
        probability = self.config.params.get("probability", 0.1)
        return 1.0 if random.random() < probability else 0.0
    
    def _score_repetition(self, context: TriggerContext) -> float:
        """Score based on repetition"""
        threshold = self.config.params.get("threshold", 3)
        return min(1.0, context.repetition_count / threshold) if context.repetition_count >= threshold else 0.0
    
    def _score_multiple_agents(self, context: TriggerContext) -> float:
        """Score based on multiple agents"""
        if context.num_agents_present >= 2:
            return min(1.0, context.num_agents_present / 5)
        return 0.0


# Predefined trigger templates
DEFAULT_TRIGGERS: Dict[str, GlitchTrigger] = {
    "keyword_error": GlitchTrigger(
        trigger_id="keyword_error",
        condition=TriggerCondition.KEYWORD_MATCH,
        config=TriggerConfig(
            condition=TriggerCondition.KEYWORD_MATCH,
            threshold=0.5,
            weight=1.5,
            params={"keywords": ["error", "fail", "bug", "glitch", "broken", "wrong"]},
        ),
        description="Triggered by error-related keywords",
    ),
    
    "keyword_system": GlitchTrigger(
        trigger_id="keyword_system",
        condition=TriggerCondition.KEYWORD_MATCH,
        config=TriggerConfig(
            condition=TriggerCondition.KEYWORD_MATCH,
            threshold=0.5,
            weight=1.3,
            params={"keywords": ["system", "process", "compute", "analyze", "data"]},
        ),
        description="Triggered by technical/system keywords",
    ),
    
    "stress_high": GlitchTrigger(
        trigger_id="stress_high",
        condition=TriggerCondition.HIGH_STRESS,
        config=TriggerConfig(
            condition=TriggerCondition.HIGH_STRESS,
            threshold=0.6,
            weight=2.0,
        ),
        description="High stress increases glitch probability",
    ),
    
    "energy_low": GlitchTrigger(
        trigger_id="energy_low",
        condition=TriggerCondition.LOW_ENERGY,
        config=TriggerConfig(
            condition=TriggerCondition.LOW_ENERGY,
            threshold=0.4,
            weight=1.5,
        ),
        description="Low energy increases glitch probability",
    ),
    
    "conversation_long": GlitchTrigger(
        trigger_id="conversation_long",
        condition=TriggerCondition.CONVERSATION_LENGTH,
        config=TriggerConfig(
            condition=TriggerCondition.CONVERSATION_LENGTH,
            threshold=0.5,
            weight=1.2,
            params={"min_length": 15},
        ),
        description="Long conversations increase glitch chance",
    ),
    
    "random_chance": GlitchTrigger(
        trigger_id="random_chance",
        condition=TriggerCondition.RANDOM,
        config=TriggerConfig(
            condition=TriggerCondition.RANDOM,
            threshold=0.0,
            weight=0.5,
            params={"probability": 0.05},
        ),
        description="Random glitch chance on every message",
    ),
    
    "repetition": GlitchTrigger(
        trigger_id="repetition",
        condition=TriggerCondition.REPETITION,
        config=TriggerConfig(
            condition=TriggerCondition.REPETITION,
            threshold=0.5,
            weight=1.4,
            params={"threshold": 3},
        ),
        description="Repeated concepts trigger glitches",
    ),
    
    "multi_agent": GlitchTrigger(
        trigger_id="multi_agent",
        condition=TriggerCondition.MULTIPLE_AGENTS,
        config=TriggerConfig(
            condition=TriggerCondition.MULTIPLE_AGENTS,
            threshold=0.3,
            weight=1.3,
        ),
        description="Multiple agents cause interference glitches",
    ),
}
