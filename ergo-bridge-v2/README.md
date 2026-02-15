# Secure Ergo Bridge (Python Implementation)

A high-security, production-ready bridge module for Rustchain, rewritten in Python to ensure full compatibility with the existing SQLite-based architecture.

## Key Features

- **Re-org Resilience**: Implements a sliding-window verification algorithm that ensures chain continuity and halts operations if an Ergo network roll-back is detected.
- **Full Integration**: Uses the existing `rustchain_v2.db` (SQLite) and follows the established data structures used in `ergo_miner_anchor.py`.
- **Deterministic Traceability**: Replaced random identifiers with event-derived deterministic IDs for consistent cross-chain auditing.
- **Crash Recovery**: Includes an automatic state-recovery mechanism that syncs transaction statuses with the Ergo node upon service restart.
- **Async Efficiency**: Built using `asyncio` and `httpx` for high-concurrency node interaction without the weight of an external server framework.

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure your Ergo node URL and API key in the configuration dictionary.

## Architecture

- `core/security.py`: The security engine handles finality checks and re-org protection.
- `providers/ergo_node.py`: Async adapter for the Ergo Node REST API.
- `providers/sqlite_db.py`: Persistence layer for bridge requests and block audits.
- `bridge.py`: Main orchestration loop.
