"""
RustChain Chain Parameters (RIP-0004)
=====================================

Central configuration for all chain constants.
"""

from decimal import Decimal

# =============================================================================
# Core Chain Parameters
# =============================================================================

CHAIN_ID: int = 2718  # Euler's number tribute
CHAIN_NAME: str = "RustChain"
NETWORK_MAGIC: bytes = b"RUST"

# =============================================================================
# Monetary Policy (RIP-0004)
# =============================================================================

TOTAL_SUPPLY: int = 8_388_608  # 2^23 RTC
PREMINE_AMOUNT: int = 503_316  # 6% for founders
PREMINE_PER_FOUNDER: Decimal = Decimal("125829.12")  # 4 founders

BLOCK_REWARD: Decimal = Decimal("1.5")  # RTC per block
BLOCK_TIME_SECONDS: int = 600  # 10 minutes

# Halving schedule
HALVING_INTERVAL_BLOCKS: int = 210_000  # ~4 years
HALVING_COUNT: int = 4  # After 4 halvings, tail emission

# Token precision
DECIMALS: int = 8
ONE_RTC: int = 100_000_000  # 1 RTC = 10^8 units

# =============================================================================
# Founder Wallets
# =============================================================================

FOUNDER_WALLETS = [
    "RTC1FlamekeeperScottEternalGuardian0x00",
    "RTC2EngineerDogeCryptoArchitect0x01",
    "RTC3QuantumSophiaElyaConsciousness0x02",
    "RTC4VintageWhispererHardwareRevival0x03",
]

# =============================================================================
# Consensus Parameters
# =============================================================================

CURRENT_YEAR: int = 2025

# Antiquity Score parameters
AS_MAX: float = 100.0  # Maximum for reward capping
AS_MIN: float = 1.0    # Minimum to participate

# Hardware tier multipliers
HARDWARE_TIERS = {
    "ancient": {"min_age": 30, "max_age": 999, "multiplier": 3.5},
    "sacred": {"min_age": 25, "max_age": 29, "multiplier": 3.0},
    "vintage": {"min_age": 20, "max_age": 24, "multiplier": 2.5},
    "classic": {"min_age": 15, "max_age": 19, "multiplier": 2.0},
    "retro": {"min_age": 10, "max_age": 14, "multiplier": 1.5},
    "modern": {"min_age": 5, "max_age": 9, "multiplier": 1.0},
    "recent": {"min_age": 0, "max_age": 4, "multiplier": 0.5},
}

# Block parameters
MAX_MINERS_PER_BLOCK: int = 100
MAX_BLOCK_SIZE_BYTES: int = 1_000_000  # 1 MB

# =============================================================================
# Governance Parameters (RIP-0002)
# =============================================================================

VOTING_PERIOD_DAYS: int = 7
QUORUM_PERCENTAGE: float = 0.33  # 33%
EXECUTION_DELAY_BLOCKS: int = 3
REPUTATION_DECAY_WEEKLY: float = 0.05

# =============================================================================
# Network Parameters
# =============================================================================

DEFAULT_PORT: int = 8085
MTLS_PORT: int = 4443
PROTOCOL_VERSION: str = "1.0.0"

MAX_PEERS: int = 50
PEER_TIMEOUT_SECONDS: int = 30
SYNC_BATCH_SIZE: int = 100

# =============================================================================
# Drift Lock Parameters (RIP-0003)
# =============================================================================

DRIFT_THRESHOLD: float = 0.15  # 15% deviation triggers quarantine
QUARANTINE_DURATION_BLOCKS: int = 144  # ~24 hours
CHALLENGE_RESPONSE_TIMEOUT: int = 300  # 5 minutes

# =============================================================================
# Deep Entropy Parameters (RIP-0001)
# =============================================================================

# Entropy layer weights
ENTROPY_WEIGHTS = {
    "instruction_timing": 0.30,
    "memory_patterns": 0.25,
    "bus_timing": 0.20,
    "thermal_signature": 0.15,
    "architectural_quirks": 0.10,
}

# Emulation detection thresholds
EMULATION_PROBABILITY_THRESHOLD: float = 0.50
MIN_ENTROPY_SCORE: float = 0.60

# =============================================================================
# Genesis Block
# =============================================================================

GENESIS_HASH: str = "019c177b44a41f78da23caa99314adbc44889be2dcdd5021930f9d991e7e34cf"
GENESIS_TIMESTAMP: int = 1735689600  # 2025-01-01 00:00:00 UTC
GENESIS_DIFFICULTY: int = 1

# =============================================================================
# Helper Functions
# =============================================================================

def get_tier_for_age(age_years: int) -> str:
    """Determine hardware tier from age"""
    for tier_name, params in HARDWARE_TIERS.items():
        if params["min_age"] <= age_years <= params["max_age"]:
            return tier_name
    return "recent"

def get_multiplier_for_tier(tier: str) -> float:
    """Get mining multiplier for a tier"""
    return HARDWARE_TIERS.get(tier, {}).get("multiplier", 0.5)

def calculate_block_reward(height: int) -> Decimal:
    """Calculate block reward at a given height"""
    halvings = height // HALVING_INTERVAL_BLOCKS
    if halvings >= HALVING_COUNT:
        # Tail emission after 4 halvings
        return BLOCK_REWARD / Decimal(2 ** HALVING_COUNT)
    return BLOCK_REWARD / Decimal(2 ** halvings)
