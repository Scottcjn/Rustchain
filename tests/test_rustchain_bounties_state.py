import importlib.util
import json
from pathlib import Path


def load_state_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "integrations"
        / "rustchain-bounties"
        / "state.py"
    )
    spec = importlib.util.spec_from_file_location("rustchain_bounties_state", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_new_state_uses_default_schema(tmp_path):
    module = load_state_module()
    state = module.TipState(str(tmp_path / "tips.json"))

    assert state.tip_log == []
    assert state.get_pending_payouts() == []
    assert state.is_processed("owner/repo/1") is False


def test_load_migrates_older_state_file(tmp_path):
    module = load_state_module()
    state_file = tmp_path / "tips.json"
    state_file.write_text(json.dumps({"version": 0, "tip_log": []}))

    state = module.TipState(str(state_file))

    assert state._data == {
        "processed_comment_ids": [],
        "tip_log": [],
        "version": module.TipState.VERSION,
    }


def test_load_recovers_from_invalid_json(tmp_path):
    module = load_state_module()
    state_file = tmp_path / "tips.json"
    state_file.write_text("{not json")

    state = module.TipState(str(state_file))

    assert state._data["version"] == module.TipState.VERSION
    assert state.tip_log == []


def test_record_tip_marks_processed_and_saves_state(tmp_path):
    module = load_state_module()
    state_file = tmp_path / "tips.json"
    state = module.TipState(str(state_file))

    state.record_tip(
        idempotency_key="owner/repo/123",
        issue_or_pr=42,
        sender="Scottcjn",
        recipient="contributor",
        amount=2.5,
        token="RTC",
        context_url="https://github.com/owner/repo/issues/42#issuecomment-123",
    )
    state.save()

    reloaded = module.TipState(str(state_file))
    assert reloaded.is_processed("owner/repo/123") is True
    assert len(reloaded.tip_log) == 1
    tip = reloaded.tip_log[0]
    assert tip["id"] == "owner/repo/123"
    assert tip["issue_or_pr"] == 42
    assert tip["sender"] == "Scottcjn"
    assert tip["recipient"] == "contributor"
    assert tip["amount"] == 2.5
    assert tip["token"] == "RTC"
    assert tip["status"] == "pending_payout"
    assert tip["context_url"].endswith("#issuecomment-123")
    assert "timestamp" in tip


def test_pending_payouts_and_mark_paid(tmp_path):
    module = load_state_module()
    state = module.TipState(str(tmp_path / "tips.json"))
    state.record_tip("owner/repo/1", 1, "sender", "alice", 1, "RTC", "url-1")
    state.record_tip("owner/repo/2", 2, "sender", "bob", 2, "RTC", "url-2")

    state.mark_paid("owner/repo/1", tx_ref="tx-abc")

    assert state.get_pending_payouts() == [state.tip_log[1]]
    assert state.tip_log[0]["status"] == "paid"
    assert state.tip_log[0]["tx_ref"] == "tx-abc"
    assert state.tip_log[1]["status"] == "pending_payout"
