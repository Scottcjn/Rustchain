# Changelog

## 1.1.0

Signed transfers are now bound to a network (#8533).

- `RustChainClient` gained `network_info()` and `get_chain_id()`.
- Wallet transfers fetch `chain_id` from the node's `GET /network/info`,
  include it in the signed message, and send it with
  `POST /wallet/transfer/signed`. A signature made for one RustChain network
  can no longer be replayed on another.

Upgrade before nodes start rejecting signed transfers that omit `chain_id`
(Scottcjn/Rustchain#8397).

## 1.0.0

Initial release.
