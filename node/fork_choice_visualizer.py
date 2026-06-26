#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fork-choice graph helpers and optional Flask endpoints."""

from dataclasses import dataclass, asdict
from typing import Callable, Dict, Iterable, List, Optional

try:
    from flask import Blueprint, jsonify, render_template_string
    FLASK_AVAILABLE = True
except ImportError:  # pragma: no cover - pure helper tests do not need Flask
    Blueprint = None
    jsonify = None
    render_template_string = None
    FLASK_AVAILABLE = False


@dataclass(frozen=True)
class ForkChoiceBlock:
    block_hash: str
    parent_hash: Optional[str]
    height: int
    weight: int = 1
    timestamp: int = 0
    miner: str = ""


REORG_ALERT_THRESHOLDS = {
    "frequency": 3,
    "max_depth": 6,
    "duration_seconds": 900,
}

REORG_DURATION_BUCKETS = (60, 300, 900)


FORK_CHOICE_HTML = """
<!doctype html>
<html>
<head>
  <title>RustChain Fork Choice</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 24px; color: #111827; }
    .metrics { display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }
    .metric { border: 1px solid #d1d5db; border-radius: 6px; padding: 10px 12px; }
    .metric strong { display: block; font-size: 20px; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border-bottom: 1px solid #e5e7eb; padding: 8px; text-align: left; }
    .canonical { color: #047857; font-weight: 700; }
    .fork { color: #b45309; }
  </style>
</head>
<body>
  <h1>Fork Choice</h1>
  <div class="metrics">
    {% for key, value in graph.metrics.items() %}
      <div class="metric"><span>{{ key }}</span><strong>{{ value }}</strong></div>
    {% endfor %}
  </div>
  <table>
    <thead><tr><th>Height</th><th>Hash</th><th>Parent</th><th>Weight</th><th>Status</th></tr></thead>
    <tbody>
    {% for node in graph.nodes %}
      <tr class="{{ 'canonical' if node.is_canonical else 'fork' }}">
        <td>{{ node.height }}</td>
        <td>{{ node.id }}</td>
        <td>{{ node.parent or '' }}</td>
        <td>{{ node.weight }}</td>
        <td>{{ 'canonical' if node.is_canonical else ('head' if node.is_head else 'side') }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</body>
</html>
"""


def normalize_blocks(blocks: Iterable[Dict]) -> List[ForkChoiceBlock]:
    """Normalize block rows from API/database shapes into visualizer blocks."""
    normalized = []
    for raw in blocks:
        block_hash = raw.get("block_hash") or raw.get("hash") or raw.get("id")
        if not block_hash:
            continue
        parent_hash = raw.get("parent_hash") or raw.get("prev_hash") or raw.get("previous_hash")
        height = _to_int(raw.get("height", raw.get("block_height", 0)))
        weight = _to_int(raw.get("weight", raw.get("total_difficulty", raw.get("work", 1))), default=1)
        timestamp = _to_int(raw.get("timestamp", raw.get("ts", 0)))
        normalized.append(ForkChoiceBlock(
            block_hash=str(block_hash),
            parent_hash=str(parent_hash) if parent_hash else None,
            height=height,
            weight=weight,
            timestamp=timestamp,
            miner=str(raw.get("miner", raw.get("miner_id", "")) or ""),
        ))
    return normalized


def build_fork_choice_graph(blocks: Iterable[Dict]) -> Dict:
    """Build graph, metrics, and canonical path data for fork-choice views."""
    normalized = normalize_blocks(blocks)
    by_hash = {block.block_hash: block for block in normalized}
    children: Dict[str, List[str]] = {block.block_hash: [] for block in normalized}

    for block in normalized:
        if block.parent_hash in children:
            children[block.parent_hash].append(block.block_hash)

    heads = [
        block for block in normalized
        if not children.get(block.block_hash)
    ]
    canonical_head = _select_canonical_head(heads)
    canonical_path = _canonical_path(canonical_head, by_hash)
    canonical_hashes = set(canonical_path)

    nodes = []
    edges = []
    for block in sorted(normalized, key=lambda item: (item.height, item.block_hash)):
        child_hashes = sorted(children.get(block.block_hash, []))
        nodes.append({
            "id": block.block_hash,
            "parent": block.parent_hash,
            "height": block.height,
            "weight": block.weight,
            "timestamp": block.timestamp,
            "miner": block.miner,
            "children": child_hashes,
            "is_head": block in heads,
            "is_canonical": block.block_hash in canonical_hashes,
        })
        if block.parent_hash in by_hash:
            edges.append({"source": block.parent_hash, "target": block.block_hash})

    fork_points = [block_hash for block_hash, child_hashes in children.items() if len(child_hashes) > 1]
    canonical_height = canonical_head.height if canonical_head else 0
    reorg_metrics = _reorg_resistance_metrics(
        normalized,
        children,
        canonical_hashes,
        fork_points,
    )

    return {
        "nodes": nodes,
        "edges": edges,
        "heads": [block.block_hash for block in sorted(heads, key=lambda item: item.block_hash)],
        "canonical_head": canonical_head.block_hash if canonical_head else None,
        "canonical_path": canonical_path,
        "fork_points": sorted(fork_points),
        "history": _fork_history(normalized, fork_points),
        "metrics": {
            "blocks": len(normalized),
            "forks": len(fork_points),
            "heads": len(heads),
            "max_depth": max((block.height for block in normalized), default=0),
            "canonical_height": canonical_height,
            **reorg_metrics,
        },
    }


