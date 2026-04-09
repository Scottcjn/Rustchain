# RustChain Docker Miner - Quick Start

## One-Command Run

```bash
docker run -d \
  --name rustchain-miner \
  -e WALLET=your-wallet-name \
  ghcr.io/scottcjn/rustchain-miner:latest
```

## Using docker-compose

```bash
# 1. Clone this repo
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain

# 2. Create .env file
echo "WALLET_NAME=your-wallet-name" > .env

# 3. Start miner
docker compose -f docker-compose.miner.yml up -d
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| WALLET_NAME | (required) | Your RTC wallet name |
| NODE_URL | https://rustchain.org | Node URL |
| BLOCK_TIME | 600 | Block time in seconds |

## Health Check

The container includes a health check that verifies node connectivity.

## Building locally

```bash
docker build -f Dockerfile.miner -t rustchain-miner .
```

## Note

Docker miners receive reduced rewards due to anti-VM detection. For maximum rewards, run on physical hardware.

---

**Bounty:** 15 RTC
**Issue:** https://github.com/Scottcjn/rustchain-bounties/issues/2865
