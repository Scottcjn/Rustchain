"""
BoTTube Personality Engine — Demo Script
Showcases all five presets and core engine features.
"""

from bottube_personality import PersonalityEngine

DIVIDER = "-" * 60


def demo_preset(name: str, viewer: str = "CryptoFan42"):
    print(f"\n{'='*60}")
    print(f"  PRESET: {name.upper()}")
    print('='*60)

    engine = PersonalityEngine(db_path=":memory:")
    engine.load_personality({"preset": name})

    print(f"Traits  : {vars(engine.traits)}")
    print(f"\nGreeting: {engine.generate_greeting(viewer)}")
    print(f"Sign-off: {engine.generate_sign_off()}")

    comments = [
        "This stream is absolutely amazing!",
        "Honestly this is kind of boring ngl",
        "What do you think about the latest RTC update?",
    ]
    print("\nComment Reactions:")
    for c in comments:
        print(f"  > '{c}'")
        print(f"    → {engine.react_to_comment(c)}")

    print(f"\nMood after reactions: {engine.get_mood()} (score={engine.get_mood_score()})")

    styled = engine.style_text("The blockchain metrics look promising today.")
    print(f"\nStyled text: {styled}")


def demo_mood_shifts():
    print(f"\n{'='*60}")
    print("  MOOD SHIFT DEMO (comedian preset)")
    print('='*60)
    engine = PersonalityEngine(db_path=":memory:")
    engine.load_personality({"preset": "comedian"})

    events = [
        "positive_comment",
        "positive_comment",
        "milestone",
        "negative_comment",
        "quiet_period",
        "viral_video",
    ]
    for ev in events:
        engine.mood_shift(ev)
        print(f"  {ev:25s} → mood={engine.get_mood():8s} score={engine.get_mood_score():.3f}")


def demo_custom_traits():
    print(f"\n{'='*60}")
    print("  CUSTOM TRAITS DEMO")
    print('='*60)
    engine = PersonalityEngine(db_path=":memory:")
    engine.load_personality({
        "preset": "professor",
        "humor": 0.7,       # override: add some humour to the professor
        "enthusiasm": 0.8,
    })
    print(f"Traits  : {vars(engine.traits)}")
    print(f"Greeting: {engine.generate_greeting('Alice')}")
    print(f"Sign-off: {engine.generate_sign_off()}")


if __name__ == "__main__":
    for preset in ("professor", "comedian", "supportive", "edgy", "zen"):
        demo_preset(preset)
    demo_mood_shifts()
    demo_custom_traits()
    print(f"\n{DIVIDER}\nDemo complete.\n")
