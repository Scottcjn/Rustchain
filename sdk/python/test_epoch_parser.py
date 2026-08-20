#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the epoch payload parser (issue #7962).

These tests verify that the parser handles large payloads (>100KB)
correctly, including edge cases around buffer size limits, encoding
errors, and malformed responses.
"""

import json
import pytest

from rustchain_sdk.epoch_parser import (
    parse_epoch_payload,
    parse_epoch_payload_safe,
    MAX_PAYLOAD_BYTES,
    MIN_PAYLOAD_BYTES,
    validate_epoch_data,
    extract_miners_from_payload,
)


class TestParseEpochPayload:
    """Unit tests for parse_epoch_payload function."""

    def test_normal_epoch_response(self):
        """Test parsing a normal epoch response."""
        epoch_data = {
            "epoch": 74,
            "slot": 10745,
            "blocks_per_epoch": 144,
            "enrolled_miners": 32,
            "epoch_pot": 1.5,
        }
        raw = json.dumps(epoch_data).encode("utf-8")
        parsed, error = parse_epoch_payload(raw)
        assert error is None
        assert parsed["epoch"] == 74
        assert parsed["slot"] == 10745
        assert parsed["blocks_per_epoch"] == 144

    def test_empty_payload(self):
        """Test that empty payload is rejected."""
        parsed, error = parse_epoch_payload(b"")
        assert error is not None
        assert "Empty payload" in error
        assert parsed is None

    def test_too_small_payload(self):
        """Test that payload below minimum size is rejected."""
        parsed, error = parse_epoch_payload(b"{")
        assert error is not None
        assert "Payload too small" in error

    def test_non_bytes_input(self):
        """Test that non-bytes input is rejected."""
        parsed, error = parse_epoch_payload("not bytes")
        assert error is not None
        assert "Expected bytes" in error

    def test_oversized_payload(self):
        """Test that payload exceeding max size is rejected."""
        large_data = {"data": "x" * (MAX_PAYLOAD_BYTES + 1)}
        raw = json.dumps(large_data).encode("utf-8")
        parsed, error = parse_epoch_payload(raw)
        assert error is not None
        assert "exceeds maximum" in error

    def test_large_payload_normal(self):
        """Test that large payloads (100KB+) parse correctly."""
        miners = []
        for i in range(1000):
            miners.append(
                {
                    "miner_id": "RTC{:03d}aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa".format(i),
                    "device_arch": ["g4", "g5", "pentium3", "modern"][i % 4],
                    "fingerprint_passed": 1 if i % 3 != 0 else 0,
                    "antiquity_multiplier": 1.0 + (i % 10) * 0.1,
                    "last_attest_ts": 1700000000 + i * 60,
                }
            )
        epoch_data = {
            "epoch": 100,
            "slot": 10000,
            "miners": miners,
            "total_blocks": 14400,
            "epoch_pot_rtc": 150.0,
        }
        raw = json.dumps(epoch_data).encode("utf-8")
        assert len(raw) > 100000, "Test payload should be >100KB"
        parsed, error = parse_epoch_payload(raw)
        assert error is None
        assert parsed["epoch"] == 100
        assert len(parsed["miners"]) == 1000
        assert parsed["slot"] == 10000

    def test_large_payload_boundary_100kb(self):
        """Test payload at exactly ~100KB boundary."""
        epoch_data = {
            "epoch": 50,
            "slot": 5000,
            "data": "x" * 100000,
        }
        raw = json.dumps(epoch_data).encode("utf-8")
        assert len(raw) >= 100000
        parsed, error = parse_epoch_payload(raw)
        assert error is None
        assert parsed["epoch"] == 50

    def test_utf8_bom_handling(self):
        """Test handling of UTF-8 BOM."""
        epoch_data = {"epoch": 1, "slot": 100}
        raw = json.dumps(epoch_data).encode("utf-8")
        raw = b"\xef\xbb\xbf" + raw
        parsed, error = parse_epoch_payload(raw)
        assert error is None
        assert parsed["epoch"] == 1

    def test_html_response_detection(self):
        """Test that HTML responses are detected and rejected."""
        html = "<html><body>502 Bad Gateway</body></html>"
        raw = html.encode("utf-8")
        parsed, error = parse_epoch_payload(raw)
        assert error is not None
        assert "HTML response" in error

    def test_malformed_json(self):
        """Test that malformed JSON is handled gracefully."""
        raw = b"{invalid json"
        parsed, error = parse_epoch_payload(raw)
        assert error is not None
        assert "JSON decode error" in error

    def test_whitespace_padding(self):
        """Test that whitespace around JSON is handled."""
        epoch_data = {"epoch": 42}
        raw = ("  " + chr(10) + "  " + json.dumps(epoch_data) + "  " + chr(10) + "  ").encode(
            "utf-8"
        )
        parsed, error = parse_epoch_payload(raw)
        assert error is None
        assert parsed["epoch"] == 42

    def test_list_payload(self):
        """Test that list payloads return a wrapped dict."""
        raw = json.dumps([1, 2, 3]).encode("utf-8")
        parsed, error = parse_epoch_payload(raw)
        assert error is None
        assert "_raw_list" in parsed
        assert parsed["_raw_list"] == [1, 2, 3]

    def test_empty_json_object(self):
        """Test that empty JSON object {} is rejected."""
        raw = b"{}"
        parsed, error = parse_epoch_payload(raw)
        assert error is not None
        assert "Empty JSON object" in error

    def test_minimal_valid_payload(self):
        """Test the smallest valid payload works."""
        raw = b'{"epoch": 1}'
        parsed, error = parse_epoch_payload(raw)
        assert error is None
        assert parsed["epoch"] == 1


class TestParseEpochPayloadSafe:
    """Tests for the safe wrapper function."""

    def test_safe_returns_dict_on_success(self):
        """Test that safe parser returns dict on valid input."""
        raw = json.dumps({"epoch": 1}).encode("utf-8")
        result = parse_epoch_payload_safe(raw)
        assert isinstance(result, dict)
        assert result["epoch"] == 1
        assert result["parsed"] is True

    def test_safe_returns_dict_on_error(self):
        """Test that safe parser returns error dict on invalid input."""
        result = parse_epoch_payload_safe(b"")
        assert isinstance(result, dict)
        assert "error" in result
        assert "raw_size" in result
        assert result["raw_size"] == 0
        assert result["parsed"] is False

    def test_safe_preserves_original_data(self):
        """Test that safe parser preserves original data."""
        epoch_data = {"epoch": 99, "slot": 9999, "miners": 10}
        raw = json.dumps(epoch_data).encode("utf-8")
        result = parse_epoch_payload_safe(raw)
        assert result["epoch"] == 99
        assert result["slot"] == 9999
        assert result["miners"] == 10


class TestMaxPayloadSize:
    """Tests for payload size constant."""

    def test_max_is_two_megabytes(self):
        """Test that MAX_PAYLOAD_BYTES is 2MB."""
        assert MAX_PAYLOAD_BYTES == 2 * 1024 * 1024

    def test_min_is_two_bytes(self):
        """Test that MIN_PAYLOAD_BYTES is 2."""
        assert MIN_PAYLOAD_BYTES == 2

    def test_max_accepts_exactly_two_megabytes(self):
        """Test that a payload at the max boundary is accepted."""
        # JSON overhead: {"epoch": 1, "data": "} = 24 bytes
        max_len = MAX_PAYLOAD_BYTES - 24
        epoch_data = {"epoch": 1, "data": "x" * max_len}
        raw = json.dumps(epoch_data).encode("utf-8")
        assert len(raw) <= MAX_PAYLOAD_BYTES, "Payload {} > {}".format(len(raw), MAX_PAYLOAD_BYTES)
        parsed, error = parse_epoch_payload(raw)
        assert error is None
        assert parsed["epoch"] == 1


class TestIntegrationClientUsage:
    """Integration-style tests simulating client usage."""

    def test_client_normal_request(self):
        """Simulate a normal SDK client request."""
        response_body = json.dumps(
            {
                "epoch": 74,
                "slot": 10745,
                "blocks_per_epoch": 144,
                "enrolled_miners": 32,
                "epoch_pot": 1.5,
                "settled": False,
                "total_supply_rtc": 21000000.0,
            }
        ).encode("utf-8")
        result = parse_epoch_payload_safe(response_body)
        assert result["epoch"] == 74
        assert result["slot"] == 10745
        assert result["enrolled_miners"] == 32

    def test_client_large_request(self):
        """Simulate SDK client handling a large epoch response."""
        miners = []
        for i in range(500):
            miners.append(
                {
                    "miner_id": "RTC{:03d}aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa".format(i),
                    "device_arch": ["g4", "g5", "modern"][i % 3],
                    "fingerprint_passed": 1,
                }
            )
        response_body = json.dumps(
            {
                "epoch": 200,
                "slot": 20000,
                "miners": miners,
                "total_pot": 300.0,
            }
        ).encode("utf-8")
        assert len(response_body) > 50000
        result = parse_epoch_payload_safe(response_body)
        assert result["epoch"] == 200
        assert len(result["miners"]) == 500


class TestValidateEpochData:
    """Tests for validate_epoch_data function."""

    def test_valid_epoch_data(self):
        """Test validation of well-formed epoch data."""
        data = {"epoch": 74, "slot": 10745, "miners": 32}
        valid, errors = validate_epoch_data(data)
        assert valid is True
        assert len(errors) == 0

    def test_missing_required_fields(self):
        """Test validation with missing required fields."""
        data = {"slot": 10745}
        valid, errors = validate_epoch_data(data)
        assert valid is False
        assert any("epoch" in e for e in errors)

    def test_invalid_epoch_type(self):
        """Test validation with wrong epoch type."""
        data = {"epoch": "74"}
        valid, errors = validate_epoch_data(data)
        assert valid is False
        assert any("integer" in e for e in errors)

    def test_negative_epoch(self):
        """Test validation with negative epoch."""
        data = {"epoch": -1}
        valid, errors = validate_epoch_data(data)
        assert valid is False
        assert any("negative" in e for e in errors)


class TestExtractMinersFromPayload:
    """Tests for extract_miners_from_payload function."""

    def test_extract_miners_from_dict(self):
        """Test extracting miners from standard dict."""
        data = {
            "epoch": 74,
            "miners": [
                {"miner_id": "RTC001aaa", "fingerprint_passed": 1},
                {"miner_id": "RTC002bbb", "fingerprint_passed": 0},
            ],
        }
        miners = extract_miners_from_payload(data)
        assert len(miners) == 2
        assert miners[0]["miner_id"] == "RTC001aaa"

    def test_extract_miners_with_nested_format(self):
        """Test extracting miners from nested format."""
        data = {
            "data": [
                {"miner": {"miner_id": "RTC001", "hashrate": 1000}},
                {"miner": {"miner_id": "RTC002", "hashrate": 2000}},
            ]
        }
        miners = extract_miners_from_payload(data)
        assert len(miners) == 2
        assert miners[0]["miner_id"] == "RTC001"

    def test_extract_miners_from_list(self):
        """Test extracting miners from embedded list."""
        data = {
            "_raw_list": [
                {"miner_id": "RTC001", "fingerprint_passed": 1},
                {"miner_id": "RTC002", "fingerprint_passed": 0},
            ]
        }
        miners = extract_miners_from_payload(data)
        assert len(miners) == 2
        assert miners[0]["miner_id"] == "RTC001"

    def test_no_miners_key(self):
        """Test when miners key doesn't exist."""
        data = {"epoch": 74, "slot": 100}
        miners = extract_miners_from_payload(data)
        assert miners == []

    def test_miners_is_not_list(self):
        """Test when miners key exists but isn't a list."""
        data = {"epoch": 74, "miners": {"count": 32}}
        miners = extract_miners_from_payload(data)
        assert miners == []
