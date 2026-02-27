"""Dry-run bridge daemon scaffold for lock/mint and burn/release flows."""
from __future__ import annotations
import time
from .models import BridgeIntent

class BridgeDaemon:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run

    def process_intent(self, intent: BridgeIntent) -> dict:
        # Placeholder lifecycle simulation
        return {
            "ok": False,
            "error": "not_implemented",
            "intent_id": intent.intent_id,
            "direction": intent.direction.value,
            "dry_run": self.dry_run,
        }

    def run_once(self) -> dict:
        return {"ok": True, "mode": "dry-run", "ts": int(time.time())}
