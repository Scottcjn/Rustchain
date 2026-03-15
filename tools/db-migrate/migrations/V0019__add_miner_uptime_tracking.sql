-- Migration: Add miner uptime tracking
-- Version: 19
-- Adds a table to track per-epoch miner uptime for reward weighting.

-- UP

CREATE TABLE IF NOT EXISTS miner_uptime (
    miner_pk TEXT NOT NULL,
    epoch INTEGER NOT NULL,
    heartbeat_count INTEGER DEFAULT 0,
    first_seen INTEGER NOT NULL,
    last_seen INTEGER NOT NULL,
    PRIMARY KEY (miner_pk, epoch)
);

CREATE INDEX IF NOT EXISTS idx_miner_uptime_epoch ON miner_uptime(epoch);

INSERT OR IGNORE INTO schema_version (version, applied_at)
    VALUES (19, CAST(strftime('%s', 'now') AS INTEGER));


-- DOWN

DROP TABLE IF EXISTS miner_uptime;

DELETE FROM schema_version WHERE version = 19;
