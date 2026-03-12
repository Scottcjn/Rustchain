# RustChain API Usage Examples

Complete code examples for interacting with the RustChain REST API.

## Table of Contents

- [cURL Examples](#curl-examples)
- [Python Examples](#python-examples)
- [JavaScript/Node.js Examples](#javascriptnodejs-examples)
- [Go Examples](#go-examples)
- [Rust Examples](#rust-examples)
- [Bash Script](#bash-script)

---

## cURL Examples

### Health Check

```bash
curl -sk https://rustchain.org/health | jq
```

**Expected Output:**
```json
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 43200,
  "db_rw": true,
  "backup_age_hours": 12.5,
  "tip_age_slots": 0
}
```

### Get Epoch Information

```bash
curl -sk https://rustchain.org/epoch | jq
```

**Expected Output:**
```json
{
  "epoch": 75,
  "slot": 10800,
  "blocks_per_epoch": 144,
  "epoch_pot": 1.5,
  "enrolled_miners": 10
}
```

### List Active Miners

```bash
curl -sk https://rustchain.org/api/miners | jq
```

### Get Wallet Balance

```bash
# Using miner_id parameter (canonical)
curl -sk "https://rustchain.org/wallet/balance?miner_id=scott" | jq

# Using address parameter (backward compatible)
curl -sk "https://rustchain.org/wallet/balance?address=scott" | jq
```

**Expected Output:**
```json
{
  "ok": true,
  "miner_id": "scott",
  "amount_rtc": 42.5,
  "amount_i64": 42500000
}
```

### Get Transaction History

```bash
curl -sk "https://rustchain.org/wallet/history?miner_id=scott&limit=10" | jq
```

### Check Epoch Eligibility

```bash
curl -sk "https://rustchain.org/lottery/eligibility?miner_id=scott" | jq
```

### Get Network Statistics

```bash
curl -sk https://rustchain.org/api/stats | jq
```

### Get Hall of Fame

```bash
curl -sk https://rustchain.org/api/hall_of_fame | jq
```

### Get Fee Pool Statistics

```bash
curl -sk https://rustchain.org/api/fee_pool | jq
```

### Get Settlement Data

```bash
curl -sk https://rustchain.org/api/settlement/75 | jq
```

### Submit Hardware Attestation

```bash
curl -sk -X POST https://rustchain.org/attest/submit \
  -H "Content-Type: application/json" \
  -d '{
    "miner_id": "scott",
    "timestamp": 1771187406,
    "device_info": {
      "arch": "PowerPC",
      "family": "G4"
    },
    "fingerprint": {
      "clock_skew": {"drift_ppm": 24.3, "jitter_ns": 1247},
      "cache_timing": {"l1_latency_ns": 5, "l2_latency_ns": 15},
      "simd_identity": {"instruction_set": "AltiVec", "pipeline_bias": 0.76},
      "thermal_entropy": {"idle_temp_c": 42.1, "load_temp_c": 71.3, "variance": 3.8},
      "instruction_jitter": {"mean_ns": 3200, "stddev_ns": 890},
      "behavioral_heuristics": {"cpuid_clean": true, "no_hypervisor": true}
    },
    "signature": "Ed25519_base64_signature_here"
  }' | jq
```

### Admin Transfer

```bash
curl -sk -X POST https://rustchain.org/wallet/transfer \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "from_miner": "treasury",
    "to_miner": "scott",
    "amount_rtc": 10.0,
    "memo": "Bounty payment #123"
  }' | jq
```

---

## Python Examples

### Basic API Client

```python
#!/usr/bin/env python3
"""
RustChain API Client - Basic Examples
"""

import requests
from typing import Optional, List, Dict, Any

BASE_URL = "https://rustchain.org"

# Disable SSL warnings for self-signed certificate
requests.packages.urllib3.disable_warnings()


class RustChainClient:
    """Simple RustChain API client."""
    
    def __init__(self, base_url: str = BASE_URL, verify_ssl: bool = False):
        self.base_url = base_url
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.verify = verify_ssl
    
    def get_health(self) -> Dict[str, Any]:
        """Check node health status."""
        resp = self.session.get(f"{self.base_url}/health")
        resp.raise_for_status()
        return resp.json()
    
    def get_ready(self) -> Dict[str, Any]:
        """Check node readiness."""
        resp = self.session.get(f"{self.base_url}/ready")
        resp.raise_for_status()
        return resp.json()
    
    def get_epoch(self) -> Dict[str, Any]:
        """Get current epoch information."""
        resp = self.session.get(f"{self.base_url}/epoch")
        resp.raise_for_status()
        return resp.json()
    
    def get_miners(self) -> List[Dict[str, Any]]:
        """List all active miners."""
        resp = self.session.get(f"{self.base_url}/api/miners")
        resp.raise_for_status()
        return resp.json()
    
    def get_nodes(self) -> List[Dict[str, Any]]:
        """List connected nodes."""
        resp = self.session.get(f"{self.base_url}/api/nodes")
        resp.raise_for_status()
        return resp.json()
    
    def get_balance(self, miner_id: str) -> Dict[str, Any]:
        """Get wallet balance for a miner."""
        resp = self.session.get(
            f"{self.base_url}/wallet/balance",
            params={"miner_id": miner_id}
        )
        resp.raise_for_status()
        return resp.json()
    
    def get_history(self, miner_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get transaction history for a wallet."""
        resp = self.session.get(
            f"{self.base_url}/wallet/history",
            params={"miner_id": miner_id, "limit": limit}
        )
        resp.raise_for_status()
        return resp.json()
    
    def check_eligibility(self, miner_id: str) -> Dict[str, Any]:
        """Check epoch eligibility for a miner."""
        resp = self.session.get(
            f"{self.base_url}/lottery/eligibility",
            params={"miner_id": miner_id}
        )
        resp.raise_for_status()
        return resp.json()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get network statistics."""
        resp = self.session.get(f"{self.base_url}/api/stats")
        resp.raise_for_status()
        return resp.json()
    
    def get_hall_of_fame(self) -> Dict[str, Any]:
        """Get Hall of Fame leaderboard."""
        resp = self.session.get(f"{self.base_url}/api/hall_of_fame")
        resp.raise_for_status()
        return resp.json()
    
    def get_fee_pool(self) -> Dict[str, Any]:
        """Get fee pool statistics."""
        resp = self.session.get(f"{self.base_url}/api/fee_pool")
        resp.raise_for_status()
        return resp.json()
    
    def get_settlement(self, epoch: int) -> Dict[str, Any]:
        """Get settlement data for a specific epoch."""
        resp = self.session.get(f"{self.base_url}/api/settlement/{epoch}")
        resp.raise_for_status()
        return resp.json()
    
    def get_swap_info(self) -> Dict[str, Any]:
        """Get swap/bridge information."""
        resp = self.session.get(f"{self.base_url}/wallet/swap-info")
        resp.raise_for_status()
        return resp.json()


def main():
    """Example usage."""
    client = RustChainClient()
    
    print("=== RustChain API Examples ===\n")
    
    # Health check
    print("1. Health Check:")
    health = client.get_health()
    print(f"   Status: {'OK' if health.get('ok') else 'UNHEALTHY'}")
    print(f"   Version: {health.get('version')}")
    print(f"   Uptime: {health.get('uptime_s')} seconds\n")
    
    # Epoch info
    print("2. Epoch Information:")
    epoch = client.get_epoch()
    print(f"   Epoch: {epoch.get('epoch')}")
    print(f"   Slot: {epoch.get('slot')}/{epoch.get('blocks_per_epoch')}")
    print(f"   POT: {epoch.get('epoch_pot')} RTC")
    print(f"   Miners: {epoch.get('enrolled_miners')}\n")
    
    # Balance check
    print("3. Wallet Balance:")
    balance = client.get_balance("scott")
    if balance.get('ok'):
        print(f"   Miner: {balance.get('miner_id')}")
        print(f"   Balance: {balance.get('amount_rtc')} RTC\n")
    else:
        print(f"   Error: {balance.get('error')}\n")
    
    # Network stats
    print("4. Network Statistics:")
    stats = client.get_stats()
    print(f"   Total Blocks: {stats.get('total_blocks')}")
    print(f"   Total Transactions: {stats.get('total_transactions')}\n")


if __name__ == "__main__":
    main()
```

### Advanced Client with Error Handling

```python
#!/usr/bin/env python3
"""
RustChain API Client - Advanced with Error Handling
"""

import requests
from typing import Optional, Dict, Any
from dataclasses import dataclass


class RustChainError(Exception):
    """Base exception for RustChain API errors."""
    pass


class WalletNotFoundError(RustChainError):
    """Wallet not found error."""
    pass


class UnauthorizedError(RustChainError):
    """Authentication error."""
    pass


@dataclass
class WalletBalance:
    """Wallet balance data."""
    miner_id: str
    amount_rtc: float
    amount_i64: int


class AdvancedRustChainClient:
    """Advanced RustChain API client with error handling."""
    
    def __init__(self, base_url: str = "https://rustchain.org"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.verify = False  # Self-signed cert
        requests.packages.urllib3.disable_warnings()
    
    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make API request with error handling."""
        url = f"{self.base_url}{path}"
        try:
            resp = self.session.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            error_data = e.response.json() if e.response.content else {}
            error_code = error_data.get('error', 'UNKNOWN_ERROR')
            
            if error_code == 'WALLET_NOT_FOUND':
                raise WalletNotFoundError(f"Wallet not found: {error_data.get('miner_id')}")
            elif error_code == 'UNAUTHORIZED':
                raise UnauthorizedError("Invalid or missing authentication")
            else:
                raise RustChainError(f"API error: {error_code}")
        except requests.exceptions.RequestException as e:
            raise RustChainError(f"Request failed: {e}")
    
    def get_balance(self, miner_id: str) -> WalletBalance:
        """Get wallet balance with typed response."""
        data = self._request('GET', '/wallet/balance', params={'miner_id': miner_id})
        return WalletBalance(
            miner_id=data['miner_id'],
            amount_rtc=data['amount_rtc'],
            amount_i64=data['amount_i64']
        )
    
    def admin_transfer(self, admin_key: str, from_miner: str, to_miner: str, 
                       amount_rtc: float, memo: Optional[str] = None) -> Dict[str, Any]:
        """Perform admin transfer."""
        payload = {
            'from_miner': from_miner,
            'to_miner': to_miner,
            'amount_rtc': amount_rtc
        }
        if memo:
            payload['memo'] = memo
            
        headers = {'X-Admin-Key': admin_key, 'Content-Type': 'application/json'}
        return self._request('POST', '/wallet/transfer', json=payload, headers=headers)


def main():
    """Example with error handling."""
    client = AdvancedRustChainClient()
    
    try:
        balance = client.get_balance("scott")
        print(f"Balance: {balance.amount_rtc} RTC")
    except WalletNotFoundError as e:
        print(f"Wallet not found: {e}")
    except RustChainError as e:
        print(f"API error: {e}")


if __name__ == "__main__":
    main()
```

---

## JavaScript/Node.js Examples

### Basic Fetch Client

```javascript
/**
 * RustChain API Client - JavaScript/Node.js
 */

const BASE_URL = 'https://rustchain.org';

// Note: For Node.js, you may need to disable SSL verification
// process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

class RustChainClient {
  constructor(baseUrl = BASE_URL) {
    this.baseUrl = baseUrl;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.error || `HTTP ${response.status}`);
    }

    return response.json();
  }

  async getHealth() {
    return this.request('/health');
  }

  async getEpoch() {
    return this.request('/epoch');
  }

  async getMiners() {
    return this.request('/api/miners');
  }

  async getBalance(minerId) {
    return this.request(`/wallet/balance?miner_id=${encodeURIComponent(minerId)}`);
  }

  async getHistory(minerId, limit = 10) {
    return this.request(`/wallet/history?miner_id=${encodeURIComponent(minerId)}&limit=${limit}`);
  }

  async checkEligibility(minerId) {
    return this.request(`/lottery/eligibility?miner_id=${encodeURIComponent(minerId)}`);
  }

  async getStats() {
    return this.request('/api/stats');
  }

  async getHallOfFame() {
    return this.request('/api/hall_of_fame');
  }

  async getFeePool() {
    return this.request('/api/fee_pool');
  }

  async getSettlement(epoch) {
    return this.request(`/api/settlement/${epoch}`);
  }

  async getSwapInfo() {
    return this.request('/wallet/swap-info');
  }

  async adminTransfer(adminKey, fromMiner, toMiner, amountRtc, memo = null) {
    return this.request('/wallet/transfer', {
      method: 'POST',
      headers: {
        'X-Admin-Key': adminKey,
      },
      body: JSON.stringify({
        from_miner: fromMiner,
        to_miner: toMiner,
        amount_rtc: amountRtc,
        memo,
      }),
    });
  }
}

// Usage Example
async function main() {
  const client = new RustChainClient();

  try {
    console.log('=== RustChain API Examples ===\n');

    // Health check
    console.log('1. Health Check:');
    const health = await client.getHealth();
    console.log(`   Status: ${health.ok ? 'OK' : 'UNHEALTHY'}`);
    console.log(`   Version: ${health.version}`);
    console.log();

    // Epoch info
    console.log('2. Epoch Information:');
    const epoch = await client.getEpoch();
    console.log(`   Epoch: ${epoch.epoch}`);
    console.log(`   Slot: ${epoch.slot}/${epoch.blocks_per_epoch}`);
    console.log(`   POT: ${epoch.epoch_pot} RTC`);
    console.log();

    // Balance check
    console.log('3. Wallet Balance:');
    const balance = await client.getBalance('scott');
    if (balance.ok) {
      console.log(`   Miner: ${balance.miner_id}`);
      console.log(`   Balance: ${balance.amount_rtc} RTC`);
    }
    console.log();

  } catch (error) {
    console.error('Error:', error.message);
  }
}

main();

module.exports = { RustChainClient };
```

### TypeScript Client

```typescript
/**
 * RustChain API Client - TypeScript
 */

interface HealthResponse {
  ok: boolean;
  version: string;
  uptime_s: number;
  db_rw: boolean;
  backup_age_hours: number;
  tip_age_slots: number;
}

interface EpochResponse {
  epoch: number;
  slot: number;
  blocks_per_epoch: number;
  epoch_pot: number;
  enrolled_miners: number;
}

interface MinerInfo {
  miner: string;
  device_arch: string;
  device_family: string;
  hardware_type: string;
  antiquity_multiplier: number;
  entropy_score: number;
  last_attest: number;
  first_attest?: number | null;
}

interface BalanceResponse {
  ok: boolean;
  miner_id: string;
  amount_rtc: number;
  amount_i64: number;
}

export class RustChainClient {
  private baseUrl: string;

  constructor(baseUrl: string = 'https://rustchain.org') {
    this.baseUrl = baseUrl;
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.error || `HTTP ${response.status}`);
    }

    return response.json();
  }

  async getHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health');
  }

  async getEpoch(): Promise<EpochResponse> {
    return this.request<EpochResponse>('/epoch');
  }

  async getMiners(): Promise<MinerInfo[]> {
    return this.request<MinerInfo[]>('/api/miners');
  }

  async getBalance(minerId: string): Promise<BalanceResponse> {
    return this.request<BalanceResponse>(`/wallet/balance?miner_id=${encodeURIComponent(minerId)}`);
  }
}

// Usage
const client = new RustChainClient();
client.getHealth().then(console.log);
```

---

## Go Examples

```go
// RustChain API Client - Go
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
)

const BaseURL = "https://rustchain.org"

// HealthResponse represents the /health endpoint response
type HealthResponse struct {
	OK             bool    `json:"ok"`
	Version        string  `json:"version"`
	UptimeS        int     `json:"uptime_s"`
	DbRW           bool    `json:"db_rw"`
	BackupAgeHours float64 `json:"backup_age_hours"`
	TipAgeSlots    int     `json:"tip_age_slots"`
}

// EpochResponse represents the /epoch endpoint response
type EpochResponse struct {
	Epoch          int     `json:"epoch"`
	Slot           int     `json:"slot"`
	BlocksPerEpoch int     `json:"blocks_per_epoch"`
	EpochPot       float64 `json:"epoch_pot"`
	EnrolledMiners int     `json:"enrolled_miners"`
}

// MinerInfo represents a miner entry
type MinerInfo struct {
	Miner                string  `json:"miner"`
	DeviceArch           string  `json:"device_arch"`
	DeviceFamily         string  `json:"device_family"`
	HardwareType         string  `json:"hardware_type"`
	AntiquityMultiplier  float64 `json:"antiquity_multiplier"`
	EntropyScore         float64 `json:"entropy_score"`
	LastAttest           int64   `json:"last_attest"`
	FirstAttest          *int64  `json:"first_attest"`
}

// BalanceResponse represents the /wallet/balance endpoint response
type BalanceResponse struct {
	OK       bool    `json:"ok"`
	MinerID  string  `json:"miner_id"`
	AmountRTC float64 `json:"amount_rtc"`
	AmountI64 int64   `json:"amount_i64"`
}

// Client is a RustChain API client
type Client struct {
	BaseURL    string
	HTTPClient *http.Client
}

// NewClient creates a new RustChain API client
func NewClient() *Client {
	return &Client{
		BaseURL:    BaseURL,
		HTTPClient: &http.Client{},
	}
}

// GetHealth checks node health
func (c *Client) GetHealth() (*HealthResponse, error) {
	resp, err := c.HTTPClient.Get(c.BaseURL + "/health")
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	var health HealthResponse
	if err := json.Unmarshal(body, &health); err != nil {
		return nil, err
	}

	return &health, nil
}

// GetEpoch gets current epoch information
func (c *Client) GetEpoch() (*EpochResponse, error) {
	resp, err := c.HTTPClient.Get(c.BaseURL + "/epoch")
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	var epoch EpochResponse
	if err := json.Unmarshal(body, &epoch); err != nil {
		return nil, err
	}

	return &epoch, nil
}

// GetMiners lists active miners
func (c *Client) GetMiners() ([]MinerInfo, error) {
	resp, err := c.HTTPClient.Get(c.BaseURL + "/api/miners")
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	var miners []MinerInfo
	if err := json.Unmarshal(body, &miners); err != nil {
		return nil, err
	}

	return miners, nil
}

// GetBalance gets wallet balance for a miner
func (c *Client) GetBalance(minerID string) (*BalanceResponse, error) {
	params := url.Values{}
	params.Add("miner_id", minerID)

	resp, err := c.HTTPClient.Get(c.BaseURL + "/wallet/balance?" + params.Encode())
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	var balance BalanceResponse
	if err := json.Unmarshal(body, &balance); err != nil {
		return nil, err
	}

	return &balance, nil
}

func main() {
	client := NewClient()

	fmt.Println("=== RustChain API Examples ===\n")

	// Health check
	fmt.Println("1. Health Check:")
	health, err := client.GetHealth()
	if err != nil {
		fmt.Printf("   Error: %v\n", err)
	} else {
		fmt.Printf("   Status: %v\n", health.OK)
		fmt.Printf("   Version: %s\n", health.Version)
		fmt.Printf("   Uptime: %d seconds\n", health.UptimeS)
	}
	fmt.Println()

	// Epoch info
	fmt.Println("2. Epoch Information:")
	epoch, err := client.GetEpoch()
	if err != nil {
		fmt.Printf("   Error: %v\n", err)
	} else {
		fmt.Printf("   Epoch: %d\n", epoch.Epoch)
		fmt.Printf("   Slot: %d/%d\n", epoch.Slot, epoch.BlocksPerEpoch)
		fmt.Printf("   POT: %.2f RTC\n", epoch.EpochPot)
	}
	fmt.Println()

	// Balance check
	fmt.Println("3. Wallet Balance:")
	balance, err := client.GetBalance("scott")
	if err != nil {
		fmt.Printf("   Error: %v\n", err)
	} else if balance.OK {
		fmt.Printf("   Miner: %s\n", balance.MinerID)
		fmt.Printf("   Balance: %.2f RTC\n", balance.AmountRTC)
	}
	fmt.Println()
}
```

---

## Rust Examples

```rust
// RustChain API Client - Rust
// Add to Cargo.toml:
// [dependencies]
// reqwest = { version = "0.11", features = ["json"] }
// tokio = { version = "1", features = ["full"] }
// serde = { version = "1.0", features = ["derive"] }

use reqwest;
use serde::Deserialize;

const BASE_URL: &str = "https://rustchain.org";

#[derive(Debug, Deserialize)]
struct HealthResponse {
    ok: bool,
    version: String,
    uptime_s: u64,
    db_rw: bool,
    backup_age_hours: f64,
    tip_age_slots: u64,
}

#[derive(Debug, Deserialize)]
struct EpochResponse {
    epoch: u64,
    slot: u64,
    blocks_per_epoch: u64,
    epoch_pot: f64,
    enrolled_miners: u64,
}

#[derive(Debug, Deserialize)]
struct MinerInfo {
    miner: String,
    device_arch: String,
    device_family: String,
    hardware_type: String,
    antiquity_multiplier: f64,
    entropy_score: f64,
    last_attest: i64,
    first_attest: Option<i64>,
}

#[derive(Debug, Deserialize)]
struct BalanceResponse {
    ok: bool,
    miner_id: String,
    amount_rtc: f64,
    amount_i64: i64,
}

struct RustChainClient {
    client: reqwest::Client,
    base_url: String,
}

impl RustChainClient {
    fn new() -> Self {
        // Accept invalid certificates for self-signed cert
        let client = reqwest::Client::builder()
            .danger_accept_invalid_certs(true)
            .build()
            .unwrap();

        Self {
            client,
            base_url: BASE_URL.to_string(),
        }
    }

    async fn get_health(&self) -> Result<HealthResponse, reqwest::Error> {
        self.client
            .get(format!("{}/health", self.base_url))
            .send()
            .await?
            .json()
            .await
    }

    async fn get_epoch(&self) -> Result<EpochResponse, reqwest::Error> {
        self.client
            .get(format!("{}/epoch", self.base_url))
            .send()
            .await?
            .json()
            .await
    }

    async fn get_miners(&self) -> Result<Vec<MinerInfo>, reqwest::Error> {
        self.client
            .get(format!("{}/api/miners", self.base_url))
            .send()
            .await?
            .json()
            .await
    }

    async fn get_balance(&self, miner_id: &str) -> Result<BalanceResponse, reqwest::Error> {
        self.client
            .get(format!("{}/wallet/balance?miner_id={}", self.base_url, miner_id))
            .send()
            .await?
            .json()
            .await
    }
}

#[tokio::main]
async fn main() {
    let client = RustChainClient::new();

    println!("=== RustChain API Examples ===\n");

    // Health check
    println!("1. Health Check:");
    match client.get_health().await {
        Ok(health) => {
            println!("   Status: {}", health.ok);
            println!("   Version: {}", health.version);
            println!("   Uptime: {} seconds", health.uptime_s);
        }
        Err(e) => println!("   Error: {}", e),
    }
    println!();

    // Epoch info
    println!("2. Epoch Information:");
    match client.get_epoch().await {
        Ok(epoch) => {
            println!("   Epoch: {}", epoch.epoch);
            println!("   Slot: {}/{}", epoch.slot, epoch.blocks_per_epoch);
            println!("   POT: {:.2} RTC", epoch.epoch_pot);
        }
        Err(e) => println!("   Error: {}", e),
    }
    println!();

    // Balance check
    println!("3. Wallet Balance:");
    match client.get_balance("scott").await {
        Ok(balance) if balance.ok => {
            println!("   Miner: {}", balance.miner_id);
            println!("   Balance: {:.2} RTC", balance.amount_rtc);
        }
        Ok(_) => println!("   Wallet not found"),
        Err(e) => println!("   Error: {}", e),
    }
    println!();
}
```

---

## Bash Script

```bash
#!/bin/bash
#
# RustChain API Helper Script
# Usage: ./rustchain_api.sh <command> [args]
#

set -e

BASE_URL="https://rustchain.org"
CURL="curl -sk"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${GREEN}=== $1 ===${NC}"
    echo
}

print_error() {
    echo -e "${RED}Error: $1${NC}" >&2
}

cmd_health() {
    print_header "Health Check"
    $CURL "$BASE_URL/health" | jq
}

cmd_epoch() {
    print_header "Epoch Information"
    $CURL "$BASE_URL/epoch" | jq
}

cmd_miners() {
    print_header "Active Miners"
    $CURL "$BASE_URL/api/miners" | jq
}

cmd_balance() {
    local miner_id="$1"
    if [[ -z "$miner_id" ]]; then
        print_error "Miner ID required"
        echo "Usage: $0 balance <miner_id>"
        exit 1
    fi
    print_header "Balance for: $miner_id"
    $CURL "$BASE_URL/wallet/balance?miner_id=$miner_id" | jq
}

cmd_history() {
    local miner_id="$1"
    local limit="${2:-10}"
    if [[ -z "$miner_id" ]]; then
        print_error "Miner ID required"
        echo "Usage: $0 history <miner_id> [limit]"
        exit 1
    fi
    print_header "Transaction History for: $miner_id"
    $CURL "$BASE_URL/wallet/history?miner_id=$miner_id&limit=$limit" | jq
}

cmd_eligibility() {
    local miner_id="$1"
    if [[ -z "$miner_id" ]]; then
        print_error "Miner ID required"
        echo "Usage: $0 eligibility <miner_id>"
        exit 1
    fi
    print_header "Eligibility for: $miner_id"
    $CURL "$BASE_URL/lottery/eligibility?miner_id=$miner_id" | jq
}

cmd_stats() {
    print_header "Network Statistics"
    $CURL "$BASE_URL/api/stats" | jq
}

cmd_hall_of_fame() {
    print_header "Hall of Fame"
    $CURL "$BASE_URL/api/hall_of_fame" | jq
}

cmd_fee_pool() {
    print_header "Fee Pool Statistics"
    $CURL "$BASE_URL/api/fee_pool" | jq
}

cmd_settlement() {
    local epoch="$1"
    if [[ -z "$epoch" ]]; then
        print_error "Epoch number required"
        echo "Usage: $0 settlement <epoch>"
        exit 1
    fi
    print_header "Settlement for Epoch: $epoch"
    $CURL "$BASE_URL/api/settlement/$epoch" | jq
}

cmd_swap_info() {
    print_header "Swap Information"
    $CURL "$BASE_URL/wallet/swap-info" | jq
}

show_help() {
    echo "RustChain API Helper Script"
    echo
    echo "Usage: $0 <command> [args]"
    echo
    echo "Commands:"
    echo "  health              Check node health"
    echo "  epoch               Get epoch information"
    echo "  miners              List active miners"
    echo "  balance <miner_id>  Get wallet balance"
    echo "  history <miner_id>  Get transaction history"
    echo "  eligibility <id>    Check epoch eligibility"
    echo "  stats               Get network statistics"
    echo "  hall-of-fame        Get Hall of Fame"
    echo "  fee-pool            Get fee pool statistics"
    echo "  settlement <epoch>  Get settlement data"
    echo "  swap-info           Get swap information"
    echo "  help                Show this help"
    echo
}

# Main command dispatcher
case "${1:-help}" in
    health)
        cmd_health
        ;;
    epoch)
        cmd_epoch
        ;;
    miners)
        cmd_miners
        ;;
    balance)
        cmd_balance "$2"
        ;;
    history)
        cmd_history "$2" "$3"
        ;;
    eligibility)
        cmd_eligibility "$2"
        ;;
    stats)
        cmd_stats
        ;;
    hall-of-fame)
        cmd_hall_of_fame
        ;;
    fee-pool)
        cmd_fee_pool
        ;;
    settlement)
        cmd_settlement "$2"
        ;;
    swap-info)
        cmd_swap_info
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
```

---

## Related Documentation

- [OpenAPI Specification](./openapi.yaml)
- [API Reference](./REFERENCE.md)
- [README](./README.md)
