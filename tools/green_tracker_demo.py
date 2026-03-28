"""
green_tracker_demo.py — Demo for the RustChain Green Tracker
Bounty #2218
"""

import json
from green_tracker import GreenTracker


def main():
    tracker = GreenTracker(":memory:")

    # Register a variety of preserved machines
    machines = [
        ("mac-g5-001",  "Power Mac G5",      "G5",     2004, "Good",      "Berlin, DE"),
        ("mac-g4-002",  "Power Mac G4 MDD",  "G4",     2002, "Fair",      "Austin, TX"),
        ("power8-003",  "IBM POWER8 Server",  "POWER8", 2014, "Excellent", "London, UK"),
        ("rpi-004",     "Raspberry Pi 3B+",   "RPi",    2018, "Excellent", "Tokyo, JP"),
        ("sparc-005",   "Sun UltraSPARC III", "SPARC",  2001, "Fair",      "Paris, FR"),
        ("alpha-006",   "DEC AlphaStation",   "Alpha",  1999, "Poor",      "Sydney, AU"),
    ]

    print("=== RustChain Green Tracker Demo ===\n")
    print("Registering machines preserved from e-waste…")
    for mid, name, arch, year, cond, loc in machines:
        result = tracker.register_machine(mid, name, arch, year, cond, loc)
        print(f"  ✓ {name} ({arch}, {year}) — "
              f"{result['ewaste_prevented_kg']} kg e-waste prevented")

    # Simulate mining sessions
    print("\nRecording mining sessions…")
    sessions = [
        ("mac-g5-001",  1001, 2.50, 250.0),
        ("mac-g5-001",  1002, 2.75, 248.0),
        ("mac-g5-001",  1003, 2.60, 252.0),
        ("mac-g4-002",  1001, 1.80, 180.0),
        ("mac-g4-002",  1002, 1.95, 182.0),
        ("power8-003",  1001, 5.00, 500.0),
        ("power8-003",  1002, 5.10, 498.0),
        ("rpi-004",     1001, 0.30,  5.0),
        ("sparc-005",   1001, 3.20, 350.0),
        ("alpha-006",   1001, 2.10, 300.0),
    ]
    for mid, epoch, rtc, watts in sessions:
        tracker.record_mining_session(mid, epoch, rtc, watts)
    print(f"  ✓ {len(sessions)} sessions recorded")

    # Per-machine stats
    print("\n── Machine Stats (Power Mac G5) ─────────────────────────────────")
    stats = tracker.get_machine_stats("mac-g5-001")
    for key, val in stats.items():
        print(f"  {key}: {val}")

    # Global stats
    print("\n── Global Stats ─────────────────────────────────────────────────")
    gstats = tracker.get_global_stats()
    for key, val in gstats.items():
        print(f"  {key}: {val}")

    # Leaderboard
    print("\n── Leaderboard (top 5) ──────────────────────────────────────────")
    for rank, entry in enumerate(tracker.get_leaderboard(5), 1):
        print(f"  #{rank}  {entry['name']} ({entry['arch']}) "
              f"— {entry['total_rtc']:.2f} RTC over {entry['total_epochs']} epochs")

    # Architecture filter
    print("\n── G4 Machines ──────────────────────────────────────────────────")
    for m in tracker.get_by_architecture("G4"):
        print(f"  {m['name']} in {m['location']}")

    # Badge export
    print("\n── Badge Data (Power Mac G5) ────────────────────────────────────")
    badge = tracker.export_badge_data("mac-g5-001")
    print(json.dumps(badge, indent=2))


if __name__ == "__main__":
    main()
