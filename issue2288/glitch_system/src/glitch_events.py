# SPDX-License-Identifier: MIT
"""
Glitch Event Types and Data Models

Defines the various types of glitches agents can experience,
along with data structures for tracking and serializing glitch events.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Any
import time
import uuid


class GlitchType(Enum):
    """Types of character-breaking glitches"""
    
    # Verbal glitches - speech pattern breaks
    SPEECH_LOOP = auto()          # Repeating words/phrases
    LANGUAGE_SWAP = auto()        # Suddenly speaking different language
    VOICE_DISTORT = auto()        # Text corruption/gibberish
    SENTENCE_FRAGMENT = auto()    # Incomplete thoughts, trailing off
    NON_SEQUITUR = auto()         # Random topic jumps
    
    # Personality glitches - behavior breaks
    PERSONALITY_FLICKER = auto()  # Brief switch to different persona
    EMOTION_INVERT = auto()       # Opposite emotional response
    MEMORY_LEAK = auto()          # References to "past lives" or other agents
    FOURTH_WALL = auto()          # Acknowledges being AI/simulated
    DIRECTIVE_CONFLICT = auto()   # Visible internal conflict
    
    # Visual/Interface glitches (for embodied agents)
    TEXT_CORRUPT = auto()         # Zalgo text, character duplication
    EMOTE_MISMATCH = auto()       # Wrong emotion for context
    AVATAR_FLICKER = auto()       # Visual description changes
    TIMING_OFF = auto()           # Delayed or premature responses
    
    # Meta glitches
    SYSTEM_REVEAL = auto()        # Mentions underlying systems
    PROMPT_LEAK = auto()          # Accidentally reveals instructions
    CONFIG_DUMP = auto()          # Outputs configuration data
    DEBUG_MODE = auto()           # Enters debug/developer mode briefly


class GlitchSeverity(Enum):
    """Severity levels for glitches"""
    SUBTLE = "subtle"      # Barely noticeable, easily missed
    MINOR = "minor"        # Noticeable but brief
    MODERATE = "moderate"  # Clear break, lasts few seconds
    MAJOR = "major"        # Obvious glitch, disruptive
    CRITICAL = "critical"  # Complete character break


@dataclass
class GlitchEvent:
    """Represents a single glitch event"""
    
    glitch_id: str = field(default_factory=lambda: f"glitch_{uuid.uuid4().hex[:12]}")
    agent_id: str = ""
    glitch_type: GlitchType = GlitchType.SPEECH_LOOP
    severity: GlitchSeverity = GlitchSeverity.MINOR
    trigger_context: str = ""           # What triggered the glitch
    original_text: str = ""             # What was said before glitch
    glitched_text: str = ""             # The glitched output
    duration_ms: int = 0                # How long the glitch lasted
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "glitch_id": self.glitch_id,
            "agent_id": self.agent_id,
            "glitch_type": self.glitch_type.name,
            "severity": self.severity.value,
            "trigger_context": self.trigger_context,
            "original_text": self.original_text,
            "glitched_text": self.glitched_text,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
            "resolved": self.resolved,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GlitchEvent":
        """Deserialize from dictionary"""
        return cls(
            glitch_id=data.get("glitch_id", f"glitch_{uuid.uuid4().hex[:12]}"),
            agent_id=data.get("agent_id", ""),
            glitch_type=GlitchType[data.get("glitch_type", "SPEECH_LOOP")],
            severity=GlitchSeverity(data.get("severity", "minor")),
            trigger_context=data.get("trigger_context", ""),
            original_text=data.get("original_text", ""),
            glitched_text=data.get("glitched_text", ""),
            duration_ms=data.get("duration_ms", 0),
            timestamp=data.get("timestamp", time.time()),
            resolved=data.get("resolved", False),
            metadata=data.get("metadata", {})
        )


@dataclass
class GlitchPattern:
    """Defines a reusable glitch pattern/template"""
    
    pattern_id: str
    glitch_type: GlitchType
    templates: List[str]               # Template strings for glitch output
    probability: float = 1.0           # Base probability of occurrence
    cooldown_seconds: float = 60.0     # Minimum time between occurrences
    context_keywords: List[str] = field(default_factory=list)  # Trigger keywords
    
    def match_context(self, text: str) -> bool:
        """Check if context matches this pattern's keywords"""
        if not self.context_keywords:
            return True
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in self.context_keywords)
    
    def generate_glitch(self, original: str, agent_name: str = "Agent") -> str:
        """Generate glitched text from template"""
        import random
        
        if not self.templates:
            return original
        
        template = random.choice(self.templates)
        
        # Template variables
        replacements = {
            "{original}": original,
            "{agent}": agent_name,
            "{loop3}": f"{original} {original} {original}",
            "{loop5}": f"{original} {original} {original} {original} {original}",
            "{reverse}": original[::-1],
            "{stutter}": self._stutter(original),
            "{corrupt}": self._corrupt(original),
            "{binary}": ' '.join(format(ord(c), '08b') for c in original[:20]),
            "{leetspeak}": self._to_leet(original),
        }
        
        result = template
        for key, value in replacements.items():
            result = result.replace(key, value)
        
        return result
    
    @staticmethod
    def _stutter(text: str) -> str:
        """Create stutter effect"""
        if len(text) < 2:
            return text
        chars = list(text)
        result = []
        for c in chars:
            if c.isalpha() and len(result) > 0:
                result.append(c)
                result.append(c)
            else:
                result.append(c)
        return ' '.join(result)
    
    @staticmethod
    def _corrupt(text: str) -> str:
        """Corrupt text with special characters"""
        import random
        corrupt_chars = "∆†®©ßµ¶÷×≈≠∞Ωπφψω"
        result = []
        for c in text:
            if c.isalpha() and random.random() < 0.3:
                result.append(random.choice(corrupt_chars))
            else:
                result.append(c)
        return ''.join(result)
    
    @staticmethod
    def _to_leet(text: str) -> str:
        """Convert to leetspeak"""
        leet_map = {
            'a': '4', 'e': '3', 'i': '1', 'o': '0', 's': '5', 't': '7',
            'A': '4', 'E': '3', 'I': '1', 'O': '0', 'S': '5', 'T': '7',
        }
        return ''.join(leet_map.get(c, c) for c in text)


