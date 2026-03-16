"""Core monitoring logic: poll API, detect conditions, fire alerts."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from .api import MinerInfo, RustChainClient, WalletBalance
from .config import AlertThresholds, AppConfig
from .db import AlertDB
from .notifiers import EmailNotifier, NullNotifier, SmsNotifier

logger = logging.getLogger(__name__)


@dataclass
class AlertEvent:
    miner_id: str
    alert_type: str  # offline | reward | large_transfer | attest_fail
    subject: str
    message: str


class MinerMonitor:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.db = AlertDB(config.db_path)
        self.client = RustChainClient(
            base_url=config.rustchain.base_url,
            verify_ssl=config.rustchain.verify_ssl,
        )

        cfg = config.email
        self.email = (
            EmailNotifier(
                smtp_host=cfg.smtp_host,
                smtp_port=cfg.smtp_port,
                smtp_user=cfg.smtp_user,
                smtp_password=cfg.smtp_password,
                from_addr=cfg.from_addr,
                to_addrs=cfg.to_addrs,
                use_tls=cfg.use_tls,
            )
            if cfg.enabled
            else NullNotifier()
        )

        scfg = config.sms
        self.sms = (
            SmsNotifier(
                account_sid=scfg.account_sid,
                auth_token=scfg.auth_token,
                from_number=scfg.from_number,
                to_numbers=scfg.to_numbers,
            )
            if scfg.enabled
            else NullNotifier()
        )

    # ── main loop ────────────────────────────────────────────────────────────

    async def run(self) -> None:
        interval = self.config.rustchain.poll_interval_seconds
        logger.info("Monitor started — polling every %ds", interval)
        while True:
            try:
                await self._poll()
            except Exception as exc:
                logger.error("Poll error: %s", exc)
            await asyncio.sleep(interval)

    async def _poll(self) -> None:
        now = int(time.time())

        miners = await self.client.get_miners()
        watch_ids = self._resolve_watch_ids(miners)

        for miner in miners:
            if miner.miner not in watch_ids:
                continue
            await self._check_miner(miner, now)

    def _resolve_watch_ids(self, miners: list[MinerInfo]) -> set[str]:
        if self.config.miners.watch_all:
            return {m.miner for m in miners}
        return set(self.config.miners.watch_ids)

    # ── per-miner checks ─────────────────────────────────────────────────────

    async def _check_miner(self, miner: MinerInfo, now: int) -> None:
        prev = self.db.get_miner(miner.miner)

        # fetch wallet balance (may fail if miner not enrolled)
        balance: Optional[WalletBalance] = None
        try:
            balance = await self.client.wallet_balance(miner.miner)
        except Exception as exc:
            logger.debug("Balance fetch failed for %s: %s", miner.miner, exc)

        events: list[AlertEvent] = []

        # 1. Offline detection
        events.extend(self._check_offline(miner, now, prev))

        # 2. Attestation failure (entropy_score == 0.0 and miner was previously active)
        events.extend(self._check_attest_fail(miner, prev))

        # 3. Rewards received / large transfer (requires balance history)
        if balance is not None and prev and prev.get("balance_rtc") is not None:
            events.extend(
                self._check_balance_changes(miner.miner, prev["balance_rtc"], balance.amount_rtc)
            )

        # persist updated state
        self.db.upsert_miner(
            miner_id=miner.miner,
            last_attest=miner.last_attest,
            balance_rtc=balance.amount_rtc if balance else (prev or {}).get("balance_rtc"),
            offline_alerted=any(e.alert_type == "offline" for e in events)
            if any(e.alert_type == "offline" for e in events)
            else (bool(prev.get("offline_alerted")) if prev else False),
        )

        for event in events:
            self._dispatch(event)

    def _check_offline(
        self, miner: MinerInfo, now: int, prev: Optional[dict] = None
    ) -> list[AlertEvent]:
        if miner.last_attest is None:
            return []

        threshold_seconds = self.config.thresholds.offline_minutes * 60
        age = now - miner.last_attest
        is_offline = age > threshold_seconds
        was_alerted = bool(prev.get("offline_alerted")) if prev else False

        if is_offline and not was_alerted:
            if not self.db.was_alerted_recently(miner.miner, "offline", within_seconds=threshold_seconds):
                minutes_ago = age // 60
                msg = (
                    f"Miner {miner.miner} has not submitted an attestation in "
                    f"{minutes_ago} minutes (threshold: {self.config.thresholds.offline_minutes}m).\n"
                    f"Last seen: epoch ts {miner.last_attest}"
                )
                self.db.record_alert(miner.miner, "offline", msg)
                return [AlertEvent(miner.miner, "offline", f"[RustChain] Miner Offline: {miner.miner}", msg)]

        if not is_offline and was_alerted:
            # miner came back online — clear flag
            self.db.set_offline_alerted(miner.miner, False)
            back_msg = f"Miner {miner.miner} is back online."
            self.db.record_alert(miner.miner, "back_online", back_msg)
            return [AlertEvent(miner.miner, "back_online", f"[RustChain] Miner Back Online: {miner.miner}", back_msg)]

        return []

    def _check_attest_fail(
        self, miner: MinerInfo, prev: Optional[dict] = None
    ) -> list[AlertEvent]:
        """Detect stale last_attest — same timestamp as last poll = no new attestation."""
        if prev is None or miner.last_attest is None:
            return []

        prev_attest = prev.get("last_attest")
        if prev_attest is None:
            return []

        # If last_attest hasn't moved across two polls, mark as attestation failure
        if miner.last_attest == prev_attest:
            if not self.db.was_alerted_recently(miner.miner, "attest_fail", within_seconds=300):
                msg = (
                    f"Miner {miner.miner} attestation has not updated since ts {miner.last_attest}. "
                    f"Possible attestation failure."
                )
                self.db.record_alert(miner.miner, "attest_fail", msg)
                return [AlertEvent(miner.miner, "attest_fail", f"[RustChain] Attestation Failure: {miner.miner}", msg)]

        return []

    def _check_balance_changes(
        self, miner_id: str, prev_balance: float, curr_balance: float
    ) -> list[AlertEvent]:
        events: list[AlertEvent] = []
        delta = curr_balance - prev_balance

        # Rewards received (balance increased)
        if delta >= self.config.thresholds.reward_min_rtc:
            if not self.db.was_alerted_recently(miner_id, "reward", within_seconds=300):
                msg = (
                    f"Miner {miner_id} received rewards: +{delta:.4f} RTC "
                    f"(balance: {prev_balance:.4f} → {curr_balance:.4f} RTC)"
                )
                self.db.record_alert(miner_id, "reward", msg)
                events.append(AlertEvent(miner_id, "reward", f"[RustChain] Rewards Received: {miner_id}", msg))

        # Large transfer (balance dropped significantly)
        elif -delta >= self.config.thresholds.large_transfer_rtc:
            if not self.db.was_alerted_recently(miner_id, "large_transfer", within_seconds=300):
                msg = (
                    f"Miner {miner_id} large transfer detected: {delta:.4f} RTC "
                    f"(balance: {prev_balance:.4f} → {curr_balance:.4f} RTC)"
                )
                self.db.record_alert(miner_id, "large_transfer", msg, )
                events.append(AlertEvent(miner_id, "large_transfer", f"[RustChain] Large Transfer: {miner_id}", msg))

        return events

    # ── dispatch ─────────────────────────────────────────────────────────────

    def _dispatch(self, event: AlertEvent) -> None:
        logger.warning("[ALERT] %s — %s", event.alert_type.upper(), event.subject)
        logger.info(event.message)

        if self.config.email.enabled:
            self.email.send(event.subject, event.message)  # type: ignore[arg-type]

        if self.config.sms.enabled:
            self.sms.send(f"{event.subject}\n{event.message}")  # type: ignore[arg-type]

    async def aclose(self) -> None:
        await self.client.aclose()
