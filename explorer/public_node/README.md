# Public node explorer page

`explorer.html` is the page served at https://rustchain.org/explorer/ and
https://explorer.rustchain.org/.

Deployed on node 1 as `/opt/rustchain/explorer.html`. `public_node_gui.py`
(systemd unit `rustchain-gui`, Flask on 127.0.0.1:5555) returns it with
`send_file` on every request, and nginx proxies `/explorer/` (rustchain.org)
and `/` (explorer.rustchain.org) to that port. Replacing the file takes effect
on the next request; no restart is needed.

The page fetches `/health`, `/epoch`, `/api/miners`, `/agent/stats` and
`/agent/jobs` from its own origin, so each must be proxied to the node by the
nginx vhost serving it. Tests: `tests/test_public_explorer_page.py`.
