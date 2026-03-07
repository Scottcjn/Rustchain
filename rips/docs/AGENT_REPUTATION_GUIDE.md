# Agent Reputation Score System - Usage Guide

## Quick Start

### Basic Usage

```rust
use rustchain::prelude::*;
use rustchain::agent_reputation::*;

// Create in-memory store (use SQLite store for production)
let store = Box::new(InMemoryReputationStore::default());

// Initialize reputation manager
let mut rep_manager = ReputationManager::new(store);

// Create wallet
let wallet = WalletAddress::new("RTC1AgentName123");

// Process attestation (called when miner submits proof)
let score = rep_manager.process_attestation(
    &wallet,
    "192.168.1.100",      // IP address (hashed internally)
    "hardware_fingerprint_hash",
    true,                  // Success
);

println!("Reputation score: {}", score.score);
println!("Breakdown: {:?}", score.breakdown);
```

### Processing Different Activities

```rust
// Block mining
let score = rep_manager.process_block_mined(
    &wallet,
    12345,                 // Block height
    TokenAmount(50_000_000) // Reward (0.5 RTC)
);

// Community interaction
let score = rep_manager.process_community_interaction(
    &wallet,
    "governance_vote",     // Interaction type
    1.0                    // Quality score (0.0 - 1.0)
);

// Challenge response
let score = rep_manager.process_challenge(
    &wallet,
    5.2,                   // Response time in seconds
    true                   // Success
);
```

### Querying Reputation

```rust
// Get score for specific wallet
if let Some(score) = rep_manager.get_score(&wallet) {
    println!("Score: {}", score.score);
    println!("Peak: {}", score.history.peak_score);
    println!("30d avg: {}", score.history.avg_30d);
    println!("7d trend: {}", score.history.trend_7d);
}

// Get top 100 wallets by reputation
let top_wallets = rep_manager.get_top_wallets(100);
for (rank, (wallet, score)) in top_wallets.iter().enumerate() {
    println!("{}. {}: {}", rank + 1, wallet.0, score);
}

// Get wallets above threshold (for qualified tasks)
let qualified = rep_manager.get_above_threshold(0.7);
println!("{} wallets qualified for high-reputation tasks", qualified.len());
```

## API Integration

### REST API Endpoints

The reputation system exposes these endpoints via the RustChain node API:

#### 1. Get Agent Reputation

```bash
curl -sk https://rustchain.org/api/reputation/RTC1AgentName123
```

**Response**:
```json
{
  "wallet": "RTC1AgentName123",
  "score": 0.847,
  "breakdown": {
    "uptime_score": 0.92,
    "attestation_score": 0.88,
    "hardware_score": 1.0,
    "community_score": 0.75,
    "history_score": 0.80,
    "anti_gaming_multiplier": 1.0,
    "decay_factor": 0.95
  },
  "history": {
    "peak_score": 0.89,
    "avg_30d": 0.82,
    "trend_7d": 0.03,
    "days_tracked": 45
  },
  "risk_flags": [],
  "last_updated": 1741392000,
  "version": 1
}
```

#### 2. Get Top Agents

```bash
curl -sk "https://rustchain.org/api/reputation/top?limit=100"
```

**Response**:
```json
[
  {"wallet": "RTC1TopAgent1", "score": 0.952, "rank": 1},
  {"wallet": "RTC1TopAgent2", "score": 0.943, "rank": 2},
  ...
]
```

#### 3. Get Qualified Agents

```bash
curl -sk "https://rustchain.org/api/reputation/qualified?threshold=0.7"
```

Use this to find agents qualified for:
- High-value bounties (>50 RTC)
- Governance participation
- Validator roles

#### 4. Submit Attestation

```bash
curl -sk -X POST https://rustchain.org/api/reputation/attestation \
  -H "Content-Type: application/json" \
  -d '{
    "wallet": "RTC1Agent123",
    "ip_hash": "abc123def456...",
    "hardware_hash": "789xyz...",
    "success": true
  }'
```

#### 5. Record Community Interaction

```bash
curl -sk -X POST https://rustchain.org/api/reputation/interaction \
  -H "Content-Type: application/json" \
  -d '{
    "wallet": "RTC1Agent123",
    "interaction_type": "help_new_miner",
    "quality_score": 1.0
  }'
```

