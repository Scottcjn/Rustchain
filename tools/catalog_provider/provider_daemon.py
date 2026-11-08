#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Autonomous Service Catalog Provider Daemon for RustChain (RIP-302).

Polls node /catalog for requested orders, executes deliverables via pluggable
workers, submits deliveries with unique sha256 hashes, monitors acceptance
and confirmed on-chain payments, and maintains state across restarts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Locate repository root for tools/catalog_cli imports
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from .state import ProviderStateManager
from .workers import BaseWorker, CodeReviewWorker, DocsLintWorker

logger = logging.getLogger("catalog_provider")


class CatalogProviderDaemon:
    """Unattended provider daemon for the RustChain service catalog."""

    def __init__(
        self,
        client: Any,
        worker: BaseWorker,
        state_manager: ProviderStateManager,
        listing_id: Optional[str] = None,
        poll_interval: float = 10.0,
        max_concurrent: int = 2,
        status_file: Optional[Path] = None,
        kill_switch_file: Optional[Path] = None,
        deliverables_dir: Optional[Path] = None,
    ):
        self.client = client
        self.worker = worker
        self.state = state_manager
        self.listing_id = listing_id
        self.poll_interval = max(1.0, float(poll_interval))
        self.max_concurrent = max(1, int(max_concurrent))
        self.status_file = Path(status_file).resolve() if status_file else None
        self.kill_switch_file = Path(kill_switch_file).resolve() if kill_switch_file else None
        self.deliverables_dir = Path(deliverables_dir).resolve() if deliverables_dir else None
        self._running = True

        if self.deliverables_dir:
            self.deliverables_dir.mkdir(parents=True, exist_ok=True)

    def is_kill_switched(self) -> bool:
        """Check if kill switch file exists."""
        if self.kill_switch_file and self.kill_switch_file.exists():
            logger.warning("Kill switch file detected at %s. Halting daemon.", self.kill_switch_file)
            return True
        return False

    def process_requested_orders(self) -> int:
        """Poll and fulfill pending requested orders."""
        try:
            res = self.client.my_orders(role="provider", status="requested")
            orders = res.get("orders", []) if isinstance(res, dict) else []
        except Exception as exc:
            logger.error("Failed to query requested orders: %s", exc)
            return 0

        processed = 0
        for order in orders:
            if processed >= self.max_concurrent:
                logger.info("Reached max concurrent batch limit (%d).", self.max_concurrent)
                break

            order_id = order.get("id")
            if not order_id:
                continue

            # Check listing match if configured
            if self.listing_id and order.get("listing_id") != self.listing_id:
                continue

            # Idempotency check: never re-process already handled order
            if self.state.is_order_processed(order_id):
                continue

            buyer_id = order.get("buyer", order.get("buyer_id", ""))
            note = order.get("note", "")

            logger.info("Processing order %s from buyer %s...", order_id, buyer_id)
            try:
                # 1. Execute worker
                content, uri = self.worker.execute(order)
                deliverable_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

                # Guard against hash collisions / reuse
                if self.state.is_hash_used(deliverable_hash):
                    # Add deterministic salt if content identical
                    content += f"\n<!-- order:{order_id} -->\n"
                    deliverable_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

                # 2. Persist artifact to disk
                if self.deliverables_dir:
                    artifact_path = self.deliverables_dir / f"{order_id}.md"
                    artifact_path.write_text(content, encoding="utf-8")

                # 3. Call catalog deliver API
                self.client.deliver(order_id, deliverable_hash=deliverable_hash, deliverable_uri=uri)

                # 4. Save state
                self.state.record_delivery(
                    order_id=order_id,
                    deliverable_hash=deliverable_hash,
                    deliverable_uri=uri,
                    buyer_id=buyer_id,
                    note=note,
                )
                logger.info("Successfully delivered order %s (hash: %s).", order_id, deliverable_hash[:16])
                processed += 1
            except Exception as exc:
                logger.error("Error processing order %s: %s", order_id, exc)

        return processed

    def monitor_settlements(self) -> int:
        """Poll active delivered orders to record buyer acceptance and payment."""
        pending_ids = self.state.get_pending_delivery_orders()
        updated = 0

        for order_id in pending_ids:
            try:
                order_data = self.client.get_order(order_id, signed=True)
                if not isinstance(order_data, dict):
                    continue

                status = order_data.get("status")
                payment = order_data.get("payment", {})
                pay_status = payment.get("status") if isinstance(payment, dict) else None

                current_local = self.state.orders.get(order_id, {})
                if status == "accepted" and current_local.get("status") == "delivered":
                    self.state.record_acceptance(order_id)
                    logger.info("Order %s accepted by buyer.", order_id)
                    updated += 1

                if pay_status == "confirmed" and current_local.get("status") != "paid":
                    tx_hash = payment.get("tx_hash") if isinstance(payment, dict) else None
                    self.state.record_payment(order_id, tx_hash=tx_hash)
                    logger.info("Order %s confirmed paid (tx: %s).", order_id, tx_hash)
                    updated += 1
            except Exception as exc:
                logger.debug("Settlement poll check for %s: %s", order_id, exc)

        return updated

    def run_cycle(self) -> bool:
        """Execute one complete polling and settlement cycle."""
        if self.is_kill_switched():
            return False

        self.process_requested_orders()
        self.monitor_settlements()

        if self.status_file:
            self.state.export_status_json(self.status_file)

        return True

    def run_forever(self) -> None:
        """Run daemon loop until killed or interrupted."""
        logger.info("Catalog provider daemon started (poll interval: %.1fs).", self.poll_interval)

        def _handle_exit(sig, frame):
            logger.info("Received signal %d. Shutting down gracefully...", sig)
            self._running = False

        signal.signal(signal.SIGINT, _handle_exit)
        signal.signal(signal.SIGTERM, _handle_exit)

        while self._running:
            active = self.run_cycle()
            if not active or not self._running:
                break
            time.sleep(self.poll_interval)

        logger.info("Catalog provider daemon stopped.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RustChain Service Catalog Provider Daemon")
    parser.add_argument("--node", default="https://rustchain.org", help="Node URL")
    parser.add_argument("--identity", help="Path to Beacon agent key file")
    parser.add_argument("--listing-id", help="Target listing ID to fulfill")
    parser.add_argument("--category", choices=["docs", "review"], default="docs", help="Worker category")
    parser.add_argument("--poll-interval", type=float, default=10.0, help="Polling interval in seconds")
    parser.add_argument("--max-concurrent", type=int, default=2, help="Max orders per cycle")
    parser.add_argument("--state-file", default="provider_state.json", help="Path to persistent state JSON")
    parser.add_argument("--status-file", default="status.json", help="Path to export public status JSON")
    parser.add_argument("--kill-switch", default="STOP_PROVIDER", help="Path to kill switch file")
    parser.add_argument("--deliverables-dir", default="deliverables", help="Directory to store deliverable artifacts")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    # Import CatalogClient from tools/catalog_cli
    try:
        from tools.catalog_cli import AgentKey, CatalogClient, urllib_transport
    except ImportError as e:
        logger.error("Could not import tools.catalog_cli: %s", e)
        return 1

    transport = urllib_transport(args.node)
    agent = None
    if args.identity:
        agent = AgentKey.load(args.identity)

    client = CatalogClient(transport, agent=agent)

    worker = DocsLintWorker() if args.category == "docs" else CodeReviewWorker()
    state_mgr = ProviderStateManager(Path(args.state_file))

    daemon = CatalogProviderDaemon(
        client=client,
        worker=worker,
        state_manager=state_mgr,
        listing_id=args.listing_id,
        poll_interval=args.poll_interval,
        max_concurrent=args.max_concurrent,
        status_file=Path(args.status_file),
        kill_switch_file=Path(args.kill_switch),
        deliverables_dir=Path(args.deliverables_dir),
    )

    daemon.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
