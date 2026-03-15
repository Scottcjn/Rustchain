#!/usr/bin/env python3
"""
RustChain Node Log Analyzer

Parses RustChain node logs and produces diagnostics including error frequency,
mining success/failure rates, attestation pass/fail tracking, peer connection
statistics, performance metrics over time, and anomaly alerts.

Supports three CLI modes:
    analyze  — one-shot analysis of a log file
    report   — generate an HTML report from a log file
    watch    — tail a log file and print live anomaly alerts
"""

import argparse
import datetime
import html
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Log line patterns
# ---------------------------------------------------------------------------

# Standard Python logging: 2025-01-15 12:34:56,789 [BFT] message
_TS_FMT_LOGGING = r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}[,\.]\d+"
# Bracket-prefix prints: [P2P] message  /  [SETTLEMENT] message
_BRACKET_TAG = r"\[([A-Z0-9_]+)\]"

RE_TIMESTAMP = re.compile(
    rf"({_TS_FMT_LOGGING})"
)
RE_LOG_LEVEL = re.compile(
    r"\b(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)\b", re.IGNORECASE
)
RE_BRACKET_TAG = re.compile(_BRACKET_TAG)

# Domain-specific patterns ---------------------------------------------------

# Mining
RE_BLOCK_MINED = re.compile(
    r"(?:block\s+(?:mined|produced|created))|(?:mined\s+block)|"
    r"(?:Block\s+#?\d+\s+(?:mined|produced))|(?:\[OK\]\s+Settled\s+epoch)",
    re.IGNORECASE,
)
RE_MINING_FAIL = re.compile(
    r"(?:mining\s+fail)|(?:block\s+rejected)|(?:invalid\s+block)|"
    r"(?:not\s+(?:my|this\s+node.s)\s+turn)|(?:block\s+production\s+error)",
    re.IGNORECASE,
)

# Attestation
RE_ATTEST_PASS = re.compile(
    r"(?:attestation\s+(?:pass|valid|verified|accepted|ok))|"
    r"(?:attest(?:ed)?(?:\s+successfully)?)|(?:hardware\s+verified)",
    re.IGNORECASE,
)
RE_ATTEST_FAIL = re.compile(
    r"(?:attestation\s+(?:fail|invalid|rejected|expired|error))|"
    r"(?:attest(?:ation)?\s+check\s+failed)|(?:hardware\s+(?:rejected|invalid))",
    re.IGNORECASE,
)

# Peer connections
RE_PEER_CONNECT = re.compile(
    r"(?:(?:added|connected|new)\s+peer)|(?:peer\s+(?:connected|added|joined))",
    re.IGNORECASE,
)
RE_PEER_DISCONNECT = re.compile(
    r"(?:peer\s+(?:disconnected|removed|lost|timed\s+out|unreachable))|"
    r"(?:(?:removed|lost)\s+peer)|(?:connection\s+(?:lost|closed|refused))",
    re.IGNORECASE,
)

# Consensus
RE_CONSENSUS = re.compile(
    r"(?:consensus|pre.prepare|prepare|commit|view.change|checkpoint)",
    re.IGNORECASE,
)

# Payout / settlement
RE_PAYOUT_OK = re.compile(
    r"(?:withdrawal.*completed)|(?:payout.*success)|(?:\[OK\].*withdrawal)",
    re.IGNORECASE,
)
RE_PAYOUT_FAIL = re.compile(
    r"(?:withdrawal.*failed)|(?:payout.*fail)|(?:settlement.*error)",
    re.IGNORECASE,
)

