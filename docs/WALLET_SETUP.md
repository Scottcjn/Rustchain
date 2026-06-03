# RustChain Wallet Setup for Beginners

This guide is for someone who has never used crypto before.

RustChain uses **RTC** as its native token. A common reference rate in the project docs is **1 RTC = $0.10 USD**. The network has already reached **500 wallet holders**, and code bounties commonly pay **1 to 400 RTC** depending on difficulty.

## First: understand what "wallet" means on RustChain

On RustChain, you will see two public wallet styles:

- A human-readable miner ID, such as `victus-x86-scott`
- An Ed25519-backed RustChain address, such as `RTC14f06ee294f327f5685d3de5e1ed501cffab33e7`

Both can show up in balance lookups and mining rewards.

Important difference:

- A **miner ID** is a public identifier used by the miner and explorer
- An **RTC... address** is a public identifier backed by a private key and can be used for **signed transfers**

If you only want to start mining, the auto-generated miner wallet is enough.
If you want to **send RTC yourself**, create or restore an **Ed25519-backed `RTC...` wallet**.

## Network and API endpoints

These are the main RustChain endpoints used in this guide:

- Health: `https://rustchain.org/health`
- Active miners: `https://rustchain.org/api/miners`
- Current epoch: `https://rustchain.org/epoch`
- Wallet balance: `https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET`
- Explorer: `https://rustchain.org/explorer/`

Use `curl -sk` because the public node uses a self-signed TLS certificate.

## 1. Three ways to get an RTC wallet

### Method A: install the miner and let RustChain create one for you

This is the fastest way to get started.

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

On Linux, the installer saves the miner config here:

```bash
cat /opt/rustchain-miner/config.json
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

- Start mining quickly
- Receive epoch rewards automatically
- Get a wallet ID without learning signatures first

### Method B: use the wallet GUI

If you want a visual wallet, use the RustChain wallet GUI from the repo.

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
python3 -m pip install requests
python3 wallet/rustchain_wallet_gui.py
```

In the GUI:

1. Click `New Wallet`
2. Save the wallet ID it creates
3. Use `Load` later to reopen it
4. Use the balance panel to refresh your RTC amount

Important note:

- `wallet/rustchain_wallet_gui.py` is the simple GUI wallet
- If your checkout includes `wallet/rustchain_wallet_secure.py`, prefer that for real funds because it uses encrypted keystores and seed phrase backup

Run the secure GUI like this:

```bash
python3 wallet/rustchain_wallet_secure.py
```

The secure GUI stores encrypted wallet files here:

```bash
ls ~/.rustchain/wallets
```

### Method C: create one programmatically with the Python wallet and crypto module

If you are comfortable running Python, this is the easiest self-custody path.

Install the official Python SDK:

```bash
python3 -m pip install rustchain
```

Create a wallet:

```bash
python3 - <<'PY'
from rustchain_sdk import RustChainWallet

wallet = RustChainWallet.create(strength=256)  # 24-word wallet
print("Address:", wallet.address)
print("Public key:", wallet.public_key_hex)
print("Seed phrase:", " ".join(wallet.seed_phrase))
PY
```

What to save immediately:

- The `RTC...` address
- The 24-word seed phrase
- The private key only if you know how to protect it

## 2. How to check your balance

### Method 1: curl

This is the most direct balance check:

```bash
curl -sk 'https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET'
```

Example:

```bash
curl -sk 'https://rustchain.org/wallet/balance?miner_id=victus-x86-scott'
```

Typical response:

```json
{
  "amount_i64": 266673241,
  "amount_rtc": 266.673241,
  "miner_id": "victus-x86-scott"
}
```

### Method 2: explorer

Open the explorer:

```text
https://rustchain.org/explorer/
```

Use it like this:

1. Look at `Active Attestations`
2. Find your miner ID or `RTC...` address in the list
3. Confirm your machine is live on the network
4. For the exact numeric balance, open the balance endpoint in your browser:

```text
https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET
```

The explorer is the best visual way to confirm that your miner is online. The balance endpoint is the exact numeric source of truth.

### Method 3: wallet GUI

In the GUI wallet:

1. Enter your wallet ID or load your saved wallet
2. Click `Load` or `Refresh`
3. Read the balance shown in the balance panel

The GUI is easier if you do not want to use the terminal.

## 3. How to receive RTC

### Option 1: mine it

Mining is automatic once your miner is installed and online.

Useful checks:

```bash
curl -sk https://rustchain.org/health
curl -sk https://rustchain.org/api/miners
curl -sk https://rustchain.org/epoch
```

What to expect:

- The miner appears in `/api/miners`
- RustChain pays mining rewards every epoch
- Current public docs describe epochs as roughly 10-minute reward cycles

### Option 2: earn bounties

RustChain pays RTC for code contributions.

Typical payout flow:

1. Pick a bounty issue
2. Submit a pull request
3. Get the PR reviewed and merged
4. Share your wallet address when asked, or include it in the PR description
5. Receive RTC from the community fund

Typical reward sizes:

