import importlib.util
import json
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "integrations"
    / "rustchain-bounties"
    / "bounty_tracker.py"
)


def load_bounty_tracker_module():
    spec = importlib.util.spec_from_file_location("bounty_tracker_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_tracker(tmp_path):
    module = load_bounty_tracker_module()
    tracker = module.BountyTracker(
        github_token="token",
        repo="owner/repo",
        state_file=str(tmp_path / "bounty_state.json"),
    )
    return module, tracker


def test_bounty_round_trips_through_dict():
    module = load_bounty_tracker_module()
    bounty = module.Bounty(
        issue_number=42,
        title="Fix thing",
        description="Detailed bounty",
        reward_rtc=12.5,
        status="claimed",
        claimant="alice",
        claimed_at="2026-05-15T00:00:00+00:00",
        pr_url="https://github.com/owner/repo/pull/1",
        labels=["bounty", "bounty-micro"],
    )

    restored = module.Bounty.from_dict(bounty.to_dict())

    assert restored == bounty


def test_parse_reward_prefers_amount_in_issue_body(tmp_path):
    _module, tracker = make_tracker(tmp_path)

    reward = tracker._parse_reward(
        "Reward: 37.5 RTC for a focused fix",
        [{"name": "bounty-critical"}],
    )

    assert reward == 37.5


def test_parse_reward_falls_back_to_bounty_labels(tmp_path):
    _module, tracker = make_tracker(tmp_path)

    assert tracker._parse_reward("", [{"name": "bounty-critical"}]) == 150.0
    assert tracker._parse_reward("", [{"name": "bounty-major"}]) == 100.0
    assert tracker._parse_reward("", [{"name": "bounty-standard"}]) == 50.0
    assert tracker._parse_reward("", [{"name": "bounty-micro"}]) == 10.0
    assert tracker._parse_reward("", [{"name": "bounty"}]) == 25.0


def test_state_transitions_are_persisted(tmp_path):
    module, tracker = make_tracker(tmp_path)
    tracker.bounties[7] = module.Bounty(
        issue_number=7,
        title="Add tests",
        description="Cover helper behavior",
        reward_rtc=5.0,
    )

    claimed = tracker.claim_bounty(7, "alice", "https://github.com/owner/repo/pull/7")
    completed = tracker.complete_bounty(7)
    paid = tracker.mark_paid(7)

    assert claimed is not None
    assert completed is not None
    assert paid is not None
    assert paid.status == "paid"
    assert paid.claimant == "alice"
    assert paid.pr_url == "https://github.com/owner/repo/pull/7"
    assert paid.claimed_at is not None
    assert paid.paid_at is not None

    reloaded = module.BountyTracker(
        github_token="token",
        repo="owner/repo",
        state_file=tracker.state_file,
    )
    assert reloaded.bounties[7].status == "paid"
    assert reloaded.bounties[7].claimant == "alice"


def test_pending_claims_and_summary_include_claimed_and_completed(tmp_path):
    module, tracker = make_tracker(tmp_path)
    tracker.bounties = {
        1: module.Bounty(1, "Open", "", 1.0),
        2: module.Bounty(2, "Claimed", "", 2.5, status="claimed"),
        3: module.Bounty(3, "Completed", "", 4.0, status="completed"),
        4: module.Bounty(4, "Paid", "", 8.0, status="paid"),
    }

    pending = tracker.get_pending_claims()
    summary = tracker.get_summary()

    assert [b.issue_number for b in pending] == [2, 3]
    assert tracker.get_total_pending() == 6.5
    assert "**Total Bounties:** 4" in summary
    assert "**Pending Payout:** 6.50 RTC" in summary


def test_invalid_state_file_starts_empty(tmp_path):
    _module = load_bounty_tracker_module()
    state_file = tmp_path / "bad_state.json"
    state_file.write_text("{not valid json")

    module = load_bounty_tracker_module()
    tracker = module.BountyTracker(
        github_token="token",
        repo="owner/repo",
        state_file=str(state_file),
    )

    assert tracker.bounties == {}


def test_saved_state_contains_serialized_bounties(tmp_path):
    module, tracker = make_tracker(tmp_path)
    tracker.bounties[9] = module.Bounty(9, "Serialize me", "body", 3.0)

    tracker._save_state()

    data = json.loads(Path(tracker.state_file).read_text())
    assert data["bounties"][0]["issue_number"] == 9
    assert data["bounties"][0]["reward_rtc"] == 3.0
    assert data["updated_at"]
