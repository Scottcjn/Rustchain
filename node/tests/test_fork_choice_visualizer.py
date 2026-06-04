#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Tests for fork-choice graph visualization helpers."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fork_choice_visualizer import build_fork_choice_graph, normalize_blocks


def test_build_graph_marks_weighted_canonical_path():
    graph = build_fork_choice_graph([
        {"hash": "genesis", "height": 0, "weight": 1},
        {"hash": "a1", "parent_hash": "genesis", "height": 1, "weight": 10},
        {"hash": "a2", "parent_hash": "a1", "height": 2, "weight": 20},
        {"hash": "b1", "parent_hash": "genesis", "height": 1, "weight": 30},
    ])

    assert graph["canonical_head"] == "b1"
    assert graph["metrics"] == {
        "blocks": 4,
        "forks": 1,
        "heads": 2,
        "max_depth": 2,
        "canonical_height": 1,
        "reorg_frequency_counter": 1,
        "max_reorg_depth": 2,
        "reorg_duration_histogram": {
            "le_60": 1,
            "le_300": 0,
            "le_900": 0,
            "gt_900": 0,
        },
        "reorg_alert_thresholds": {
            "frequency": 3,
            "max_depth": 6,
            "duration_seconds": 900,
        },
        "reorg_alerts": {
            "frequency": False,
            "max_depth": False,
            "duration_seconds": False,
        },
        "reorg_events": [
            {
                "fork_point": "genesis",
                "height": 0,
                "max_depth": 2,
                "duration_seconds": 0,
                "abandoned_heads": ["a2"],
            }
        ],
    }

    canonical = {node["id"] for node in graph["nodes"] if node["is_canonical"]}
    assert canonical == {"genesis", "b1"}
    assert graph["fork_points"] == ["genesis"]


def test_normalize_blocks_accepts_api_aliases():
    blocks = normalize_blocks([
        {
            "block_hash": "h1",
            "prev_hash": "h0",
            "block_height": "7",
            "total_difficulty": "11",
            "ts": "1234",
            "miner_id": "miner-a",
        }
    ])

    assert blocks[0].block_hash == "h1"
    assert blocks[0].parent_hash == "h0"
    assert blocks[0].height == 7
    assert blocks[0].weight == 11
    assert blocks[0].timestamp == 1234
    assert blocks[0].miner == "miner-a"


def test_graph_edges_and_heads_are_stable():
    graph = build_fork_choice_graph([
        {"hash": "a", "height": 0},
        {"hash": "c", "parent_hash": "b", "height": 2},
        {"hash": "b", "parent_hash": "a", "height": 1},
    ])

    assert graph["heads"] == ["c"]
    assert graph["edges"] == [
        {"source": "a", "target": "b"},
        {"source": "b", "target": "c"},
    ]
    assert [node["id"] for node in graph["nodes"]] == ["a", "b", "c"]


def test_graph_suppresses_edges_to_missing_windowed_parents():
    graph = build_fork_choice_graph([
        {"hash": "child", "parent_hash": "missing-parent", "height": 10},
    ])

    assert graph["nodes"][0]["id"] == "child"
    assert graph["nodes"][0]["parent"] == "missing-parent"
    assert graph["edges"] == []
    assert graph["heads"] == ["child"]


def test_reorg_metrics_track_duration_buckets_and_alerts():
    graph = build_fork_choice_graph([
        {"hash": "genesis", "height": 0, "weight": 1, "timestamp": 100},
        {"hash": "a1", "parent_hash": "genesis", "height": 1, "weight": 10, "timestamp": 140},
        {"hash": "a2", "parent_hash": "a1", "height": 2, "weight": 11, "timestamp": 470},
        {"hash": "b1", "parent_hash": "genesis", "height": 1, "weight": 20, "timestamp": 200},
        {"hash": "b2", "parent_hash": "b1", "height": 2, "weight": 30, "timestamp": 300},
        {"hash": "b3", "parent_hash": "b2", "height": 3, "weight": 40, "timestamp": 400},
        {"hash": "b4", "parent_hash": "b3", "height": 4, "weight": 50, "timestamp": 500},
        {"hash": "b5", "parent_hash": "b4", "height": 5, "weight": 60, "timestamp": 600},
        {"hash": "b6", "parent_hash": "b5", "height": 6, "weight": 70, "timestamp": 700},
        {"hash": "b7", "parent_hash": "b6", "height": 7, "weight": 80, "timestamp": 800},
        {"hash": "c1", "parent_hash": "b2", "height": 3, "weight": 1, "timestamp": 1500},
        {"hash": "d1", "parent_hash": "b3", "height": 4, "weight": 1, "timestamp": 690},
    ])

    assert graph["canonical_head"] == "b7"
    assert graph["metrics"]["reorg_frequency_counter"] == 3
    assert graph["metrics"]["max_reorg_depth"] == 2
    assert graph["metrics"]["reorg_duration_histogram"] == {
        "le_60": 0,
        "le_300": 1,
        "le_900": 1,
        "gt_900": 1,
    }
    assert graph["metrics"]["reorg_alerts"] == {
        "frequency": True,
        "max_depth": False,
        "duration_seconds": True,
    }
