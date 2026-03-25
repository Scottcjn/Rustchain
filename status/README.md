# RustChain Multi-Node Health Dashboard

Real-time status page monitoring all 4 RustChain attestation nodes.

## Features

- **Real-time monitoring** — polls all 4 nodes every 60 seconds
- **Status display** — up/down, response time, version, uptime, active miners, epoch
- **24-hour uptime history** — visual timeline per node
- **Incident log** — automatic detection of outages and recoveries
- **Mobile-friendly** — responsive dark-mode UI
- **RSS feed** — `/feed.xml` for incident notifications
- **API endpoints** — JSON API for integration

## Quickstart

```bash
cd status/
pip install -r requirements.txt
python status_server.py
# Open http://localhost:8050
```

## Deployment

Deploy at `rustchain.org/status` with nginx:

```nginx
location /status {
    proxy_pass http://127.0.0.1:8050/;
    proxy_set_header Host $host;
}
```

## API

| Endpoint | Description |
|---|---|
| `GET /api/status` | Current status of all nodes |
| `GET /api/history/<node-id>` | 24h history for a node |
| `GET /api/incidents` | Recent incidents (last 50) |
| `GET /api/uptime` | 24h uptime percentage per node |
| `GET /feed.xml` | RSS feed for incidents |

## Nodes Monitored

| Node | Endpoint | Location |
|---|---|---|
| Node 1 | `https://50.28.86.131/health` | LiquidWeb US |
| Node 2 | `https://50.28.86.153/health` | LiquidWeb US |
| Node 3 | `http://76.8.228.245:8099/health` | Ryan's Proxmox |
| Node 4 | `http://38.76.217.189:8099/health` | Hong Kong |
