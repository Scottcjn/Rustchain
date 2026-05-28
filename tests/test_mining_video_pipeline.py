# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "mining-video-pipeline"
    / "mining_video_pipeline.py"
)
spec = importlib.util.spec_from_file_location("mining_video_pipeline", MODULE_PATH)
mining_video_pipeline = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mining_video_pipeline)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_fetch_miners_accepts_enveloped_miner_payload(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(
            {
                "miners": [
                    {
                        "miner": "miner-a",
                        "device_arch": "ppc64",
                        "device_family": "PowerPC",
                        "hardware_type": "PowerPC (Vintage)",
                        "antiquity_multiplier": 1.7,
                        "entropy_score": 42,
                        "last_attest": 1_700_000_000,
                    }
                ],
                "pagination": {"total": 1},
            }
        )

    monkeypatch.setattr(mining_video_pipeline.requests, "get", fake_get)

    miners = mining_video_pipeline.fetch_miners()

    assert calls == [
        (
            "https://50.28.86.131/api/miners",
            {"verify": False, "timeout": 30},
        )
    ]
    assert len(miners) == 1
    assert miners[0].miner_id == "miner-a"
    assert miners[0].device_arch == "ppc64"
    assert miners[0].hardware_type == "PowerPC (Vintage)"


def test_fetch_miners_ignores_malformed_envelope_rows(monkeypatch):
    monkeypatch.setattr(
        mining_video_pipeline.requests,
        "get",
        lambda *_args, **_kwargs: FakeResponse({"miners": [None, "bad"]}),
    )

    assert mining_video_pipeline.fetch_miners() == []
