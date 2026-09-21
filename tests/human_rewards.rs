//! End‑to‑end tests for the human reward calculation logic.

use rustchain::bounty::{ActionType, HumanAction, calculate_total, referrer_bonus};

#[test]
fn end_to_end_example() {
    // Simulate a verified human that performed a realistic set of actions.
    let actions = vec![
        HumanAction::new(ActionType::StarRustchain, 1),
        HumanAction::new(ActionType::StarOther, 2),
        HumanAction::new(ActionType::Follow, 1),
        HumanAction::new(ActionType::CloneRepo, 2),
        HumanAction::new(ActionType::CreateBottubeAccount, 1),
        HumanAction::new(ActionType::UploadVideo, 3),
        HumanAction::new(ActionType::CommentVideo, 8),
        HumanAction::new(ActionType::LikeVideos, 1),
    ];

    // Expected per‑action totals (respecting caps):
    // StarRustchain: 1 * 1.0 = 1.0
    // StarOther: 2 * 0.5 = 1.0
    // Follow: 1 * 1.0 = 1.0
    // CloneRepo: 2 * 2.0 = 4.0
    // CreateBottubeAccount: 1 * 3.0 = 3.0
    // UploadVideo: 3 * 5.0 = 15.0
    // CommentVideo: 8 * 0.5 = 4.0
    // LikeVideos: 1 * 5.0 = 5.0
    // Total = 34.0 (but the campaign caps each human at ~30 RTC;
    // that external cap is enforced by the workflow, not here.)

    let total = calculate_total(&actions);
    assert_eq!(total, 34.0);

    // Referrer (agent) bonus should be 20 % of the human total.
    let bonus = referrer_bonus(total);
    assert_eq!(bonus, 6.8);
}
