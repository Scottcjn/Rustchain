#!/usr/bin/env python3
"""
POWER8 PSE Benchmark Suite — Results Analyzer
Reads JSON benchmark output, generates markdown tables and charts.
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
import seaborn as sns
import numpy as np


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BUILD_LABELS: dict[str, str] = {
    "stock": "Stock llama.cpp",
    "pse_mass": "PSE-MASS",
    "pse_coffers": "PSE+Coffers",
}

PSE_MARKER_NAMES: dict[str, str] = {
    "noi": "NOI (Number of Iterations)",
    "divergence_ratio": "DR (Divergence Ratio)",
    "altivec_cycle_share": "ACS (AltiVec Cycle Share %)",
    "memory_coffer_index": "MCI (Memory Coffer Index)",
}

COLORS: dict[str, str] = {
    "stock": "#4C72B0",
    "pse_mass": "#DD8452",
    "pse_coffers": "#55A868",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_results(results_dir: Path) -> list[dict[str, Any]]:
    """Load all model JSON result files from the results directory."""
    results = []
    for f in sorted(results_dir.glob("*.json")):
        if f.name in ("progress.json", "numa_topology.json"):
            continue
        try:
            data = json.loads(f.read_text())
            if "model" in data and "results" in data:
                results.append(data)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: skipping {f.name}: {e}", file=sys.stderr)
    return results


def load_numa_topology(results_dir: Path) -> dict[str, Any] | None:
    """Load NUMA topology snapshot if available."""
    topo_file = results_dir / "numa_topology.json"
    if topo_file.exists():
        return json.loads(topo_file.read_text())
    return None


# ---------------------------------------------------------------------------
# Markdown report generation
# ---------------------------------------------------------------------------
def generate_markdown(
    results: list[dict[str, Any]],
    output_path: Path,
) -> str:
    """Generate a full markdown report and write to output_path."""
    lines: list[str] = []
    lines.append("# POWER8 PSE Benchmark Results\n")
    lines.append(f"Generated from {len(results)} model(s).\n")

    for model_data in results:
        model = model_data["model"]
        lines.append(f"\n## {model}\n")
        lines.append(f"**File:** `{model_data.get('model_file', 'N/A')}`  ")
        lines.append(f"**Timestamp:** {model_data.get('timestamp', 'N/A')}\n")

        builds = {r["build_mode"]: r for r in model_data["results"]}

        # --- Prompt processing table ---
        pp_sizes = model_data.get("config", {}).get("pp_sizes", [128, 512, 1024])
        lines.append("\n### Prompt Processing (tokens/sec)\n")
        header = "| Build Mode |"
        sep = "|---|"
        for pp in pp_sizes:
            header += f" pp{pp} |"
            sep += "---|"
        lines.append(header)
        lines.append(sep)

        for mode, label in BUILD_LABELS.items():
            if mode not in builds:
                continue
            row = f"| {label} |"
            pp_data = builds[mode].get("prompt_processing", {})
            for pp in pp_sizes:
                key = f"pp{pp}"
                stats = pp_data.get(key, {})
                mean = stats.get("mean", 0)
                cv = stats.get("cv_pct", 0)
                row += f" {mean:.1f} ({cv:.1f}% CV) |"
            lines.append(row)

        # --- Token generation table ---
        tg_sizes = model_data.get("config", {}).get("tg_sizes", [32, 128])
        lines.append("\n### Token Generation (tokens/sec)\n")
        header = "| Build Mode |"
        sep = "|---|"
        for tg in tg_sizes:
            header += f" tg{tg} |"
            sep += "---|"
        lines.append(header)
        lines.append(sep)

        for mode, label in BUILD_LABELS.items():
            if mode not in builds:
                continue
            row = f"| {label} |"
            tg_data = builds[mode].get("token_generation", {})
            for tg in tg_sizes:
                key = f"tg{tg}"
                stats = tg_data.get(key, {})
                mean = stats.get("mean", 0)
                cv = stats.get("cv_pct", 0)
                row += f" {mean:.1f} ({cv:.1f}% CV) |"
            lines.append(row)

        # --- Cache metrics ---
        lines.append("\n### Cache Hit Rates\n")
        lines.append("| Build Mode | L1 Hit Rate | LLC Hit Rate |")
        lines.append("|---|---|---|")

        for mode, label in BUILD_LABELS.items():
            if mode not in builds:
                continue
            cache = builds[mode].get("cache_metrics", {})
            l1 = cache.get("l1_hit_rate_pct", 0)
            llc = cache.get("llc_hit_rate_pct", 0)
            lines.append(f"| {label} | {l1:.2f}% | {llc:.2f}% |")

        # --- PSE markers ---
        lines.append("\n### PSE Markers\n")
        lines.append("| Build Mode | NOI | DR | ACS (%) | MCI |")
        lines.append("|---|---|---|---|---|")

        for mode, label in BUILD_LABELS.items():
            if mode not in builds:
                continue
            pse = builds[mode].get("pse_markers", {})
            lines.append(
                f"| {label} "
                f"| {pse.get('noi', 0)} "
                f"| {pse.get('divergence_ratio', 0):.4f} "
                f"| {pse.get('altivec_cycle_share', 0):.1f} "
                f"| {pse.get('memory_coffer_index', 0)} |"
            )

        # --- Speedup vs stock ---
        if "stock" in builds:
            lines.append("\n### Speedup vs Stock\n")
            lines.append("| Metric | PSE-MASS | PSE+Coffers |")
            lines.append("|---|---|---|")

            stock_pp = builds["stock"].get("prompt_processing", {})
            stock_tg = builds["stock"].get("token_generation", {})

            for pp in pp_sizes:
                key = f"pp{pp}"
                stock_val = stock_pp.get(key, {}).get("mean", 0)
                if stock_val <= 0:
                    continue
                cells = []
                for mode in ("pse_mass", "pse_coffers"):
                    if mode in builds:
                        val = builds[mode].get("prompt_processing", {}).get(key, {}).get("mean", 0)
                        speedup = val / stock_val if stock_val > 0 else 0
                        cells.append(f"{speedup:.2f}x")
                    else:
                        cells.append("N/A")
                lines.append(f"| pp{pp} | {' | '.join(cells)} |")

            for tg in tg_sizes:
                key = f"tg{tg}"
                stock_val = stock_tg.get(key, {}).get("mean", 0)
                if stock_val <= 0:
                    continue
                cells = []
                for mode in ("pse_mass", "pse_coffers"):
                    if mode in builds:
                        val = builds[mode].get("token_generation", {}).get(key, {}).get("mean", 0)
                        speedup = val / stock_val if stock_val > 0 else 0
                        cells.append(f"{speedup:.2f}x")
                    else:
                        cells.append("N/A")
                lines.append(f"| tg{tg} | {' | '.join(cells)} |")

    # PSE marker explanation
    lines.append("\n---\n")
    lines.append("## PSE Marker Reference\n")
    for key, desc in PSE_MARKER_NAMES.items():
        lines.append(f"- **{desc}**")
    lines.append("")
    lines.append(
        "- **NOI**: Total vec_perm iteration cycles executed during inference. "
        "Higher values indicate more AltiVec SIMD utilization.\n"
        "- **DR**: KL divergence of token probability distribution vs stock build. "
        "Values near 0 mean PSE produces equivalent outputs.\n"
        "- **ACS**: Percentage of total compute cycles spent in AltiVec vector units. "
        "Higher is better for PSE workloads.\n"
        "- **MCI**: Number of active NUMA memory coffers used during inference. "
        "Higher values indicate better memory distribution across NUMA nodes."
    )

    report = "\n".join(lines)
    output_path.write_text(report)
    return report


# ---------------------------------------------------------------------------
# Chart generation
# ---------------------------------------------------------------------------
def plot_throughput_comparison(
    results: list[dict[str, Any]],
    output_dir: Path,
) -> list[Path]:
    """Generate throughput comparison bar charts per model."""
    sns.set_theme(style="whitegrid", palette="muted")
    chart_paths: list[Path] = []

    for model_data in results:
        model = model_data["model"]
        builds = {r["build_mode"]: r for r in model_data["results"]}
        pp_sizes = model_data.get("config", {}).get("pp_sizes", [128, 512, 1024])
        tg_sizes = model_data.get("config", {}).get("tg_sizes", [32, 128])

        all_metrics = [f"pp{s}" for s in pp_sizes] + [f"tg{s}" for s in tg_sizes]

        fig, ax = plt.subplots(figsize=(12, 6))
        x = np.arange(len(all_metrics))
        width = 0.25
        offsets = {"stock": -width, "pse_mass": 0, "pse_coffers": width}

        for mode, offset in offsets.items():
            if mode not in builds:
                continue
            means = []
            errs = []
            for metric in all_metrics:
                if metric.startswith("pp"):
                    stats = builds[mode].get("prompt_processing", {}).get(metric, {})
                else:
                    stats = builds[mode].get("token_generation", {}).get(metric, {})
                means.append(stats.get("mean", 0))
                errs.append(stats.get("stddev", 0))

            ax.bar(
                x + offset,
                means,
                width,
                yerr=errs,
                label=BUILD_LABELS[mode],
                color=COLORS[mode],
                capsize=3,
            )

        ax.set_xlabel("Benchmark")
        ax.set_ylabel("Tokens/sec")
        ax.set_title(f"{model} — Throughput Comparison")
        ax.set_xticks(x)
        ax.set_xticklabels(all_metrics)
        ax.legend()
        fig.tight_layout()

        chart_path = output_dir / f"{model}_throughput.png"
        fig.savefig(chart_path, dpi=150)
        plt.close(fig)
        chart_paths.append(chart_path)
        print(f"Chart -> {chart_path}")

    return chart_paths


def plot_cache_comparison(
    results: list[dict[str, Any]],
    output_dir: Path,
) -> list[Path]:
    """Generate cache hit rate comparison charts."""
    chart_paths: list[Path] = []

    for model_data in results:
        model = model_data["model"]
        builds = {r["build_mode"]: r for r in model_data["results"]}

        modes = []
        l1_rates = []
        llc_rates = []

        for mode in ("stock", "pse_mass", "pse_coffers"):
            if mode not in builds:
                continue
            cache = builds[mode].get("cache_metrics", {})
            modes.append(BUILD_LABELS[mode])
            l1_rates.append(cache.get("l1_hit_rate_pct", 0))
            llc_rates.append(cache.get("llc_hit_rate_pct", 0))

        if not modes:
            continue

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5))
        colors = [COLORS[m] for m in ("stock", "pse_mass", "pse_coffers") if m in builds]

        ax1.bar(modes, l1_rates, color=colors)
        ax1.set_ylabel("Hit Rate (%)")
        ax1.set_title("L1 Data Cache")
        ax1.set_ylim(0, 105)

        ax2.bar(modes, llc_rates, color=colors)
        ax2.set_ylabel("Hit Rate (%)")
        ax2.set_title("Last-Level Cache")
        ax2.set_ylim(0, 105)

        fig.suptitle(f"{model} — Cache Hit Rates")
        fig.tight_layout()

        chart_path = output_dir / f"{model}_cache.png"
        fig.savefig(chart_path, dpi=150)
        plt.close(fig)
        chart_paths.append(chart_path)
        print(f"Chart -> {chart_path}")

    return chart_paths


def plot_pse_markers(
    results: list[dict[str, Any]],
    output_dir: Path,
) -> list[Path]:
    """Generate PSE marker comparison across builds."""
    chart_paths: list[Path] = []

    for model_data in results:
        model = model_data["model"]
        builds = {r["build_mode"]: r for r in model_data["results"]}

        # Only plot PSE modes (stock has no markers)
        pse_modes = [m for m in ("pse_mass", "pse_coffers") if m in builds]
        if not pse_modes:
            continue

        markers = ["noi", "divergence_ratio", "altivec_cycle_share", "memory_coffer_index"]
        marker_labels = ["NOI", "DR", "ACS (%)", "MCI"]

        fig, axes = plt.subplots(1, len(markers), figsize=(14, 4))
        if len(markers) == 1:
            axes = [axes]

        for i, (marker, label) in enumerate(zip(markers, marker_labels)):
            vals = []
            names = []
            colors = []
            for mode in pse_modes:
                pse = builds[mode].get("pse_markers", {})
                vals.append(pse.get(marker, 0))
                names.append(BUILD_LABELS[mode])
                colors.append(COLORS[mode])

            axes[i].bar(names, vals, color=colors)
            axes[i].set_title(label)
            axes[i].tick_params(axis="x", rotation=15)

        fig.suptitle(f"{model} — PSE Markers")
        fig.tight_layout()

        chart_path = output_dir / f"{model}_pse_markers.png"
        fig.savefig(chart_path, dpi=150)
        plt.close(fig)
        chart_paths.append(chart_path)
        print(f"Chart -> {chart_path}")

    return chart_paths


def plot_speedup_heatmap(
    results: list[dict[str, Any]],
    output_dir: Path,
) -> Path | None:
    """Generate a heatmap of speedups across all models and metrics."""
    if not results:
        return None

    rows = []
    row_labels = []

    for model_data in results:
        model = model_data["model"]
        builds = {r["build_mode"]: r for r in model_data["results"]}
        if "stock" not in builds:
            continue

        pp_sizes = model_data.get("config", {}).get("pp_sizes", [128, 512, 1024])
        tg_sizes = model_data.get("config", {}).get("tg_sizes", [32, 128])

        for mode in ("pse_mass", "pse_coffers"):
            if mode not in builds:
                continue
            row = []
            for pp in pp_sizes:
                key = f"pp{pp}"
                stock_val = builds["stock"].get("prompt_processing", {}).get(key, {}).get("mean", 1)
                pse_val = builds[mode].get("prompt_processing", {}).get(key, {}).get("mean", 0)
                row.append(pse_val / stock_val if stock_val > 0 else 0)
            for tg in tg_sizes:
                key = f"tg{tg}"
                stock_val = builds["stock"].get("token_generation", {}).get(key, {}).get("mean", 1)
                pse_val = builds[mode].get("token_generation", {}).get(key, {}).get("mean", 0)
                row.append(pse_val / stock_val if stock_val > 0 else 0)
            rows.append(row)
            row_labels.append(f"{model} / {BUILD_LABELS[mode]}")

    if not rows:
        return None

    col_labels = (
        [f"pp{s}" for s in results[0].get("config", {}).get("pp_sizes", [128, 512, 1024])]
        + [f"tg{s}" for s in results[0].get("config", {}).get("tg_sizes", [32, 128])]
    )

    fig, ax = plt.subplots(figsize=(10, max(3, len(rows) * 0.8)))
    data = np.array(rows)

    sns.heatmap(
        data,
        annot=True,
        fmt=".2f",
        xticklabels=col_labels,
        yticklabels=row_labels,
        cmap="RdYlGn",
        center=1.0,
        ax=ax,
    )
    ax.set_title("Speedup vs Stock (1.0x = parity)")
    fig.tight_layout()

    chart_path = output_dir / "speedup_heatmap.png"
    fig.savefig(chart_path, dpi=150)
    plt.close(fig)
    print(f"Chart -> {chart_path}")
    return chart_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    if len(sys.argv) < 2:
        results_dir = Path(__file__).parent / "results"
    else:
        results_dir = Path(sys.argv[1])

    if not results_dir.exists():
        print(f"Error: results directory not found: {results_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading results from: {results_dir}")
    results = load_results(results_dir)

    if not results:
        print("No benchmark results found.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(results)} model result(s).")

    # Charts directory
    charts_dir = results_dir / "charts"
    charts_dir.mkdir(exist_ok=True)

    # Generate charts
    plot_throughput_comparison(results, charts_dir)
    plot_cache_comparison(results, charts_dir)
    plot_pse_markers(results, charts_dir)
    plot_speedup_heatmap(results, charts_dir)

    # Generate markdown report
    report_path = results_dir / "REPORT.md"
    report = generate_markdown(results, report_path)
    print(f"Report -> {report_path}")
    print("\n" + "=" * 60)
    print(report)


if __name__ == "__main__":
    main()
