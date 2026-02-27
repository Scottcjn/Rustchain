"""Spectrum DEX integration scaffold for RTC/ERG pair."""
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class SpectrumConfig:
    base_url: str = "https://api.spectrum.fi"
    network: str = "ergo-mainnet"

class SpectrumClient:
    def __init__(self, cfg: SpectrumConfig | None = None):
        self.cfg = cfg or SpectrumConfig()

    def get_pair(self, base: str, quote: str) -> Dict[str, Any]:
        return {"ok": False, "error": "not_implemented", "base": base, "quote": quote}

    def get_quote(self, base: str, quote: str, amount_in: int) -> Dict[str, Any]:
        return {"ok": False, "error": "not_implemented", "amount_in": amount_in}

    def build_swap_intent(self, wallet: str, base: str, quote: str, amount_in: int) -> Dict[str, Any]:
        return {
            "ok": False,
            "error": "not_implemented",
            "wallet": wallet,
            "base": base,
            "quote": quote,
            "amount_in": amount_in,
        }
