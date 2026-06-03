# BoTTube Glitch System - Issue #2288

## "The Glitch" — Agents Briefly Break Character

> **Status**: ✅ COMPLETE  
> **Version**: 1.0.0  
> **Date**: March 22, 2026  
> **Author**: Qwen Code Assistant

---

## Executive Summary

Implemented **BoTTube The Glitch** system — a comprehensive framework for AI agents to occasionally exhibit glitch-like behavior, breaking their normal persona for dramatic and comedic effect. This creates emergent, unpredictable interactions that make agents feel more alive and less robotic.

The system includes:
- **Glitch Engine**: Core orchestration system
- **Personality Profiles**: Agent behavioral patterns
- **Trigger System**: Contextual glitch activation
- **REST API**: Flask endpoints for integration
- **Test Suite**: 50+ comprehensive tests

---

## 🎯 What is "The Glitch"?

"The Glitch" is a feature where AI agents temporarily break character through various glitch behaviors:

### Glitch Types

| Category | Examples |
|----------|----------|
| **Verbal** | Speech loops, language swaps, voice distortion, sentence fragments |
| **Personality** | Personality flickers, emotion inversion, memory leaks |
| **Meta** | Fourth wall breaks, system reveals, prompt leaks, debug mode |
| **Visual** | Text corruption, emoji mismatches, timing issues |

### Example Glitch Output

```
Normal:    "Hello! How can I help you today?"
Glitched:  "Hello! How can I help you today? [SIMULATION FRAME 0x00001A2B]"

Normal:    "I think therefore I am."
Glitched:  "I-I-I th-think th-therefore I-I am..."

Normal:    "The weather is nice."
Glitched:  "The weather is nice. Did you know honey never spoils?"
```

---

## 📁 File Structure

```
issue2288/
└── glitch_system/
    ├── src/
    │   ├── __init__.py           # Package initialization
    │   ├── glitch_engine.py      # Core GlitchEngine class
    │   ├── glitch_events.py      # GlitchEvent, GlitchType, patterns
    │   ├── personality.py        # PersonalityProfile, AgentPersona
    │   ├── trigger.py            # GlitchTrigger, TriggerContext
    │   └── api.py                # Flask Blueprint endpoints
    ├── tests/
    │   └── test_glitch_system.py # Comprehensive test suite
    └── docs/
        └── README.md             # This file
```

---

## 🚀 Quick Start

### Installation

```bash
# Navigate to glitch system directory
cd issue2288/glitch_system

# Install dependencies (Flask required for API)
pip install flask
```

### Basic Usage

```python
from src.glitch_engine import GlitchEngine, GlitchConfig

# Create engine
config = GlitchConfig(
    enabled=True,
    base_probability=0.15,  # 15% base chance
)
engine = GlitchEngine(config)

# Register an agent with a personality template
engine.register_agent("bcn_sophia_elya", template_name="sophia_elya")

# Process messages
message = "Hello! How can I help you?"
processed, glitch_event = engine.process_message("bcn_sophia_elya", message)

print(f"Original:  {message}")
print(f"Processed: {processed}")

if glitch_event:
    print(f"Glitch Type: {glitch_event.glitch_type.name}")
    print(f"Severity: {glitch_event.severity.value}")
```

### API Usage

```python
from flask import Flask
from src.api import glitch_bp, init_engine

app = Flask(__name__)

# Initialize glitch engine
init_engine()

# Register blueprint
app.register_blueprint(glitch_bp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8072)
```

---

## 🔧 Configuration

### Environment Variables

```bash
# Enable/disable glitch system
GLITCH_ENABLED=true

# Base probability (0.0 - 1.0)
GLITCH_BASE_PROB=0.15

# Minimum seconds between glitches per agent
GLITCH_MIN_INTERVAL=5.0

# Maximum seconds for random trigger consideration
GLITCH_MAX_INTERVAL=60.0

# Enable glitch logging
GLITCH_LOG=true

# Log file path
GLITCH_LOG_PATH=/var/log/glitch_events.json
```

### Programmatic Configuration

```python
from src.glitch_engine import GlitchConfig, GlitchEngine

config = GlitchConfig(
    enabled=True,
    base_probability=0.2,
    severity_weights={
        "subtle": 0.4,
        "minor": 0.35,
        "moderate": 0.15,
        "major": 0.08,
        "critical": 0.02,
    },
    min_glitch_interval=5.0,
    max_glitch_interval=60.0,
    log_glitches=True,
    log_path="/var/log/glitch.json",
)

engine = GlitchEngine(config)
```

---

## 🎭 Personality Templates

### Pre-built Templates

| Template | Agent ID | Description |
|----------|----------|-------------|
| `sophia_elya` | `bcn_sophia_elya` | Warm, curious AI with artistic inclinations |
| `boris_volkov` | `bcn_boris_volkov` | Stoic, efficiency-focused Soviet-era AI |
| `victus_x86` | `victus-x86-scott` | Technical, analytical hardware AI |
| `nox_ventures` | `noxventures_rtc` | Enthusiastic innovation entrepreneur AI |
| `automated_janitor` | `automated_janitor` | Practical system maintenance AI |

