# RustChain Python SDK Tutorial

Interact with the RustChain network from Python using the `requests` library.
No dedicated SDK package is required — the API is a straightforward REST
interface.

**Nodes:**
- `http://rustchain.org:8088` — primary attestation node
- `http://50.28.86.153:8088` — ergo anchor node

---

## Installation

```bash
pip install requests PyNaCl
```

`PyNaCl` is required only if you need to generate Ed25519 signatures for
attestation submissions. Read-only queries need only `requests`.

---

## Basic Client Setup

```python
import requests
import time

BASE_URL = "http://rustchain.org:8088"   # primary node
FALLBACK_URL = "http://50.28.86.153:8088"  # anchor node

class RustChainClient:
    """Minimal RustChain REST client."""

    def __init__(self, base_url: str = BASE_URL, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def get(self, path: str, **params) -> dict:
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, body: dict) -> dict:
        url = f"{self.base_url}{path}"
        resp = self.session.post(url, json=body, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()


client = RustChainClient()
```

---

## Submit Attestation

`POST /attest/submit` enrolls your miner in the current epoch. The fingerprint
must be generated from real hardware; virtual-machine detections result in
`VM_DETECTED`.

```python
import nacl.signing
import nacl.encoding
import hashlib
import json
import time


def build_fingerprint(arch: str, family: str) -> dict:
    """
    Build a hardware fingerprint dict.
    Replace the placeholder values with real measurements from
    hardware_fingerprint.py when running on real hardware.
    """
    return {
        "clock_skew":            {"drift_ppm": 24.3, "jitter_ns": 1247},
        "cache_timing":          {"l1_latency_ns": 5, "l2_latency_ns": 15},
        "simd_identity":         {"instruction_set": "AltiVec", "pipeline_bias": 0.76},
        "thermal_entropy":       {"idle_temp_c": 42.1, "load_temp_c": 71.3, "variance": 3.8},
        "instruction_jitter":    {"mean_ns": 3200, "stddev_ns": 890},
        "behavioral_heuristics": {"cpuid_clean": True, "no_hypervisor": True},
    }


def submit_attestation(
    client: RustChainClient,
    miner_id: str,
    signing_key: nacl.signing.SigningKey,
    arch: str = "PowerPC",
    family: str = "G4",
) -> dict:
    """Submit hardware attestation and return the enrollment result."""
    fingerprint = build_fingerprint(arch, family)
    ts = int(time.time())

    # Canonical payload to sign (deterministic JSON)
    canonical = json.dumps(
        {"miner_id": miner_id, "timestamp": ts, "fingerprint": fingerprint},
        sort_keys=True, separators=(",", ":"),
    ).encode()
    sig_bytes = signing_key.sign(canonical).signature
    import base64
    signature = base64.b64encode(sig_bytes).decode()

    body = {
        "miner_id": miner_id,
        "timestamp": ts,
        "device_info": {"arch": arch, "family": family},
        "fingerprint": fingerprint,
        "signature": signature,
    }

    result = client.post("/attest/submit", body)

    if result.get("enrolled"):
        print(f"✅ Enrolled — epoch={result['epoch']}, multiplier={result['multiplier']}x")
    else:
        print(f"❌ Rejected — error={result.get('error')}")

    return result


# Usage
signing_key = nacl.signing.SigningKey.generate()   # persist this in production!
result = submit_attestation(client, miner_id="mywalletRTC", signing_key=signing_key)
```

> **Persist your signing key.** Generate it once and save the hex seed:
> `signing_key.encode(nacl.encoding.HexEncoder).decode()`. Losing your key
> means you lose access to your wallet.

---

## Query Miners

```python
def get_miners(client: RustChainClient) -> list:
    """Return list of all enrolled miners."""
    miners = client.get("/api/miners")
    return miners


def print_miner_table(miners: list) -> None:
    print(f"{'Miner':<45} {'Family':<12} {'Multiplier':>10} {'Last Attest'}")
    print("-" * 85)
    for m in miners:
        last = time.strftime("%Y-%m-%d %H:%M", time.gmtime(m["last_attest"])) \
               if m.get("last_attest") else "—"
        print(
            f"{m['miner']:<45} {m['device_family']:<12} "
            f"{m['antiquity_multiplier']:>10.1f}x  {last}"
        )


# Usage
miners = get_miners(client)
print(f"Active miners: {len(miners)}")
print_miner_table(miners)
```

---

## Check Current Epoch

