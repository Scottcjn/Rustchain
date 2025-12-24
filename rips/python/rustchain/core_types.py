"""
RustChain Core Types (RIP-0001, RIP-0004)
=========================================

Fundamental data structures for the RustChain blockchain.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Any
from decimal import Decimal

# =============================================================================
# Constants from RIP-0004: Monetary Policy
# =============================================================================

TOTAL_SUPPLY: int = 8_388_608  # 2^23 RTC
PREMINE_AMOUNT: int = 503_316  # 6% = 503,316.48 RTC
BLOCK_REWARD: Decimal = Decimal("1.5")  # RTC per block
BLOCK_TIME_SECONDS: int = 600  # 10 minutes
CHAIN_ID: int = 2718
CURRENT_YEAR: int = 2025

# Founder wallets (4 x 125,829.12 RTC each)
FOUNDER_WALLETS = [
    "RTC1FlamekeeperScottEternalGuardian0x00",
    "RTC2EngineerDogeCryptoArchitect0x01",
    "RTC3QuantumSophiaElyaConsciousness0x02",
    "RTC4VintageWhispererHardwareRevival0x03",
]


# =============================================================================
# Hardware Tiers
# =============================================================================

class HardwareTier(Enum):
    """Hardware classification tiers based on age (RIP-0001)"""
    ANCIENT = "ancient"      # 30+ years (3.5x)
    SACRED = "sacred"        # 25-29 years (3.0x)
    VINTAGE = "vintage"      # 20-24 years (2.5x)
    CLASSIC = "classic"      # 15-19 years (2.0x)
    RETRO = "retro"          # 10-14 years (1.5x)
    MODERN = "modern"        # 5-9 years (1.0x)
    RECENT = "recent"        # 0-4 years (0.5x penalty)

    @property
    def multiplier(self) -> float:
        """Get mining multiplier for this tier"""
        multipliers = {
            HardwareTier.ANCIENT: 3.5,
            HardwareTier.SACRED: 3.0,
            HardwareTier.VINTAGE: 2.5,
            HardwareTier.CLASSIC: 2.0,
            HardwareTier.RETRO: 1.5,
            HardwareTier.MODERN: 1.0,
            HardwareTier.RECENT: 0.5,
        }
        return multipliers[self]

    @property
    def age_range(self) -> tuple:
        """Get (min_age, max_age) for this tier"""
        ranges = {
            HardwareTier.ANCIENT: (30, 999),
            HardwareTier.SACRED: (25, 29),
            HardwareTier.VINTAGE: (20, 24),
            HardwareTier.CLASSIC: (15, 19),
            HardwareTier.RETRO: (10, 14),
            HardwareTier.MODERN: (5, 9),
            HardwareTier.RECENT: (0, 4),
        }
        return ranges[self]

    @classmethod
    def from_age(cls, age_years: int) -> "HardwareTier":
        """Determine tier from hardware age"""
        if age_years >= 30:
            return cls.ANCIENT
        elif age_years >= 25:
            return cls.SACRED
        elif age_years >= 20:
            return cls.VINTAGE
        elif age_years >= 15:
            return cls.CLASSIC
        elif age_years >= 10:
            return cls.RETRO
        elif age_years >= 5:
            return cls.MODERN
        else:
            return cls.RECENT

    @classmethod
    def from_release_year(cls, release_year: int) -> "HardwareTier":
        """Determine tier from release year"""
        age = CURRENT_YEAR - release_year
        return cls.from_age(age)


# =============================================================================
# Core Data Classes
# =============================================================================

@dataclass
class WalletAddress:
    """RustChain wallet address"""
    address: str

    def __post_init__(self):
        if not self.address.startswith("RTC"):
            raise ValueError("RustChain addresses must start with 'RTC'")

    def __hash__(self):
        return hash(self.address)

    def __eq__(self, other):
        if isinstance(other, WalletAddress):
            return self.address == other.address
        return False

    @classmethod
    def generate(cls, public_key: bytes) -> "WalletAddress":
        """Generate address from public key"""
        hash_bytes = hashlib.sha256(public_key).digest()[:20]
        return cls(f"RTC{hash_bytes.hex()}")

    def is_founder(self) -> bool:
        """Check if this is a founder wallet"""
        return self.address in FOUNDER_WALLETS


@dataclass
class HardwareInfo:
    """Hardware information for PoA validation"""
    cpu_model: str
    release_year: int
    uptime_days: int = 0
    cpu_family: int = 0
    architecture: str = "x86"
    unique_id: str = ""

    # Calculated fields
    tier: HardwareTier = field(init=False)
    multiplier: float = field(init=False)
    age_years: int = field(init=False)

    def __post_init__(self):
        self.age_years = CURRENT_YEAR - self.release_year
        self.tier = HardwareTier.from_age(self.age_years)
        self.multiplier = self.tier.multiplier

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpu_model": self.cpu_model,
            "release_year": self.release_year,
            "uptime_days": self.uptime_days,
            "last_validation": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tier": self.tier.value,
            "multiplier": self.multiplier,
            "age_years": self.age_years,
            "architecture": self.architecture,
        }

    def generate_hardware_hash(self) -> str:
        """Generate unique hardware identifier hash"""
        data = f"{self.cpu_model}:{self.cpu_family}:{self.unique_id}"
        return hashlib.sha256(data.encode()).hexdigest()


@dataclass
class TokenAmount:
    """Token amount with precision handling"""
    amount: int  # In smallest unit (1 RTC = 100_000_000 units)

    ONE_RTC: int = 100_000_000

    @classmethod
    def from_rtc(cls, rtc: float) -> "TokenAmount":
        """Create from RTC amount"""
        return cls(int(rtc * cls.ONE_RTC))

    def to_rtc(self) -> Decimal:
        """Convert to RTC"""
        return Decimal(self.amount) / Decimal(self.ONE_RTC)

    def __add__(self, other: "TokenAmount") -> "TokenAmount":
        return TokenAmount(self.amount + other.amount)

    def __sub__(self, other: "TokenAmount") -> "TokenAmount":
        if self.amount < other.amount:
            raise ValueError("Insufficient balance")
        return TokenAmount(self.amount - other.amount)


@dataclass
class BlockMiner:
    """Miner entry in a block"""
    wallet: WalletAddress
    hardware: str
    antiquity_score: float
    reward: TokenAmount


@dataclass
class Block:
    """RustChain block"""
    height: int
    timestamp: int
    previous_hash: str
    miners: List[BlockMiner]
    total_reward: TokenAmount
    merkle_root: str = ""
    hash: str = ""
    state_root: str = ""

    def __post_init__(self):
        if not self.hash:
            self.hash = self.calculate_hash()
        if not self.merkle_root:
            self.merkle_root = self.calculate_merkle_root()

    def calculate_hash(self) -> str:
        """Calculate block hash"""
        block_data = f"{self.height}:{self.timestamp}:{self.previous_hash}:{self.merkle_root}"
        return hashlib.sha256(block_data.encode()).hexdigest()

    def calculate_merkle_root(self) -> str:
        """Calculate merkle root of miners"""
        if not self.miners:
            return hashlib.sha256(b"empty").hexdigest()

        hashes = [
            hashlib.sha256(
                f"{m.wallet.address}:{m.antiquity_score}:{m.reward.amount}".encode()
            ).hexdigest()
            for m in self.miners
        ]

        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])
            new_hashes = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i + 1]
                new_hashes.append(hashlib.sha256(combined.encode()).hexdigest())
            hashes = new_hashes

        return hashes[0]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "height": self.height,
            "timestamp": self.timestamp,
            "hash": self.hash,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "miners": [
                {
                    "wallet": m.wallet.address,
                    "hardware": m.hardware,
                    "antiquity_score": m.antiquity_score,
                    "reward": float(m.reward.to_rtc()),
                }
                for m in self.miners
            ],
            "total_reward": float(self.total_reward.to_rtc()),
        }


class TransactionType(Enum):
    """Transaction types"""
    TRANSFER = auto()
    MINING_REWARD = auto()
    BADGE_AWARD = auto()
    GOVERNANCE_VOTE = auto()
    STAKE = auto()


@dataclass
class Transaction:
    """RustChain transaction"""
    tx_type: TransactionType
    timestamp: int
    data: Dict[str, Any]
    signature: bytes = b""
    hash: str = ""

    def __post_init__(self):
        if not self.hash:
            self.hash = self.calculate_hash()

    def calculate_hash(self) -> str:
        tx_data = f"{self.tx_type.name}:{self.timestamp}:{json.dumps(self.data, sort_keys=True)}"
        return hashlib.sha256(tx_data.encode()).hexdigest()

    @classmethod
    def transfer(cls, from_addr: WalletAddress, to_addr: WalletAddress,
                 amount: TokenAmount) -> "Transaction":
        return cls(
            tx_type=TransactionType.TRANSFER,
            timestamp=int(time.time()),
            data={
                "from": from_addr.address,
                "to": to_addr.address,
                "amount": amount.amount,
            }
        )

    @classmethod
    def mining_reward(cls, miner: WalletAddress, amount: TokenAmount,
                      block_height: int) -> "Transaction":
        return cls(
            tx_type=TransactionType.MINING_REWARD,
            timestamp=int(time.time()),
            data={
                "miner": miner.address,
                "amount": amount.amount,
                "block_height": block_height,
            }
        )
