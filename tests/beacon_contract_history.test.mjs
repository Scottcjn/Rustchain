// SPDX-License-Identifier: MIT

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildContractHistory,
  contractTimeMillis,
  contractTimestampIso,
  formatContractTimestamp,
} from '../site/beacon/contract-history.mjs';

test('buildContractHistory filters both directions and sorts newest first', () => {
  const history = buildContractHistory([
    {
      id: 'ctr-old-incoming', from: 'bcn_bob', to: 'bcn_alice',
      type: 'rent', amount: 4, currency: 'RTC', term: '7d',
      state: 'completed', created_at: 1_700_000_000,
    },
    {
      id: 'ctr-unrelated', from: 'bcn_carol', to: 'bcn_dan',
      type: 'buy', amount: 9, currency: 'RTC', term: 'once',
      state: 'active', created_at: 1_900_000_000,
    },
    {
      id: 'ctr-new-outgoing', from: 'bcn_alice', to: 'bcn_carol',
      type: 'bounty', amount: 15, currency: 'RTC', term: '14d',
      state: 'active', created_at: 1_800_000_000,
    },
  ], 'bcn_alice');

  assert.deepEqual(history.map(contract => contract.id), [
    'ctr-new-outgoing',
    'ctr-old-incoming',
  ]);
  assert.deepEqual(
    history.map(({ direction, counterpartyId }) => ({ direction, counterpartyId })),
    [
      { direction: 'outgoing', counterpartyId: 'bcn_carol' },
      { direction: 'incoming', counterpartyId: 'bcn_bob' },
    ],
  );
});

test('buildContractHistory is deterministic for tied and unknown timestamps', () => {
  const contracts = [
    { id: 'ctr-z', from: 'bcn_alice', to: 'bcn_zed', created_at: null },
    { id: 'ctr-b', from: 'bcn_alice', to: 'bcn_bob', created_at: 1_700_000_000 },
    { id: 'ctr-a', from: 'bcn_ann', to: 'bcn_alice', created_at: 1_700_000_000 },
  ];

  assert.deepEqual(
    buildContractHistory(contracts, 'bcn_alice').map(contract => contract.id),
    ['ctr-a', 'ctr-b', 'ctr-z'],
  );
  assert.deepEqual(buildContractHistory([...contracts].reverse(), 'bcn_alice').map(contract => contract.id), [
    'ctr-a', 'ctr-b', 'ctr-z',
  ]);
});

test('contract timestamps accept API seconds, milliseconds, and ISO text', () => {
  const expectedMilliseconds = 1_700_000_000_000;
  assert.equal(contractTimeMillis(1_700_000_000), expectedMilliseconds);
  assert.equal(contractTimeMillis(expectedMilliseconds), expectedMilliseconds);
  assert.equal(contractTimeMillis('2023-11-14T22:13:20Z'), expectedMilliseconds);
  assert.equal(contractTimestampIso(1_700_000_000), '2023-11-14T22:13:20.000Z');
  assert.equal(formatContractTimestamp(1_700_000_000), '2023-11-14 22:13:20 UTC');
});

test('invalid inputs fail closed without breaking the selected-agent panel', () => {
  assert.equal(contractTimeMillis('not-a-date'), null);
  assert.equal(contractTimestampIso(null), '');
  assert.equal(formatContractTimestamp(undefined), 'TIME UNKNOWN');
  assert.deepEqual(buildContractHistory(null, 'bcn_alice'), []);
  assert.deepEqual(buildContractHistory([], ''), []);
});
