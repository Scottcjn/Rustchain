-- SPDX-License-Identifier: MIT

CREATE TABLE IF NOT EXISTS node_status_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_name TEXT NOT NULL,
    node_url TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL CHECK (status IN ('up', 'down', 'degraded')),
    response_time_ms INTEGER,
    version TEXT,
    uptime_seconds INTEGER,
    database_status TEXT,
    backup_age_hours INTEGER,
    block_height INTEGER,
    miner_count INTEGER,
    sync_status TEXT,
    error_message TEXT,
    raw_response TEXT
);

CREATE TABLE IF NOT EXISTS uptime_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_name TEXT NOT NULL,
    date TEXT NOT NULL,
    total_checks INTEGER DEFAULT 0,
    successful_checks INTEGER DEFAULT 0,
    uptime_percentage REAL DEFAULT 0.0,
    avg_response_time_ms REAL DEFAULT 0.0,
    min_response_time_ms INTEGER,
    max_response_time_ms INTEGER,
    downtime_minutes INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(node_name, date)
);

CREATE TABLE IF NOT EXISTS dashboard_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_node_status_timestamp ON node_status_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_node_status_node_name ON node_status_log(node_name);
CREATE INDEX IF NOT EXISTS idx_node_status_status ON node_status_log(status);
CREATE INDEX IF NOT EXISTS idx_uptime_summary_date ON uptime_summary(date);
CREATE INDEX IF NOT EXISTS idx_uptime_summary_node ON uptime_summary(node_name);

INSERT OR IGNORE INTO dashboard_config (key, value, description) VALUES
('check_interval_seconds', '60', 'How often to check node health'),
('retention_days', '30', 'Days to keep detailed logs'),
('summary_retention_days', '365', 'Days to keep daily summaries'),
('alert_threshold_minutes', '5', 'Minutes down before alerting'),
('response_timeout_seconds', '10', 'HTTP timeout for health checks');