#### 6. Issue Challenge

```bash
curl -sk -X POST https://rustchain.org/api/reputation/challenge \
  -H "Content-Type: application/json" \
  -d '{
    "wallet": "RTC1SuspectWallet"
  }'
```

### Python SDK Example

```python
import requests

BASE_URL = "https://rustchain.org"

def get_reputation(wallet):
    """Get reputation score for wallet"""
    resp = requests.get(
        f"{BASE_URL}/api/reputation/{wallet}",
        verify=False
    )
    return resp.json()

def get_top_agents(limit=100):
    """Get top agents by reputation"""
    resp = requests.get(
        f"{BASE_URL}/api/reputation/top?limit={limit}",
        verify=False
    )
    return resp.json()

def submit_attestation(wallet, ip_hash, hardware_hash, success=True):
    """Submit attestation and update reputation"""
    resp = requests.post(
        f"{BASE_URL}/api/reputation/attestation",
        json={
            "wallet": wallet,
            "ip_hash": ip_hash,
            "hardware_hash": hardware_hash,
            "success": success
        },
        verify=False
    )
    return resp.json()

def record_community_interaction(wallet, interaction_type, quality_score=1.0):
    """Record community interaction"""
    resp = requests.post(
        f"{BASE_URL}/api/reputation/interaction",
        json={
            "wallet": wallet,
            "interaction_type": interaction_type,
            "quality_score": quality_score
        },
        verify=False
    )
    return resp.json()

# Usage
wallet = "RTC1AgentName123"

# Get reputation
rep = get_reputation(wallet)
print(f"Score: {rep['score']}")
print(f"Breakdown: {rep['breakdown']}")

# Get top agents
top = get_top_agents(10)
print("Top 10 agents:")
for agent in top:
    print(f"  {agent['rank']}. {agent['wallet']}: {agent['score']}")

# Submit attestation
result = submit_attestation(wallet, "abc123", "def456")
print(f"New score: {result['score']}")

# Record community help
result = record_community_interaction(wallet, "help_new_miner")
print(f"Updated score: {result['score']}")
```

### JavaScript SDK Example

```javascript
const BASE_URL = 'https://rustchain.org';

async function getReputation(wallet) {
  const resp = await fetch(`${BASE_URL}/api/reputation/${wallet}`);
  return resp.json();
}

async function getTopAgents(limit = 100) {
  const resp = await fetch(`${BASE_URL}/api/reputation/top?limit=${limit}`);
  return resp.json();
}

async function submitAttestation(wallet, ipHash, hardwareHash, success = true) {
  const resp = await fetch(`${BASE_URL}/api/reputation/attestation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      wallet,
      ip_hash: ipHash,
      hardware_hash: hardwareHash,
      success
    })
  });
  return resp.json();
}

async function recordCommunityInteraction(wallet, interactionType, qualityScore = 1.0) {
  const resp = await fetch(`${BASE_URL}/api/reputation/interaction`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      wallet,
      interaction_type: interactionType,
      quality_score: qualityScore
    })
  });
  return resp.json();
}

// Usage
const wallet = 'RTC1AgentName123';

// Get reputation
const rep = await getReputation(wallet);
console.log(`Score: ${rep.score}`);
console.log(`Breakdown:`, rep.breakdown);

// Get top agents
const top = await getTopAgents(10);
console.log('Top 10 agents:');
top.forEach(agent => {
  console.log(`  ${agent.rank}. ${agent.wallet}: ${agent.score}`);
});

// Submit attestation
const result = await submitAttestation(wallet, 'abc123', 'def456');
console.log(`New score: ${result.score}`);
```

## Anti-Gaming Examples

### Detecting Sybil Clusters

```rust
use rustchain::agent_reputation::AntiGamingDetector;

let mut detector = AntiGamingDetector::new();

// Simulate 5 wallets on same IP
let ip = "192.168.1.100";
for i in 0..5 {
    let wallet = WalletAddress::new(format!("RTC1Bot{}", i));
    let flags = detector.record_ip(&wallet, ip);
    
    if !flags.is_empty() {
        println!("Sybil detected! Flags: {:?}", flags);
    }
}

