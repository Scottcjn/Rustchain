// ============================================================
// BEACON ATLAS - Wireframe Cities & Region Platforms
// ============================================================

import * as THREE from 'three';
import {
  REGIONS, CITIES, regionPosition, cityPosition,
  cityRegion,
} from './data.js';
import {
  citySkylineRadius,
  generateSkylineLayout,
} from './city-skyline-layout.mjs';
import { getScene, registerClickable, registerHoverable } from './scene.js';

const cityGroups = new Map();   // cityId -> THREE.Group
const regionGroups = new Map(); // regionId -> THREE.Group

export function getCityGroup(cityId) { return cityGroups.get(cityId); }
export function getCityCenter(cityId) {
  const city = CITIES.find(c => c.id === cityId);
  if (!city) return new THREE.Vector3();
  const pos = cityPosition(city);
  return new THREE.Vector3(pos.x, 0, pos.z);
}

export function buildCities() {
  const scene = getScene();

  // Build region platforms
  for (const region of REGIONS) {
    const rp = regionPosition(region);
    const group = new THREE.Group();
    group.position.set(rp.x, 0, rp.z);

    // Hexagonal platform
    const hexGeo = new THREE.CircleGeometry(35, 6);
    const hexMat = new THREE.MeshBasicMaterial({
      color: new THREE.Color(region.color),
      transparent: true,
      opacity: 0.04,
      side: THREE.DoubleSide,
    });
    const hex = new THREE.Mesh(hexGeo, hexMat);
    hex.rotation.x = -Math.PI / 2;
    hex.position.y = -0.3;
    group.add(hex);

    // Hex wireframe outline
    const hexEdge = new THREE.EdgesGeometry(hexGeo);
    const hexLine = new THREE.LineSegments(hexEdge,
      new THREE.LineBasicMaterial({ color: region.color, transparent: true, opacity: 0.15 })
    );
    hexLine.rotation.x = -Math.PI / 2;
    hexLine.position.y = -0.2;
    group.add(hexLine);

    // Region label
    const label = makeTextSprite(region.name, region.color, 20);
    label.position.set(0, 2, 28);
    label.scale.set(28, 7, 1);
    group.add(label);

    scene.add(group);
    regionGroups.set(region.id, group);
  }

  // Build city clusters
  for (const city of CITIES) {
    const region = cityRegion(city);
    const pos = cityPosition(city);
    const group = new THREE.Group();
    group.position.set(pos.x, 0, pos.z);
    group.userData = { type: 'city', cityId: city.id };

    const color = new THREE.Color(region.color);
    const skyline = createCitySkyline(city, color);
    const maxH = skyline.userData.maxHeight;
    group.add(skyline);

    // City ground ring
    const ringGeo = new THREE.RingGeometry(
      citySkylineRadius(city.type) - 0.5,
      citySkylineRadius(city.type),
      24
    );
    const ringMat = new THREE.MeshBasicMaterial({
      color, transparent: true, opacity: 0.2, side: THREE.DoubleSide,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = 0.1;
    group.add(ring);

    // Clickable invisible sphere over city
    const hitGeo = new THREE.SphereGeometry(citySkylineRadius(city.type), 8, 8);
    const hitMat = new THREE.MeshBasicMaterial({ visible: false });
    const hitMesh = new THREE.Mesh(hitGeo, hitMat);
    hitMesh.position.y = maxH / 2;
    hitMesh.userData = { type: 'city', cityId: city.id };
    group.add(hitMesh);
    registerClickable(hitMesh);
    registerHoverable(hitMesh);

    // City label
    const label = makeTextSprite(city.name, region.color, 14);
    label.position.set(0, maxH + 6, 0);
    label.scale.set(24, 5, 1);
    group.add(label);

    scene.add(group);
    cityGroups.set(city.id, group);
  }
}

function createCitySkyline(city, color) {
  const layout = generateSkylineLayout(city);
  const group = new THREE.Group();
  group.name = `city-skyline-${city.id}`;

  const segments = layout.flatMap(buildingSegments);
  const unitBox = new THREE.BoxGeometry(1, 1, 1);
  const facades = new THREE.InstancedMesh(
    unitBox,
    new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity: 0.10,
      depthWrite: false,
    }),
    segments.length,
  );
  facades.name = `city-skyline-facades-${city.id}`;

  const outlines = new THREE.InstancedMesh(
    unitBox,
    new THREE.MeshBasicMaterial({
      color,
      wireframe: true,
      transparent: true,
      opacity: 0.46,
    }),
    segments.length,
  );
  outlines.name = `city-skyline-outlines-${city.id}`;

  const matrix = new THREE.Matrix4();
  const quaternion = new THREE.Quaternion();
  const position = new THREE.Vector3();
  const scale = new THREE.Vector3();
  const yAxis = new THREE.Vector3(0, 1, 0);

  segments.forEach((segment, index) => {
    position.set(segment.x, segment.y, segment.z);
    quaternion.setFromAxisAngle(yAxis, segment.rotation);
    scale.set(segment.width, segment.height, segment.depth);
    matrix.compose(position, quaternion, scale);
    facades.setMatrixAt(index, matrix);
    outlines.setMatrixAt(index, matrix);
  });
  facades.instanceMatrix.needsUpdate = true;
  outlines.instanceMatrix.needsUpdate = true;
  group.add(facades, outlines);

  const windows = makeWindowMesh(layout, color, city.id);
  if (windows) group.add(windows);

  const spires = makeSpireMeshes(layout, color, city.id);
  if (spires) group.add(...spires);

  const tallest = Math.max(...layout.map(building => (
    building.height + (building.hasSpire ? Math.min(8, building.height * 0.22) : 0)
  )));
  group.userData = {
    buildingCount: layout.length,
    segmentCount: segments.length,
    maxHeight: tallest,
  };
  return group;
}

