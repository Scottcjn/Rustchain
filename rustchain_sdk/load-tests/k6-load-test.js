/**
 * RustChain API Load Test Suite (k6)
 * 
 * Usage:
 *   k6 run --config k6-config.json k6-load-test.js
 *   k6 run -e TARGET_URL=https://rustchain.org -e RATE_LIMIT=30 k6-load-test.js
 * 
 * Environment Variables:
 *   TARGET_URL    - API base URL (default: https://rustchain.org)
 *   RATE_LIMIT    - Requests per second (default: 30)
 *   DURATION      - Test duration (default: 5m)
 *   VUS           - Virtual users (default: 10)
 *   MINER_ID      - Miner wallet ID for testing (default: scott)
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const apiLatency = new Trend('api_latency_ms');
const healthCheckPass = new Rate('health_check_pass');
const epochCheckPass = new Rate('epoch_check_pass');
const minersCheckPass = new Rate('miners_check_pass');
const balanceCheckPass = new Rate('balance_check_pass');

// Configuration from environment or defaults
const BASE_URL = __ENV.TARGET_URL || 'https://rustchain.org';
const TEST_MINER_ID = __ENV.MINER_ID || 'scott';

// Test scenarios configuration
export const options = {
  // Default scenario - can be overridden via --config
  scenarios: {
    // Smoke test: quick health check
    smoke: {
      executor: 'constant-vus',
      vus: 1,
      duration: '30s',
      tags: { test_type: 'smoke' },
    },
    // Load test: sustained load
    load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '1m', target: 10 },  // Ramp up
        { duration: '3m', target: 10 },  // Sustained load
        { duration: '1m', target: 0 },   // Ramp down
      ],
      tags: { test_type: 'load' },
      startTime: '35s',
    },
    // Stress test: peak load
    stress: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 50 },  // Ramp to stress
        { duration: '2m', target: 50 },  // Hold stress
        { duration: '1m', target: 100 }, // Spike
        { duration: '1m', target: 0 },   // Recovery
      ],
      tags: { test_type: 'stress' },
      startTime: '8m5s',
    },
  },
  thresholds: {
    http_req_duration: ['p(50)<500', 'p(95)<2000', 'p(99)<5000'],
    http_req_failed: ['rate<0.05'],
    errors: ['rate<0.1'],
    health_check_pass: ['rate>0.95'],
    epoch_check_pass: ['rate>0.95'],
    miners_check_pass: ['rate>0.95'],
    balance_check_pass: ['rate>0.90'],
  },
};

/**
 * Test the /health endpoint
 */
function testHealth() {
  const response = http.get(`${BASE_URL}/health`, {
    tags: { name: 'health' },
  });
  
  const passed = check(response, {
    'health status is 200': (r) => r.status === 200,
    'health response has ok field': (r) => {
      try {
        const body = r.json();
        return body.ok === true;
      } catch (e) {
        return false;
      }
    },
    'health response has version': (r) => {
      try {
        const body = r.json();
        return body.version !== undefined;
      } catch (e) {
        return false;
      }
    },
  });
  
  healthCheckPass.add(passed);
  errorRate.add(!passed);
  apiLatency.add(response.timings.duration);
  
  sleep(0.5);
}

/**
 * Test the /epoch endpoint
 */
function testEpoch() {
  const response = http.get(`${BASE_URL}/epoch`, {
    tags: { name: 'epoch' },
  });
  
  const passed = check(response, {
    'epoch status is 200': (r) => r.status === 200,
    'epoch response has epoch field': (r) => {
      try {
        const body = r.json();
        return typeof body.epoch === 'number';
      } catch (e) {
        return false;
      }
    },
    'epoch response has slot field': (r) => {
      try {
        const body = r.json();
        return typeof body.slot === 'number';
      } catch (e) {
        return false;
      }
    },
  });
  
  epochCheckPass.add(passed);
  errorRate.add(!passed);
  apiLatency.add(response.timings.duration);
  
  sleep(0.3);
}

/**
 * Test the /api/miners endpoint
 */
function testMiners() {
  const response = http.get(`${BASE_URL}/api/miners`, {
    tags: { name: 'miners' },
  });
  
  const passed = check(response, {
    'miners status is 200': (r) => r.status === 200,
    'miners response is array': (r) => {
      try {
        const body = r.json();
        return Array.isArray(body);
      } catch (e) {
        return false;
      }
    },
  });
  
  minersCheckPass.add(passed);
  errorRate.add(!passed);
  apiLatency.add(response.timings.duration);
  
  sleep(0.5);
}

/**
 * Test the /wallet/balance endpoint
 */
function testBalance() {
  const params = {
    params: { miner_id: TEST_MINER_ID },
    tags: { name: 'balance' },
  };
  
  const response = http.get(`${BASE_URL}/wallet/balance`, params);
  
  const passed = check(response, {
    'balance status is 200': (r) => r.status === 200,
    'balance response has ok field': (r) => {
      try {
        const body = r.json();
        return body.ok !== undefined;
      } catch (e) {
        return false;
      }
    },
  });
  
  balanceCheckPass.add(passed);
  errorRate.add(!passed);
  apiLatency.add(response.timings.duration);
  
  sleep(0.3);
}

