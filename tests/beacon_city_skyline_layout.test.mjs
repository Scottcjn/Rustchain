// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import test from 'node:test';

import {
  citySkylineRadius,
  generateSkylineLayout,
  skylineBuildingCount,
} from '../site/beacon/city-skyline-layout.mjs';

const compilerHeights = {
  id: 'compiler_heights',
  type: 'megalopolis',
  population: 42,
};

test('layout is deterministic and population-scaled', () => {
  const first = generateSkylineLayout(compilerHeights);
  const second = generateSkylineLayout(compilerHeights);

  assert.deepEqual(first, second);
  assert.equal(first.length, 15);
  assert.equal(skylineBuildingCount(0), 1);
  assert.equal(skylineBuildingCount(500), 15);
});

test('the skyline has a tall core and bounded outer buildings', () => {
  const layout = generateSkylineLayout(compilerHeights);
  const radius = citySkylineRadius(compilerHeights.type);
  const core = layout[0];

  assert.equal(core.radial, 0);
  assert.equal(core.tiers, 2);
  assert.equal(core.hasSpire, true);
  assert.equal(core.height, Math.max(...layout.map(building => building.height)));

  for (const building of layout) {
    assert.ok(building.radial < radius * 0.75);
    assert.ok(building.height >= 4);
    assert.ok(building.width > 0);
    assert.ok(building.depth > 0);
    assert.ok(building.windowBands >= 1 && building.windowBands <= 7);
  }
});

test('city identity changes the deterministic arrangement', () => {
  const first = generateSkylineLayout(compilerHeights);
  const second = generateSkylineLayout({
    ...compilerHeights,
    id: 'another_megalopolis',
  });

  assert.notDeepEqual(first, second);
  assert.equal(first.length, second.length);
});

test('city profiles control footprint and signature spire count', () => {
  const megalopolis = generateSkylineLayout(compilerHeights);
  const outpost = generateSkylineLayout({ id: 'outpost', type: 'outpost', population: 42 });

  assert.equal(megalopolis.filter(building => building.hasSpire).length, 3);
  assert.equal(outpost.filter(building => building.hasSpire).length, 1);
  assert.ok(citySkylineRadius('megalopolis') > citySkylineRadius('outpost'));
});