# Generic error extractor
RE_ERROR_MSG = re.compile(
    r"(?:error|exception|traceback|fail(?:ed|ure)?)[:\s]*(.*)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class LogStats:
    total_lines: int = 0
    first_ts: Optional[str] = None
    last_ts: Optional[str] = None

    # Severity counters
    level_counts: Dict[str, int] = field(default_factory=Counter)

    # Mining
    blocks_mined: int = 0
    mining_failures: int = 0

    # Attestation
    attestation_pass: int = 0
    attestation_fail: int = 0

    # Peers
    peer_connects: int = 0
    peer_disconnects: int = 0

    # Consensus
    consensus_events: int = 0

    # Payouts
    payout_ok: int = 0
    payout_fail: int = 0

    # Error breakdown
    error_messages: List[str] = field(default_factory=list)
    error_freq: Dict[str, int] = field(default_factory=Counter)

    # Per-minute event buckets for time-series
    events_per_minute: Dict[str, Dict[str, int]] = field(
        default_factory=lambda: defaultdict(Counter)
    )

    # Tag distribution (e.g. [BFT], [P2P], …)
    tag_counts: Dict[str, int] = field(default_factory=Counter)

    # Anomalies
    anomalies: List[Dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _extract_minute_key(ts_match: str) -> str:
    """Return 'YYYY-MM-DD HH:MM' from a timestamp string."""
    clean = ts_match.replace(",", ".").strip()
    return clean[:16]


def parse_log(path: str, *, tail: int = 0) -> LogStats:
    """
    Parse a RustChain node log file and return aggregated statistics.

    Parameters
    ----------
    path : str
        Path to the log file.
    tail : int
        If > 0, only parse the last *tail* lines (useful for watch mode).
    """
    stats = LogStats()
    lines: List[str] = []

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        if tail > 0:
            # Read all then slice — acceptable for moderate log sizes.
            lines = fh.readlines()[-tail:]
        else:
            lines = fh.readlines()

    for line in lines:
        stats.total_lines += 1
        stripped = line.strip()
        if not stripped:
            continue

        # Timestamp
        ts_match = RE_TIMESTAMP.search(stripped)
        ts_key: Optional[str] = None
        if ts_match:
            ts_str = ts_match.group(1)
            if stats.first_ts is None:
                stats.first_ts = ts_str
            stats.last_ts = ts_str
            ts_key = _extract_minute_key(ts_str)

        # Log level
        lv_match = RE_LOG_LEVEL.search(stripped)
        if lv_match:
            level = lv_match.group(1).upper()
            if level == "WARN":
                level = "WARNING"
            stats.level_counts[level] += 1

        # Bracket tags
        tag_match = RE_BRACKET_TAG.search(stripped)
        if tag_match:
            stats.tag_counts[tag_match.group(1)] += 1

        # Mining
        if RE_BLOCK_MINED.search(stripped):
            stats.blocks_mined += 1
            if ts_key:
                stats.events_per_minute[ts_key]["blocks_mined"] += 1
        if RE_MINING_FAIL.search(stripped):
            stats.mining_failures += 1
            if ts_key:
                stats.events_per_minute[ts_key]["mining_failures"] += 1

        # Attestation
        if RE_ATTEST_PASS.search(stripped):
            stats.attestation_pass += 1
        if RE_ATTEST_FAIL.search(stripped):
            stats.attestation_fail += 1

        # Peers
        if RE_PEER_CONNECT.search(stripped):
            stats.peer_connects += 1
            if ts_key:
                stats.events_per_minute[ts_key]["peer_connects"] += 1
        if RE_PEER_DISCONNECT.search(stripped):
            stats.peer_disconnects += 1
            if ts_key:
                stats.events_per_minute[ts_key]["peer_disconnects"] += 1

        # Consensus
        if RE_CONSENSUS.search(stripped):
            stats.consensus_events += 1

        # Payouts
        if RE_PAYOUT_OK.search(stripped):
            stats.payout_ok += 1
        if RE_PAYOUT_FAIL.search(stripped):
            stats.payout_fail += 1

        # Errors
        if lv_match and lv_match.group(1).upper() in ("ERROR", "CRITICAL", "FATAL"):
            err_detail = RE_ERROR_MSG.search(stripped)
            msg = err_detail.group(1).strip()[:120] if err_detail else stripped[:120]
            stats.error_messages.append(msg)
            stats.error_freq[msg] += 1

    _detect_anomalies(stats)
    return stats


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

_ANOMALY_THRESHOLDS = {
    "high_error_rate": 0.05,          # >5 % of lines are errors
    "mining_failure_rate": 0.30,      # >30 % failure
    "attestation_failure_rate": 0.20, # >20 % attestation failures
    "peer_churn_ratio": 3.0,          # disconnects > 3x connects
}


def _detect_anomalies(stats: LogStats) -> None:
    if stats.total_lines == 0:
        return

    error_count = stats.level_counts.get("ERROR", 0) + stats.level_counts.get(
        "CRITICAL", 0
    ) + stats.level_counts.get("FATAL", 0)

    # High error rate
    error_rate = error_count / stats.total_lines
    if error_rate > _ANOMALY_THRESHOLDS["high_error_rate"]:
        stats.anomalies.append({
            "type": "HIGH_ERROR_RATE",
            "detail": f"Error rate {error_rate:.1%} exceeds threshold "
                      f"({_ANOMALY_THRESHOLDS['high_error_rate']:.0%})",
            "severity": "critical",
        })

    # Mining failures
    total_mining = stats.blocks_mined + stats.mining_failures
    if total_mining > 0:
        fail_rate = stats.mining_failures / total_mining
        if fail_rate > _ANOMALY_THRESHOLDS["mining_failure_rate"]:
            stats.anomalies.append({
                "type": "HIGH_MINING_FAILURE_RATE",
                "detail": f"Mining failure rate {fail_rate:.1%} "
                          f"({stats.mining_failures}/{total_mining})",
                "severity": "warning",
            })

    # Attestation failures
    total_attest = stats.attestation_pass + stats.attestation_fail
    if total_attest > 0:
        afr = stats.attestation_fail / total_attest
        if afr > _ANOMALY_THRESHOLDS["attestation_failure_rate"]:
            stats.anomalies.append({
                "type": "HIGH_ATTESTATION_FAILURE_RATE",
                "detail": f"Attestation failure rate {afr:.1%} "
                          f"({stats.attestation_fail}/{total_attest})",
                "severity": "warning",
            })

    # Peer churn
    if stats.peer_connects > 0:
        churn = stats.peer_disconnects / stats.peer_connects
        if churn > _ANOMALY_THRESHOLDS["peer_churn_ratio"]:
            stats.anomalies.append({
                "type": "HIGH_PEER_CHURN",
                "detail": f"Disconnect/connect ratio {churn:.1f}x "
                          f"({stats.peer_disconnects} disc / "
                          f"{stats.peer_connects} conn)",
                "severity": "warning",
            })
    elif stats.peer_disconnects > 0:
        stats.anomalies.append({
            "type": "PEER_LOSS_NO_NEW_CONNECTIONS",
            "detail": f"{stats.peer_disconnects} disconnects with no new connections",
            "severity": "critical",
        })

    # Error burst detection — any single minute with >10 errors
    for minute_key, counters in stats.events_per_minute.items():
        if counters.get("errors", 0) > 10:
            stats.anomalies.append({
                "type": "ERROR_BURST",
                "detail": f"{counters['errors']} errors at {minute_key}",
                "severity": "warning",
            })


# ---------------------------------------------------------------------------
# Text summary
# ---------------------------------------------------------------------------


def format_summary(stats: LogStats) -> str:
    lines = []
    lines.append("=" * 64)
    lines.append("  RustChain Node Log Analysis")
    lines.append("=" * 64)

    lines.append(f"\nTime range   : {stats.first_ts or 'N/A'} -> {stats.last_ts or 'N/A'}")
    lines.append(f"Total lines  : {stats.total_lines:,}")

    # Severity
    lines.append("\n--- Log Levels ---")
    for lvl in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "FATAL"):
        cnt = stats.level_counts.get(lvl, 0)
        if cnt:
            lines.append(f"  {lvl:<10s}: {cnt:>8,}")

    # Mining
    total_mining = stats.blocks_mined + stats.mining_failures
    lines.append("\n--- Mining ---")
    lines.append(f"  Blocks mined   : {stats.blocks_mined:,}")
    lines.append(f"  Failures       : {stats.mining_failures:,}")
    if total_mining:
        lines.append(f"  Success rate   : {stats.blocks_mined / total_mining:.1%}")

    # Attestation
    total_att = stats.attestation_pass + stats.attestation_fail
    lines.append("\n--- Attestation ---")
    lines.append(f"  Passed : {stats.attestation_pass:,}")
    lines.append(f"  Failed : {stats.attestation_fail:,}")
    if total_att:
        lines.append(f"  Pass rate : {stats.attestation_pass / total_att:.1%}")

    # Peers
    lines.append("\n--- Peer Connections ---")
    lines.append(f"  Connects    : {stats.peer_connects:,}")
    lines.append(f"  Disconnects : {stats.peer_disconnects:,}")
    net = stats.peer_connects - stats.peer_disconnects
    lines.append(f"  Net change  : {'+' if net >= 0 else ''}{net:,}")

    # Consensus
    lines.append(f"\n--- Consensus ---")
    lines.append(f"  Events : {stats.consensus_events:,}")

    # Payouts
    lines.append(f"\n--- Payouts ---")
    lines.append(f"  Successful : {stats.payout_ok:,}")
    lines.append(f"  Failed     : {stats.payout_fail:,}")

    # Top errors
    if stats.error_freq:
        lines.append("\n--- Top Errors (by frequency) ---")
        for msg, cnt in sorted(stats.error_freq.items(), key=lambda x: -x[1])[:15]:
            lines.append(f"  [{cnt:>4}x] {msg}")

    # Tags
    if stats.tag_counts:
        lines.append("\n--- Subsystem Tags ---")
        for tag, cnt in sorted(stats.tag_counts.items(), key=lambda x: -x[1])[:15]:
            lines.append(f"  [{tag}] : {cnt:,}")

    # Anomalies
    if stats.anomalies:
        lines.append("\n!!! ANOMALIES DETECTED !!!")
        for a in stats.anomalies:
            sev = a["severity"].upper()
            lines.append(f"  [{sev}] {a['type']}: {a['detail']}")
    else:
        lines.append("\nNo anomalies detected.")

    lines.append("\n" + "=" * 64)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML report generation
# ---------------------------------------------------------------------------

_CSS = """
body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
       margin: 0; padding: 0; background: #0d1117; color: #c9d1d9; }
.container { max-width: 1100px; margin: 0 auto; padding: 24px; }
h1 { color: #58a6ff; border-bottom: 1px solid #30363d; padding-bottom: 12px; }
h2 { color: #79c0ff; margin-top: 32px; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; }
th, td { text-align: left; padding: 8px 14px; border: 1px solid #30363d; }
th { background: #161b22; color: #8b949e; font-weight: 600; }
tr:nth-child(even) { background: #161b22; }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px;
        padding: 18px 22px; margin: 12px 0; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
             gap: 14px; margin: 16px 0; }
.stat-box { background: #0d1117; border: 1px solid #30363d; border-radius: 6px;
            padding: 16px; text-align: center; }
.stat-box .value { font-size: 2rem; font-weight: 700; color: #58a6ff; }
.stat-box .label { font-size: 0.85rem; color: #8b949e; margin-top: 4px; }
.severity-critical { color: #f85149; font-weight: 700; }
.severity-warning  { color: #d29922; font-weight: 600; }
.bar { height: 18px; border-radius: 3px; display: inline-block; vertical-align: middle; }
.bar-ok   { background: #3fb950; }
.bar-fail { background: #f85149; }
.footer { text-align: center; color: #484f58; margin-top: 40px; font-size: 0.8rem; }
"""


def _pct_bar(ok: int, fail: int, width: int = 300) -> str:
    total = ok + fail
    if total == 0:
        return "<span style='color:#484f58'>No data</span>"
    ok_w = int(width * ok / total)
    fail_w = width - ok_w
    return (
        f'<span class="bar bar-ok" style="width:{ok_w}px"></span>'
        f'<span class="bar bar-fail" style="width:{fail_w}px"></span>'
        f' <span style="color:#8b949e">{ok / total:.1%} success</span>'
    )


def generate_html_report(stats: LogStats, output_path: str) -> str:
    """Generate an HTML report and write it to *output_path*. Returns the path."""
    ts_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_mining = stats.blocks_mined + stats.mining_failures
    total_att = stats.attestation_pass + stats.attestation_fail

    anomaly_rows = ""
    for a in stats.anomalies:
        cls = f"severity-{a['severity']}"
        anomaly_rows += (
            f'<tr><td class="{cls}">{html.escape(a["severity"].upper())}</td>'
            f'<td>{html.escape(a["type"])}</td>'
            f'<td>{html.escape(a["detail"])}</td></tr>'
        )

    error_rows = ""
    for msg, cnt in sorted(stats.error_freq.items(), key=lambda x: -x[1])[:20]:
        error_rows += f"<tr><td>{cnt}</td><td>{html.escape(msg)}</td></tr>"

    tag_rows = ""
    for tag, cnt in sorted(stats.tag_counts.items(), key=lambda x: -x[1])[:15]:
        tag_rows += f"<tr><td>{html.escape(tag)}</td><td>{cnt:,}</td></tr>"

    level_rows = ""
    for lvl in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "FATAL"):
        cnt = stats.level_counts.get(lvl, 0)
        if cnt:
            level_rows += f"<tr><td>{lvl}</td><td>{cnt:,}</td></tr>"

    # Time-series data for simple inline chart
    ts_keys = sorted(stats.events_per_minute.keys())
    ts_labels = json.dumps(ts_keys[-60:])  # last 60 minutes max
    ts_mined = json.dumps([stats.events_per_minute[k].get("blocks_mined", 0) for k in ts_keys[-60:]])
    ts_peers = json.dumps([
        stats.events_per_minute[k].get("peer_connects", 0)
        - stats.events_per_minute[k].get("peer_disconnects", 0)
        for k in ts_keys[-60:]
    ])

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RustChain Log Report</title>
<style>{_CSS}</style>
</head>
<body>
<div class="container">
<h1>RustChain Node Log Report</h1>
<p style="color:#8b949e">Generated {html.escape(ts_now)} &mdash;
   Covering {html.escape(stats.first_ts or 'N/A')} to {html.escape(stats.last_ts or 'N/A')}
   &mdash; {stats.total_lines:,} lines analyzed</p>

