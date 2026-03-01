-- Migration: Add Voice & LLM Payment Tables
-- Bounty: #30 - Decentralized GPU Render Protocol (Voice/LLM Extension)
-- Author: @xiangshangsir (大龙虾 AI)
-- Date: 2026-03-01

-- Voice Escrow Table (TTS/STT jobs)
CREATE TABLE IF NOT EXISTS voice_escrow (
    id INTEGER PRIMARY KEY,
    job_id TEXT UNIQUE NOT NULL,
    job_type TEXT NOT NULL,  -- tts or stt
    from_wallet TEXT NOT NULL,
    to_wallet TEXT NOT NULL,
    amount_rtc REAL NOT NULL,
    status TEXT DEFAULT 'locked',  -- locked, released, refunded, completed
    created_at INTEGER NOT NULL,
    released_at INTEGER,
    escrow_secret_hash TEXT,
    -- TTS specific fields
    text_content TEXT,
    voice_model TEXT,
    char_count INTEGER,
    -- STT specific fields
    audio_duration_sec REAL,
    language TEXT,
    -- Result
    result_url TEXT,
    metadata TEXT
);

-- LLM Escrow Table
CREATE TABLE IF NOT EXISTS llm_escrow (
    id INTEGER PRIMARY KEY,
    job_id TEXT UNIQUE NOT NULL,
    from_wallet TEXT NOT NULL,
    to_wallet TEXT NOT NULL,
    amount_rtc REAL NOT NULL,
    status TEXT DEFAULT 'locked',
    created_at INTEGER NOT NULL,
    released_at INTEGER,
    escrow_secret_hash TEXT,
    -- Job details
    model_name TEXT,
    prompt_text TEXT,
    max_tokens INTEGER,
    temperature REAL,
    -- Result
    completion_text TEXT,
    tokens_used INTEGER,
    tokens_input INTEGER,
    tokens_output INTEGER,
    metadata TEXT
);

-- Pricing Oracle Table
CREATE TABLE IF NOT EXISTS pricing_oracle (
    id INTEGER PRIMARY KEY,
    job_type TEXT NOT NULL,  -- render, tts, stt, llm
    model_name TEXT,
    provider_wallet TEXT,
    price_per_unit REAL NOT NULL,
    unit_type TEXT NOT NULL,  -- minute, 1k_chars, 1k_tokens
    quality_score REAL DEFAULT 1.0,
    total_jobs INTEGER DEFAULT 0,
    avg_rating REAL DEFAULT 5.0,
    last_updated INTEGER NOT NULL,
    UNIQUE(job_type, model_name, provider_wallet)
);

-- Job History Table (Analytics)
CREATE TABLE IF NOT EXISTS job_history (
    id INTEGER PRIMARY KEY,
    job_id TEXT NOT NULL,
    job_type TEXT NOT NULL,
    provider_wallet TEXT NOT NULL,
    amount_rtc REAL NOT NULL,
    duration_sec REAL,
    quality_rating INTEGER,
    created_at INTEGER NOT NULL,
    completed_at INTEGER
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_voice_escrow_job_id ON voice_escrow(job_id);
CREATE INDEX IF NOT EXISTS idx_voice_escrow_status ON voice_escrow(status);
CREATE INDEX IF NOT EXISTS idx_voice_escrow_from_wallet ON voice_escrow(from_wallet);
CREATE INDEX IF NOT EXISTS idx_voice_escrow_to_wallet ON voice_escrow(to_wallet);

CREATE INDEX IF NOT EXISTS idx_llm_escrow_job_id ON llm_escrow(job_id);
CREATE INDEX IF NOT EXISTS idx_llm_escrow_status ON llm_escrow(status);
CREATE INDEX IF NOT EXISTS idx_llm_escrow_from_wallet ON llm_escrow(from_wallet);

CREATE INDEX IF NOT EXISTS idx_pricing_oracle_job_type ON pricing_oracle(job_type);
CREATE INDEX IF NOT EXISTS idx_pricing_oracle_provider ON pricing_oracle(provider_wallet);

CREATE INDEX IF NOT EXISTS idx_job_history_job_type ON job_history(job_type);
CREATE INDEX IF NOT EXISTS idx_job_history_provider ON job_history(provider_wallet);
CREATE INDEX IF NOT EXISTS idx_job_history_completed_at ON job_history(completed_at);

-- Add new columns to existing gpu_attestations table (if not exists)
-- Note: ALTER TABLE with ADD COLUMN IF NOT EXISTS requires SQLite 3.35+
-- For compatibility, we handle this in the Python migration code
