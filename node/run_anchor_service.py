#!/usr/bin/env python3
"""RustChain Ergo Anchor Service Runner"""
import os
import sys
import time

# Set env vars
os.environ["ERGO_NODE_URL"] = "http://localhost:9053"
os.environ["ERGO_API_KEY"] = "hello"

from rustchain_ergo_anchor import AnchorService, ErgoClient

DB_PATH = "/root/rustchain/rustchain_v2.db"

print("=" * 60)
print("RustChain -> Ergo Anchor Service Starting")
print("=" * 60)

# Initialize
client = ErgoClient()
info = client.get_info()
if info:
    print(f"Ergo height: {info.get(\"fullHeight\", \"N/A\")}")
else:
    print("WARNING: Cannot connect to Ergo node")
    sys.exit(1)

service = AnchorService(
    db_path=DB_PATH,
    ergo_client=client,
    interval_blocks=144  # Anchor every 144 RC blocks
)

print(f"DB: {DB_PATH}")
print(f"Anchor interval: 144 blocks")
print("Starting service loop...")
print("=" * 60)

# Run the anchor service
service.start(check_interval=60)  # Check every 60 seconds