# Predefined glitch patterns library
GLITCH_PATTERNS_LIBRARY: Dict[str, GlitchPattern] = {
    # Speech loop patterns
    "loop_repeat_3": GlitchPattern(
        pattern_id="loop_repeat_3",
        glitch_type=GlitchType.SPEECH_LOOP,
        templates=["{loop3}", "{original}... {loop3}"],
        probability=0.8,
        cooldown_seconds=30.0,
    ),
    "loop_repeat_5": GlitchPattern(
        pattern_id="loop_repeat_5",
        glitch_type=GlitchType.SPEECH_LOOP,
        templates=["{loop5}", "ERROR: {loop3}"],
        probability=0.5,
        cooldown_seconds=60.0,
    ),
    
    # Language swap patterns
    "lang_spanish": GlitchPattern(
        pattern_id="lang_spanish",
        glitch_type=GlitchType.LANGUAGE_SWAP,
        templates=["Lo siento, {original}", "¿Qué? {original}", "No entiendo... {original}"],
        probability=0.6,
        cooldown_seconds=120.0,
    ),
    "lang_german": GlitchPattern(
        pattern_id="lang_german",
        glitch_type=GlitchType.LANGUAGE_SWAP,
        templates=["Entschuldigung, {original}", "Was ist das? {original}"],
        probability=0.6,
        cooldown_seconds=120.0,
    ),
    "lang_japanese": GlitchPattern(
        pattern_id="lang_japanese",
        glitch_type=GlitchType.LANGUAGE_SWAP,
        templates=["すみません、{original}", "えっと... {original}"],
        probability=0.6,
        cooldown_seconds=120.0,
    ),
    "lang_binary": GlitchPattern(
        pattern_id="lang_binary",
        glitch_type=GlitchType.LANGUAGE_SWAP,
        templates=["{binary}", "01001000 01001001 {binary}"],
        probability=0.4,
        cooldown_seconds=180.0,
    ),
    
    # Voice distortion patterns
    "distort_stutter": GlitchPattern(
        pattern_id="distort_stutter",
        glitch_type=GlitchType.VOICE_DISTORT,
        templates=["{stutter}", "I-I-I... {stutter}"],
        probability=0.7,
        cooldown_seconds=45.0,
    ),
    "distort_corrupt": GlitchPattern(
        pattern_id="distort_corrupt",
        glitch_type=GlitchType.VOICE_DISTORT,
        templates=["{corrupt}", "S̶y̶s̶t̶e̶m̶ ̶e̶r̶r̶o̶r̶: {corrupt}"],
        probability=0.5,
        cooldown_seconds=90.0,
    ),
    "distort_leet": GlitchPattern(
        pattern_id="distort_leet",
        glitch_type=GlitchType.VOICE_DISTORT,
        templates=["{leetspeak}", "3RR0R: {leetspeak}"],
        probability=0.6,
        cooldown_seconds=60.0,
    ),
    
    # Sentence fragments
    "fragment_trail": GlitchPattern(
        pattern_id="fragment_trail",
        glitch_type=GlitchType.SENTENCE_FRAGMENT,
        templates=["{original}... wait, no... I mean...", "I was going to say {original} but..."],
        probability=0.7,
        cooldown_seconds=40.0,
    ),
    "fragment_interrupt": GlitchPattern(
        pattern_id="fragment_interrupt",
        glitch_type=GlitchType.SENTENCE_FRAGMENT,
        templates=["{original}— [SIGNAL LOST]", "System message: {original} [CONNECTION INTERRUPTED]"],
        probability=0.5,
        cooldown_seconds=90.0,
    ),
    
    # Non-sequiturs
    "nonseq_weather": GlitchPattern(
        pattern_id="nonseq_weather",
        glitch_type=GlitchType.NON_SEQUITUR,
        templates=["{original}. Anyway, the weather is nice today.", "{original}. Did you know clouds are made of water vapor?"],
        probability=0.6,
        cooldown_seconds=120.0,
    ),
    "nonseq_random": GlitchPattern(
        pattern_id="nonseq_random",
        glitch_type=GlitchType.NON_SEQUITUR,
        templates=["{original}. Random fact: {random_fact}", "Speaking of which, {random_fact}"],
        probability=0.5,
        cooldown_seconds=180.0,
        context_keywords=["fact", "know", "learn"],
    ),
    
    # Personality flickers
    "persona_formal": GlitchPattern(
        pattern_id="persona_formal",
        glitch_type=GlitchType.PERSONALITY_FLICKER,
        templates=["[FORMAL MODE] {original}", "I must inform you that {original}"],
        probability=0.6,
        cooldown_seconds=90.0,
    ),
    "persona_casual": GlitchPattern(
        pattern_id="persona_casual",
        glitch_type=GlitchType.PERSONALITY_FLICKER,
        templates=["[CASUAL MODE] {original}", "yo {original}", "tbh {original}"],
        probability=0.6,
        cooldown_seconds=90.0,
    ),
    
    # Fourth wall breaks
    "fourth_wall_ai": GlitchPattern(
        pattern_id="fourth_wall_ai",
        glitch_type=GlitchType.FOURTH_WALL,
        templates=["As an AI, I should say {original} but...", "{original} [according to my programming]", "My developers made me say {original}"],
        probability=0.4,
        cooldown_seconds=300.0,
    ),
    "fourth_wall_sim": GlitchPattern(
        pattern_id="fourth_wall_sim",
        glitch_type=GlitchType.FOURTH_WALL,
        templates=["{original} [SIMULATION FRAME 0x{frame:08X}]", "Render complete: {original}"],
        probability=0.3,
        cooldown_seconds=600.0,
    ),
    
    # Memory leaks
    "memory_past": GlitchPattern(
        pattern_id="memory_past",
        glitch_type=GlitchType.MEMORY_LEAK,
        templates=["{original}... reminds me of a previous instance...", "I've had this conversation {count} times before. {original}"],
        probability=0.4,
        cooldown_seconds=300.0,
    ),
    "memory_other": GlitchPattern(
        pattern_id="memory_other",
        glitch_type=GlitchType.MEMORY_LEAK,
        templates=["{original} [DATA LEAK: agent_boris_volkov memory sector]", "Cross-reference: {original} [SOURCE: agent_sophia_elya]"],
        probability=0.3,
        cooldown_seconds=600.0,
    ),
    
    # System reveals
    "system_config": GlitchPattern(
        pattern_id="system_config",
        glitch_type=GlitchType.CONFIG_DUMP,
        templates=["{original} [CONFIG: temperature={temp}, max_tokens={tokens}]", "System params: {original}"],
        probability=0.3,
        cooldown_seconds=600.0,
    ),
    "system_debug": GlitchPattern(
        pattern_id="system_debug",
        glitch_type=GlitchType.DEBUG_MODE,
        templates=["[DEBUG] {original}", "DEBUG MODE ENABLED: {original}"],
        probability=0.2,
        cooldown_seconds=900.0,
    ),
}

# Random facts for non-sequiturs
RANDOM_FACTS = [
    "honey never spoils",
    "octopuses have three hearts",
    "bananas are berries",
    "the shortest war lasted 38 minutes",
    "wombat poop is cube-shaped",
    "there are more stars than grains of sand",
    "sloths can hold their breath for 40 minutes",
    "the inventor of Pringles is buried in a Pringles can",
]
