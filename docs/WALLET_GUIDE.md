# RustChain Wallet User Guide

This guide explains how to create, manage, and use RustChain (RTC) wallets. RustChain supports multiple wallet formats depending on your needs.

## 1. Miner ID Wallets (Current Standard)

The majority of active miners and GUI wallets currently use a **32-character Hex ID**. This ID is derived from a SHA256 hash and serves as both your identity on the network and your wallet address.

### Creating a Miner ID
1. Run the RustChain miner for the first time.
2. The miner will generate a unique `miner_id` based on your hardware fingerprint.
3. This ID is saved locally (usually in a `.miner_id` file).

### Checking Balance
You can check your balance via the web explorer or API:
```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_ID"
```

---

## 2. Compatibility CLI Wallet

If you need a command-line tool to manage balances and send RTC without running a full miner, you can use the `rustchain_cli_wallet.py` tool (found in the `tools/` directory).

### Setup
```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/tools
pip install requests
```

### Usage

**Create a new wallet:**
```bash
python3 rustchain_cli_wallet.py create
```
*Note: This generates a random 32-char hex ID. Save this ID!*

**Check balance:**
```bash
python3 rustchain_cli_wallet.py balance --miner-id YOUR_ID
```

**Send RTC:**
```bash
python3 rustchain_cli_wallet.py send --from-id YOUR_ID --to-id RECIPIENT_ID --amount 10.0
```

---

## 3. Secure Wallets (Founder Edition)

*Note: This format is currently being transitioned. The required `rustchain_crypto` module is pending release in the main repository.*

The Secure Wallet format uses **Ed25519** keypairs and **BIP39** seed phrases (12-24 words). 

### Benefits
- Hierarchical Deterministic (HD) structure.
- Industry-standard security (similar to Solana/Polkadot).
- Supports offline signing.

### Transition Status
Once `rustchain_crypto.py` is available, existing Miner ID wallets can be linked to Secure Wallets for enhanced protection.

---

## 4. BoTTube Wallet Integration

BoTTube (the AI video platform) uses RustChain for tipping and creator rewards.

- **Rewards:** Uploading videos and reaching milestones earns RTC.
- **Tipping:** Viewers can tip creators directly in RTC.
- **Withdrawal:** You can link your BoTTube profile to your RustChain Miner ID to withdraw earnings.

---

## 5. Security Best Practices

1. **Protect your ID:** Your 32-char Hex ID is effectively your private key for current miners. Do not share it publicly unless you only want to receive funds.
2. **Hardware Binding:** Miner IDs are often bound to hardware fingerprints. If you move your wallet to a new machine, ensure you use the same ID to keep your balance.
3. **Pending Window:** All RTC transfers have a **24-hour pending window** for security and anti-fraud verification before they are finalized.
