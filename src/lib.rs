use chrono::{DateTime, Utc, Duration};
use serde::{Serialize, Deserialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub enum Tier {
    Explorer,
    Miner,
    Foreman,
    Architect,
    Guardian,
}

impl Tier {
    pub fn max_bounty(&self) -> u64 {
        match self {
            Tier::Explorer => 10,
            Tier::Miner => 50,
            Tier::Foreman => 150,
            Tier::Architect => u64::MAX,
            Tier::Guardian => u64::MAX,
        }
    }

    pub fn bonus_rtc(&self) -> u64 {
        match self {
            Tier::Explorer => 5,
            Tier::Miner => 25,
            Tier::Foreman => 100,
            Tier::Architect => 250,
            Tier::Guardian => 500,
        }
    }

    pub fn can_vote(&self) -> bool {
        matches!(self, Tier::Foreman | Tier::Architect | Tier::Guardian)
    }

    pub fn can_author(&self) -> bool {
        matches!(self, Tier::Architect | Tier::Guardian)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Contributor {
    pub username: String,
    pub merged_prs: u32,
    pub active_since: DateTime<Utc>,
    pub reviews_given: u32,
    pub major_security_contribution: bool,
    pub current_tier: Tier,
    pub total_bonus_received: u64,
}

impl Contributor {
    pub fn new(username: &str) -> Self {
        Self {
            username: username.to_string(),
            merged_prs: 0,
            active_since: Utc::now(),
            reviews_given: 0,
            major_security_contribution: false,
            current_tier: Tier::Explorer,
            total_bonus_received: 0,
        }
    }

    /// Calculate the tier based on current stats (excluding guardian which is manual).
    pub fn calculate_tier(&self) -> Tier {
        if self.major_security_contribution {
            return Tier::Guardian;
        }

        let days_active = (Utc::now() - self.active_since).num_days();

        if self.merged_prs >= 10 && days_active >= 90 && self.reviews_given >= 3 {
            Tier::Foreman
        } else if self.merged_prs >= 3 && days_active >= 30 {
            Tier::Miner
        } else if self.merged_prs >= 1 {
            Tier::Explorer
        } else {
            Tier::Explorer
        }
    }

    /// Determine if the contributor qualifies for Architect (manual check based on PR count and days).
    pub fn qualifies_for_architect(&self) -> bool {
        let days_active = (Utc::now() - self.active_since).num_days();
        self.merged_prs >= 15 && days_active >= 180 && self.reviews_given >= 5
    }

    /// Attempt to promote to a higher tier. Returns the bonus amount if promoted, 0 otherwise.
    pub fn promote(&mut self) -> u64 {
        let new_tier = self.calculate_tier();
        if new_tier > self.current_tier || (self.current_tier == Tier::Explorer && new_tier == Tier::Explorer) {
            // For explorer, always give welcome bonus on first PR?
            if self.current_tier == Tier::Explorer && self.merged_prs >= 1 && self.total_bonus_received == 0 {
                let bonus = Tier::Explorer.bonus_rtc();
                self.total_bonus_received += bonus;
                self.current_tier = Tier::Explorer; // stay explorer but give bonus
                return bonus;
            }
            if new_tier != self.current_tier {
                let bonus = new_tier.bonus_rtc();
                self.total_bonus_received += bonus;
                self.current_tier = new_tier;
                return bonus;
            }
        }
        0
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Leaderboard {
    pub entries: Vec<Contributor>,
}

impl Leaderboard {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn update_leaderboard(&mut self, contributors: &[Contributor]) {
        self.entries = contributors.to_vec();
        self.entries.sort_by(|a, b| b.merged_prs.cmp(&a.merged_prs));
    }

    pub fn display(&self) -> Vec<&Contributor> {
        self.entries.iter().take(10).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    #[test]
    fn test_explorer_bonus() {
        let mut c = Contributor::new("testuser");
        c.merged_prs = 1;
        let bonus = c.promote();
        assert_eq!(bonus, 5);
        assert_eq!(c.current_tier, Tier::Explorer);
    }

    #[test]
    fn test_miner_promotion() {
        let mut c = Contributor::new("testuser");
        c.merged_prs = 4;
        c.active_since = Utc::now() - Duration::days(31);
        let bonus = c.promote();
        assert_eq!(bonus, 25);
        assert_eq!(c.current_tier, Tier::Miner);
    }

    #[test]
    fn test_foreman_promotion() {
        let mut c = Contributor::new("testuser");
        c.merged_prs = 10;
        c.active_since = Utc::now() - Duration::days(91);
        c.reviews_given = 3;
        let bonus = c.promote();
        assert_eq!(bonus, 100);
        assert_eq!(c.current_tier, Tier::Foreman);
    }

    #[test]
    fn test_guardian() {
        let mut c = Contributor::new("testuser");
        c.major_security_contribution = true;
        assert_eq!(c.calculate_tier(), Tier::Guardian);
        let bonus = c.promote();
        assert_eq!(bonus, 500);
        assert_eq!(c.current_tier, Tier::Guardian);
    }

    #[test]
    fn test_max_bounty() {
        assert_eq!(Tier::Explorer.max_bounty(), 10);
        assert_eq!(Tier::Miner.max_bounty(), 50);
        assert_eq!(Tier::Foreman.max_bounty(), 150);
        assert_eq!(Tier::Architect.max_bounty(), u64::MAX);
        assert_eq!(Tier::Guardian.max_bounty(), u64::MAX);
    }

    #[test]
    fn test_governance_rights() {
        assert!(!Tier::Explorer.can_vote());
        assert!(!Tier::Miner.can_vote());
        assert!(Tier::Foreman.can_vote());
        assert!(Tier::Architect.can_vote());
        assert!(Tier::Guardian.can_vote());
        assert!(!Tier::Explorer.can_author());
        assert!(!Tier::Miner.can_author());
        assert!(!Tier::Foreman.can_author());
        assert!(Tier::Architect.can_author());
        assert!(Tier::Guardian.can_author());
    }

    #[test]
    fn test_leaderboard_integration() {
        let mut lb = Leaderboard::new();
        let c1 = Contributor::new("alice");
        let c2 = Contributor::new("bob");
        let mut c3 = Contributor::new("charlie");
        c3.merged_prs = 5;
        lb.update_leaderboard(&[c1, c2, c3]);
        let top = lb.display();
        assert_eq!(top.len(), 3);
        assert_eq!(top[0].username, "charlie");
    }
}