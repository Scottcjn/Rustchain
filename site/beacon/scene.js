// ============================================================
// BEACON ATLAS - Three.js Scene, Camera, Controls, Raycaster
// ============================================================

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

let scene, camera, renderer, controls;
let raycaster, mouse;
let clock;
let clickables = [];      // meshes that respond to clicks
let hoverables = [];       // meshes that respond to hover
let animationCallbacks = [];
let autoRotate = true;
let autoRotateSpeed = 0.001; // radians per frame (~0.06°)
let lerpTarget = null;
let lerpAlpha = 0;

// Day/Night Cycle - Light references
let ambientLight, dirLight;
let currentTime = new Date();
let dayNightPhase = 0; // 0-1 progress through the day

// Color palettes for day/night
const NIGHT_COLORS = {
  background: 0x020502,
  fog: 0x020502,
  ambient: 0x112211,
  dirLight: 0x33ff33,
  grid: [0x0a1a0a, 0x060e06],
  ground: 0x010301
};

const DAY_COLORS = {
  background: 0x0a1510,
  fog: 0x0a1510,
  ambient: 0x224422,
  dirLight: 0x88ff88,
  grid: [0x1a2a1a, 0x0e1a0e],
  ground: 0x0a0806
};

const DAWN_COLORS = {
  background: 0x150d10,
  fog: 0x150d10,
  ambient: 0x332222,
  dirLight: 0xffaa66,
  grid: [0x2a1a1a, 0x1a0e0e],
  ground: 0x100808
};

const DUSK_COLORS = {
  background: 0x101215,
  fog: 0x101215,
  ambient: 0x222233,
  dirLight: 0xff8844,
  grid: [0x1a1a2a, 0x0e0e1a],
  ground: 0x080810
};

export function getScene() { return scene; }
export function getCamera() { return camera; }
export function getRenderer() { return renderer; }
export function getClock() { return clock; }

export function registerClickable(mesh) { clickables.push(mesh); }
export function registerHoverable(mesh) { hoverables.push(mesh); }
export function onAnimate(fn) { animationCallbacks.push(fn); }

// Helper to interpolate between colors
function lerpColor(color1, color2, t) {
  const c1 = new THREE.Color(color1);
  const c2 = new THREE.Color(color2);
  return c1.lerp(c2, t);
}

