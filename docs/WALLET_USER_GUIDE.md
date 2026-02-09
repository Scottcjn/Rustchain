# RustChain Wallet User Guide

Complete guide for managing RTC tokens using RustChain wallets.

---

## Table of Contents

- [Overview](#overview)
- [Wallet Types](#wallet-types)
- [Installation](#installation)
- [Creating a Wallet](#creating-a-wallet)
- [Securing Your Wallet](#securing-your-wallet)
- [Checking Balance](#checking-balance)
- [Sending RTC](#sending-rtc)
- [Receiving RTC](#receiving-rtc)
- [Transaction History](#transaction-history)
- [Backup & Recovery](#backup--recovery)
- [Advanced Features](#advanced-features)
- [Troubleshooting](#troubleshooting)

---

## Overview

RustChain wallets store your RTC tokens and allow you to:
- ✅ Check your balance
- ✅ Send RTC to other wallets
- ✅ Receive RTC from miners or other users
- ✅ View transaction history
- ✅ Backup and restore with seed phrases

**Wallet Format**: `<name>_<hash>_RTC` (e.g., `powerbook_g4_a1b2c3d4_RTC`)

---

## Wallet Types

### 1. Secure Founder Wallet (Recommended)

**Location**: `wallet/rustchain_wallet_secure.py`

**Features**:
- 24-word BIP39 seed phrases
- Password-encrypted keystore
- Ed25519 cryptographic signatures
- Multiple wallet support
- Transaction history
- GUI interface

**Best for**: Long-term storage, high-value holdings

### 2. Simple GUI Wallet

**Location**: `wallet/rustchain_wallet_gui.py`

**Features**:
- Simple balance checking
- Send/receive RTC
- Transaction history
- Dark theme UI

**Best for**: Everyday use, beginners

### 3. PowerPC Wallet

**Location**: `wallet/rustchain_wallet_ppc.py`

**Features**:
- Python 2.5 compatible
- Lightweight
- Command-line interface

**Best for**: Vintage PowerPC Macs (G3/G4/G5)

### 4. Command-Line Wallet

**Location**: Use `curl` commands directly

**Features**:
- No installation required
- Works on any platform
- Scriptable

**Best for**: Automation, servers, minimal systems

---

## Installation

### Secure Founder Wallet

**Prerequisites**:
```bash
# Install Python 3.8+
sudo apt install python3 python3-pip python3-tk  # Linux
brew install python3 python-tk  # macOS

# Install dependencies
pip install requests urllib3 pynacl tkinter
```

**Download wallet**:
```bash
cd ~/Rustchain/wallet
python3 rustchain_wallet_secure.py
```

### Simple GUI Wallet

```bash
cd ~/Rustchain/wallet
pip install requests urllib3 tkinter
python3 rustchain_wallet_gui.py
```

### PowerPC Wallet

```bash
cd ~/Rustchain/wallet
python rustchain_wallet_ppc.py
```

---

## Creating a Wallet

### Method 1: Secure Founder Wallet (GUI)

1. **Launch wallet**:
   ```bash
   python3 rustchain_wallet_secure.py
   ```

2. **Click "Create New Wallet"**

3. **Enter wallet name**:
   ```
   Wallet name: my-wallet
   ```

4. **Set password**:
   ```
   Password: ********
   Confirm: ********
   ```

5. **Save seed phrase** (CRITICAL!):
   ```
   Your 24-word seed phrase:
   
   abandon ability able about above absent absorb abstract
   absurd abuse access accident account accuse achieve acid
   acoustic acquire across act action actor actress actual
   
   ⚠️  Write this down and store securely!
   ⚠️  Anyone with this phrase can access your wallet!
   ```

6. **Wallet created**:
   ```
   ✅ Wallet created: my-wallet_a1b2c3d4_RTC
   Balance: 0.00 RTC
   ```

### Method 2: Command-Line

```python
#!/usr/bin/env python3
from nacl.signing import SigningKey
import hashlib

# Generate Ed25519 keypair
signing_key = SigningKey.generate()
verify_key = signing_key.verify_key

# Create wallet ID
pubkey_hash = hashlib.sha256(verify_key.encode()).hexdigest()[:40]
wallet_id = f"my-wallet_{pubkey_hash[:8]}_RTC"

print(f"Wallet ID: {wallet_id}")
print(f"Private Key: {signing_key.encode().hex()}")
print(f"Public Key: {verify_key.encode().hex()}")
print("\n⚠️  Save your private key securely!")
```

### Method 3: Miner Auto-Generation

When you run a miner for the first time, it automatically generates a wallet:

```bash
python3 rustchain_linux_miner.py --wallet my-miner
```

**Output**:
```
Wallet: my-miner_RTC
⚠️  Wallet auto-generated. Check ~/.rustchain/ for keystore.
```

---

## Securing Your Wallet

### Seed Phrase Security

**DO**:
- ✅ Write seed phrase on paper
- ✅ Store in fireproof safe
- ✅ Make multiple copies in different locations
- ✅ Consider metal backup (fire/water resistant)
- ✅ Never share with anyone

**DON'T**:
- ❌ Store seed phrase digitally (no photos, no cloud)
- ❌ Email or message seed phrase
- ❌ Store on computer or phone
- ❌ Share with anyone claiming to be "support"

### Password Best Practices

- Use 12+ characters
- Mix uppercase, lowercase, numbers, symbols
- Don't reuse passwords
- Use password manager (1Password, Bitwarden)

### Keystore Location

**Default paths**:
- Linux/macOS: `~/.rustchain/wallets/`
- Windows: `%USERPROFILE%\.rustchain\wallets\`

**Permissions**:
```bash
chmod 600 ~/.rustchain/wallets/*.enc
```

### Two-Factor Authentication

RustChain uses Ed25519 signatures as "something you have" (private key). For additional security:

1. **Encrypt keystore** with strong password ("something you know")
2. **Store backup** in separate location ("something you have")

---

## Checking Balance

### Method 1: GUI Wallet

1. Launch wallet
2. Enter wallet name
3. Click "Check Balance"

**Display**:
```
Balance: 12.456789 RTC
Last Updated: 2026-02-09 14:23:45
```

### Method 2: Command-Line (curl)

```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_ID"
```

**Example**:
```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=powerbook_g4_RTC"
```

**Response**:
```json
{
  "miner_id": "powerbook_g4_RTC",
  "balance_rtc": 12.456789,
  "balance_urtc": 12456789,
  "last_updated": "2026-02-09T14:23:45Z"
}
```

### Method 3: Python Script

```python
import requests
import urllib3

urllib3.disable_warnings()

def check_balance(wallet_id):
    response = requests.get(
        "https://50.28.86.131/wallet/balance",
        params={"miner_id": wallet_id},
        verify=False
    )
    data = response.json()
    return data["balance_rtc"]

balance = check_balance("powerbook_g4_RTC")
print(f"Balance: {balance} RTC")
```

---

## Sending RTC

### Method 1: Secure Founder Wallet (GUI)

1. **Launch wallet and unlock**
2. **Click "Send RTC"**
3. **Enter details**:
   ```
   To Address: recipient_wallet_RTC
   Amount: 5.0
   ```
4. **Review transaction**:
   ```
   From: my-wallet_RTC
   To: recipient_wallet_RTC
   Amount: 5.0 RTC
   Fee: 0.0 RTC (no fees!)
   ```
5. **Click "Send"**
6. **Transaction submitted**:
   ```
   ✅ Transaction successful!
   TX Hash: a1b2c3d4e5f6...
   New Balance: 7.456789 RTC
   ```

### Method 2: Python Script

```python
import requests
import time
from nacl.signing import SigningKey
import base64
import urllib3

urllib3.disable_warnings()

def send_rtc(from_wallet, to_address, amount_rtc, private_key_hex):
    """Send RTC to another wallet."""
    
    # Load private key
    private_key = bytes.fromhex(private_key_hex)
    signing_key = SigningKey(private_key)
    
    # Create transaction
    nonce = int(time.time())
    message = f"{from_wallet}{to_address}{amount_rtc}{nonce}"
    
    # Sign transaction
    signature = signing_key.sign(message.encode()).signature
    public_key = signing_key.verify_key.encode()
    
    # Submit transaction
    payload = {
        "from_address": from_wallet,
        "to_address": to_address,
        "amount_rtc": amount_rtc,
        "nonce": nonce,
        "signature": base64.b64encode(signature).decode(),
        "public_key": base64.b64encode(public_key).decode()
    }
    
    response = requests.post(
        "https://50.28.86.131/wallet/transfer/signed",
        json=payload,
        verify=False
    )
    
    return response.json()

# Example
result = send_rtc(
    from_wallet="my-wallet_RTC",
    to_address="recipient_wallet_RTC",
    amount_rtc=5.0,
    private_key_hex="your-private-key-hex"
)

if result["ok"]:
    print(f"✅ Sent {result['amount_rtc']} RTC")
    print(f"TX Hash: {result['tx_hash']}")
else:
    print(f"❌ Error: {result['error']}")
```

### Transaction Fees

**RustChain has ZERO transaction fees!** 🎉

All transfers are free, regardless of amount.

---

## Receiving RTC

### Share Your Wallet Address

Your wallet address is your wallet ID:
```
powerbook_g4_a1b2c3d4_RTC
```

**Share via**:
- Text message
- Email
- QR code (generate with any QR code tool)

### Monitor Incoming Transactions

**Method 1: GUI Wallet**
- Balance updates automatically
- Transaction history shows incoming transfers

**Method 2: Command-Line**
```bash
# Check balance periodically
watch -n 60 'curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET"'
```

**Method 3: Python Script**
```python
import time
import requests
import urllib3

urllib3.disable_warnings()

def monitor_wallet(wallet_id, interval=60):
    """Monitor wallet for incoming transactions."""
    last_balance = 0
    
    while True:
        response = requests.get(
            "https://50.28.86.131/wallet/balance",
            params={"miner_id": wallet_id},
            verify=False
        )
        
        balance = response.json()["balance_rtc"]
        
        if balance > last_balance:
            received = balance - last_balance
            print(f"✅ Received {received} RTC! New balance: {balance} RTC")
        
        last_balance = balance
        time.sleep(interval)

monitor_wallet("powerbook_g4_RTC", interval=60)
```

---

## Transaction History

### Method 1: GUI Wallet

1. Launch wallet
2. Click "Transaction History"
3. View recent transactions:
   ```
   2026-02-09 14:30:00  Sent      5.0 RTC  → recipient_wallet_RTC
   2026-02-09 12:15:00  Received  1.5 RTC  ← epoch_settlement
   2026-02-08 14:30:00  Sent      2.0 RTC  → another_wallet_RTC
   ```

### Method 2: API Call

```bash
curl -sk "https://50.28.86.131/wallet/transactions/YOUR_WALLET_ID?limit=50"
```

**Response**:
```json
{
  "transactions": [
    {
      "tx_id": "a1b2c3d4e5f6...",
      "type": "send",
      "from_address": "my-wallet_RTC",
      "to_address": "recipient_wallet_RTC",
      "amount_rtc": 5.0,
      "timestamp": "2026-02-09T14:30:00Z",
      "signature": "..."
    },
    {
      "tx_id": "g7h8i9j0k1l2...",
      "type": "receive",
      "from_address": "epoch_settlement",
      "to_address": "my-wallet_RTC",
      "amount_rtc": 1.5,
      "timestamp": "2026-02-09T12:15:00Z"
    }
  ],
  "total": 234,
  "limit": 50
}
```

---

## Backup & Recovery

### Backup Seed Phrase

**When creating wallet**:
1. Write down 24-word seed phrase
2. Store in safe location
3. Make multiple copies
4. Test recovery before funding wallet

**Seed phrase example**:
```
abandon ability able about above absent absorb abstract
absurd abuse access accident account accuse achieve acid
acoustic acquire across act action actor actress actual
```

### Backup Keystore File

**Location**: `~/.rustchain/wallets/my-wallet.enc`

**Backup**:
```bash
# Copy to USB drive
cp ~/.rustchain/wallets/my-wallet.enc /media/usb/

# Copy to cloud (encrypted!)
gpg --encrypt ~/.rustchain/wallets/my-wallet.enc
cp ~/.rustchain/wallets/my-wallet.enc.gpg ~/Dropbox/
```

### Recover from Seed Phrase

**Secure Founder Wallet**:
1. Launch wallet
2. Click "Restore from Seed"
3. Enter 24-word seed phrase
4. Set new password
5. Wallet restored!

**Python Script**:
```python
from nacl.signing import SigningKey
from mnemonic import Mnemonic
import hashlib

def restore_from_seed(seed_phrase):
    """Restore wallet from BIP39 seed phrase."""
    mnemo = Mnemonic("english")
    
    # Validate seed phrase
    if not mnemo.check(seed_phrase):
        raise ValueError("Invalid seed phrase")
    
    # Derive seed
    seed = mnemo.to_seed(seed_phrase)
    
    # Generate keypair from seed
    signing_key = SigningKey(seed[:32])
    verify_key = signing_key.verify_key
    
    # Create wallet ID
    pubkey_hash = hashlib.sha256(verify_key.encode()).hexdigest()[:40]
    wallet_id = f"restored_{pubkey_hash[:8]}_RTC"
    
    return {
        "wallet_id": wallet_id,
        "private_key": signing_key.encode(),
        "public_key": verify_key.encode()
    }

# Example
seed = "abandon ability able about above absent absorb abstract absurd abuse access accident account accuse achieve acid acoustic acquire across act action actor actress actual"
wallet = restore_from_seed(seed)
print(f"Restored wallet: {wallet['wallet_id']}")
```

### Recover from Keystore

```python
from nacl.secret import SecretBox
from nacl.hash import blake2b
import json
import base64

def restore_from_keystore(filepath, password):
    """Restore wallet from encrypted keystore."""
    # Derive key from password
    key = blake2b(password.encode(), digest_size=32, encoder=base64.b64encode)
    box = SecretBox(base64.b64decode(key))
    
    # Load and decrypt
    with open(filepath, 'rb') as f:
        encrypted = f.read()
    
    decrypted = box.decrypt(encrypted)
    wallet_data = json.loads(decrypted)
    
    return {
        "wallet_id": wallet_data["miner_id"],
        "private_key": base64.b64decode(wallet_data["private_key"]),
        "public_key": base64.b64decode(wallet_data["public_key"])
    }

# Example
wallet = restore_from_keystore("~/.rustchain/wallets/my-wallet.enc", "password")
print(f"Restored wallet: {wallet['wallet_id']}")
```

---

## Advanced Features

### Multiple Wallets

**Secure Founder Wallet** supports multiple wallets:

1. Click "Switch Wallet"
2. Select from list or create new
3. Each wallet has separate balance and history

### Export Private Key

**⚠️  WARNING: Never share your private key!**

```python
from nacl.signing import SigningKey

# Load wallet
wallet = load_wallet("~/.rustchain/my-wallet.enc", "password")

# Export private key
private_key_hex = wallet["private_key"].hex()
print(f"Private Key: {private_key_hex}")
print("\n⚠️  Keep this secret! Anyone with this key can access your funds!")
```

### Import Private Key

```python
from nacl.signing import SigningKey
import hashlib

def import_private_key(private_key_hex, name="imported"):
    """Import wallet from private key."""
    private_key = bytes.fromhex(private_key_hex)
    signing_key = SigningKey(private_key)
    verify_key = signing_key.verify_key
    
    # Create wallet ID
    pubkey_hash = hashlib.sha256(verify_key.encode()).hexdigest()[:40]
    wallet_id = f"{name}_{pubkey_hash[:8]}_RTC"
    
    return {
        "wallet_id": wallet_id,
        "private_key": private_key,
        "public_key": verify_key.encode()
    }

# Example
wallet = import_private_key("your-private-key-hex", "imported-wallet")
print(f"Imported wallet: {wallet['wallet_id']}")
```

### Batch Transfers

```python
def send_batch(from_wallet, recipients, private_key_hex):
    """Send RTC to multiple recipients.
    
    Args:
        from_wallet: Sender wallet ID
        recipients: List of (address, amount) tuples
        private_key_hex: Sender's private key
    
    Returns:
        List of transaction results
    """
    results = []
    
    for to_address, amount in recipients:
        result = send_rtc(from_wallet, to_address, amount, private_key_hex)
        results.append(result)
        time.sleep(1)  # Rate limiting
    
    return results

# Example
recipients = [
    ("wallet1_RTC", 1.0),
    ("wallet2_RTC", 2.0),
    ("wallet3_RTC", 3.0)
]

results = send_batch("my-wallet_RTC", recipients, "private-key-hex")

for i, result in enumerate(results):
    if result["ok"]:
        print(f"✅ Transfer {i+1}: {result['amount_rtc']} RTC sent")
    else:
        print(f"❌ Transfer {i+1} failed: {result['error']}")
```

---

## Troubleshooting

### "Wallet not found" Error

**Cause**: Wallet has no balance record on chain

**Solution**: 
- Wallet exists but has 0 balance
- Mine or receive RTC to activate wallet

### "Invalid signature" Error

**Cause**: Transaction signature verification failed

**Solutions**:
1. Check private key is correct
2. Ensure nonce is current timestamp
3. Verify message format: `from+to+amount+nonce`

### "Insufficient balance" Error

**Cause**: Trying to send more RTC than available

**Solution**:
```bash
# Check balance
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET"

# Send less than balance
```

### "Nonce reused" Error

**Cause**: Replay protection detected duplicate nonce

**Solution**:
- Use current timestamp as nonce
- Wait 1 second between transactions
- Don't resubmit failed transactions

### Lost Password

**If you have seed phrase**:
1. Restore wallet from seed phrase
2. Set new password

**If you don't have seed phrase**:
- ❌ Wallet is permanently inaccessible
- This is why seed phrase backup is critical!

### Corrupted Keystore

**If you have seed phrase**:
1. Delete corrupted keystore
2. Restore from seed phrase

**If you have backup keystore**:
1. Delete corrupted file
2. Copy backup to `~/.rustchain/wallets/`

---

## Best Practices

### Security
- ✅ Always backup seed phrase
- ✅ Use strong passwords
- ✅ Never share private keys
- ✅ Verify recipient addresses
- ✅ Test with small amounts first

### Backups
- ✅ Multiple copies of seed phrase
- ✅ Store in different locations
- ✅ Test recovery process
- ✅ Update backups after changes

### Transactions
- ✅ Double-check recipient address
- ✅ Verify amount before sending
- ✅ Keep transaction records
- ✅ Monitor balance regularly

---

## Additional Resources

- **API Reference**: `docs/API_REFERENCE.md`
- **Python SDK Tutorial**: `docs/PYTHON_SDK_TUTORIAL.md`
- **Miner Setup Guide**: `docs/MINER_SETUP_GUIDE.md`
- **Community Support**: [GitHub Discussions](https://github.com/Scottcjn/Rustchain/discussions)

---

**Last Updated**: February 9, 2026  
**Wallet Version**: 1.0
