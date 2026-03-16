#!/usr/bin/env python3
"""
POWER8 PSE Benchmark Suite — NUMA Topology Visualization
Shows active coffers during inference across NUMA nodes.
RustChain Bounty #35
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np


# ---------------------------------------------------------------------------
# NUMA topology data structures
# ---------------------------------------------------------------------------
def load_topology(results_dir: Path) -> dict[str, Any] | None:
    """Load NUMA topology JSON from benchmark results."""
    topo_file = results_dir / "numa_topology.json"
    if topo_file.exists():
        return json.loads(topo_file.read_text())
    return None


def load_coffer_activity(results_dir: Path) -> dict[str, Any]:
    """
    Load coffer activity from PSE+Coffers benchmark runs.
    Coffer activity is inferred from numastat snapshots taken during
    each build mode's benchmark run.
    """
    activity: dict[str, list[dict[str, Any]]] = {}

    for model_dir in results_dir.iterdir():
        if not model_dir.is_dir() or model_dir.name in ("charts",):
            continue

        model_name = model_dir.name
        activity[model_name] = []

        for numastat_file in sorted(model_dir.glob("*_numastat.txt")):
            mode = numastat_file.stem.replace("_numastat", "")
            parsed = parse_numastat(numastat_file)
            if parsed:
                activity[model_name].append({"mode": mode, "numa": parsed})

    return activity


def parse_numastat(filepath: Path) -> dict[str, dict[str, float]] | None:
    """Parse numastat -m output into per-node memory data."""
    if not filepath.exists():
        return None

    text = filepath.read_text()
    if not text.strip():
        return None

    result: dict[str, dict[str, float]] = {}
    lines = text.strip().split("\n")

    # Find header line with node numbers
    header_line = None
    for i, line in enumerate(lines):
        if "Node" in line and any(c.isdigit() for c in line):
            header_line = i
            break

    if header_line is None:
        return None

    # Parse node columns
    header_parts = lines[header_line].split()
    node_indices = [
        int(p) for p in header_parts if p.isdigit()
    ]

    # Parse memory rows
    for line in lines[header_line + 1:]:
        parts = line.split()
        if len(parts) < len(node_indices) + 1:
            continue
        metric = parts[0]
        values = {}
        for j, node_id in enumerate(node_indices):
            try:
                values[f"node{node_id}"] = float(parts[j + 1])
            except (ValueError, IndexError):
                values[f"node{node_id}"] = 0.0
        result[metric] = values

    return result


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------
def draw_numa_topology(
    topology: dict[str, Any],
    output_path: Path,
) -> None:
    """Draw a schematic of NUMA node layout with CPU and memory info."""
    nodes = topology.get("nodes", [])
    node_count = len(nodes)

    if node_count == 0:
        print("No NUMA nodes found in topology data.")
        return

    # Layout: 2 columns of NUMA nodes
    cols = min(2, node_count)
    rows = (node_count + cols - 1) // cols

    fig, axes = plt.subplots(rows, cols, figsize=(8 * cols, 4 * rows))
    if node_count == 1:
        axes = np.array([[axes]])
    elif rows == 1:
        axes = axes.reshape(1, -1)
    elif cols == 1:
        axes = axes.reshape(-1, 1)

    for i, node in enumerate(nodes):
        r, c = divmod(i, cols)
        ax = axes[r][c]

        node_id = node.get("node", i)
        cpus = node.get("cpus", "N/A")
        mem_total = node.get("mem_total_mb", 0)
        mem_free = node.get("mem_free_mb", 0)
        mem_used = mem_total - mem_free if mem_total > 0 else 0
        usage_pct = (mem_used / mem_total * 100) if mem_total > 0 else 0

        # Draw node box
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)
        ax.set_aspect("equal")
        ax.axis("off")

        # Background
        rect = mpatches.FancyBboxPatch(
            (0.5, 0.5), 9, 9,
            boxstyle="round,pad=0.3",
            facecolor="#2C3E50" if usage_pct > 50 else "#34495E",
            edgecolor="#ECF0F1",
            linewidth=2,
        )
        ax.add_patch(rect)

        # Node title
        ax.text(
            5, 8.5, f"NUMA Node {node_id}",
            ha="center", va="center",
            fontsize=14, fontweight="bold", color="#ECF0F1",
        )

        # CPU list
        cpu_list = str(cpus)
        if len(cpu_list) > 40:
            cpu_list = cpu_list[:37] + "..."
        ax.text(
            5, 7, f"CPUs: {cpu_list}",
            ha="center", va="center",
            fontsize=9, color="#BDC3C7",
        )

        # Memory bar
        bar_x, bar_y, bar_w, bar_h = 1.5, 4.5, 7, 1.5
        ax.add_patch(mpatches.Rectangle(
            (bar_x, bar_y), bar_w, bar_h,
            facecolor="#7F8C8D", edgecolor="#ECF0F1",
        ))
        used_w = bar_w * (usage_pct / 100)
        color = "#E74C3C" if usage_pct > 80 else "#F39C12" if usage_pct > 50 else "#27AE60"
        ax.add_patch(mpatches.Rectangle(
            (bar_x, bar_y), used_w, bar_h,
            facecolor=color,
        ))
        ax.text(
            5, 5.25, f"{mem_used:.0f} / {mem_total:.0f} MB ({usage_pct:.0f}%)",
            ha="center", va="center",
            fontsize=10, fontweight="bold", color="white",
        )

        # Label
        ax.text(
            5, 3.2, "Memory Usage",
            ha="center", va="center",
            fontsize=9, color="#BDC3C7",
        )

    # Hide unused axes
    for i in range(node_count, rows * cols):
        r, c = divmod(i, cols)
        axes[r][c].axis("off")

    fig.suptitle(
        "POWER8 S824 — NUMA Topology",
        fontsize=16, fontweight="bold", y=0.98,
    )
    fig.patch.set_facecolor("#1A1A2E")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(output_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"NUMA topology chart -> {output_path}")


def draw_coffer_activity(
    topology: dict[str, Any],
    activity: dict[str, Any],
    output_dir: Path,
) -> list[Path]:
    """
    Draw per-model coffer activity heatmaps showing which NUMA nodes
    were active during each build mode's inference run.
    """
    chart_paths: list[Path] = []
    nodes = topology.get("nodes", [])
    node_count = len(nodes)

    if node_count == 0:
        return chart_paths

    for model_name, runs in activity.items():
        if not runs:
            continue

        modes = []
        mem_usage_matrix = []

        for run in runs:
            mode = run["mode"]
            numa_data = run.get("numa", {})
            mem_used_row = []

            mem_total_data = numa_data.get("MemTotal", {})
            mem_free_data = numa_data.get("MemFree", {})

            for n in range(node_count):
                total = mem_total_data.get(f"node{n}", 0)
                free = mem_free_data.get(f"node{n}", 0)
                used_pct = ((total - free) / total * 100) if total > 0 else 0
                mem_used_row.append(used_pct)

            modes.append(mode)
            mem_usage_matrix.append(mem_used_row)

        if not mem_usage_matrix:
            continue

        fig, ax = plt.subplots(figsize=(max(6, node_count * 2), max(3, len(modes) * 0.8 + 2)))
        data = np.array(mem_usage_matrix)

        im = ax.imshow(data, cmap="YlOrRd", aspect="auto", vmin=0, vmax=100)

        ax.set_xticks(range(node_count))
        ax.set_xticklabels([f"Node {n}" for n in range(node_count)])
        ax.set_yticks(range(len(modes)))
        ax.set_yticklabels(modes)

        # Annotate cells
        for i in range(len(modes)):
            for j in range(node_count):
                val = data[i, j]
                color = "white" if val > 60 else "black"
                ax.text(j, i, f"{val:.0f}%", ha="center", va="center", color=color, fontsize=10)

        cbar = fig.colorbar(im, ax=ax, label="Memory Usage %")
        ax.set_title(f"{model_name} — Coffer Activity by NUMA Node")
        fig.tight_layout()

        chart_path = output_dir / f"{model_name}_coffer_activity.png"
        fig.savefig(chart_path, dpi=150)
        plt.close(fig)
        chart_paths.append(chart_path)
        print(f"Coffer activity chart -> {chart_path}")

    return chart_paths


def generate_sample_topology() -> dict[str, Any]:
    """Generate a sample POWER8 S824 topology for demonstration."""
    return {
        "node_count": 4,
        "nodes": [
            {"node": 0, "cpus": "0-23", "mem_total_mb": 65536, "mem_free_mb": 32000},
            {"node": 1, "cpus": "24-47", "mem_total_mb": 65536, "mem_free_mb": 45000},
            {"node": 2, "cpus": "48-71", "mem_total_mb": 65536, "mem_free_mb": 60000},
            {"node": 3, "cpus": "72-95", "mem_total_mb": 65536, "mem_free_mb": 58000},
        ],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    if len(sys.argv) < 2:
        results_dir = Path(__file__).parent / "results"
    else:
        results_dir = Path(sys.argv[1])

    charts_dir = results_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    # Load or generate topology
    topology = load_topology(results_dir)
    if topology is None:
        print("No live topology found, using sample POWER8 S824 topology for demo.")
        topology = generate_sample_topology()

    # Draw static topology
    draw_numa_topology(topology, charts_dir / "numa_topology.png")

    # Draw coffer activity if benchmark data exists
    activity = load_coffer_activity(results_dir)
    if activity:
        draw_coffer_activity(topology, activity, charts_dir)
    else:
        print("No coffer activity data found (run benchmark_pse.sh first).")

    print("NUMA visualization complete.")


if __name__ == "__main__":
    main()
