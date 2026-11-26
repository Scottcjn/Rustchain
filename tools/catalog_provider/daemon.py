#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Unattended RTC service catalog provider daemon.

Reuses ``tools/catalog_cli.py``'s ``AgentKey``, ``CatalogClient``,
``CatalogError``, ``urllib_transport`` and ``sha256_file`` so request signing
and key loading stay identical to the CLI.
"""

from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional

from .workers import CodeReviewWorker, DocsLintWorker, WorkResult, Worker

ROOT = Path(__file__).resolve().parents[2]
_HEX_SECRET_RE = re.compile(r"\b[0-9a-fA-F]{64}\b")


def load_catalog_cli():
    """Load ``tools/catalog_cli.py`` from the repository tree (cached in sys.modules)."""
    existing = sys.modules.get("rustchain_catalog_cli")
    if existing is not None:
        return existing
    path = ROOT / "tools" / "catalog_cli.py"
    spec = importlib.util.spec_from_file_location("rustchain_catalog_cli", path)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["rustchain_catalog_cli"] = module
    spec.loader.exec_module(module)
    return module


catalog_cli = load_catalog_cli()
AgentKey = catalog_cli.AgentKey
CatalogClient = catalog_cli.CatalogClient
CatalogError = catalog_cli.CatalogError
urllib_transport = catalog_cli.urllib_transport
sha256_file = catalog_cli.sha256_file
CATEGORIES = catalog_cli.CATEGORIES


class KillSwitchActive(RuntimeError):
    """Raised when the configured kill-switch file is present."""


class RateLimitExceeded(RuntimeError):
    """Raised when the local order fulfillment rate limit is reached."""


class _SecretRedactingFilter(logging.Filter):
    """Guarantees no 64-hex private key seed or secret is ever emitted to logs."""

    def __init__(self, forbidden_tokens: Optional[List[str]] = None):
        super().__init__()
        self._tokens = [t for t in (forbidden_tokens or []) if t and len(t) >= 16]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        redacted = _HEX_SECRET_RE.sub("<redacted-hex>", msg)
        for tok in self._tokens:
            if tok in redacted:
                redacted = redacted.replace(tok, "<redacted-key>")
        if redacted != msg:
            record.msg = redacted
            record.args = ()
        return True


@dataclass
class ProviderConfig:
    """Configuration for :class:`ProviderDaemon`."""

    state_dir: Path
    category: str = "review"
    listing_id: Optional[str] = None
    max_concurrent_orders: int = 2
    max_orders_per_minute: int = 10
    kill_switch_path: Optional[Path] = None
    deliverable_base_uri: Optional[str] = None
    poll_interval_s: float = 15.0
    clock: Callable[[], float] = field(default=time.time)

    def __post_init__(self) -> None:
        self.state_dir = Path(self.state_dir).expanduser().resolve()
        if self.category not in CATEGORIES:
            raise ValueError(f"category must be one of {CATEGORIES}, got {self.category!r}")
        if self.max_concurrent_orders < 1:
            raise ValueError("max_concurrent_orders must be >= 1")
        if self.max_orders_per_minute < 1:
            raise ValueError("max_orders_per_minute must be >= 1")
        if self.kill_switch_path is None:
            self.kill_switch_path = self.state_dir / "KILL"
        else:
            self.kill_switch_path = Path(self.kill_switch_path).expanduser().resolve()

    @property
    def state_file(self) -> Path:
        return self.state_dir / "state.json"

    @property
    def status_file(self) -> Path:
        return self.state_dir / "status.json"

    @property
    def deliverables_dir(self) -> Path:
        return self.state_dir / "deliverables"


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


class ProviderDaemon:
    """Unattended service catalog provider daemon.

    Responsibilities:
    1. Poll ``GET /catalog/orders?role=provider&status=requested`` for orders
       matching the configured ``listing_id`` or ``category``.
    2. Run the pluggable :class:`Worker`, compute the deliverable's SHA-256,
       call ``POST /catalog/orders/<id>/deliver``, and persist state on disk
       so restarts never double-deliver.
    3. Poll ``GET /catalog/orders/<id>`` for delivered/accepted orders until
       payment is ``confirmed`` on-chain, log confirmation, and write
       ``status.json`` with work counts only (never RTC volume totals).
    """

    def __init__(
        self,
        client: Any,
        worker: Worker,
        config: ProviderConfig,
        logger: Optional[logging.Logger] = None,
    ):
        if getattr(client, "agent", None) is None:
            raise ValueError("CatalogClient must be initialized with an AgentKey identity")
        self.client = client
        self.worker = worker
        self.config = config
        self.config.state_dir.mkdir(parents=True, exist_ok=True)
        self.config.deliverables_dir.mkdir(parents=True, exist_ok=True)

        self.logger = logger or logging.getLogger(f"catalog_provider.{self.agent_id}")
        self.logger.setLevel(logging.INFO)
        # Ensure private key material can never leak even if someone passes a
        # custom log message.
        self._install_redaction_filter()

        self._delivery_timestamps: Deque[float] = collections.deque()
        self._listing_category_cache: Dict[str, str] = {}
        self.state: Dict[str, Any] = self._load_state()
        self._write_status()

    @property
    def agent_id(self) -> str:
        return str(self.client.agent.agent_id)

    def _install_redaction_filter(self) -> None:
        self.logger.filters = [
            f for f in self.logger.filters if not isinstance(f, _SecretRedactingFilter)
        ]
        self.logger.addFilter(_SecretRedactingFilter())

    def __repr__(self) -> str:
        return (
            f"ProviderDaemon(agent_id={self.agent_id!r}, "
            f"category={self.config.category!r}, "
            f"listing_id={self.config.listing_id!r})"
        )

    # ------------------------------------------------------------------
    # Disk state & status.json
    # ------------------------------------------------------------------

    def _load_state(self) -> Dict[str, Any]:
        if not self.config.state_file.exists():
            return {
                "version": 1,
                "agent_id": self.agent_id,
                "orders": {},
                "used_hashes": [],
            }
        try:
            raw = json.loads(self.config.state_file.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("state.json is not a JSON object")
            raw.setdefault("version", 1)
            raw["agent_id"] = self.agent_id
            raw.setdefault("orders", {})
            raw.setdefault("used_hashes", [])
            return raw
        except (OSError, ValueError) as exc:
            self.logger.warning("corrupted state.json (%s); starting fresh state", exc)
            return {
                "version": 1,
                "agent_id": self.agent_id,
                "orders": {},
                "used_hashes": [],
            }

    def _save_state(self) -> None:
        _atomic_write_json(self.config.state_file, self.state)
        self._write_status()

    def build_status_summary(self) -> Dict[str, Any]:
        """Compute ``status.json`` metrics (counts only, zero RTC totals)."""
        orders: Dict[str, Dict[str, Any]] = self.state.get("orders", {})
        delivered_ids = []
        accepted_ids = []
        paid_ids = []
        rejected_ids = []
        cancelled_ids = []

        buyers_delivered = set()
        buyers_accepted = set()
        buyers_paid = set()

        for oid, rec in orders.items():
            st = rec.get("status")
            pay_st = rec.get("payment_state")
            buyer = rec.get("buyer")
            if st in ("delivered", "accepted", "paid", "rejected"):
                delivered_ids.append(oid)
                if buyer:
                    buyers_delivered.add(buyer)
            if st in ("accepted", "paid") or pay_st in ("pending", "confirmed"):
                accepted_ids.append(oid)
                if buyer:
                    buyers_accepted.add(buyer)
            if st == "paid" or pay_st == "confirmed":
                paid_ids.append(oid)
                if buyer:
                    buyers_paid.add(buyer)
            if st == "rejected":
                rejected_ids.append(oid)
            if st == "cancelled":
                cancelled_ids.append(oid)

        return {
            "agent_id": self.agent_id,
            "category": self.config.category,
            "listing_id": self.config.listing_id,
            "orders_delivered": len(delivered_ids),
            "orders_accepted": len(accepted_ids),
            "orders_paid": len(paid_ids),
            "orders_rejected": len(rejected_ids),
            "orders_cancelled": len(cancelled_ids),
            "distinct_buyers_delivered": len(buyers_delivered),
            "distinct_buyers_accepted": len(buyers_accepted),
            "distinct_buyers_paid": len(buyers_paid),
            "updated_at": int(self.config.clock()),
        }

    def _write_status(self) -> Dict[str, Any]:
        summary = self.build_status_summary()
        _atomic_write_json(self.config.status_file, summary)
        return summary

    # ------------------------------------------------------------------
    # Safety checks
    # ------------------------------------------------------------------

    def check_kill_switch(self) -> None:
        if self.config.kill_switch_path and self.config.kill_switch_path.exists():
            raise KillSwitchActive(
                f"kill switch active at {self.config.kill_switch_path}; halting provider"
            )

    def _allow_delivery_now(self) -> bool:
        now = float(self.config.clock())
        window_start = now - 60.0
        while self._delivery_timestamps and self._delivery_timestamps[0] < window_start:
            self._delivery_timestamps.popleft()
        return len(self._delivery_timestamps) < self.config.max_orders_per_minute

    def _record_delivery_timestamp(self) -> None:
        self._delivery_timestamps.append(float(self.config.clock()))

    # ------------------------------------------------------------------
    # Listing / Order Filtering
    # ------------------------------------------------------------------

    def _order_matches_scope(self, order: Dict[str, Any]) -> bool:
        if order.get("provider") and order.get("provider") != self.agent_id:
            return False
        if order.get("buyer") == self.agent_id:
            # Never fulfill self-orders.
            return False
        listing_id = str(order.get("listing_id", ""))
        if self.config.listing_id and listing_id != self.config.listing_id:
            return False
        if not self.config.listing_id and listing_id:
            cat = self._listing_category(listing_id)
            if cat and cat != self.config.category:
                return False
        return True

    def _listing_category(self, listing_id: str) -> Optional[str]:
        if listing_id in self._listing_category_cache:
            return self._listing_category_cache[listing_id]
        try:
            info = self.client.listing(listing_id)
            cat = info.get("category") if isinstance(info, dict) else None
            if isinstance(cat, str):
                self._listing_category_cache[listing_id] = cat
                return cat
        except CatalogError:
            return None
        return None

    # ------------------------------------------------------------------
    # Fulfillment & Idempotent Delivery
    # ------------------------------------------------------------------

    def fulfill_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Fulfill and deliver a single ``requested`` order idempotently."""
        self.check_kill_switch()
        order_id = str(order["id"])
        orders_map: Dict[str, Dict[str, Any]] = self.state.setdefault("orders", {})
        existing = orders_map.get(order_id)

        # 1. Local idempotency guard: never re-deliver an order already marked
        # delivered, accepted, paid, rejected or cancelled on disk.
        if existing and existing.get("status") in (
            "delivered",
            "accepted",
            "paid",
            "rejected",
            "cancelled",
        ):
            self.logger.info("order %s already in state %s; skipping delivery", order_id, existing["status"])
            return existing

        # 2. Server reconciliation before work: if a previous run delivered to
        # the node right before a crash, sync state from the server instead of
        # re-running or double-delivering.
        latest = self.client.get_order(order_id, signed=True)
        server_status = latest.get("status")
        if server_status != "requested":
            rec = self._sync_record_from_server(latest, existing)
            self._save_state()
            return rec

        if not self._allow_delivery_now():
            raise RateLimitExceeded(
                f"rate limit ({self.config.max_orders_per_minute}/min) reached; deferring {order_id}"
            )

        out_dir = self.config.deliverables_dir / order_id
        used_hashes = set(self.state.get("used_hashes", []))

        # Reuse pre-computed artifact if a crash occurred between worker run and /deliver
        attempt = 1
        result: Optional[WorkResult] = None
        digest: Optional[str] = None
        if (
            existing
            and existing.get("status") == "working"
            and existing.get("deliverable_path")
            and Path(existing["deliverable_path"]).exists()
        ):
            cand_path = Path(existing["deliverable_path"])
            cand_hash = sha256_file(str(cand_path))
            if cand_hash not in used_hashes:
                result = WorkResult(
                    artifact_path=cand_path,
                    deliverable_uri=existing.get("deliverable_uri"),
                    summary=existing.get("summary", ""),
                )
                digest = cand_hash

        while True:
            self.check_kill_switch()
            if result is None or digest is None:
                result = self.worker.fulfill(
                    latest,
                    out_dir,
                    attempt=attempt,
                    base_uri=self.config.deliverable_base_uri,
                )
                digest = sha256_file(str(result.artifact_path))
                if digest in used_hashes:
                    attempt += 1
                    result = None
                    digest = None
                    continue

            # Persist "working" checkpoint before calling /deliver
            orders_map[order_id] = {
                "order_id": order_id,
                "listing_id": latest.get("listing_id"),
                "buyer": latest.get("buyer"),
                "status": "working",
                "deliverable_path": str(result.artifact_path),
                "deliverable_hash": digest,
                "deliverable_uri": result.deliverable_uri,
                "summary": result.summary,
                "payment_state": "unpaid",
                "payment_tx_hash": None,
                "updated_at": int(self.config.clock()),
            }
            self._save_state()

            try:
                delivered = self.client.deliver(order_id, digest, result.deliverable_uri)
                self._record_delivery_timestamp()
                used_hashes.add(digest)
                self.state["used_hashes"] = sorted(used_hashes)
                rec = self._sync_record_from_server(delivered, orders_map[order_id])
                self._save_state()
                self.logger.info(
                    "delivered order %s for buyer %s (sha256=%s)",
                    order_id,
                    rec.get("buyer"),
                    digest,
                )
                return rec
            except CatalogError as exc:
                msg = str(exc).lower()
                if exc.status == 409 and "deliverable_hash" in msg and attempt < 5:
                    self.logger.warning(
                        "deliverable_hash collision on %s (attempt %d); regenerating",
                        order_id,
                        attempt,
                    )
                    used_hashes.add(digest)
                    self.state["used_hashes"] = sorted(used_hashes)
                    attempt += 1
                    result = None
                    digest = None
                    continue
                if exc.status == 409:
                    refreshed = self.client.get_order(order_id, signed=True)
                    rec = self._sync_record_from_server(refreshed, orders_map[order_id])
                    self._save_state()
                    return rec
                raise

    def _sync_record_from_server(
        self, server_order: Dict[str, Any], prev: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        order_id = str(server_order["id"])
        prev = prev or self.state.get("orders", {}).get(order_id, {})
        server_status = str(server_order.get("status", prev.get("status", "requested")))
        payment = server_order.get("payment") if isinstance(server_order.get("payment"), dict) else {}
        pay_state = str(payment.get("state") or prev.get("payment_state") or "unpaid")
        pay_tx = payment.get("tx_hash") or prev.get("payment_tx_hash")

        effective_status = "paid" if pay_state == "confirmed" else server_status
        rec = {
            "order_id": order_id,
            "listing_id": server_order.get("listing_id", prev.get("listing_id")),
            "buyer": server_order.get("buyer", prev.get("buyer")),
            "status": effective_status,
            "deliverable_path": prev.get("deliverable_path"),
            "deliverable_hash": server_order.get("deliverable_hash") or prev.get("deliverable_hash"),
            "deliverable_uri": server_order.get("deliverable_uri") or prev.get("deliverable_uri"),
            "summary": prev.get("summary", ""),
            "payment_state": pay_state,
            "payment_tx_hash": pay_tx,
            "updated_at": int(self.config.clock()),
        }
        self.state.setdefault("orders", {})[order_id] = rec
        if rec["deliverable_hash"]:
            hashes = set(self.state.get("used_hashes", []))
            hashes.add(rec["deliverable_hash"])
            self.state["used_hashes"] = sorted(hashes)
        return rec

    # ------------------------------------------------------------------
    # Payment Watching & Poll Cycle
    # ------------------------------------------------------------------

    def watch_payments(self) -> List[Dict[str, Any]]:
        """Poll tracked orders that have been delivered/accepted until payment is confirmed."""
        self.check_kill_switch()
        newly_confirmed: List[Dict[str, Any]] = []
        orders_map: Dict[str, Dict[str, Any]] = self.state.get("orders", {})

        # Also discover any accepted/delivered orders on the server not yet in local state
        for status_filter in ("delivered", "accepted"):
            try:
                inbox = self.client.my_orders(role="provider", status=status_filter)
                for item in inbox.get("orders", []):
                    oid = item.get("id")
                    if oid and oid not in orders_map and self._order_matches_scope(item):
                        self._sync_record_from_server(item)
            except CatalogError as exc:
                self.logger.warning("failed polling provider %s inbox: %s", status_filter, exc)

        for order_id, rec in list(orders_map.items()):
            self.check_kill_switch()
            if rec.get("payment_state") == "confirmed" or rec.get("status") in (
                "paid",
                "rejected",
                "cancelled",
            ):
                continue
            try:
                latest = self.client.get_order(order_id, signed=True)
            except CatalogError as exc:
                self.logger.warning("could not refresh order %s: %s", order_id, exc)
                continue

            was_confirmed = rec.get("payment_state") == "confirmed"
            updated = self._sync_record_from_server(latest, rec)
            if not was_confirmed and updated.get("payment_state") == "confirmed":
                self.logger.info(
                    "payment CONFIRMED for order %s from buyer %s (tx_hash=%s, memo=svc:%s)",
                    order_id,
                    updated.get("buyer"),
                    updated.get("payment_tx_hash"),
                    order_id,
                )
                newly_confirmed.append(updated)

        self._save_state()
        return newly_confirmed

    def run_once(self) -> Dict[str, Any]:
        """Run one full provider tick: fulfill requested orders + watch payments."""
        self.check_kill_switch()
        inbox = self.client.my_orders(role="provider", status="requested")
        requested_orders = [
            o for o in inbox.get("orders", []) if isinstance(o, dict) and self._order_matches_scope(o)
        ]
        # Oldest requested orders first for fair FIFO fulfillment
        requested_orders.sort(key=lambda o: (o.get("created_at", 0), o.get("id", "")))

        delivered_this_tick: List[str] = []
        for order in requested_orders[: self.config.max_concurrent_orders]:
            self.check_kill_switch()
            if not self._allow_delivery_now():
                self.logger.warning("rate limit reached; remaining orders deferred to next tick")
                break
            rec = self.fulfill_order(order)
            if rec.get("status") in ("delivered", "accepted", "paid"):
                delivered_this_tick.append(str(order["id"]))

        confirmed_this_tick = self.watch_payments()
        status_summary = self._write_status()
        return {
            "delivered_order_ids": delivered_this_tick,
            "confirmed_order_ids": [r["order_id"] for r in confirmed_this_tick],
            "status": status_summary,
        }

    def run_forever(self, max_ticks: Optional[int] = None) -> None:
        """Poll and fulfill orders in a loop until interrupted or kill-switched.

        Transient transport or HTTP errors are logged and retried on the next
        polling interval so an unattended daemon survives temporary proxy or
        node timeouts, while :class:`KillSwitchActive` halts immediately.
        """
        ticks = 0
        while max_ticks is None or ticks < max_ticks:
            self.check_kill_switch()
            try:
                self.run_once()
            except KillSwitchActive:
                raise
            except (CatalogError, OSError) as exc:
                self.logger.warning("transient poll error on tick %d: %s", ticks, exc)
            ticks += 1
            if max_ticks is not None and ticks >= max_ticks:
                break
            time.sleep(self.config.poll_interval_s)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="catalog_provider",
        description="Unattended RTC service catalog provider daemon.",
    )
    parser.add_argument(
        "--node",
        default=os.environ.get("RUSTCHAIN_NODE", catalog_cli.DEFAULT_NODE),
        help="RustChain node URL",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="skip TLS verification (for self-signed node IP)",
    )
    parser.add_argument(
        "--identity",
        help="Beacon agent key file (default $BEACON_IDENTITY_PATH or ~/.beacon/identity/agent.key)",
    )
    parser.add_argument(
        "--category",
        choices=CATEGORIES,
        default="review",
        help="service category to serve (default: review)",
    )
    parser.add_argument(
        "--listing-id",
        help="restrict fulfillment to a specific listing_id (lst_...)",
    )
    parser.add_argument(
        "--worker",
        choices=("review", "docs"),
        default="review",
        help="built-in worker implementation to run (default: review)",
    )
    parser.add_argument(
        "--repo-root",
        help="optional default repository/docs root for local inspection",
    )
    parser.add_argument(
        "--state-dir",
        default=str(Path.home() / ".rustchain" / "catalog_provider"),
        help="directory for state.json, status.json, and deliverables/",
    )
    parser.add_argument(
        "--kill-switch",
        help="path to kill-switch file (default: <state-dir>/KILL)",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=2,
        help="maximum orders to fulfill per polling cycle (default: 2)",
    )
    parser.add_argument(
        "--rate-limit",
        type=int,
        default=10,
        help="maximum order deliveries per minute (default: 10)",
    )
    parser.add_argument(
        "--base-uri",
        help="optional https:// base URI prefix for published deliverables",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=15.0,
        help="polling interval in seconds when running continuously (default: 15)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="run one poll/fulfill/watch cycle and exit",
    )
    return parser


def main(argv: Optional[List[str]] = None, transport: Optional[Any] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        agent = AgentKey.load(args.identity)
        send = transport or urllib_transport(args.node, insecure=args.insecure)
        client = CatalogClient(send, agent)

        root_path = Path(args.repo_root).resolve() if args.repo_root else ROOT
        worker: Worker
        if args.worker == "docs" or args.category == "docs":
            worker = DocsLintWorker(docs_root=root_path)
        else:
            worker = CodeReviewWorker(repo_root=root_path)

        config = ProviderConfig(
            state_dir=Path(args.state_dir),
            category=args.category,
            listing_id=args.listing_id,
            max_concurrent_orders=args.max_concurrent,
            max_orders_per_minute=args.rate_limit,
            kill_switch_path=Path(args.kill_switch) if args.kill_switch else None,
            deliverable_base_uri=args.base_uri,
            poll_interval_s=args.interval,
        )
        daemon = ProviderDaemon(client=client, worker=worker, config=config)
        if args.once:
            result = daemon.run_once()
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            daemon.run_forever()
    except KillSwitchActive as exc:
        print(f"halted: {exc}", file=sys.stderr)
        return 2
    except CatalogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
