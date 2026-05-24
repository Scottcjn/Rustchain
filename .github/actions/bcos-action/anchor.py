#!/usr/bin/env python3
"""
BCOS v2 Action - Anchor to RustChain

Anchors the BCOS attestation to the RustChain blockchain.
"""

import json
import logging
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    """Anchor the BCOS attestation to RustChain."""
    # Get inputs from environment
    node_url = os.environ.get("INPUT_NODE_URL", "https://rustchain.org")
    cert_id = os.environ.get("CERT_ID", "")
    commitment = os.environ.get("COMMITMENT", "")
    repo = os.environ.get("REPO", "")
    pr_number = os.environ.get("PR_NUMBER", "")
    merged_commit = os.environ.get("MERGED_COMMIT", "")
    
    if not all([cert_id, commitment, repo, pr_number, merged_commit]):
        logger.warning("Missing required environment variables. Skipping anchor.")
        return
    
    # Build attestation payload
    attestation = {
        "cert_id": cert_id,
        "commitment": commitment,
        "repo": repo,
        "pr_number": int(pr_number),
        "merged_commit": merged_commit,
        "schema": "bcos-attestation/v2"
    }
    
    # POST to RustChain anchor endpoint
    anchor_url = f"{node_url}/api/v1/bcos/anchor"
    
    req = Request(
        anchor_url,
        data=json.dumps(attestation).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        },
        method='POST'
    )
    
    try:
        response = urlopen(req)
        result = json.loads(response.read().decode("utf-8"))
        logger.info("Attestation anchored successfully.")
        logger.info("Transaction: %s", result.get("tx_hash", "N/A"))
        logger.info("Block: %s", result.get("block_number", "N/A"))
    except HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        logger.warning("Failed to anchor: %s", e.code)
        if error_body:
            logger.warning("Response: %s", error_body)
    except Exception as e:
        logger.warning("Anchor skipped (node may be unavailable): %s", e)


if __name__ == "__main__":
    main()
