# SPDX-License-Identifier: MIT
import pytest
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sophia_core import _build_analysis_prompt, _parse_ollama_response, _rule_based_fallback, VERDICTS

class TestBuildAnalysisPrompt:
      def test_contains_fingerprint(self):
                fp = {"cpu": "PowerPC G4", "clock_drift_cv": 0.005}
                prompt = _build_analysis_prompt(fp)
                assert "PowerPC G4" in prompt
                assert "clock_drift_cv" in prompt

      def test_is_string(self):
                prompt = _build_analysis_prompt({"test": 1})
                assert isinstance(prompt, str)

      def test_contains_instructions(self):
                prompt = _build_analysis_prompt({})
                assert "VERDICT" in prompt
                assert "CONFIDENCE" in prompt

  class TestParseOllamaResponse:
        def test_valid_response(self):
                  raw = "VERDICT: APPROVED\nCONFIDENCE: 0.95\nREASONING: All checks passed"
                  result = _parse_ollama_response(raw)
                  assert result["verdict"] == "APPROVED"
                  assert result["confidence"] == 0.95
                  assert result["reasoning"] == "All checks passed"

        def test_suspicious_verdict(self):
                  raw = "VERDICT: SUSPICIOUS\nCONFIDENCE: 0.7\nREASONING: Emulation detected"
                  result = _parse_ollama_response(raw)
                  assert result["verdict"] == "SUSPICIOUS"

        def test_rejected_verdict(self):
                  raw = "VERDICT: REJECTED\nCONFIDENCE: 0.9\nREASONING: Invalid hardware"
                  result = _parse_ollama_response(raw)
                  assert result["verdict"] == "REJECTED"
                  assert result["confidence"] == 0.9

        def test_missing_verdict_raises(self):
                  raw = "CONFIDENCE: 0.5\nREASONING: test"
                  with pytest.raises(ValueError):
                                _parse_ollama_response(raw)

              def test_missing_confidence_raises(self):
                        raw = "VERDICT: APPROVED\nREASONING: test"
                        with pytest.raises(ValueError):
                                      _parse_ollama_response(raw)

                    def test_missing_reasoning_raises(self):
                              raw = "VERDICT: APPROVED\nCONFIDENCE: 0.5"
                              with pytest.raises(ValueError):
                                            _parse_ollama_response(raw)

                          def test_invalid_verdict_raises(self):
                                    raw = "VERDICT: MAYBE\nCONFIDENCE: 0.5\nREASONING: unsure"
                                    with pytest.raises(ValueError):
                                                  _parse_ollama_response(raw)

                                def test_confidence_out_of_range_raises(self):
                                          raw = "VERDICT: APPROVED\nCONFIDENCE: 1.5\nREASONING: too high"
                                          with pytest.raises(ValueError):
                                                        _parse_ollama_response(raw)

                                      def test_confidence_boundary_zero(self):
                                                raw = "VERDICT: CAUTIOUS\nCONFIDENCE: 0.0\nREASONING: minimum"
                                                result = _parse_ollama_response(raw)
                                                assert result["confidence"] == 0.0

    def test_confidence_boundary_one(self):
              raw = "VERDICT: APPROVED\nCONFIDENCE: 1.0\nREASONING: maximum"
              result = _parse_ollama_response(raw)
              assert result["confidence"] == 1.0

class TestRuleBasedFallback:
      def test_empty_fingerprint(self):
                result = _rule_based_fallback({})
                assert result["verdict"] in VERDICTS
                assert 0.0 <= result["confidence"] <= 1.0
                assert isinstance(result["reasoning"], str)

    def test_low_clock_drift_suspicious(self):
              fp = {"clock_drift_cv": 0.0001}
              result = _rule_based_fallback(fp)
              assert "emulation" in result["reasoning"].lower()

    def test_normal_clock_drift(self):
              fp = {"clock_drift_cv": 0.005}
              result = _rule_based_fallback(fp)
              assert "normal" in result["reasoning"].lower()

    def test_high_clock_drift(self):
              fp = {"clock_drift_cv": 0.15}
              result = _rule_based_fallback(fp)
              assert "high" in result["reasoning"].lower() or "unstable" in result["reasoning"].lower()

    def test_valid_cache_hierarchy(self):
              fp = {"cache_hierarchy": {"l1_latency_ns": 1, "l2_latency_ns": 5, "l3_latency_ns": 20}}
              result = _rule_based_fallback(fp)
              assert "valid" in result["reasoning"].lower()

    def test_invalid_cache_hierarchy(self):
              fp = {"cache_hierarchy": {"l1_latency_ns": 10, "l2_latency_ns": 5, "l3_latency_ns": 2}}
              result = _rule_based_fallback(fp)
              assert "violate" in result["reasoning"].lower()

    def test_uniform_cache_emulation(self):
              fp = {"cache_hierarchy": {"l1_latency_ns": 5, "l2_latency_ns": 5, "l3_latency_ns": 5}}
              result = _rule_based_fallback(fp)
              assert "emulation" in result["reasoning"].lower()

    def test_impossible_low_temp(self):
              fp = {"thermal": {"cpu_temp_c": 5}}
              result = _rule_based_fallback(fp)
              assert "low" in result["reasoning"].lower()

    def test_normal_temp(self):
              fp = {"thermal": {"cpu_temp_c": 55}}
              result = _rule_based_fallback(fp)
              assert "normal" in result["reasoning"].lower()

    def test_perfect_stability_suspicious(self):
              fp = {"stability_score": 0.999}
              result = _rule_based_fallback(fp)
              assert "perfect" in result["reasoning"].lower() or "suspicious" in result["reasoning"].lower()

    def test_healthy_stability(self):
              fp = {"stability_score": 0.90}
              result = _rule_based_fallback(fp)
              assert "healthy" in result["reasoning"].lower()

    def test_combined_good_fingerprint(self):
              fp = {
                            "clock_drift_cv": 0.005,
                            "cache_hierarchy": {"l1_latency_ns": 1, "l2_latency_ns": 4, "l3_latency_ns": 15},
                            "simd_identity": {"SSE2": True, "AVX": True},
                            "thermal": {"cpu_temp_c": 55},
                            "stability_score": 0.92,
              }
              result = _rule_based_fallback(fp)
              assert result["verdict"] in ("APPROVED", "CAUTIOUS")

    def test_combined_bad_fingerprint(self):
              fp = {
                            "clock_drift_cv": 0.0001,
                            "cache_hierarchy": {"l1_latency_ns": 5, "l2_latency_ns": 5, "l3_latency_ns": 5},
                            "thermal": {"cpu_temp_c": 5},
                            "stability_score": 0.999,
              }
              result = _rule_based_fallback(fp)
              assert result["verdict"] in ("SUSPICIOUS", "REJECTED")

class TestVerdicts:
      def test_all_verdicts_have_emoji(self):
                for v in ["APPROVED", "CAUTIOUS", "SUSPICIOUS", "REJECTED"]:
                              assert v in VERDICTS
                              assert len(VERDICTS[v]) > 0
                  
