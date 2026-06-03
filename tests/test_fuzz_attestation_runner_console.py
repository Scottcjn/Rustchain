"""Regression tests for console-safe attestation fuzz runner output."""

import importlib.util
import io
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tests" / "fuzz_attestation_runner.py"


def _load_runner_module():
    spec = importlib.util.spec_from_file_location("fuzz_attestation_runner", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_console_output_replaces_unencodable_glyphs():
    runner = _load_runner_module()
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="gbk", errors="strict")

    runner._configure_console_output((stream,))
    stream.write("🔥 RustChain Attestation Fuzz Runner")
    stream.flush()

    assert buffer.getvalue().startswith(b"? RustChain")


def test_console_output_ignores_streams_without_reconfigure():
    runner = _load_runner_module()

    runner._configure_console_output((object(),))
