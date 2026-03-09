# RustChain First API Calls — Quickstart Guide

**Bounty #1494** — Verified walkthrough for developers making their first RustChain API calls.

---

## Prerequisites

- `curl` (command-line HTTP client)
- Python 3.8+ (for signed transfer example)
- Network access to `https://rustchain.org` (or test node `https://50.28.86.131`)

> **Note:** The node uses a self-signed TLS certificate. Use `-k` (insecure) flag with `curl` or `verify=False` in Python requests.

---

## Step 1: Health Check

Verify the node is online and healthy.

### cURL

```bash
curl -sk https://rustchain.org/health | python3 -m json.tool
```

### Expected Response

```json
{
    "ok": true,
    "version": "2.2.1-rip200",
    "uptime_s": 123456,
    "db_rw": true,
    "tip_age_slots": 0
}
```

### Python

```python
import requests

response = requests.get("https://rustchain.org/health", verify=False)
print(response.json())
```

---

## Step 2: Get Epoch Info

Query the current epoch, slot, and enrolled miners.

### cURL

```bash
curl -sk https://rustchain.org/epoch | python3 -m json.tool
```

### Expected Response

```json
{
    "epoch": 95,
    "slot": 12345,
    "blocks_per_epoch": 144,
    "epoch_pot": 1.5,
    "enrolled_miners": 10,
    "slot_progress": 0.45,
    "seconds_remaining": 300
}
```

### Python

```python
import requests

response = requests.get("https://rustchain.org/epoch", verify=False)
epoch = response.json()
print(f"Epoch: {epoch['epoch']}, Slot: {epoch['slot']}, Miners: {epoch['enrolled_miners']}")
```

---

## Step 3: List Active Miners

Get the list of all active miners with their hardware details.

### cURL

```bash
curl -sk https://rustchain.org/api/miners | python3 -m json.tool
```

### Expected Response (Array)

```json
[
    {
        "miner": "miner_id_1",
        "hardware_type": "NVIDIA RTX 4090",
        "antiquity_multiplier": 1.5,
        "last_heartbeat": 1234567890
    },
    {
        "miner": "miner_id_2",
        "hardware_type": "AMD RX 7900 XTX",
        "antiquity_multiplier": 1.2,
        "last_heartbeat": 1234567885
    }
]
```

### Python

```python
import requests

response = requests.get("https://rustchain.org/api/miners", verify=False)
miners = response.json()
print(f"Active miners: {len(miners)}")
for miner in miners[:3]:
    print(f"  - {miner['miner']}: {miner['hardware_type']}")
```

---

## Step 4: Hall of Fame

Get the top contributors and miners.

### cURL

```bash
curl -sk https://rustchain.org/api/hall_of_fame | python3 -m json.tool
```

### Expected Response

```json
{
    "top_miners": [...],
    "top_contributors": [...],
    "epoch_leaders": [...]
}
```

---

## Step 5: Fee Pool Info

Check the current fee pool status.

### cURL

```bash
curl -sk https://rustchain.org/api/fee_pool | python3 -m json.tool
```

### Expected Response

```json
{
    "total_fees": 1234.56,
    "pending_claims": 10,
    "last_distribution": 1234567890
}
```

---

## Step 6: Check Wallet Balance

Query the balance of a specific wallet.

### cURL

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=scott" | python3 -m json.tool
```

### Expected Response

```json
{
    "ok": true,
    "miner_id": "scott",
    "amount_rtc": 155.0,
    "amount_i64": 155000000
}
```

### Python

```python
import requests

miner_id = "scott"
response = requests.get(
    "https://rustchain.org/wallet/balance",
    params={"miner_id": miner_id},
    verify=False
)
data = response.json()
if data.get("ok"):
    print(f"Balance: {data['amount_rtc']} RTC")
else:
    print(f"Wallet not found or error: {data}")
```

---

## Complete Python Example

Here's a script that tests all the basic endpoints:

```python
#!/usr/bin/env python3
"""RustChain First API Calls — Complete Example"""

import requests

NODE_URL = "https://rustchain.org"
VERIFY_SSL = False

def main():
    session = requests.Session()
    session.verify = VERIFY_SSL
    
    print("=" * 60)
    print("RustChain First API Calls")
    print("=" * 60)
    
    # 1. Health Check
    print("\n1. Health Check")
    response = session.get(f"{NODE_URL}/health", timeout=10)
    health = response.json()
    print(f"   Status: {'✓ Online' if health.get('ok') else '✗ Offline'}")
    print(f"   Version: {health.get('version', 'unknown')}")
    
    # 2. Epoch Info
    print("\n2. Epoch Info")
    response = session.get(f"{NODE_URL}/epoch", timeout=10)
    epoch = response.json()
    print(f"   Epoch: {epoch.get('epoch')}")
    print(f"   Slot: {epoch.get('slot')}")
    print(f"   Active Miners: {epoch.get('enrolled_miners')}")
    
    # 3. List Miners
    print("\n3. Active Miners")
    response = session.get(f"{NODE_URL}/api/miners", timeout=10)
    miners = response.json()
    print(f"   Total: {len(miners)} miners")
    for miner in miners[:3]:
        print(f"   - {miner.get('miner')}: {miner.get('hardware_type')}")
    
    # 4. Hall of Fame
    print("\n4. Hall of Fame")
    response = session.get(f"{NODE_URL}/api/hall_of_fame", timeout=10)
    hof = response.json()
    print(f"   Categories: {list(hof.keys())}")
    
    # 5. Fee Pool
    print("\n5. Fee Pool")
    response = session.get(f"{NODE_URL}/api/fee_pool", timeout=10)
    pool = response.json()
    print(f"   Total Fees: {pool.get('total_fees')} RTC")
    
    # 6. Balance Check
    print("\n6. Balance Check (scott)")
    response = session.get(
        f"{NODE_URL}/wallet/balance",
        params={"miner_id": "scott"},
        timeout=10
    )
    balance = response.json()
    if balance.get("ok"):
        print(f"   Balance: {balance.get('amount_rtc')} RTC")
    else:
        print(f"   Wallet not found")
    
    print("\n" + "=" * 60)
    print("All API calls completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
```

---

## Next Steps

After completing these first API calls, you can:

1. **Create a wallet** — See `examples/signed_transfer_example.py`
2. **Submit signed transfers** — See `docs/SIGNED_TRANSFER_EXAMPLE.md`
3. **Explore the full API** — See `docs/api-reference.md`

---

## Troubleshooting

### SSL Certificate Error

```
SSL: CERTIFICATE_VERIFY_FAILED
```

**Solution:** Use `-k` flag with curl or `verify=False` in Python.

### Connection Timeout

```
ConnectionError: Max retries exceeded
```

**Solution:** Check your network connection and verify the node URL.

### 404 Not Found

```
HTTPError: 404 Not Found
```

**Solution:** Verify the endpoint path and wallet ID format.

---

*Last Updated: March 2026 | Bounty #1494*
