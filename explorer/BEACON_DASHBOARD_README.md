# Beacon Dashboard v1.1 for RustChain

## Overview

The Beacon Dashboard provides real-time monitoring and visualization for RustChain beacon nodes. This dashboard helps validators and node operators track node health, performance metrics, and network status.

## Features

- **Real-time Monitoring**: Live updates on beacon node status
- **Performance Metrics**: Track sync status, peer count, and slot progression
- **Alert System**: Configurable alerts for node issues
- **Historical Data**: View past performance and uptime statistics
- **Multi-Node Support**: Monitor multiple beacon nodes from a single dashboard

## Installation

### Quick Install

```bash
# Clone the repository
git clone https://github.com/Scottcjn/RustChain.git
cd RustChain/explorer

# Install dependencies
pip install -r requirements-beacon-dashboard.txt

# Start the dashboard
python beacon_dashboard_v1.1.py
```

### Docker Installation

```bash
# Using docker-compose
docker-compose -f docker-compose.beacon-dashboard.yml up -d

# Or build manually
docker build -f Dockerfile.beacon-dashboard -t rustchain/beacon-dashboard .
docker run -p 8080:8080 rustchain/beacon-dashboard
```

## Configuration

Edit `config.json` to configure:

- Beacon node RPC endpoints
- Update intervals
- Alert thresholds
- Dashboard port and host

## API Endpoints

- `GET /` - Dashboard UI
- `GET /api/status` - Overall system status
- `GET /api/nodes` - Detailed node information
- `GET /api/metrics` - Performance metrics
- `GET /api/alerts` - Active alerts

## Requirements

- Python 3.8+
- aiohttp
- asyncio
- Modern web browser

## Usage

1. Start the dashboard: `python beacon_dashboard_v1.1.py`
2. Open your browser to `http://localhost:8080`
3. Add your beacon node RPC endpoints in the settings
4. Monitor your nodes in real-time!

## Troubleshooting

### Dashboard won't start
- Check if port 8080 is already in use
- Verify Python dependencies are installed
- Check logs for error messages

### No data showing
- Verify beacon node RPC endpoint is correct
- Ensure beacon node is running and accessible
- Check network connectivity

## Contributing

Contributions welcome! Please submit PRs to the main RustChain repository.

## License

MIT License - See LICENSE file for details

## Support

For issues and questions:
- GitHub Issues: https://github.com/Scottcjn/RustChain/issues
- Discord: RustChain Community Server

---

**Version**: 1.1  
**Author**: RustChain Contributors  
**Last Updated**: 2026-03-13
