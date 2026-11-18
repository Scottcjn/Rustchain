// SPDX-License-Identifier: MIT
const DEFAULT_BOUNDS = Object.freeze({ minX: -250, maxX: 250, minZ: -250, maxZ: 250 });

export function computeAtlasBounds(points, padding = 20) {
  const finite = (points || []).filter(
    point => Number.isFinite(point?.x) && Number.isFinite(point?.z),
  );
  if (finite.length === 0) return { ...DEFAULT_BOUNDS };

  let minX = Math.min(...finite.map(point => point.x));
  let maxX = Math.max(...finite.map(point => point.x));
  let minZ = Math.min(...finite.map(point => point.z));
  let maxZ = Math.max(...finite.map(point => point.z));

  if (minX === maxX) { minX -= 1; maxX += 1; }
  if (minZ === maxZ) { minZ -= 1; maxZ += 1; }

  const safePadding = Number.isFinite(padding) ? Math.max(0, padding) : 0;
  return {
    minX: minX - safePadding,
    maxX: maxX + safePadding,
    minZ: minZ - safePadding,
    maxZ: maxZ + safePadding,
  };
}

export function projectAtlasPoint(point, bounds, width, height, inset = 8) {
  const safeWidth = Math.max(1, Number(width) || 1);
  const safeHeight = Math.max(1, Number(height) || 1);
  const safeInset = Math.max(0, Math.min(Number(inset) || 0, safeWidth / 2, safeHeight / 2));
  const spanX = Math.max(1e-9, bounds.maxX - bounds.minX);
  const spanZ = Math.max(1e-9, bounds.maxZ - bounds.minZ);
  const xRatio = (Number(point?.x) - bounds.minX) / spanX;
  const zRatio = (Number(point?.z) - bounds.minZ) / spanZ;

  return {
    x: safeInset + Math.min(1, Math.max(0, xRatio)) * (safeWidth - safeInset * 2),
    y: safeHeight - safeInset - Math.min(1, Math.max(0, zRatio)) * (safeHeight - safeInset * 2),
  };
}

export function collectAtlasPoints(cities, agents, getCityCenter, getAgentPosition) {
  const cityPoints = (cities || []).map(city => {
    const position = getCityCenter(city.id);
    return position && Number.isFinite(position.x) && Number.isFinite(position.z)
      ? { id: city.id, name: city.name || city.id, x: position.x, z: position.z }
      : null;
  }).filter(Boolean);

  const agentPoints = (agents || []).map(agent => {
    const position = getAgentPosition(agent.id);
    return position && Number.isFinite(position.x) && Number.isFinite(position.z)
      ? { id: agent.id, x: position.x, z: position.z }
      : null;
  }).filter(Boolean);

  return { cityPoints, agentPoints };
}
