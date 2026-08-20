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

// Day/Night Cycle - Lighting references
let ambientLight, dirLight;

export function getScene() { return scene; }
export function getCamera() { return camera; }
export function getRenderer() { return renderer; }
export function getClock() { return clock; }

export function registerClickable(mesh) { clickables.push(mesh); }
export function registerHoverable(mesh) { hoverables.push(mesh); }
export function onAnimate(fn) { animationCallbacks.push(fn); }

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
  // Make the gesture contract explicit so touch behavior stays stable when
  // OrbitControls defaults change between Three.js releases.
  controls.touches.ONE = THREE.TOUCH.ROTATE;
  controls.touches.TWO = THREE.TOUCH.DOLLY_PAN;
  controls.screenSpacePanning = true;
  if (window.matchMedia?.('(pointer: coarse)').matches) {
    controls.rotateSpeed = 0.65;
    controls.panSpeed = 0.8;
  }
  controls.target.set(0, 0, 0);

  controls.addEventListener('start', () => { autoRotate = false; });

  // Raycaster
  raycaster = new THREE.Raycaster();
  mouse = new THREE.Vector2();

  // Lights - Day/Night Cycle
  ambientLight = new THREE.AmbientLight(0x112211, 0.4);
  scene.add(ambientLight);

  dirLight = new THREE.DirectionalLight(0x33ff33, 0.15);
  dirLight.position.set(50, 200, 100);
  scene.add(dirLight);

  // Register day/night cycle update
  onAnimate(updateDayNightCycle);

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

  return { scene, camera, renderer, controls };
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
  // OrbitControls uses Pointer Events for mouse, pen, and touch. Handle taps
  // on the same event stream so a swipe/drag never opens an agent by accident.
  canvas.style.touchAction = 'none';
  const tapDistance = 10;
  let pointerStart = null;

  const updatePointer = (e) => {
    const rect = canvas.getBoundingClientRect();
    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
  };

  const selectAt = (e) => {
    updatePointer(e);

    raycaster.setFromCamera(mouse, camera);
    const hits = raycaster.intersectObjects(clickables, false);

    if (hits.length > 0 && onClickHandler) {
      onClickHandler(hits[0].object);
    } else if (onMissHandler) {
      onMissHandler();
    }
  };

  canvas.addEventListener('pointerdown', (e) => {
    if (e.isPrimary && e.button === 0) {
      pointerStart = { x: e.clientX, y: e.clientY };
    }
  });

  canvas.addEventListener('pointerup', (e) => {
    if (!pointerStart || !e.isPrimary || e.button !== 0) return;
    const distance = Math.hypot(e.clientX - pointerStart.x, e.clientY - pointerStart.y);
    pointerStart = null;
    if (distance <= tapDistance) selectAt(e);
  });

  canvas.addEventListener('pointercancel', () => {
    pointerStart = null;
  });

  canvas.addEventListener('pointermove', (e) => {
    // Touch screens do not have hover; avoiding raycasts while dragging keeps
    // the gesture responsive and prevents tooltip flicker.
    if (e.pointerType === 'touch') return;
    updatePointer(e);

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
  function animate() {
    requestAnimationFrame(animate);
    const dt = clock.getDelta();
    const elapsed = clock.getElapsedTime();

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

// --- Day/Night Cycle based on real UTC time ---
function updateDayNightCycle(elapsed, dt) {
  // Get current UTC time
  const now = new Date();
  const utcHours = now.getUTCHours();
  const utcMinutes = now.getUTCMinutes();
  const utcSeconds = now.getUTCSeconds();
  
  // Calculate time of day (0-24)
  const timeOfDay = utcHours + utcMinutes / 60 + utcSeconds / 3600;
  
  // Sun position based on time (0 = midnight, 12 = noon)
  const angle = ((timeOfDay - 6) / 24) * Math.PI * 2; // offset so 6am = sunrise
  const radius = 200;
  
  const sunX = Math.cos(angle) * radius;
  const sunY = Math.sin(angle) * radius;
  
  // Update directional light position
  dirLight.position.set(sunX, Math.max(sunY, -50), 100);
  
  // Calculate day/night factor (0 = night, 1 = day)
  const dayFactor = Math.max(0, Math.sin(angle));
  
  // Interpolate colors and intensities based on time of day
  // Night: dark blue-green, Day: bright green
  const nightColor = new THREE.Color(0x0a1a2a);
  const dayColor = new THREE.Color(0x33ff33);
  const currentColor = nightColor.clone().lerp(dayColor, dayFactor);
  
  dirLight.color = currentColor;
  dirLight.intensity = 0.05 + dayFactor * 0.2;
  
  // Ambient light changes too
  const nightAmbient = 0.15;
  const dayAmbient = 0.5;
  ambientLight.intensity = nightAmbient + (dayAmbient - nightAmbient) * dayFactor;
  ambientLight.color = new THREE.Color(0x112211).lerp(new THREE.Color(0x224422), dayFactor);
  
  // Adjust scene background slightly
  const nightBg = new THREE.Color(0x010301);
  const dayBg = new THREE.Color(0x020502);
  scene.background = nightBg.clone().lerp(dayBg, dayFactor);
  scene.fog.color = scene.background;
  
  // Adjust exposure
  renderer.toneMappingExposure = 0.5 + dayFactor * 0.4;
}
