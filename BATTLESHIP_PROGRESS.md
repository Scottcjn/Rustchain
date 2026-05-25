# BATTLESHIP PROGRESS — 400-Cell Grid

## Vaulted Accomplishments (cells complete — do not re-hunt)

| Cell | File | Vulnerability | PR |
|------|------|---------------|----|
| A1-A5 | utxo_db.py | Mempool/input bounds | #6237 |
| A6, A9-A11 | utxo_db.py | Input validation | #6241 |
| A7 | utxo_db.py | Box ID endianness | #6243 |
| A12 | utxo_db.py | TX type normalize | #6242 |
| A13 | utxo_db.py | TX data JSON size | #6245 |
| A14 | utxo_db.py | Spending proof size | #6246 |
| B1-B3, C1 | utxo_db.py | Dynamic race conds | #6239 |
| B4, B5 | lock_ledger.py | TOCTOU release/forfeit race | #6285 |
| C2-C4, D1 | utxo_db.py | Adversarial vulns | #6240 |
| C7 | utxo_db.py | Genesis migration | #6249 |
| C8 | rewards.py | ADM double-credit | #6250 |
| C9 | governance.py | Vote tally race | #6251 |
| C10 | coalition.py | Vote tally race | #6252 |
| C11 | bridge.py | Confirm cap | #6253 |
| C12 | bridge.py | Req confirm cap | #6254 |
| C16 | utxo_db.py | Mining reward dup | #6247 |

## Unbounded offset/pagination — Row C (Col 13-15) — Open PRs

| Cell | File | Field | PR | Status |
|------|------|-------|----|--------|
| C13 | governance.py | offset | #6255 | Open |
| C14 | machine_passport_api.py | offset | #6256 | Open |
| C15 | ergo_anchor.py | offset | #6257 | Open |

## Unbounded TEXT / input — Row A (Col 15-41) — Open PRs

| Cell | File | Field | PR | Status |
|------|------|-------|----|--------|
| A15 | bottube_feed_routes.py | Host header | #6258 | 2nd fix pushed |
| A16 | utxo_endpoints.py | memo | #6259 | Open |
| A17 | gpu_render_endpoints.py | pricing | #6260 | Open |
| A18 | bcos_routes.py | cert_id/repo/commit_sha/reviewer | #6261 | Open |
| A19 | beacon_api.py | agent_id/pubkey/name/type/term/currency | #6262 | Open |
| A20 | bridge_api.py | source_address/dest_address | #6263 | Open |
| A21 | airdrop_v2.py | github_username/wallet_address/chain/tier | #6264 | Open |
| A22 | lock_ledger.py | miner_id/release_tx_hash/reason | #6265 | Open |
| A23 | rustchain_sync_endpoints.py | X-Peer-ID/X-Sync-Nonce/X-Sync-Signature/table | #6266 | Open |
| A24 | bridge/bridge_api.py | sender_wallet/target_wallet/tx_hash/... | #6267 | Open |
| A25 | faucet.py | wallet | #6268 | Open |
| A26 | sophia_api.py | miner_id (POST + 2 GET) | #6269 | Open |
| A27 | explorer/app.py | miner_id (2 GET path params) | #6270 | Open |
| A28 | node/rustchain_p2p_sync.py | peer_url (POST /p2p/announce) | #6271 | Open |
| A29 | explorer/rustchain_dashboard.py | wallet_address (GET path param) | #6272 | Open |
| A30 | tools/testnet_faucet.py | wallet, github_username | #6273 | Open |
| A31 | tools/rent_a_relic/server.py | agent_id, machine_id | #6274 | Open |
| A32 | tools/explorer-api/api.py | addr (GET path param) | #6275 | Open |
| A33 | tools/explorer-api/api.py | q (GET /api/search) | #6276 | Open |
| A34 | health-dashboard/server.py | node_id (GET path param) | #6277 | Open |
| A35 | node/beacon_x402.py | agent_id, _json_string_field | #6278 | Open |
| A36 | node/bottube_embed.py | video_id, url | #6279 | Open |
| A37 | rips/rustchain-core/api/rpc.py | address/block_hash/proposal_id | #6280 | Open |
| A38 | contributor_registry.py | username (admin approve) | #6281 | Open |
| A39 | node/hall_of_rust.py | miner_id/device_model/arch/family/hw_serial | #6282 | Open |
| A40 | node/machine_passport_api.py | name/owner_miner_id/architecture/photo_* | #6283 | Open |
| A41 | bottube_mood_engine.py | agent_name (6 path param endpoints) | #6284 | Open |