function buildingSegments(building) {
  if (building.tiers === 1) {
    return [{ ...building, y: building.height / 2 }];
  }

  const lowerHeight = building.height * 0.62;
  const upperHeight = building.height - lowerHeight;
  return [
    {
      ...building,
      y: lowerHeight / 2,
      height: lowerHeight,
    },
    {
      ...building,
      y: lowerHeight + upperHeight / 2,
      width: building.width * 0.68,
      depth: building.depth * 0.68,
      height: upperHeight,
    },
  ];
}

function makeWindowMesh(layout, color, cityId) {
  const windows = [];
  for (const building of layout) {
    for (let band = 0; band < building.windowBands; band += 1) {
      const y = 2.3 + band * ((building.height - 3.4) / Math.max(1, building.windowBands - 1));
      if (y >= building.height - 0.8) continue;

      const upperTier = building.tiers > 1 && y > building.height * 0.62;
      const tierScale = upperTier ? 0.68 : 1;
      const width = building.width * tierScale;
      const depth = building.depth * tierScale;
      windows.push(
        windowTransform(building, 0, y, depth / 2 + 0.04, width * 0.50, 0.18, 0.07),
        windowTransform(building, width / 2 + 0.04, y, 0, 0.07, 0.18, depth * 0.50),
      );
    }
  }

  if (windows.length === 0) return null;

  const mesh = new THREE.InstancedMesh(
    new THREE.BoxGeometry(1, 1, 1),
    new THREE.MeshBasicMaterial({
      color: color.clone().lerp(new THREE.Color(0xffffff), 0.34),
      transparent: true,
      opacity: 0.78,
      toneMapped: false,
    }),
    windows.length,
  );
  mesh.name = `city-skyline-windows-${cityId}`;

  const matrix = new THREE.Matrix4();
  const quaternion = new THREE.Quaternion();
  const yAxis = new THREE.Vector3(0, 1, 0);
  windows.forEach((window, index) => {
    quaternion.setFromAxisAngle(yAxis, window.rotation);
    matrix.compose(
      new THREE.Vector3(window.x, window.y, window.z),
      quaternion,
      new THREE.Vector3(window.width, window.height, window.depth),
    );
    mesh.setMatrixAt(index, matrix);
  });
  mesh.instanceMatrix.needsUpdate = true;
  return mesh;
}

function windowTransform(building, localX, y, localZ, width, height, depth) {
  const sin = Math.sin(building.rotation);
  const cos = Math.cos(building.rotation);
  return {
    x: building.x + localX * cos + localZ * sin,
    y,
    z: building.z - localX * sin + localZ * cos,
    rotation: building.rotation,
    width,
    height,
    depth,
  };
}

function makeSpireMeshes(layout, color, cityId) {
  const towers = layout.filter(building => building.hasSpire);
  if (towers.length === 0) return null;

  const spires = new THREE.InstancedMesh(
    new THREE.CylinderGeometry(0.10, 0.22, 1, 6),
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.74 }),
    towers.length,
  );
  spires.name = `city-skyline-spires-${cityId}`;

  const beacons = new THREE.InstancedMesh(
    new THREE.SphereGeometry(1, 8, 6),
    new THREE.MeshBasicMaterial({ color: 0xffffff, toneMapped: false }),
    towers.length,
  );
  beacons.name = `city-skyline-beacons-${cityId}`;

  const identity = new THREE.Quaternion();
  const matrix = new THREE.Matrix4();
  towers.forEach((building, index) => {
    const spireHeight = Math.min(8, building.height * 0.22);
    matrix.compose(
      new THREE.Vector3(building.x, building.height + spireHeight / 2, building.z),
      identity,
      new THREE.Vector3(1, spireHeight, 1),
    );
    spires.setMatrixAt(index, matrix);

    matrix.compose(
      new THREE.Vector3(building.x, building.height + spireHeight, building.z),
      identity,
      new THREE.Vector3(0.20, 0.20, 0.20),
    );
    beacons.setMatrixAt(index, matrix);
  });
  spires.instanceMatrix.needsUpdate = true;
  beacons.instanceMatrix.needsUpdate = true;
  return [spires, beacons];
}

// --- Text sprite helper ---
function makeTextSprite(text, color, fontSize) {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  canvas.width = 512;
  canvas.height = 128;

  ctx.font = `bold ${fontSize * 2}px "IBM Plex Mono", monospace`;
  ctx.fillStyle = 'transparent';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.fillStyle = color;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.shadowColor = color;
  ctx.shadowBlur = 8;
  ctx.fillText(text, canvas.width / 2, canvas.height / 2);

  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearFilter;
  const mat = new THREE.SpriteMaterial({
    map: texture, transparent: true, opacity: 0.85,
    depthTest: false,
  });
  return new THREE.Sprite(mat);
}

export { makeTextSprite };
