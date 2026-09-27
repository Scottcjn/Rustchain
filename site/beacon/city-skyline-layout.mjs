// SPDX-License-Identifier: MIT
// Pure, deterministic layout helpers for Beacon Atlas city skylines.

const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

const CITY_PROFILES = Object.freeze({
  megalopolis: Object.freeze({ radius: 16, footprint: 3.6, spires: 3, tierBias: 0.58 }),
  city:        Object.freeze({ radius: 12, footprint: 3.1, spires: 2, tierBias: 0.66 }),
  township:    Object.freeze({ radius: 9,  footprint: 2.7, spires: 1, tierBias: 0.76 }),
  outpost:     Object.freeze({ radius: 6,  footprint: 2.3, spires: 1, tierBias: 0.84 }),
  default:     Object.freeze({ radius: 8,  footprint: 2.6, spires: 1, tierBias: 0.76 }),
});

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function hashString(value) {
  let hash = 2166136261;
  for (const char of String(value)) {
    hash ^= char.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function seededRandom(seed) {
  let state = seed >>> 0;
  return function random() {
    state += 0x6d2b79f5;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

export function citySkylineProfile(type) {
  return CITY_PROFILES[type] || CITY_PROFILES.default;
}

export function citySkylineRadius(type) {
  return citySkylineProfile(type).radius;
}

export function skylineBuildingCount(population) {
  const safePopulation = Math.max(0, Number(population) || 0);
  return clamp(Math.floor(safePopulation / 3) + 1, 1, 15);
}

export function skylineMaxHeight(population) {
  const safePopulation = Math.max(0, Number(population) || 0);
  return Math.log2(safePopulation + 1) * 8 + 4;
}

/**
 * Generate a compact skyline whose tallest tower is in the core and whose
 * height falls toward the city ring. The same city data always produces the
 * same geometry, so live Atlas refreshes do not make buildings jump around.
 */
export function generateSkylineLayout(city) {
  const profile = citySkylineProfile(city?.type);
  const population = Math.max(0, Number(city?.population) || 0);
  const count = skylineBuildingCount(population);
  const maxHeight = skylineMaxHeight(population);
  const random = seededRandom(hashString(`${city?.id || 'city'}:${city?.type || 'default'}`));
  const phase = random() * Math.PI * 2;
  const buildings = [];

  for (let index = 0; index < count; index += 1) {
    const normalized = count === 1 ? 0 : index / (count - 1);
    const radial = index === 0
      ? 0
      : Math.sqrt(normalized) * profile.radius * (0.64 + random() * 0.10);
    const angle = phase + index * GOLDEN_ANGLE + (random() - 0.5) * 0.18;
    const centerWeight = 1 - radial / profile.radius;

    const height = index === 0
      ? maxHeight
      : maxHeight * (0.30 + centerWeight * 0.54) * (0.82 + random() * 0.16);
    const footprintScale = 0.72 + random() * 0.36;
    const width = profile.footprint * footprintScale;
    const depth = profile.footprint * (0.72 + random() * 0.36);
    const tiered = index === 0 || (height / maxHeight >= profile.tierBias && random() > 0.25);

    buildings.push({
      index,
      x: Math.cos(angle) * radial,
      z: Math.sin(angle) * radial,
      radial,
      rotation: angle + Math.PI / 4,
      width,
      depth,
      height: Math.max(4, height),
      tiers: tiered ? 2 : 1,
      windowBands: clamp(Math.floor(height / 5), 1, 7),
      hasSpire: index < profile.spires,
    });
  }

  return buildings;
}

