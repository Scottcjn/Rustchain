// SPDX-License-Identifier: MIT

import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildCityTeleportGroups,
  resolveTeleportCity,
} from '../site/beacon/city-teleport.mjs';
import { CITIES, REGIONS } from '../site/beacon/data.js';

const regions = [
  { id: 'north', name: 'North' },
  { id: 'south', name: 'South' },
];

const cities = [
  { id: 'south_z', name: 'Zulu', region: 'south' },
  { id: 'north_b', name: 'Beta', region: 'north' },
  { id: 'north_a', name: 'Alpha', region: 'north' },
  { id: 'unknown', name: 'Orphan', region: 'missing' },
];

test('groups every valid city by region order and sorts city names', () => {
  assert.deepEqual(buildCityTeleportGroups(cities, regions), [
    {
      id: 'north',
      name: 'North',
      cities: [
        { id: 'north_a', name: 'Alpha' },
        { id: 'north_b', name: 'Beta' },
      ],
    },
    {
      id: 'south',
      name: 'South',
      cities: [{ id: 'south_z', name: 'Zulu' }],
    },
    {
      id: 'other',
      name: 'Other',
      cities: [{ id: 'unknown', name: 'Orphan' }],
    },
  ]);
});

test('does not mutate the source city order', () => {
  const originalIds = cities.map(city => city.id);
  buildCityTeleportGroups(cities, regions);
  assert.deepEqual(cities.map(city => city.id), originalIds);
});

test('resolves only an exact known city id', () => {
  assert.equal(resolveTeleportCity(cities, 'north_a'), cities[2]);
  assert.equal(resolveTeleportCity(cities, 'NORTH_A'), null);
  assert.equal(resolveTeleportCity(cities, ''), null);
  assert.equal(resolveTeleportCity(null, 'north_a'), null);
});

test('ignores malformed city and region input safely', () => {
  assert.deepEqual(buildCityTeleportGroups([null, { id: 5, name: 'Bad' }], null), []);
});

test('lists every canonical Atlas city exactly once', () => {
  const listed = buildCityTeleportGroups(CITIES, REGIONS).flatMap(group => group.cities);

  assert.equal(listed.length, CITIES.length);
  assert.equal(new Set(listed.map(city => city.id)).size, CITIES.length);
});
