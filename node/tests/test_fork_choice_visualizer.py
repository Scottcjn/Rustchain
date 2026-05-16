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
