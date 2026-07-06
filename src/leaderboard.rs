use crate::models::Contributor;
use serde::Serialize;

#[derive(Debug, Serialize)]
pub struct LeaderboardEntry {
    pub id: String,
    pub merged_prs: u32,
    pub active_since: String,
    pub current_tier: String,
}

pub fn build_leaderboard(contributors: &[Contributor]) -> Vec<LeaderboardEntry> {
    let mut entries: Vec<LeaderboardEntry> = contributors
        .iter()
        .map(|c| LeaderboardEntry {
            id: c.id.clone(),
            merged_prs: c.merged_prs,
            active_since: c.active_since.to_string(),
            current_tier: format!("{:?}", c.current_tier),
        })
        .collect();
    entries.sort_by(|a, b| b.merged_prs.cmp(&a.merged_prs));
    entries
}
