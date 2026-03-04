# RustChain Wallet CLI (Preview for bounty #39)

This draft adds a headless wallet tool:

- `rustchain-wallet create`
- `rustchain-wallet import <mnemonic>`
- `rustchain-wallet export <wallet-name>`
- `rustchain-wallet balance <wallet-address>`
- `rustchain-wallet send <to> <amount> --from <wallet-name>`
- `rustchain-wallet history <wallet-address>`
- `rustchain-wallet miners`
- `rustchain-wallet epoch`

## Paths

- CLI implementation: `tools/rustchain_wallet_cli.py`
- Command wrapper: `scripts/rustchain-wallet`
- Keystore dir: `~/.rustchain/wallets/`

## Security / format notes

- Private keys are encrypted with **AES-256-GCM**
- KDF: **PBKDF2-HMAC-SHA256** with **100,000 iterations**
- Address derivation: `RTC` + `SHA256(pubkey)[:40]`
- Transfer signing: Ed25519 over canonical payload used by `/wallet/transfer/signed`

## Dependency

Install BIP39 helper once:

```bash
python3 -m pip install mnemonic
```

## Quick smoke test

```bash
scripts/rustchain-wallet create --name demo
scripts/rustchain-wallet export demo
scripts/rustchain-wallet epoch
scripts/rustchain-wallet miners
```
