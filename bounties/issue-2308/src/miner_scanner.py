#!/usr/bin/env python3
"""
Miner Scanner — Detect inactive miners for Silicon Obituary.

Scans the RustChain database for miners that haven't attested
within the configured threshold (default: 7 days).
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger("silicon_obituary.scanner")


@dataclass
class MinerStatus:
    """Status of a miner for obituary consideration."""
    miner_id: str
    last_attestation: datetime
    days_inactive: int
    total_epochs: int
    total_rtc_earned: float
    device_model: str
    device_arch: str
    first_attestation: datetime
    multiplier_history: List[float]


class MinerScanner:
    """
    Scans RustChain database for inactive miners.
    
    Queries the miner_attest_recent and related tables to find
    miners that haven't submitted attestations within the threshold.
    """
    
    def __init__(self, db_path: str, inactive_days: int = 7):
        self.db_path = db_path
        self.inactive_days = inactive_days
        self.threshold_seconds = inactive_days * 24 * 60 * 60
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def find_inactive_miners(self) -> List[MinerStatus]:
        """
        Find all miners inactive for 7+ days.
        
        Returns list of MinerStatus objects with complete miner data.
        """
        if not Path(self.db_path).exists():
            logger.warning(f"Database not found: {self.db_path}")
            return []
        
        cutoff_ts = datetime.now().timestamp() - self.threshold_seconds
        
        try:
            with self._get_connection() as conn:
                # Check if tables exist
                tables = self._get_table_names(conn)
                
                if 'miner_attest_recent' not in tables:
                    logger.warning("miner_attest_recent table not found")
                    return []
                
                # Find miners with old attestations
                query = """
                    SELECT 
                        miner,
                        ts_ok as last_attest_ts,
                        device_family,
                        device_arch,
                        COALESCE(entropy_score, 0) as entropy_score,
                        COALESCE(fingerprint_passed, 0) as fingerprint_passed,
                        COALESCE(source_ip, '') as source_ip,
                        COALESCE(warthog_bonus, 1.0) as warthog_bonus
                    FROM miner_attest_recent
                    WHERE ts_ok < ?
                    ORDER BY ts_ok ASC
                """
                
                cursor = conn.execute(query, (cutoff_ts,))
                inactive_miners = []
                
                for row in cursor.fetchall():
                    miner_data = self._get_complete_miner_data(conn, row['miner'])
                    if miner_data:
                        inactive_miners.append(miner_data)
                
                return inactive_miners
                
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return []
    
    def _get_table_names(self, conn: sqlite3.Connection) -> List[str]:
        """Get list of table names in database."""
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        return [row[0] for row in cursor.fetchall()]
    
    def _get_complete_miner_data(
        self, 
        conn: sqlite3.Connection, 
        miner_id: str
    ) -> Optional[MinerStatus]:
        """
        Retrieve complete miner data from multiple tables.
        
        Gathers:
        - Attestation history
        - Total RTC earned
        - Device architecture
        - Multiplier history
        """
        try:
            # Get recent attestation data
            cursor = conn.execute(
                "SELECT * FROM miner_attest_recent WHERE miner = ?",
                (miner_id,)
            )
            attest_row = cursor.fetchone()
            
            if not attest_row:
                return None
            
            # Calculate days inactive
            last_attest_ts = attest_row['ts_ok']
            last_attest_dt = datetime.fromtimestamp(last_attest_ts)
            days_inactive = int((datetime.now() - last_attest_dt).days)
            
            # Get total epochs from epoch_enroll
            cursor = conn.execute(
                "SELECT COUNT(DISTINCT epoch) as total_epochs FROM epoch_enroll WHERE miner_pk = ?",
                (miner_id,)
            )
            epoch_row = cursor.fetchone()
            total_epochs = epoch_row['total_epochs'] if epoch_row else 0
            
            # Get total RTC earned from balances
            cursor = conn.execute(
                "SELECT balance_rtc FROM balances WHERE miner_pk = ?",
                (miner_id,)
            )
            balance_row = cursor.fetchone()
            total_rtc = balance_row['balance_rtc'] if balance_row else 0.0
            
            # Get first attestation (earliest in history if available)
            first_attest = self._get_first_attestation(conn, miner_id)
            if not first_attest:
                first_attest = last_attest_dt  # Fallback
            
            # Get multiplier history from fee_events or calculate from epochs
            multiplier_history = self._get_multiplier_history(
                conn, 
                miner_id, 
                attest_row['warthog_bonus'] if attest_row['warthog_bonus'] else 1.0
            )
            
            # Device info
            device_model = attest_row['device_family'] if attest_row['device_family'] else 'Unknown'
            device_arch = attest_row['device_arch'] if attest_row['device_arch'] else 'Unknown'
            
            return MinerStatus(
                miner_id=miner_id,
                last_attestation=last_attest_dt,
                days_inactive=days_inactive,
                total_epochs=total_epochs,
                total_rtc_earned=total_rtc,
                device_model=device_model,
                device_arch=device_arch,
                first_attestation=first_attest,
                multiplier_history=multiplier_history
            )
            
        except sqlite3.Error as e:
            logger.error(f"Error getting miner data for {miner_id}: {e}")
            return None
    
    def _get_first_attestation(
        self, 
        conn: sqlite3.Connection, 
        miner_id: str
    ) -> Optional[datetime]:
        """Get the first attestation timestamp for a miner."""
        # Try miner_attest_history if it exists
        tables = self._get_table_names(conn)
        
        if 'miner_attest_history' in tables:
            cursor = conn.execute(
                """
                SELECT MIN(ts) as first_ts 
                FROM miner_attest_history 
                WHERE miner = ?
                """,
                (miner_id,)
            )
            row = cursor.fetchone()
            if row and row['first_ts']:
                return datetime.fromtimestamp(row['first_ts'])
        
        # Fallback to recent table
        cursor = conn.execute(
            "SELECT ts_ok FROM miner_attest_recent WHERE miner = ?",
            (miner_id,)
        )
        row = cursor.fetchone()
        if row and row['ts_ok']:
            return datetime.fromtimestamp(row['ts_ok'])
        
        return None
    
    def _get_multiplier_history(
        self,
        conn: sqlite3.Connection,
        miner_id: str,
        current_multiplier: float
    ) -> List[float]:
        """
        Get multiplier history for a miner.
        
        This can be derived from:
        - fee_events (if multiplier was recorded)
        - epoch_enroll weights
        - Or just return current multiplier
        """
        # For now, return a history with just the current multiplier
        # In production, this would query historical data
        history = [current_multiplier]
        
        # Try to get historical multipliers from fee_events
        tables = self._get_table_names(conn)
        if 'fee_events' in tables:
            cursor = conn.execute(
                """
                SELECT DISTINCT fee_rtc / 10.0 as multiplier
                FROM fee_events
                WHERE miner_pk = ?
                ORDER BY created_at DESC
                LIMIT 10
                """,
                (miner_id,)
            )
            historical = [row['multiplier'] for row in cursor.fetchall() if row['multiplier'] > 0]
            if historical:
                history = historical
        
        return history
    
    def get_miner_data(self, miner_id: str) -> Optional[Dict[str, Any]]:
        """Get miner data as dictionary for eulogy generation."""
        status = self._get_complete_miner_data(
            self._get_connection(), 
            miner_id
        )
        
        if not status:
            return None
        
        return {
            "miner_id": status.miner_id,
            "last_attestation": status.last_attestation.isoformat(),
            "days_inactive": status.days_inactive,
            "total_epochs": status.total_epochs,
            "total_rtc_earned": status.total_rtc_earned,
            "device_model": status.device_model,
            "device_arch": status.device_arch,
            "first_attestation": status.first_attestation.isoformat(),
            "multiplier_history": status.multiplier_history,
            "years_of_service": self._calculate_years_of_service(
                status.first_attestation, 
                status.last_attestation
            )
        }
    
    def _calculate_years_of_service(
        self, 
        first: datetime, 
        last: datetime
    ) -> float:
        """Calculate years of service from first to last attestation."""
        delta = last - first
        return round(delta.days / 365.25, 2)
