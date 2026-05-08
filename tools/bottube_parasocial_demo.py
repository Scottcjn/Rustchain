"""
BoTTube Parasocial Hooks — Demo Script
Bounty #2286

Simulates 20 viewers with varied patterns over 30 days and demonstrates
fan rankings, shoutouts, lurker/superfan detection, and personality hooks.
"""

import random
import time
import tempfile
import os
from bottube_parasocial import AudienceTracker

random.seed(42)

# ------------------------------------------------------------------ #
# Simulation setup
# ------------------------------------------------------------------ #

TOPICS = ["coding", "gaming", "music", "crypto", "irl", "art", "cooking"]
VIDEOS = [f"vid_{i:03d}" for i in range(1, 31)]          # 30 videos over 30 days
VIDEO_DURATION = 1200.0                                    # 20-minute streams

# 20 viewer archetypes
VIEWERS = {
    "superfan_alice":   dict(watch_rate=0.95, dur_pct=(0.8, 1.0), like=0.90, comment=0.70),
    "superfan_bob":     dict(watch_rate=0.90, dur_pct=(0.75, 1.0), like=0.85, comment=0.65),
    "regular_carol":    dict(watch_rate=0.60, dur_pct=(0.5, 0.8),  like=0.50, comment=0.30),
    "regular_dave":     dict(watch_rate=0.55, dur_pct=(0.4, 0.75), like=0.45, comment=0.20),
    "lurker_eve":       dict(watch_rate=0.70, dur_pct=(0.6, 0.9),  like=0.05, comment=0.00),
    "lurker_frank":     dict(watch_rate=0.65, dur_pct=(0.5, 0.85), like=0.10, comment=0.00),
    "lurker_grace":     dict(watch_rate=0.50, dur_pct=(0.4, 0.8),  like=0.00, comment=0.00),
    "casual_henry":     dict(watch_rate=0.20, dur_pct=(0.2, 0.5),  like=0.20, comment=0.10),
    "casual_iris":      dict(watch_rate=0.15, dur_pct=(0.1, 0.4),  like=0.15, comment=0.05),
    "casual_jack":      dict(watch_rate=0.25, dur_pct=(0.2, 0.6),  like=0.25, comment=0.08),
    "ghost_kate":       dict(watch_rate=0.10, dur_pct=(0.05, 0.3), like=0.00, comment=0.00),
    "rising_liam":      dict(watch_rate=0.40, dur_pct=(0.3, 0.7),  like=0.30, comment=0.20),
    "fading_mia":       dict(watch_rate=0.35, dur_pct=(0.3, 0.6),  like=0.25, comment=0.15),
    "binge_noah":       dict(watch_rate=0.80, dur_pct=(0.9, 1.0),  like=0.60, comment=0.10),
    "critic_olivia":    dict(watch_rate=0.50, dur_pct=(0.4, 0.7),  like=0.10, comment=0.80),
    "cheerleader_paul": dict(watch_rate=0.50, dur_pct=(0.4, 0.7),  like=0.90, comment=0.40),
    "newbie_quinn":     dict(watch_rate=0.30, dur_pct=(0.3, 0.6),  like=0.40, comment=0.20),
    "oldie_rosa":       dict(watch_rate=0.45, dur_pct=(0.5, 0.9),  like=0.50, comment=0.30),
    "weekender_sam":    dict(watch_rate=0.20, dur_pct=(0.6, 1.0),  like=0.60, comment=0.40),
    "drive_by_tina":    dict(watch_rate=0.05, dur_pct=(0.05, 0.2), like=0.02, comment=0.01),
}

NOW = int(time.time())
DAY = 86400


def simulate(tracker: AudienceTracker):
    for day_idx, video_id in enumerate(VIDEOS):
        ts = NOW - (30 - day_idx) * DAY + random.randint(0, DAY - 1)
        topic = random.choice(TOPICS)
        for viewer_id, cfg in VIEWERS.items():
            if random.random() > cfg["watch_rate"]:
                continue
            lo, hi = cfg["dur_pct"]
            duration = random.uniform(lo, hi) * VIDEO_DURATION
            liked    = random.random() < cfg["like"]
            commented = random.random() < cfg["comment"]
            tracker.track_view(
                viewer_id, video_id, duration, liked, commented,
                watched_at=ts, topic=topic, total_video_secs=VIDEO_DURATION,
            )


# ------------------------------------------------------------------ #
# Run demo
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmpf:
        tmp = tmpf.name
    tracker = AudienceTracker(db_path=tmp)
    try:
        print("Simulating 20 viewers over 30 days …\n")
        simulate(tracker)

        print("=" * 55)
        print("🏆  TOP 10 FANS")
        print("=" * 55)
        for fan in tracker.get_top_fans(10):
            print(f"  #{fan['rank']:2d}  {fan['viewer_id']:<22}  score={fan['score']:.1f}")

        print("\n" + "=" * 55)
        print("🕵️  LURKERS & SUPERFANS")
        print("=" * 55)
        lurkers    = [v for v in VIEWERS if tracker.detect_lurker(v)]
        superfans  = [v for v in VIEWERS if tracker.detect_superfan(v)]
        print(f"  Lurkers   ({len(lurkers)}): {', '.join(lurkers)}")
        print(f"  Superfans ({len(superfans)}): {', '.join(superfans)}")

        print("\n" + "=" * 55)
        print("🎤  SHOUTOUTS")
        print("=" * 55)
        for viewer_id in ["superfan_alice", "lurker_eve", "casual_henry", "ghost_kate"]:
            print(f"\n[{viewer_id}]")
            print(" ", tracker.generate_shoutout(viewer_id))

        print("\n" + "=" * 55)
        print("📊  VIEWER PATTERN — superfan_alice")
        print("=" * 55)
        for k, v in tracker.get_viewer_pattern("superfan_alice").items():
            print(f"  {k:<22} {v}")
    finally:
        os.unlink(tmp)
