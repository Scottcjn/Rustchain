# Script — “No Admin Key Needed?”

**Hook:** “A RustChain wallet transfer can be signed without an admin key.”

RustChain’s public API documents a wallet-to-wallet transfer route called `/wallet/transfer/signed`.

Instead of an admin key, the request carries an Ed25519 public key and signature, plus the sender, recipient, amount, nonce, memo, and chain ID.

If verification succeeds, the API returns `verified: true` — but notice the next field: `phase: pending`.

The same reference says confirmation takes 24 hours.

So the useful distinction is simple: cryptographic authorization proves who signed the transfer, while settlement state tells you whether it has actually confirmed.

Signed does not mean settled.

**End card:** RustChain — verify the signature, then verify the state.
