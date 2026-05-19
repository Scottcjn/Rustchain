# SPDX-License-Identifier: MIT
import importlib.util
import io
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tests" / "fuzz_attestation_runner.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("fuzz_attestation_runner_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_configure_stdio_encoding_replaces_unencodable_status_glyphs():
    runner = load_runner()
    stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    stderr = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")

    runner.configure_stdio_encoding(stdout=stdout, stderr=stderr)

    print("🔥 RustChain Attestation Fuzz Runner", file=stdout)
    print("✅ ready", file=stderr)
    stdout.flush()
    stderr.flush()
    assert b"?" in stdout.buffer.getvalue()
    assert b"?" in stderr.buffer.getvalue()