---

## ACTIVE GRID — Fresh 360 gaps to hunt

### Row S — Production Stubs / "Not Implemented" (S1-S30)

| Cell | File | Gap | Priority | |
|------|------|-----|----------|---|
| S1 | claims_settlement.py:311 | sign_and_broadcast_transaction() is a hard stub | HIGH | ✅ #6286 |
| S3 | beacon_api.py:1058 | mock LLM response in production | MED | ✅ #6287 |
| S4 | tools/validate_vintage_submission.py:37 | photo validation → real PIL analysis | MED | ✅ #3 |
| S5 | tools/validate_vintage_submission.py:83 | screenshot validation → real PIL analysis | MED | ✅ #3 |
| S6 | tools/comment-moderation-bot/scorer.py:192 | semantic scoring stub → HTTP client | MED | ✅ #6289 |
| S7 | tools/rent_a_relic/provenance.py:49 | attestation proof digest (real SHA-256, Ed25519-signed, functional) | LOW | ✅ verified |
| S8 | tools/cli/rustchain_cli.py:175 | epoch history not implemented | LOW | ✅ #6 |
| S9 | tools/cli/rustchain_cli.py:263 | wallet creation not implemented | LOW | ✅ #7 |
| S10 | tools/cli/rustchain_cli.py:409 | agent registration not implemented | LOW | ✅ #8 |
| S11 | tools/cli/rustchain_cli.py:514 | bounty claim not implemented | LOW | ✅ #9 |
| S12 | tools/cli/rustchain_cli.py:567 | x402 payment not implemented | LOW | ✅ #9 |
| S13 | payout_worker.py:22 | MOCK_MODE default → safe mock (False→True) | HIGH | ✅ #6290 |
| S14 | machine_passport_viewer.py:290 | QR code is placeholder div — no real QR gen | LOW |
| S15 | bottube_embed.py:708 | _get_mock_video() fallback → persistent DB | MED | ✅ #11 |
| S16 | bottube_feed_routes.py:80 | pagination cursor not implemented in mock | MED |
| S17 | ed25519_config.py:27 | TESTNET_ALLOW_MOCK_SIG → env-var-driven, prevents monkey-patching | HIGH | ✅ #6291 |
| S18 | bridge_api.py | no rate limiting on any endpoint → per-IP sliding window | MED | ✅ #6292 |
| S19 | beacon_api.py | no rate limiting → 8 endpoints per-IP rate-limited | MED | ✅ #4 |
| S20 | airdrop_v2.py | no rate limiting → 5 endpoints per-IP rate-limited | MED | ✅ #5 |
| S21 | governance.py | mock erc20/ed25519 config reference | MED |
| S22 | bottube_feed_routes.py | feed routes have no auth — anyone can spam | MED |
| S23 | bridge_api.py:225 | chain address validation is format-only, no checksum | MED |
| S24 | beacon_x402.py | x402 payment flow not fully wired | MED |
| S25 | utxo_endpoints.py:493 | new-client fee signed but drift/expiry not checked | LOW |
| S26 | rustchain_p2p_gossip.py:93 | insecure placeholder p2p secret config | HIGH | ✅ #10 |
| S27 | hardware_fingerprint_replay.py | fingerprint replay DB has no cleanup cron | LOW |
| S28 | anti_double_mining.py | anti-double-mining table no index on miner+block | LOW |
| S29 | machine_passport_api.py | photo_hash not verified client-side | MED |
| S30 | payout_worker.py:285 | recover_orphans flags but no auto-refund path | MED |

### Row M — Missing Error Handling (M1-M30)

