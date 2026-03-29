/**
 * Vintage Hardware Museum - Three.js Scene Builder
 * Sets up the 3D environment, lighting, and exhibit geometry
 */

class MuseumScene {
  constructor(container) {
    this.container = container;
    this.renderer = null;
    this.scene = null;
    this.camera = null;
    this.exhibitMeshes = new Map(); // id -> mesh
    this.activeGlows = new Map();   // id -> glow mesh
    this.clock = null;
    this.raycaster = null;
    this.mouse = new THREE.Vector2();
    this.animFrameId = null;
  }

  init() {
    // Renderer
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 0.85;
    this.container.appendChild(this.renderer.domElement);

    // Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x06080a);
    this.scene.fog = new THREE.FogExp2(0x06080a, 0.035);

    // Camera
    this.camera = new THREE.PerspectiveCamera(65, window.innerWidth / window.innerHeight, 0.1, 200);
    this.camera.position.set(0, 2.2, 12);

    // Clock
    this.clock = new THREE.Clock();

    // Raycaster
    this.raycaster = new THREE.Raycaster();

    this._buildFloor();
    this._buildCeiling();
    this._buildWalls();
    this._buildLighting();
    this._buildExhibits();
    this._buildAmbientDetails();

    window.addEventListener('resize', () => this._onResize());
  }

  _buildFloor() {
    const size = 50;
    // Grid floor
    const gridHelper = new THREE.GridHelper(size, 50, 0x0a2a14, 0x0a1a0f);
    gridHelper.position.y = 0;
    this.scene.add(gridHelper);

    // Solid floor
    const floorGeo = new THREE.PlaneGeometry(size, size);
    const floorMat = new THREE.MeshStandardMaterial({
      color: 0x07100a,
      metalness: 0.1,
      roughness: 0.95,
    });
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    floor.position.y = -0.01;
    this.scene.add(floor);
  }

  _buildCeiling() {
    const ceilingGeo = new THREE.PlaneGeometry(50, 50);
    const ceilingMat = new THREE.MeshStandardMaterial({
      color: 0x060808,
      metalness: 0.2,
      roughness: 0.9,
    });
    const ceiling = new THREE.Mesh(ceilingGeo, ceilingMat);
    ceiling.rotation.x = Math.PI / 2;
    ceiling.position.y = 8;
    this.scene.add(ceiling);

    // Ceiling strip lights
    const stripColors = [0x00ff88, 0x0044aa, 0xff6600];
    const stripPositions = [
      { x: 0, z: 0 }, { x: -6, z: 0 }, { x: 6, z: 0 },
    ];
    stripPositions.forEach((pos, i) => {
      const stripGeo = new THREE.BoxGeometry(0.08, 0.02, 20);
      const stripMat = new THREE.MeshBasicMaterial({ color: stripColors[i % stripColors.length] });
      const strip = new THREE.Mesh(stripGeo, stripMat);
      strip.position.set(pos.x, 7.95, pos.z);
      this.scene.add(strip);
    });
  }

  _buildWalls() {
    const wallMat = new THREE.MeshStandardMaterial({
      color: 0x080e0a,
      metalness: 0.3,
      roughness: 0.85,
    });
    const wallConfigs = [
      { w: 50, h: 8, pos: [0, 4, -25], rot: [0, 0, 0] },
      { w: 50, h: 8, pos: [0, 4, 25],  rot: [0, Math.PI, 0] },
      { w: 50, h: 8, pos: [-25, 4, 0], rot: [0, Math.PI/2, 0] },
      { w: 50, h: 8, pos: [25, 4, 0],  rot: [0, -Math.PI/2, 0] },
    ];
    wallConfigs.forEach(cfg => {
      const geo = new THREE.PlaneGeometry(cfg.w, cfg.h);
      const mesh = new THREE.Mesh(geo, wallMat);
      mesh.position.set(...cfg.pos);
      mesh.rotation.set(...cfg.rot);
      mesh.receiveShadow = true;
      this.scene.add(mesh);
    });
  }

