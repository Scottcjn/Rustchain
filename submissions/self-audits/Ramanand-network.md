# Self-Audit: rips/src/core/network.rs

## Wallet
9A8VVXnQxEL1EkygpegBztwx7kxWYhF9kWW97f4WVbiH

## Module reviewed
- Path: rips/src/core/network.rs
- Commit: 92888df

## Confidence
Low Confidence (Multiple Failures Found)

## Known Failures (Specific Findings)

### 1. Unbounded known_peers Growth (Memory Exhaustion DoS)
- **Severity:** Critical
- **Description:** In `NetworkManager::handle_message`, the `Message::AnnouncePeer` handler inserts arbitrarily formatted strings into the `self.known_peers` HashSet without checking a maximum capacity limit.
- **Exploit:** An attacker can spam fake `AnnouncePeer` messages, causing the node's memory footprint to grow infinitely until an Out-Of-Memory (OOM) crash occurs.

### 2. SystemTime Panic in create_hello
- **Severity:** Medium
- **Description:** `create_hello()` uses `.unwrap()` on `duration_since(std::time::UNIX_EPOCH)`.
- **Exploit:** If a node (especially vintage hardware) boots with a clock desynchronized to pre-1970, attempting to create a Hello message will panic and crash the node software. It should be handled with a safe fallback (e.g., `unwrap_or_default()`).

## What I would test next
- Check if other message handlers (like `Blocks` or `PendingTransactions`) also lack memory/size limits when parsing incoming network data.
- Test the `cleanup_stale_peers` function to see if it properly drops dead connections or if it can be bypassed to cause connection exhaustion.