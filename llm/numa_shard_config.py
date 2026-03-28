#!/usr/bin/env python3
"""
numa_shard_config.py — Generate optimal GGML_NUMA_SHARD_MAP for a model

Analyzes a GGUF model file (or layer count) and system NUMA topology,
then suggests an optimal layer-to-node mapping that places hot layers
on the fastest NUMA nodes.

Usage:
    python numa_shard_config.py --layers 32 --nodes 4
    python numa_shard_config.py --model path/to/model.gguf --nodes 4
    python numa_shard_config.py --auto   # detect nodes from /sys

License: MIT
"""

import argparse
import os
import struct
import sys
from pathlib import Path


def detect_numa_nodes():
    """Detect NUMA node count and bandwidth from sysfs."""
    node_dir = Path("/sys/devices/system/node")
    if not node_dir.exists():
        return []

    nodes = []
    for entry in sorted(node_dir.iterdir()):
        if entry.name.startswith("node") and entry.name[4:].isdigit():
            node_id = int(entry.name[4:])
            # Try to read meminfo for size
            mem_total = 0
            meminfo = entry / "meminfo"
            if meminfo.exists():
                for line in meminfo.read_text().splitlines():
                    if "MemTotal" in line:
                        parts = line.split()
                        for i, p in enumerate(parts):
                            if p.isdigit():
                                mem_total = int(p) * 1024  # kB → bytes
                                break
            nodes.append({
                "id": node_id,
                "mem_total_gb": mem_total / (1024**3),
            })
    return nodes


# Known POWER8 S824 bandwidth from RustChain benchmarks
POWER8_BW = {
    0: 220.0,   # Slowest
    1: 350.0,
    2: 415.0,   # Fastest
    3: 420.0,   # Fastest
}

# Default bandwidth assumptions for unknown systems
DEFAULT_BW = {i: 100.0 for i in range(16)}


