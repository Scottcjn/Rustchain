# Sources

Primary source: RustChain Unified API Reference
https://github.com/Scottcjn/Rustchain/blob/main/docs/API_REFERENCE.md

Claim map:
- `/wallet/transfer/signed` exists as the documented wallet-to-wallet signed transfer endpoint → API Reference, Wallet section.
- The endpoint requires an Ed25519 signature and does not require an admin key → API Reference, Authentication + `POST /wallet/transfer/signed`.
- The example request includes sender, recipient, amount, nonce, memo, public key, signature, and chain ID → API Reference request example.
- The documented success response includes `verified: true` and `phase: pending` → API Reference response example.
- The documentation states confirmation takes 24 hours → API Reference important notes.

Editorial interpretation used in the script: cryptographic authorization and settlement state are distinct checks. This is phrased as an explanatory distinction, not a claim that signing guarantees transaction safety or finality.