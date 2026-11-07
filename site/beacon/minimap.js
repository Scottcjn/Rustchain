// SPDX-License-Identifier: MIT
import { AGENTS, CITIES } from './data.js';
import { getAgentPosition } from './agents.js';
import { getCityCenter } from './cities.js';
import { getCamera, onAnimate } from './scene.js';
import { collectAtlasPoints, computeAtlasBounds, projectAtlasPoint } from './minimap-model.mjs';

const DRAW_INTERVAL_S = 0.1;

function mountStyles() {
  if (document.getElementById('atlas-minimap-styles')) return;
  const style = document.createElement('style');
  style.id = 'atlas-minimap-styles';
  style.textContent = `
    .atlas-minimap {
      position: fixed;
      right: 16px;
      bottom: 16px;
      z-index: 50;
      width: 190px;
      padding: 8px;
      border: 1px solid var(--green-dim);
      border-radius: 4px;
      background: rgba(0, 8, 0, 0.88);
      box-shadow: 0 0 18px rgba(0, 255, 0, 0.08), inset 0 0 18px rgba(0, 255, 0, 0.025);
      pointer-events: none;
      color: var(--text-dim);
      font: 10px/1.2 var(--font-mono);
      letter-spacing: 1px;
    }
    .atlas-minimap-title {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 5px;
      color: var(--amber);
    }
    .atlas-minimap canvas {
      display: block;
      width: 172px;
      height: 132px;
      border: 1px solid var(--border);
      background: rgba(0, 3, 0, 0.92);
    }
    @media (max-width: 700px) {
      .atlas-minimap {
        right: 8px;
        bottom: 8px;
        width: 142px;
        padding: 6px;
      }
      .atlas-minimap canvas { width: 128px; height: 96px; }
      .atlas-minimap-title { font-size: 9px; }
    }
  `;
  document.head.append(style);
}

function createRoot() {
  const root = document.createElement('aside');
  root.className = 'atlas-minimap';
  root.setAttribute('aria-label', 'Beacon Atlas overview minimap');

  const title = document.createElement('div');
  title.className = 'atlas-minimap-title';
  const label = document.createElement('span');
  label.textContent = '[ATLAS MAP]';
  const legend = document.createElement('span');
  legend.textContent = '■ CITY · AGENT ◇ YOU';
  title.append(label, legend);

  const canvas = document.createElement('canvas');
  canvas.setAttribute('aria-hidden', 'true');
  root.append(title, canvas);
  document.body.append(root);
  return canvas;
}

function fitCanvas(canvas) {
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const width = Math.max(1, Math.round(canvas.clientWidth));
  const height = Math.max(1, Math.round(canvas.clientHeight));
  const pixelWidth = Math.round(width * ratio);
  const pixelHeight = Math.round(height * ratio);
  if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
    canvas.width = pixelWidth;
    canvas.height = pixelHeight;
  }
  const ctx = canvas.getContext('2d');
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  return { ctx, width, height };
}

function drawMinimap(canvas) {
  const { ctx, width, height } = fitCanvas(canvas);
  const { cityPoints, agentPoints } = collectAtlasPoints(
    CITIES,
    AGENTS,
    getCityCenter,
    getAgentPosition,
  );
  const camera = getCamera();
  const cameraPoint = camera ? { x: camera.position.x, z: camera.position.z } : null;
  // Keep the overview footprint stable while the camera moves. The camera
  // marker is projected separately and clamps to the minimap edge when it
  // moves outside the populated Atlas bounds.
  const bounds = computeAtlasBounds([
    ...cityPoints,
    ...agentPoints,
  ], 24);

  ctx.clearRect(0, 0, width, height);

  ctx.strokeStyle = 'rgba(26, 140, 26, 0.24)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(width / 2, 6); ctx.lineTo(width / 2, height - 6);
  ctx.moveTo(6, height / 2); ctx.lineTo(width - 6, height / 2);
  ctx.stroke();

  ctx.fillStyle = 'rgba(51, 255, 51, 0.55)';
  for (const agent of agentPoints) {
    const point = projectAtlasPoint(agent, bounds, width, height);
    ctx.fillRect(point.x - 1, point.y - 1, 2, 2);
  }

  ctx.fillStyle = '#ffb000';
  for (const city of cityPoints) {
    const point = projectAtlasPoint(city, bounds, width, height);
    ctx.fillRect(point.x - 2.5, point.y - 2.5, 5, 5);
  }

  if (cameraPoint) {
    const point = projectAtlasPoint(cameraPoint, bounds, width, height);
    ctx.strokeStyle = '#00ffff';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(point.x, point.y - 5);
    ctx.lineTo(point.x + 4, point.y + 4);
    ctx.lineTo(point.x - 4, point.y + 4);
    ctx.closePath();
    ctx.stroke();
  }
}

export function initMinimap() {
  mountStyles();
  const canvas = createRoot();
  drawMinimap(canvas);
  // Start the interval on the first animation tick after the initial draw.
  let lastDraw = null;
  onAnimate((elapsed) => {
    if (lastDraw === null) { lastDraw = elapsed; return; }
    if (elapsed - lastDraw < DRAW_INTERVAL_S) return;
    lastDraw = elapsed;
    drawMinimap(canvas);
  });
  return canvas;
}
