"""Entry point: python -m rustchain_alerts [--config path] [--once]"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from .config import load_config
from .monitor import MinerMonitor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RustChain Miner Alert System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m rustchain_alerts                    # run with default config.yaml
  python -m rustchain_alerts --config my.yaml  # custom config
  python -m rustchain_alerts --once            # single poll and exit
  python -m rustchain_alerts --history         # show recent alerts and exit
""",
    )
    parser.add_argument("--config", default="config.yaml", help="Path to YAML config (default: config.yaml)")
    parser.add_argument("--once", action="store_true", help="Run one poll cycle and exit")
    parser.add_argument("--history", action="store_true", help="Print recent alert history and exit")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    config = load_config(args.config)
    monitor = MinerMonitor(config)

    if args.history:
        rows = monitor.db.recent_alerts(limit=50)
        if not rows:
            print("No alerts recorded yet.")
        else:
            print(f"{'Time':<20} {'Miner':<40} {'Type':<16} {'Message'}")
            print("-" * 100)
            for row in rows:
                import datetime
                ts = datetime.datetime.fromtimestamp(row["fired_at"]).strftime("%Y-%m-%d %H:%M:%S")
                miner = row["miner_id"][:38]
                print(f"{ts:<20} {miner:<40} {row['alert_type']:<16} {row['message'][:60]}")
        return

    try:
        if args.once:
            await monitor._poll()
        else:
            await monitor.run()
    finally:
        await monitor.aclose()


if __name__ == "__main__":
    asyncio.run(main())