<!-- KPI cards -->
<div class="stat-grid">
  <div class="stat-box"><div class="value">{stats.total_lines:,}</div><div class="label">Log Lines</div></div>
  <div class="stat-box"><div class="value">{stats.blocks_mined:,}</div><div class="label">Blocks Mined</div></div>
  <div class="stat-box"><div class="value">{stats.peer_connects:,}</div><div class="label">Peer Connects</div></div>
  <div class="stat-box"><div class="value">{stats.level_counts.get('ERROR', 0) + stats.level_counts.get('CRITICAL', 0):,}</div><div class="label">Errors</div></div>
  <div class="stat-box"><div class="value">{len(stats.anomalies)}</div><div class="label">Anomalies</div></div>
</div>

<!-- Anomalies -->
<h2>Anomalies</h2>
<div class="card">
{'<table><tr><th>Severity</th><th>Type</th><th>Detail</th></tr>' + anomaly_rows + '</table>' if anomaly_rows else '<p style="color:#3fb950">No anomalies detected.</p>'}
</div>

<!-- Mining -->
<h2>Mining Performance</h2>
<div class="card">
  <p>Total attempts: {total_mining:,} &mdash; Mined: {stats.blocks_mined:,} &mdash;
     Failed: {stats.mining_failures:,}</p>
  {_pct_bar(stats.blocks_mined, stats.mining_failures)}
