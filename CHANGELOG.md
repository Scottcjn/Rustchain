# Changelog

All notable changes to RustChain will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security Fixes

- **VULN-1 (CRITICAL): Token Conservation Bypass** — Added strict token conservation
  validation in `apply_transaction()`. Input and output token quantities must match
  exactly, preventing minting/burning arbitrary tokens in non-coinbase transactions.

- **VULN-2 (HIGH): tx_id Collision Attack** — Updated `compute_tx_id()` to include
  `outputs`, `lock_time`, and `version` in the hash computation. Previously, only
  `inputs` and `timestamp` were included, allowing attackers to create transactions
  with identical tx_ids but different outputs.

- **VULN-3 (MEDIUM): Mempool tx_id Spoofing** — `mempool_add()` now recomputes tx_id
  from transaction contents (including `lock_time` and `version`) and verifies it
  matches the provided tx_id before acceptance.

- **Mempool Rate Limiting** — Added sliding-window rate limiting to `mempool_add()`:
  max 10 transactions per 60-second window to prevent spam/DoS attacks.
