// ============================================================
// BEACON ATLAS - 3D Bounty Beacons
// Visualizes active bounties as floating crystal beacons
// ============================================================

import * as THREE from 'three';
import { getScene, onAnimate, registerClickable, registerHoverable } from './scene.js';

const bountyBeacons = new Map(); // bountyId -> { mesh, glow, light, data }
const bountyPositions = new Map(); // bountyId -> Vector3

// Bounty difficulty colors
const DIFFICULTY_COLORS = {
  EASY: '#33ff33',
  MEDIUM: '#ffb000',
  HARD: '#ff4444',
  ANY: '#8888ff',
};

// Position bounties in orbiting rings around the central hub
function getBountyPosition(bountyId, index, total) {
  const ringRadius = 180 + (Math.floor(index / 8) * 40);
  const angle = (index % 8) * (Math.PI * 2 / 8) + (Date.now() * 0.0001);
  const height = 60 + (Math.floor(index / 8) * 30);
  
  return new THREE.Vector3(
    Math.cos(angle) * ringRadius,
    height,
    Math.sin(angle) * ringRadius
  );
}

function buildBountyMesh(bounty, color) {
  const group = new THREE.Group();
  
  // Crystal core - octahedron for bounty beacons
  const coreGeo = new THREE.OctahedronGeometry(2.5, 0);
  const coreMat = new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity: 0.85,
    wireframe: true,
  });
  const core = new THREE.Mesh(coreGeo, coreMat);
  group.add(core);
  registerClickable(core);
  registerHoverable(core);
  
  // Inner glow sphere
  const glowGeo = new THREE.SphereGeometry(3.5, 16, 12);
  const glowMat = new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity: 0.12,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const glow = new THREE.Mesh(glowGeo, glowMat);
  group.add(glow);
  
  // Point light
  const light = new THREE.PointLight(color, 0.5, 40);
  light.position.set(0, 0, 0);
  group.add(light);
  
  // Floating RTC amount label
  const label = makeBountyLabel(bounty.reward, color);
  label.position.set(0, 5, 0);
  label.scale.set(18, 4, 1);
  group.add(label);
  
  // Difficulty badge ring
  const ringGeo = new THREE.TorusGeometry(4.5, 0.3, 8, 24);
  const ringMat = new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity: 0.6,
  });
  const ring = new THREE.Mesh(ringGeo, ringMat);
  ring.rotation.x = Math.PI / 2;
  ring.position.y = -2;
  group.add(ring);
  
  return { core, glow, light, ring, group };
}

function makeBountyLabel(text, color) {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  canvas.width = 256;
  canvas.height = 64;
  
  ctx.font = 'bold 28px "IBM Plex Mono", monospace';
  ctx.fillStyle = color;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.shadowColor = color;
  ctx.shadowBlur = 8;
  ctx.fillText(text, canvas.width / 2, canvas.height / 2);
  
  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearFilter;
  const mat = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    opacity: 0.85,
    depthTest: false,
  });
  return new THREE.Sprite(mat);
}

export function buildBounties(bounties = []) {
  const scene = getScene();
  
  // Clear existing bounties
  for (const [id, beacon] of bountyBeacons) {
    scene.remove(beacon.group);
    beacon.core.geometry.dispose();
    beacon.core.material.dispose();
    beacon.glow.geometry.dispose();
    beacon.glow.material.dispose();
    beacon.light.dispose();
    beacon.ring.geometry.dispose();
    beacon.ring.material.dispose();
  }
  bountyBeacons.clear();
  bountyPositions.clear();
  
  if (!bounties || bounties.length === 0) return;
  
  // Create bounty beacons
  bounties.forEach((bounty, index) => {
    const colorHex = DIFFICULTY_COLORS[bounty.difficulty] || DIFFICULTY_COLORS.ANY;
    const color = new THREE.Color(colorHex);
    
    const pos = getBountyPosition(bounty.id, index, bounties.length);
    bountyPositions.set(bounty.id, pos);
    
    const mesh = buildBountyMesh(bounty, color);
    mesh.group.position.copy(pos);
    mesh.group.userData = {
      type: 'bounty',
      bountyId: bounty.id,
      baseY: pos.y,
      phase: Math.random() * Math.PI * 2,
    };
    
    scene.add(mesh.group);
    bountyBeacons.set(bounty.id, mesh);
  });
  
  // Animation: bobbing, rotation, pulsing
  onAnimate((elapsed) => {
    for (const [bountyId, beacon] of bountyBeacons) {
      const baseY = beacon.group.userData.baseY;
      const phase = beacon.group.userData.phase;
      
      // Gentle bobbing
      beacon.group.position.y = baseY + Math.sin(elapsed * 1.5 + phase) * 2;
      
      // Slow rotation
      beacon.core.rotation.y = elapsed * 0.4 + phase;
      beacon.core.rotation.x = Math.sin(elapsed * 0.3 + phase) * 0.15;
      
      // Pulsing glow
      beacon.glow.material.opacity = 0.10 + Math.sin(elapsed * 2.5 + phase) * 0.06;
      beacon.light.intensity = 0.4 + Math.sin(elapsed * 2 + phase) * 0.2;
      
      // Ring rotation (counter-rotate)
      beacon.ring.rotation.z = -elapsed * 0.2 - phase;
    }
  });
}

export function getBountyPosition(bountyId) {
  return bountyPositions.get(bountyId);
}

export function highlightBounty(bountyId, on) {
  const beacon = bountyBeacons.get(bountyId);
  if (!beacon) return;
  
  beacon.glow.material.opacity = on ? 0.35 : 0.12;
  beacon.core.material.opacity = on ? 1.0 : 0.85;
  beacon.light.intensity = on ? 0.9 : 0.5;
}

export function getBountyCount() {
  return bountyBeacons.size;
}