</div>

<!-- Attestation -->
<h2>Attestation</h2>
<div class="card">
  <p>Total: {total_att:,} &mdash; Passed: {stats.attestation_pass:,} &mdash;
     Failed: {stats.attestation_fail:,}</p>
  {_pct_bar(stats.attestation_pass, stats.attestation_fail)}
</div>

<!-- Peers -->
<h2>Peer Connections</h2>
<div class="card">
  <p>Connects: {stats.peer_connects:,} &mdash; Disconnects: {stats.peer_disconnects:,}
     &mdash; Net: {'+' if stats.peer_connects - stats.peer_disconnects >= 0 else ''}{stats.peer_connects - stats.peer_disconnects:,}</p>
</div>

<!-- Payouts -->
<h2>Payouts / Settlements</h2>
<div class="card">
  <p>Successful: {stats.payout_ok:,} &mdash; Failed: {stats.payout_fail:,}</p>
  {_pct_bar(stats.payout_ok, stats.payout_fail)}
</div>

<!-- Log Levels -->
<h2>Log Level Distribution</h2>
<div class="card">
<table><tr><th>Level</th><th>Count</th></tr>
{level_rows}
</table></div>

<!-- Top Errors -->
<h2>Top Errors</h2>
<div class="card">
{'<table><tr><th>Count</th><th>Message</th></tr>' + error_rows + '</table>' if error_rows else '<p style="color:#3fb950">No errors recorded.</p>'}
</div>

