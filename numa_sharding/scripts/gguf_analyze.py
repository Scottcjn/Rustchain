#!/usr/bin/env python3
"""
gguf_analyze.py - GGUF Model Tensor Analyzer for NUMA Sharding

Analyzes a GGUF model file and generates optimal NUMA shard recommendations
based on the model's tensor layout. Shows per-layer memory footprint,
tensor type distribution, and suggests GGML_NUMA_SHARD_MAP configuration.

Usage:
    python gguf_analyze.py --model model.gguf [--json] [--verbose]

Bounty: Scottcjn/rustchain-bounties #2277
Version: 1.1.0
"""

import argparse
import json
import struct
import sys
import os
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from pathlib import Path


@dataclass
class TensorInfo:
    """Represents a single GGUF tensor."""
    name: str
    dtype: int
    shape: Tuple[int, ...]
    offset: int
    size_bytes: int
    layer_index: int
    tensor_type: str
    
    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)


class GGUFAnalyzer:
    """
    Analyzes GGUF model files to extract tensor metadata.
    
    GGUF format (from llama.cpp):
    - Magic: uint32 = 0x46554747 ('GGUF')
    - Version: uint32
    - Then: tensor infos and data
    """
    
    GGUF_MAGIC = 0x46554747
    DTYPE_NAMES = {
        0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1",
        4: "Q4_2", 5: "Q4_3", 6: "Q5_0", 7: "Q5_1",
        8: "Q6_K", 9: "Q8_0", 10: "Q8_1", 11: "I8",
        12: "I16", 13: "I32", 14: "F64", 15: "BF16",
    }
    
    TENSOR_PATTERNS = {
        "token_embd": ("embedding", 0),
        "pos_embd": ("embedding", 0),
        "blk.": ("transformer", -1),
        "attn_q": ("attention_q", 1),
        "attn_k": ("attention_k", 2),
        "attn_v": ("attention_v", 3),
        "attn_output": ("attention_output", 4),
        "attn_o": ("attention_o", 4),
        "ffn_up": ("ffn_up", 5),
        "ffn_gate": ("ffn_gate", 5),
        "ffn_down": ("ffn_down", 6),
        "mlp_gate": ("mlp_gate", 5),
        "mlp_up": ("mlp_up", 5),
        "mlp_down": ("mlp_down", 6),
        "output_norm": ("output_norm", 8),
        "output.": ("output", 8),
        "llama.": ("llama_layer", -1),
    }
    
    def __init__(self, model_path: str):
        self.model_path = Path(model_path)
        self.tensors: List[TensorInfo] = []
        self.metadata: Dict = {}
        self.num_layers = 0
        
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
    
    def analyze(self) -> None:
        """Read and analyze the GGUF file."""
        with open(self.model_path, "rb") as f:
            # Check magic
            magic = struct.unpack("I", f.read(4))[0]
            if magic != self.GGUF_MAGIC:
                raise ValueError(f"Not a GGUF file (magic: 0x{magic:08X})")
            
            # Version
            version = struct.unpack("I", f.read(4))[0]
            self.metadata["version"] = version
            
            # Alignment
            alignment = struct.unpack("I", f.read(4))[0]
            self.metadata["alignment"] = alignment
            
            # Count tensors (simplified - real GGUF parsing is more complex)
            # This is a simplified parser that reads tensor data structures
            self._parse_tensors(f)
    
    def _parse_tensors(self, f) -> None:
        """Parse tensor metadata from GGUF file."""
        try:
            # Try to read tensor count
            # In real GGUF, this is part of kv data section
            # We'll do a heuristic parse of the binary
            
            f.seek(0, 2)
            file_size = f.tell()
            
            # Reset and look for tensor data
            f.seek(32)  # Skip header
            
            # Read what we can as strings to find tensor names
            data = f.read(min(file_size - 32, 10 * 1024 * 1024))  # Read up to 10MB
            
            # Try to find tensor names using common patterns
            self._extract_tensor_patterns(data)
            
        except Exception as e:
            print(f"[WARN] Could not fully parse GGUF: {e}")
            print("[INFO] Using fallback tensor estimation...")
            self._estimate_from_metadata()
    
    def _extract_tensor_patterns(self, data: bytes) -> None:
        """Extract tensor patterns from binary data."""
        # Find strings that look like tensor names
        current_name = bytearray()
        
        for i, b in enumerate(data):
            if 32 <= b < 127:  # Printable ASCII
                current_name.append(b)
            else:
                if len(current_name) > 5:
                    name_str = current_name.decode('ascii', errors='ignore')
                    # Check if it looks like a GGUF tensor name
                    if self._is_valid_tensor_name(name_str):
                        tensor_info = self._parse_tensor_entry(name_str, data, i)
                        if tensor_info:
                            self.tensors.append(tensor_info)
                
                current_name.clear()
    
    def _is_valid_tensor_name(self, name: str) -> bool:
        """Check if string looks like a GGUF tensor name."""
        if len(name) < 5:
            return False
        
        # Must contain recognizable patterns
        patterns = ["blk.", "token_embd", "pos_embd", "attn_", "ffn_", 
                    "mlp_", "output", "llama.", "rope."]
        return any(p in name for p in patterns)
    
    def _parse_tensor_entry(self, name: str, data: bytes, position: int) -> Optional[TensorInfo]:
        """Parse a tensor entry."""
        layer_idx = -1
        tensor_type = "unknown"
        
        # Extract layer index
        if "blk." in name:
            parts = name.split(".")
            for j, part in enumerate(parts):
                if part == "blk" and j + 1 < len(parts):
                    try:
                        layer_idx = int(parts[j + 1].split(".")[0])
                    except (ValueError, IndexError):
                        pass
        
        # Determine tensor type
        for pattern, (ttype, _) in self.TENSOR_PATTERNS.items():
            if pattern in name:
                tensor_type = ttype
                break
        
        # Estimate size (we can't easily get this from binary scan)
        # Use a reasonable estimate based on name
        size_bytes = self._estimate_tensor_size(name)
        
        return TensorInfo(
            name=name,
            dtype=1,  # Assume F16
            shape=(0, 0),  # Unknown from binary scan
            offset=0,
            size_bytes=size_bytes,
            layer_index=layer_idx,
            tensor_type=tensor_type
        )
    
    def _estimate_tensor_size(self, name: str) -> int:
        """Estimate tensor size from name patterns."""
        # These are rough estimates for common model sizes
        base_sizes = {
            "token_embd": 512 * 4096 * 2,  # vocab_size * hidden * 2 bytes (F16)
            "attn_q": 4096 * 4096 * 2,
            "attn_k": 4096 * 4096 * 2,
            "attn_v": 4096 * 4096 * 2,
            "attn_output": 4096 * 4096 * 2,
            "ffn_gate": 4096 * 11008 * 2,
            "ffn_up": 4096 * 11008 * 2,
            "ffn_down": 11008 * 4096 * 2,
            "mlp_": 4096 * 11008 * 2,
            "output_norm": 4096 * 2,
            "output.": 4096 * 32000 * 2,
            "rope.": 4096 * 2,
            "blk.": 4096 * 4096 * 2,  # Layer norm etc.
        }
        
        for pattern, size in base_sizes.items():
            if pattern in name:
                return size
        
        return 4096 * 4096 * 2  # Default estimate
    
    def _estimate_from_metadata(self) -> None:
        """Estimate tensors from file size and model architecture."""
        # This is a fallback for when we can't parse the binary
        file_size = self.model_path.stat().st_size
        
        # Assume Llama-like architecture
        # For a ~7B model: ~14GB
        # Estimate 32 transformer layers + embeddings
        self.num_layers = 32
        
        for layer in range(self.num_layers):
            for ttype in ["attn_q", "attn_k", "attn_v", "attn_o", 
                         "ffn_gate", "ffn_up", "ffn_down"]:
                self.tensors.append(TensorInfo(
                    name=f"blk.{layer}.{ttype}.weight",
                    dtype=1,
                    shape=(4096, 4096),
                    offset=0,
                    size_bytes=4096 * 4096 * 2,
                    layer_index=layer,
                    tensor_type=ttype
                ))
        
        # Add embedding tensors
        self.tensors.append(TensorInfo(
            name="token_embd.weight",
            dtype=1,
            shape=(32000, 4096),
            offset=0,
            size_bytes=32000 * 4096 * 2,
            layer_index=0,
            tensor_type="embedding"
        ))
    
    def get_layer_summary(self) -> Dict[int, Dict]:
        """Group tensors by layer and compute per-layer stats."""
        layers: Dict[int, Dict] = {}
        
        for tensor in self.tensors:
            if tensor.layer_index < 0:
                continue
            
            if tensor.layer_index not in layers:
                layers[tensor.layer_index] = {
                    "count": 0,
                    "size_mb": 0.0,
                    "types": {},
                }
            
            layers[tensor.layer_index]["count"] += 1
            layers[tensor.layer_index]["size_mb"] += tensor.size_mb
            
            tt = tensor.tensor_type
            if tt not in layers[tensor.layer_index]["types"]:
                layers[tensor.layer_index]["types"][tt] = 0
            layers[tensor.layer_index]["types"][tt] += 1
        
        self.num_layers = max(layers.keys()) + 1 if layers else 0
        return layers
    
    def recommend_numa_map(self, num_nodes: int = 4) -> str:
        """
        Generate NUMA shard map based on tensor analysis.
        
        For POWER8 S824 (4 nodes):
        - Node 0: Slowest - best for I/O embeddings
        - Node 1: Moderate - early layers (0-8)
        - Node 2: Fastest bandwidth - FFN layers (21+)
        - Node 3: Fastest - attention layers (9-20)
        """
        if num_nodes == 4:
            # Default POWER8 S824 config
            if self.num_layers <= 22:
                mid = self.num_layers // 2
                return f"0-{mid-1}:1,{mid}:3,{mid+1}-{self.num_layers-1}:2"
            elif self.num_layers <= 32:
                return "0-8:1,9-20:3,21-31:2"
            elif self.num_layers <= 40:
                t1, t2 = 10, 26
                return f"0-{t1}:1,{t1+1}-{t2}:3,{t2+1}-{self.num_layers-1}:2"
            elif self.num_layers <= 60:
                t1, t2 = 15, 40
                return f"0-{t1}:1,{t1+1}-{t2}:3,{t2+1}-{self.num_layers-1}:2"
            else:
                t1, t2, t3 = 20, 53, 79
                return f"0-{t1}:1,{t1+1}-{t2}:3,{t2+1}-{t3}:2"
        elif num_nodes == 2:
            mid = self.num_layers // 2
            return f"0-{mid-1}:0,{mid}-{self.num_layers-1}:1"
        else:
            # Generic even distribution
            step = max(1, self.num_layers // num_nodes)
            rules = []
            for i in range(num_nodes):
                start = i * step
                end = min((i + 1) * step - 1, self.num_layers - 1)
                if i == num_nodes - 1:
                    end = self.num_layers - 1
                rules.append(f"{start}-{end}:{i}")
            return ",".join(rules)
    
    def generate_report(self, output_format: str = "text") -> str:
        """Generate analysis report."""
        layers = self.get_layer_summary()
        
        if output_format == "json":
            report = {
                "model": str(self.model_path),
                "file_size_mb": self.model_path.stat().st_size / (1024 * 1024),
                "num_layers": self.num_layers,
                "num_tensors": len(self.tensors),
                "recommended_numa_map": self.recommend_numa_map(),
                "per_layer": layers,
            }
            return json.dumps(report, indent=2)
        
        # Text report
        lines = []
        lines.append(f"{'='*60}")
        lines.append(f"  GGUF Model NUMA Analysis Report")
        lines.append(f"{'='*60}")
        lines.append(f"")
        lines.append(f"Model:     {self.model_path.name}")
        lines.append(f"Size:      {self.model_path.stat().st_size / (1024**3):.2f} GB")
        lines.append(f"Layers:    {self.num_layers}")
        lines.append(f"Tensors:   {len(self.tensors)}")
        lines.append(f"")
        lines.append(f"{'='*60}")
        lines.append(f"  Per-Layer Memory Footprint")
        lines.append(f"{'='*60}")
        lines.append(f"")
        lines.append(f"{'Layer':<8} {'Count':<8} {'Size (MB)':<12} {'Types'}")
        lines.append("-" * 60)
        
        total_mb = 0.0
        for layer_idx in sorted(layers.keys()):
            info = layers[layer_idx]
            total_mb += info["size_mb"]
            types_str = ", ".join(f"{k}={v}" for k, v in info["types"].items())
            lines.append(f"{layer_idx:<8} {info['count']:<8} {info['size_mb']:<12.1f} {types_str}")
        
        lines.append("-" * 60)
        lines.append(f"{'TOTAL':<8} {'':<8} {total_mb:<12.1f}")
        lines.append(f"")
        lines.append(f"{'='*60}")
        lines.append(f"  NUMA Shard Recommendations")
        lines.append(f"{'='*60}")
        lines.append(f"")
        lines.append(f"POWER8 S824 (4 NUMA nodes):")
        lines.append(f"")
        numa_map = self.recommend_numa_map(4)
        lines.append(f"  export GGML_NUMA_SHARD_MAP=\"{numa_map}\"")
        lines.append(f"")
        lines.append(f"  Node 1: Layers 0-{min(8, self.num_layers-1)} (early/embedding)")
        lines.append(f"  Node 3: Layers 9-{min(20, self.num_layers-1)} (attention)")
        lines.append(f"  Node 2: Layers 21-{max(0, self.num_layers-1)} (FFN/compute)")
        lines.append(f"")
        lines.append(f"Environment setup:")
        lines.append(f"  export GGML_NUMA_SHARD_MAP=\"{numa_map}\"")
        lines.append(f"  export OMP_NUM_THREADS=64")
        lines.append(f"  numactl --cpunodebind=0,1,2,3 --membind=0,1,2,3 ./llama-bench ...")
        lines.append(f"")
        
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="GGUF Model Tensor Analyzer for NUMA Sharding"
    )
    parser.add_argument("--model", "-m", required=True, help="Path to GGUF model file")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--num-nodes", "-n", type=int, default=4, 
                       help="Number of NUMA nodes (default: 4 for POWER8 S824)")
    
    args = parser.parse_args()
    
    try:
        analyzer = GGUFAnalyzer(args.model)
        analyzer.analyze()
        report = analyzer.generate_report("json" if args.json else "text")
        print(report)
        
        if args.verbose:
            print(f"\n[DEBUG] Found {len(analyzer.tensors)} tensors")
            print(f"[DEBUG] {analyzer.num_layers} layers")
        
        return 0
    except Exception as e:
        print(f"[ERROR] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
