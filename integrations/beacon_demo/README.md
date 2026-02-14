# Beacon Integration Demo (Bounty #158)

This folder contains a small, runnable demo that integrates with **Beacon (beacon-skill)**.

What it demonstrates:
- **Heartbeat**: send a signed Beacon v2 heartbeat over UDP
- **Contracts**: run a local contract lifecycle (list -> offer -> accept -> escrow -> active -> settle)

No wallet keys are required. No RTC transfers are performed.

## Prereqs

Python 3.10+ recommended.

Install Beacon:

```bash
pip install beacon-skill
```

## Run (local loopback)

Terminal A (listen):

```bash
python integrations/beacon_demo/beacon_demo.py listen --bind 127.0.0.1 --port 38400 --timeout 8
```

Terminal B (send heartbeat):

```bash
python integrations/beacon_demo/beacon_demo.py send-heartbeat --host 127.0.0.1 --port 38400 --status alive
```

Contracts demo (local state under integrations/beacon_demo/.state):

```bash
python integrations/beacon_demo/beacon_demo.py contracts-demo
```

## Notes

- UDP is bound to loopback by default in the examples above.
- Demo state is written only under `integrations/beacon_demo/.state/`.