<!-- Subsystem Tags -->
<h2>Subsystem Tags</h2>
<div class="card">
{'<table><tr><th>Tag</th><th>Count</th></tr>' + tag_rows + '</table>' if tag_rows else '<p>No subsystem tags found.</p>'}
</div>

<div class="footer">RustChain Log Analyzer</div>
</div>
</body>
</html>"""

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    return output_path


# ---------------------------------------------------------------------------
# Watch mode
# ---------------------------------------------------------------------------


def watch_log(path: str, interval: float = 2.0) -> None:
    """
    Continuously tail a log file and print anomaly alerts in real time.
    """
    print(f"Watching {path} (Ctrl+C to stop) ...")
    last_size = 0
    try:
        while True:
            try:
                cur_size = os.path.getsize(path)
            except FileNotFoundError:
                time.sleep(interval)
                continue

            if cur_size > last_size:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    fh.seek(last_size)
                    new_lines = fh.readlines()
                last_size = cur_size

                # Quick parse of new chunk
                chunk_stats = LogStats()
                for line in new_lines:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    chunk_stats.total_lines += 1

                    lv = RE_LOG_LEVEL.search(stripped)
                    if lv:
                        level = lv.group(1).upper()
                        if level == "WARN":
                            level = "WARNING"
                        chunk_stats.level_counts[level] += 1

                    if RE_BLOCK_MINED.search(stripped):
                        chunk_stats.blocks_mined += 1
                    if RE_MINING_FAIL.search(stripped):
                        chunk_stats.mining_failures += 1
                    if RE_ATTEST_PASS.search(stripped):
                        chunk_stats.attestation_pass += 1
                    if RE_ATTEST_FAIL.search(stripped):
                        chunk_stats.attestation_fail += 1
                    if RE_PEER_CONNECT.search(stripped):
                        chunk_stats.peer_connects += 1
                    if RE_PEER_DISCONNECT.search(stripped):
                        chunk_stats.peer_disconnects += 1
                    if RE_PAYOUT_FAIL.search(stripped):
                        chunk_stats.payout_fail += 1

                _detect_anomalies(chunk_stats)

                now = datetime.datetime.now().strftime("%H:%M:%S")

                # Print live counts for the new chunk
                parts = []
                if chunk_stats.blocks_mined:
                    parts.append(f"mined={chunk_stats.blocks_mined}")
                if chunk_stats.mining_failures:
                    parts.append(f"mine_fail={chunk_stats.mining_failures}")
                if chunk_stats.peer_connects:
                    parts.append(f"peer+={chunk_stats.peer_connects}")
                if chunk_stats.peer_disconnects:
                    parts.append(f"peer-={chunk_stats.peer_disconnects}")
                errs = chunk_stats.level_counts.get("ERROR", 0)
                if errs:
                    parts.append(f"errors={errs}")

                if parts:
                    print(f"[{now}] +{chunk_stats.total_lines} lines | {', '.join(parts)}")

                for a in chunk_stats.anomalies:
                    sev = a["severity"].upper()
                    print(f"[{now}] *** ALERT [{sev}] {a['type']}: {a['detail']}")

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nWatch stopped.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RustChain Node Log Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  python analyzer.py analyze node.log
  python analyzer.py report  node.log -o report.html
  python analyzer.py watch   node.log
""",
    )
    sub = parser.add_subparsers(dest="command")

    # analyze
    p_analyze = sub.add_parser("analyze", help="Analyze a log file and print summary")
    p_analyze.add_argument("logfile", help="Path to the RustChain node log file")
    p_analyze.add_argument("--json", action="store_true", help="Output as JSON")
    p_analyze.add_argument(
        "--tail", type=int, default=0, help="Only analyze last N lines"
    )

    # report
    p_report = sub.add_parser("report", help="Generate an HTML report")
    p_report.add_argument("logfile", help="Path to the RustChain node log file")
    p_report.add_argument(
        "-o", "--output", default="rustchain_report.html",
        help="Output HTML file (default: rustchain_report.html)",
    )

    # watch
    p_watch = sub.add_parser("watch", help="Tail a log file and alert on anomalies")
    p_watch.add_argument("logfile", help="Path to the RustChain node log file")
    p_watch.add_argument(
        "--interval", type=float, default=2.0,
        help="Poll interval in seconds (default: 2)",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "analyze":
        stats = parse_log(args.logfile, tail=args.tail)
        if args.json:
            out = {
                "total_lines": stats.total_lines,
                "time_range": [stats.first_ts, stats.last_ts],
                "levels": dict(stats.level_counts),
                "mining": {
                    "blocks_mined": stats.blocks_mined,
                    "failures": stats.mining_failures,
                },
                "attestation": {
                    "pass": stats.attestation_pass,
                    "fail": stats.attestation_fail,
                },
                "peers": {
                    "connects": stats.peer_connects,
                    "disconnects": stats.peer_disconnects,
                },
                "consensus_events": stats.consensus_events,
                "payouts": {
                    "ok": stats.payout_ok,
                    "fail": stats.payout_fail,
                },
                "top_errors": dict(
                    sorted(stats.error_freq.items(), key=lambda x: -x[1])[:20]
                ),
                "anomalies": stats.anomalies,
            }
            print(json.dumps(out, indent=2))
        else:
            print(format_summary(stats))

        # Exit with non-zero if critical anomalies found
        if any(a["severity"] == "critical" for a in stats.anomalies):
            sys.exit(2)

    elif args.command == "report":
        stats = parse_log(args.logfile)
        path = generate_html_report(stats, args.output)
        print(f"Report written to {path}")

    elif args.command == "watch":
        watch_log(args.logfile, interval=args.interval)


if __name__ == "__main__":
    main()
