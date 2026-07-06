use serde::{Deserialize, Serialize};
use chrono::NaiveDate;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub enum Tier {
    Explorer,
    Miner,
    Foreman,
    Architect,
    Guardian,
}

impl Tier {
    pub fn bonus(&self) -> u64 {
        match self {
            Tier::Explorer => 5,
            Tier::Miner => 25,
            Tier::Foreman => 100,
            Tier::Architect => 250,
            Tier::Guardian => 500,
        }
    }

    pub fn max_bounty(&self) -> Option<u64> {
        match self {
            Tier::Explorer => Some(10),
            Tier::Miner => Some(50),
            Tier::Foreman => Some(150),
            Tier::Architect => None,
            Tier::Guardian => None,
        }
    }

    pub fn has_voting_rights(&self) -> bool {
        matches!(self, Tier::Foreman | Tier::Architect | Tier::Guardian)
    }

    pub fn can_author_rip(&self) -> bool {
        matches!(self, Tier::Architect | Tier::Guardian)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Contributor {
    pub id: String,
    pub merged_prs: u32,
    pub active_since: NaiveDate,
    pub current_tier: Tier,
    pub reviews_given: u32,
    pub major_contributions: bool,
    pub security_vuln_found: bool,
}
