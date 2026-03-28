"""
BoTTube Discovery Engine — Demo
================================
Indexes 50 mock videos then demonstrates search, recommendations,
trending and tag/agent filtering.

Usage:
    python tools/bottube_discovery_demo.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))
from bottube_discovery import VideoDiscovery

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_VIDEOS = [
    # (video_id, title, description, tags, agent_id, duration_s)
    ("v001", "Rust in 2026: What Changed?", "A deep dive into Rust language evolution", ["rust","programming","systems"], "agent_alpha", 720),
    ("v002", "Building a Blockchain in Python", "Step-by-step blockchain from scratch", ["blockchain","python","crypto"], "agent_beta", 1800),
    ("v003", "SQLite Tips & Tricks", "Advanced SQLite patterns for developers", ["sqlite","database","sql"], "agent_gamma", 540),
    ("v004", "TF-IDF Explained Simply", "How search engines rank documents", ["search","nlp","ml"], "agent_alpha", 900),
    ("v005", "Decentralised Video Streaming", "P2P video delivery on BoTTube", ["bottube","p2p","streaming"], "agent_delta", 1200),
    ("v006", "Rust Ownership Model Deep Dive", "Memory safety without GC", ["rust","memory","systems"], "agent_alpha", 1500),
    ("v007", "Smart Contracts 101", "Introduction to Ethereum smart contracts", ["blockchain","ethereum","solidity"], "agent_beta", 660),
    ("v008", "Python Async IO Patterns", "asyncio, aiohttp and beyond", ["python","async","networking"], "agent_gamma", 780),
    ("v009", "Cosine Similarity in Practice", "Implementing vector similarity search", ["ml","nlp","search"], "agent_alpha", 480),
    ("v010", "BoTTube Architecture Overview", "How BoTTube works under the hood", ["bottube","architecture","p2p"], "agent_delta", 2100),
    ("v011", "Consensus Algorithms Explained", "Raft, PBFT and PoW compared", ["blockchain","consensus","distributed"], "agent_beta", 1350),
    ("v012", "Writing Fast Rust Code", "Profiling and optimising Rust programs", ["rust","performance","systems"], "agent_alpha", 960),
    ("v013", "SQLite vs PostgreSQL", "Choosing the right database", ["sqlite","database","postgresql"], "agent_gamma", 720),
    ("v014", "Recommendation Systems Crash Course", "Collaborative filtering and content-based methods", ["ml","recommendations","search"], "agent_epsilon", 1440),
    ("v015", "IPFS for Developers", "Storing files on the decentralised web", ["ipfs","p2p","distributed"], "agent_delta", 840),
    ("v016", "Zero-Knowledge Proofs Intro", "Privacy in public blockchains", ["blockchain","cryptography","privacy"], "agent_beta", 1200),
    ("v017", "Building REST APIs with Python", "FastAPI from zero to hero", ["python","api","web"], "agent_gamma", 2400),
    ("v018", "Embeddings and Vector DBs", "Semantic search with dense vectors", ["ml","nlp","database"], "agent_epsilon", 1080),
    ("v019", "BoTTube Token Economics", "RTC tokenomics deep dive", ["bottube","crypto","economics"], "agent_delta", 900),
    ("v020", "Rust Macros Masterclass", "Procedural and declarative macros", ["rust","metaprogramming","systems"], "agent_alpha", 1680),
    ("v021", "Distributed Hash Tables", "How DHTs power P2P networks", ["p2p","distributed","networking"], "agent_delta", 780),
    ("v022", "Python Type Hints in 2026", "Full typing guide for modern Python", ["python","typing","programming"], "agent_gamma", 600),
    ("v023", "Merkle Trees Explained", "Data integrity in distributed systems", ["blockchain","cryptography","data"], "agent_beta", 540),
    ("v024", "NLP Pipeline from Scratch", "Tokenisation to classification", ["nlp","ml","python"], "agent_epsilon", 1920),
    ("v025", "BoTTube Content Moderation", "AI-driven community safety", ["bottube","ai","safety"], "agent_delta", 660),
    ("v026", "Async Rust with Tokio", "High-performance async IO in Rust", ["rust","async","networking"], "agent_alpha", 1260),
    ("v027", "Graph Databases 101", "When to use Neo4j over SQL", ["database","graph","sql"], "agent_gamma", 840),
    ("v028", "Proof of Work vs Proof of Stake", "Consensus mechanisms compared", ["blockchain","consensus","crypto"], "agent_beta", 1080),
    ("v029", "Text Ranking with BM25", "Beyond TF-IDF for search", ["search","nlp","ml"], "agent_epsilon", 720),
    ("v030", "BoTTube Live Streaming Guide", "Setting up your live stream on BoTTube", ["bottube","streaming","tutorial"], "agent_delta", 480),
    ("v031", "WebAssembly with Rust", "Compiling Rust to WASM", ["rust","wasm","web"], "agent_alpha", 1140),
    ("v032", "Data Pipelines in Python", "ETL best practices", ["python","data","etl"], "agent_gamma", 1560),
    ("v033", "Cryptographic Hash Functions", "SHA-256 and beyond", ["cryptography","blockchain","security"], "agent_beta", 660),
    ("v034", "Semantic Search Deep Dive", "Building a semantic search engine", ["search","ml","nlp"], "agent_epsilon", 1800),
    ("v035", "BoTTube Node Setup", "Running a BoTTube node at home", ["bottube","tutorial","p2p"], "agent_delta", 2400),
    ("v036", "Rust Error Handling", "Result, Option and the ? operator", ["rust","programming","errors"], "agent_alpha", 840),
    ("v037", "Microservices with Python", "Designing distributed Python services", ["python","microservices","distributed"], "agent_gamma", 1320),
    ("v038", "Layer 2 Scaling Solutions", "Rollups and state channels explained", ["blockchain","scaling","ethereum"], "agent_beta", 1440),
    ("v039", "Retrieval-Augmented Generation", "Combining LLMs with search", ["ml","nlp","ai"], "agent_epsilon", 2160),
    ("v040", "BoTTube Monetisation Guide", "Earning RTC from your content", ["bottube","crypto","economics"], "agent_delta", 900),
    ("v041", "Unsafe Rust Patterns", "When and how to use unsafe", ["rust","systems","memory"], "agent_alpha", 1080),
    ("v042", "Python Dataclasses & Pydantic", "Modern data modelling in Python", ["python","data","programming"], "agent_gamma", 780),
    ("v043", "DeFi Protocol Design", "Building AMMs and lending protocols", ["blockchain","defi","crypto"], "agent_beta", 1920),
    ("v044", "Transformer Architecture Explained", "Self-attention from first principles", ["ml","ai","nlp"], "agent_epsilon", 2400),
    ("v045", "BoTTube SDK Tutorial", "Build on BoTTube with the Python SDK", ["bottube","tutorial","python"], "agent_delta", 1200),
    ("v046", "Cargo Workspaces in Rust", "Managing large Rust projects", ["rust","programming","tools"], "agent_alpha", 720),
    ("v047", "SQLite Full-Text Search", "FTS5 for powerful text queries", ["sqlite","search","database"], "agent_gamma", 600),
    ("v048", "Cross-Chain Bridges", "Interoperability between blockchains", ["blockchain","crypto","distributed"], "agent_beta", 1080),
    ("v049", "Fine-Tuning Language Models", "Adapting LLMs to your domain", ["ml","ai","nlp"], "agent_epsilon", 2700),
    ("v050", "BoTTube 2026 Roadmap", "What's coming to BoTTube this year", ["bottube","roadmap","community"], "agent_delta", 600),
]

# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("BoTTube Discovery Engine — Demo")
    print("=" * 60)

    disc = VideoDiscovery(":memory:")

    # Index 50 mock videos with staggered timestamps
    base_ts = time.time() - 7 * 86400  # 7 days ago
    for i, (vid, title, desc, tags, agent, dur) in enumerate(MOCK_VIDEOS):
        created = base_ts + i * 3600 * 3  # every 3 hours
        disc.index_video(vid, title, desc, tags, agent, dur, created)

    # Simulate views for trending
    now = time.time()
    view_data = [
        ("v005", 12), ("v010", 20), ("v019", 8), ("v035", 15),
        ("v050", 25), ("v039", 10), ("v044", 18), ("v002", 6),
    ]
    for vid, count in view_data:
        for j in range(count):
            disc.record_view(vid, viewed_at=now - j * 600)

    print(f"\n📦 Indexed {disc.video_count()} videos\n")

    # 1. Search
    print("🔍 Search: 'rust async performance'")
    results = disc.search("rust async performance", limit=5)
    for r in results:
        print(f"   [{r['video_id']}] {r['title']}")

    # 2. Recommendations
    print("\n💡 Recommendations for v005 (Decentralised Video Streaming):")
    recs = disc.get_recommendations("v005", limit=5)
    for r in recs:
        print(f"   [{r['video_id']}] {r['title']}")

    # 3. Trending
    print("\n🔥 Trending (last 24h):")
    trending = disc.get_trending(hours=24, limit=5)
    for r in trending:
        print(f"   [{r['video_id']}] {r['title']}  views={r['view_count']}")

    # 4. By tag
    print("\n🏷  Videos tagged 'blockchain':")
    tagged = disc.get_by_tag("blockchain", limit=5)
    for r in tagged:
        print(f"   [{r['video_id']}] {r['title']}")

    # 5. By agent
    print("\n🤖 Videos by agent_alpha:")
    by_agent = disc.get_by_agent("agent_alpha", limit=5)
    for r in by_agent:
        print(f"   [{r['video_id']}] {r['title']}")

    # 6. Newest
    print("\n🆕 Newest videos:")
    new_vids = disc.get_new(limit=5)
    for r in new_vids:
        print(f"   [{r['video_id']}] {r['title']}")

    disc.close()
    print("\n✅ Demo complete.")


if __name__ == "__main__":
    main()
