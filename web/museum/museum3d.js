import * as THREE from './vendor/three.module.js';
import { OrbitControls } from './vendor/OrbitControls.js';

(() => {
  const canvas = document.getElementById('c');
  const statusChip = document.getElementById('statusChip');
  const recenterBtn = document.getElementById('recenterBtn');

  const panel = document.getElementById('panel');
  const pTitle = document.getElementById('pTitle');
  const pSub = document.getElementById('pSub');
  const pBody = document.getElementById('pBody');
  const closeBtn = document.getElementById('closeBtn');

  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x0f1318, 0.035);

  const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 200);
  camera.position.set(0, 10, 22);

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
  renderer.setClearColor(0x0f1318, 1);
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));

  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.target.set(0, 4, 0);

  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();

  const clock = new THREE.Clock();

  function resize() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h, false);
  }
  window.addEventListener('resize', resize);
  resize();

  // Lighting
  scene.add(new THREE.AmbientLight(0xffffff, 0.35));
  const key = new THREE.DirectionalLight(0xffffff, 0.85);
  key.position.set(8, 16, 10);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0x4b7bd8, 0.35);
  rim.position.set(-10, 10, -10);
  scene.add(rim);

  // Floor
  const floorGeo = new THREE.PlaneGeometry(140, 140);
  const floorMat = new THREE.MeshStandardMaterial({
    color: 0x141a21,
    roughness: 0.95,
    metalness: 0.0,
  });
  const floor = new THREE.Mesh(floorGeo, floorMat);
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = 0;
  scene.add(floor);

  // Wing markers
  function makeWing(label, x, z, color) {
    const group = new THREE.Group();

    const pad = new THREE.Mesh(
      new THREE.PlaneGeometry(34, 22),
      new THREE.MeshStandardMaterial({ color, roughness: 1.0, metalness: 0.0, transparent: true, opacity: 0.07 })
    );
    pad.rotation.x = -Math.PI / 2;
    pad.position.set(x, 0.01, z);
    group.add(pad);

    const border = new THREE.Mesh(
      new THREE.RingGeometry(10, 10.18, 96),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.45 })
    );
    border.rotation.x = -Math.PI / 2;
    border.position.set(x, 0.02, z);
    group.add(border);

    const sprite = makeTextSprite(label, { color: '#f7f4ef', bg: 'rgba(0,0,0,0.0)', font: '600 22px IBM Plex Mono' });
    sprite.position.set(x, 6.5, z);
    group.add(sprite);

    scene.add(group);
    return { x, z };
  }

  const wingVintage = makeWing('VINTAGE', -28, 0, 0xd6b25e);
  const wingModern = makeWing('MODERN', 0, 0, 0x4b7bd8);
  const wingOther = makeWing('EXOTIC', 28, 0, 0x3a7a62);

  // Machine instances
  const machines = new Map(); // miner_id -> {group, orb, base, data, last_attest}
  const clickable = [];

  function colorFor(m) {
    const t = String(m.hardware_type || '').toLowerCase();
    if (t.includes('vintage') || t.includes('retro') || t.includes('powerpc')) return 0xd6b25e;
    if (t.includes('modern') || t.includes('apple silicon') || t.includes('x86-64')) return 0x4b7bd8;
    return 0x3a7a62;
  }

  function wingFor(m) {
    const t = String(m.hardware_type || '').toLowerCase();
    if (t.includes('vintage') || t.includes('retro') || t.includes('powerpc')) return wingVintage;
    if (t.includes('modern') || t.includes('apple silicon') || t.includes('x86-64')) return wingModern;
    return wingOther;
  }

  function makePedestal(color) {
    const g = new THREE.Group();

    const base = new THREE.Mesh(
      new THREE.CylinderGeometry(1.05, 1.25, 0.6, 18),
      new THREE.MeshStandardMaterial({ color: 0x1b222b, roughness: 0.9, metalness: 0.0 })
    );
    base.position.y = 0.3;
    g.add(base);

    const rim = new THREE.Mesh(
      new THREE.TorusGeometry(1.05, 0.05, 10, 40),
      new THREE.MeshStandardMaterial({ color, roughness: 0.3, metalness: 0.25, emissive: color, emissiveIntensity: 0.15 })
    );
    rim.rotation.x = Math.PI / 2;
    rim.position.y = 0.62;
    g.add(rim);

    return g;
  }

  function makeOrb(color) {
    const mat = new THREE.MeshStandardMaterial({
      color,
      emissive: color,
      emissiveIntensity: 0.35,
      roughness: 0.35,
      metalness: 0.2,
    });
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.55, 22, 18), mat);
    mesh.position.y = 2.0;
    return mesh;
  }

  function makeTextSprite(text, opts = {}) {
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const pad = 10 * dpr;
    const font = opts.font || '600 20px IBM Plex Mono';

    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');

    ctx.font = font;
    const metrics = ctx.measureText(text);
    const w = Math.ceil(metrics.width + pad * 2);
    const h = Math.ceil(40 * dpr);

    canvas.width = w;
    canvas.height = h;

    ctx.font = font;
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'center';

    ctx.fillStyle = opts.bg || 'rgba(15,19,24,0.65)';
    roundRect(ctx, 0, 0, w, h, 14 * dpr);
    ctx.fill();

    ctx.strokeStyle = 'rgba(255,255,255,0.18)';
    ctx.lineWidth = 2 * dpr;
    ctx.stroke();

    ctx.fillStyle = opts.color || '#f7f4ef';
    ctx.fillText(text, w / 2, h / 2 + 1);

    const tex = new THREE.CanvasTexture(canvas);
    tex.minFilter = THREE.LinearFilter;
    tex.magFilter = THREE.LinearFilter;

    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true }));
    sprite.scale.set((w / dpr) / 60, (h / dpr) / 60, 1);
    return sprite;
  }

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  function openPanel(m) {
    pTitle.textContent = m.hardware_type || 'Machine';
    pSub.textContent = `${m.device_family || 'unknown'} / ${m.device_arch || 'unknown'}`;

    const rows = [
      ['Miner', m.miner],
      ['Multiplier', `${Number(m.antiquity_multiplier || 1).toFixed(3)}x`],
      ['Entropy', Number(m.entropy_score || 0).toFixed(6)],
      ['First Attest', m.first_attest ? new Date(m.first_attest * 1000).toLocaleString() : 'n/a'],
      ['Last Attest', m.last_attest ? new Date(m.last_attest * 1000).toLocaleString() : 'n/a'],
    ];

    pBody.innerHTML = '';
    for (const [k, v] of rows) {
      const kv = document.createElement('div');
      kv.className = 'kv';
      kv.innerHTML = `<div class="k">${k}</div><div class="v">${String(v || '')}</div>`;
      pBody.appendChild(kv);
    }

    panel.hidden = false;
  }

  closeBtn.addEventListener('click', () => (panel.hidden = true));

  function recenter() {
    controls.target.set(0, 4, 0);
    camera.position.set(0, 10, 22);
    controls.update();
  }
  recenterBtn.addEventListener('click', recenter);

  function onPointer(e) {
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    pointer.x = x * 2 - 1;
    pointer.y = -(y * 2 - 1);
  }

  canvas.addEventListener('pointermove', onPointer);
  canvas.addEventListener('click', (e) => {
    onPointer(e);
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(clickable, true);
    if (!hits.length) return;
    let obj = hits[0].object;
    while (obj && !obj.userData.miner) obj = obj.parent;
    if (obj && obj.userData.miner) openPanel(obj.userData.miner);
  });

  function setStatus(text) {
    statusChip.textContent = text;
  }

  async function api(path) {
    const r = await fetch(path, { cache: 'no-store' });
    if (!r.ok) throw new Error(`${path} -> ${r.status}`);
    return await r.json();
  }

  function placeMachines(miners) {
    // deterministic layout within each wing
    const byWing = { vintage: [], modern: [], other: [] };
    for (const m of miners) {
      const t = String(m.hardware_type || '').toLowerCase();
      if (t.includes('vintage') || t.includes('retro') || t.includes('powerpc')) byWing.vintage.push(m);
      else if (t.includes('modern') || t.includes('apple silicon') || t.includes('x86-64')) byWing.modern.push(m);
      else byWing.other.push(m);
    }

    const layouts = [
      ['vintage', wingVintage],
      ['modern', wingModern],
      ['other', wingOther],
    ];

    for (const [k, wing] of layouts) {
      const list = byWing[k];
      const cols = 3;
      const spacingX = 5.0;
      const spacingZ = 4.0;
      for (let i = 0; i < list.length; i++) {
        const m = list[i];
        const col = i % cols;
        const row = Math.floor(i / cols);
        const x = wing.x + (col - 1) * spacingX;
        const z = wing.z + (row - 1) * spacingZ;

        upsertMachine(m, x, z);
      }
    }

    // Remove missing machines
    const keep = new Set(miners.map(m => String(m.miner)));
    for (const [id, rec] of machines.entries()) {
      if (!keep.has(id)) {
        scene.remove(rec.group);
        machines.delete(id);
      }
    }
  }

  function upsertMachine(m, x, z) {
    const id = String(m.miner);
    const existing = machines.get(id);
    const color = colorFor(m);

    if (!existing) {
      const group = new THREE.Group();
      group.position.set(x, 0, z);

      const pedestal = makePedestal(color);
      group.add(pedestal);

      const orb = makeOrb(color);
      group.add(orb);

      const label = makeTextSprite(shortId(id), { bg: 'rgba(15,19,24,0.70)' });
      label.position.set(0, 3.2, 0);
      group.add(label);

      group.userData.miner = m;
      clickable.push(group);

      scene.add(group);
      machines.set(id, { group, orb, data: m, last_attest: m.last_attest || 0, pulse: 0 });
      return;
    }

    existing.group.position.set(x, 0, z);
    existing.group.userData.miner = m;

    const last = Number(existing.last_attest || 0);
    const cur = Number(m.last_attest || 0);
    if (cur && cur > last) existing.pulse = 1.0;

    existing.last_attest = cur;
    existing.data = m;
  }

  function shortId(id) {
    if (id.length <= 10) return id;
    return id.slice(0, 6) + '…' + id.slice(-3);
  }

  async function refresh() {
    try {
      const miners = await api('/api/miners');
      const list = Array.isArray(miners) ? miners : (miners?.miners || []);
      placeMachines(list);
      setStatus(`Loaded ${list.length} miners | ${new Date().toLocaleTimeString()}`);
    } catch (e) {
      setStatus(`Load failed: ${String(e)}`);
    }
  }

  let tNext = 0;
  function tick() {
    const dt = clock.getDelta();
    controls.update();

    // Idle animation + pulse
    for (const rec of machines.values()) {
      const g = rec.group;
      const orb = rec.orb;
      const t = performance.now() * 0.001;

      orb.position.y = 2.0 + Math.sin(t * 1.6 + g.position.x * 0.05) * 0.18;
      orb.rotation.y += dt * 0.3;

      if (rec.pulse > 0) {
        rec.pulse = Math.max(0, rec.pulse - dt * 1.2);
        const s = 1 + rec.pulse * 0.55;
        orb.scale.set(s, s, s);
        orb.material.emissiveIntensity = 0.35 + rec.pulse * 1.1;
      } else {
        orb.scale.set(1, 1, 1);
        orb.material.emissiveIntensity = 0.35;
      }
    }

    // soft refresh
    if (performance.now() > tNext) {
      tNext = performance.now() + 10_000;
      refresh();
    }

    renderer.render(scene, camera);
    requestAnimationFrame(tick);
  }

  recenter();
  refresh().then(() => {
    tNext = performance.now() + 10_000;
    tick();
  });
})();
