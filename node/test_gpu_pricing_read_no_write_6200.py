"""
Unit tests for Issue #6200: GPU pricing reads should not append persistent
history rows.

Verifies that:
1. Repeated calls to get_fair_market_rates() do not insert rows into
   pricing_history (the read path is now write-free).
2. record_pricing_sample() explicitly writes to pricing_history when called
   from write paths.

Run: python -m pytest node/test_gpu_pricing_read_no_write_6200.py -v
"""

import pytest
import os
import sqlite3
import tempfile
import sys

sys.path.insert(0, os.path.dirname(__file__))

from gpu_render_protocol import GPURenderProtocol


class TestGPUPricingReadNoWrite:
    """Issue #6200: GET /render/pricing must not cause persistent writes."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "gpu_test.db")
        self.proto = GPURenderProtocol(db_path=self.db_path)
        # Attest a GPU node so get_fair_market_rates has data
        self.proto.attest_gpu("miner-1", {
            "gpu_model": "RTX 4090",
            "vram_gb": 24,
            "device_arch": "nvidia_gpu",
            "price_render_minute": 0.5,
        })

    def _count_pricing_history(self):
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM pricing_history").fetchone()[0]

    def test_single_read_no_history_rows(self):
        """A single pricing read should not add any pricing_history rows."""
        self.proto.get_fair_market_rates("render")
        assert self._count_pricing_history() == 0

    def test_repeated_reads_no_history_growth(self):
        """Repeated pricing reads should not grow pricing_history."""
        for _ in range(5):
            self.proto.get_fair_market_rates("render")
        assert self._count_pricing_history() == 0

    def test_all_job_types_read_no_history(self):
        """Reading all job types at once should not write history."""
        self.proto.get_fair_market_rates()
        assert self._count_pricing_history() == 0

    def test_record_pricing_sample_writes(self):
        """Explicit record_pricing_sample should write to pricing_history."""
        rates = self.proto.get_fair_market_rates("render")
        assert "rates" in rates
        result = self.proto.record_pricing_sample("render", rates["rates"])
        assert result["ok"] is True
        assert self._count_pricing_history() == 1

    def test_record_pricing_sample_repeated(self):
        """Multiple explicit recordings should grow history."""
        rates = self.proto.get_fair_market_rates("render")
        for _ in range(3):
            self.proto.record_pricing_sample("render", rates["rates"])
        assert self._count_pricing_history() == 3

    def test_record_pricing_sample_invalid_job_type(self):
        """Recording with invalid job_type should return error."""
        result = self.proto.record_pricing_sample("invalid_type", {})
        assert "error" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