| Cell | Gap |
|------|-----|
| M1 | bridge_api.py: create_bridge_transfer no timeout on external network calls |
| M2 | beacon_api.py: create_contract no validation on JSON fields |
| M3 | bottube_embed.py: _fetch_videos no timeout on DB queries |
| M4 | governance.py: propose() no fee validation |
| M5 | coalition.py: no quorum check on vote tally |
| M6 | payout_worker.py: cleanup_old_withdrawals file descriptor leak on archive |
| M7 | machine_passport_api.py: register() no duplicate name check |
| M8 | bcos_routes.py: attest() no rate limit on cert generation |
| M9 | airdrop_v2.py: claim() no duplicate wallet check |
| M10 | beacon_x402.py: no refund path for failed x402 payments |
| M11 | lock_ledger.py: auto_release_expired_locks no per-lock timeout cap |
| M12 | bridge_api.py: void_bridge_transfer no 2FA for admin |
| M13 | beacon_api.py: no pagination limit on get_agents() |
| M14 | governance.py: results() no cached results for repeated queries |
| M15 | coalition.py: join() no minimum stake validation |
| M16 | faucet.py: claim() no IP-based rate limit |
| M17 | hall_of_rust.py: submit() no uniqueness check on hardware fingerprint |
| M18 | bottube_feed_routes.py: rss_feed() no cache header for mock data |
| M19 | machine_passport_api.py: no batch query endpoint |
| M20 | ergo_miner_anchor.py: no fallback on anchor submit failure |
| M21 | contributor_registry.py: approve() no admin audit log |
| M22 | testnet_faucet.py: no rate limit across all endpoints |
| M23 | rent_a_relic/server.py: no max-rental-duration cap |
| M24 | explorer-api/api.py: no result limit on /api/search |
| M25 | health-dashboard/server.py: no timeout on upstream health check |
| M26 | beacon_x402.py: no retry on IPFS upload failure |
| M27 | governance.py: vote() no delegate weight cap |
| M28 | coalition.py: no slashing for double-vote detection |
| M29 | claims_submission.py: no submission fee to prevent spam |
| M30 | infrastructure: no monitoring/alerting on failed cron jobs |

### Row T — Test Coverage Gaps (T1-T40)

| Cell | Gap |
|------|-----|
| T1-T40 | Every file without test coverage: lock_ledger.py, bridge_api.py, beacon_api.py, bcos_routes.py, coalition.py, governance.py, airdrop_v2.py, payout_worker.py, claims_settlement.py, bottube_feed_routes.py, bottube_embed.py, machine_passport_api.py, hall_of_rust.py, ergo_miner_anchor.py, contributor_registry.py, beacon_x402.py, faucet.py, sophia_api.py, rustchain_sync_endpoints.py, health-dashboard, explorer-api, rent_a_relic, testnet_faucet, rustchain_dashboard, mining_pool_tracker, anti_double_mining, rom_clustering, fingerprint_checks, arch_cross_validation, warthog_verification, beacon_anchor, beacon_identity, consensus_probe, fork_choice_visualizer, ed25519_config, claims_eligibility, gpu_attestation, gpu_render_endpoints, bottube_feed, bottube_mood_engine |

### Row D — Dynamic testing / Protocol gaps (D2-D40)

| Cell | Gap |
|------|-----|
| D2 | race condition in batch epoch settlement |
| D3 | concurrent bridge transfer creation |
| D4 | concurrent airdrop claim |
| D5 | concurrent governance vote |
| D6 | concurrent coalition join |
| D7 | concurrent machine_passport register |
| D8 | concurrent bcos attestation |
| D9 | concurrent beacon join |
| D10-D40 | (expand as found) |

### Row E — Infrastructure / CI gaps (E1-E30)

| Cell | Gap |
|------|-----|
| E1 | CI/CD: no linting/type checking in GitHub Actions |
| E2 | CI/CD: no automated test run on PR |
| E3 | CI/CD: no Docker image build/publish |
| E4 | Monitoring: no Prometheus metrics endpoint |
| E5 | Monitoring: no structured logging |
| E6 | Deployment: no Helm chart |
| E7 | Deployment: no migration automation |
| E8 | Backup: no automated DB backup |
| E9 | Backup: no recovery test |
| E10-E30 | (expand as found) |

---

### Legend
- **Row A (Open PRs)** — Unbounded TEXT / Input — 41 cells, 27 open PRs
- **Row B (Completed)** — TOCTOU races — 5 cells done
- **Row C (Completed)** — Adversarial — 16 cells done (C13-C15 open via PRs)
- **Row D** — Protocol / dynamic testing — to hunt
- **Row S** — Production stubs / not implemented — 30 cells
- **Row M** — Missing error handling — 30 cells
- **Row T** — Test coverage gaps — 40 cells
- **Row E** — Infrastructure / CI — expandable
- **Row H** — Economic — expandable
- **Row I** — Cross-repo — expandable

**56 cells vaulted. ~360 fresh gaps to hunt.**

Pick lowest undone coordinate by row priority: S → M → D → E → T
