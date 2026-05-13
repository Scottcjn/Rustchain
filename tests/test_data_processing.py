import pytest

from src.utils.data_processing import parse_json_input


def test_parse_json_input_returns_object_payload():
    payload = parse_json_input('{"miner": "rtc-node-1", "score": 42}')

    assert payload == {"miner": "rtc-node-1", "score": 42}


def test_parse_json_input_preserves_non_object_json_values():
    payload = parse_json_input('[{"epoch": 7}, {"epoch": 8}]')

    assert payload == [{"epoch": 7}, {"epoch": 8}]


def test_parse_json_input_wraps_decode_errors():
    with pytest.raises(ValueError, match="Invalid JSON input"):
        parse_json_input('{"miner": "rtc-node-1",')
