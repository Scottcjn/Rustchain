# SPDX-License-Identifier: MIT
import json

from i18n import validate_i18n as validator


def make_valid_translation(error_count=20):
    wallet_errors = {f"wallet_{idx}": f"wallet error {idx}" for idx in range(error_count)}
    return {
        "locale": "en-US",
        "language": "English",
        "version": "1.0.0",
        "errors": {
            "wallet": wallet_errors,
            "miner": {"offline": "miner offline"},
            "network": {"timeout": "network timeout"},
            "common": {"unknown": "unknown error"},
        },
        "messages": {
            "wallet": {"created": "wallet created"},
            "miner": {"started": "miner started"},
        },
    }


def write_translation(tmp_path, data, name="en-US.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_count_all_strings_ignores_metadata_and_counts_nested_values():
    data = {
        "locale": "en-US",
        "language": "English",
        "version": "1",
        "description": "ignored",
        "errors": {
            "wallet": {
                "missing": "wallet missing",
                "nested": {"bad": "nested bad"},
            }
        },
        "messages": {"miner": {"ok": "miner ok"}},
    }

    assert validator.count_all_strings(data) == 3


def test_validate_json_structure_reports_missing_required_sections():
    data = {
        "locale": "en-US",
        "language": "English",
        "version": "1.0.0",
        "errors": {"wallet": {}, "miner": {}, "network": {}},
        "messages": {"wallet": {}},
    }

    valid, errors = validator.validate_json_structure(data)

    assert valid is False
    assert any("common" in error for error in errors)
    assert any("miner" in error for error in errors)


def test_locale_format_accepts_language_or_region_codes_only():
    assert validator.validate_locale_format("en")
    assert validator.validate_locale_format("zh-CN")
    assert not validator.validate_locale_format("EN-us")
    assert not validator.validate_locale_format("en_us")


def test_check_placeholders_reports_unbalanced_nested_placeholders():
    data = {
        "errors": {
            "wallet": {
                "missing_close": "Wallet {address",
                "missing_open": "Wallet address}",
                "balanced": "Wallet {address}",
            }
        }
    }

    warnings = validator.check_placeholders(data, "sample.json")

    assert len(warnings) == 2
    assert any("errors.wallet.missing_close" in warning for warning in warnings)
    assert any("errors.wallet.missing_open" in warning for warning in warnings)


def test_validate_translation_file_accepts_complete_file(tmp_path, capsys):
    path = write_translation(tmp_path, make_valid_translation())

    valid, errors, warnings = validator.validate_translation_file(path)

    output = capsys.readouterr().out
    assert valid is True
    assert errors == []
    assert warnings == []
    assert "23" in output


def test_validate_translation_file_reports_structure_count_and_placeholder_issues(tmp_path):
    data = make_valid_translation(error_count=2)
    data["locale"] = "en_us"
    del data["errors"]["network"]
    data["errors"]["wallet"]["bad_placeholder"] = "Wallet {address"
    path = write_translation(tmp_path, data, "broken.json")

    valid, errors, warnings = validator.validate_translation_file(path)

    assert valid is False
    assert any("network" in error for error in errors)
    assert any("20" in error for error in errors)
    assert any("en_us" in warning for warning in warnings)
    assert any("bad_placeholder" in warning for warning in warnings)
