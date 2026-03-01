-- Migration: Add Alert System Tables
-- Bounty: #28 - Email/SMS Alert System for Miners
-- Author: @xiangshangsir (大龙虾 AI)
-- Date: 2026-03-01

-- Alert Preferences Table
CREATE TABLE IF NOT EXISTS alert_preferences (
    miner_id TEXT PRIMARY KEY,
    email TEXT,
    phone TEXT,
    alert_types TEXT,  -- JSON array: ["offline", "reward", ...]
    enabled INTEGER DEFAULT 1,
    created_at INTEGER NOT NULL
);

-- Alert History Table (Audit Trail)
CREATE TABLE IF NOT EXISTS alert_history (
    id INTEGER PRIMARY KEY,
    miner_id TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    message TEXT NOT NULL,
    sent_at INTEGER NOT NULL,
    channel TEXT,  -- 'email' or 'sms'
    status TEXT,  -- 'sent' or 'failed'
    error TEXT
);

-- Alert Rate Limiting Table (Prevent Spam)
CREATE TABLE IF NOT EXISTS alert_rate_limit (
    miner_id TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    last_sent INTEGER NOT NULL,
    count_24h INTEGER DEFAULT 1,
    PRIMARY KEY (miner_id, alert_type)
);

-- Indexes for Performance
CREATE INDEX IF NOT EXISTS idx_alert_history_miner ON alert_history(miner_id);
CREATE INDEX IF NOT EXISTS idx_alert_history_sent_at ON alert_history(sent_at);
CREATE INDEX IF NOT EXISTS idx_alert_history_type ON alert_history(alert_type);

CREATE INDEX IF NOT EXISTS idx_alert_rate_limit_miner ON alert_rate_limit(miner_id);

-- Sample Data (Optional)
-- Insert default preferences for existing miners
-- INSERT OR IGNORE INTO alert_preferences (miner_id, alert_types, created_at)
-- SELECT DISTINCT miner, '["offline", "reward", "large_transfer", "attestation_failure"]', strftime('%s', 'now')
-- FROM miner_attest_recent;
