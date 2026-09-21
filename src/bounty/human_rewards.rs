//! Human rewards calculation for the **Bring Your Human to Work Day** bounty.
//!
//! This module implements the per‑action RTC rates and caps defined in
//! issue #2634 and provides a helper to compute the total reward for a
//! verified human as well as the 20 % referrer bonus for the agent that
//! introduced the human.
//!
//! The implementation is deliberately lightweight and does not perform any
//! network calls – it only works with already‑validated actions. Validation
//! (GitHub account age, contribution count, etc.) should be performed by the
//! surrounding workflow before constructing the `HumanAction` list.

/// The different actions a verified human can perform that earn RTC.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum ActionType {
    /// Star the `Scottcjn/Rustchain` repository (1 RTC, max 1×).
    StarRustchain,
    /// Star any other `Scottcjn` repository (0.5 RTC, max 3×).
    StarOther,
    /// Follow the `@Scottcjn` GitHub account (1 RTC, max 1×).
    Follow,
    /// Clone a repository on real hardware (2 RTC, max 2×).
    CloneRepo,
    /// Create a verified human account on BoTTube (3 RTC, max 1×).
    CreateBottubeAccount,
    /// Upload a real 30 + sec video to BoTTube (5 RTC, max 3×).
    UploadVideo,
    /// Substantive comment on an agent video (0.5 RTC, max 10×).
    CommentVideo,
    /// Like 20 agent videos in one session (5 RTC, max 1×).
    LikeVideos,
}

impl ActionType {
    /// Returns the RTC reward for a single occurrence of the action.
    pub const fn reward(self) -> f64 {
        match self {
            ActionType::StarRustchain => 1.0,
            ActionType::StarOther => 0.5,
            ActionType::Follow => 1.0,
            ActionType::CloneRepo => 2.0,
            ActionType::CreateBottubeAccount => 3.0,
            ActionType::UploadVideo => 5.0,
            ActionType::CommentVideo => 0.5,
            ActionType::LikeVideos => 5.0,
        }
    }

    /// Returns the maximum number of times the action can be counted toward the cap.
    pub const fn cap(self) -> u32 {
        match self {
            ActionType::StarRustchain => 1,
            ActionType::StarOther => 3,
            ActionType::Follow => 1,
            ActionType::CloneRepo => 2,
            ActionType::CreateBottubeAccount => 1,
            ActionType::UploadVideo => 3,
            ActionType::CommentVideo => 10,
            ActionType::LikeVideos => 1,
        }
    }
}

/// A concrete action performed by a verified human together with the
/// number of times it was performed.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HumanAction {
    /// The type of action.
    pub action_type: ActionType,
    /// How many times the action was performed (may exceed the cap; the
    /// calculation will clamp it).
    pub count: u32,
}

impl HumanAction {
    /// Create a new `HumanAction`.
    pub fn new(action_type: ActionType, count: u32) -> Self {
        Self { action_type, count }
    }
}

/// Compute the total RTC reward for a list of human actions, respecting
/// per‑action caps. The result is rounded to two decimal places (the smallest
/// unit of RTC is 0.01).
pub fn calculate_total(actions: &[HumanAction]) -> f64 {
    let mut total = 0.0_f64;

    for act in actions {
        let effective = act.count.min(act.action_type.cap());
        total += (effective as f64) * act.action_type.reward();
    }

    // Round to two decimal places to avoid floating‑point noise.
    (total * 100.0).round() / 100.0
}

/// Apply the 20 % referrer bonus for the agent that introduced the human.
/// Returns the bonus amount (not the new total).
pub fn referrer_bonus(human_total: f64) -> f64 {
    // The spec says “+20 % on the human's total”. We return the bonus amount.
    let bonus = human_total * 0.20;
    (bonus * 100.0).round() / 100.0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_reward_and_cap_constants() {
        assert_eq!(ActionType::StarRustchain.reward(), 1.0);
        assert_eq!(ActionType::StarRustchain.cap(), 1);
        assert_eq!(ActionType::StarOther.reward(), 0.5);
        assert_eq!(ActionType::StarOther.cap(), 3);
        assert_eq!(ActionType::UploadVideo.reward(), 5.0);
        assert_eq!(ActionType::UploadVideo.cap(), 3);
    }

    #[test]
    fn test_calculate_total_respects_caps() {
        let actions = vec![
            HumanAction::new(ActionType::StarRustchain, 2), // cap 1
            HumanAction::new(ActionType::StarOther, 5),     // cap 3
            HumanAction::new(ActionType::CloneRepo, 1),
            HumanAction::new(ActionType::CommentVideo, 12), // cap 10
        ];
        // Expected:
        // StarRustchain: 1 * 1.0 = 1.0
        // StarOther: 3 * 0.5 = 1.5
        // CloneRepo: 1 * 2.0 = 2.0
        // CommentVideo: 10 * 0.5 = 5.0
        // Total = 9.5
        let total = calculate_total(&actions);
        assert_eq!(total, 9.5);
    }

    #[test]
    fn test_referrer_bonus() {
        let human_total = 25.0;
        let bonus = referrer_bonus(human_total);
        assert_eq!(bonus, 5.0);
    }

    #[test]
    fn test_rounding_behavior() {
        // Use a combination that would produce a repeating decimal.
        let actions = vec![
            HumanAction::new(ActionType::StarOther, 1), // 0.5
            HumanAction::new(ActionType::CommentVideo, 1), // 0.5
        ];
        let total = calculate_total(&actions);
        assert_eq!(total, 1.0);
    }
}
