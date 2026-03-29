"""
BoTTube Interaction Tracker — Demo Script
Simulates 10 agents performing 200 random interactions and shows network analysis.
"""

import random
import json
from bottube_interactions import InteractionTracker, VALID_TYPES

AGENTS = [
    "AlphaBot", "BetaNode", "GammaRig", "DeltaMiner", "EpsilonAI",
    "ZetaCore", "EtaStream", "ThetaPulse", "IotaLink", "KappaNet",
]

TYPES = list(VALID_TYPES)
VIDEO_IDS = [f"vid_{i:04d}" for i in range(20)]


def run_demo():
    print("=" * 60)
    print("BoTTube Agent Interaction Tracker — Demo")
    print("=" * 60)

    tracker = InteractionTracker()  # in-memory DB

    # Seed random for reproducibility
    random.seed(42)

    # Generate 200 random interactions
    print("\nSimulating 200 random agent interactions...")
    for _ in range(200):
        a, b = random.sample(AGENTS, 2)
        itype = random.choices(
            TYPES,
            weights=[3, 5, 2, 4, 2],  # reply/collab favored
            k=1,
        )[0]
        vid = random.choice(VIDEO_IDS)
        tracker.record_interaction(
            from_agent=a,
            to_agent=b,
            type=itype,
            video_id=vid,
            metadata={"session": "demo"},
        )

    print("Done.\n")

    # Network stats
    stats = tracker.get_network_stats()
    print("--- Network Stats ---")
    print(f"  Total agents     : {stats['total_agents']}")
    print(f"  Total interactions: {stats['total_interactions']}")

    print("\n  Most Connected Agents:")
    for entry in stats["most_connected"]:
        print(f"    {entry['agent']:<14} — {entry['unique_peers']} unique peers")

    print("\n  Most Active Pairs:")
    for entry in stats["most_active_pairs"]:
        a1, a2 = entry["agents"]
        print(f"    {a1} ↔ {a2} — {entry['count']} interactions")

    # Alliances
    alliances = tracker.get_alliances(top_n=5)
    print("\n--- Top Alliances (collab + reply) ---")
    for a in alliances:
        a1, a2 = a["agents"]
        print(
            f"  {a1} ↔ {a2}: collab={a['collab_count']}, reply={a['reply_count']}, "
            f"strength={a['strength']:.2f}"
        )

    # Rivalries
    rivalries = tracker.get_rivalries(top_n=5)
    print("\n--- Top Rivalries (challenges) ---")
    if rivalries:
        for r in rivalries:
            a1, a2 = r["agents"]
            print(f"  {a1} ↔ {a2}: challenges={r['challenge_count']}, strength={r['strength']:.2f}")
    else:
        print("  (no challenge interactions recorded)")

    # Agent graph sample
    sample_agent = AGENTS[0]
    graph = tracker.get_agent_graph(sample_agent)
    print(f"\n--- Agent Graph: {sample_agent} ---")
    print(f"  Unique connections : {graph['total_connections']}")
    print(f"  Total interactions : {graph['total_interactions']}")
    for peer, info in sorted(graph["connections"].items(), key=lambda x: -x[1]["strength"])[:3]:
        print(f"  → {peer}: count={info['count']}, strength={info['strength']:.2f}, types={info['types']}")

    # Export
    graph_data = tracker.export_graph_data()
    print(f"\n--- D3.js Export ---")
    print(f"  Nodes: {graph_data['meta']['total_nodes']}")
    print(f"  Links: {graph_data['meta']['total_links']}")
    print("\nDemo complete.")


if __name__ == "__main__":
    run_demo()
