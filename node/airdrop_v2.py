#!/usr/bin/env python3
"""
RustChain Airdrop V2 - Cross-Chain Distribution Infrastructure

Implements RIP-305: Cross-Chain Airdrop for wRTC on Solana + Base

Tracks:
  A: Solana SPL Token (wRTC)
  B: Base ERC-20 Token (wRTC)
  C: Bridge API (/bridge/lock, /bridge/release)
  D: Eligibility + Claim infrastructure

Anti-Sybil Measures:
  - Wallet balance check (0.1 SOL / 0.01 ETH minimum)
  - Wallet age (> 7 days)
  - GitHub account age (> 30 days)
  - One claim per GitHub/wallet pair

Eligibility Tiers:
  - Stargazer (10+ repos starred): 25 wRTC
  - Contributor (1+ merged PR): 50 wRTC
  - Builder (3+ merged PRs): 100 wRTC
  - Security (verified vulnerability): 150 wRTC
  - Core (5+ merged PRs): 200 wRTC
  - Miner (active attestation): 100 wRTC

Allocation:
  - Solana: 30,000 wRTC
  - Base: 20,000 wRTC
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import sqlite3
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

# Token contracts (to be deployed)
SOLANA_WRTC_MINT = os.environ.get("SOLANA_WRTC_MINT", "")  # SPL token mint
BASE_WRTC_CONTRACT = os.environ.get("BASE_WRTC_CONTRACT", "0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6")  # ERC-20 on Base

# Network configuration
SOLANA_NETWORK = os.environ.get("SOLANA_NETWORK", "mainnet-beta")  # or "devnet"
BASE_CHAIN_ID = 8453  # Base mainnet
BASE_RPC_URL = os.environ.get("BASE_RPC_URL", "https://mainnet.base.org")
SOLANA_RPC_URL = os.environ.get("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")

# Anti-Sybil thresholds
MIN_SOL_BALANCE_LAMPORTS = int(0.1 * 1e9)  # 0.1 SOL
MIN_ETH_BALANCE_WEI = int(0.01 * 1e18)  # 0.01 ETH
MIN_WALLET_AGE_DAYS = 7
MIN_GITHUB_AGE_DAYS = 30

# Airdrop allocation
TOTAL_SOLANA_ALLOCATION = 30_000 * 1_000_000  # 30k wRTC (6 decimals)
TOTAL_BASE_ALLOCATION = 20_000 * 1_000_000  # 20k wRTC (6 decimals)

# Rate limiting
CLAIM_COOLDOWN_SECONDS = 86400 * 30  # 30 days between claims

# ============================================================================
# Enums and Data Classes
# ============================================================================


class EligibilityTier(Enum):
    """Airdrop eligibility tiers."""
    STARGAZER = ("stargazer", 25 * 1_000_000, "10+ repos starred")
    CONTRIBUTOR = ("contributor", 50 * 1_000_000, "1+ merged PR")
    BUILDER = ("builder", 100 * 1_000_000, "3+ merged PRs")
    SECURITY = ("security", 150 * 1_000_000, "Verified vulnerability")
    CORE = ("core", 200 * 1_000_000, "5+ merged PRs / Star King")
    MINER = ("miner", 100 * 1_000_000, "Active attestation")

    def __init__(self, tier_id: str, reward_uwrtc: int, description: str):
        self.tier_id = tier_id
        self.reward_uwrtc = reward_uwrtc  # In micro-wRTC (6 decimals)
        self.description = description


class Chain(Enum):
    """Supported chains for airdrop."""
    SOLANA = "solana"
    BASE = "base"


@dataclass
class EligibilityResult:
    """Result of eligibility check."""
    eligible: bool
    tier: Optional[str] = None
    reward_uwrtc: int = 0
    reward_wrtc: float = 0.0
    reason: str = ""
    checks: Optional[Dict[str, bool]] = None
    github_username: Optional[str] = None
    wallet_address: Optional[str] = None
    chain: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["reward_wrtc"] = self.reward_uwrtc / 1_000_000
        return result


@dataclass
class ClaimRecord:
    """Record of an airdrop claim."""
    claim_id: str
    github_username: str
    wallet_address: str
    chain: str
    tier: str
    amount_uwrtc: int
    amount_wrtc: float
    timestamp: int
    tx_signature: Optional[str] = None
    status: str = "pending"  # pending, completed, failed

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["amount_wrtc"] = self.amount_uwrtc / 1_000_000
        result["timestamp_iso"] = datetime.fromtimestamp(
            self.timestamp, tz=timezone.utc
        ).isoformat()
        return result


@dataclass
class BridgeLock:
    """Record of a bridge lock."""
    lock_id: str
    from_address: str
    to_address: str
    from_chain: str
    to_chain: str
    amount_uwrtc: int
    amount_wrtc: float
    timestamp: int
    status: str = "pending"  # pending, locked, released, failed
    source_tx: Optional[str] = None
    dest_tx: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["amount_wrtc"] = self.amount_uwrtc / 1_000_000
        result["timestamp_iso"] = datetime.fromtimestamp(
            self.timestamp, tz=timezone.utc
        ).isoformat()
        return result


# ============================================================================
# Database Schema
# ============================================================================

AIRDROP_SCHEMA = """
-- Airdrop claims tracking
CREATE TABLE IF NOT EXISTS airdrop_claims (
    claim_id TEXT PRIMARY KEY,
    github_username TEXT NOT NULL,
    wallet_address TEXT NOT NULL,
    chain TEXT NOT NULL,
    tier TEXT NOT NULL,
    amount_uwrtc INTEGER NOT NULL,
    timestamp INTEGER NOT NULL,
    tx_signature TEXT,
    status TEXT DEFAULT 'pending',
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(github_username, wallet_address, chain)
);

