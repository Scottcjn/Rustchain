// SPDX-License-Identifier: MIT

import assert from 'node:assert/strict';
import test from 'node:test';

import {
  CONTRACT_PULSE_DURATION_SECONDS,
  contractPulseFrame,
} from '../site/beacon/contract-pulse.mjs';

test('a new contract starts with a visible additive glow', () => {
  const frame = contractPulseFrame(0, 0.3);

  assert.equal(frame.done, false);
  assert.ok(frame.glowOpacity >= 0.85);
  assert.ok(frame.glowScale > 1);
});

test('three beats decay inside the bounded animation envelope', () => {
  const firstPeak = contractPulseFrame(0, 0.3);
  const firstValley = contractPulseFrame(CONTRACT_PULSE_DURATION_SECONDS / 6, 0.3);
  const secondPeak = contractPulseFrame(CONTRACT_PULSE_DURATION_SECONDS / 3, 0.3);

  assert.ok(firstValley.glowOpacity < 1e-12);
  assert.ok(secondPeak.glowOpacity > firstValley.glowOpacity);
  assert.ok(secondPeak.glowOpacity < firstPeak.glowOpacity);
});

test('the glow reaches a disposable neutral frame at the deadline', () => {
  const frame = contractPulseFrame(CONTRACT_PULSE_DURATION_SECONDS, 0.6);

  assert.equal(frame.done, true);
  assert.equal(frame.glowOpacity, 0);
  assert.equal(frame.glowScale, 1);
});

test('invalid timing and opacity inputs remain bounded', () => {
  const invalid = contractPulseFrame(Number.NaN, Number.NaN);
  const high = contractPulseFrame(0, 5);
  const low = contractPulseFrame(-10, -5);

  assert.equal(invalid.done, false);
  assert.ok(invalid.glowOpacity >= 0 && invalid.glowOpacity <= 1);
  assert.ok(high.glowOpacity >= 0 && high.glowOpacity <= 1);
  assert.ok(low.glowOpacity >= 0 && low.glowOpacity <= 1);
});
