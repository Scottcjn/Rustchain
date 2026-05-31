import pytest
from sophia_governor import _heuristic_review, _parse_transfer_amount

def test_parse_transfer_amount():
    assert _parse_transfer_amount(10.5) == 10.5
    assert _parse_transfer_amount(10) == 10.0
    assert _parse_transfer_amount("10.5") == 10.5
    # Malformed cases
    assert _parse_transfer_amount(["bad"]) is None
    assert _parse_transfer_amount({"bad": "val"}) is None
    assert _parse_transfer_amount(True) is None
    assert _parse_transfer_amount(False) is None
    assert _parse_transfer_amount(None) is None
    assert _parse_transfer_amount("bad string") is None

def test_heuristic_review_pending_transfer_malformed():
    # Array payload
    payload = {"amount_rtc": ["bad"]}
    result = _heuristic_review("pending_transfer", payload)
    
    assert result["risk_level"] == "high"
    assert "malformed_amount" in result["signals"]
    assert "review malformed transfer amount" in result["recommended_actions"]
    
    # Boolean payload
    payload2 = {"amount_rtc": True}
    result2 = _heuristic_review("pending_transfer", payload2)
    assert result2["risk_level"] == "high"
    assert "malformed_amount" in result2["signals"]
    
    # Missing payload completely, but i64 is present and valid
    payload3 = {"amount_i64": 1_000_000}
    result3 = _heuristic_review("pending_transfer", payload3)
    # Should not flag malformed because amount_i64 parsed fine
    assert "malformed_amount" not in result3.get("signals", [])

    # valid rtc string
    payload4 = {"amount_rtc": "2.5"}
    result4 = _heuristic_review("pending_transfer", payload4)
    assert "malformed_amount" not in result4.get("signals", [])
