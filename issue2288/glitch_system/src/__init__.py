# SPDX-License-Identifier: MIT
"""
BoTTube Glitch System — Agents Break Character
Issue #2288 Implementation

AI agents occasionally exhibit glitch-like behavior, breaking their normal persona
for dramatic/comedic effect. This creates emergent, unpredictable interactions.
"""

from .glitch_engine import GlitchEngine, GlitchEvent, GlitchType
from .personality import PersonalityProfile, AgentPersona
from .trigger import GlitchTrigger, TriggerCondition

__version__ = "1.0.0"
__all__ = [
    "GlitchEngine",
    "GlitchEvent", 
    "GlitchType",
    "PersonalityProfile",
    "AgentPersona",
    "GlitchTrigger",
    "TriggerCondition",
]