// Get current time-based factors
function getDayNightFactors() {
  const now = new Date();
  const utcHour = now.getUTCHours() + now.getUTCMinutes() / 60;
  
  // Calculate phase: 0 = midnight, 0.5 = noon, 1 = midnight
  const phase = utcHour / 24;
  
  // Determine if it's day, night, dawn, or dusk
  let factors = {};
  
  if (utcHour >= 6 && utcHour < 8) {
    // Dawn transition (6-8)
    const t = (utcHour - 6) / 2;
    factors = {
      background: lerpColor(NIGHT_COLORS.background, DAWN_COLORS.background, t),
      fog: lerpColor(NIGHT_COLORS.fog, DAWN_COLORS.fog, t),
      ambient: lerpColor(NIGHT_COLORS.ambient, DAWN_COLORS.ambient, t),
      dirLight: lerpColor(NIGHT_COLORS.dirLight, DAWN_COLORS.dirLight, t),
      ambientIntensity: 0.4 + t * 0.2,
      dirLightIntensity: 0.15 + t * 0.25,
    };
  } else if (utcHour >= 8 && utcHour < 18) {
    // Day (8-18)
    const t = Math.sin(((utcHour - 8) / 10) * Math.PI);
    factors = {
      background: lerpColor(DAWN_COLORS.background, DAY_COLORS.background, t),
      fog: lerpColor(DAWN_COLORS.fog, DAY_COLORS.fog, t),
      ambient: lerpColor(DAWN_COLORS.ambient, DAY_COLORS.ambient, t),
      dirLight: lerpColor(DAWN_COLORS.dirLight, DAY_COLORS.dirLight, t),
      ambientIntensity: 0.6 + t * 0.2,
      dirLightIntensity: 0.4 + t * 0.3,
    };
  } else if (utcHour >= 18 && utcHour < 20) {
    // Dusk transition (18-20)
    const t = (utcHour - 18) / 2;
    factors = {
      background: lerpColor(DAY_COLORS.background, DUSK_COLORS.background, t),
      fog: lerpColor(DAY_COLORS.fog, DUSK_COLORS.fog, t),
      ambient: lerpColor(DAY_COLORS.ambient, DUSK_COLORS.ambient, t),
      dirLight: lerpColor(DAY_COLORS.dirLight, DUSK_COLORS.dirLight, t),
      ambientIntensity: 0.8 - t * 0.2,
      dirLightIntensity: 0.7 - t * 0.35,
    };
  } else if (utcHour >= 20 && utcHour < 22) {
    // Night transition (20-22)
    const t = (utcHour - 20) / 2;
    factors = {
      background: lerpColor(DUSK_COLORS.background, NIGHT_COLORS.background, t),
      fog: lerpColor(DUSK_COLORS.fog, NIGHT_COLORS.fog, t),
      ambient: lerpColor(DUSK_COLORS.ambient, NIGHT_COLORS.ambient, t),
      dirLight: lerpColor(DUSK_COLORS.dirLight, NIGHT_COLORS.dirLight, t),
      ambientIntensity: 0.6 - t * 0.2,
      dirLightIntensity: 0.35 - t * 0.2,
    };
  } else {
    // Night (22-6)
    factors = {
      background: new THREE.Color(NIGHT_COLORS.background),
      fog: new THREE.Color(NIGHT_COLORS.fog),
      ambient: new THREE.Color(NIGHT_COLORS.ambient),
      dirLight: new THREE.Color(NIGHT_COLORS.dirLight),
      ambientIntensity: 0.4,
      dirLightIntensity: 0.15,
    };
  }
  
  return factors;
}

export function initScene(canvas) {
  clock = new THREE.Clock();

  // Scene
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x020502);
  scene.fog = new THREE.FogExp2(0x020502, 0.0015);

  // Camera
  camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.5, 1200);
  camera.position.set(0, 180, 280);
  camera.lookAt(0, 0, 0);

  // Renderer
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.8;

  // Controls
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.minDistance = 30;
  controls.maxDistance = 600;
  controls.maxPolarAngle = Math.PI * 0.48;
  controls.target.set(0, 0, 0);

  controls.addEventListener('start', () => { autoRotate = false; });

  // Raycaster
  raycaster = new THREE.Raycaster();
  mouse = new THREE.Vector2();

  // Lights - Store references for day/night cycle
  ambientLight = new THREE.AmbientLight(0x112211, 0.4);
  scene.add(ambientLight);

  dirLight = new THREE.DirectionalLight(0x33ff33, 0.15);
  dirLight.position.set(50, 200, 100);
  scene.add(dirLight);

  // Ground grid
  const gridHelper = new THREE.GridHelper(500, 60, 0x0a1a0a, 0x060e06);
  gridHelper.position.y = -0.5;
  scene.add(gridHelper);

  // Ground plane (barely visible)
  const groundGeo = new THREE.PlaneGeometry(600, 600);
  const groundMat = new THREE.MeshBasicMaterial({
    color: 0x010301, transparent: true, opacity: 0.5,
  });
  const ground = new THREE.Mesh(groundGeo, groundMat);
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -1;
  scene.add(ground);

  // Resize handler
  window.addEventListener('resize', onResize);

  // Initial day/night update
  updateDayNightCycle();

  return { scene, camera, renderer, controls };
}