def read_gguf_layers(model_path):
    """Read layer count from GGUF file header (minimal parse)."""
    try:
        with open(model_path, "rb") as f:
            magic = f.read(4)
            if magic != b"GGUF":
                print(f"Warning: {model_path} is not a GGUF file", file=sys.stderr)
                return None
            version = struct.unpack("<I", f.read(4))[0]
            tensor_count = struct.unpack("<Q", f.read(8))[0]
            # Count unique "blk.N" prefixes
            # For now, estimate from tensor count
            # Typical: ~10 tensors per layer + embeddings
            estimated_layers = max(1, (tensor_count - 4) // 10)
            return estimated_layers
    except (IOError, struct.error) as e:
        print(f"Warning: couldn't read {model_path}: {e}", file=sys.stderr)
        return None


def generate_shard_map(num_layers, nodes, bw_map=None, arch="power8"):
    """
    Generate optimal GGML_NUMA_SHARD_MAP string.

    Strategy:
    1. Attention layers go to fastest node (highest bandwidth)
    2. FFN layers go to second-fastest
    3. Early layers (embeddings) go to any node
    4. Remaining layers distributed proportionally to bandwidth
    """
    if not nodes:
        return None

    num_nodes = len(nodes)
    if bw_map is None:
        if arch == "power8":
            bw_map = POWER8_BW
        else:
            bw_map = DEFAULT_BW

    # Sort nodes by bandwidth (fastest first)
    sorted_nodes = sorted(range(num_nodes),
                          key=lambda n: bw_map.get(n, 100.0),
                          reverse=True)

    # Distribute layers proportional to bandwidth
    total_bw = sum(bw_map.get(n, 100.0) for n in range(num_nodes))
    layers_per_node = []
    assigned = 0

    for i, node in enumerate(sorted_nodes):
        bw = bw_map.get(node, 100.0)
        if i == num_nodes - 1:
            count = num_layers - assigned  # remainder to last
        else:
            count = max(1, round(num_layers * bw / total_bw))
        layers_per_node.append((node, count))
        assigned += count

    # Build ranges
    rules = []
    start = 0
    for node, count in layers_per_node:
        if count <= 0:
            continue
        end = start + count - 1
        if end >= num_layers:
            end = num_layers - 1
        if start == end:
            rules.append(f"{start}:node{node}")
        else:
            rules.append(f"{start}-{end}:node{node}")
        start = end + 1
        if start >= num_layers:
            break

    # Add type-specific rules: attention to fastest node
    fastest = sorted_nodes[0]
    rules.append(f"attn:node{fastest}")

    return ",".join(rules)


def print_report(num_layers, num_nodes, shard_map, bw_map, nodes_info):
    """Print a human-readable configuration report."""
    print("=" * 60)
    print("  NUMA Shard Configuration Report")
    print("=" * 60)
    print()
    print(f"  Model layers:  {num_layers}")
    print(f"  NUMA nodes:    {num_nodes}")
    print()

    print("  Node Topology:")
    print(f"  {'Node':<8} {'BW (MB/s)':<12} {'RAM (GiB)':<12}")
    print(f"  {'----':<8} {'---------':<12} {'---------':<12}")
    for i in range(num_nodes):
        bw = bw_map.get(i, 100.0)
        ram = nodes_info[i]["mem_total_gb"] if i < len(nodes_info) else 0
        print(f"  Node {i:<3} {bw:<12.1f} {ram:<12.1f}")
    print()

    print(f"  Shard map:")
    print(f"  export {os.environ.get('GGML_NUMA_SHARD_MAP', 'GGML_NUMA_SHARD_MAP')}=\"{shard_map}\"")
    print()

    # Parse and explain rules
    print("  Rule breakdown:")
    for rule in shard_map.split(","):
        parts = rule.split(":")
        if len(parts) == 2:
            target, node = parts
            print(f"    {target:>10} → {node}")
    print()
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Generate GGML_NUMA_SHARD_MAP for optimal tensor placement")
    parser.add_argument("--model", type=str, help="Path to GGUF model file")
    parser.add_argument("--layers", type=int, help="Number of transformer layers")
    parser.add_argument("--nodes", type=int, help="Number of NUMA nodes (auto-detect if omitted)")
    parser.add_argument("--arch", choices=["power8", "x86", "auto"], default="auto",
                        help="Architecture for bandwidth hints")
    parser.add_argument("--auto", action="store_true", help="Auto-detect everything from system")
    parser.add_argument("--export", action="store_true", help="Output only the export line")
    args = parser.parse_args()

    # Detect or use provided layer count
    num_layers = args.layers
    if args.model:
        detected = read_gguf_layers(args.model)
        if detected:
            num_layers = detected
            print(f"Detected {num_layers} layers from {args.model}", file=sys.stderr)

    if not num_layers:
        num_layers = 32  # default for 7B models
        print(f"Using default {num_layers} layers (specify --layers or --model)", file=sys.stderr)

    # Detect or use provided node count
    nodes_info = detect_numa_nodes()
    num_nodes = args.nodes if args.nodes else len(nodes_info)
    if num_nodes < 1:
        num_nodes = 4  # default for POWER8 S824
        print(f"Using default {num_nodes} nodes", file=sys.stderr)

    # Fill in node info if we didn't detect
    while len(nodes_info) < num_nodes:
        nodes_info.append({"id": len(nodes_info), "mem_total_gb": 128.0})

    # Architecture detection
    arch = args.arch
    if arch == "auto":
        import platform
        machine = platform.machine().lower()
        if "ppc" in machine or "power" in machine:
            arch = "power8"
        else:
            arch = "x86"

    bw_map = POWER8_BW if arch == "power8" else DEFAULT_BW

    # Generate map
    shard_map = generate_shard_map(num_layers, nodes_info, bw_map, arch)

    if args.export:
        print(f'export GGML_NUMA_SHARD_MAP="{shard_map}"')
    else:
        print_report(num_layers, num_nodes, shard_map, bw_map, nodes_info)


if __name__ == "__main__":
    main()
