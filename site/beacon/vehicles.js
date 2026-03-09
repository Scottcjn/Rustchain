// ============================================================
// BEACON ATLAS - Ambient Vehicles (Cars, Planes, Drones)
// Little vehicles moving between cities for lively atmosphere
// ============================================================

import * as THREE from 'three';
import { CITIES, cityPosition } from './data.js';
import { getScene, onAnimate } from './scene.js';

const vehicles = [];
const VEHICLE_COUNT = 18;  // Total ambient vehicles
const CAR_Y = 1.2;         // Ground vehicles hover slightly
const PLANE_Y_MIN = 40;    // Planes fly high
const PLANE_Y_MAX = 70;
const DRONE_Y_MIN = 15;    // Drones fly medium
const DRONE_Y_MAX = 30;

// Vehicle types with different shapes and behaviors
const TYPES = [
  { name: 'car',   weight: 5, y: () => CAR_Y,                                speed: () => 0.3 + Math.random() * 0.4 },
  { name: 'plane', weight: 3, y: () => PLANE_Y_MIN + Math.random() * (PLANE_Y_MAX - PLANE_Y_MIN), speed: () => 0.8 + Math.random() * 0.6 },
  { name: 'drone', weight: 4, y: () => DRONE_Y_MIN + Math.random() * (DRONE_Y_MAX - DRONE_Y_MIN), speed: () => 0.5 + Math.random() * 0.3 },
];

function pickType() {
  const total = TYPES.reduce((s, t) => s + t.weight, 0);
  let r = Math.random() * total;
  for (const t of TYPES) {
    r -= t.weight;
    if (r <= 0) return t;
  }
  return TYPES[0];
}

function pickTwoCities() {
  const a = Math.floor(Math.random() * CITIES.length);
  let b = Math.floor(Math.random() * CITIES.length);
  while (b === a) b = Math.floor(Math.random() * CITIES.length);
  return [CITIES[a], CITIES[b]];
}

function buildCarMesh(color) {
  const group = new THREE.Group();

  // Body - elongated box
  const bodyGeo = new THREE.BoxGeometry(2.0, 0.8, 1.0);
  const bodyMat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.7 });
  const body = new THREE.Mesh(bodyGeo, bodyMat);
  group.add(body);

  // Cabin - smaller box on top
  const cabGeo = new THREE.BoxGeometry(1.0, 0.6, 0.8);
  const cabMat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.5 });
  const cab = new THREE.Mesh(cabGeo, cabMat);
  cab.position.set(-0.1, 0.6, 0);
  group.add(cab);

  // Headlights - two small emissive dots
  const hlGeo = new THREE.SphereGeometry(0.12, 4, 4);
  const hlMat = new THREE.MeshBasicMaterial({ color: 0xffffcc, transparent: true, opacity: 0.9 });
  const hl1 = new THREE.Mesh(hlGeo, hlMat);
  hl1.position.set(1.05, 0.1, 0.3);
  group.add(hl1);
  const hl2 = new THREE.Mesh(hlGeo, hlMat);
  hl2.position.set(1.05, 0.1, -0.3);
  group.add(hl2);

  // Taillights - red
  const tlMat = new THREE.MeshBasicMaterial({ color: 0xff2200, transparent: true, opacity: 0.7 });
  const tl1 = new THREE.Mesh(hlGeo, tlMat);
  tl1.position.set(-1.05, 0.1, 0.3);
  group.add(tl1);
  const tl2 = new THREE.Mesh(hlGeo, tlMat);
  tl2.position.set(-1.05, 0.1, -0.3);
  group.add(tl2);

  group.scale.set(0.8, 0.8, 0.8);
  return group;
}

function buildPlaneMesh(color) {
  const group = new THREE.Group();

  // Fuselage - elongated cone-ish
  const fuseGeo = new THREE.CylinderGeometry(0.3, 0.6, 3.5, 6);
  fuseGeo.rotateZ(Math.PI / 2);
  const fuseMat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.6 });
  const fuse = new THREE.Mesh(fuseGeo, fuseMat);
  group.add(fuse);

  // Wings - flat box
  const wingGeo = new THREE.BoxGeometry(0.3, 0.08, 4.0);
  const wingMat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.5 });
  const wing = new THREE.Mesh(wingGeo, wingMat);
  wing.position.set(0.2, 0, 0);
  group.add(wing);

  // Tail fin
  const tailGeo = new THREE.BoxGeometry(0.3, 1.2, 0.08);
  const tailMat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.5 });
  const tail = new THREE.Mesh(tailGeo, tailMat);
  tail.position.set(-1.5, 0.5, 0);
  group.add(tail);

  // Navigation lights
  const navGeo = new THREE.SphereGeometry(0.1, 4, 4);
  const redNav = new THREE.Mesh(navGeo, new THREE.MeshBasicMaterial({ color: 0xff0000, transparent: true, opacity: 0.8 }));
  redNav.position.set(0.2, 0, -2.0);
  group.add(redNav);
  const greenNav = new THREE.Mesh(navGeo, new THREE.MeshBasicMaterial({ color: 0x00ff00, transparent: true, opacity: 0.8 }));
  greenNav.position.set(0.2, 0, 2.0);
  group.add(greenNav);

  // Blinking white light on tail
  const whiteNav = new THREE.Mesh(navGeo, new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.9 }));
  whiteNav.position.set(-1.7, 0.1, 0);
  whiteNav.userData.blink = true;
  group.add(whiteNav);

  group.scale.set(1.2, 1.2, 1.2);
  return group;
}

