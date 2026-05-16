# SPDX-License-Identifier: MIT
"""Unit tests for replay_defense.py - Bounty #1589"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from replay_defense import ReplayDefenseResult, _compute_hardware_id


class TestAllowedResult:
          def test_default_reason(self):
                        r = ReplayDefenseResult.allowed_result()
                        assert r.reason == "ok"

          def test_custom_reason(self):
                        r = ReplayDefenseResult.allowed_result("unavailable")
                        assert r.reason == "unavailable"

          def test_is_not_replay(self):
                        r = ReplayDefenseResult.allowed_result()
                        assert r.is_replay is False

          def test_is_allowed(self):
                        r = ReplayDefenseResult.allowed_result()
                        assert r.allowed is True

          def test_http_200(self):
                        r = ReplayDefenseResult.allowed_result()
                        assert r.http_status == 200


class TestReplayDetected:
          def test_is_replay(self):
                        r = ReplayDefenseResult.replay_detected("hash_match")
                        assert r.is_replay is True

          def test_not_allowed(self):
                        r = ReplayDefenseResult.replay_detected("hash_match")
                        assert r.allowed is False

          def test_http_409(self):
                        r = ReplayDefenseResult.replay_detected("hash_match")
                        assert r.http_status == 409

          def test_reason(self):
                        r = ReplayDefenseResult.replay_detected("entropy")
                        assert r.reason == "entropy"

          def test_details(self):
                        d = {"hash": "abc"}
                        r = ReplayDefenseResult.replay_detected("m", d)
                        assert r.details == d

          def test_details_none(self):
                        r = ReplayDefenseResult.replay_detected("m")
                        assert r.details is None


class TestRateLimited:
          def test_not_replay(self):
                        r = ReplayDefenseResult.rate_limited()
                        assert r.is_replay is False

          def test_not_allowed(self):
                        r = ReplayDefenseResult.rate_limited()
                        assert r.allowed is False

          def test_http_429(self):
                        r = ReplayDefenseResult.rate_limited()
                        assert r.http_status == 429

          def test_reason(self):
                        r = ReplayDefenseResult.rate_limited()
                        assert r.reason == "rate_limit_exceeded"


class TestHardwareId:
          def test_none(self):
                        assert _compute_hardware_id(None) is None

          def test_non_dict(self):
                        assert _compute_hardware_id("x") is None
                        assert _compute_hardware_id(42) is None

          def test_cache_hash(self):
                        fp = {"checks": {"cache_timing": {"data": {"cache_hash": "abc123"}}}}
                        assert _compute_hardware_id(fp) == "hw_abc123"

          def test_empty(self):
                        r = _compute_hardware_id({})
                        assert r is None or isinstance(r, str)


class TestDefaults:
          def test_details_none(self):
                        r = ReplayDefenseResult(is_replay=False, reason="t", allowed=True)
                        assert r.details is None

          def test_http_default(self):
                        r = ReplayDefenseResult(is_replay=False, reason="t", allowed=True)
                        assert r.http_status == 200

          def test_custom_status(self):
                        r = ReplayDefenseResult(is_replay=False, reason="t", allowed=True, http_status=503)
                        assert r.http_status == 503
                
