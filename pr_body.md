Fixes the gap in Scottcjn/rustchain-bounties#17180: every node monitor
decided "up" from the HTTP status code alone, so a host replaced by an
unrelated SPA answering 200 on every path stayed green forever.

## The shared probe

`monitoring/node_probe.py` (stdlib-only, Python 3.9+) is now the one place
that classifies a `/health` answer. `classify_health(status_code,
content_type, body)` is a pure function; `probe_health(url, timeout)`
fetches with urllib and classifies. States:

- `up` — HTTP 200, JSON object with `ok` (bool), `version` (non-empty
  string), `uptime_s` (number >= 0), `ok` true, `db_rw` not false,
  `tip_age_slots` within threshold (default 600).
- `degraded` — a real node reporting `ok: false`, `db_rw: false`, or a
  `tip_age_slots` above the threshold. The node itself answers 503 when
  `ok` is false, so this is `degraded` on either status.
- `impostor` — HTTP 200 but the body is `text/html`, not JSON, not a JSON
  object, or JSON missing `ok` / `version` / `uptime_s`.
- `down` — the node answered with an HTTP error status.
- `unreachable` — no HTTP response at all.

The genuine body shape is taken from the node's own `api_health`
(`ok`, `version`, `uptime_s`, `db_rw`, `backup_age_hours`,
`tip_age_slots`, `settlement_lag_epochs`, `last_settled_epoch`).

## Per-monitor wiring

- Prometheus exporter — imports `node_probe` directly (same directory;
  `Dockerfile.exporter` now copies it in). `rustchain_node_health` is set
  to 0 on any failed scrape instead of keeping the last value, and two new
  metrics are exported: `rustchain_last_successful_scrape_timestamp`
  (moves only on a genuine node body) and
  `rustchain_node_health_state_info{state="..."}`.
- Status page — imports the shared module off the repo root. `check_node`
  returns the probe `state`; the page renders `impostor` / `degraded` as
  their own badges, and `/api/status` reports `overall: "impostor"` when
  any node is one.
- Health dashboard — vendors `classify_health`. Its Docker build context
  is `health-dashboard/`, so COPY cannot reach `../monitoring/node_probe.py`,
  and restructuring the build context is out of scope here. The vendored
  copy is byte-identical to the canonical one and a parity test enforces
  that. Transport failures keep the existing `down` mapping; response
  states come from the probe. The badge, map marker and `/api/status`
  counts (`nodes_impostor`, `nodes_degraded`) all show the new states, and
  an impostor transition logs a `node_down` incident like a down does.
- `tools/node_health_monitor.py` — imports the shared module in a
  checkout and falls back to the vendored copy when copied out on its own
  (it is a standalone stdlib-only script). The epoch probe still decides
  `status` (`online` / `slow` / `offline`, pinned by the existing liveness
  tests); the `/health` verdict is attached as `health_state` /
  `health_detail`, shown in the table and JSON, and raises `IMPOSTOR` /
  `DEGRADED` alerts.
- `tools/node-health-cli/node_health.py` — same import-with-fallback
  (the README promises a standalone script). `check_health` now returns a
  distinct `state` on `HealthStatus`; an impostor fails the run with a
  non-zero exit code.

## Tests

Recorded fixtures in `monitoring/test_node_probe.py`: a genuine body, an
HTML SPA body with 200, JSON missing keys, `ok: false`, a 500 and a
timeout, plus `db_rw: false` and stale-tip degraded cases.
`monitoring/test_impostor_across_monitors.py` asserts the HTML-200
fixture comes out `impostor` in every monitor's own output, checks the
exporter gauge goes to 0 (and the timestamp does not move) on a bad
scrape, and asserts every vendored copy returns the canonical verdict on
all fixtures.

Local results (Python 3.13, pytest):

- new tests: 26 (probe) + 15 (cross-monitor) = 41 passed
- existing suites still green: status 19, health-dashboard 24,
  node-health-cli 25, tests/test_health_monitor.py 21,
  test_node_liveness_requires_node_state.py 14,
  test_node_health_total_miners.py 3, monitoring/alerts/tests/ 45 passed
- tests/test_settlement_lag_visibility.py is NOT in the CI step: its
  NodeHelperTest setup errors identically on clean upstream main
  (duplicate prometheus registration when the node module loads), so
  including it would turn the step red for a pre-existing reason.
- the new tests run in CI (new "Monitor probe tests" step in
  .github/workflows/ci.yml; alerts tests run in a separate invocation
  because monitoring/alerts/tests/ and tests/ share basenames, so pytest
  cannot collect both in one run — also pre-existing).

I also ran both tools copied alone against a local SPA answering 200 +
HTML on every path: the monitor reports `health_state: impostor` with an
IMPOSTOR alert, the CLI reports `state: impostor` and exits non-zero.

No production config changes, no new endpoints on the node, monitors only.
