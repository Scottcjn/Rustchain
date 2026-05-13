# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "validate_vintage_submission.py"
spec = importlib.util.spec_from_file_location("validate_vintage_submission", MODULE_PATH)
validate_vintage_submission = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validate_vintage_submission)

SubmissionValidator = validate_vintage_submission.SubmissionValidator


def test_wallet_validation_accepts_rtc1_alphanumeric_range():
    validator = SubmissionValidator()

    result = validator.validate_wallet("RTC1" + "A1b2C3" * 6)

    assert result["status"] == "PASS"
    assert result["checks"]["prefix"] == "RTC1"
    assert result["checks"]["format"] == "valid"


def test_wallet_validation_rejects_bad_prefix_length_and_symbols():
    validator = SubmissionValidator()

    bad_prefix = validator.validate_wallet("BTC1" + "A" * 36)
    too_short = validator.validate_wallet("RTC1" + "A" * 8)
    bad_symbols = validator.validate_wallet("RTC1" + "A" * 30 + "-")

    assert bad_prefix["status"] == "FAIL"
    assert "start with 'RTC1'" in bad_prefix["message"]
    assert too_short["status"] == "FAIL"
    assert "length invalid" in too_short["message"]
    assert bad_symbols["status"] == "FAIL"
    assert "alphanumeric" in bad_symbols["message"]


def test_attestation_log_json_requires_core_fields(tmp_path):
    validator = SubmissionValidator()
    log_path = tmp_path / "attestation.json"
    log_path.write_text('{"miner_id":"miner-1","device_arch":"ppc"}')

    result = validator.validate_attestation_log(str(log_path))

    assert result["status"] == "FAIL"
    assert "fingerprint_hash" in result["message"]
    assert "timestamp" in result["message"]
    assert result["checks"]["json_valid"] is True


def test_validate_submission_extracts_arch_and_bounty_from_valid_log(tmp_path):
    validator = SubmissionValidator()
    log_path = tmp_path / "attestation.json"
    log_path.write_text(
        '{"miner_id":"miner-1","device_arch":"m68k","fingerprint_hash":"abc","timestamp":1}'
    )

    result = validator.validate_submission(
        attestation_log_path=str(log_path),
        wallet_address="RTC1" + "Z9" * 18,
    )

    assert result["valid"] is True
    assert result["device_arch"] == "m68k"
    assert result["bounty"] == 100
    assert result["checks"]["attestation_log"]["status"] == "PASS"
    assert result["checks"]["wallet"]["status"] == "PASS"


def test_writeup_reports_missing_sections_and_short_content(tmp_path):
    validator = SubmissionValidator()
    writeup_path = tmp_path / "writeup.md"
    writeup_path.write_text("CPU: 486\nOS: DOS\n")

    result = validator.validate_writeup(str(writeup_path))

    assert result["status"] == "WARN"
    assert "memory" in result["checks"]["missing_sections"]
    assert "storage" in result["checks"]["missing_sections"]
    assert result["checks"]["word_count"] < 100
    assert validator.warnings
