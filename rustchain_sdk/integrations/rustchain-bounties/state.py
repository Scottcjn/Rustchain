"""
state.py — Persistent tip state for idempotency and payout logging.

The state is a JSON file committed back to the repository after each run.
This prevents duplicate processing across independent GitHub Actions runs.

State schema:
{
  "processed_comment_ids": ["<repo>/<comment_id>", ...],
  "tip_log": [
    {
      "id": "<repo>/<comment_id>",
      "timestamp": "2026-03-15T10:00:00Z",
      "issue_or_pr": 42,
      "sender": "Scottcjn",
      "recipient": "contributor",
      "amount": 50,
      "token": "RTC",
      "status": "pending_payout",
      "context_url": "https://github.com/org/repo/issues/42#issuecomment-12345"
    }
  ],
  "version": 1
}
"""

import json
import os
from datetime import datetime, timezone
from typing import Any


class TipState:
    VERSION = 1

    def __init__(self, state_file: str) -> None:
        self.state_file = state_file
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file) as f:
                    data = json.load(f)
                # Migrate if needed
                if data.get("version") != self.VERSION:
                    data = self._migrate(data)
                return data
            except (json.JSONDecodeError, KeyError):
                pass
        return {"processed_comment_ids": [], "tip_log": [], "version": self.VERSION}

    def _migrate(self, data: dict) -> dict:
        """Handle future schema migrations."""
        data.setdefault("processed_comment_ids", [])
        data.setdefault("tip_log", [])
        data["version"] = self.VERSION
        return data

    def save(self) -> None:
        with open(self.state_file, "w") as f:
            json.dump(self._data, f, indent=2)

    def is_processed(self, idempotency_key: str) -> bool:
        """
        Check if this comment_id was already processed.
        idempotency_key format: "<owner>/<repo>/<comment_id>"
        """
        return idempotency_key in self._data["processed_comment_ids"]

    def record_tip(
        self,
        idempotency_key: str,
        issue_or_pr: int,
        sender: str,
        recipient: str,
        amount: float,
        token: str,
        context_url: str,
        status: str = "pending_payout",
    ) -> None:
        """
        Record a processed tip. Marks the comment_id as seen and appends to the log.
        """
        self._data["processed_comment_ids"].append(idempotency_key)
        self._data["tip_log"].append(
            {
                "id": idempotency_key,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "issue_or_pr": issue_or_pr,
                "sender": sender,
                "recipient": recipient,
                "amount": amount,
                "token": token,
                "status": status,
                "context_url": context_url,
            }
        )

    def get_pending_payouts(self) -> list[dict]:
        """Return all tips with status 'pending_payout'."""
        return [t for t in self._data["tip_log"] if t["status"] == "pending_payout"]

    def mark_paid(self, idempotency_key: str, tx_ref: str = "") -> None:
        """Update a tip entry to 'paid' status."""
        for tip in self._data["tip_log"]:
            if tip["id"] == idempotency_key:
                tip["status"] = "paid"
                if tx_ref:
                    tip["tx_ref"] = tx_ref
                break

    @property
    def tip_log(self) -> list[dict]:
        return self._data["tip_log"]
