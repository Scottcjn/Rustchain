"""Batch scheduler for SophiaCore Attestation Inspector.

Placeholder batch processor that iterates all known miners
and triggers inspection. Designed to be called by cron or a scheduler.
"""
import logging
from typing import Dict, Any

from .db import get_all_miner_ids, save_inspection, get_latest_verdict
from .inspector import evaluate_fingerprint

logger = logging.getLogger(__name__)


def run_batch() -> Dict[str, Any]:
    """Run batch inspection on all known miners.

    Returns a summary dict with counts of each verdict type.
    """
    miner_ids = get_all_miner_ids()
    results = {
        "total": len(miner_ids),
        "APPROVED": 0,
        "CAUTIOUS": 0,
        "SUSPICIOUS": 0,
        "REJECTED": 0,
        "errors": 0,
    }

    for miner_id in miner_ids:
        try:
            latest = get_latest_verdict(miner_id)
            if not latest:
                logger.warning(f"No fingerprint data for miner {miner_id}, skipping")
                continue

            # Reconstruct fingerprint from stored data
            import json

            fingerprint = json.loads(latest.get("fingerprint_data", "{}"))
            verdict, confidence, reasoning = evaluate_fingerprint(fingerprint)

            save_inspection(
                miner_id=miner_id,
                verdict=verdict.value,
                confidence=confidence,
                reasoning=reasoning,
                signature=latest.get("signature"),
                fingerprint_data=latest.get("fingerprint_data"),
                test_mode=False,
            )

            results[verdict.value] += 1
            logger.info(f"[Batch] {miner_id}: {verdict.value} ({confidence:.2f})")
        except Exception as e:
            results["errors"] += 1
            logger.error(f"[Batch] Error processing miner {miner_id}: {e}")

    logger.info(f"[Batch] Complete — {results}")
    return results