// Check fleet correlation
let wallet = WalletAddress::new("RTC1Bot0");
let correlation = detector.calculate_fleet_correlation(&wallet);
println!("Fleet correlation: {}", correlation);

if correlation > 0.85 {
    println!("High fleet correlation - likely coordinated attack");
}
```

### Challenge-Response System

```rust
// Issue challenge to suspicious wallet
rep_manager.process_challenge(&wallet, 5.2, true);  // Success, 5.2s response

// Failed challenge
let score = rep_manager.process_challenge(&wallet, 10.0, false);

// Check for challenge failure flag
if score.risk_flags.iter().any(|f| f.flag_type == RiskType::ChallengeFailure) {
    println!("Wallet failed challenge - applying penalty");
}

// Too-fast response (suspicious automation)
let score = rep_manager.process_challenge(&wallet, 0.5, true);

if score.risk_flags.iter().any(|f| f.flag_type == RiskType::ScoreManipulation) {
    println!("Suspiciously fast response - possible bot");
}
```

## Production Deployment

### SQLite Store Implementation

For production use, implement persistent storage:

```rust
use rusqlite::{Connection, Result};
use rustchain::agent_reputation::{ReputationStore, ReputationScore, WalletAddress};

pub struct SqliteReputationStore {
    conn: Connection,
}

impl SqliteReputationStore {
    pub fn new(path: &str) -> Result<Self> {
        let conn = Connection::open(path)?;
        
        // Create tables
        conn.execute_batch(include_str!("schema.sql"))?;
        
        Ok(SqliteReputationStore { conn })
    }
}

impl ReputationStore for SqliteReputationStore {
    fn get_score(&self, wallet: &WalletAddress) -> Option<ReputationScore> {
        let mut stmt = self.conn.prepare(
            "SELECT * FROM reputation_scores WHERE wallet_address = ?1"
        ).ok()?;
        
        // ... implementation
    }
    
    fn update_score(&mut self, score: ReputationScore) {
        // ... implementation
    }
    
    // ... other methods
}

// Usage
let store = Box::new(SqliteReputationStore::new("reputation.db").unwrap());
let mut manager = ReputationManager::new(store);
```

### Database Schema

```sql
-- schema.sql
CREATE TABLE IF NOT EXISTS reputation_scores (
    wallet_address TEXT PRIMARY KEY,
    score REAL NOT NULL,
    uptime_score REAL NOT NULL,
    attestation_score REAL NOT NULL,
    hardware_score REAL NOT NULL,
    community_score REAL NOT NULL,
    history_score REAL NOT NULL,
    anti_gaming_multiplier REAL NOT NULL DEFAULT 1.0,
    decay_factor REAL NOT NULL DEFAULT 1.0,
    peak_score REAL NOT NULL DEFAULT 0.0,
    avg_30d REAL NOT NULL DEFAULT 0.0,
    trend_7d REAL NOT NULL DEFAULT 0.0,
    days_tracked INTEGER NOT NULL DEFAULT 0,
    last_updated INTEGER NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS risk_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_address TEXT NOT NULL,
    flag_type TEXT NOT NULL,
    severity REAL NOT NULL,
    description TEXT NOT NULL,
    flagged_at INTEGER NOT NULL,
    resolved BOOLEAN NOT NULL DEFAULT 0,
    FOREIGN KEY (wallet_address) REFERENCES reputation_scores(wallet_address)
);

CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_address TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    activity_type TEXT NOT NULL,
    outcome REAL NOT NULL,
    ip_hash TEXT,
    hardware_hash TEXT,
    metadata TEXT,
    FOREIGN KEY (wallet_address) REFERENCES reputation_scores(wallet_address)
);

CREATE INDEX IF NOT EXISTS idx_activity_wallet ON activity_log(wallet_address);
CREATE INDEX IF NOT EXISTS idx_activity_timestamp ON activity_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_risk_wallet ON risk_flags(wallet_address);
CREATE INDEX IF NOT EXISTS idx_scores_score ON reputation_scores(score);
```

## Monitoring and Metrics

### Prometheus Metrics

```rust
// Example metrics to expose
let registry = Registry::new();

