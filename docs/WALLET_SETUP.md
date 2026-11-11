# RustChain Wallet Setup Guide

A complete guide to creating, using, and managing your RustChain wallet.

---

## 1. Quick Start: Create Your First Wallet

You have three options:

1. **Automatic (via miner installer):** Creates a lightweight wallet file during installation.
2. **Interactive GUI / Desktop:** Generates a secure BIP39 24-word seed phrase wallet.
3. **Programmatic / CLI:** Generates keypairs directly via Python or JavaScript SDK.

---

## 2. Option A: Create a Wallet via the Miner Installer

The easiest way to start mining:

```bash
curl -sL https://rustchain.org/install.sh | bash
```

What happens next:

1. The installer checks your machine and downloads the Python miner.
2. It asks for a wallet ID.
3. You can type your own wallet ID, or press Enter to let RustChain auto-generate one.
4. At the end, the installer prints your wallet ID on screen.

Example wallet IDs:

- `victus-x86-scott`
- `RTC14f06ee294f327f5685d3de5e1ed501cffab33e7`

On Linux, the location of the miner config depends on how you installed:

- **Automated one-liner (`rustchain.org/install.sh` / `scripts/install.sh`):** `/opt/rustchain-miner/config.json`
- **Repository installer (`setup.sh` / `INSTALL.md`):** `~/.rustchain/config.json`

To read your config regardless of which installer was used:

```bash
cat /opt/rustchain-miner/config.json 2>/dev/null || cat ~/.rustchain/config.json
```

You should see a `wallet_id` field.

Example:

```json
{
  "wallet_id": "victus-x86-scott",
  "node_url": "https://rustchain.org"
}
```

This method is best if your goal is:

- Start mining immediately
- Avoid managing private keys or seed phrases right away
- Use a simple public name on the network

---

## 3. Option B: Create a Secure BIP39 Wallet (GUI / Desktop)

If you want full custody of your keys and plan to receive, hold, or transfer RTC:

1. Open the RustChain desktop application.
2. Click **Create New Wallet**.
3. Choose a password to encrypt your wallet on disk.
4. The app generates a **24-word BIP39 seed phrase**.
5. Write down the 24 words in exact order on paper. Keep it offline.
6. Verify your seed phrase by re-entering the requested words.
7. Your new public address (`RTC...`) is displayed.

---

## 4. Option C: Create a Wallet via CLI / SDK

### Python SDK

```bash
pip install rustchain
rustchain wallet create
```

Or using Python code:

```python
from rustchain_sdk import RustChainWallet

wallet = RustChainWallet.create(strength=256) # 24 words
print("Address:", wallet.address)
print("Seed phrase:", " ".join(wallet.seed_phrase))
```

---

## 5. Security basics

### Back up your wallet

What to back up depends on how you created it:

- Miner install: save the printed wallet ID and copy your config file (`/opt/rustchain-miner/config.json` or `~/.rustchain/config.json` depending on the installer)
- Secure GUI: back up the 24-word seed phrase and `~/.rustchain/wallets/*.json`
- Programmatic wallet: back up the seed phrase and any encrypted keystore you create

### Never share your private key

Never send anyone:

- Your private key hex
- Your seed phrase
- Your wallet password
- Your encrypted keystore file unless you fully trust the destination and know why you are doing it

### Wallet name vs private key

Public information:

- Miner ID
- `RTC...` address

Secret information:

- Seed phrase
- Private key
- Password used to unlock your encrypted wallet

You can safely post your public wallet in a PR comment for bounty payment.
You must never post your seed phrase or private key.

## 6. Common questions

### Where is my wallet stored?

Usually here:

- Miner install: `/opt/rustchain-miner/config.json` (from `install.sh`) or `~/.rustchain/config.json` (from `setup.sh`)
- Running Linux miner: sometimes also `/tmp/local_miner_wallet.txt`
- Secure GUI and CLI keystores: `~/.rustchain/wallets/`
- Programmatic wallet: wherever you saved it

### I lost my wallet name

Try these in order:

```bash
cat /opt/rustchain-miner/config.json 2>/dev/null || cat ~/.rustchain/config.json
ls ~/.rustchain/wallets
curl -sk https://rustchain.org/api/miners
```

If you still have the secure wallet keystore or seed phrase, you can usually recover the public `RTC...` address.
If you lost the seed phrase and private key for a self-custody wallet, nobody can recover the funds for you.

### Why is my balance zero?

Common reasons:

- You queried the wrong wallet ID
- Your miner has not finished a reward cycle yet
- Your miner is not showing up in `/api/miners`
