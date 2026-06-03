from __future__ import annotations

import importlib.util
import struct
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "llm" / "numa_shard_config.py"
SPEC = importlib.util.spec_from_file_location("numa_shard_config", MODULE_PATH)
numa_shard_config = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(numa_shard_config)


def _nodes(count: int) -> list[dict[str, int]]:
    return [{"id": node_id, "mem_total_gb": 128} for node_id in range(count)]


def _write_gguf_header(path: Path, *, magic: bytes = b"GGUF", tensor_count: int = 94) -> None:
    path.write_bytes(magic + struct.pack("<I", 3) + struct.pack("<Q", tensor_count))


def test_generate_shard_map_uses_power8_bandwidth_order():
    shard_map = numa_shard_config.generate_shard_map(32, _nodes(4))

    assert shard_map == "0-9:node3,10-18:node2,19-26:node1,27-31:node0,attn:node3"


def test_generate_shard_map_returns_none_without_nodes():
    assert numa_shard_config.generate_shard_map(32, []) is None


def test_read_gguf_layers_estimates_layers_from_tensor_count(tmp_path):
    model_path = tmp_path / "model.gguf"
    _write_gguf_header(model_path, tensor_count=94)

    assert numa_shard_config.read_gguf_layers(model_path) == 9


def test_read_gguf_layers_rejects_non_gguf_file(tmp_path):
    model_path = tmp_path / "model.bin"
    _write_gguf_header(model_path, magic=b"NOPE")

    assert numa_shard_config.read_gguf_layers(model_path) is None
