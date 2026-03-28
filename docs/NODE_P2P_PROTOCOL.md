# 🌐 Understanding the RustChain Node: P2P Gossip & Block Production

The RustChain node is the heart of the network. It manages the ledger, validates miner attestations, and syncs blocks via a custom **P2P Gossip Protocol**.

---

## 🤝 1. The P2P Handshake
When a node starts, it connects to seed nodes and performs a handshake.
- **Identity:** Every node has a unique `node_id`.
- **Version Check:** Nodes will only peer with others running compatible protocol versions (current: v2.x).
- **Gossip Mechanism:** When a new block is produced, it is "gossiped" to all connected peers, who then validate and relay it to their own neighbors.

---

## 🧱 2. Block Production & Validation
Unlike standard PoW where any hash wins, RustChain requires:
1. **Valid PoW Hash:** Meeting the current network difficulty.
2. **Valid Hardware Attestation:** The block must include the miner's hardware serial and fingerprint data.
3. **Serial Binding Check:** The node verifies that this serial hasn't already submitted a block in the current 600-second window.

---

## 🔄 3. State Migration & ROM Clustering
RustChain uses a unique **ROM Clustering** server for identity management.
- **Migration:** When the protocol upgrades (e.g., from v1 to v2), the `rustchain_migration.py` script handles the state transition of wallets and hardware bindings.
- **Fingerprint DB:** A central (or clustered) database stores historical fingerprint data to prevent "fingerprint spoofing" across the network.

---

## 🛡️ 4. Transaction Handling
The `rustchain_tx_handler.py` manages the mempool.
- **Validation:** Transactions are checked for double-spending and signature validity before being added to the next block candidate.
- **Round Robin:** In some versions (RIP-200), a Round Robin 1CPU1Vote mechanism is used to further decentralize the block production among active miners.

---

*Written by RematNOC - Building a decentralized future with RustChain.*
