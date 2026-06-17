# Node Operator Guide

Run a RustChain attestation node to help secure the network.

## Requirements

- Linux server (Ubuntu 22.04+ recommended)
- Python 3.8+
- 2+ GB RAM
- 10+ GB disk
- Public IP or domain
- Open ports: 80/443 (API), custom for attestation

## Setup

```bash
git clone https://github.com/Scottcjn/Rustchain
cd Rustchain
pip install -r requirements.txt
```

## Configuration

Create `.env`:
```bash
NODE_HOST=0.0.0.0
NODE_PORT=80
ATTEST_PORT=8099
ADMIN_KEY=your-secure-random-key
```

## Run

```bash
python3 src/main.py
```

## Systemd Unit

```ini
[Unit]
Description=RustChain Attestation Node
After=network.target

[Service]
Type=simple
User=rustchain
WorkingDirectory=/opt/rustchain
ExecStart=/usr/bin/python3 src/main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## Health Monitoring

```bash
curl localhost/health
```

Set up Prometheus exporter (see docs/guides/MONITORING.md).

## Current Nodes

| Node | Location | Hardware |
|------|----------|----------|
| 50.28.86.131 | Louisiana, US | LiquidWeb VPS |
| 50.28.86.153 | Louisiana, US | LiquidWeb VPS |
| 76.8.228.245:8099 | US | Proxmox |
| 38.76.217.189:8099 | Hong Kong | CognetCloud |
| Local Lab | - | IBM POWER8 S824 |

## Security

- Use TLS with valid certificates
- Restrict admin endpoints to localhost
- Rate-limit attestation submissions
- Monitor for VM/emulator farming attempts
