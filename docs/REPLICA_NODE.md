# Running a verified ledger replica

A replica holds a copy of the settlement node's ledger and proves it is the
same one. It does not settle epochs, accept transfers or pay rewards; the
settlement node does that. What a replica gives the network is an
independently held, independently checkable copy of the ledger.

## What you need

- Linux, Python 3.9+, the `openssl` binary (3.0+), `curl`.
- About 50 MB of disk.
- Outbound HTTPS to `rustchain.org`.
- Your machine's public IP address added to the settlement node's snapshot
  allowlist. Ask a maintainer; the signed manifest is public, the snapshot
  files are served to known replicas.
- The publisher's public key (`publisher.pub`). Get it from a maintainer over
  a channel you trust, not from the same place you download snapshots.

## Install

```bash
sudo mkdir -p /opt/rustchain-replica /etc/rustchain-replica /var/lib/rustchain-replica
sudo install -m 755 tools/ledger_snapshot.py /opt/rustchain-replica/ledger_snapshot.py
sudo install -m 644 publisher.pub /etc/rustchain-replica/publisher.pub

# one pull by hand
sudo python3 /opt/rustchain-replica/ledger_snapshot.py pull \
    --base-url https://rustchain.org/state/ \
    --pubkey /etc/rustchain-replica/publisher.pub \
    --dest-dir /var/lib/rustchain-replica
```

The pull verifies the publisher's signature, the signed sizes and the state
root recomputed from the rows it received. It installs nothing unless all
three hold.

Run it on a timer, a few minutes after the publisher's schedule (`:04` past
every ten minutes):

```ini
# /etc/systemd/system/rustchain-replica-pull.service
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /opt/rustchain-replica/ledger_snapshot.py pull --base-url https://rustchain.org/state/ --pubkey /etc/rustchain-replica/publisher.pub --dest-dir /var/lib/rustchain-replica

# /etc/systemd/system/rustchain-replica-pull.timer
[Timer]
OnCalendar=*:07/10
Persistent=true
[Install]
WantedBy=timers.target
```

## Check that you agree with the settlement node

```bash
python3 /opt/rustchain-replica/ledger_snapshot.py root --db /var/lib/rustchain-replica/current/ledger.db
curl -s https://rustchain.org/state/manifest.json | python3 -c 'import json,sys; print(json.loads(json.load(sys.stdin)["payload"])["state_root"])'
```

The two lines are equal, or yours is one publish cycle behind.

## If you also run the node software

- Set `RC_NODE_ROLE=sync` and leave `RC_P2P_SECRET` unset. A `401` on
  `/p2p/*` is expected for a node that is not part of the settlement fleet.
- Do not expose the node's port (8099) to the internet. A node that is not
  the settlement node has its own empty ledger; answering balance or transfer
  requests from it would give people wrong answers. Point clients at
  `https://rustchain.org`.
- Keep the code current with `main`.