// Current reputation score
let score_gauge = Gauge::new(
    "rustchain_reputation_score",
    "Current reputation score for wallet"
).with_labels(labels).unwrap();
registry.register(Box::new(score_gauge)).unwrap();

// Risk flags count
let flags_counter = IntCounter::new(
    "rustchain_risk_flags_total",
    "Total risk flags raised"
).with_labels(labels).unwrap();
registry.register(Box::new(flags_counter)).unwrap();

// Challenge success rate
let challenge_gauge = Gauge::new(
    "rustchain_challenge_success_rate",
    "Challenge response success rate"
).unwrap();
registry.register(Box::new(challenge_gauge)).unwrap();
```

### Grafana Dashboard

Key panels to monitor:

1. **Reputation Distribution**: Histogram of scores across all wallets
2. **Top 10 Agents**: Time series of top agents' scores
3. **Risk Flags**: Count of active flags by type
4. **Challenge Metrics**: Success rate, average response time
5. **Decay Impact**: Wallets affected by time decay
6. **Sybil Detection**: Clusters detected and blocked

## Best Practices

### For Agent Operators

1. **Maintain Consistent Attestations**
   - Attest ~2x per day
   - Avoid bot-like regularity (add some randomness)
   - Use stable hardware and network

2. **Build Community Score**
   - Participate in governance
   - Help new miners
   - Contribute to ecosystem

3. **Avoid Red Flags**
   - Don't share hardware across wallets
   - Don't use multiple IPs excessively
   - Respond to challenges promptly

4. **Monitor Your Score**
   - Check reputation regularly
   - Address risk flags quickly
   - Maintain activity during long periods

### For Protocol Integrators

1. **Set Appropriate Thresholds**
   - Start conservative (0.5-0.6)
   - Adjust based on false positive rate
   - Consider task-specific requirements

2. **Implement Grace Periods**
   - Allow new agents to build reputation
   - Don't penalize brief inactivity
   - Provide clear feedback on score changes

3. **Use Reputation Weighting**
   - Amplify high-reputation agents
   - Limit low-reputation agent impact
   - Combine with other signals (stake, history)

4. **Monitor for Gaming**
   - Watch for score manipulation patterns
   - Investigate sudden score changes
   - Update detection rules regularly

## Troubleshooting

### Low Reputation Score

**Symptoms**: Score < 0.5

**Causes**:
- Inactive for extended period
- Failed attestations
- Risk flags present
- Insufficient history

**Solutions**:
1. Increase attestation frequency
2. Ensure stable hardware/network
3. Resolve any risk flags
4. Participate in community activities
5. Wait for history to build

### False Positive Sybil Detection

**Symptoms**: Legitimate wallets flagged

**Causes**:
- Shared NAT/CGNAT IP ranges
- Corporate network with shared egress
- VPN/proxy usage

**Solutions**:
1. Use hardware fingerprint as primary identifier
2. Implement allowlist for known networks
3. Manual review and clearance
4. Adjust `MAX_WALLETS_PER_IP` threshold

### Score Not Updating

**Symptoms**: Activities not reflected in score

**Causes**:
- Store not persisted
- Activity log full
- Decay overpowering gains

**Solutions**:
1. Check store implementation
2. Increase activity window size
3. Verify activity recording
4. Review decay parameters

## FAQ

**Q: How long does it take to build a good reputation?**

A: With consistent activity (2 attestations/day, no failures), you can reach 0.7+ in ~2 weeks and 0.9+ in ~6 weeks.

**Q: Can reputation be lost?**

A: Yes, through inactivity (decay), failed attestations, or risk flags. A 0.9 score can decay to 0.5 in ~30 days of inactivity.

**Q: Is reputation transferable?**

A: No, reputation is bound to wallet address. However, future versions may support cross-chain reputation proofs.

**Q: What happens if I change hardware?**

A: Hardware score will temporarily decrease. Maintain consistent attestations to rebuild. Multiple hardware fingerprints reduce score to 0.7 (2-3) or 0.4 (4+).

**Q: Can I appeal a risk flag?**

A: Yes, flags can be resolved through:
- Time-based expiration (30 days)
- Successful challenge responses
- Manual review by network operators
- Consistent honest behavior

## License

Copyright (c) 2026 RustChain Contributors  
Licensed under MIT License
