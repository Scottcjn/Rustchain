"""Data models for RTC<->ERG bridge scaffolding."""
from dataclasses import dataclass
from enum import Enum

class BridgeDirection(str, Enum):
    RTC_TO_ERG = "rtc_to_erg"
    ERG_TO_RTC = "erg_to_rtc"

@dataclass
class BridgeIntent:
    intent_id: str
    direction: BridgeDirection
    source_wallet: str
    target_wallet: str
    amount: int
    nonce: str

@dataclass
class BridgeEvent:
    event_id: str
    intent_id: str
    stage: str
    tx_ref: str | None = None
