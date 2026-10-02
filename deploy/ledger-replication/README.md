# Ledger replication: what is deployed

These are the files that run in production next to `tools/ledger_snapshot.py`.
They are here so a publisher or a replica can be rebuilt from the repository
alone. Operator steps for a replica are in [docs/REPLICA_NODE.md](../../docs/REPLICA_NODE.md).

| Path | Runs on | What it is |
|---|---|---|
| `publisher.pub` | everywhere | The settlement node's Ed25519 public key. Replicas pin it. The private key exists only on the settlement node (`/etc/rustchain-state/publisher.key`). |
| `publisher/rustchain-state-snapshot.{service,timer}` | settlement node | Publishes a signed manifest and snapshot every 10 minutes at `:04`, clear of the rewards run. |
| `publisher/nginx-state.conf` | settlement node | `/state/manifest.json` for everyone; `/state/snapshots/…` for allowlisted replica addresses. |
| `replica/rustchain-replica-pull.{service,timer}` | replicas | Pulls, verifies and installs at `:07`. |
| `replica/rustchain-replica-status` | replicas | Prints the replica's state root next to the settlement node's. |
| `follower/nginx-follower*.conf` | a node that must not answer from its own database | Redirects every ledger route to the settlement node with a 307; `/health`, `/ready` and `/p2p/` stay local. |
| `follower/rustchain-follower-check*` | the same node | Every 10 minutes: fails, and mails `ALERT_EMAIL`, if a ledger route is answered locally again. |

Layout on disk: tool at `/opt/rustchain-state/` (publisher) or
`/opt/rustchain-replica/` (replica); output in `/var/lib/rustchain-state/` or
`/var/lib/rustchain-replica/current/`.

Adding a replica: add its public IP to the `allow` lines in
`publisher/nginx-state.conf` on the settlement node, reload nginx, then follow
the operator guide on the new machine.

If the publisher key is ever replaced, every replica must be given the new
`publisher.pub` and run one pull with `--allow-regress`.
