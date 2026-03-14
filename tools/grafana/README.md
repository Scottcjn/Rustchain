# RustChain Grafana Dashboard

A comprehensive Grafana dashboard for monitoring the RustChain network via Prometheus metrics.

## Panels

### Network Health
- **Node Status** — UP/DOWN indicator with color-coded background
- **Node Uptime** — how long the node has been running
- **Current Epoch** — the active epoch number
- **Current Slot (Block Height)** — latest slot/block
- **Epoch Progress** — gauge showing progress through the current epoch
- **Epoch Time Remaining** — countdown to next epoch

### Mining & Attestation
- **Active Miners** — miners that attested in the last 30 minutes
- **Enrolled Miners** — total enrolled miner count
- **Miner Participation Rate** — active/enrolled ratio gauge
- **Slots/Hour (Mining Rate)** — block production rate
- **Total Attestations** — cumulative attestation count
- **Total Machines** — registered machine count
- **Active vs Enrolled Miners Over Time** — time series comparison
- **Mining Rate (Slots per Hour)** — bar chart of block throughput

### RTC Token Metrics & Balances
- **Total Fees Collected (RTC)** — cumulative fee pool
- **Fee Events (Tx Volume)** — total transaction/fee events
- **Fee Events/Hour** — recent transaction throughput
- **Highest Rust Score** — top antiquity score
- **Top 15 Miner Balances (RTC)** — time series of richest miners
- **Fee Pool Over Time** — fees and events trend

### Chain Sync & Epoch Timeline
- **Epoch & Slot Progression** — dual-axis time series
- **Epoch Sync Progress Over Time** — epoch completion tracking

### Hall of Fame & Miner Details
- **Hall of Fame Metrics** — machines, attestations, rust scores
- **Miner Last Attestation Time** — per-miner attest timestamps
- **Oldest Machine Year** / **Fees 24h** / **Avg Balance** / **Total RTC Supply**

## Import

1. In Grafana, go to **Dashboards > Import**.
2. Upload `rustchain-dashboard.json` or paste its contents.
3. Select your Prometheus datasource when prompted.
4. Click **Import**.

## Prerequisites

- The [RustChain Prometheus exporter](../prometheus/) must be running and scraped by Prometheus.
- Grafana 10.x+ recommended (schema version 39).

## Visual Style

The dashboard uses RustChain's purple accent palette:
- Primary: `#8b5cf6`
- Secondary: `#a78bfa`
- Tertiary: `#c4b5fd`
- Dark theme enabled by default
