// SPDX-License-Identifier: MIT
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  collectAtlasPoints,
  computeAtlasBounds,
  projectAtlasPoint,
} from '../site/beacon/minimap-model.mjs';

test('computeAtlasBounds covers finite points with padding', () => {
  assert.deepEqual(
    computeAtlasBounds([
      { x: -10, z: 5 },
      { x: 20, z: 45 },
      { x: Infinity, z: 2 },
    ], 5),
    { minX: -15, maxX: 25, minZ: 0, maxZ: 50 },
  );
});

test('projectAtlasPoint maps x/z into a north-up canvas', () => {
  const bounds = { minX: 0, maxX: 100, minZ: 0, maxZ: 100 };
  assert.deepEqual(
    projectAtlasPoint({ x: 0, z: 0 }, bounds, 120, 80, 10),
    { x: 10, y: 70 },
  );
  assert.deepEqual(
    projectAtlasPoint({ x: 100, z: 100 }, bounds, 120, 80, 10),
    { x: 110, y: 10 },
  );
  assert.deepEqual(
    projectAtlasPoint({ x: 50, z: 50 }, bounds, 120, 80, 10),
    { x: 60, y: 40 },
  );
});

test('projectAtlasPoint clamps off-map positions to the minimap edge', () => {
  const bounds = { minX: 0, maxX: 100, minZ: 0, maxZ: 100 };
  assert.deepEqual(
    projectAtlasPoint({ x: -500, z: 800 }, bounds, 120, 80, 10),
    { x: 10, y: 10 },
  );
});

test('collectAtlasPoints skips missing positions instead of inventing coordinates', () => {
  const cities = [{ id: 'a', name: 'Alpha' }, { id: 'b', name: 'Beta' }];
  const agents = [{ id: 'one' }, { id: 'two' }];
  const positions = {
    a: { x: 1, z: 2 },
    one: { x: 3, z: 4 },
  };
  const result = collectAtlasPoints(
    cities,
    agents,
    id => positions[id],
    id => positions[id],
  );
  assert.deepEqual(result.cityPoints, [{ id: 'a', name: 'Alpha', x: 1, z: 2 }]);
  assert.deepEqual(result.agentPoints, [{ id: 'one', x: 3, z: 4 }]);
});
