# 9:16 Capture Instructions

Target length: 45–55 seconds. Canvas: 1080×1920.

1. 0–4s — Large hook text: “NO ADMIN KEY?” with a small subtitle “Signed wallet transfer”.
2. 4–11s — Screen-record the RustChain API reference heading `POST /wallet/transfer/signed`; crop tightly enough that the endpoint and “Ed25519 signature” are readable.
3. 11–23s — Show the request JSON example. Highlight `from_address`, `to_address`, `amount_rtc`, `nonce`, `public_key`, `signature`, and `chain_id` one group at a time.
4. 23–34s — Show the documented success response and zoom sequentially to `verified: true` and `phase: pending`.
5. 34–43s — Show the documentation note stating confirmation takes 24 hours.
6. 43–52s — End card text: “SIGNED ≠ SETTLED” then “Verify the signature. Verify the state.”

Use only screen captures from the canonical public RustChain documentation and generated text cards. No third-party media is required. Do not display real private keys or signatures.