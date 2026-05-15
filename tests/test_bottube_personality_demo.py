from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import bottube_personality_demo as demo


class FakePersonalityEngine:
    instances: list["FakePersonalityEngine"] = []

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.traits = SimpleNamespace(humor=0.1, enthusiasm=0.2, formality=0.9)
        self.loaded_configs: list[dict] = []
        self.reacted_comments: list[str] = []
        self.mood_events: list[str] = []
        FakePersonalityEngine.instances.append(self)

    def load_personality(self, config: dict) -> None:
        self.loaded_configs.append(config)
        for key, value in config.items():
            if key != "preset":
                setattr(self.traits, key, value)

    def generate_greeting(self, viewer: str) -> str:
        return f"hello {viewer}"

    def generate_sign_off(self) -> str:
        return "goodbye"

    def react_to_comment(self, comment: str) -> str:
        self.reacted_comments.append(comment)
        return f"reaction to {comment[:8]}"

    def get_mood(self) -> str:
        return "focused"

    def get_mood_score(self) -> float:
        return 0.42 + (len(self.mood_events) / 100)

    def style_text(self, text: str) -> str:
        return f"styled: {text}"

    def mood_shift(self, event: str) -> None:
        self.mood_events.append(event)


def install_fake_engine(monkeypatch) -> None:
    FakePersonalityEngine.instances = []
    monkeypatch.setattr(demo, "PersonalityEngine", FakePersonalityEngine)


def test_demo_preset_loads_requested_preset_and_reacts_to_sample_comments(monkeypatch, capsys) -> None:
    install_fake_engine(monkeypatch)

    demo.demo_preset("zen", viewer="ViewerOne")

    assert len(FakePersonalityEngine.instances) == 1
    engine = FakePersonalityEngine.instances[0]
    assert engine.db_path == ":memory:"
    assert engine.loaded_configs == [{"preset": "zen"}]
    assert engine.reacted_comments == [
        "This stream is absolutely amazing!",
        "Honestly this is kind of boring ngl",
        "What do you think about the latest RTC update?",
    ]

    output = capsys.readouterr().out
    assert "PRESET: ZEN" in output
    assert "hello ViewerOne" in output
    assert "goodbye" in output
    assert "Mood after reactions: focused" in output
    assert "Styled text: styled: The blockchain metrics look promising today." in output


def test_demo_mood_shifts_applies_events_in_displayed_order(monkeypatch, capsys) -> None:
    install_fake_engine(monkeypatch)

    demo.demo_mood_shifts()

    engine = FakePersonalityEngine.instances[0]
    assert engine.loaded_configs == [{"preset": "comedian"}]
    assert engine.mood_events == [
        "positive_comment",
        "positive_comment",
        "milestone",
        "negative_comment",
        "quiet_period",
        "viral_video",
    ]

    output = capsys.readouterr().out
    assert "MOOD SHIFT DEMO (comedian preset)" in output
    for event in engine.mood_events:
        assert event in output
    assert output.count("mood=focused") == len(engine.mood_events)


def test_demo_custom_traits_loads_professor_overrides(monkeypatch, capsys) -> None:
    install_fake_engine(monkeypatch)

    demo.demo_custom_traits()

    engine = FakePersonalityEngine.instances[0]
    assert engine.loaded_configs == [
        {
            "preset": "professor",
            "humor": 0.7,
            "enthusiasm": 0.8,
        }
    ]
    assert vars(engine.traits)["humor"] == 0.7
    assert vars(engine.traits)["enthusiasm"] == 0.8

    output = capsys.readouterr().out
    assert "CUSTOM TRAITS DEMO" in output
    assert "hello Alice" in output
    assert "goodbye" in output
