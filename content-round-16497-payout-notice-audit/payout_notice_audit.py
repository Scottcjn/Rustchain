# SPDX-License-Identifier: MIT
"""Conservative offline preflight checks for RustChain payout notices."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


AUTHORIZED_AUTHORS = {"Scottcjn", "sophiaeagent-beep", "AutoJanitor"}
AUTHORIZED_AUTHOR_KEYS = {author.casefold() for author in AUTHORIZED_AUTHORS}
FIELD_PATTERNS = {
    "amount": re.compile(r"(?i)\b(?:amount|payout)\s*[:=]\s*([^\s,;]+)"),
    "wallet": re.compile(r"(?i)\b(?:recipient|wallet)\s*[:=]\s*([^\s,;]+)"),
    "pending_id": re.compile(r"(?i)\bpending_id\s*[:=]\s*([^\s,;]+)"),
    "tx_hash": re.compile(r"(?i)\btx_hash\s*[:=]\s*([^\s,;]+)"),
    "confirms_at": re.compile(r"(?i)\bconfirms_at\s*[:=]\s*([^\s,;]+)"),
}


def extract_fields(body: str) -> dict[str, str]:
    """Extract documented payout fields without interpreting their values."""
    fields: dict[str, str] = {}
    for name, pattern in FIELD_PATTERNS.items():
        match = pattern.search(body)
        if match:
            fields[name] = match.group(1)
    return fields


def audit_notice(notice: dict[str, Any]) -> dict[str, Any]:
    """Classify one notice for manual follow-up, never as settled payment."""
    if not isinstance(notice, dict):
        raise ValueError("each notice must be a JSON object")
    author = str(notice.get("author", ""))
    body = str(notice.get("body", ""))
    fields = extract_fields(body)
    missing = [name for name in FIELD_PATTERNS if name not in fields]

    if author.casefold() not in AUTHORIZED_AUTHOR_KEYS:
        status = "reject_unauthorized_author"
    elif missing:
        status = "hold_missing_fields"
    else:
        status = "ready_for_project_record_verification"

    return {
        "author": author,
        "status": status,
        "fields": fields,
        "missing": missing,
        "settled": False,
    }


def audit_file(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("input must be a JSON array of notice objects")
    return [audit_notice(item) for item in payload]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON array containing author/body notices")
    args = parser.parse_args()
    print(json.dumps(audit_file(args.input), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
