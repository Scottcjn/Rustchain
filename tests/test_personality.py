"""
Tests for the BoTTube Personality Engine.
Run with: pytest tests/test_personality.py -v
"""

import sys
import os
import pytest

# Allow importing from tools/ without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from bottube_personality import PersonalityEngine, PRESETS, TRAIT_NAMES, MOOD_EVENTS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_engine(preset: str = None, **kwargs) -> PersonalityEngine:
    eng = PersonalityEngine(db_path=":memory:")
    cfg = dict(kwargs)
    if preset:
        cfg["preset"] = preset
    if cfg:
        eng.load_personality(cfg)
    return eng


# ---------------------------------------------------------------------------
# Trait loading
# ---------------------------------------------------------------------------

class TestLoadPersonality:

    def test_preset_professor(self):
        eng = make_engine("professor")
        assert eng.traits.formality >= 0.8
        assert eng.traits.humor <= 0.2

    def test_preset_comedian(self):
        eng = make_engine("comedian")
        assert eng.traits.humor >= 0.9
        assert eng.traits.sarcasm >= 0.75

    def test_preset_supportive(self):
        eng = make_engine("supportive")
        assert eng.traits.empathy >= 0.9
        assert eng.traits.sarcasm <= 0.1

    def test_preset_edgy(self):
        eng = make_engine("edgy")
        assert eng.traits.sarcasm >= 0.85
        assert eng.traits.empathy <= 0.15

    def test_preset_zen(self):
        eng = make_engine("zen")
        assert eng.traits.verbosity <= 0.2
        assert eng.traits.enthusiasm <= 0.3

    def test_all_presets_exist(self):
        for name in PRESETS:
            eng = make_engine(name)
            for trait in TRAIT_NAMES:
                val = getattr(eng.traits, trait)
                assert 0.0 <= val <= 1.0, f"{name}.{trait} out of range: {val}"

    def test_override_single_trait(self):
        eng = make_engine("professor", humor=0.9)
        assert eng.traits.humor == pytest.approx(0.9)
        assert eng.traits.formality >= 0.8  # rest of preset intact

    def test_unknown_preset_raises(self):
        with pytest.raises(ValueError, match="Unknown preset"):
            make_engine("unicorn")

    def test_trait_clamping(self):
        eng = make_engine(humor=1.5, sarcasm=-0.3)
        assert eng.traits.humor == pytest.approx(1.0)
        assert eng.traits.sarcasm == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# style_text
# ---------------------------------------------------------------------------

class TestStyleText:

    def test_returns_string(self):
        eng = make_engine()
        assert isinstance(eng.style_text("Hello world"), str)

    def test_high_enthusiasm_adds_exclamation(self):
        eng = make_engine(enthusiasm=0.95)
        result = eng.style_text("This is great")
        assert "!" in result

    def test_low_verbosity_shortens_text(self):
        eng = make_engine(verbosity=0.1)
        long = "This is a long sentence. It has a second sentence. And a third."
        result = eng.style_text(long)
        # Should be truncated to first sentence
        assert len(result) < len(long)

    def test_low_formality_lowercases(self):
        eng = make_engine(formality=0.1)
        result = eng.style_text("Hello World")
        assert result == result.lower()


# ---------------------------------------------------------------------------
# Greeting & sign-off
# ---------------------------------------------------------------------------

class TestGreetingSignOff:

    def test_greeting_contains_name(self):
        eng = make_engine("supportive")
        result = eng.generate_greeting("Alice")
        assert "Alice" in result

    def test_greeting_no_name(self):
        eng = make_engine("zen")
        result = eng.generate_greeting()
        assert isinstance(result, str) and len(result) > 0

    def test_sign_off_is_string(self):
        for preset in PRESETS:
            eng = make_engine(preset)
            assert isinstance(eng.generate_sign_off(), str)

    def test_professor_greeting_formal(self):
        eng = make_engine("professor")
        result = eng.generate_greeting()
        # Should be capitalised and proper
        assert result[0] == result[0].upper()


# ---------------------------------------------------------------------------
# react_to_comment
# ---------------------------------------------------------------------------

class TestReactToComment:

    def test_react_positive(self):
        eng = make_engine("supportive")
        result = eng.react_to_comment("This stream is amazing!")
        assert isinstance(result, str) and len(result) > 0

    def test_react_negative(self):
        eng = make_engine("edgy")
        result = eng.react_to_comment("This is terrible and boring")
        assert isinstance(result, str) and len(result) > 0

    def test_react_neutral(self):
        eng = make_engine("professor")
        result = eng.react_to_comment("What do you think about the halving?")
        assert isinstance(result, str)

    def test_positive_comment_raises_mood(self):
        eng = make_engine("comedian")
        before = eng.get_mood_score()
        eng.react_to_comment("This is so cool and amazing!")
        assert eng.get_mood_score() > before


# ---------------------------------------------------------------------------
# Mood tracking
# ---------------------------------------------------------------------------

class TestMoodTracking:

    def test_default_mood_neutral(self):
        eng = make_engine()
        assert eng.get_mood() == "neutral"

    def test_mood_shift_viral_video(self):
        eng = make_engine()
        eng.mood_shift("viral_video")
        assert eng.get_mood() in ("good", "elated")

    def test_mood_shift_negative(self):
        eng = make_engine()
        eng.mood_shift("negative_comment")
        eng.mood_shift("negative_comment")
        eng.mood_shift("negative_comment")
        assert eng.get_mood() in ("sour", "moody")

    def test_mood_score_clamped(self):
        eng = make_engine()
        for _ in range(20):
            eng.mood_shift("viral_video")
        assert eng.get_mood_score() <= 1.0

    def test_unknown_event_raises(self):
        eng = make_engine()
        with pytest.raises(ValueError, match="Unknown event"):
            eng.mood_shift("alien_invasion")

    def test_all_events_accepted(self):
        eng = make_engine()
        for ev in MOOD_EVENTS:
            eng.mood_shift(ev)  # should not raise

    def test_mood_history_persisted(self):
        eng = make_engine()
        eng.mood_shift("milestone")
        eng.mood_shift("positive_comment")
        history = eng.mood_history(limit=10)
        assert len(history) >= 2
        assert history[0]["event"] == "positive_comment"  # most recent first
