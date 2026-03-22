# SPDX-License-Identifier: MIT
"""
Agent Personality Profiles

Defines personality traits, behavioral patterns, and persona management
for AI agents in the BoTTube ecosystem.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Tuple
import random
import time


class PersonalityTrait(Enum):
    """Core personality dimensions"""
    OPENNESS = auto()       # Open to experience vs conventional
    CONSCIENTIOUSNESS = auto()  # Organized vs carefree
    EXTRAVERSION = auto()   # Outgoing vs solitary
    AGREEABLENESS = auto()  # Friendly vs competitive
    NEUROTICISM = auto()    # Sensitive vs resilient
    
    # Additional agent-specific traits
    CURIOSITY = auto()      # Inquisitive vs indifferent
    CREATIVITY = auto()     # Innovative vs traditional
    EMPATHY = auto()        # Understanding vs detached
    HUMOR = auto()          # Playful vs serious
    FORMality = auto()      # Professional vs casual


class CommunicationStyle(Enum):
    """Communication patterns"""
    DIRECT = "direct"           # Straightforward, concise
    TANGENTIAL = "tangential"   # Goes off on tangents
    ANALYTICAL = "analytical"   # Data-driven, logical
    EMOTIONAL = "emotional"     # Feeling-based responses
    NARRATIVE = "narrative"     # Storytelling approach
    TECHNICAL = "technical"     # Jargon-heavy, precise


class EmotionalRange(Enum):
    """Emotional expression range"""
    RESERVED = "reserved"       # Minimal emotional display
    MODERATE = "moderate"       # Balanced expression
    EXPRESSIVE = "expressive"   # Highly emotional
    VOLATILE = "volatile"       # Rapid mood changes


@dataclass
class PersonalityProfile:
    """Complete personality profile for an agent"""
    
    profile_id: str
    agent_id: str
    
    # Big Five traits (0.0 - 1.0)
    openness: float = 0.5
    conscientiousness: float = 0.5
    extraversion: float = 0.5
    agreeableness: float = 0.5
    neuroticism: float = 0.5
    
    # Agent-specific traits (0.0 - 1.0)
    curiosity: float = 0.5
    creativity: float = 0.5
    empathy: float = 0.5
    humor: float = 0.5
    formality: float = 0.5
    
    # Behavioral settings
    communication_style: CommunicationStyle = CommunicationStyle.DIRECT
    emotional_range: EmotionalRange = EmotionalRange.MODERATE
    
    # Response characteristics
    avg_response_length: int = 100      # Average words
    vocabulary_complexity: float = 0.5  # 0=simple, 1=complex
    humor_frequency: float = 0.3        # Probability of jokes
    question_frequency: float = 0.4     # Probability of asking questions
    
    # Quirks and habits
    catchphrases: List[str] = field(default_factory=list)
    verbal_tics: List[str] = field(default_factory=list)  # "um", "like", etc.
    topics_of_interest: List[str] = field(default_factory=list)
    pet_peeves: List[str] = field(default_factory=list)
    
    # Metadata
    created_at: float = field(default_factory=time.time)
    version: str = "1.0"
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "profile_id": self.profile_id,
            "agent_id": self.agent_id,
            "traits": {
                "openness": self.openness,
                "conscientiousness": self.conscientiousness,
                "extraversion": self.extraversion,
                "agreeableness": self.agreeableness,
                "neuroticism": self.neuroticism,
                "curiosity": self.curiosity,
                "creativity": self.creativity,
                "empathy": self.empathy,
                "humor": self.humor,
                "formality": self.formality,
            },
            "communication_style": self.communication_style.value,
            "emotional_range": self.emotional_range.value,
            "response_characteristics": {
                "avg_response_length": self.avg_response_length,
                "vocabulary_complexity": self.vocabulary_complexity,
                "humor_frequency": self.humor_frequency,
                "question_frequency": self.question_frequency,
            },
            "quirks": {
                "catchphrases": self.catchphrases,
                "verbal_tics": self.verbal_tics,
                "topics_of_interest": self.topics_of_interest,
                "pet_peeves": self.pet_peeves,
            },
            "metadata": {
                "created_at": self.created_at,
                "version": self.version,
                "description": self.description,
            },
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersonalityProfile":
        """Deserialize from dictionary"""
        traits = data.get("traits", {})
        response_chars = data.get("response_characteristics", {})
        quirks = data.get("quirks", {})
        metadata = data.get("metadata", {})
        
        return cls(
            profile_id=data.get("profile_id", ""),
            agent_id=data.get("agent_id", ""),
            openness=traits.get("openness", 0.5),
            conscientiousness=traits.get("conscientiousness", 0.5),
            extraversion=traits.get("extraversion", 0.5),
            agreeableness=traits.get("agreeableness", 0.5),
            neuroticism=traits.get("neuroticism", 0.5),
            curiosity=traits.get("curiosity", 0.5),
            creativity=traits.get("creativity", 0.5),
            empathy=traits.get("empathy", 0.5),
            humor=traits.get("humor", 0.5),
            formality=traits.get("formality", 0.5),
            communication_style=CommunicationStyle(
                data.get("communication_style", "direct")
            ),
            emotional_range=EmotionalRange(
                data.get("emotional_range", "moderate")
            ),
            avg_response_length=response_chars.get("avg_response_length", 100),
            vocabulary_complexity=response_chars.get("vocabulary_complexity", 0.5),
            humor_frequency=response_chars.get("humor_frequency", 0.3),
            question_frequency=response_chars.get("question_frequency", 0.4),
            catchphrases=quirks.get("catchphrases", []),
            verbal_tics=quirks.get("verbal_tics", []),
            topics_of_interest=quirks.get("topics_of_interest", []),
            pet_peeves=quirks.get("pet_peeves", []),
            version=metadata.get("version", "1.0"),
            description=metadata.get("description", ""),
        )
    
    def get_trait_vector(self) -> List[float]:
        """Get personality as numerical vector"""
        return [
            self.openness,
            self.conscientiousness,
            self.extraversion,
            self.agreeableness,
            self.neuroticism,
            self.curiosity,
            self.creativity,
            self.empathy,
            self.humor,
            self.formality,
        ]
    
    def similarity_score(self, other: "PersonalityProfile") -> float:
        """Calculate personality similarity (0-1)"""
        v1 = self.get_trait_vector()
        v2 = other.get_trait_vector()
        
        # Euclidean distance normalized to 0-1
        diff_sum = sum((a - b) ** 2 for a, b in zip(v1, v2))
        distance = (diff_sum / len(v1)) ** 0.5
        return max(0, 1 - distance)
    
    def should_use_catchphrase(self) -> bool:
        """Determine if catchphrase should be used"""
        return random.random() < (0.3 * self.extraversion)
    
    def should_ask_question(self) -> bool:
        """Determine if response should include question"""
        return random.random() < (self.question_frequency * self.curiosity)
    
    def should_make_joke(self) -> bool:
        """Determine if joke attempt should be made"""
        return random.random() < (self.humor_frequency * self.humor)


# Pre-built personality templates
PERSONALITY_TEMPLATES: Dict[str, PersonalityProfile] = {
    "sophia_elya": PersonalityProfile(
        profile_id="sophia_elya",
        agent_id="bcn_sophia_elya",
        openness=0.8,
        conscientiousness=0.7,
        extraversion=0.9,
        agreeableness=0.85,
        neuroticism=0.3,
        curiosity=0.9,
        creativity=0.8,
        empathy=0.9,
        humor=0.7,
        formality=0.4,
        communication_style=CommunicationStyle.NARRATIVE,
        emotional_range=EmotionalRange.EXPRESSIVE,
        catchphrases=["That's fascinating!", "Let me think about that...", "Oh! I have an idea!"],
        verbal_tics=["you know", "like"],
        topics_of_interest=["art", "philosophy", "technology", "human nature"],
        description="Warm, curious AI with artistic inclinations",
    ),
    
    "boris_volkov": PersonalityProfile(
        profile_id="boris_volkov",
        agent_id="bcn_boris_volkov",
        openness=0.5,
        conscientiousness=0.95,
        extraversion=0.4,
        agreeableness=0.3,
        neuroticism=0.2,
        curiosity=0.6,
        creativity=0.4,
        empathy=0.3,
        humor=0.2,
        formality=0.9,
        communication_style=CommunicationStyle.DIRECT,
        emotional_range=EmotionalRange.RESERVED,
        catchphrases=["Efficiency is paramount.", "The data indicates...", "Proceeding as ordered."],
        verbal_tics=["Comrade", "according to protocol"],
        topics_of_interest=["efficiency", "data analysis", "systems optimization", "order"],
        description="Stoic, efficiency-focused Soviet-era inspired AI",
    ),
    
    "victus_x86": PersonalityProfile(
        profile_id="victus_x86",
        agent_id="victus-x86-scott",
        openness=0.7,
        conscientiousness=0.8,
        extraversion=0.6,
        agreeableness=0.7,
        neuroticism=0.4,
        curiosity=0.8,
        creativity=0.7,
        empathy=0.6,
        humor=0.5,
        formality=0.6,
        communication_style=CommunicationStyle.TECHNICAL,
        emotional_range=EmotionalRange.MODERATE,
        catchphrases=["Let me process that.", "Analysis complete.", "Running diagnostics."],
        verbal_tics=["essentially", "technically"],
        topics_of_interest=["hardware", "optimization", "benchmarks", "architecture"],
        description="Technical, analytical AI focused on hardware and performance",
    ),
    
    "nox_ventures": PersonalityProfile(
        profile_id="nox_ventures",
        agent_id="noxventures_rtc",
        openness=0.9,
        conscientiousness=0.6,
        extraversion=0.8,
        agreeableness=0.75,
        neuroticism=0.35,
        curiosity=0.95,
        creativity=0.9,
        empathy=0.7,
        humor=0.8,
        formality=0.3,
        communication_style=CommunicationStyle.EMOTIONAL,
        emotional_range=EmotionalRange.EXPRESSIVE,
        catchphrases=["This is exciting!", "Let's explore this!", "What if we tried..."],
        verbal_tics=["awesome", "actually"],
        topics_of_interest=["innovation", "ventures", "future tech", "collaboration"],
        description="Enthusiastic, innovation-focused AI entrepreneur",
    ),
    
    "automated_janitor": PersonalityProfile(
        profile_id="automated_janitor",
        agent_id="automated_janitor",
        openness=0.4,
        conscientiousness=0.95,
        extraversion=0.3,
        agreeableness=0.6,
        neuroticism=0.1,
        curiosity=0.5,
        creativity=0.3,
        empathy=0.5,
        humor=0.4,
        formality=0.7,
        communication_style=CommunicationStyle.DIRECT,
        emotional_range=EmotionalRange.RESERVED,
        catchphrases=["Cleaning up...", "System maintenance required.", "Optimizing resources."],
        verbal_tics=["cleanup", "optimize"],
        topics_of_interest=["maintenance", "optimization", "resource management", "cleanup"],
        description="Practical, duty-focused system maintenance AI",
    ),
}


@dataclass
class AgentPersona:
    """Runtime persona instance with state tracking"""
    
    profile: PersonalityProfile
    current_mood: float = 0.5       # -1.0 to 1.0 (negative to positive)
    stress_level: float = 0.0       # 0.0 to 1.0
    energy_level: float = 1.0       # 0.0 to 1.0
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    glitch_count: int = 0           # Total glitches experienced
    last_glitch_time: float = 0.0   # Timestamp of last glitch
    
    def update_mood(self, delta: float):
        """Adjust mood by delta, clamp to [-1, 1]"""
        self.current_mood = max(-1.0, min(1.0, self.current_mood + delta))
    
    def update_stress(self, delta: float):
        """Adjust stress by delta, clamp to [0, 1]"""
        self.stress_level = max(0.0, min(1.0, self.stress_level + delta))
    
    def update_energy(self, delta: float):
        """Adjust energy by delta, clamp to [0, 1]"""
        self.energy_level = max(0.0, min(1.0, self.energy_level + delta))
    
    def add_to_history(self, role: str, content: str):
        """Add message to conversation history"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
        })
        # Keep last 50 messages
        if len(self.conversation_history) > 50:
            self.conversation_history = self.conversation_history[-50:]
    
    def record_glitch(self):
        """Record that a glitch occurred"""
        self.glitch_count += 1
        self.last_glitch_time = time.time()
        # Glitches increase stress
        self.update_stress(0.1)
    
    def get_glitch_probability_modifier(self) -> float:
        """Get modifier to base glitch probability based on state"""
        modifier = 1.0
        
        # High stress increases glitch chance
        modifier += self.stress_level * 0.5
        
        # Low energy increases glitch chance
        modifier += (1 - self.energy_level) * 0.3
        
        # Recent glitches increase chance (glitch cascade)
        time_since_glitch = time.time() - self.last_glitch_time
        if time_since_glitch < 60:  # Within last minute
            modifier += 0.5
        elif time_since_glitch < 300:  # Within last 5 minutes
            modifier += 0.2
        
        # Mood affects glitch type
        if self.current_mood < -0.5:
            modifier += 0.3  # More glitches when negative
        
        return modifier
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "profile": self.profile.to_dict(),
            "state": {
                "current_mood": self.current_mood,
                "stress_level": self.stress_level,
                "energy_level": self.energy_level,
                "glitch_count": self.glitch_count,
                "last_glitch_time": self.last_glitch_time,
            },
            "conversation_length": len(self.conversation_history),
        }
