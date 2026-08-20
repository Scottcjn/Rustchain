// ============================================================
// BEACON ATLAS - Contract Lines & Calibration Connections
// ============================================================

import * as THREE from 'three';
import {
  CONTRACTS, CALIBRATIONS,
  CONTRACT_STYLES, CONTRACT_STATE_OPACITY,
} from './data.js';
import { getScene, onAnimate } from './scene.js';
import { getAgentPosition } from './agents.js';
import { contractPulseFrame } from './contract-pulse.mjs';

const contractLines = [];
const calibrationLines = [];
const particles = [];
const contractPulses = [];

export function buildConnections() {
  const scene = getScene();

  // Contract lines
  for (const contract of CONTRACTS) {
    const fromPos = getAgentPosition(contract.from);
    const toPos = getAgentPosition(contract.to);
    if (!fromPos || !toPos) continue;

    const style = CONTRACT_STYLES[contract.type] || CONTRACT_STYLES.rent;
    const opacity = CONTRACT_STATE_OPACITY[contract.state] || 0.3;

    const points = [fromPos, toPos];
    const geo = new THREE.BufferGeometry().setFromPoints(points);

    let mat;
    if (style.dash.length > 0) {
      mat = new THREE.LineDashedMaterial({
        color: contract.state === 'breached' ? '#ff4444' : style.color,
        transparent: true,
        opacity,
        dashSize: style.dash[0],
        gapSize: style.dash[1],
        linewidth: 1,
      });
    } else {
      mat = new THREE.LineBasicMaterial({
        color: contract.state === 'breached' ? '#ff4444' : style.color,
        transparent: true,
        opacity,
        linewidth: 1,
      });
    }

    const line = new THREE.Line(geo, mat);
    line.computeLineDistances();
    line.userData = { type: 'contract', contractId: contract.id };
    scene.add(line);
    contractLines.push({ line, contract });

    // Particle flow on active contracts
    if (contract.state === 'active' || contract.state === 'renewed') {
      const particle = createFlowParticle(fromPos, toPos, style.color);
      scene.add(particle.mesh);
      particles.push(particle);
    }
  }

  // Calibration lines
  for (const cal of CALIBRATIONS) {
    if (cal.score < 0.6) continue;

    const aPos = getAgentPosition(cal.a);
    const bPos = getAgentPosition(cal.b);
    if (!aPos || !bPos) continue;

    const points = [aPos, bPos];
    const geo = new THREE.BufferGeometry().setFromPoints(points);
    const mat = new THREE.LineDashedMaterial({
      color: '#00ffff',
      transparent: true,
      opacity: 0.08 + cal.score * 0.12,
      dashSize: 1.5,
      gapSize: 2.5,
      linewidth: 1,
    });

    const line = new THREE.Line(geo, mat);
    line.computeLineDistances();
    line.userData = { type: 'calibration', a: cal.a, b: cal.b };
    scene.add(line);
    calibrationLines.push({ line, cal });
  }

  // Animate particles
  onAnimate((elapsed) => {
    for (const p of particles) {
      p.t = (p.t + 0.008) % 1;
      p.mesh.position.lerpVectors(p.from, p.to, p.t);
      p.mesh.material.opacity = 0.5 + Math.sin(elapsed * 4 + p.phase) * 0.3;
    }

    for (let i = contractPulses.length - 1; i >= 0; i--) {
      const pulse = contractPulses[i];
      if (pulse.startedAt === null) pulse.startedAt = elapsed;

      const frame = contractPulseFrame(elapsed - pulse.startedAt, pulse.baseOpacity);
      pulse.glow.material.opacity = frame.glowOpacity;
      pulse.glow.scale.setScalar(frame.glowScale);

      if (frame.done) disposeContractPulse(i);
    }
  });
}

function createFlowParticle(from, to, color) {
  const geo = new THREE.SphereGeometry(0.4, 6, 6);
  const mat = new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity: 0.6,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.copy(from);

  return {
    mesh,
    from: from.clone(),
    to: to.clone(),
    t: Math.random(),
    phase: Math.random() * Math.PI * 2,
  };
}

