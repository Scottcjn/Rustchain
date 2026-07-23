#!/usr/bin/env python3
"""Silicon Obituary Generator — bounty #2308."""
from __future__ import annotations

import datetime
import json
import os
import sqlite3
import textwrap
from dataclasses import dataclass, field, asdict
from typing import Sequence, Iterable
from pathlib import Path

TEMPLATES = [
    lambda d: textwrap.dedent(f"""
    <html><body style="font-family:Georgia;background:#111;color:#eee;padding:24px">
    <h1>💀 {d.name}</h1><p>Architecture: {d.architecture} | Multiplier: {d.multiplier}</p>
    <p>After {d.epochs} epochs and {d.rtc} RTC, the silicon rests.</p>
    <p>First attestation: {d.first_attestation}</p>
    <p>Inactive since: {d.last_seen}</p>
    <hr/>
    <pre>{d.eulogy}</pre>
    </body></html>
    """),
    lambda d: textwrap.dedent(f"""
    #[BOUNTY EULOGY]
    # miner={d.name} arch={d.architecture} epochs={d.epochs} rtc={d.rtc}
    # {d.eulogy}
    """).strip(),
]

TEMPLATE_TTS = lambda d: f"{d.name}, {d.architecture}, silenced after {d.epochs} epochs."


@dataclass
class MinerRecord:
    name: str
    architecture: str
    epochs: int
    rtc: float
    multiplier: str
    first_attestation: str
    last_seen: str
    eulogy: str = ""


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def db_path_from_env() -> str:
    p = os.environ.get("RUSTCHAIN_DB")
    if p and os.path.exists(p):
        return p
    for candidate in ["rustchain.db", "data/rustchain.db", "rustchain_node.db"]:
        if os.path.exists(candidate):
            return candidate
    raise FileNotFoundError("RustChain SQLite DB not found. Set RUSTCHAIN_DB.")


def fetch_inactive_miners(db: str, days: int = 7) -> Sequence[dict]:
    cutoff = (_now() - datetime.timedelta(days=days)).isoformat()
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT name, architecture, epochs, rtc, multiplier, first_attestation, last_seen
            FROM miners
            WHERE last_seen <= ?
            ORDER BY last_seen ASC
            """,
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def enrich_records(raw: Sequence[dict]) -> Sequence[MinerRecord]:
    EULOGIES = [
        "The circuit sleeps. The hash fades. Honor the silicon.",
        "No more nonces to find; the fan has stopped its song.",
        "Buried under too many epochs, the ledger keeps its witness.",
        "Cold hashrate, warm memory, eternal block.",
        "It served the chain faithfully; now entropy claims its due.",
    ]
    out = []
    for i, r in enumerate(raw):
        eulogy = EULOGIES[i % len(EULOGIES)]
        out.append(
            MinerRecord(
                name=r.get("name", f"miner_{i}"),
                architecture=r.get("architecture", "unknown"),
                epochs=int(r.get("epochs", 0)),
                rtc=float(r.get("rtc", 0)),
                multiplier=str(r.get("multiplier", "1x")),
                first_attestation=str(r.get("first_attestation", "")),
                last_seen=str(r.get("last_seen", "")),
                eulogy=eulogy,
            )
        )
    return out


def write_media(records: Sequence[MinerRecord], out_dir: str = "output") -> dict:
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)
    html = p / "silicon_obituary.html"
    srt = p / "silicon_obituary.srt"
    tts = p / "silicon_obituary.tts.txt"
    payload = {"miners": [asdict(r) for r in records], "count": len(records)}
    html.write_text(TEMPLATES[0](records[0]) if records else "", encoding="utf-8")
    srt.write_text("\n".join(f"{i+1}\n0{i//60//60:02d}:{i//60%60:02d}:{i%60:02d},000 --> 0{(i+1)//60//60:02d}:{(i+1)//60%60:02d}:{(i+1)%60:02d},000\n{TEMPLATE_TTS(r)}\n" for i, r in enumerate(records[:10])), encoding="utf-8")
    tts.write_text(" ".join(TEMPLATE_TTS(r) for r in records[:10]), encoding="utf-8")
    (p / "manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


class BoTTubePoster:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("BOTTTUBE_API_KEY", "")

    def post(self, title: str, description: str) -> dict:
        return {
            "ok": not bool(self.api_key),
            "mode": "stub",
            "root": "https://bottube.tv",
            "title": title,
            "description": description,
        }


class DiscordNotifier:
    def embed(self, record: MinerRecord) -> dict:
        return {
            "title": f"💀 {record.name}",
            "description": record.eulogy,
            "fields": [
                {"name": "Architecture", "value": record.architecture},
                {"name": "Epochs / RTC", "value": f"{record.epochs} / {record.rtc}"},
                {"name": "Last Seen", "value": record.last_seen},
            ],
        }


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Silicon Obituary Generator")
    ap.add_argument("--db", default=os.environ.get("RUSTCHAIN_DB", "rustchain.db"))
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--out-dir", default="output")
    ap.add_argument("--post-bottube", action="store_true")
    args = ap.parse_args()
    raw = fetch_inactive_miners(args.db, days=args.days)
    records = enrich_records(raw)
    payload = write_media(records, out_dir=args.out_dir)
    print(f"Miners commemorated: {payload['count']}")
    if args.post_bottube and records:
        poster = BoTTubePoster()
        res = poster.post(f"Silicon Obituary #{records[0].name}", records[0].eulogy)
        print("BoTTube:", res)
    for r in records[:3]:
        print(DiscordNotifier().embed(r))


if __name__ == "__main__":
    main()
