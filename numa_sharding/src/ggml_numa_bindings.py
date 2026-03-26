"""
ggml_numa_bindings.py - Python ctypes bindings for ggml-numa-shard.h

Provides Python-level access to NUMA-aware memory binding for llama.cpp GGUF models.
Use this to analyze tensor layout and get NUMA recommendations before model loading.

Usage:
    from ggml_numa_bindings import GGMLNUMABindings
    
    numa = GGMLNUMABindings()
    numa.init("0-8:1,9-20:3,21-31:2")
    node = numa.assign_tensor("blk.15.attn_q.weight", layer_idx=15)
    numa.bind(addr, size, node)
    numa.cleanup()

Bounty: Scottcjn/rustchain-bounties #2277
Version: 1.1.0
"""

import ctypes
import os
import sys
from ctypes import c_int, c_void_p, c_size_t, c_char_p, POINTER, Structure
from typing import Optional, List, Dict, Tuple, Any


class GGMLNUMABindings:
    """
    Python bindings for ggml-numa-shard C library.
    
    This class wraps the C API with Python-friendly interface for:
    - NUMA initialization and configuration
    - Tensor-to-node assignment
    - Memory binding
    - Statistics collection
    """
    
    _lib: Optional[ctypes.CDLL] = None
    _loaded: bool = False
    _lib_path: Optional[str] = None
    
    def __init__(self, lib_path: Optional[str] = None):
        """
        Initialize bindings.
        
        Args:
            lib_path: Optional path to compiled libggml-numa-shared.so/.dll
                     If not provided, searches standard locations.
        """
        self._tensor_info_struct = None
        self._shard_ctx_struct = None
        self._load_library(lib_path)
    
    def _load_library(self, lib_path: Optional[str] = None) -> None:
        """Load the native NUMA library."""
        if GGMLNUMABindings._loaded:
            self._lib = GGMLNUMABindings._lib
            return
        
        search_paths = []
        
        if lib_path:
            search_paths.append(lib_path)
        
        if sys.platform == "darwin":
            search_paths.extend([
                "./build/lib/libggml-numa.dylib",
                "./numa_sharding/build/libggml-numa.dylib",
                "/usr/local/lib/libggml-numa.dylib",
            ])
        elif sys.platform == "win32":
            search_paths.extend([
                ".\\build\\lib\\ggml-numa.dll",
                ".\\numa_sharding\\build\\ggml-numa.dll",
                "C:\\Program Files\\llama.cpp\\ggml-numa.dll",
            ])
        else:  # Linux
            search_paths.extend([
                "./build/lib/libggml-numa-shared.so",
                "./numa_sharding/build/libggml-numa-shared.so",
                "/usr/local/lib/libggml-numa-shared.so",
                "/usr/lib/libggml-numa-shared.so",
            ])
        
        for path in search_paths:
            try:
                self._lib = ctypes.CDLL(path)
                GGMLNUMABindings._lib = self._lib
                GGMLNUMABindings._loaded = True
                GGMLNUMABindings._lib_path = path
                self._setup_function_signatures()
                return
            except (OSError, FileNotFoundError):
                continue
        
        print("[NUMA-PY] Warning: Native library not found. Using pure Python fallback.")
        print("[NUMA-PY] For full functionality, compile ggml-numa-shard.c with:")
        print("[NUMA-PY]   gcc -shared -fPIC -o libggml-numa-shared.so ggml-numa-shard.c -lnuma")
        self._lib = None
        self._setup_function_signatures()
    
    def _setup_function_signatures(self) -> None:
        """Define ctypes function signatures."""
        if self._lib is None:
            return
        
        # ggml_numa_available
        self._lib.ggml_numa_available.restype = c_int
        self._lib.ggml_numa_available.argtypes = []
        
        # ggml_numa_num_nodes
        self._lib.ggml_numa_num_nodes.restype = c_int
        self._lib.ggml_numa_num_nodes.argtypes = []
        
        # ggml_numa_shard_init
        self._lib.ggml_numa_shard_init.restype = c_int
        self._lib.ggml_numa_shard_init.argtypes = [c_char_p]
        
        # ggml_numa_shard_assign_tensor
        self._lib.ggml_numa_shard_assign_tensor.restype = c_int
        self._lib.ggml_numa_shard_assign_tensor.argtypes = [c_char_p, c_int]
        
        # ggml_numa_shard_bind
        self._lib.ggml_numa_shard_bind.restype = c_int
        self._lib.ggml_numa_shard_bind.argtypes = [c_void_p, c_size_t, c_int]
        
        # ggml_numa_shard_get_recommended_threads
        self._lib.ggml_numa_get_recommended_threads.restype = c_int
        self._lib.ggml_numa_get_recommended_threads.argtypes = []
        
        # ggml_numa_shard_cleanup
        self._lib.ggml_numa_shard_cleanup.restype = None
        self._lib.ggml_numa_shard_cleanup.argtypes = []
    
    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------
    
    def available(self) -> bool:
        """Check if NUMA is available on this system."""
        if self._lib:
            return bool(self._lib.ggml_numa_available())
        return self._is_numa_available_fallback()
    
    def num_nodes(self) -> int:
        """Get number of NUMA nodes."""
        if self._lib:
            return self._lib.ggml_numa_num_nodes()
        return self._get_numa_nodes_fallback()
    
    def init(self, config: Optional[str] = None) -> bool:
        """
        Initialize NUMA sharding.
        
        Args:
            config: Configuration string like "0-8:1,9-20:3,21-31:2"
                   If None, uses GGML_NUMA_SHARD_MAP env var.
        
        Returns:
            True on success, False on failure.
        """
        env_config = os.environ.get("GGML_NUMA_SHARD_MAP")
        final_config = config or envConfig or "0-8:1,9-20:3,21-31:2"
        
        if self._lib:
            result = self._lib.ggml_numa_shard_init(final_config.encode('utf-8'))
            return result == 0
        
        return self._init_fallback(final_config)
    
    def assign_tensor(self, tensor_name: str, layer_idx: int = -1) -> int:
        """
        Get NUMA node assignment for a tensor.
        
        Args:
            tensor_name: GGUF tensor name (e.g., "blk.15.attn_q.weight")
            layer_idx: Layer index (-1 for auto-detect)
        
        Returns:
            NUMA node ID (0, 1, 2, 3...)
        """
        if self._lib:
            return self._lib.ggml_numa_shard_assign_tensor(
                tensor_name.encode('utf-8'), layer_idx
            )
        
        return self._assign_tensor_fallback(tensor_name, layer_idx)
    
    def bind(self, addr: int, size: int, node: int) -> bool:
        """
        Bind memory region to NUMA node.
        
        Args:
            addr: Memory address (as int)
            size: Size in bytes
            node: NUMA node ID
        
        Returns:
            True on success.
        """
        if self._lib:
            result = self._lib.ggml_numa_shard_bind(
                c_void_p(addr), c_size_t(size), node
            )
            return result == 0
        
        return True  # Fallback: no-op
    
    def get_recommended_threads(self) -> int:
        """
        Get recommended thread count for POWER8.
        
        Returns:
            64 for POWER8, 0 for auto-detect on other platforms.
        """
        if self._lib:
            return self._lib.ggml_numa_get_recommended_threads()
        return 64  # Default for POWER8
    
    def cleanup(self) -> None:
        """Cleanup NUMA sharding resources."""
        if self._lib:
            self._lib.ggml_numa_shard_cleanup()
    
    def parse_tensor_name(self, tensor_name: str) -> Dict[str, Any]:
        """
        Parse GGUF tensor name and extract metadata.
        
        Args:
            tensor_name: e.g., "blk.15.attn_q.weight"
        
        Returns:
            Dict with layer_index, tensor_type, and recommended_node.
        """
        layer = -1
        if "." in tensor_name:
            parts = tensor_name.split(".")
            for i, part in enumerate(parts):
                if part.isdigit():
                    layer = int(part)
                    break
        
        tensor_type = self._infer_tensor_type(tensor_name)
        node = self.assign_tensor(tensor_name, layer)
        
        return {
            "name": tensor_name,
            "layer_index": layer,
            "tensor_type": tensor_type,
            "recommended_node": node,
            "tensor_type_name": self._TENSOR_TYPE_NAMES.get(tensor_type, "unknown"),
        }
    
    def analyze_model_tensors(self, tensor_names: List[str]) -> Dict[int, Dict]:
        """
        Analyze all tensors in a model and group by NUMA node.
        
        Args:
            tensor_names: List of GGUF tensor names.
        
        Returns:
            Dict keyed by NUMA node ID, with per-node tensor lists.
        """
        result: Dict[int, List[Dict]] = {}
        
        for name in tensor_names:
            info = self.parse_tensor_name(name)
            node = info["recommended_node"]
            
            if node not in result:
                result[node] = []
            result[node].append(info)
        
        return result
    
    # -------------------------------------------------------------------------
    # Tensor type classification
    # -------------------------------------------------------------------------
    
    _TENSOR_TYPE_NAMES = {
        0: "embedding/misc",
        1: "attention_query",
        2: "attention_key",
        3: "attention_value",
        4: "attention_output",
        5: "ffn_up/gate",
        6: "ffn_down",
        7: "ffn_gate",
        8: "output",
    }
    
    _TENSOR_PATTERNS = {
        "token_embd": (0, 0),
        "pos_embd": (0, 0),
        "blk.": (-1, -1),  # Dynamic
        "attn_q": (1, None),
        "attn_k": (2, None),
        "attn_v": (3, None),
        "attn_output": (4, None),
        "attn_o": (4, None),
        "ffn_up": (5, None),
        "ffn_gate": (7, None),
        "ffn_down": (6, None),
        "mlp_gate": (7, None),
        "mlp_up": (5, None),
        "mlp_down": (6, None),
        "output_norm": (8, 99),
        "output.": (8, None),
    }
    
    def _infer_tensor_type(self, tensor_name: str) -> int:
        """Infer tensor type from name."""
        for pattern, (ttype, _) in self._TENSOR_PATTERNS.items():
            if pattern in tensor_name:
                return ttype
        return 0
    
    # -------------------------------------------------------------------------
    # Pure Python fallbacks (when native lib unavailable)
    # -------------------------------------------------------------------------
    
    def _is_numa_available_fallback(self) -> bool:
        """Fallback: check /proc/sys/kernel/numa_balancing or numactl."""
        if os.path.exists("/proc/sys/kernel/numa_balancing"):
            return True
        import shutil
        return shutil.which("numactl") is not None
    
    def _get_numa_nodes_fallback(self) -> int:
        """Fallback: detect NUMA nodes via numactl or sysfs."""
        import subprocess
        try:
            result = subprocess.run(
                ["numactl", "--hardware"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split("\n"):
                if "available:" in line:
                    parts = line.split("available:")[1].strip().split()
                    if parts:
                        return int(parts[0])
        except Exception:
            pass
        
        # Try sysfs
        node_path = "/sys/devices/system/node"
        if os.path.exists(node_path):
            try:
                nodes = os.listdir(node_path)
                return len([n for n in nodes if n.startswith("node")])
            except Exception:
                pass
        
        return 1  # Assume single-node
    
    def _init_fallback(self, config: str) -> bool:
        """Fallback init: just validate config format."""
        if not config:
            return False
        parts = config.split(",")
        for part in parts:
            if ":" in part:
                range_part = part.split(":")[0]
                if "-" in range_part:
                    try:
                        start, end = range_part.split("-")
                        int(start), int(end)
                    except ValueError:
                        return False
        return True
    
    def _assign_tensor_fallback(self, tensor_name: str, layer_idx: int) -> int:
        """Fallback: pure Python assignment logic."""
        if layer_idx < 0:
            parts = tensor_name.split(".")
            for p in parts:
                if p.isdigit():
                    layer_idx = int(p)
                    break
            if layer_idx < 0:
                return 0
        
        # POWER8 S824: 0-8 → node 1, 9-20 → node 3, 21-31 → node 2
        if 0 <= layer_idx <= 8:
            return 1
        elif 9 <= layer_idx <= 20:
            return 3
        elif layer_idx >= 21:
            return 2
        return 0


# =============================================================================
# Convenience functions
# =============================================================================

def get_numa_topology() -> Dict[str, Any]:
    """
    Get NUMA topology of current system.
    
    Returns:
        Dict with node count, memory per node, CPU per node, distances.
    """
    numa = GGMLNUMABindings()
    
    topology = {
        "numa_available": numa.available(),
        "num_nodes": numa.num_nodes(),
        "recommended_threads": numa.get_recommended_threads(),
        "platform": sys.platform,
    }
    
    return topology


def recommend_shard_map(num_layers: int, num_nodes: int = 4) -> str:
    """
    Generate optimal shard map for given model and NUMA topology.
    
    Args:
        num_layers: Total number of transformer layers.
        num_nodes: Number of NUMA nodes (default 4 for POWER8 S824).
    
    Returns:
        GGML_NUMA_SHARD_MAP format string.
    
    Examples:
        >>> recommend_shard_map(32, 4)
        "0-8:1,9-20:3,21-31:2"
    """
    if num_nodes == 4:
        # POWER8 S824: Use Node 1 for early layers, Node 3 for middle, Node 2 for late
        if num_layers <= 22:
            # TinyLlama 1.1B: 22 layers
            mid = num_layers // 2
            return f"0-{mid-1}:1,{mid}:3,{mid+1}-{num_layers-1}:2"
        elif num_layers <= 32:
            # Llama 2 7B: 32 layers
            return "0-8:1,9-20:3,21-31:2"
        elif num_layers <= 40:
            # Llama 2 13B: 40 layers
            t1, t2 = num_layers * 3 // 10, num_layers * 6 // 10
            return f"0-{t1-1}:1,{t1}-{t2-1}:3,{t2}-{num_layers-1}:2"
        elif num_layers <= 60:
            # Llama 2 33B: 60 layers
            t1, t2 = num_layers * 3 // 10, num_layers * 6 // 10
            return f"0-{t1-1}:1,{t1}-{t2-1}:3,{t2}-{num_layers-1}:2"
        else:
            # Llama 2 70B: 80 layers - split across all 4 nodes
            t1, t2, t3 = num_layers // 4, num_layers // 2, num_layers * 3 // 4
            return f"0-{t1-1}:0,{t1}-{t2-1}:1,{t2}-{t3-1}:3,{t3}-{num_layers-1}:2"
    elif num_nodes == 2:
        # Dual-socket x86
        mid = num_layers // 2
        return f"0-{mid-1}:0,{mid}-{num_layers-1}:1"
    else:
        # Generic: evenly distribute
        step = max(1, num_layers // num_nodes)
        rules = []
        for i in range(num_nodes):
            start = i * step
            end = min((i + 1) * step - 1, num_layers - 1)
            if i == num_nodes - 1:
                end = num_layers - 1
            rules.append(f"{start}-{end}:{i}")
        return ",".join(rules)


def format_numa_stats_table(stats: Dict[int, Dict]) -> str:
    """
    Format NUMA statistics as a markdown table.
    
    Args:
        stats: Per-node stats dict.
    
    Returns:
        Markdown formatted string.
    """
    lines = [
        "| Node | Tensors | Size (MB) | Description |",
        "|------|---------|-----------|-------------|"
    ]
    
    node_descriptions = {
        0: "I/O, slow (POWER8 S824)",
        1: "Moderate bandwidth",
        2: "Fast (FFN layers)",
        3: "Fastest (Attention, KV cache)",
    }
    
    for node, data in sorted(stats.items()):
        tensors = data.get("count", 0)
        size_mb = data.get("size_mb", 0)
        desc = node_descriptions.get(node, "")
        lines.append(f"| {node} | {tensors} | {size_mb:.1f} | {desc} |")
    
    return "\n".join(lines)


# =============================================================================
# CLI entry point
# =============================================================================

def main():
    """CLI for ggml-numa-bindings."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="NUMA-aware model sharding bindings for llama.cpp"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # topology
    topo_parser = subparsers.add_parser("topology", help="Show NUMA topology")
    
    # recommend
    rec_parser = subparsers.add_parser("recommend", help="Recommend shard map")
    rec_parser.add_argument("--layers", type=int, required=True, help="Number of layers")
    rec_parser.add_argument("--nodes", type=int, default=4, help="Number of NUMA nodes")
    
    # analyze
    ana_parser = subparsers.add_parser("analyze", help="Analyze model tensors")
    ana_parser.add_argument("--model", required=True, help="Path to GGUF model")
    
    args = parser.parse_args()
    
    if args.command == "topology":
        topo = get_numa_topology()
        print(f"NUMA Available: {topo['numa_available']}")
        print(f"NUMA Nodes: {topo['num_nodes']}")
        print(f"Recommended Threads: {topo['recommended_threads']}")
        print(f"Platform: {topo['platform']}")
    
    elif args.command == "recommend":
        shard_map = recommend_shard_map(args.layers, args.nodes)
        print(f"GGML_NUMA_SHARD_MAP=\"{shard_map}\"")
        print()
        print(f"For {args.layers}-layer model on {args.nodes}-node system:")
        print(f"  Export the above environment variable before running llama.cpp")
    
    elif args.command == "analyze":
        print("GGUF tensor analysis requires the gguf-analyze.py script")
        print(f"Run: python numa_sharding/scripts/gguf_analyze.py --model {args.model}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
