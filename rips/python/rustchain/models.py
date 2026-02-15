from pydantic import BaseModel
from typing import List, Optional

class Miner(BaseModel):
    miner: str
    hardware_type: str
    antiquity_multiplier: float
    last_attest: int

class Stats(BaseModel):
    epoch: int
    total_miners: int
    total_balance: float

class Epoch(BaseModel):
    epoch: int
    slot: int
    blocks_per_epoch: int
    epoch_pot: float
    enrolled_miners: int

class AttestationResponse(BaseModel):
    success: bool
    enrolled: bool
    epoch: int
    multiplier: float
    next_settlement_slot: int
