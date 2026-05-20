# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "mining-video-pipeline"
    / "mining_video_pipeline.py"
)
spec = importlib.util.spec_from_file_location("mining_video_pipeline", MODULE_PATH)
mining_video_pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mining_video_pipeline)


def test_fetch_miners_accepts_paginated_api_envelope(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "miners": [
                    {
                        "miner_id": "alice-id",
                        "device_arch": "G4",
                        "device_family": "PowerPC",
                        "hardware_type": "PowerPC (Vintage)",
                        "antiquity_multiplier": 3,
                        "entropy_score": 0.8,
                    },
                    {"miner": "bob", "device_arch": "SPARC"},
                    "bad-row",
                ],
                "pagination": {"total": 3, "limit": 3, "offset": 0, "count": 3},
            }

    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(mining_video_pipeline.requests, "get", fake_get)

    miners = mining_video_pipeline.fetch_miners()

    assert calls == [
        (
            f"{mining_video_pipeline.RUSTCHAIN_API}/api/miners",
            {"verify": False, "timeout": 30},
        )
    ]
    assert [miner.miner_id for miner in miners] == ["alice-id", "bob"]
    assert miners[0].device_arch == "G4"
    assert miners[0].style == mining_video_pipeline.ARCH_STYLES["PowerPC (Vintage)"]