/**
 * Test the /ready endpoint (Kubernetes readiness probe)
 */
function testReady() {
  const response = http.get(`${BASE_URL}/ready`, {
    tags: { name: 'ready' },
  });
  
  check(response, {
    'ready status is 200': (r) => r.status === 200,
    'ready response indicates ready': (r) => {
      try {
        const body = r.json();
        return body.ready === true;
      } catch (e) {
        return false;
      }
    },
  });
  
  sleep(0.2);
}

/**
 * Test the /governance/proposals endpoint
 */
function testGovernance() {
  const response = http.get(`${BASE_URL}/governance/proposals`, {
    tags: { name: 'governance_proposals' },
  });
  
  check(response, {
    'governance proposals status is 200': (r) => r.status === 200,
  });
  
  sleep(0.3);
}

/**
 * Test the /api/nodes endpoint
 */
function testNodes() {
  const response = http.get(`${BASE_URL}/api/nodes`, {
    tags: { name: 'nodes' },
  });
  
  check(response, {
    'nodes status is 200': (r) => r.status === 200,
  });
  
  sleep(0.3);
}

/**
 * Main load test function - executes all endpoint tests
 */
export default function () {
  // Execute all endpoint tests
  testHealth();
  testEpoch();
  testMiners();
  testBalance();
  testReady();
  testGovernance();
  testNodes();
}

/**
 * Handle test start - log configuration
 */
export function handleSummary(data) {
  const summary = {
    test_info: {
      target_url: BASE_URL,
      test_miner_id: TEST_MINER_ID,
      timestamp: new Date().toISOString(),
    },
    metrics: {
      total_requests: data.metrics.http_reqs ? data.metrics.http_reqs.values.count : 0,
      request_rate: data.metrics.http_reqs ? data.metrics.http_reqs.values.rate : 0,
      error_rate: data.metrics.errors ? data.metrics.errors.values.rate : 0,
      avg_latency_ms: data.metrics.api_latency_ms ? data.metrics.api_latency_ms.values.avg : 0,
      p95_latency_ms: data.metrics.api_latency_ms ? data.metrics.api_latency_ms.values['p(95)'] : 0,
      p99_latency_ms: data.metrics.api_latency_ms ? data.metrics.api_latency_ms.values['p(99)'] : 0,
    },
    checks: {
      health_pass_rate: data.metrics.health_check_pass ? data.metrics.health_check_pass.values.rate : 0,
      epoch_pass_rate: data.metrics.epoch_check_pass ? data.metrics.epoch_check_pass.values.rate : 0,
      miners_pass_rate: data.metrics.miners_check_pass ? data.metrics.miners_check_pass.values.rate : 0,
      balance_pass_rate: data.metrics.balance_check_pass ? data.metrics.balance_check_pass.values.rate : 0,
    },
  };
  
  return {
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
    'load-test-results.json': JSON.stringify(summary, null, 2),
  };
}

function textSummary(data, options) {
  const { indent = '', enableColors = false } = options;
  
  let output = '\n';
  output += `${indent}═══════════════════════════════════════════════════════════\n`;
  output += `${indent}  RustChain API Load Test Results\n`;
  output += `${indent}═══════════════════════════════════════════════════════════\n\n`;
  
  output += `${indent}Target URL: ${BASE_URL}\n`;
  output += `${indent}Test Miner: ${TEST_MINER_ID}\n\n`;
  
  if (data.metrics.http_reqs) {
    output += `${indent}Requests:\n`;
    output += `${indent}  Total: ${data.metrics.http_reqs.values.count}\n`;
    output += `${indent}  Rate:  ${data.metrics.http_reqs.values.rate.toFixed(2)} req/s\n\n`;
  }
  
  if (data.metrics.api_latency_ms) {
    output += `${indent}Latency:\n`;
    output += `${indent}  Avg:  ${data.metrics.api_latency_ms.values.avg.toFixed(2)} ms\n`;
    output += `${indent}  P95:  ${data.metrics.api_latency_ms.values['p(95)'].toFixed(2)} ms\n`;
    output += `${indent}  P99:  ${data.metrics.api_latency_ms.values['p(99)'].toFixed(2)} ms\n\n`;
  }
  
  if (data.metrics.errors) {
    output += `${indent}Error Rate: ${(data.metrics.errors.values.rate * 100).toFixed(2)}%\n\n`;
  }
  
  output += `${indent}Check Pass Rates:\n`;
  if (data.metrics.health_check_pass) {
    output += `${indent}  Health:  ${(data.metrics.health_check_pass.values.rate * 100).toFixed(1)}%\n`;
  }
  if (data.metrics.epoch_check_pass) {
    output += `${indent}  Epoch:   ${(data.metrics.epoch_check_pass.values.rate * 100).toFixed(1)}%\n`;
  }
  if (data.metrics.miners_check_pass) {
    output += `${indent}  Miners:  ${(data.metrics.miners_check_pass.values.rate * 100).toFixed(1)}%\n`;
  }
  if (data.metrics.balance_check_pass) {
    output += `${indent}  Balance: ${(data.metrics.balance_check_pass.values.rate * 100).toFixed(1)}%\n`;
  }
  
  output += `\n${indent}═══════════════════════════════════════════════════════════\n`;
  
  return output;
}