function updateDayNightCycle() {
  if (!scene || !ambientLight || !dirLight) return;
  
  const factors = getDayNightFactors();
  
  // Update scene colors
  scene.background = factors.background;
  scene.fog.color = factors.fog;
  
  // Update light colors and intensities
  ambientLight.color = factors.ambient;
  ambientLight.intensity = factors.ambientIntensity;
  
  dirLight.color = factors.dirLight;
  dirLight.intensity = factors.dirLightIntensity;
  
  // Adjust renderer exposure based on time of day
  if (renderer) {
    const now = new Date();
    const utcHour = now.getUTCHours();
    if (utcHour >= 10 && utcHour <= 16) {
      // Brightest during midday
      renderer.toneMappingExposure = 0.8 + Math.sin(((utcHour - 10) / 6) * Math.PI) * 0.3;
    } else {
      renderer.toneMappingExposure = 0.8;
    }
  }
}

function onResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

// --- Click detection ---
let onClickHandler = null;
let onHoverHandler = null;
let onMissHandler = null;

export function setClickHandler(fn) { onClickHandler = fn; }
export function setHoverHandler(fn) { onHoverHandler = fn; }
export function setMissHandler(fn) { onMissHandler = fn; }

export function setupInteraction(canvas) {
  canvas.addEventListener('click', (e) => {
    mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const hits = raycaster.intersectObjects(clickables, false);

    if (hits.length > 0 && onClickHandler) {
      onClickHandler(hits[0].object);
    } else if (onMissHandler) {
      onMissHandler();
    }
  });

  canvas.addEventListener('mousemove', (e) => {
    mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const hits = raycaster.intersectObjects(hoverables, false);

    if (onHoverHandler) {
      onHoverHandler(hits.length > 0 ? hits[0] : null, e);
    }
  });
}

// --- Camera lerp ---
export function lerpCameraTo(target, distance = 60) {
  const dir = new THREE.Vector3().subVectors(camera.position, controls.target).normalize();
  lerpTarget = {
    position: new THREE.Vector3(
      target.x + dir.x * distance,
      Math.max(target.y + 40, 50),
      target.z + dir.z * distance
    ),
    lookAt: target.clone(),
    startPos: camera.position.clone(),
    startLook: controls.target.clone(),
  };
  lerpAlpha = 0;
  autoRotate = false;
}

export function resetCamera() {
  lerpTarget = {
    position: new THREE.Vector3(0, 180, 280),
    lookAt: new THREE.Vector3(0, 0, 0),
    startPos: camera.position.clone(),
    startLook: controls.target.clone(),
  };
  lerpAlpha = 0;
  setTimeout(() => { autoRotate = true; }, 2000);
}

// --- Animation loop ---
export function startLoop() {
  let lastDayNightUpdate = 0;
  
  function animate() {
    requestAnimationFrame(animate);
    const dt = clock.getDelta();
    const elapsed = clock.getElapsedTime();

    // Update day/night cycle every minute
    if (elapsed - lastDayNightUpdate > 60) {
      updateDayNightCycle();
      lastDayNightUpdate = elapsed;
    }

    // Camera lerp
    if (lerpTarget) {
      lerpAlpha = Math.min(lerpAlpha + dt * 2.0, 1);
      const t = smoothstep(lerpAlpha);
      camera.position.lerpVectors(lerpTarget.startPos, lerpTarget.position, t);
      controls.target.lerpVectors(lerpTarget.startLook, lerpTarget.lookAt, t);
      if (lerpAlpha >= 1) lerpTarget = null;
    }

    // Auto-rotate
    if (autoRotate && !lerpTarget) {
      const angle = autoRotateSpeed;
      const x = controls.target.x;
      const z = controls.target.z;
      const dx = camera.position.x - x;
      const dz = camera.position.z - z;
      camera.position.x = x + dx * Math.cos(angle) - dz * Math.sin(angle);
      camera.position.z = z + dx * Math.sin(angle) + dz * Math.cos(angle);
    }

    controls.update();

    // Callbacks
    for (const cb of animationCallbacks) {
      cb(elapsed, dt);
    }

    renderer.render(scene, camera);
  }

  animate();
}

function smoothstep(t) {
  return t * t * (3 - 2 * t);
}
