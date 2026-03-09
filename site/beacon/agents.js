// ============================================================
// BEACON ATLAS - Agent Spheres + Relay Diamonds with Glow + Bob
// ============================================================

import * as THREE from 'three';
import {
  AGENTS, GRADE_COLORS, agentCity, cityPosition, seededRandom,
  getProviderColor,
} from './data.js';
import {
  getScene, registerClickable, registerHoverable, onAnimate,
} from './scene.js';

const agentMeshes = new Map(); // agentId -> { core, glow, group }
const agentPositions = new Map(); // agentId -> Vector3

export function getAgentPosition(agentId) {
  return agentPositions.get(agentId);
}

export function getAgentMesh(agentId) {
  return agentMeshes.get(agentId);
}

export function buildAgents() {
  const scene = getScene();

  // Track per-city agent index for offset placement
  const cityCounts = {};

  for (const agent of AGENTS) {
    const city = agentCity(agent);
    if (!city) continue;

    const cityPos = cityPosition(city);
    const idx = cityCounts[city.id] || 0;
    cityCounts[city.id] = idx + 1;

    const rng = seededRandom(hashCode(agent.id));
    const angle = (idx / (countAgentsInCity(city.id))) * Math.PI * 2 + rng() * 0.5;
    const dist = 4 + rng() * 8;
    const baseY = 8 + rng() * 12;

    const x = cityPos.x + Math.cos(angle) * dist;
    const z = cityPos.z + Math.sin(angle) * dist;
    const pos = new THREE.Vector3(x, baseY, z);

    agentPositions.set(agent.id, pos);

    const group = new THREE.Group();
    group.position.copy(pos);
    group.userData = { type: 'agent', agentId: agent.id, baseY, relay: !!agent.relay };

    const isRelay = agent.relay === true;

    // Relay agents use provider-specific color; native agents use grade color
    const colorHex = isRelay
      ? (getProviderColor(agent.provider) || '#ffffff')
      : (GRADE_COLORS[agent.grade] || '#33ff33');
    const color = new THREE.Color(colorHex);

    // Core geometry: Octahedron (diamond) for relay, Sphere for native
    const coreGeo = isRelay
      ? new THREE.OctahedronGeometry(1.8, 0)
      : new THREE.SphereGeometry(1.5, 16, 12);
    const coreMat = new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity: 0.9,
      wireframe: isRelay,  // Wireframe gives relay agents a "holographic bridge" look
    });
    const core = new THREE.Mesh(coreGeo, coreMat);
    core.userData = { type: 'agent', agentId: agent.id };
    group.add(core);
    registerClickable(core);
    registerHoverable(core);

    // Outer glow — slightly larger for relay to emphasize presence
    const glowGeo = isRelay
      ? new THREE.OctahedronGeometry(3.0, 1)
      : new THREE.SphereGeometry(2.5, 16, 12);
    const glowMat = new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity: isRelay ? 0.08 : 0.12,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const glow = new THREE.Mesh(glowGeo, glowMat);
    group.add(glow);

    // Point light for local illumination
    const light = new THREE.PointLight(color, isRelay ? 0.4 : 0.3, 20);
    light.position.set(0, 0, 0);
    group.add(light);

    // Agent name label
    const labelColor = isRelay ? colorHex : GRADE_COLORS[agent.grade];
    const label = makeAgentLabel(agent.name, labelColor, isRelay);
    label.position.set(0, 4, 0);
    label.scale.set(16, 3.5, 1);
    group.add(label);

    scene.add(group);
    agentMeshes.set(agent.id, { core, glow, group, light, relay: isRelay });
  }

  // Bob + spin animation
  onAnimate((elapsed) => {
    for (const [agentId, mesh] of agentMeshes) {
      const baseY = mesh.group.userData.baseY;
      const phase = hashCode(agentId) * 0.001;
      mesh.group.position.y = baseY + Math.sin(elapsed * 1.2 + phase) * 1.5;

      // Gentle glow pulse
      mesh.glow.material.opacity = mesh.relay
        ? 0.06 + Math.sin(elapsed * 2.5 + phase) * 0.04
        : 0.10 + Math.sin(elapsed * 2.0 + phase) * 0.04;

      // Relay agents: slow rotation on Y axis (spinning diamond)
      if (mesh.relay) {
        mesh.core.rotation.y = elapsed * 0.8 + phase;
        mesh.core.rotation.x = Math.sin(elapsed * 0.3 + phase) * 0.2;
      }
    }
  });
}

export function highlightAgent(agentId, on) {
  const mesh = agentMeshes.get(agentId);
  if (!mesh) return;
  mesh.glow.material.opacity = on ? 0.35 : (mesh.relay ? 0.08 : 0.12);
  mesh.core.material.opacity = on ? 1.0 : 0.9;
  mesh.light.intensity = on ? 0.8 : (mesh.relay ? 0.4 : 0.3);
}

function countAgentsInCity(cityId) {
  return AGENTS.filter(a => a.city === cityId).length;
}

function hashCode(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = ((h << 5) - h + str.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

function makeAgentLabel(text, color, isRelay = false) {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  canvas.width = 256;
  canvas.height = 64;

  ctx.font = `bold 24px "IBM Plex Mono", monospace`;
  ctx.fillStyle = color;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.shadowColor = color;
  ctx.shadowBlur = isRelay ? 10 : 6;
  ctx.fillText(text, canvas.width / 2, canvas.height / 2);

  // Relay agents get a small "R" badge
  if (isRelay) {
    ctx.font = 'bold 14px "IBM Plex Mono", monospace';
    ctx.fillStyle = '#000';
    ctx.shadowBlur = 0;
    const tw = ctx.measureText(text).width;
    const badgeX = canvas.width / 2 + tw / 2 + 10;
    const badgeY = canvas.height / 2;
    ctx.fillStyle = color;
    ctx.fillRect(badgeX - 8, badgeY - 8, 16, 16);
    ctx.fillStyle = '#000';
    ctx.textAlign = 'center';
    ctx.fillText('R', badgeX, badgeY + 1);
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearFilter;
  const mat = new THREE.SpriteMaterial({
    map: texture, transparent: true, opacity: 0.7,
    depthTest: false,
  });
  return new THREE.Sprite(mat);
}
