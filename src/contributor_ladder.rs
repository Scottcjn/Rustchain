use chrono::{DateTime, Utc, Duration};
use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Tier {
    Explorer,
    Miner,
    Foreman,
    Architect,
    Guardian,
}

#[derive(Debug, Clone)]
pub struct Contributor {
    pub name: String,
    pub merged_prs: u32,
    pub active_since: DateTime<Utc>,
    pub prs_reviewed: u32,
    pub major_feature_or_security: bool,
    pub found_critical_vulnerability: bool,
}

impl Contributor {
    pub fn new(name: &str, merged_prs: u32, active_since: DateTime<Utc>, prs_reviewed: u32) -> Self {
        Self {
            name: name.to_string(),
            merged_prs,
            active_since,
            prs_reviewed,
            major_feature_or_security: false,
            found_critical_vulnerability: false,
        }
    }

    pub fn days_active(&self) -> i64 {
        let now = Utc::now();
        (now - self.active_since).num_days()
    }

    pub fn current_tier(&self) -> Tier {
        if self.found_critical_vulnerability {
            return Tier::Guardian;
        }
        if self.merged_prs >= 20 && self.days_active() >= 180 && self.major_feature_or_security {
            return Tier::Architect;
        }
        if self.merged_prs >= 10 && self.days_active() >= 90 && self.prs_reviewed >= 3 {
            return Tier::Foreman;
        }
        if self.merged_prs >= 3 && self.days_active() >= 30 {
            return Tier::Miner;
        }
        if self.merged_prs >= 1 {
            return Tier::Explorer;
        }
        Tier::Explorer // fallback, but should not happen if first PR is merged
    }

    pub fn tier_up_bonus(&self) -> u32 {
        match self.current_tier() {
            Tier::Explorer => 5,
            Tier::Miner => 25,
            Tier::Foreman => 100,
            Tier::Architect => 250,
            Tier::Guardian => 500,
        }
    }

    pub fn max_bounty(&self) -> u32 {
        match self.current_tier() {
            Tier::Explorer => 10,
            Tier::Miner => 50,
            Tier::Foreman => 150,
            Tier::Architect => u32::MAX,
            Tier::Guardian => u32::MAX,
        }
    }

    pub fn can_vote_on_rip(&self) -> bool {
        matches!(self.current_tier(), Tier::Foreman | Tier::Architect | Tier::Guardian)
    }

    pub fn can_author_rip(&self) -> bool {
        matches!(self.current_tier(), Tier::Architect | Tier::Guardian)
    }
}

pub fn leaderboard(contributors: &[Contributor]) -> Vec<(String, u32, DateTime<Utc>, Tier)> {
    let mut entries: Vec<_> = contributors
        .iter()
        .map(|c| (c.name.clone(), c.merged_prs, c.active_since, c.current_tier()))
        .collect();
    entries.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.2.cmp(&b.2)));
    entries
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    #[test]
    fn test_explorer_tier() {
        let contributor = Contributor::new("alice", 1, Utc.with_ymd_and_hms(2026, 1, 1, 0, 0, 0).unwrap(), 0);
        assert_eq!(contributor.current_tier(), Tier::Explorer);
        assert_eq!(contributor.tier_up_bonus(), 5);
        assert_eq!(contributor.max_bounty(), 10);
        assert!(!contributor.can_vote_on_rip());
    }

    #[test]
    fn test_miner_tier() {
        let active = Utc::now() - Duration::days(60);
        let contributor = Contributor::new("bob", 4, active, 0);
        assert_eq!(contributor.current_tier(), Tier::Miner);
        assert_eq!(contributor.tier_up_bonus(), 25);
        assert_eq!(contributor.max_bounty(), 50);
        assert!(!contributor.can_vote_on_rip());
    }

    #[test]
    fn test_foreman_tier() {
        let active = Utc::now() - Duration::days(100);
        let mut contributor = Contributor::new("carol", 12, active, 4);
        contributor.prs_reviewed = 4;
        assert_eq!(contributor.current_tier(), Tier::Foreman);
        assert_eq!(contributor.tier_up_bonus(), 100);
        assert!(contributor.can_vote_on_rip());
        assert!(!contributor.can_author_rip());
    }

    #[test]
    fn test_architect_tier() {
        let active = Utc::now() - Duration::days(200);
        let mut contributor = Contributor::new("dave", 25, active, 10);
        contributor.major_feature_or_security = true;
        assert_eq!(contributor.current_tier(), Tier::Architect);
        assert_eq!(contributor.tier_up_bonus(), 250);
        assert!(contributor.can_vote_on_rip());
        assert!(contributor.can_author_rip());
    }

    #[test]
    fn test_guardian_tier() {
        let active = Utc::now() - Duration::days(10);
        let mut contributor = Contributor::new("eve", 2, active, 1);
        contributor.found_critical_vulnerability = true;
        assert_eq!(contributor.current_tier(), Tier::Guardian);
        assert_eq!(contributor.tier_up_bonus(), 500);
        assert!(contributor.can_vote_on_rip());
        assert!(contributor.can_author_rip());
    }

    #[test]
    fn test_leaderboard_order() {
        let contributors = vec![
            Contributor::new("alice", 5, Utc.with_ymd_and_hms(2026, 2, 1, 0, 0, 0).unwrap(), 0),
            Contributor::new("bob", 10, Utc.with_ymd_and_hms(2025, 12, 1, 0, 0, 0).unwrap(), 3),
            Contributor::new("carol", 7, Utc.with_ymd_and_hms(2026, 1, 15, 0, 0, 0).unwrap(), 2),
        ];
        let lb = leaderboard(&contributors);
        assert_eq!(lb[0].0, "bob");
        assert_eq!(lb[1].0, "carol");
        assert_eq!(lb[2].0, "alice");
    }
}
