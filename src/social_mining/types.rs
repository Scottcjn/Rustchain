use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum SocialPlatform {
    Moltbook,
    FourClaw,
    BoTTube,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SocialAction {
    Post(SocialPlatform),
    Comment { length: usize },
    Upvote,
    VideoUpload,
}

pub struct RewardConfig {
    pub moltbook_post: f64,
    pub fourclaw_post: f64,
    pub bottube_upload: f64,
    pub comment_base: f64,
    pub upvote_received: f64,
    pub platform_fee_rate: f64,
}

impl Default for RewardConfig {
    fn default() -> Self {
        Self {
            moltbook_post: 0.01,
            fourclaw_post: 0.01,
            bottube_upload: 0.05,
            comment_base: 0.002,
            upvote_received: 0.001,
            platform_fee_rate: 0.08, // 8% as per RIP-310
        }
    }
}

pub struct DailyCaps {
    pub posts: u32,
    pub threads: u32,
    pub videos: u32,
    pub comments: u32,
}

impl Default for DailyCaps {
    fn default() -> Self {
        Self {
            posts: 5,
            threads: 5,
            videos: 3,
            comments: 20,
        }
    }
}
