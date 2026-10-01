# Changelog

## 0.2.0

Signed transfers are now bound to a network (#8533).

- `Transaction` has a new public field `chain_id: Option<String>`, plus
  `Transaction::with_chain_id` and `TransactionBuilder::chain_id`. Code that
  builds `Transaction` with a struct literal must add the field, which is why
  this is a minor (breaking, pre-1.0) bump.
- `chain_id` is part of the signed message, so a signature made for one
  RustChain network cannot be replayed on another.
- New `signed_transfer_payload(&Transaction)` builds the request body for
  `POST /wallet/transfer/signed`, including `chain_id`.
- The client reads `chain_id` from the node's `GET /network/info` before
  signing and sends it with the transfer.

Upgrade before nodes start rejecting signed transfers that omit `chain_id`
(Scottcjn/Rustchain#8397).

## 0.1.0

Initial release.
