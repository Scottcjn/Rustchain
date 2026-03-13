#!/usr/bin/env node

/**
 * RustChain Wallet - Phase 2 Self-Test Runner
 *
 * Runs all extension and snap tests with explicit PASS/FAIL output.
 * 
 * Usage: node scripts/run-self-tests.js
 */

import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const rootDir = join(__dirname, '..');

const tests = [
  {
    name: 'Extension: Send/Sign Flow',
    path: join(rootDir, 'extension', 'tests', 'send-sign-flow.test.js'),
    cwd: join(rootDir, 'extension')
  },
  {
    name: 'Extension: Core Tests',
    path: join(rootDir, 'extension', 'tests', 'extension.test.js'),
    cwd: join(rootDir, 'extension')
  },
  {
    name: 'Snap: Unit Tests',
    path: join(rootDir, 'snap', 'tests', 'snap.test.js'),
    cwd: join(rootDir, 'snap')
  },
  {
    name: 'Snap: Integration Tests',
    path: join(rootDir, 'snap', 'tests', 'snap-integration.test.js'),
    cwd: join(rootDir, 'snap')
  }
];

let results = {
  passed: 0,
  failed: 0,
  total: tests.length
};

console.log('╔════════════════════════════════════════════════════════╗');
console.log('║     RustChain Wallet - Phase 2 Self-Test Runner       ║');
console.log('║     Send/Sign Flow + MetaMask Snap Integration        ║');
console.log('╚════════════════════════════════════════════════════════╝');
console.log('');

async function runTest(test) {
  return new Promise((resolve) => {
    console.log(`\n${'─'.repeat(60)}`);
    console.log(`📋 Running: ${test.name}`);
    console.log(`${'─'.repeat(60)}`);

    const proc = spawn('node', ['--test', test.path], {
      cwd: test.cwd,
      stdio: 'inherit'
    });

    proc.on('close', (code) => {
      if (code === 0) {
        results.passed++;
        console.log(`\n✅ ${test.name}: PASSED`);
      } else {
        results.failed++;
        console.log(`\n❌ ${test.name}: FAILED (exit code ${code})`);
      }
      resolve(code === 0);
    });

    proc.on('error', (err) => {
      results.failed++;
      console.log(`\n❌ ${test.name}: ERROR - ${err.message}`);
      resolve(false);
    });
  });
}

async function runAllTests() {
  const startTime = Date.now();

  for (const test of tests) {
    await runTest(test);
  }

  const duration = ((Date.now() - startTime) / 1000).toFixed(2);

  // Print final summary
  console.log('');
  console.log('╔════════════════════════════════════════════════════════╗');
  console.log('║                  FINAL TEST SUMMARY                    ║');
  console.log('╠════════════════════════════════════════════════════════╣');
  console.log(`║  Total Tests:  ${String(results.total).padEnd(34)}║`);
  console.log(`║  ✅ Passed:     ${String(results.passed).padEnd(34)}║`);
  console.log(`║  ❌ Failed:     ${String(results.failed).padEnd(34)}║`);
  console.log(`║  Duration:      ${String(duration + 's').padEnd(34)}║`);
  console.log('╠════════════════════════════════════════════════════════╣');

  if (results.failed === 0) {
    console.log('║  🎉 ALL PHASE 2 TESTS PASSED!                        ║');
    console.log('╚════════════════════════════════════════════════════════╝');
    console.log('');
    console.log('Phase 2 Implementation Complete:');
    console.log('  ✅ Send transaction flow with validation');
    console.log('  ✅ Sign message flow with confirmation');
    console.log('  ✅ MetaMask Snap integration path');
    console.log('  ✅ Fallback behavior (extension-first/snap-first)');
    console.log('  ✅ Address and transaction validation');
    console.log('  ✅ EIP-1193 compatibility layer');
    console.log('');
    process.exit(0);
  } else {
    console.log('║  ⚠️  SOME TESTS FAILED - Review output above           ║');
    console.log('╚════════════════════════════════════════════════════════╝');
    process.exit(1);
  }
}

// Run all tests
runAllTests().catch((err) => {
  console.error('Test runner error:', err);
  process.exit(1);
});
