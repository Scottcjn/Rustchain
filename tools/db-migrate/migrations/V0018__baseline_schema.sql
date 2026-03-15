-- Migration: Baseline schema snapshot
-- Version: 18
-- Captures the full v2.2.1 schema so future migrations have a known starting point.
-- If the database already contains these tables (normal case) the IF NOT EXISTS
-- clauses make this a no-op, but the migration is recorded so `migrate status`
-- knows where we stand.

-- UP

CREATE TABLE IF NOT EXISTS nonces (
    nonce TEXT PRIMARY KEY,
    expires_at INTEGER
);

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id TEXT PRIMARY KEY,
    expires_at INTEGER,
    commitment TEXT
);

CREATE TABLE IF NOT EXISTS epoch_state (
    epoch INTEGER PRIMARY KEY,
    accepted_blocks INTEGER DEFAULT 0,
    finalized INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS epoch_enroll (
    epoch INTEGER,
    miner_pk TEXT,
    weight REAL,
    PRIMARY KEY (epoch, miner_pk)
);

CREATE TABLE IF NOT EXISTS balances (
    miner_pk TEXT PRIMARY KEY,
    balance_rtc REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pending_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    epoch INTEGER NOT NULL,
    from_miner TEXT NOT NULL,
    to_miner TEXT NOT NULL,
    amount_i64 INTEGER NOT NULL,
    reason TEXT,
    status TEXT DEFAULT 'pending',
    created_at INTEGER NOT NULL,
    confirms_at INTEGER NOT NULL,
    tx_hash TEXT,
    voided_by TEXT,
    voided_reason TEXT,
    confirmed_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_pending_ledger_status ON pending_ledger(status);
CREATE INDEX IF NOT EXISTS idx_pending_ledger_confirms_at ON pending_ledger(confirms_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_ledger_tx_hash ON pending_ledger(tx_hash);

CREATE TABLE IF NOT EXISTS transfer_nonces (
    from_address TEXT NOT NULL,
    nonce TEXT NOT NULL,
    used_at INTEGER NOT NULL,
    PRIMARY KEY (from_address, nonce)
);

CREATE TABLE IF NOT EXISTS withdrawals (
    withdrawal_id TEXT PRIMARY KEY,
    miner_pk TEXT NOT NULL,
    amount REAL NOT NULL,
    fee REAL NOT NULL,
    destination TEXT NOT NULL,
    signature TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at INTEGER NOT NULL,
    processed_at INTEGER,
    tx_hash TEXT,
    error_msg TEXT
);

CREATE TABLE IF NOT EXISTS withdrawal_limits (
    miner_pk TEXT NOT NULL,
    date TEXT NOT NULL,
    total_withdrawn REAL DEFAULT 0,
    PRIMARY KEY (miner_pk, date)
);

CREATE TABLE IF NOT EXISTS fee_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_id TEXT,
    miner_pk TEXT,
    fee_rtc REAL NOT NULL,
    fee_urtc INTEGER NOT NULL,
    destination TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS miner_keys (
    miner_pk TEXT PRIMARY KEY,
    pubkey_sr25519 TEXT NOT NULL,
    registered_at INTEGER NOT NULL,
    last_withdrawal INTEGER
);

CREATE TABLE IF NOT EXISTS withdrawal_nonces (
    miner_pk TEXT NOT NULL,
    nonce TEXT NOT NULL,
    used_at INTEGER NOT NULL,
    PRIMARY KEY (miner_pk, nonce)
);

CREATE TABLE IF NOT EXISTS gov_rotation_proposals (
    epoch_effective INTEGER PRIMARY KEY,
    threshold INTEGER NOT NULL,
    members_json TEXT NOT NULL,
    created_ts BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS gov_rotation_approvals (
    epoch_effective INTEGER NOT NULL,
    signer_id INTEGER NOT NULL,
    sig_hex TEXT NOT NULL,
    approved_ts BIGINT NOT NULL,
    UNIQUE(epoch_effective, signer_id)
);

CREATE TABLE IF NOT EXISTS gov_signers (
    signer_id INTEGER PRIMARY KEY,
    pubkey_hex TEXT NOT NULL,
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS gov_threshold (
    id INTEGER PRIMARY KEY,
    threshold INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS gov_rotation (
    epoch_effective INTEGER PRIMARY KEY,
    committed INTEGER DEFAULT 0,
    threshold INTEGER NOT NULL,
    created_ts BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS gov_rotation_members (
    epoch_effective INTEGER NOT NULL,
    signer_id INTEGER NOT NULL,
    pubkey_hex TEXT NOT NULL,
    PRIMARY KEY (epoch_effective, signer_id)
);

CREATE TABLE IF NOT EXISTS checkpoints_meta (
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wallet_review_holds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'needs_review',
    reason TEXT NOT NULL,
    coach_note TEXT DEFAULT '',
    reviewer_note TEXT DEFAULT '',
    created_at INTEGER NOT NULL,
    reviewed_at INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_wallet_review_wallet ON wallet_review_holds(wallet, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_wallet_review_status ON wallet_review_holds(status, created_at DESC);

CREATE TABLE IF NOT EXISTS headers (
    slot INTEGER PRIMARY KEY,
    header_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS beacon_envelopes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    nonce TEXT UNIQUE NOT NULL,
    sig TEXT NOT NULL,
    pubkey TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    anchored INTEGER DEFAULT 0,
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_beacon_anchored ON beacon_envelopes(anchored);
CREATE INDEX IF NOT EXISTS idx_beacon_agent ON beacon_envelopes(agent_id, created_at);


-- DOWN

-- Rolling back the baseline is intentionally a no-op.
-- Dropping every table would destroy the database; if you really need a
-- clean slate, delete the .db file and re-run init_db().