- Small docs/tests: `1-10 RTC`
- Standard work: `20-50 RTC`
- Major work: `75-150 RTC`
- Critical or special security work: up to `400 RTC`

### Option 3: receive a transfer from another wallet

To receive RTC, share your **public wallet only**:

- A miner ID like `victus-x86-scott`, or
- An `RTC...` address like `RTC14f06ee294f327f5685d3de5e1ed501cffab33e7`

Never share your seed phrase or private key.

## 4. How to send RTC

### Before you send: know which wallet type you have

If your wallet is only a simple miner ID, you can mine to it and receive funds there.
But **public signed transfers require an Ed25519-backed `RTC...` wallet**.
A readable miner ID like `victus-x86-scott` is not enough by itself for `POST /wallet/transfer/signed`.

If you plan to send RTC yourself, use:

- The secure GUI wallet, or
- A programmatic `RTC...` wallet created from the Python SDK

### Method 1: send with the secure wallet GUI

If you are using `wallet/rustchain_wallet_secure.py`:

1. Load your wallet from `~/.rustchain/wallets`
2. Copy and paste the recipient `RTC...` address
3. Enter the amount
4. Optionally add a memo
5. Enter your wallet password
6. Click `SIGN & SEND`

Under the hood, the GUI signs your transfer and posts it to:

```text
POST https://rustchain.org/wallet/transfer/signed
```

### Method 2: send via the signed transfer API

You cannot safely send RTC with plain `curl` alone because the transfer must be signed first.

Install the required Python packages:

```bash
python3 -m pip install pynacl requests
```

Then run:

```bash
python3 - <<'PY'
import hashlib
import json
import time
import requests
from nacl.signing import SigningKey

NODE_URL = "https://rustchain.org"
PRIVATE_KEY_HEX = "YOUR_PRIVATE_KEY_HEX"
TO_ADDRESS = "RTC_RECIPIENT_ADDRESS"
AMOUNT_RTC = 1.0
MEMO = "First RustChain transfer"
NONCE = int(time.time())

signing_key = SigningKey(bytes.fromhex(PRIVATE_KEY_HEX))
public_key_hex = signing_key.verify_key.encode().hex()
from_address = "RTC" + hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()[:40]

canonical = {
    "from": from_address,
    "to": TO_ADDRESS,
    "amount": AMOUNT_RTC,
    "memo": MEMO,
    "nonce": str(NONCE),
}

message = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
signature_hex = signing_key.sign(message).signature.hex()

payload = {
    "from_address": from_address,
    "to_address": TO_ADDRESS,
    "amount_rtc": AMOUNT_RTC,
    "memo": MEMO,
    "nonce": NONCE,
    "chain_id": "rustchain-mainnet-v2",
    "public_key": public_key_hex,
    "signature": signature_hex,
}

resp = requests.post(
    f"{NODE_URL}/wallet/transfer/signed",
    json=payload,
    verify=False,
    timeout=15,
)

print(resp.status_code)
print(resp.json())
PY
```

### Why Ed25519 signatures matter

RustChain requires Ed25519 signatures so the network can verify:

- You really own the wallet you are sending from
- Nobody changed the amount or destination after you signed
- The transfer is tied to a unique nonce, which helps block replay attacks

If someone knows only your public wallet name, they still cannot send your funds without your private key.

## 5. Security basics

### Back up your wallet

What to back up depends on how you created it:

- Miner install: save the printed wallet ID and copy `/opt/rustchain-miner/config.json`
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

- Miner install: `/opt/rustchain-miner/config.json`
- Running Linux miner: sometimes also `/tmp/local_miner_wallet.txt`
- Secure GUI and CLI keystores: `~/.rustchain/wallets/`
- Programmatic wallet: wherever you saved it

### I lost my wallet name

Try these in order:

```bash
cat /opt/rustchain-miner/config.json
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
- The wallet is brand new and has never received RTC
- You are checking a human-readable miner ID, but your funds are in a separate `RTC...` wallet, or the other way around

Quick checks:

```bash
curl -sk https://rustchain.org/health
curl -sk https://rustchain.org/api/miners
curl -sk 'https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET'
```

### How long until I earn RTC?

For mining:

- Your miner must attest successfully
- Your miner must stay online through a reward cycle
- RustChain then credits rewards at epoch settlement

In current public docs, epochs are described as roughly **10 minutes**. If you just started, give it at least one full epoch before assuming something is wrong.

For bounties:

- Payment happens after review and merge
- You usually receive funds after you share your wallet address with the maintainers

## Quick start if you want the shortest possible path

1. Install the miner:

```bash
curl -sL https://rustchain.org/install.sh | bash
```

2. Copy the wallet ID shown at the end.

3. Check your balance:

```bash
curl -sk 'https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET'
```

4. Confirm you are live:

```bash
curl -sk https://rustchain.org/api/miners
curl -sk https://rustchain.org/epoch
```

5. If you later want to send RTC yourself, create a secure `RTC...` wallet with the secure GUI or the Python wallet module.