// --- Dynamic contract line management ---
export function addContractLine(contract) {
  const scene = getScene();
  const fromPos = getAgentPosition(contract.from);
  const toPos = getAgentPosition(contract.to);
  if (!fromPos || !toPos) return;

  const style = CONTRACT_STYLES[contract.type] || CONTRACT_STYLES.rent;
  const opacity = CONTRACT_STATE_OPACITY[contract.state] || 0.3;
  const lineColor = contract.state === 'breached' ? '#ff4444' : style.color;

  const points = [fromPos, toPos];
  const geo = new THREE.BufferGeometry().setFromPoints(points);

  let mat;
  if (style.dash.length > 0) {
    mat = new THREE.LineDashedMaterial({
      color: lineColor,
      transparent: true, opacity,
      dashSize: style.dash[0], gapSize: style.dash[1], linewidth: 1,
    });
  } else {
    mat = new THREE.LineBasicMaterial({
      color: lineColor,
      transparent: true, opacity, linewidth: 1,
    });
  }

  const line = new THREE.Line(geo, mat);
  line.computeLineDistances();
  line.userData = { type: 'contract', contractId: contract.id };
  scene.add(line);
  contractLines.push({ line, contract });
  startContractPulse(scene, contract.id, fromPos, toPos, lineColor, opacity);

  if (contract.state === 'active' || contract.state === 'renewed' || contract.state === 'offered') {
    const particle = createFlowParticle(fromPos, toPos, style.color);
    scene.add(particle.mesh);
    particle.contractId = contract.id;
    particles.push(particle);
  }
}

function startContractPulse(scene, contractId, from, to, color, baseOpacity) {
  const midpoint = from.clone().add(to).multiplyScalar(0.5);
  const glowGeometry = new THREE.BufferGeometry().setFromPoints([
    from.clone().sub(midpoint),
    to.clone().sub(midpoint),
  ]);
  const initialFrame = contractPulseFrame(0, baseOpacity);
  const glowMaterial = new THREE.LineBasicMaterial({
    color,
    transparent: true,
    opacity: initialFrame.glowOpacity,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    linewidth: 2,
  });
  const glow = new THREE.Line(glowGeometry, glowMaterial);
  glow.position.copy(midpoint);
  glow.scale.setScalar(initialFrame.glowScale);
  glow.renderOrder = 2;
  glow.userData = { type: 'contract-pulse', contractId };
  scene.add(glow);

  contractPulses.push({
    contractId,
    glow,
    baseOpacity,
    startedAt: null,
  });
}

function disposeContractPulse(index) {
  const pulse = contractPulses[index];
  if (!pulse) return;

  getScene().remove(pulse.glow);
  pulse.glow.geometry.dispose();
  pulse.glow.material.dispose();
  contractPulses.splice(index, 1);
}

export function removeContractLine(contractId) {
  const scene = getScene();
  for (let i = contractPulses.length - 1; i >= 0; i--) {
    if (contractPulses[i].contractId === contractId) {
      disposeContractPulse(i);
    }
  }
  for (let i = contractLines.length - 1; i >= 0; i--) {
    if (contractLines[i].contract.id === contractId) {
      const { line } = contractLines[i];
      scene.remove(line);
      line.geometry.dispose();
      line.material.dispose();
      contractLines.splice(i, 1);
    }
  }
  for (let i = particles.length - 1; i >= 0; i--) {
    if (particles[i].contractId === contractId) {
      scene.remove(particles[i].mesh);
      particles[i].mesh.geometry.dispose();
      particles[i].mesh.material.dispose();
      particles.splice(i, 1);
    }
  }
}

// Highlight connections related to an agent
export function highlightAgentConnections(agentId, on) {
  for (const { line, contract } of contractLines) {
    if (contract.from === agentId || contract.to === agentId) {
      line.material.opacity = on
        ? Math.min((CONTRACT_STATE_OPACITY[contract.state] || 0.3) + 0.3, 1.0)
        : (CONTRACT_STATE_OPACITY[contract.state] || 0.3);
    }
  }

  for (const { line, cal } of calibrationLines) {
    if (cal.a === agentId || cal.b === agentId) {
      line.material.opacity = on
        ? 0.3 + cal.score * 0.3
        : 0.08 + cal.score * 0.12;
    }
  }
}
