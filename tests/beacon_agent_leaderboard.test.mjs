// SPDX-License-Identifier: MIT

import assert from 'node:assert/strict';
import test from 'node:test';

import { buildAgentLeaderboard } from '../site/beacon/leaderboard.mjs';

const agents = [
  { id: 'bcn_beta', name: 'Beta', beat_count: 8 },
  { id: 'bcn_alpha', name: 'Alpha', beat_count: 8 },
  { id: 'bcn_gamma', name: 'Gamma', beat_count: 3 },
  { id: 'bcn_idle', name: 'Idle', beat_count: 0 },
];

const contracts = [
  { id: 'ctr-1', from: 'bcn_alpha', to: 'bcn_gamma' },
  { id: 'ctr-2', from: 'bcn_gamma', to: 'bcn_beta' },
  { id: 'ctr-3', from: 'bcn_gamma', to: 'bcn_gamma' },
];

test('beat mode ranks by heartbeats, then contracts, then name', () => {
  const ranked = buildAgentLeaderboard(agents, contracts, {}, 'beats');

  assert.deepEqual(ranked.map(entry => entry.id), [
    'bcn_alpha',
    'bcn_beta',
    'bcn_gamma',
  ]);
  assert.deepEqual(ranked.map(entry => entry.beats), [8, 8, 3]);
});

test('contract mode combines visible relationships with reputation history', () => {
  const ranked = buildAgentLeaderboard(
    agents,
    contracts,
    { bcn_beta: { contracts_completed: 7 } },
    'contracts',
  );

  assert.equal(ranked[0].id, 'bcn_beta');
  assert.equal(ranked[0].contracts, 7);
  assert.equal(ranked.find(entry => entry.id === 'bcn_gamma').contracts, 3);
});

test('duplicate contract ids and self-contracts count once per agent', () => {
  const ranked = buildAgentLeaderboard(
    [{ id: 'bcn_one', name: 'One', beat_count: 1 }],
    [
      { id: 'same', from: 'bcn_one', to: 'bcn_one' },
      { id: 'same', from: 'bcn_one', to: 'bcn_other' },
    ],
    {},
    'contracts',
  );

  assert.equal(ranked[0].contracts, 1);
});

test('malformed counts fail closed and source arrays are not mutated', () => {
  const sourceAgents = [
    { id: 'bcn_bad', name: 'Bad', beat_count: '<script>' },
    { id: 'bcn_good', name: 'Good', beat_count: 2.9 },
    { id: 'bcn_good', name: 'Duplicate', beat_count: 99 },
    null,
  ];
  const snapshot = structuredClone(sourceAgents);

  const ranked = buildAgentLeaderboard(
    sourceAgents,
    [],
    { bcn_bad: { contracts_completed: Number.POSITIVE_INFINITY } },
    'unknown-mode',
  );

  assert.deepEqual(ranked, [{ id: 'bcn_good', name: 'Good', beats: 2, contracts: 0 }]);
  assert.deepEqual(sourceAgents, snapshot);
});

test('limit is bounded and invalid input returns an empty leaderboard', () => {
  assert.deepEqual(buildAgentLeaderboard(null, null), []);
  assert.equal(buildAgentLeaderboard(agents, contracts, {}, 'beats', 2).length, 2);
});
