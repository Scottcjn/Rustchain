# SPDX-License-Identifier: MIT

import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, NamedTuple


class TableRequirement(NamedTuple):
    """Configuration for required table validation"""
    name: str
    min_rows: int
    row_count_check: bool = True
    custom_validation: Optional[str] = None


class BackupConfig:
    """Configuration for RustChain backup verification"""

    # Database paths
    LIVE_DB_PATH = "node/rustchain_v2.db"
    BACKUP_DIR = "backups"
    BACKUP_PATTERN = "rustchain_v2.db.bak"
    TEMP_DIR = "/tmp"

    # Backup file patterns to search for
    BACKUP_PATTERNS = [
        "rustchain_v2.db.bak",
        "rustchain_v2_*.db.bak",
        "backup_*.db",
        "rustchain_backup_*.db"
    ]

    # Table requirements
    REQUIRED_TABLES = [
        TableRequirement(
            name="balances",
            min_rows=1,
            custom_validation="SELECT COUNT(*) FROM balances WHERE amount > 0"
        ),
        TableRequirement(
            name="miner_attest_recent",
            min_rows=1,
            custom_validation="SELECT COUNT(*) FROM miner_attest_recent WHERE timestamp > datetime('now', '-24 hours')"
        ),
        TableRequirement(
            name="headers",
            min_rows=1,
            row_count_check=True
        ),
        TableRequirement(
            name="ledger",
            min_rows=1,
            row_count_check=True
        ),
        TableRequirement(
            name="epoch_rewards",
            min_rows=1,
            row_count_check=True
        )
    ]

    # Validation thresholds
    MAX_EPOCH_LAG = 1  # Maximum epochs backup can be behind
    MIN_RECENT_ATTESTATIONS = 1  # Minimum recent attestations required
    ROW_COUNT_TOLERANCE = 0.95  # Backup must have at least 95% of live DB rows

    # Alert settings
    ALERT_ON_FAILURE = True
    ALERT_EMAIL = None  # Set to email address if needed
    ALERT_WEBHOOK = None  # Set to webhook URL if needed
    LOG_FILE = "backup_verification.log"

    # Timing settings
    BACKUP_MAX_AGE_HOURS = 25  # Maximum age for backup to be considered valid
    VERIFICATION_TIMEOUT = 300  # Maximum seconds for verification

    # SQLite settings
    SQLITE_TIMEOUT = 30
    PRAGMA_CHECKS = [
        "PRAGMA integrity_check;",
        "PRAGMA foreign_key_check;",
        "PRAGMA quick_check;"
    ]

    @classmethod
    def get_backup_search_paths(cls) -> List[str]:
        """Get list of paths to search for backup files"""
        paths = []

        # Current directory backups
        for pattern in cls.BACKUP_PATTERNS:
            if "*" not in pattern:
                paths.append(pattern)

        # Backup directory
        if os.path.exists(cls.BACKUP_DIR):
            for pattern in cls.BACKUP_PATTERNS:
                if "*" not in pattern:
                    paths.append(os.path.join(cls.BACKUP_DIR, pattern))

        # Node directory backups
        node_backup_dir = "node/backups"
        if os.path.exists(node_backup_dir):
            for pattern in cls.BACKUP_PATTERNS:
                if "*" not in pattern:
                    paths.append(os.path.join(node_backup_dir, pattern))

        return paths

    @classmethod
    def is_backup_recent(cls, backup_path: str) -> bool:
        """Check if backup file is recent enough"""
        if not os.path.exists(backup_path):
            return False

        file_time = datetime.fromtimestamp(os.path.getmtime(backup_path))
        cutoff_time = datetime.now() - timedelta(hours=cls.BACKUP_MAX_AGE_HOURS)

        return file_time > cutoff_time

    @classmethod
    def get_temp_backup_path(cls, backup_filename: str) -> str:
        """Generate temporary path for backup testing"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_name = f"verify_{timestamp}_{os.path.basename(backup_filename)}"
        return os.path.join(cls.TEMP_DIR, temp_name)

    @classmethod
    def get_table_validation_query(cls, table_req: TableRequirement) -> str:
        """Get validation query for a table requirement"""
        if table_req.custom_validation:
            return table_req.custom_validation
        else:
            return f"SELECT COUNT(*) FROM {table_req.name}"

    @classmethod
    def should_alert(cls, failure_type: str) -> bool:
        """Determine if alert should be sent for failure type"""
        return cls.ALERT_ON_FAILURE
