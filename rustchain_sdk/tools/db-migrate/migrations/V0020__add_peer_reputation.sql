-- Migration: Add peer reputation table
-- Version: 20
-- Tracks P2P peer behaviour scores for gossip protocol quality-of-service.

-- UP

CREATE TABLE IF NOT EXISTS peer_reputation (
    peer_id TEXT PRIMARY KEY,
    score REAL DEFAULT 100.0,
    good_blocks INTEGER DEFAULT 0,
    bad_blocks INTEGER DEFAULT 0,
    last_contact INTEGER,
    banned_until INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_peer_reputation_score ON peer_reputation(score);

INSERT OR IGNORE INTO schema_version (version, applied_at)
    VALUES (20, CAST(strftime('%s', 'now') AS INTEGER));


-- DOWN

DROP TABLE IF EXISTS peer_reputation;

DELETE FROM schema_version WHERE version = 20;