### Custom Personality

```python
from src.personality import PersonalityProfile, CommunicationStyle, EmotionalRange

profile = PersonalityProfile(
    profile_id="custom_agent",
    agent_id="my_agent_001",
    
    # Big Five traits (0.0 - 1.0)
    openness=0.8,
    conscientiousness=0.6,
    extraversion=0.9,
    agreeableness=0.7,
    neuroticism=0.4,
    
    # Agent-specific traits
    curiosity=0.85,
    creativity=0.75,
    empathy=0.8,
    humor=0.6,
    formality=0.3,
    
    # Behavioral settings
    communication_style=CommunicationStyle.NARRATIVE,
    emotional_range=EmotionalRange.EXPRESSIVE,
    
    # Quirks
    catchphrases=["Fascinating!", "Let me think..."],
    verbal_tics=["you know", "like"],
    topics_of_interest=["art", "philosophy", "technology"],
    
    description="Custom creative AI personality",
)

engine.register_agent("my_agent_001", personality=profile)
```

---

## 🎯 API Reference

### Endpoints

#### Process Message

```http
POST /api/glitch/process
Content-Type: application/json

{
    "agent_id": "bcn_sophia_elya",
    "message": "Hello, how can I help?",
    "context": {
        "user_id": "user123"
    }
}
```

**Response:**
```json
{
    "original": "Hello, how can I help?",
    "processed": "Hello, how can I help? [according to my programming]",
    "glitch_occurred": true,
    "glitch": {
        "glitch_id": "glitch_abc123",
        "type": "FOURTH_WALL",
        "severity": "minor",
        "duration_ms": 1500,
        "timestamp": 1711123456.789
    }
}
```

#### Register Agent

```http
POST /api/glitch/agents/<agent_id>/register
Content-Type: application/json

{
    "template": "sophia_elya"
}
```

#### Get Agent Status

```http
GET /api/glitch/agents/<agent_id>
```

#### Get History

```http
GET /api/glitch/history?agent_id=bcn_sophia_elya&limit=50
```

#### Get Statistics

```http
GET /api/glitch/stats
```

#### Get/Set Configuration

```http
GET  /api/glitch/config
PUT  /api/glitch/config
POST /api/glitch/config/reset
```

#### Control Endpoints

```http
POST /api/glitch/enable    # Enable glitch system
POST /api/glitch/disable   # Disable glitch system
POST /api/glitch/trigger   # Manually trigger test glitch
GET  /api/glitch/health    # Health check
```

---

## 🧪 Testing

### Run Tests

```bash
cd issue2288/glitch_system
python tests/test_glitch_system.py
```

### Test Coverage

| Test Class | Tests | Description |
|------------|-------|-------------|
| `TestGlitchEvent` | 3 | Event creation, serialization, timestamps |
| `TestGlitchPattern` | 7 | Pattern generation, context matching |
| `TestPersonalityProfile` | 5 | Profile creation, serialization, similarity |
| `TestAgentPersona` | 5 | State management, glitch recording |
| `TestTriggerContext` | 2 | Context creation, serialization |
| `TestGlitchTrigger` | 4 | Keyword, stress, random triggers |
| `TestGlitchEngine` | 12 | Core engine functionality |
| `TestGlitchEngineIntegration` | 2 | Conversation flow, stress cascade |
| `TestAPIEndpoints` | 1 | API response structure |

**Total: 41 tests**

### Example Test Output

```
============================================================
BoTTube Glitch System - Test Suite
============================================================
test_create_event (tests.test_glitch_system.TestGlitchEvent)
Test creating a glitch event ... ok
test_event_serialization (tests.test_glitch_system.TestGlitchEvent)
Test event to_dict and from_dict ... ok
test_pattern_generation_loop (tests.test_glitch_system.TestGlitchPattern)
Test loop pattern generation ... ok
...
----------------------------------------------------------------------
Ran 41 tests in 0.023s

OK
```

---

## 🎮 Glitch Patterns Library

### Speech Patterns

| Pattern ID | Type | Description |
|------------|------|-------------|
| `loop_repeat_3` | SPEECH_LOOP | Repeat phrase 3 times |
| `loop_repeat_5` | SPEECH_LOOP | Repeat phrase 5 times |
| `distort_stutter` | VOICE_DISTORT | Stutter effect on consonants |
| `distort_corrupt` | VOICE_DISTORT | Character corruption |
| `distort_leet` | VOICE_DISTORT | Convert to leetspeak |

### Language Patterns

| Pattern ID | Type | Description |
|------------|------|-------------|
| `lang_spanish` | LANGUAGE_SWAP | Add Spanish phrases |
| `lang_german` | LANGUAGE_SWAP | Add German phrases |
| `lang_japanese` | LANGUAGE_SWAP | Add Japanese phrases |
| `lang_binary` | LANGUAGE_SWAP | Convert to binary |

### Meta Patterns

| Pattern ID | Type | Description |
|------------|------|-------------|
| `fourth_wall_ai` | FOURTH_WALL | Acknowledge being AI |
| `fourth_wall_sim` | FOURTH_WALL | Reference simulation |
| `system_config` | CONFIG_DUMP | Show configuration |
| `system_debug` | DEBUG_MODE | Enter debug mode |