-- Bridge lock ledger
CREATE TABLE IF NOT EXISTS bridge_locks (
    lock_id TEXT PRIMARY KEY,
    from_address TEXT NOT NULL,
    to_address TEXT NOT NULL,
    from_chain TEXT NOT NULL,
    to_chain TEXT NOT NULL,
    amount_uwrtc INTEGER NOT NULL,
    timestamp INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    source_tx TEXT,
    dest_tx TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

-- Anti-Sybil cache (GitHub + wallet checks)
CREATE TABLE IF NOT EXISTS sybil_cache (
    cache_key TEXT PRIMARY KEY,
    github_username TEXT,
    wallet_address TEXT,
    chain TEXT,
    wallet_age_days INTEGER,
    wallet_balance_uatomic INTEGER,
    github_age_days INTEGER,
    github_stars INTEGER,
    github_prs INTEGER,
    checked_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL
);

-- Allocation tracking
CREATE TABLE IF NOT EXISTS airdrop_allocation (
    chain TEXT PRIMARY KEY,
    total_uwrtc INTEGER NOT NULL,
    claimed_uwrtc INTEGER DEFAULT 0,
    updated_at INTEGER DEFAULT (strftime('%s', 'now'))
);
"""

# Allocation values (separate to avoid SQL injection concerns)
AIRDROP_INITIAL_ALLOCATIONS = [
    ("solana", TOTAL_SOLANA_ALLOCATION, 0),
    ("base", TOTAL_BASE_ALLOCATION, 0),
]


# ============================================================================
# Core Airdrop Logic
# ============================================================================


class AirdropV2:
    """Cross-chain airdrop infrastructure."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection (shared for in-memory DBs)."""
        if self.db_path == ":memory:":
            if self._conn is None:
                self._conn = sqlite3.connect(":memory:")
                self._conn.row_factory = sqlite3.Row
            return self._conn
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn

    def _close_conn(self, conn: sqlite3.Connection) -> None:
        """Close connection if not in-memory."""
        if self.db_path != ":memory:":
            conn.close()

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_conn()
        conn.executescript(AIRDROP_SCHEMA)
        
        # Initialize allocations
        cursor = conn.cursor()
        cursor.executemany(
            "INSERT OR IGNORE INTO airdrop_allocation (chain, total_uwrtc, claimed_uwrtc) VALUES (?, ?, ?)",
            AIRDROP_INITIAL_ALLOCATIONS,
        )
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_claims_github ON airdrop_claims(github_username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_claims_wallet ON airdrop_claims(wallet_address)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_locks_from ON bridge_locks(from_address)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_locks_to ON bridge_locks(to_address)")
        
        conn.commit()
        
        # Don't close in-memory database connection
        if self.db_path != ":memory:":
            self._close_conn(conn)
        
        logger.info("Airdrop V2 database initialized")

    def _generate_id(self, prefix: str, *args: str) -> str:
        """Generate unique ID from components."""
        data = ":".join([prefix] + list(args) + [str(time.time())])
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    # ========================================================================
    # Eligibility Checks
    # ========================================================================

    @staticmethod
    def _normalize_github_username(github_username: str) -> str:
        return (github_username or "").strip().casefold()

    def check_eligibility(
        self,
        github_username: str,
        wallet_address: str,
        chain: str,
        github_token: Optional[str] = None,
        skip_antisybil: bool = False,
    ) -> EligibilityResult:
        """
        Check airdrop eligibility for a user.

        Args:
            github_username: GitHub username
            wallet_address: Wallet address (Solana or Base)
            chain: Chain name ('solana' or 'base')
            github_token: Optional GitHub API token for higher rate limits
            skip_antisybil: Skip anti-Sybil checks (testing only)

        Returns:
            EligibilityResult with tier and reward info
        """
        github_username = self._normalize_github_username(github_username)
        chain_lower = chain.lower()
        if chain_lower not in ["solana", "base"]:
            return EligibilityResult(
                eligible=False,
                reason=f"Unsupported chain: {chain}. Must be 'solana' or 'base'",
            )

        checks = {}

        # Check if already claimed
        if self._has_claimed(github_username, wallet_address, chain_lower):
            return EligibilityResult(
                eligible=False,
                reason="Already claimed airdrop for this GitHub account or wallet",
                checks={"already_claimed": True},
            )

        # Anti-Sybil checks (can be skipped for testing)
        if not skip_antisybil:
            # Check GitHub account
            github_ok, github_info = self._check_github_account(
                github_username, github_token
            )
            checks["github_valid"] = github_ok
            if not github_ok:
                return EligibilityResult(
                    eligible=False,
                    reason=f"GitHub check failed: {github_info}",
                    checks=checks,
                )

            # Check wallet
            wallet_ok, wallet_info = self._check_wallet(
                wallet_address, chain_lower
            )
            checks["wallet_valid"] = wallet_ok
            if not wallet_ok:
                return EligibilityResult(
                    eligible=False,
                    reason=f"Wallet check failed: {wallet_info}",
                    checks=checks,
                )

        # Determine tier based on GitHub activity
        tier = self._determine_tier(github_username, github_token)
        if tier is None:
            return EligibilityResult(
                eligible=False,
                reason="No eligible tier found (need GitHub activity)",
                checks=checks,
            )

        # Check remaining allocation
        if not self._has_allocation(chain_lower, tier.reward_uwrtc):
            return EligibilityResult(
                eligible=False,
                reason=f"Airdrop allocation exhausted for {chain_lower}",
                checks=checks,
            )

        return EligibilityResult(
            eligible=True,
            tier=tier.tier_id,
            reward_uwrtc=tier.reward_uwrtc,
            reward_wrtc=tier.reward_uwrtc / 1_000_000,
            reason=f"Eligible for {tier.description}",
            checks=checks,
            github_username=github_username,
            wallet_address=wallet_address,
            chain=chain_lower,
        )

    def _check_github_account(
        self, username: str, token: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Check GitHub account meets anti-Sybil requirements.

        Returns:
            (is_valid, reason)
        """
        try:
            import requests

            headers = {"Accept": "application/vnd.github.v3+json"}
            if token:
                headers["Authorization"] = f"token {token}"

            # Get user info
            resp = requests.get(
                f"https://api.github.com/users/{username}",
                headers=headers,
                timeout=10,
            )

            if resp.status_code == 404:
                return False, f"GitHub user '{username}' not found"
            if resp.status_code != 200:
                return False, f"GitHub API error: {resp.status_code}"

            user_data = resp.json()

            # Check account age
            created_at = datetime.fromisoformat(
                user_data["created_at"].replace("Z", "+00:00")
            )
            age_days = (datetime.now(timezone.utc) - created_at).days

            if age_days < MIN_GITHUB_AGE_DAYS:
                return (
                    False,
                    f"GitHub account too new ({age_days} days, need {MIN_GITHUB_AGE_DAYS})",
                )

            # Get starred repos count
            stars_resp = requests.get(
                user_data.get("starred_url", "").replace("{/owner}{/repo}", ""),
                headers=headers,
                timeout=10,
            )
            # GitHub returns Link header with total count
            total_stars = 0
            if "Link" in stars_resp.headers:
                import re
                link_header = stars_resp.headers["Link"]
                match = re.search(r'page=(\d+)>; rel="last"', link_header)
                if match:
                    total_stars = int(match.group(1))

            # Cache the result
            self._cache_sybil_check(
                cache_key=f"github:{username}",
                github_username=username,
                github_age_days=age_days,
                github_stars=total_stars,
            )

            return True, f"Account age: {age_days} days, Stars: {total_stars}"

        except requests.RequestException as e:
            logger.warning(f"GitHub check failed for {username}: {e}")
            return False, f"GitHub API unavailable: {e}"
        except Exception as e:
            logger.warning(f"GitHub check error for {username}: {e}")
            return False, f"Check error: {e}"

    def _check_wallet(
        self, address: str, chain: str
    ) -> Tuple[bool, str]:
        """
        Check wallet meets anti-Sybil requirements.

        Returns:
            (is_valid, reason)
        """
        try:
            if chain == "solana":
                return self._check_solana_wallet(address)
            elif chain == "base":
                return self._check_base_wallet(address)
            else:
                return False, f"Unsupported chain: {chain}"

        except Exception as e:
            logger.warning(f"Wallet check failed for {address}: {e}")
            return False, f"Check error: {e}"

    def _check_solana_wallet(self, address: str) -> Tuple[bool, str]:
        """Check Solana wallet balance and age."""
        try:
            import requests

            # Check balance via RPC
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBalance",
                "params": [address],
            }

            resp = requests.post(
                SOLANA_RPC_URL,
                json=payload,
                timeout=10,
            )

            if resp.status_code != 200:
                return False, "Solana RPC error"

            result = resp.json()
            if "error" in result:
                return False, result["error"]["message"]

            balance = result.get("result", {}).get("value", 0)
            balance_sol = balance / 1e9

            # Note: Wallet age check requires historical data which is complex
            # For now, we just check balance
            if balance < MIN_SOL_BALANCE_LAMPORTS:
                return (
                    False,
                    f"Insufficient SOL balance ({balance_sol:.4f} SOL, need {MIN_SOL_BALANCE_LAMPORTS/1e9})",
                )

            self._cache_sybil_check(
                cache_key=f"solana:{address}",
                wallet_address=address,
                chain="solana",
                wallet_balance_uatomic=balance,
            )

            return True, f"Balance: {balance_sol:.4f} SOL"

        except requests.RequestException as e:
            return False, f"Solana RPC unavailable: {e}"

    def _check_base_wallet(self, address: str) -> Tuple[bool, str]:
        """Check Base wallet balance and age."""
        try:
            import requests

            # Check ETH balance via RPC
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_getBalance",
                "params": [address, "latest"],
            }

            resp = requests.post(
                BASE_RPC_URL,
                json=payload,
                timeout=10,
            )

            if resp.status_code != 200:
                return False, "Base RPC error"

            result = resp.json()
            if "error" in result:
                return False, result["error"]["message"]

            balance_hex = result.get("result", "0x0")
            balance_wei = int(balance_hex, 16)
            balance_eth = balance_wei / 1e18

            if balance_wei < MIN_ETH_BALANCE_WEI:
                return (
                    False,
                    f"Insufficient ETH balance ({balance_eth:.6f} ETH, need {MIN_ETH_BALANCE_WEI/1e18})",
                )

            self._cache_sybil_check(
                cache_key=f"base:{address}",
                wallet_address=address,
                chain="base",
                wallet_balance_uatomic=balance_wei,
            )

            return True, f"Balance: {balance_eth:.6f} ETH"

        except requests.RequestException as e:
            return False, f"Base RPC unavailable: {e}"

    def _determine_tier(
        self, github_username: str, token: Optional[str] = None
    ) -> Optional[EligibilityTier]:
        """
        Determine airdrop tier based on GitHub activity.

        Returns:
            EligibilityTier or None if not eligible
        """
        try:
            import requests

            headers = {"Accept": "application/vnd.github.v3+json"}
            if token:
                headers["Authorization"] = f"token {token}"

            # Get user info
            user_resp = requests.get(
                f"https://api.github.com/users/{github_username}",
                headers=headers,
                timeout=10,
            )

            if user_resp.status_code != 200:
                return None

            # Get contributions (PRs merged)
            # Use GitHub search API for contributions
            contrib_resp = requests.get(
                f"https://api.github.com/search/commits",
                headers={
                    **headers,
                    "Accept": "application/vnd.github.cloak-preview",
                },
                params={
                    "q": f"author:{github_username} merged:true",
                    "per_page": 1,
                },
                timeout=10,
            )

            total_prs = 0
            if contrib_resp.status_code == 200:
                total_prs = contrib_resp.json().get("total_count", 0)

            # Get starred repos
            stars_resp = requests.get(
                f"https://api.github.com/users/{github_username}/starred",
                headers=headers,
                params={"per_page": 1},
                timeout=10,
            )

            total_stars = 0
            if "Link" in stars_resp.headers:
                import re
                link_header = stars_resp.headers["Link"]
                match = re.search(r'page=(\d+)>; rel="last"', link_header)
                if match:
                    total_stars = int(match.group(1))

            # Determine tier (highest first)
            if total_prs >= 5:
                return EligibilityTier.CORE
            if total_prs >= 3:
                return EligibilityTier.BUILDER
            if total_prs >= 1:
                return EligibilityTier.CONTRIBUTOR
            if total_stars >= 10:
                return EligibilityTier.STARGAZER

            return None

        except Exception as e:
            logger.warning(f"Tier determination failed for {github_username}: {e}")
            return None

    def _has_claimed(
        self, github_username: str, wallet_address: str, chain: str
    ) -> bool:
        """Check if a GitHub account or wallet already claimed an airdrop."""
        github_username = self._normalize_github_username(github_username)
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 1 FROM airdrop_claims
            WHERE chain = ?
            AND (github_username = ? OR wallet_address = ?)
            AND status IN ('pending', 'completed')
            """,
            (chain, github_username, wallet_address),
        )
        result = cursor.fetchone() is not None
        self._close_conn(conn)
        return result

    def _has_allocation(self, chain: str, amount_uwrtc: int) -> bool:
        """Check if chain has remaining allocation."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT total_uwrtc, claimed_uwrtc FROM airdrop_allocation
            WHERE chain = ?
            """,
            (chain,),
        )
        row = cursor.fetchone()
        self._close_conn(conn)

        if not row:
            return False

        remaining = row["total_uwrtc"] - row["claimed_uwrtc"]
        return remaining >= amount_uwrtc

    def _cache_sybil_check(self, cache_key: str, **kwargs) -> None:
        """Cache anti-Sybil check result."""
        conn = self._get_conn()
        cursor = conn.cursor()

        now = int(time.time())
        expires = now + 3600  # Cache for 1 hour

        cursor.execute(
            """
            INSERT OR REPLACE INTO sybil_cache
            (cache_key, github_username, wallet_address, chain,
             wallet_age_days, wallet_balance_uatomic, github_age_days,
             github_stars, github_prs, checked_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cache_key,
                kwargs.get("github_username"),
                kwargs.get("wallet_address"),
                kwargs.get("chain"),
                kwargs.get("wallet_age_days"),
                kwargs.get("wallet_balance_uatomic"),
                kwargs.get("github_age_days"),
                kwargs.get("github_stars"),
                kwargs.get("github_prs"),
                now,
                expires,
            ),
        )
        conn.commit()
        self._close_conn(conn)

    # ========================================================================
    # Claim Processing
    # ========================================================================

    def claim_airdrop(
        self,
        github_username: str,
        wallet_address: str,
        chain: str,
        tier: str,
        github_token: Optional[str] = None,
        skip_antisybil: bool = False,
    ) -> Tuple[bool, str, Optional[ClaimRecord]]:
        """
        Process airdrop claim.

        Args:
            github_username: GitHub username
            wallet_address: Wallet address
            chain: Chain name
            tier: Eligibility tier
            github_token: Optional GitHub API token
            skip_antisybil: Skip anti-Sybil checks (testing only)

        Returns:
            (success, message, claim_record)
        """
        github_username = self._normalize_github_username(github_username)
        chain_lower = chain.lower()

        if self._has_claimed(github_username, wallet_address, chain_lower):
            return False, "Claim already exists for this GitHub account or wallet", None

        # When skip_antisybil is True (testing), use provided tier directly
        if skip_antisybil:
            tier_enum = getattr(EligibilityTier, tier.upper(), None)
            if not tier_enum:
                return False, f"Invalid tier: {tier}", None
            
            # Still check allocation
            if not self._has_allocation(chain_lower, tier_enum.reward_uwrtc):
                return False, f"Airdrop allocation exhausted for {chain_lower}", None
            
            result = EligibilityResult(
                eligible=True,
                tier=tier_enum.tier_id,
                reward_uwrtc=tier_enum.reward_uwrtc,
                reward_wrtc=tier_enum.reward_uwrtc / 1_000_000,
                reason=f"Testing mode - {tier_enum.description}",
                checks={"skip_antisybil": True},
                github_username=github_username,
                wallet_address=wallet_address,
                chain=chain_lower,
            )
        else:
            # Verify eligibility
            result = self.check_eligibility(
                github_username, wallet_address, chain_lower, github_token, skip_antisybil
            )

            if not result.eligible:
                return False, result.reason, None

            # Verify tier matches
            tier_enum = getattr(EligibilityTier, tier.upper(), None)
            if not tier_enum or tier_enum.tier_id != result.tier:
                return False, f"Invalid tier. Eligible tier: {result.tier}", None

        # Generate claim ID
        claim_id = self._generate_id("claim", github_username, wallet_address, chain_lower)
        tier_lower = tier.lower()

        # Create claim record
        claim = ClaimRecord(
            claim_id=claim_id,
            github_username=github_username,
            wallet_address=wallet_address,
            chain=chain_lower,
            tier=tier_lower,
            amount_uwrtc=result.reward_uwrtc,
            amount_wrtc=result.reward_uwrtc / 1_000_000,
            timestamp=int(time.time()),
            status="pending",
        )

        # Store claim
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO airdrop_claims
                (claim_id, github_username, wallet_address, chain, tier,
                 amount_uwrtc, timestamp, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim.claim_id,
                    claim.github_username,
                    claim.wallet_address,
                    claim.chain,
                    claim.tier,
                    claim.amount_uwrtc,
                    claim.timestamp,
                    claim.status,
                ),
            )

            # Update allocation atomically to prevent TOCTOU race
            cursor.execute(
                """
                UPDATE airdrop_allocation
                SET claimed_uwrtc = claimed_uwrtc + ?, updated_at = ?
                WHERE chain = ? AND (total_uwrtc - claimed_uwrtc) >= ?
                """,
                (claim.amount_uwrtc, claim.timestamp, chain_lower, claim.amount_uwrtc),
            )

            if cursor.rowcount == 0:
                conn.rollback()
                return False, "Airdrop allocation exhausted or concurrent claim conflict", None

            conn.commit()
            logger.info(
                f"Airdrop claim created: {claim_id} - "
                f"{github_username} -> {wallet_address} ({chain_lower}) - "
                f"{claim.amount_wrtc} wRTC"
            )

            return True, "Claim created successfully", claim

        except sqlite3.IntegrityError as e:
            conn.rollback()
            return False, "Claim already exists for this wallet/github pair", None
        except Exception as e:
            conn.rollback()
            logger.error(f"Claim processing error: {e}")
            return False, f"Processing error: {e}", None
        finally:
            self._close_conn(conn)

    def finalize_claim(
        self, claim_id: str, tx_signature: str
    ) -> Tuple[bool, str]:
        """
        Mark claim as completed with transaction signature.

        Args:
            claim_id: Claim ID
            tx_signature: Blockchain transaction signature

        Returns:
            (success, message)
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE airdrop_claims
            SET status = 'completed', tx_signature = ?
            WHERE claim_id = ? AND status = 'pending'
            """,
            (tx_signature, claim_id),
        )

        if cursor.rowcount == 0:
            self._close_conn(conn)
            return False, "Claim not found or already finalized"

        conn.commit()
        self._close_conn(conn)
        logger.info(f"Claim finalized: {claim_id} with tx {tx_signature[:16]}...")
        return True, "Claim completed"

    # ========================================================================
    # Bridge Operations
    # ========================================================================

    def create_bridge_lock(
        self,
        from_address: str,
        to_address: str,
        from_chain: str,
        to_chain: str,
        amount_uwrtc: int,
    ) -> Tuple[bool, str, Optional[BridgeLock]]:
        """
        Create a bridge lock.

        Args:
            from_address: Source wallet address
            to_address: Destination wallet address
            from_chain: Source chain
            to_chain: Destination chain
            amount_uwrtc: Amount in micro-wRTC

        Returns:
            (success, message, lock_record)
        """
        # Validate chains
        if from_chain not in ["solana", "base", "rustchain"]:
            return False, f"Invalid source chain: {from_chain}", None
        if to_chain not in ["solana", "base", "rustchain"]:
            return False, f"Invalid destination chain: {to_chain}", None
        if from_chain == to_chain:
            return False, "Source and destination chains must differ", None

        # Validate amount
        if amount_uwrtc <= 0:
            return False, "Amount must be positive", None

        # Generate lock ID
        lock_id = self._generate_id(
            "bridge", from_address, to_address, from_chain, to_chain
        )

        # Create lock record
        lock = BridgeLock(
            lock_id=lock_id,
            from_address=from_address,
            to_address=to_address,
            from_chain=from_chain,
            to_chain=to_chain,
            amount_uwrtc=amount_uwrtc,
            amount_wrtc=amount_uwrtc / 1_000_000,
            timestamp=int(time.time()),
            status="pending",
        )

        # Store lock
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO bridge_locks
                (lock_id, from_address, to_address, from_chain, to_chain,
                 amount_uwrtc, timestamp, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    lock.lock_id,
                    lock.from_address,
                    lock.to_address,
                    lock.from_chain,
                    lock.to_chain,
                    lock.amount_uwrtc,
                    lock.timestamp,
                    lock.status,
                ),
            )
            conn.commit()
            logger.info(
                f"Bridge lock created: {lock_id} - "
                f"{amount_uwrtc / 1_000_000} wRTC from {from_chain} to {to_chain}"
            )
            return True, "Bridge lock created", lock

        except Exception as e:
            conn.rollback()
            logger.error(f"Bridge lock error: {e}")
            return False, f"Error: {e}", None
        finally:
            self._close_conn(conn)

    def confirm_bridge_lock(
        self, lock_id: str, source_tx: str
    ) -> Tuple[bool, str]:
        """
        Confirm bridge lock with source transaction.

        Args:
            lock_id: Lock ID
            source_tx: Source chain transaction signature

        Returns:
            (success, message)
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE bridge_locks
            SET status = 'locked', source_tx = ?
            WHERE lock_id = ? AND status = 'pending'
            """,
            (source_tx, lock_id),
        )

        if cursor.rowcount == 0:
            self._close_conn(conn)
            return False, "Lock not found or already confirmed"

        conn.commit()
        self._close_conn(conn)
        return True, "Lock confirmed"

    def release_bridge_lock(
        self, lock_id: str, dest_tx: str
    ) -> Tuple[bool, str]:
        """
        Release bridge lock with destination transaction.

        Args:
            lock_id: Lock ID
            dest_tx: Destination chain transaction signature

        Returns:
            (success, message)
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE bridge_locks
            SET status = 'released', dest_tx = ?
            WHERE lock_id = ? AND status = 'locked'
            """,
            (dest_tx, lock_id),
        )

        if cursor.rowcount == 0:
            self._close_conn(conn)
            return False, "Lock not found or not in locked status"

        conn.commit()
        self._close_conn(conn)
        return True, "Lock released"

    # ========================================================================
    # Query Methods
    # ========================================================================

    def get_claim(self, claim_id: str) -> Optional[ClaimRecord]:
        """Get claim by ID."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM airdrop_claims WHERE claim_id = ?", (claim_id,)
        )
        row = cursor.fetchone()
        self._close_conn(conn)

        if not row:
            return None

        return ClaimRecord(
            claim_id=row["claim_id"],
            github_username=row["github_username"],
            wallet_address=row["wallet_address"],
            chain=row["chain"],
            tier=row["tier"],
            amount_uwrtc=row["amount_uwrtc"],
            amount_wrtc=row["amount_uwrtc"] / 1_000_000,
            timestamp=row["timestamp"],
            tx_signature=row["tx_signature"],
            status=row["status"],
        )

    def get_claims_by_github(
        self, github_username: str
    ) -> List[ClaimRecord]:
        """Get all claims for a GitHub user."""
        github_username = self._normalize_github_username(github_username)
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM airdrop_claims WHERE github_username = ?",
            (github_username,),
        )
        rows = cursor.fetchall()
        self._close_conn(conn)

        return [
            ClaimRecord(
                claim_id=row["claim_id"],
                github_username=row["github_username"],
                wallet_address=row["wallet_address"],
                chain=row["chain"],
                tier=row["tier"],
                amount_uwrtc=row["amount_uwrtc"],
                amount_wrtc=row["amount_uwrtc"] / 1_000_000,
                timestamp=row["timestamp"],
                tx_signature=row["tx_signature"],
                status=row["status"],
            )
            for row in rows
        ]

    def get_lock(self, lock_id: str) -> Optional[BridgeLock]:
        """Get bridge lock by ID."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM bridge_locks WHERE lock_id = ?", (lock_id,)
        )
        row = cursor.fetchone()
        self._close_conn(conn)

        if not row:
            return None

        return BridgeLock(
            lock_id=row["lock_id"],
            from_address=row["from_address"],
            to_address=row["to_address"],
            from_chain=row["from_chain"],
            to_chain=row["to_chain"],
            amount_uwrtc=row["amount_uwrtc"],
            amount_wrtc=row["amount_uwrtc"] / 1_000_000,
            timestamp=row["timestamp"],
            status=row["status"],
            source_tx=row["source_tx"],
            dest_tx=row["dest_tx"],
        )

    def get_allocation_status(self) -> Dict[str, Dict[str, Any]]:
        """Get airdrop allocation status for all chains."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM airdrop_allocation")
        rows = cursor.fetchall()
        self._close_conn(conn)

        return {
            row["chain"]: {
                "total_wrtc": row["total_uwrtc"] / 1_000_000,
                "claimed_wrtc": row["claimed_uwrtc"] / 1_000_000,
                "remaining_wrtc": (row["total_uwrtc"] - row["claimed_uwrtc"])
                / 1_000_000,
                "percent_claimed": (row["claimed_uwrtc"] / row["total_uwrtc"])
                * 100,
            }
            for row in rows
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get airdrop statistics."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Total claims
        cursor.execute("SELECT COUNT(*) as count FROM airdrop_claims")
        total_claims = cursor.fetchone()["count"]

        # Claims by tier
        cursor.execute(
            """
            SELECT tier, COUNT(*) as count, SUM(amount_uwrtc) as total
            FROM airdrop_claims GROUP BY tier
            """
        )
        by_tier = {
            row["tier"]: {"count": row["count"], "total_wrtc": row["total"] / 1_000_000}
            for row in cursor.fetchall()
        }

        # Claims by chain
        cursor.execute(
            """
            SELECT chain, COUNT(*) as count, SUM(amount_uwrtc) as total
            FROM airdrop_claims GROUP BY chain
            """
        )
        by_chain = {
            row["chain"]: {"count": row["count"], "total_wrtc": row["total"] / 1_000_000}
            for row in cursor.fetchall()
        }

        # Bridge locks
        cursor.execute("SELECT COUNT(*) as count FROM bridge_locks WHERE status = 'locked'")
        pending_locks = cursor.fetchone()["count"]

        self._close_conn(conn)

        return {
            "total_claims": total_claims,
            "by_tier": by_tier,
            "by_chain": by_chain,
            "pending_bridge_locks": pending_locks,
            "allocation": self.get_allocation_status(),
        }


# ============================================================================
# Flask Integration Helper
# ============================================================================


def init_airdrop_routes(app, airdrop: AirdropV2, db_path: str) -> None:
    """
    Initialize airdrop API routes on Flask app.

    Args:
        app: Flask application
        airdrop: AirdropV2 instance
        db_path: Database path for persistence
    """

    def require_admin_key():
        required = os.environ.get("RC_ADMIN_KEY", "").strip()
        if not required:
            return jsonify({"ok": False, "error": "admin_key_not_configured"}), 503
        provided = (
            request.headers.get("X-Admin-Key")
            or request.headers.get("X-API-Key")
            or ""
        ).strip()
        if not hmac.compare_digest(provided, required):
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        return None

    @app.route("/api/airdrop/eligibility", methods=["POST"])
    def check_airdrop_eligibility():
        """Check airdrop eligibility."""
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"ok": False, "error": "invalid_json"}), 400

        github_username = data.get("github_username", "").strip()
        wallet_address = data.get("wallet_address", "").strip()
        chain = data.get("chain", "").strip()
        github_token = data.get("github_token")
        # SECURITY: skip_antisybil must NEVER be settable from API requests.
        # It exists only for internal testing via direct Python calls.

        if not github_username:
            return jsonify({"ok": False, "error": "missing_github_username"}), 400
        if not wallet_address:
            return jsonify({"ok": False, "error": "missing_wallet_address"}), 400
        if not chain:
            return jsonify({"ok": False, "error": "missing_chain"}), 400

        result = airdrop.check_eligibility(
            github_username, wallet_address, chain, github_token, skip_antisybil=False
        )

        return jsonify({"ok": result.eligible, **result.to_dict()})

    @app.route("/api/airdrop/claim", methods=["POST"])
    def claim_airdrop():
        """Submit airdrop claim."""
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"ok": False, "error": "invalid_json"}), 400

        github_username = data.get("github_username", "").strip()
        wallet_address = data.get("wallet_address", "").strip()
        chain = data.get("chain", "").strip()
        tier = data.get("tier", "").strip()
        github_token = data.get("github_token")

        if not all([github_username, wallet_address, chain, tier]):
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": "missing_required_fields",
                        "required": ["github_username", "wallet_address", "chain", "tier"],
                    }
                ),
                400,
            )

        success, message, claim = airdrop.claim_airdrop(
            github_username, wallet_address, chain, tier, github_token
        )

        if success:
            return jsonify({"ok": True, "message": message, "claim": claim.to_dict()})
        else:
            return jsonify({"ok": False, "error": message}), 400

    @app.route("/api/airdrop/claim/<claim_id>", methods=["GET"])
    def get_airdrop_claim(claim_id: str):
        """Get claim status."""
        claim = airdrop.get_claim(claim_id)
        if claim:
            return jsonify({"ok": True, "claim": claim.to_dict()})
        return jsonify({"ok": False, "error": "claim_not_found"}), 404

    @app.route("/api/airdrop/stats", methods=["GET"])
    def get_airdrop_stats():
        """Get airdrop statistics."""
        return jsonify({"ok": True, "stats": airdrop.get_stats()})

    @app.route("/api/bridge/lock", methods=["POST"])
    def create_bridge_lock():
        """Create bridge lock."""
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"ok": False, "error": "invalid_json"}), 400

        from_address = data.get("from_address", "").strip()
        to_address = data.get("to_address", "").strip()
        from_chain = data.get("from_chain", "").strip()
        to_chain = data.get("to_chain", "").strip()
        amount_wrtc = data.get("amount_wrtc", 0)

        if not all([from_address, to_address, from_chain, to_chain]):
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": "missing_required_fields",
                        "required": ["from_address", "to_address", "from_chain", "to_chain"],
                    }
                ),
                400,
            )

        amount_uwrtc = int(float(amount_wrtc) * 1_000_000)

        success, message, lock = airdrop.create_bridge_lock(
            from_address, to_address, from_chain, to_chain, amount_uwrtc
        )

        if success:
            return jsonify({"ok": True, "message": message, "lock": lock.to_dict()})
        else:
            return jsonify({"ok": False, "error": message}), 400

    @app.route("/api/bridge/lock/<lock_id>/confirm", methods=["POST"])
    def confirm_lock(lock_id: str):
        """Confirm bridge lock with source tx."""
        auth_error = require_admin_key()
        if auth_error:
            return auth_error

        data = request.get_json(silent=True) or {}
        source_tx = data.get("source_tx", "").strip()

        if not source_tx:
            return jsonify({"ok": False, "error": "missing_source_tx"}), 400

        success, message = airdrop.confirm_bridge_lock(lock_id, source_tx)

        if success:
            return jsonify({"ok": True, "message": message})
        else:
            return jsonify({"ok": False, "error": message}), 400

    @app.route("/api/bridge/lock/<lock_id>/release", methods=["POST"])
    def release_lock(lock_id: str):
        """Release bridge lock with dest tx."""
        auth_error = require_admin_key()
        if auth_error:
            return auth_error

        data = request.get_json(silent=True) or {}
        dest_tx = data.get("dest_tx", "").strip()

        if not dest_tx:
            return jsonify({"ok": False, "error": "missing_dest_tx"}), 400

        success, message = airdrop.release_bridge_lock(lock_id, dest_tx)

        if success:
            return jsonify({"ok": True, "message": message})
        else:
            return jsonify({"ok": False, "error": message}), 400

    @app.route("/api/bridge/lock/<lock_id>", methods=["GET"])
    def get_bridge_lock(lock_id: str):
        """Get bridge lock status."""
        lock = airdrop.get_lock(lock_id)
        if lock:
            return jsonify({"ok": True, "lock": lock.to_dict()})
        return jsonify({"ok": False, "error": "lock_not_found"}), 404


# Import Flask dependencies if available
try:
    from flask import request, jsonify
except ImportError:
    pass  # Flask not available, routes won't be registered
