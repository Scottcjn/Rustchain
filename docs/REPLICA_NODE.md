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
- The publisher's public key: `deploy/ledger-replication/publisher.pub` in this
  repository (check it against a second source, such as a maintainer, if you
  can; it is what your replica trusts).

## Install

```bash
sudo mkdir -p /opt/rustchain-replica /etc/rustchain-replica /var/lib/rustchain-replica
sudo install -m 755 tools/ledger_snapshot.py /opt/rustchain-replica/ledger_snapshot.py
sudo install -m 644 deploy/ledger-replication/publisher.pub /etc/rustchain-replica/publisher.pub

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

```bash
sudo install -m 644 deploy/ledger-replication/replica/rustchain-replica-pull.service deploy/ledger-replication/replica/rustchain-replica-pull.timer /etc/systemd/system/
sudo install -m 755 deploy/ledger-replication/replica/rustchain-replica-status /usr/local/bin/
sudo systemctl daemon-reload && sudo systemctl enable --now rustchain-replica-pull.timer
```

## Check that you agree with the settlement node

```bash
rustchain-replica-status        # prints both roots and MATCH, or do it by hand:
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
