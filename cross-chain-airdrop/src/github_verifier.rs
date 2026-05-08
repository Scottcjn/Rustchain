//! GitHub verification for airdrop eligibility

use crate::error::{AirdropError, Result};
use crate::models::{GitHubProfile, GitHubTier, GitHubVerification};
use chrono::{DateTime, Utc};
use reqwest::Client;
use serde::Deserialize;

/// GitHub API client for verification
pub struct GitHubVerifier {
    client: Client,
    api_base: String,
    token: Option<String>,
    min_account_age_days: u64,
}

impl GitHubVerifier {
    pub fn new(api_base: String, token: Option<String>, min_account_age_days: u64) -> Self {
        Self {
            client: Client::new(),
            api_base,
            token,
            min_account_age_days,
        }
    }

    pub fn with_defaults(token: Option<String>) -> Self {
        Self {
            client: Client::new(),
            api_base: "https://api.github.com".to_string(),
            token,
            min_account_age_days: 30,
        }
    }

    /// Verify GitHub account and determine eligibility tier
    pub async fn verify(&self, oauth_token: &str) -> Result<GitHubVerification> {
        // Get user profile
        let profile = self.get_user_profile(oauth_token).await?;

        // Check account age
        let account_age_days = profile
            .created_at
            .signed_duration_since(Utc::now())
            .num_days()
            .abs() as u64;
        if account_age_days < self.min_account_age_days {
            return Err(AirdropError::GitHubVerification(format!(
                "GitHub account too young: {} days (minimum {})",
                account_age_days, self.min_account_age_days
            )));
        }

        // Get starred repos count (repos user has starred)
        let starred_count = self.get_starred_repos_count(oauth_token).await?;

        // Get merged PRs count
        let merged_prs = self.get_merged_prs_count(&profile.login).await?;

        // Check for Star King badge (users who starred early RustChain repos)
        let has_star_king_badge = self.check_star_king_badge(&profile.login).await?;

        // Check if user is a miner (has attestation history)
        let is_miner = self.check_miner_status(&profile.login).await?;

        // Determine tier based on contributions
        let tier = self.determine_tier(starred_count, merged_prs, has_star_king_badge, is_miner)?;

        Ok(GitHubVerification {
            profile,
            tier,
            starred_repos_count: starred_count,
            merged_prs_count: merged_prs,
            has_star_king_badge,
            is_miner,
            account_age_days,
        })
    }

    /// Get user profile from GitHub API
    async fn get_user_profile(&self, token: &str) -> Result<GitHubProfile> {
        let mut request = self
            .client
            .get(format!("{}/user", self.api_base))
            .header("Accept", "application/vnd.github.v3+json")
            .header("User-Agent", "RustChain-Airdrop");

        if let Some(ref app_token) = self.token {
            request = request.bearer_auth(app_token);
        } else {
            request = request.bearer_auth(token);
        }

        let response = request
            .send()
            .await
            .map_err(|e| AirdropError::GitHub(format!("Failed to fetch user profile: {}", e)))?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(AirdropError::GitHub(format!(
                "GitHub API error ({}): {}",
                status, body
            )));
        }

        let profile: GitHubProfileResponse = response
            .json()
            .await
            .map_err(|e| AirdropError::GitHub(format!("Failed to parse user profile: {}", e)))?;

        // Parse created_at timestamp
        let created_at = DateTime::parse_from_rfc3339(&profile.created_at)
            .map_err(|e| AirdropError::GitHub(format!("Invalid created_at format: {}", e)))?
            .with_timezone(&Utc);

