# RustChain Docker Miner

Docker configuration for running the RustChain miner in a containerized environment.

## Important Notice

**Docker miners earn minimal rewards (1 billionth of normal) due to RustChain's anti-VM detection.**

RustChain's Proof-of-Antiquity consensus is designed to reward authentic vintage hardware, not virtualized environments. The hardware fingerprinting system detects Docker containers and virtual machines, resulting in drastically reduced rewards.

### Reward Multipliers

- **PowerPC G4 (bare metal)**: 2.5x multiplier = 0.30 RTC/epoch
- **Modern x86 (bare metal)**: 1.0x multiplier = 0.12 RTC/epoch
- **Docker/VM**: 0.0000000025x multiplier = 0.0000000003 RTC/epoch

### Recommended Setup

For maximum rewards, run the miner on:
- Vintage PowerPC hardware (G3/G4/G5)
- Physical x86_64 machines
- IBM POWER8 systems

See the [main README](README.md) for installation instructions.

## Use Cases for Docker

This Docker setup is provided for:
- Development and testing
- Understanding the miner architecture
- CI/CD pipelines
- Environments where bare metal isn't available

## Quick Start

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+

### 1. Build and Run

```bash
# Set your wallet name
export WALLET_NAME="my-docker-miner"

# Build and start the miner
docker-compose up -d

# View logs
docker-compose logs -f
```

### 2. Using Custom Node URL

```bash
# Use a custom RustChain node
export WALLET_NAME="my-docker-miner"
export NODE_URL="https://custom-node.example.com"

docker-compose up -d
```

### 3. Build Only

```bash
# Build the Docker image
docker build -t rustchain-miner .

# Run manually
docker run -d \
  --name rustchain-miner \
  --privileged \
  -e WALLET_NAME="my-docker-miner" \
  -e NODE_URL="https://rustchain.org" \
  rustchain-miner
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WALLET_NAME` | Yes | - | Your miner wallet identifier |
| `NODE_URL` | No | `https://rustchain.org` | RustChain node URL |

### Docker Compose Options

Edit `docker-compose.yml` to customize:

- **Resource Limits**: Adjust CPU and memory limits
- **Restart Policy**: Change restart behavior
- **Logging**: Configure log rotation
- **Health Checks**: Modify health check intervals

## Monitoring

### Check Miner Status

```bash
# View real-time logs
docker-compose logs -f rustchain-miner

# Check container status
docker-compose ps

# View resource usage
docker stats rustchain-miner
```

### Check Wallet Balance

```bash
# Replace with your wallet name
curl -sk "https://rustchain.org/wallet/balance?miner_id=my-docker-miner"
```

### Health Check

```bash
# Check node health
docker-compose exec rustchain-miner curl -sk https://rustchain.org/health
```

## Troubleshooting

### Miner Not Starting

```bash
# Check logs for errors
docker-compose logs rustchain-miner

# Verify environment variables
docker-compose config

# Restart the miner
docker-compose restart rustchain-miner
```

### Low Rewards

This is expected behavior. Docker containers are detected as virtual machines and receive minimal rewards (1 billionth of normal). To earn meaningful rewards, run the miner on bare metal hardware.

### Permission Errors

The miner requires `--privileged` mode to access hardware information via `dmidecode`. This is configured in `docker-compose.yml`.

## Stopping the Miner

```bash
# Stop the miner
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

## Development

### Rebuild After Changes

```bash
# Rebuild and restart
docker-compose up -d --build

# Force rebuild
docker-compose build --no-cache
```

### Run Tests

```bash
# Run miner in test mode
docker-compose run --rm rustchain-miner python -c "import miner; print('Miner loaded successfully')"
```

## Security Notes

- The miner runs with `--privileged` flag to access hardware information
- Only use trusted RustChain node URLs
- Keep your wallet name secure
- Monitor logs for suspicious activity

## Architecture

```
rustchain-miner/
├── Dockerfile              # Container image definition
├── docker-compose.yml      # Orchestration configuration
├── miners/
│   └── linux/
│       ├── rustchain_linux_miner.py    # Main miner script
│       ├── fingerprint_checks.py       # Hardware attestation
│       └── color_logs.py               # Logging utilities
└── DOCKER.md              # This file
```

## Contributing

Improvements to the Docker setup are welcome! Please submit PRs to the main RustChain repository.

## License

MIT License - See [LICENSE](LICENSE) for details

## Related Links

- [RustChain Main Repository](https://github.com/Scottcjn/Rustchain)
- [RustChain Website](https://rustchain.org)
- [Block Explorer](https://rustchain.org/explorer)
- [Bounty Program](https://github.com/Scottcjn/rustchain-bounties)

---

**Remember**: For real mining rewards, use bare metal vintage hardware!