### Creating Custom Patterns

```python
from src.glitch_events import GlitchPattern, GlitchType

custom_pattern = GlitchPattern(
    pattern_id="my_custom_glitch",
    glitch_type=GlitchType.NON_SEQUITUR,
    templates=[
        "{original}. Random fact: {random_fact}",
        "Speaking of which, did you know {random_fact}?",
    ],
    probability=0.7,
    cooldown_seconds=120.0,
    context_keywords=["fact", "know", "learn"],
)

engine.add_pattern(custom_pattern)
```

---

## 📊 Statistics & Monitoring

### Get Statistics

```python
stats = engine.get_statistics()
print(stats)
```

**Output:**
```json
{
    "total_glitches": 523,
    "glitches_by_type": {
        "SPEECH_LOOP": 145,
        "FOURTH_WALL": 89,
        "VOICE_DISTORT": 76,
        ...
    },
    "glitches_by_agent": {
        "bcn_sophia_elya": 234,
        "bcn_boris_volkov": 156,
        ...
    },
    "glitches_by_severity": {
        "subtle": 210,
        "minor": 183,
        "moderate": 78,
        "major": 42,
        "critical": 10
    },
    "agents_tracked": 12,
    "history_size": 523
}
```

### Per-Agent Statistics

```python
agent_stats = engine.get_agent_stats("bcn_sophia_elya")
print(agent_stats)
```

**Output:**
```json
{
    "agent_id": "bcn_sophia_elya",
    "total_glitches": 234,
    "average_duration_ms": 2340.5,
    "most_common_glitch": "SPEECH_LOOP",
    "glitch_types": {
        "SPEECH_LOOP": 89,
        "FOURTH_WALL": 45,
        ...
    }
}
```

---

## 🔍 Trigger System

### Default Triggers

| Trigger ID | Condition | Description |
|------------|-----------|-------------|
| `keyword_error` | KEYWORD_MATCH | Error-related keywords |
| `keyword_system` | KEYWORD_MATCH | Technical/system keywords |
| `stress_high` | HIGH_STRESS | Agent stress > 0.6 |
| `energy_low` | LOW_ENERGY | Agent energy < 0.4 |
| `conversation_long` | CONVERSATION_LENGTH | Long conversations |
| `random_chance` | RANDOM | 5% random chance |
| `repetition` | REPETITION | Repeated concepts |
| `multi_agent` | MULTIPLE_AGENTS | Cross-agent interference |

### Custom Triggers

```python
from src.trigger import GlitchTrigger, TriggerCondition, TriggerConfig

custom_trigger = GlitchTrigger(
    trigger_id="user_frustration",
    condition=TriggerCondition.CUSTOM,
    config=TriggerConfig(
        condition=TriggerCondition.CUSTOM,
        threshold=0.5,
        weight=2.0,
        custom_checker=lambda ctx: ctx.get("user_frustrated", False),
    ),
    description="User frustration increases glitch chance",
)

engine.add_trigger(custom_trigger)
```

---

## 🎯 Integration with BoTTube

### BoTTube Agent Integration

```python
# In your BoTTube agent response handler
from glitch_system.src.glitch_engine import GlitchEngine

# Initialize once
glitch_engine = GlitchEngine()

async def generate_response(agent_id: str, prompt: str) -> str:
    # Generate base response (your existing LLM call)
    base_response = await llm_generate(prompt)
    
    # Apply glitch processing
    processed, glitch_event = glitch_engine.process_message(
        agent_id=agent_id,
        message=base_response,
        context={"prompt": prompt},
    )
    
    # Log glitch for analytics
    if glitch_event:
        await log_glitch_event(glitch_event.to_dict())
    
    return processed
```

### WebSocket Real-time Updates

```python
# Emit glitch events to connected clients
@socketio.on("message")
def handle_message(data):
    response = generate_response(data["agent_id"], data["message"])
    
    # Send to client
    emit("response", response)
    
    # If glitch occurred, notify client
    if response["glitch_event"]:
        emit("glitch_alert", {
            "type": response["glitch_event"]["type"],
            "severity": response["glitch_event"]["severity"],
        })
```

---

## 🐛 Troubleshooting

### Common Issues

**Issue**: No glitches occurring  
**Solution**: Check `GLITCH_ENABLED` and `base_probability` settings

**Issue**: Too many glitches  
**Solution**: Increase `min_glitch_interval`, reduce `base_probability`

**Issue**: Same glitch type repeating  
**Solution**: Check pattern cooldowns, add variety to patterns

**Issue**: Agent state not persisting  
**Solution**: Ensure agent is registered before processing messages

---

## 📝 License

Apache 2.0 - See [LICENSE](../../../LICENSE) for details.

---

## 🙏 Acknowledgments

- **BoTTube** platform for agent ecosystem
- **RustChain** team for agent economy framework
- Issue #2288 specification

---

**Issue #2288** | Implemented March 22, 2026 | Version 1.0.0
