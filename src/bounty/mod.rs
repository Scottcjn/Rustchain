//! Public re‑exports for the bounty sub‑module.

pub mod human_rewards;

pub use human_rewards::{ActionType, HumanAction, calculate_total, referrer_bonus};