  _buildLighting() {
    // Ambient
    const ambient = new THREE.AmbientLight(0x0a1a10, 0.6);
    this.scene.add(ambient);

    // Main overhead
    const main = new THREE.DirectionalLight(0xffffff, 0.8);
    main.position.set(5, 10, 5);
    main.castShadow = true;
    main.shadow.mapSize.width = 2048;
    main.shadow.mapSize.height = 2048;
    this.scene.add(main);

    // Green accent (RTC brand color)
    const greenFill = new THREE.PointLight(0x00ff88, 1.5, 25);
    greenFill.position.set(0, 5, 0);
    this.scene.add(greenFill);

    // Blue fill from left
    const blueFill = new THREE.PointLight(0x0033ff, 0.8, 20);
    blueFill.position.set(-12, 4, 0);
    this.scene.add(blueFill);

    // Warm accent near right exhibits
    const warmFill = new THREE.PointLight(0xff6600, 0.6, 18);
    warmFill.position.set(8, 3, -2);
    this.scene.add(warmFill);
  }

  _buildExhibits() {
    EXHIBITS.forEach(exhibit => {
      const group = this._createExhibitGroup(exhibit);
      this.scene.add(group);
      this.exhibitMeshes.set(exhibit.id, group);
    });
  }

  _createExhibitGroup(exhibit) {
    const group = new THREE.Group();
    const d = exhibit.dimensions;

    // Main body
    const bodyGeo = new THREE.BoxGeometry(d.w, d.h, d.d);
    const bodyMat = new THREE.MeshStandardMaterial({
      color: exhibit.color,
      metalness: 0.6,
      roughness: 0.4,
      envMapIntensity: 0.5,
    });
    const body = new THREE.Mesh(bodyGeo, bodyMat);
    body.castShadow = true;
    body.receiveShadow = true;
    body.position.y = d.h / 2;
    body.userData = { exhibitId: exhibit.id };
    group.add(body);

    // Accent panel / faceplate
    const faceGeo = new THREE.BoxGeometry(d.w * 0.85, d.h * 0.7, 0.04);
    const faceMat = new THREE.MeshStandardMaterial({
      color: 0x111a14,
      metalness: 0.8,
      roughness: 0.3,
    });
    const face = new THREE.Mesh(faceGeo, faceMat);
    face.position.set(0, d.h / 2, d.d / 2 + 0.02);
    face.userData = { exhibitId: exhibit.id };
    group.add(face);

    // LED indicator strip
    const ledGeo = new THREE.BoxGeometry(d.w * 0.4, 0.04, 0.05);
    const ledMat = new THREE.MeshBasicMaterial({ color: 0x004422 });
    const led = new THREE.Mesh(ledGeo, ledMat);
    led.position.set(0, d.h * 0.85, d.d / 2 + 0.03);
    led.userData = { exhibitId: exhibit.id, isLed: true };
    group.add(led);

    // Glow sphere (hidden by default, shown when active)
    const glowGeo = new THREE.SphereGeometry(d.w * 0.8, 16, 16);
    const glowMat = new THREE.MeshBasicMaterial({
      color: exhibit.glowColor,
      transparent: true,
      opacity: 0,
      side: THREE.BackSide,
    });
    const glow = new THREE.Mesh(glowGeo, glowMat);
    glow.position.y = d.h / 2;
    glow.userData = { isGlow: true };
    group.add(glow);
    this.activeGlows.set(exhibit.id, { glow, led, ledMat, glowMat, exhibit });

    // Pedestal
    if (exhibit.dimensions.h < 1.0) {
      const pedGeo = new THREE.BoxGeometry(d.w + 0.3, 1.0, d.d + 0.3);
      const pedMat = new THREE.MeshStandardMaterial({
        color: 0x0a1208,
        metalness: 0.4,
        roughness: 0.7,
      });
      const ped = new THREE.Mesh(pedGeo, pedMat);
      ped.position.y = 0.5;
      ped.castShadow = true;
      ped.receiveShadow = true;
      ped.userData = { exhibitId: exhibit.id };
      group.add(ped);
      // Shift main body up
      body.position.y = d.h / 2 + 1.0;
      face.position.y = d.h / 2 + 1.0;
      led.position.y = d.h * 0.85 + 1.0;
      glow.position.y = d.h / 2 + 1.0;
    }

    // Nameplate
    const plateGeo = new THREE.BoxGeometry(d.w * 0.6, 0.25, 0.05);
    const plateMat = new THREE.MeshStandardMaterial({
      color: 0x001a0a,
      metalness: 0.9,
      roughness: 0.2,
      emissive: exhibit.glowColor,
      emissiveIntensity: 0.05,
    });
    const plate = new THREE.Mesh(plateGeo, plateMat);
    plate.position.set(0, 0.15, d.d / 2 + 0.06);
    group.add(plate);

    group.position.set(exhibit.position.x, 0, exhibit.position.z);
    group.userData = { exhibitId: exhibit.id };

    return group;
  }

