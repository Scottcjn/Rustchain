# RustChain Python Miner - Docker Setup

Quick start guide for running the RustChain Proof-of-Antiquity miner in Docker.

## Prerequisites

- Docker 20.10+ and Docker Compose v2.0+
- A RustChain wallet address (starts with `RTC...`)
- Network access to a RustChain node

## Quick Start

### 1. Set Environment Variables

```bash
export WALLET_NAME=RTCyour_wallet_address_here
export NODE_URL=https://rustchain.org
```

### 2. Run with Docker Compose (Recommended)

```bash
docker-compose -f docker-compose.miner.yml up -d
```

### 3. Run with Docker CLI

```bash
docker run -d \
  --name rustchain-miner \
  -e WALLET_NAME="$WALLET_NAME" \
  -e NODE_URL="$NODE_URL" \
  --restart unless-stopped \
  rustchain-miner:latest
```

## Configuration

| Variable     | Required | Default                  | Description                    |
|--------------|----------|--------------------------|--------------------------------|
| `WALLET_NAME`| Yes      | -                        | Your RustChain wallet address  |
| `NODE_URL`   | No       | `https://rustchain.org`  | RustChain node endpoint        |
| `BLOCK_TIME` | No       | `600`                    | Block time in seconds          |
| `MINER_TYPE` | No       | `linux`                  | Miner type (linux/macos/etc.)  |
| `MINER_ARCH` | No       | `x86_64`                 | Architecture (x86_64/arm64)    |

## Monitoring

### View Logs

```bash
# Real-time logs
docker-compose -f docker-compose.miner.yml logs -f rustchain-miner

# Last 100 lines
docker-compose -f docker-compose.miner.yml logs --tail=100 rustchain-miner
```

### Check Status

```bash
# Container status
docker ps | grep rustchain-miner

# Health check
docker inspect --format='{{.State.Health.Status}}' rustchain-miner
```

## Validation

### Quick Health Check

```bash
# Test node connectivity
curl -f "$NODE_URL/health" || echo "Node unreachable"

# Verify miner is running
docker exec rustchain-miner python3 -c "print('OK')"
```

### Verify Wallet Registration

```bash
# Check if wallet is enrolled (replace with your wallet)
curl -s "$NODE_URL/api/miners" | jq '.miners[] | select(.wallet_name=="'"$WALLET_NAME"'")'
```

### Expected Log Output

On successful start, you should see:

```
========================================
RustChain Proof-of-Antiquity Miner
Docker Container Edition
========================================
[CONFIG] Wallet: RTCyour_wallet_address
[CONFIG] Node URL: https://rustchain.org
[CONFIG] Block Time: 600 seconds
[INFO] Running x86_64 Linux miner
[WARN] ========== IMPORTANT NOTICE ==========
[WARN] Docker miners receive REDUCED REWARDS due to anti-VM detection.
[WARN] For maximum rewards, run the miner directly on physical hardware.
[WARN] ======================================
[START] Launching miner: miners/linux/rustchain_linux_miner.py
```

### Troubleshooting

| Issue                          | Solution                                      |
|--------------------------------|-----------------------------------------------|
| `WALLET_NAME` error            | Set `-e WALLET_NAME=RTC...` in docker run     |
| Node connection failed         | Check `NODE_URL` and network connectivity     |
| Container exits immediately    | Check logs: `docker-compose logs rustchain-miner` |
| Reduced rewards warning        | Expected - Docker/VM detection is intentional |

## Building from Source

```bash
# Build the image
docker build -t rustchain-miner:latest -f Dockerfile.miner .

# Build with specific architecture
docker build -t rustchain-miner:arm64 \
  --build-arg MINER_TYPE=linux \
  --build-arg MINER_ARCH=arm64 \
  -f Dockerfile.miner .
```

## Stopping the Miner

```bash
# Docker Compose
docker-compose -f docker-compose.miner.yml down

# Docker CLI
docker stop rustchain-miner && docker rm rustchain-miner
```

## Important Notes

> ⚠️ **Reduced Rewards**: Docker miners receive reduced rewards due to RustChain's anti-VM detection mechanism. For full rewards, run the miner directly on physical hardware.

> 🔒 **Security**: The container runs as a non-root user (`rustchain`, UID 1000) following security best practices.

## License

Same as RustChain project. See main `LICENSE` file.
