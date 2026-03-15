# RustChain Development Environment

A Docker Compose stack that brings up everything you need to develop and test against RustChain locally.

## Services

| Service | Port | Description |
|---------|------|-------------|
| **RustChain Node** | `8099` | PoA blockchain node with dashboard and API |
| **MongoDB** | `27017` | Block and transaction storage |
| **Redis** | `6379` | Caching layer (LRU, 128 MB limit) |
| **Prometheus** | `9090` | Metrics collection (15-day retention) |
| **Grafana** | `3000` | Pre-configured dashboards for network monitoring |

## Quick Start

```bash
# One-command setup
chmod +x dev-setup.sh
./dev-setup.sh
```

Or manually:

```bash
cp .env.dev.example .env    # customise ports / passwords if needed
docker compose -f docker-compose.dev.yml up -d
```

## Prerequisites

- Docker Engine 24+
- Docker Compose v2 plugin

## Configuration

All tuneable settings live in `.env` (created from `.env.example` on first run).

| Variable | Default | Purpose |
|----------|---------|---------|
| `NODE_PORT` | `8099` | Host port for the RustChain node dashboard |
| `MONGO_PORT` | `27017` | Host port for MongoDB |
| `REDIS_PORT` | `6379` | Host port for Redis |
| `PROMETHEUS_PORT` | `9090` | Host port for Prometheus |
| `GRAFANA_PORT` | `3000` | Host port for Grafana |
| `GRAFANA_USER` | `admin` | Grafana admin username |
| `GRAFANA_PASSWORD` | `rustchain` | Grafana admin password |

## Monitoring

Grafana is pre-provisioned with:

- **Prometheus datasource** pointing at the in-stack Prometheus instance.
- **RustChain Network Monitor dashboard** showing node health, active miners, epoch info, hardware breakdown, and scrape latency.

Open Grafana at `http://localhost:3000` and log in with the credentials from your `.env` file (defaults: `admin` / `rustchain`).

## Common Commands

```bash
# View logs (all services)
docker compose -f docker-compose.dev.yml logs -f

# View logs (single service)
docker compose -f docker-compose.dev.yml logs -f rustchain-node

# Restart a single service
docker compose -f docker-compose.dev.yml restart rustchain-node

# Stop everything
docker compose -f docker-compose.dev.yml down

# Stop everything and delete volumes (full reset)
docker compose -f docker-compose.dev.yml down -v

# Rebuild after code changes
docker compose -f docker-compose.dev.yml up -d --build rustchain-node
```

## Architecture

```
                  ┌─────────────┐
                  │  Grafana    │ :3000
                  └──────┬──────┘
                         │
                  ┌──────▼──────┐
                  │ Prometheus  │ :9090
                  └──────┬──────┘
                         │
                  ┌──────▼──────┐
                  │  Exporter   │ :9100 (internal)
                  └──────┬──────┘
                         │
              ┌──────────▼──────────┐
              │   RustChain Node    │ :8099
              └───┬────────────┬────┘
                  │            │
          ┌───────▼──┐   ┌────▼────┐
          │ MongoDB  │   │  Redis  │
          │  :27017  │   │  :6379  │
          └──────────┘   └─────────┘
```

## Development Tips

- The node source directory (`./node`) is bind-mounted read-only, so edits are reflected on container restart without a full rebuild.
- MongoDB is initialised with the `rustchain` database automatically; no seed scripts are required.
- Redis is configured with `allkeys-lru` eviction so it will never run out of memory during development.
- Prometheus is configured with `--web.enable-lifecycle` so you can hot-reload its config by sending `POST /-/reload`.
