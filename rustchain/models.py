"""RustChain data models."""
from dataclasses import dataclass


@dataclass
class NodeHealth:
    """Node health status."""
    ok: bool
    version: str
    uptime_s: int
    db_rw: bool
    tip_age_slots: int
    backup_age_hours: float


@dataclass
class EpochInfo:
    """Epoch information."""
    epoch: int
    slot: int
    blocks_per_epoch: int
    epoch_pot: float
    enrolled_miners: int


@dataclass
class MinerInfo:
    """Miner information."""
    miner: str
    device_arch: str
    device_family: str
    hardware_type: str
    antiquity_multiplier: float
    last_attest: int


@dataclass
class BalanceInfo:
    """Wallet balance information."""
    ok: bool
    miner_id: str
    amount_rtc: float
    amount_i64: int


@dataclass
class SignedTransfer:
    """Signed transfer payload."""
    from_address: str
    to_address: str
    amount_rtc: float
    nonce: int
    signature: str
    public_key: str

    def to_dict(self) -> dict:
        """Convert to dictionary for API submission."""
        return {
            "from_address": self.from_address,
            "to_address": self.to_address,
            "amount_rtc": self.amount_rtc,
            "nonce": self.nonce,
            "signature": self.signature,
            "public_key": self.public_key,
        }