function buildDroneMesh(color) {
  const group = new THREE.Group();

  // Central body - small cube
  const bodyGeo = new THREE.BoxGeometry(0.6, 0.3, 0.6);
  const bodyMat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.7 });
  const body = new THREE.Mesh(bodyGeo, bodyMat);
  group.add(body);

  // 4 arms
  const armGeo = new THREE.BoxGeometry(1.5, 0.08, 0.08);
  const armMat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.5 });
  for (let i = 0; i < 4; i++) {
    const arm = new THREE.Mesh(armGeo, armMat);
    arm.rotation.y = (i * Math.PI) / 2 + Math.PI / 4;
    group.add(arm);
  }

  // 4 rotor discs
  const rotorGeo = new THREE.CircleGeometry(0.4, 8);
  const rotorMat = new THREE.MeshBasicMaterial({ color: 0x88ff88, transparent: true, opacity: 0.25, side: THREE.DoubleSide });
  const offsets = [
    [0.75, 0.15, 0.75], [-0.75, 0.15, 0.75],
    [0.75, 0.15, -0.75], [-0.75, 0.15, -0.75],
  ];
  for (const [ox, oy, oz] of offsets) {
    const rotor = new THREE.Mesh(rotorGeo, rotorMat);
    rotor.rotation.x = -Math.PI / 2;
    rotor.position.set(ox, oy, oz);
    rotor.userData.rotor = true;
    group.add(rotor);
  }

  // Status LED
  const ledGeo = new THREE.SphereGeometry(0.08, 4, 4);
  const ledMat = new THREE.MeshBasicMaterial({ color: 0x00ff44, transparent: true, opacity: 0.9 });
  const led = new THREE.Mesh(ledGeo, ledMat);
  led.position.set(0, -0.2, 0.35);
  led.userData.blink = true;
  group.add(led);

  group.scale.set(1.0, 1.0, 1.0);
  return group;
}

function createVehicle() {
  const type = pickType();
  const [fromCity, toCity] = pickTwoCities();
  const fromPos = cityPosition(fromCity);
  const toPos = cityPosition(toCity);

  const y = type.y();
  const speed = type.speed();

  const colors = [0x33ff33, 0x44aaff, 0xff8844, 0xffcc00, 0xff44ff, 0x44ffcc, 0xaaaaff, 0xff6666];
  const color = colors[Math.floor(Math.random() * colors.length)];

  let mesh;
  if (type.name === 'car') mesh = buildCarMesh(color);
  else if (type.name === 'plane') mesh = buildPlaneMesh(color);
  else mesh = buildDroneMesh(color);

  // Light trail for planes
  if (type.name === 'plane') {
    const trailLight = new THREE.PointLight(new THREE.Color(color), 0.15, 15);
    mesh.add(trailLight);
  }

  return {
    mesh,
    type: type.name,
    from: new THREE.Vector3(fromPos.x, y, fromPos.z),
    to: new THREE.Vector3(toPos.x, y, toPos.z),
    progress: Math.random(),  // Start at random point along route
    speed: speed * 0.008,     // Normalized per frame
    phase: Math.random() * Math.PI * 2,
  };
}

function assignNewRoute(v) {
  const [fromCity, toCity] = pickTwoCities();
  const fromPos = cityPosition(fromCity);
  const toPos = cityPosition(toCity);
  const y = v.type === 'car' ? CAR_Y : v.from.y;
  v.from.set(fromPos.x, y, fromPos.z);
  v.to.set(toPos.x, y, toPos.z);
  v.progress = 0;
}

export function buildVehicles() {
  const scene = getScene();

  for (let i = 0; i < VEHICLE_COUNT; i++) {
    const v = createVehicle();
    scene.add(v.mesh);
    vehicles.push(v);
  }

  onAnimate((elapsed) => {
    for (const v of vehicles) {
      v.progress += v.speed;

      // Arrived: assign new route
      if (v.progress >= 1.0) {
        assignNewRoute(v);
      }

      // Interpolate position
      const t = v.progress;
      const x = v.from.x + (v.to.x - v.from.x) * t;
      const z = v.from.z + (v.to.z - v.from.z) * t;

      // Cars: gentle bump on Y, planes: gentle banking wave
      let y = v.from.y;
      if (v.type === 'car') {
        y = CAR_Y + Math.sin(elapsed * 3 + v.phase) * 0.15;
      } else if (v.type === 'plane') {
        y = v.from.y + Math.sin(elapsed * 0.5 + v.phase) * 3;
      } else {
        // Drone: slight wobble
        y = v.from.y + Math.sin(elapsed * 2 + v.phase) * 0.8;
      }

      v.mesh.position.set(x, y, z);

      // Face direction of travel
      const dx = v.to.x - v.from.x;
      const dz = v.to.z - v.from.z;
      if (Math.abs(dx) > 0.01 || Math.abs(dz) > 0.01) {
        v.mesh.rotation.y = Math.atan2(dx, dz);
      }

      // Plane banking (tilt into turns slightly)
      if (v.type === 'plane') {
        v.mesh.rotation.z = Math.sin(elapsed * 0.3 + v.phase) * 0.08;
      }

      // Drone rotor spin
      if (v.type === 'drone') {
        v.mesh.children.forEach(child => {
          if (child.userData.rotor) {
            child.rotation.z = elapsed * 15 + v.phase;
          }
        });
      }

      // Blinking lights
      v.mesh.children.forEach(child => {
        if (child.userData && child.userData.blink) {
          child.material.opacity = Math.sin(elapsed * 4 + v.phase) > 0.3 ? 0.9 : 0.1;
        }
      });
    }
  });
}