  _buildAmbientDetails() {
    // Decorative floating cubes / data particles
    for (let i = 0; i < 80; i++) {
      const size = Math.random() * 0.04 + 0.01;
      const geo = new THREE.BoxGeometry(size, size, size);
      const mat = new THREE.MeshBasicMaterial({
        color: Math.random() > 0.5 ? 0x00ff88 : (Math.random() > 0.5 ? 0x0066ff : 0xff6600),
        transparent: true,
        opacity: Math.random() * 0.4 + 0.1,
      });
      const particle = new THREE.Mesh(geo, mat);
      particle.position.set(
        (Math.random() - 0.5) * 40,
        Math.random() * 6 + 0.5,
        (Math.random() - 0.5) * 40
      );
      particle.userData = {
        isParticle: true,
        speed: Math.random() * 0.3 + 0.1,
        baseY: particle.position.y,
        phase: Math.random() * Math.PI * 2,
      };
      this.scene.add(particle);
    }

    // Holographic ring around centerpiece (IBM POWER8)
    const ringGeo = new THREE.TorusGeometry(3.5, 0.03, 8, 80);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0x00aaff,
      transparent: true,
      opacity: 0.35,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.position.set(0, 0.05, 0);
    ring.rotation.x = -Math.PI / 2;
    ring.userData = { isRing: true };
    this.scene.add(ring);

    const ring2 = ring.clone();
    ring2.scale.set(1.3, 1.3, 1.3);
    ring2.material = ringMat.clone();
    ring2.material.opacity = 0.15;
    ring2.userData = { isRing: true, phase: Math.PI };
    this.scene.add(ring2);
  }

  setExhibitActive(exhibitId, active) {
    const data = this.activeGlows.get(exhibitId);
    if (!data) return;
    const targetOpacity = active ? 0.12 : 0;
    const targetLed = active ? data.exhibit.glowColor : 0x004422;

    data.glowMat.opacity = targetOpacity;
    data.ledMat.color.setHex(active ? data.exhibit.glowColor : 0x004422);

    if (active) {
      // Point light at exhibit
      if (!data.pointLight) {
        const light = new THREE.PointLight(data.exhibit.glowColor, 2.5, 8);
        light.position.set(
          data.exhibit.position.x,
          2,
          data.exhibit.position.z
        );
        this.scene.add(light);
        data.pointLight = light;
      }
      data.pointLight.intensity = 2.5;
    } else if (data.pointLight) {
      data.pointLight.intensity = 0;
    }
  }

  getIntersectedExhibit(normalizedX, normalizedY) {
    this.mouse.set(normalizedX, normalizedY);
    this.raycaster.setFromCamera(this.mouse, this.camera);
    const objects = [];
    this.exhibitMeshes.forEach(group => {
      group.traverse(child => {
        if (child.isMesh && child.userData.exhibitId) objects.push(child);
      });
    });
    const hits = this.raycaster.intersectObjects(objects, false);
    if (hits.length > 0) return hits[0].object.userData.exhibitId;
    return null;
  }

  animate(onFrame) {
    const loop = () => {
      this.animFrameId = requestAnimationFrame(loop);
      const delta = this.clock.getDelta();
      const elapsed = this.clock.getElapsedTime();

      // Animate particles
      this.scene.children.forEach(obj => {
        if (obj.userData.isParticle) {
          obj.position.y = obj.userData.baseY + Math.sin(elapsed * obj.userData.speed + obj.userData.phase) * 0.3;
          obj.rotation.x += delta * 0.5;
          obj.rotation.y += delta * 0.3;
        }
        if (obj.userData.isRing) {
          obj.rotation.z += delta * (obj.userData.phase ? -0.2 : 0.3);
        }
      });

      // Pulse active glows
      this.activeGlows.forEach((data, id) => {
        if (data.glowMat.opacity > 0.01) {
          const pulse = 0.08 + Math.sin(elapsed * 2 + (data.exhibit.position.x || 0)) * 0.04;
          data.glowMat.opacity = pulse;
          if (data.pointLight) {
            data.pointLight.intensity = 2.0 + Math.sin(elapsed * 3) * 0.5;
          }
        }
      });

      if (onFrame) onFrame(delta, elapsed);
      this.renderer.render(this.scene, this.camera);
    };
    loop();
  }

  destroy() {
    if (this.animFrameId) cancelAnimationFrame(this.animFrameId);
    this.renderer.dispose();
  }

  _onResize() {
    this.camera.aspect = window.innerWidth / window.innerHeight;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(window.innerWidth, window.innerHeight);
  }
}
