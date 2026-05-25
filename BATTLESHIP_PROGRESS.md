# BATTLESHIP PROGRESS

## Unbounded offset/pagination (Row C, Col 13-15)
| Cell | File | Field | PR | Status |
|------|------|-------|----|--------|
| C13 | governance.py | offset | #6255 | Open |
| C14 | machine_passport_api.py | offset | #6256 | Open |
| C15 | ergo_anchor.py | offset | #6257 | Open |

## Unbounded TEXT / input (Row A, Col 15-24)
| Cell | File | Field | PR | Status |
|------|------|-------|----|--------|
| A15 | bottube_feed_routes.py | Host header | #6258 | Open, fix pushed |
| A16 | utxo_endpoints.py | memo | #6259 | Open |
| A17 | gpu_render_endpoints.py | pricing | #6260 | Open |
| A18 | bcos_routes.py | cert_id/repo/commit_sha/reviewer | #6261 | Open |
| A19 | beacon_api.py | agent_id/pubkey/name/type/term/currency | #6262 | Open |
| A20 | bridge_api.py | source_address/dest_address | #6263 | Open |
| A21 | airdrop_v2.py | github_username/wallet_address/chain/tier | #6264 | Open |
| A22 | lock_ledger.py | miner_id/release_tx_hash/reason | #6265 | Open |
| A23 | rustchain_sync_endpoints.py | X-Peer-ID/X-Sync-Nonce/X-Sync-Signature/table | #6266 | Open |
| A24 | bridge/bridge_api.py | sender_wallet/target_wallet/tx_hash/receipt_signature/proof_ref/notes/release_tx | #6267 | Open |
| A25 | faucet.py | wallet | #6268 | Open |
| A26 | sophia_api.py | miner_id (POST + 2 GET path params) | #6269 | Open |
| A27 | explorer/app.py | miner_id (2 GET path params) | #6270 | Open |
| A28 | node/rustchain_p2p_sync.py | peer_url (POST /p2p/announce) | #6271 | Open |
| A29 | explorer/rustchain_dashboard.py | wallet_address (GET path param) | #6272 | Open |

## Exhausted cells (grid complete)
| Cell | File | Vulnerability | PR |
|------|------|---------------|----|
| A1-A5 | utxo_db.py | Mempool/input bounds | #6237 |
| A6, A9-A11 | utxo_db.py | Input validation | #6241 |
| A7 | utxo_db.py | Box ID endianness | #6243 |
| A12 | utxo_db.py | TX type normalize | #6242 |
| A13 | utxo_db.py | TX data JSON size | #6245 |
| A14 | utxo_db.py | Spending proof size | #6246 |
| B1-B3, C1 | utxo_db.py | Dynamic race conds | #6239 |
| C2-C4, D1 | utxo_db.py | Adversarial vulns | #6240 |
| C7 | utxo_db.py | Genesis migration | #6249 |
| C8 | rewards.py | ADM double-credit | #6250 |
| C9 | governance.py | Vote tally race | #6251 |
| C10 | coalition.py | Vote tally race | #6252 |
| C11 | bridge.py | Confirm cap | #6253 |
| C12 | bridge.py | Req confirm cap | #6254 |
| C16 | utxo_db.py | Mining reward dup | #6247 |
