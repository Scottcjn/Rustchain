// ============================================================
// BEACON ATLAS - Wireframe Cities & Region Platforms
// ============================================================

import * as THREE from 'three';
import {
  REGIONS, CITIES, regionPosition, cityPosition,
  buildingHeight, buildingCount, seededRandom, cityRegion,
} from './data.js';
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
    const maxH = buildingHeight(city.population);
    const count = buildingCount(city.population);
    const rng = seededRandom(hashCode(city.id));

    // City ground ring
    const ringGeo = new THREE.RingGeometry(
      cityTypeRadius(city.type) - 0.5,
      cityTypeRadius(city.type),
      24
    );
    const ringMat = new THREE.MeshBasicMaterial({
      color, transparent: true, opacity: 0.2, side: THREE.DoubleSide,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = 0.1;
    group.add(ring);

    // Buildings
    for (let i = 0; i < count; i++) {
      const bw = 1.2 + rng() * 2.5;
      const bd = 1.2 + rng() * 2.5;
      const bh = 4 + rng() * (maxH - 4);
      const bx = (rng() - 0.5) * cityTypeRadius(city.type) * 1.4;
      const bz = (rng() - 0.5) * cityTypeRadius(city.type) * 1.4;

      const geo = new THREE.BoxGeometry(bw, bh, bd);
      const edges = new THREE.EdgesGeometry(geo);
      const line = new THREE.LineSegments(edges,
        new THREE.LineBasicMaterial({
          color, transparent: true,
          opacity: 0.3 + rng() * 0.4,
        })
      );
      line.position.set(bx, bh / 2, bz);
      group.add(line);
    }

    // Clickable invisible sphere over city
    const hitGeo = new THREE.SphereGeometry(cityTypeRadius(city.type), 8, 8);
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

function cityTypeRadius(type) {
  switch (type) {
    case 'megalopolis': return 16;
    case 'city': return 12;
    case 'township': return 9;
    case 'outpost': return 6;
    default: return 8;
  }
}

function hashCode(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = ((h << 5) - h + str.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
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
