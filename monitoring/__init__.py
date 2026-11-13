# SPDX-License-Identifier: MIT
"""RustChain monitoring tools.

`monitoring.node_probe` is the single shared, stdlib-only node liveness probe
used by every monitor (status page, health dashboard, Prometheus exporter,
node health monitor, node-health CLI). See issue #17180.
"""