        Ok(GitHubProfile {
            login: profile.login,
            id: profile.id,
            created_at,
            public_repos: profile.public_repos,
            followers: profile.followers,
        })
    }

    /// Get count of repos starred by user
    async fn get_starred_repos_count(&self, token: &str) -> Result<u64> {
        let mut request = self
            .client
            .get(format!("{}/user/starred", self.api_base))
            .header("Accept", "application/vnd.github.v3+json")
            .header("User-Agent", "RustChain-Airdrop");

        if let Some(ref app_token) = self.token {
            request = request.bearer_auth(app_token);
        } else {
            request = request.bearer_auth(token);
        }

        // Request only 1 item per page to get total count efficiently
        request = request.query(&[("per_page", "1")]);

        let response = request
            .send()
            .await
            .map_err(|e| AirdropError::GitHub(format!("Failed to fetch starred repos: {}", e)))?;

        if !response.status().is_success() {
            return Err(AirdropError::GitHub(format!(
                "GitHub API error: {}",
                response.status()
            )));
        }

        // Get total count from Link header or count items
        if let Some(link_header) = response.headers().get("Link") {
            if let Ok(link_str) = link_header.to_str() {
                // Parse Link header for last page number
                if let Some(count) = self.parse_link_header_last_page(link_str) {
                    return Ok(count);
                }
            }
        }

        // Fallback: return 0 if we can't determine count
        Ok(0)
    }

    /// Get count of merged PRs by user
    async fn get_merged_prs_count(&self, login: &str) -> Result<u64> {
        // Search for merged PRs by the user in Scottcjn/Rustchain repo
        let query = format!("repo:Scottcjn/Rustchain type:pr author:{} is:merged", login);
        let per_page = "1".to_string();

        let request = self
            .client
            .get(format!("{}/search/issues", self.api_base))
            .header("Accept", "application/vnd.github.v3+json")
            .header("User-Agent", "RustChain-Airdrop")
            .query(&[("q", &query), ("per_page", &per_page)]);

        let response = request
            .send()
            .await
            .map_err(|e| AirdropError::GitHub(format!("Failed to fetch merged PRs: {}", e)))?;

        if !response.status().is_success() {
            return Err(AirdropError::GitHub(format!(
                "GitHub API error: {}",
                response.status()
            )));
        }

        let result: SearchResponse = response
            .json()
            .await
            .map_err(|e| AirdropError::GitHub(format!("Failed to parse search results: {}", e)))?;

        Ok(result.total_count)
    }

    /// Check if user has Star King badge (early starrer)
    async fn check_star_king_badge(&self, _login: &str) -> Result<bool> {
        // In production, check against list of early stargazers
        // For now, return false - would need to be implemented with stargazers API
        Ok(false)
    }

    /// Check if user is an active miner
    async fn check_miner_status(&self, _login: &str) -> Result<bool> {
        // In production, check RustChain node for attestation history
        // This would query the node's /miners endpoint
        Ok(false)
    }

    /// Determine GitHub tier based on contributions
    fn determine_tier(
        &self,
        starred_count: u64,
        merged_prs: u64,
        has_star_king: bool,
        is_miner: bool,
    ) -> Result<GitHubTier> {
        // Core: 5+ PRs or Star King badge
        if merged_prs >= 5 || has_star_king {
            return Ok(GitHubTier::Core);
        }

        // Security: Would need external verification
        // Skipping for now as this requires manual verification

        // Builder: 3+ PRs
        if merged_prs >= 3 {
            return Ok(GitHubTier::Builder);
        }

        // Miner: Active attestation
        if is_miner {
            return Ok(GitHubTier::Miner);
        }

        // Contributor: 1+ PRs
        if merged_prs >= 1 {
            return Ok(GitHubTier::Contributor);
        }

        // Stargazer: 10+ repos starred
        if starred_count >= 10 {
            return Ok(GitHubTier::Stargazer);
        }

        Err(AirdropError::GitHubVerification(
            "Does not meet minimum GitHub contribution requirements".to_string(),
        ))
    }

    /// Parse Link header to get last page number
    fn parse_link_header_last_page(&self, link_header: &str) -> Option<u64> {
        // Link header format: <url>; rel="first", <url>; rel="prev", <url>; rel="next", <url>; rel="last"
        for part in link_header.split(',') {
            if part.contains("rel=\"last\"") {
                if let Some(start) = part.find("page=") {
                    let start = start + 5;
                    let end = part[start..].find('>').unwrap_or(part.len() - start);
                    return part[start..start + end].parse().ok();
                }
            }
        }
        None
    }
}

/// GitHub user profile response
#[derive(Debug, Deserialize)]
struct GitHubProfileResponse {
    login: String,
    id: u64,
    created_at: String,
    public_repos: u64,
    followers: u64,
}

/// GitHub search response
#[derive(Debug, Deserialize)]
struct SearchResponse {
    total_count: u64,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_determine_tier_core_by_prs() {
        let verifier = GitHubVerifier::with_defaults(None);
        let tier = verifier.determine_tier(5, 5, false, false).unwrap();
        assert_eq!(tier, GitHubTier::Core);
    }

    #[test]
    fn test_determine_tier_builder() {
        let verifier = GitHubVerifier::with_defaults(None);
        let tier = verifier.determine_tier(5, 3, false, false).unwrap();
        assert_eq!(tier, GitHubTier::Builder);
    }

    #[test]
    fn test_determine_tier_contributor() {
        let verifier = GitHubVerifier::with_defaults(None);
        let tier = verifier.determine_tier(5, 1, false, false).unwrap();
        assert_eq!(tier, GitHubTier::Contributor);
    }

    #[test]
    fn test_determine_tier_stargazer() {
        let verifier = GitHubVerifier::with_defaults(None);
        let tier = verifier.determine_tier(15, 0, false, false).unwrap();
        assert_eq!(tier, GitHubTier::Stargazer);
    }

    #[test]
    fn test_determine_tier_ineligible() {
        let verifier = GitHubVerifier::with_defaults(None);
        let result = verifier.determine_tier(5, 0, false, false);
        assert!(result.is_err());
    }

    #[test]
    fn test_parse_link_header() {
        let verifier = GitHubVerifier::with_defaults(None);
        let link_header = r#"<https://api.github.com/user/starred?page=1>; rel="first", <https://api.github.com/user/starred?page=5>; rel="last""#;
        let last_page = verifier.parse_link_header_last_page(link_header);
        assert_eq!(last_page, Some(5));
    }
}