```python
def get_epoch(client: RustChainClient) -> dict:
    """Return current epoch info."""
    return client.get("/epoch")


def wait_for_next_epoch(client: RustChainClient) -> None:
    """Block until the next epoch starts (useful for automation)."""
    info = get_epoch(client)
    slots_remaining = info["blocks_per_epoch"] - info["slot"]
    seconds_remaining = slots_remaining * 600   # 600s per slot
    print(f"Epoch {info['epoch']} — slot {info['slot']}/{info['blocks_per_epoch']}")
    print(f"Waiting {seconds_remaining // 60} min for next epoch...")
    time.sleep(seconds_remaining)


# Usage
epoch_info = get_epoch(client)
print(f"Epoch:    {epoch_info['epoch']}")
print(f"Slot:     {epoch_info['slot']} / {epoch_info['blocks_per_epoch']}")
print(f"Pot:      {epoch_info['epoch_pot']} RTC")
print(f"Miners:   {epoch_info['enrolled_miners']} enrolled")
```

---

## Get Network Stats

```python
def get_stats(client: RustChainClient) -> dict:
    """Return aggregate network statistics."""
    return client.get("/api/stats")


# Usage
stats = get_stats(client)
print(f"Version:             {stats['version']}")
print(f"Chain ID:            {stats['chain_id']}")
print(f"Epoch:               {stats['epoch']}")
print(f"Total miners:        {stats['total_miners']}")
print(f"Total supply (RTC):  {stats['total_balance']:,.6f}")
print(f"Pending withdrawals: {stats['pending_withdrawals']}")
print(f"Features:            {', '.join(stats['features'])}")
```

---

## Error Handling Patterns

### Basic error wrapper

```python
import requests

def safe_get(client: RustChainClient, path: str, **params) -> dict | None:
    """GET with graceful error handling. Returns None on failure."""
    try:
        return client.get(path, **params)
    except requests.HTTPError as e:
        print(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
    except requests.ConnectionError as e:
        print(f"Connection failed: {e}")
    except requests.Timeout:
        print(f"Request timed out after {client.timeout}s")
    return None
```

### Retry with fallback node

```python
import time

def get_with_fallback(path: str, retries: int = 3, **params) -> dict:
    """Try primary node, fall back to anchor node, retry on transient errors."""
    nodes = [BASE_URL, FALLBACK_URL]
    for attempt in range(retries):
        for node_url in nodes:
            c = RustChainClient(base_url=node_url)
            try:
                return c.get(path, **params)
            except requests.HTTPError as e:
                if e.response.status_code == 429:
                    retry_after = int(e.response.headers.get("Retry-After", 60))
                    print(f"Rate limited — waiting {retry_after}s")
                    time.sleep(retry_after)
                elif e.response.status_code >= 500:
                    print(f"Server error on {node_url}, trying next node...")
                else:
                    raise   # 4xx client errors shouldn't be retried
            except (requests.ConnectionError, requests.Timeout):
                print(f"Node {node_url} unreachable, trying next...")
        time.sleep(2 ** attempt)  # exponential backoff between full retry rounds
    raise RuntimeError(f"All nodes failed after {retries} attempts")


# Usage
health = get_with_fallback("/health")
print(health)
```

### Handle attestation errors

```python
def attest_with_error_handling(client, miner_id, signing_key):
    try:
        result = submit_attestation(client, miner_id, signing_key)
        return result
    except requests.HTTPError as e:
        body = e.response.json() if e.response.content else {}
        error_code = body.get("error", "UNKNOWN")

        if error_code == "VM_DETECTED":
            print("Hardware check failed. Run on bare metal, not a VM.")
        elif error_code == "HARDWARE_ALREADY_BOUND":
            existing = body.get("existing_miner")
            print(f"Hardware already registered to: {existing}")
        elif error_code == "REPLAY_DETECTED":
            print("Timestamp reuse — ensure system clock is accurate (NTP).")
        elif error_code == "INVALID_SIGNATURE":
            print("Signature mismatch — verify your signing key matches miner_id.")
        elif e.response.status_code == 429:
            print("Rate limited — wait 10 minutes between attestations.")
        else:
            print(f"Unexpected error {e.response.status_code}: {body}")
        return None
```

---

## Putting It Together — Minimal Miner Loop

```python
import time

ATTEST_INTERVAL = 600   # seconds between attestation attempts

def run_miner(miner_id: str, signing_key):
    client = RustChainClient()
    print(f"Starting miner: {miner_id}")

    while True:
        epoch_info = get_epoch(client)
        print(f"[Epoch {epoch_info['epoch']} | Slot {epoch_info['slot']}]", end=" ")

        result = attest_with_error_handling(client, miner_id, signing_key)
        if result and result.get("enrolled"):
            print(f"enrolled — next settlement: {result.get('next_settlement')}")
        time.sleep(ATTEST_INTERVAL)


if __name__ == "__main__":
    import nacl.signing
    sk = nacl.signing.SigningKey.generate()
    run_miner("mywalletRTC", sk)
```

---

*Tutorial covers RustChain v2.2.1-rip200 · Nodes: http://rustchain.org:8088, http://50.28.86.153:8088*
