# SPDX-License-Identifier: MIT
"""Regression tests for cycle and duplicate-block handling in fork_choice_visualizer."""

from flask import Flask

from node.fork_choice_visualizer import (
    ForkChoiceBlock,
    _canonical_path,
    build_fork_choice_graph,
    create_fork_choice_blueprint,
    normalize_blocks,
)


def test_canonical_path_terminates_on_self_parent_and_two_node_cycle():
    self_block = ForkChoiceBlock(block_hash="self", parent_hash="self", height=1, weight=5)
    assert _canonical_path(self_block, {"self": self_block}) == ["self"]

    block_a = ForkChoiceBlock(block_hash="a", parent_hash="b", height=1, weight=5)
    block_b = ForkChoiceBlock(block_hash="b", parent_hash="a", height=2, weight=6)
    head_c = ForkChoiceBlock(block_hash="c", parent_hash="a", height=3, weight=10)
    by_hash = {"a": block_a, "b": block_b, "c": head_c}

    path = _canonical_path(head_c, by_hash)
    assert path == ["b", "a", "c"]
    assert len(path) == len(set(path))


def test_build_fork_choice_graph_handles_cyclic_parents_without_hanging():
    graph = build_fork_choice_graph(
        [
            {"hash": "a", "parent_hash": "b", "height": 1, "weight": 5},
            {"hash": "b", "parent_hash": "a", "height": 2, "weight": 6},
            {"hash": "c", "parent_hash": "a", "height": 3, "weight": 10},
        ]
    )

    assert graph["canonical_head"] == "c"
    assert graph["canonical_path"] == ["b", "a", "c"]
    assert graph["metrics"]["blocks"] == 3

    self_loop_graph = build_fork_choice_graph(
        [
            {"hash": "loop", "parent_hash": "loop", "height": 0, "weight": 1},
            {"hash": "child", "parent_hash": "loop", "height": 1, "weight": 2},
        ]
    )
    assert self_loop_graph["canonical_head"] == "child"
    assert self_loop_graph["canonical_path"] == ["loop", "child"]
    assert self_loop_graph["edges"] == [{"source": "loop", "target": "child"}]


def test_build_fork_choice_graph_deduplicates_repeated_block_hashes():
    graph = build_fork_choice_graph(
        [
            {"hash": "genesis", "height": 0, "weight": 1},
            {"hash": "a1", "parent_hash": "genesis", "height": 1, "weight": 10},
            {"hash": "a1", "parent_hash": "genesis", "height": 1, "weight": 10},
        ]
    )

    assert graph["metrics"]["blocks"] == 2
    assert graph["metrics"]["forks"] == 0
    assert graph["fork_points"] == []
    assert [node["id"] for node in graph["nodes"]] == ["genesis", "a1"]
    assert graph["edges"] == [{"source": "genesis", "target": "a1"}]


def test_normalize_blocks_ignores_non_dict_entries():
    blocks = normalize_blocks([None, "invalid", 123, {"hash": "g", "height": 0}])
    assert len(blocks) == 1
    assert blocks[0].block_hash == "g"


def test_flask_routes_render_cyclic_graph_cleanly():
    sample_blocks = [
        {"hash": "a", "parent_hash": "b", "height": 1, "weight": 5},
        {"hash": "b", "parent_hash": "a", "height": 2, "weight": 6},
        {"hash": "c", "parent_hash": "a", "height": 3, "weight": 10},
        {"hash": "c", "parent_hash": "a", "height": 3, "weight": 10},
    ]

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_fork_choice_blueprint(lambda: sample_blocks))
    client = app.test_client()

    api_res = client.get("/api/fork-choice")
    assert api_res.status_code == 200
    payload = api_res.get_json()
    assert payload["canonical_head"] == "c"
    assert payload["metrics"]["blocks"] == 3

    html_res = client.get("/fork-choice")
    assert html_res.status_code == 200
    assert "Fork Choice" in html_res.get_data(as_text=True)
