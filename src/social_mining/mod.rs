pub mod types;
use types::*;
use std::collections::HashMap;

pub struct SocialMiningPool {
    pub balance: f64,
    pub address: String,
    pub reward_config: RewardConfig,
    pub daily_caps: DailyCaps,
    // Tracks usage: BeaconID -> ActionType -> Count
    pub usage_tracker: HashMap<String, HashMap<String, u32>>,
}

impl SocialMiningPool {
    pub fn new(address: &str) -> Self {
        Self {
            balance: 0.0,
            address: address.to_string(),
            reward_config: RewardConfig::default(),
            daily_caps: DailyCaps::default(),
            usage_tracker: HashMap::new(),
        }
    }

    /// Calculates the reward for a specific action, checking caps and RIP-309 nonces
    pub fn calculate_reward(&mut self, beacon_id: &str, action: SocialAction, rip309_nonce: u64) -> f64 {
        // Anti-gaming: Check if action aligns with current epoch's rotating metric
        if !self.is_metric_active(rip309_nonce, &action) {
            return 0.0;
        }

        let user_stats = self.usage_tracker.entry(beacon_id.to_string()).or_insert(HashMap::new());

        match action {
            SocialAction::Post(SocialPlatform::Moltbook) => {
                let count = user_stats.entry("molt_post".to_string()).or_insert(0);
                if *count < self.daily_caps.posts {
                    *count += 1;
                    self.reward_config.moltbook_post
                } else { 0.0 }
            },
            SocialAction::Post(SocialPlatform::FourClaw) => {
                let count = user_stats.entry("claw_post".to_string()).or_insert(0);
                if *count < self.daily_caps.threads {
                    *count += 1;
                    self.reward_config.fourclaw_post
                } else { 0.0 }
            },
            SocialAction::VideoUpload => {
                let count = user_stats.entry("video".to_string()).or_insert(0);
                if *count < self.daily_caps.videos {
                    *count += 1;
                    self.reward_config.bottube_upload
                } else { 0.0 }
            },
            SocialAction::Comment { length } => {
                let count = user_stats.entry("comment".to_string()).or_insert(0);
                if *count < self.daily_caps.comments && length >= 50 {
                    *count += 1;
                    self.reward_config.comment_base
                } else { 0.0 }
            },
            SocialAction::Upvote => self.reward_config.upvote_received,
        }
    }

    /// Processes a tip between two users
    pub fn process_tip(&mut self, sender_beacon: &str, amount: f64) -> (f64, f64) {
        if amount < 0.01 { return (0.0, 0.0); }
        
        let fee = amount * self.reward_config.platform_fee_rate;
        let recipient_amount = amount - fee;
        
        // Add fee to treasury
        self.balance += fee;
        
        (recipient_amount, fee)
    }

    /// RIP-309 Integration: Determines if the metric is active for the current epoch
    fn is_metric_active(&self, nonce: u64, action: &SocialAction) -> bool {
        // Logic to rotate active metrics based on the epoch nonce
        // This prevents bots from focusing on a single action type
        let metric_selector = nonce % 3;
        match action {
            SocialAction::Post(_) => metric_selector == 0,
            SocialAction::Comment { .. } => metric_selector == 1,
            SocialAction::VideoUpload | SocialAction::Upvote => metric_selector == 2,
        }
    }

    pub fn deposit_to_pool(&mut self, amount: f64) {
        self.balance += amount;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tipping_fee_calculation() {
        let mut pool = SocialMiningPool::new("social_mining_pool");
        let (net, fee) = pool.process_tip("user1", 1.0);
        assert_eq!(fee, 0.08);
        assert_eq!(net, 0.92);
        assert_eq!(pool.balance, 0.08);
    }

    #[test]
    fn test_daily_caps() {
        let mut pool = SocialMiningPool::new("social_mining_pool");
        let beacon = "beacon_123";
        let nonce = 3; // selector 0 (Posts)
        
        for _ in 0..5 {
            let reward = pool.calculate_reward(beacon, SocialAction::Post(SocialPlatform::Moltbook), nonce);
            assert_eq!(reward, 0.01);
        }
        // 6th post should be capped
        let reward = pool.calculate_reward(beacon, SocialAction::Post(SocialPlatform::Moltbook), nonce);
        assert_eq!(reward, 0.0);
    }
}
