mod contributor_ladder;

use contributor_ladder::*;
use chrono::Utc;

fn main() {
    // Sample contributors similar to the leaderboard in the requirements
    let contributors = vec![
        Contributor::new("createkr", 26, Utc.with_ymd_and_hms(2026, 2, 1, 0, 0, 0).unwrap(), 5),
        Contributor::new("liu971227-sys", 23, Utc.with_ymd_and_hms(2025, 12, 1, 0, 0, 0).unwrap(), 6),
        Contributor::new("David-code-tang", 20, Utc.with_ymd_and_hms(2026, 2, 15, 0, 0, 0).unwrap(), 2),
        Contributor::new("autonomy414941", 7, Utc.with_ymd_and_hms(2026, 2, 10, 0, 0, 0).unwrap(), 1),
        Contributor::new("erdogan98", 5, Utc.with_ymd_and_hms(2026, 2, 20, 0, 0, 0).unwrap(), 0),
    ];

    println!("Current Leaderboard:");
    println!("{:<20} {:<12} {:<15} {:<10}", "Contributor", "Merged PRs", "Active Since", "Current Tier");
    for (name, prs, active, tier) in leaderboard(&contributors) {
        println!("{:<20} {:<12} {:<15} {:<10?}", name, prs, active.format("%b %Y").to_string(), tier);
    }

    // Example: get tier for a specific contributor
    let contributor = Contributor::new("newbie", 1, Utc::now(), 0);
    println!("\nNew contributor tier: {:?}", contributor.current_tier());
}
