# Wallet CLI Compatibility Notes (Issue #39)

This note documents format compatibility and cross-platform validation for the RustChain Wallet CLI.

## Keystore compatibility

CLI keystore output fields:
- `version`
- `name`
- `address`
- `public_key_hex`
- `mnemonic_words`
- `crypto`:
  - `cipher: AES-256-GCM`
  - `kdf: PBKDF2-HMAC-SHA256`
  - `kdf_iterations: 100000`
  - `salt_b64`
  - `nonce_b64`
  - `ciphertext_b64`

Backward-compatible decryption aliases supported by the CLI loader:
- `salt_b64` or `salt`
- `nonce_b64` or `nonce` or `iv_b64` or `iv`
- `ciphertext_b64` or `ciphertext` or `encrypted_private_key`
- `kdf_iterations` or `iterations` or `pbkdf2_iterations`

This allows the CLI to read equivalent legacy JSON key names while preserving modern output format.

## Signature payload compatibility

Signed transfer payload uses:
- `from_address`
- `to_address`
- `amount_rtc`
- `nonce`
- `memo`
- `public_key`
- `signature`

Signature is Ed25519 over canonical JSON message:

```json
{"amount":<float>,"from":"<RTC...>","memo":"...","nonce":"<nonce>","to":"<RTC...>"}
```

This matches `/wallet/transfer/signed` server-side verification pattern.

## Validation summary

Local (macOS):
- `python3 -m pytest -q tests/test_wallet_cli_39.py` -> passed
- `python3 tools/rustchain_wallet_cli.py epoch` -> success
- `python3 tools/rustchain_wallet_cli.py miners` -> success
- `python3 tools/rustchain_wallet_cli.py balance <wallet>` -> success

Remote (Linux, HK machine):
- same test command and CLI command smoke checks executed successfully.
