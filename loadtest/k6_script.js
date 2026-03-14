/**
 * SPDX-License-Identifier: Apache-2.0
 * RustChain API Load Test — k6 script
 * Issue: https://github.com/Scottcjn/rustchain-bounties/issues/1614
 *
 * Usage:
 *   k6 run --insecure-skip-tls-verify k6_script.js
 *
 * NOTE: API uses a self-signed TLS cert — --insecure-skip-tls-verify is required.
 * POST /wallet/transfer/signed is NOT tested — included as a commented mock only.
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

// ─── Config ──────────────────────────────────────────────────────────────────

const BASE_URL = "https://50.28.86.131";

// Custom metrics
const errorRate = new Rate("error_rate");
const healthLatency = new Trend("health_latency", true);
const epochLatency = new Trend("epoch_latency", true);
const balanceLatency = new Trend("balance_latency", true);

// ─── Load stages ─────────────────────────────────────────────────────────────

export const options = {
  stages: [
    { duration: "10s", target: 3 },  // ramp up to 3 users
    { duration: "20s", target: 5 },  // hold at 5 users
    { duration: "10s", target: 0 },  // ramp down
  ],
  thresholds: {
    // 95th percentile response time under 2s
    http_req_duration: ["p(95)<2000"],
    // Error rate under 5%
    error_rate: ["rate<0.05"],
    // Health endpoint p95 under 1s
    health_latency: ["p(95)<1000"],
  },
  // Accept self-signed TLS cert (same as --insecure-skip-tls-verify)
  insecureSkipTLSVerify: true,
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

const params = {
  headers: { "Content-Type": "application/json" },
  // k6 doesn't have a verify=False option at the request level;
  // insecureSkipTLSVerify in options handles it globally.
};

// ─── Main test function ───────────────────────────────────────────────────────

export default function () {
  // 1. Health check
  {
    const res = http.get(`${BASE_URL}/health`, params);
    const ok = check(res, {
      "health: status 200": (r) => r.status === 200,
      "health: has ok field": (r) => {
        try {
          return JSON.parse(r.body).ok === true;
        } catch {
          return false;
        }
      },
    });
    errorRate.add(!ok);
    healthLatency.add(res.timings.duration);
  }

  sleep(0.5);

  // 2. Epoch info
  {
    const res = http.get(`${BASE_URL}/epoch`, params);
    const ok = check(res, {
      "epoch: status 200": (r) => r.status === 200,
      "epoch: has epoch field": (r) => {
        try {
          return "epoch" in JSON.parse(r.body);
        } catch {
          return false;
        }
      },
    });
    errorRate.add(!ok);
    epochLatency.add(res.timings.duration);
  }

  sleep(0.5);

  // 3. Wallet balance
  {
    const res = http.get(
      `${BASE_URL}/wallet/balance?miner_id=loadtest-benchmark`,
      params
    );
    const ok = check(res, {
      "balance: status 200 or 404": (r) => r.status === 200 || r.status === 404,
    });
    errorRate.add(!ok);
    balanceLatency.add(res.timings.duration);
  }

  // 1–3 second think time between iterations
  sleep(1 + Math.random() * 2);
}

// ─── MOCK ONLY — Do NOT uncomment ────────────────────────────────────────────
//
// export function transferMock() {
//   const payload = JSON.stringify({
//     from: "MOCK_FROM_ADDRESS",
//     to: "MOCK_TO_ADDRESS",
//     amount: 0.001,
//     fee: 0.0001,
//     signature: "MOCK_SIGNATURE_NOT_VALID",
//     timestamp: Math.floor(Date.now() / 1000),
//   });
//   // http.post(`${BASE_URL}/wallet/transfer/signed`, payload, params);
// }
