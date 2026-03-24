/**
 * RustChain API Load Test Suite — k6
 * ====================================
 * Exercises the five core read endpoints.
 *
 * Run:
 *   k6 run k6-test.js                        # default 10 VUs, 30s
 *   k6 run --vus 50 --duration 2m k6-test.js # custom
 *   k6 run --out json=results/k6_raw.json k6-test.js
 *
 * Produce an HTML report (requires xk6-dashboard or k6 cloud):
 *   K6_WEB_DASHBOARD=true k6 run k6-test.js
 */

import http from "k6/http";
import { check, group, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";
import { textSummary } from "https://jslib.k6.io/k6-summary/0.0.3/index.js";
import { htmlReport } from "https://raw.githubusercontent.com/benc-uk/k6-reporter/main/dist/bundle.js";

// ---------------------------------------------------------------------------
// Options — ramp-up, steady, ramp-down
// ---------------------------------------------------------------------------
export const options = {
  insecureSkipTLSVerify: true,
  thresholds: {
    http_req_duration: ["p(95)<3000"], // 95 % of requests under 3 s
    http_req_failed: ["rate<0.05"],    // < 5 % failure rate
  },
  scenarios: {
    smoke: {
      executor: "constant-vus",
      vus: 5,
      duration: "30s",
      tags: { phase: "smoke" },
    },
    load: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "30s", target: 25 },
        { duration: "1m",  target: 25 },
        { duration: "15s", target: 0 },
      ],
      startTime: "35s",
      tags: { phase: "load" },
    },
    stress: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "30s", target: 50 },
        { duration: "1m",  target: 50 },
        { duration: "15s", target: 0 },
      ],
      startTime: "2m30s",
      tags: { phase: "stress" },
    },
  },
};

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
const BASE = __ENV.RUSTCHAIN_HOST || "https://50.28.86.131";
const MINER_ID = __ENV.RUSTCHAIN_MINER_ID || "Ivan-houzhiwen";

// Custom metrics
const healthOk   = new Rate("health_ok");
const epochTrend  = new Trend("epoch_response_ms");
const tipTrend    = new Trend("tip_response_ms");
const minersTrend = new Trend("miners_response_ms");
const balTrend    = new Trend("balance_response_ms");

// ---------------------------------------------------------------------------
// Default function — each VU iteration hits all endpoints
// ---------------------------------------------------------------------------
export default function () {
  group("GET /health", () => {
    const res = http.get(`${BASE}/health`);
    const ok = check(res, {
      "status 200": (r) => r.status === 200,
      "ok is true":  (r) => {
        try { return r.json().ok === true; } catch { return false; }
      },
    });
    healthOk.add(ok ? 1 : 0);
  });

  group("GET /epoch", () => {
    const res = http.get(`${BASE}/epoch`);
    epochTrend.add(res.timings.duration);
    check(res, {
      "status 200":   (r) => r.status === 200,
      "has epoch key": (r) => {
        try { return "epoch" in r.json(); } catch { return false; }
      },
    });
  });

  group("GET /headers/tip", () => {
    const res = http.get(`${BASE}/headers/tip`);
    tipTrend.add(res.timings.duration);
    check(res, {
      "status 200": (r) => r.status === 200,
    });
  });

  group("GET /api/miners", () => {
    const res = http.get(`${BASE}/api/miners`);
    minersTrend.add(res.timings.duration);
    check(res, {
      "status 200": (r) => r.status === 200,
    });
  });

  group("GET /wallet/balance", () => {
    const res = http.get(`${BASE}/wallet/balance?miner_id=${MINER_ID}`);
    balTrend.add(res.timings.duration);
    check(res, {
      "status 200":       (r) => r.status === 200,
      "has amount_rtc":   (r) => {
        try { return "amount_rtc" in r.json(); } catch { return false; }
      },
    });
  });

  sleep(0.5);
}

// ---------------------------------------------------------------------------
// Summary — write both text (stdout) and HTML report
// ---------------------------------------------------------------------------
export function handleSummary(data) {
  return {
    stdout: textSummary(data, { indent: "  ", enableColors: true }),
    "results/k6_report.html": htmlReport(data),
    "results/k6_summary.json": JSON.stringify(data, null, 2),
  };
}