def create_fork_choice_blueprint(block_provider: Callable[[], Iterable[Dict]]):
    """Create dashboard and JSON endpoints for fork-choice visualization."""
    if not FLASK_AVAILABLE:
        raise RuntimeError("Flask is required for fork-choice routes")

    blueprint = Blueprint("fork_choice_visualizer", __name__)

    @blueprint.get("/fork-choice")
    def fork_choice_dashboard():
        graph = build_fork_choice_graph(block_provider())
        return render_template_string(FORK_CHOICE_HTML, graph=_AttrDict(graph))

    @blueprint.get("/api/fork-choice")
    def fork_choice_api():
        return jsonify(build_fork_choice_graph(block_provider()))

    return blueprint


def _select_canonical_head(heads: List[ForkChoiceBlock]) -> Optional[ForkChoiceBlock]:
    if not heads:
        return None
    return max(heads, key=lambda block: (block.weight, block.height, block.timestamp, block.block_hash))


def _canonical_path(head: Optional[ForkChoiceBlock], by_hash: Dict[str, ForkChoiceBlock]) -> List[str]:
    path = []
    current = head
    while current:
        path.append(current.block_hash)
        current = by_hash.get(current.parent_hash) if current.parent_hash else None
    return list(reversed(path))


def _fork_history(blocks: List[ForkChoiceBlock], fork_points: List[str]) -> List[Dict]:
    by_hash = {block.block_hash: block for block in blocks}
    history = []
    for block_hash in fork_points:
        block = by_hash.get(block_hash)
        if block:
            history.append(asdict(block))
    return sorted(history, key=lambda item: (item["height"], item["block_hash"]))


def _reorg_resistance_metrics(
    blocks: List[ForkChoiceBlock],
    children: Dict[str, List[str]],
    canonical_hashes: set,
    fork_points: List[str],
) -> Dict:
    by_hash = {block.block_hash: block for block in blocks}
    durations = []
    max_reorg_depth = 0
    reorg_events = []

    for fork_hash in sorted(fork_points):
        fork_block = by_hash.get(fork_hash)
        if not fork_block:
            continue

        fork_max_depth = 0
        fork_max_duration = 0
        abandoned_heads = []

        for child_hash in children.get(fork_hash, []):
            if child_hash in canonical_hashes:
                continue

            descendant_hashes = _descendant_hashes(child_hash, children)
            branch_hashes = [child_hash, *descendant_hashes]
            abandoned_hashes = [hash_ for hash_ in branch_hashes if hash_ not in canonical_hashes]
            if not abandoned_hashes:
                continue

            abandoned_blocks = [by_hash[hash_] for hash_ in abandoned_hashes if hash_ in by_hash]
            if not abandoned_blocks:
                continue

            branch_depth = max(block.height for block in abandoned_blocks) - fork_block.height
            branch_duration = max(
                max(block.timestamp - fork_block.timestamp, 0)
                for block in abandoned_blocks
            )
            branch_heads = [
                block.block_hash
                for block in abandoned_blocks
                if not any(child in abandoned_hashes for child in children.get(block.block_hash, []))
            ]

            fork_max_depth = max(fork_max_depth, branch_depth)
            fork_max_duration = max(fork_max_duration, branch_duration)
            abandoned_heads.extend(sorted(branch_heads))

        if fork_max_depth:
            durations.append(fork_max_duration)
            max_reorg_depth = max(max_reorg_depth, fork_max_depth)
            reorg_events.append({
                "fork_point": fork_hash,
                "height": fork_block.height,
                "max_depth": fork_max_depth,
                "duration_seconds": fork_max_duration,
                "abandoned_heads": sorted(abandoned_heads),
            })

    max_duration = max(durations, default=0)

    return {
        "reorg_frequency_counter": len(reorg_events),
        "max_reorg_depth": max_reorg_depth,
        "reorg_duration_histogram": _duration_histogram(durations),
        "reorg_alert_thresholds": dict(REORG_ALERT_THRESHOLDS),
        "reorg_alerts": {
            "frequency": len(reorg_events) >= REORG_ALERT_THRESHOLDS["frequency"],
            "max_depth": max_reorg_depth >= REORG_ALERT_THRESHOLDS["max_depth"],
            "duration_seconds": max_duration >= REORG_ALERT_THRESHOLDS["duration_seconds"],
        },
        "reorg_events": reorg_events,
    }


def _descendant_hashes(root_hash: str, children: Dict[str, List[str]]) -> List[str]:
    descendants = []
    visited = {root_hash}
    stack = list(children.get(root_hash, []))
    while stack:
        block_hash = stack.pop()
        if block_hash in visited:
            continue
        visited.add(block_hash)
        descendants.append(block_hash)
        stack.extend(children.get(block_hash, []))
    return descendants


def _duration_histogram(durations: List[int]) -> Dict[str, int]:
    histogram = {
        "le_60": 0,
        "le_300": 0,
        "le_900": 0,
        "gt_900": 0,
    }
    for duration in durations:
        if duration <= REORG_DURATION_BUCKETS[0]:
            histogram["le_60"] += 1
        elif duration <= REORG_DURATION_BUCKETS[1]:
            histogram["le_300"] += 1
        elif duration <= REORG_DURATION_BUCKETS[2]:
            histogram["le_900"] += 1
        else:
            histogram["gt_900"] += 1
    return histogram


def _to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class _AttrDict(dict):
    def __getattr__(self, item):
        value = self[item]
        if isinstance(value, dict):
            return _AttrDict(value)
        return value
