/**
 * Vintage Hardware Museum - Camera / Player Controls
 * WASD + mouse look, mobile touch joystick
 */

class MuseumControls {
  constructor(camera, domElement) {
    this.camera = camera;
    this.domElement = domElement;

    // Movement state
    this.keys = { w: false, a: false, s: false, d: false, q: false, e: false };
    this.moveSpeed = 6.0;
    this.sprintSpeed = 14.0;
    this.isSprinting = false;

    // Mouse look state
    this.yaw = 0;
    this.pitch = 0;
    this.sensitivity = 0.002;
    this.isPointerLocked = false;

    // Touch state
    this.touchMove = { x: 0, y: 0 };
    this.touchLook = { x: 0, y: 0, startX: 0, startY: 0, active: false };

    // Bounds
    this.minY = 1.5;
    this.maxY = 6.0;
    this.bounds = 23;

    // Look angles (match initial camera orientation)
    this.yaw = Math.PI; // face into museum

    this._bindEvents();
  }

  _bindEvents() {
    // Keyboard
    document.addEventListener('keydown', e => this._onKeyDown(e));
    document.addEventListener('keyup', e => this._onKeyUp(e));

    // Pointer lock
    this.domElement.addEventListener('click', () => {
      if (!this.isPointerLocked) {
        this.domElement.requestPointerLock().catch(() => {});
      }
    });
    document.addEventListener('pointerlockchange', () => {
      this.isPointerLocked = document.pointerLockElement === this.domElement;
    });
    document.addEventListener('mousemove', e => this._onMouseMove(e));

    // Touch controls for mobile
    document.addEventListener('touchstart', e => this._onTouchStart(e), { passive: false });
    document.addEventListener('touchmove', e => this._onTouchMove(e), { passive: false });
    document.addEventListener('touchend', e => this._onTouchEnd(e), { passive: false });

    // Touch button elements (set up after DOM ready)
    this._setupTouchButtons();
  }

  _setupTouchButtons() {
    const btnMap = {
      'touch-w': 'w', 'touch-s': 's',
      'touch-a': 'a', 'touch-d': 'd',
    };
    Object.entries(btnMap).forEach(([id, key]) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.addEventListener('touchstart', e => {
        e.preventDefault();
        this.keys[key] = true;
        el.classList.add('pressed');
      }, { passive: false });
      el.addEventListener('touchend', e => {
        e.preventDefault();
        this.keys[key] = false;
        el.classList.remove('pressed');
      }, { passive: false });
      // Mouse fallback for desktop testing
      el.addEventListener('mousedown', () => { this.keys[key] = true; el.classList.add('pressed'); });
      el.addEventListener('mouseup', () => { this.keys[key] = false; el.classList.remove('pressed'); });
    });
  }

  _onKeyDown(e) {
    const k = e.key.toLowerCase();
    if (k === 'w' || k === 'arrowup') this.keys.w = true;
    if (k === 'a' || k === 'arrowleft') this.keys.a = true;
    if (k === 's' || k === 'arrowdown') this.keys.s = true;
    if (k === 'd' || k === 'arrowright') this.keys.d = true;
    if (k === 'q') this.keys.q = true;
    if (k === 'e') this.keys.e = true;
    if (k === 'shift') this.isSprinting = true;
    if (k === 'escape' && this.isPointerLocked) document.exitPointerLock();
  }

  _onKeyUp(e) {
    const k = e.key.toLowerCase();
    if (k === 'w' || k === 'arrowup') this.keys.w = false;
    if (k === 'a' || k === 'arrowleft') this.keys.a = false;
    if (k === 's' || k === 'arrowdown') this.keys.s = false;
    if (k === 'd' || k === 'arrowright') this.keys.d = false;
    if (k === 'q') this.keys.q = false;
    if (k === 'e') this.keys.e = false;
    if (k === 'shift') this.isSprinting = false;
  }

  _onMouseMove(e) {
    if (!this.isPointerLocked) return;
    this.yaw -= e.movementX * this.sensitivity;
    this.pitch -= e.movementY * this.sensitivity;
    this.pitch = Math.max(-Math.PI / 3, Math.min(Math.PI / 3, this.pitch));
  }

  _onTouchStart(e) {
    // Right half of screen = look
    for (const touch of e.changedTouches) {
      if (touch.clientX > window.innerWidth / 2) {
        this.touchLook = {
          active: true,
          x: touch.clientX,
          y: touch.clientY,
          startX: touch.clientX,
          startY: touch.clientY,
          id: touch.identifier,
        };
      }
    }
  }

  _onTouchMove(e) {
    e.preventDefault();
    for (const touch of e.changedTouches) {
      if (this.touchLook.active && touch.identifier === this.touchLook.id) {
        const dx = touch.clientX - this.touchLook.x;
        const dy = touch.clientY - this.touchLook.y;
        this.yaw -= dx * this.sensitivity * 1.5;
        this.pitch -= dy * this.sensitivity * 1.5;
        this.pitch = Math.max(-Math.PI / 3, Math.min(Math.PI / 3, this.pitch));
        this.touchLook.x = touch.clientX;
        this.touchLook.y = touch.clientY;
      }
    }
  }

  _onTouchEnd(e) {
    for (const touch of e.changedTouches) {
      if (touch.identifier === this.touchLook.id) {
        this.touchLook.active = false;
      }
    }
  }

  update(delta) {
    const speed = (this.isSprinting ? this.sprintSpeed : this.moveSpeed) * delta;

    // Calculate forward/right vectors from yaw
    const forward = new THREE.Vector3(
      -Math.sin(this.yaw),
      0,
      -Math.cos(this.yaw)
    );
    const right = new THREE.Vector3(
      Math.cos(this.yaw),
      0,
      -Math.sin(this.yaw)
    );

    const move = new THREE.Vector3();
    if (this.keys.w) move.addScaledVector(forward, speed);
    if (this.keys.s) move.addScaledVector(forward, -speed);
    if (this.keys.a) move.addScaledVector(right, -speed);
    if (this.keys.d) move.addScaledVector(right, speed);
    if (this.keys.q) move.y -= speed;
    if (this.keys.e) move.y += speed;

    this.camera.position.add(move);

    // Clamp position
    this.camera.position.x = Math.max(-this.bounds, Math.min(this.bounds, this.camera.position.x));
    this.camera.position.z = Math.max(-this.bounds, Math.min(this.bounds, this.camera.position.z));
    this.camera.position.y = Math.max(this.minY, Math.min(this.maxY, this.camera.position.y));

    // Apply rotation
    const euler = new THREE.Euler(this.pitch, this.yaw, 0, 'YXZ');
    this.camera.quaternion.setFromEuler(euler);
  }

  // Set look direction toward a world position
  lookAt(worldPos) {
    const dir = new THREE.Vector3().subVectors(worldPos, this.camera.position).normalize();
    this.yaw = Math.atan2(-dir.x, -dir.z);
    this.pitch = Math.asin(Math.max(-1, Math.min(1, dir.y)));
  }
}
