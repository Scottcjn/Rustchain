use crate::models::{Contributor, Tier};
use chrono::NaiveDate;

pub fn determine_tier(c: &Contributor) -> Tier {
    // Guardian: found and reported critical security vulnerability
    if c.security_vuln_found {
        return Tier::Guardian;
    }
    // Architect: 6+ months sustained, major feature or security contribution
    let months_active = months_between(c.active_since, chrono::Local::now().date_naive());
    if months_active >= 6 && c.major_contributions {
        return Tier::Architect;
    }
    // Foreman: 10+ merged PRs, 90+ days, reviewed 3+ others' PRs
    if c.merged_prs >= 10 && months_active >= 3 && c.reviews_given >= 3 {
        return Tier::Foreman;
    }
    // Miner: 3+ merged PRs over 30+ days
    if c.merged_prs >= 3 && months_active >= 1 {
        return Tier::Miner;
    }
    // Explorer: default (first merged PR or detailed bug report)
    Tier::Explorer
}

fn months_between(start: NaiveDate, end: NaiveDate) -> u32 {
    ((end.year() - start.year()) * 12 + end.month() as i32 - start.month() as i32) as u32
}
