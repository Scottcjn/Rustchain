#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Idempotent persistent state manager for the RustChain Catalog Provider Daemon.

Guarantees atomic on-disk persistence so restarts never double-deliver,
and provides public status.json summaries (work counts only, no volume/RTC).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class ProviderStateManager:
    """Manages provider order progression and status metrics."""

    def __init__(self, state_file_path: Path):
        self.state_file = Path(state_file_path).resolve()
        self.orders: Dict[str, Dict[str, Any]] = {}
        self.delivered_hashes: Set[str] = set()
        self.distinct_buyers: Set[str] = set()
        self.delivered_count: int = 0
        self.accepted_count: int = 0
        self.paid_count: int = 0
        self._load()

    def _load(self) -> None:
        """Load state from disk if present."""
        if not self.state_file.exists():
            return

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.orders = data.get("orders", {})
            self.delivered_hashes = set(data.get("delivered_hashes", []))
            self.distinct_buyers = set(data.get("distinct_buyers", []))
            self.delivered_count = int(data.get("delivered_count", 0))
            self.accepted_count = int(data.get("accepted_count", 0))
            self.paid_count = int(data.get("paid_count", 0))
        except (json.JSONDecodeError, OSError, ValueError):
            # If state file was corrupted, maintain memory state
            pass

    def save(self) -> None:
        """Atomically persist state to disk."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "orders": self.orders,
            "delivered_hashes": sorted(list(self.delivered_hashes)),
            "distinct_buyers": sorted(list(self.distinct_buyers)),
            "delivered_count": self.delivered_count,
            "accepted_count": self.accepted_count,
            "paid_count": self.paid_count,
        }
        temp_file = self.state_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_file, self.state_file)

    def is_order_processed(self, order_id: str) -> bool:
        """Check if an order has already been delivered or resolved."""
        return order_id in self.orders

    def is_hash_used(self, deliverable_hash: str) -> bool:
        """Check if a deliverable hash was previously submitted."""
        return deliverable_hash in self.delivered_hashes

    def record_delivery(
        self,
        order_id: str,
        deliverable_hash: str,
        deliverable_uri: str,
        buyer_id: str = "",
        note: str = "",
    ) -> None:
        """Record that an order deliverable was submitted."""
        self.orders[order_id] = {
            "order_id": order_id,
            "status": "delivered",
            "deliverable_hash": deliverable_hash,
            "deliverable_uri": deliverable_uri,
            "buyer_id": buyer_id,
            "note": note,
        }
        self.delivered_hashes.add(deliverable_hash)
        if buyer_id:
            self.distinct_buyers.add(buyer_id)
        self.delivered_count = len([o for o in self.orders.values() if o.get("status") in ("delivered", "accepted", "paid")])
        self.save()

    def record_acceptance(self, order_id: str) -> None:
        """Record that buyer accepted the deliverable."""
        if order_id in self.orders:
            self.orders[order_id]["status"] = "accepted"
            self.accepted_count = len([o for o in self.orders.values() if o.get("status") in ("accepted", "paid")])
            self.save()

    def record_payment(self, order_id: str, tx_hash: Optional[str] = None) -> None:
        """Record that payment for the order was confirmed on-chain."""
        if order_id in self.orders:
            self.orders[order_id]["status"] = "paid"
            if tx_hash:
                self.orders[order_id]["tx_hash"] = tx_hash
            self.paid_count = len([o for o in self.orders.values() if o.get("status") == "paid"])
            self.save()

    def get_pending_delivery_orders(self) -> List[str]:
        """Return orders currently awaiting acceptance or payment."""
        return [
            oid
            for oid, o in self.orders.items()
            if o.get("status") in ("delivered", "accepted")
        ]

    def export_status_json(self, export_path: Path) -> None:
        """Export clean status.json with counts only (no RTC totals)."""
        export_path = Path(export_path).resolve()
        export_path.parent.mkdir(parents=True, exist_ok=True)
        summary = {
            "orders_delivered": self.delivered_count,
            "orders_accepted": self.accepted_count,
            "orders_paid": self.paid_count,
            "distinct_buyers_count": len(self.distinct_buyers),
            "distinct_buyers": sorted(list(self.distinct_buyers)),
        }
        temp_file = export_path.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_file, export_path)
