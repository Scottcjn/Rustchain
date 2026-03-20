// SPDX-License-Identifier: MIT

class BeaconMobileControls {
    constructor(camera, renderer, scene) {
        this.camera = camera;
        this.renderer = renderer;
        this.scene = scene;

        this.touchState = {
            isTouch: false,
            touches: new Map(),
            lastDistance: 0,
            lastAngle: 0,
            rotationSpeed: 0.002,
            zoomSpeed: 0.01,
            dampingFactor: 0.95
        };

        this.momentum = {
            rotation: { x: 0, y: 0 },
            zoom: 0,
            active: false
        };

        this.initEventListeners();
    }

    initEventListeners() {
        const canvas = this.renderer.domElement;

        canvas.addEventListener('touchstart', (e) => this.handleTouchStart(e), { passive: false });
        canvas.addEventListener('touchmove', (e) => this.handleTouchMove(e), { passive: false });
        canvas.addEventListener('touchend', (e) => this.handleTouchEnd(e), { passive: false });
        canvas.addEventListener('touchcancel', (e) => this.handleTouchEnd(e), { passive: false });

        // Prevent default browser behaviors
        canvas.addEventListener('gesturestart', (e) => e.preventDefault());
        canvas.addEventListener('gesturechange', (e) => e.preventDefault());
        canvas.addEventListener('gestureend', (e) => e.preventDefault());
    }

    handleTouchStart(event) {
        event.preventDefault();

        this.touchState.isTouch = true;
        this.momentum.active = false;

        for (let i = 0; i < event.touches.length; i++) {
            const touch = event.touches[i];
            this.touchState.touches.set(touch.identifier, {
                x: touch.clientX,
                y: touch.clientY,
                startTime: Date.now()
            });
        }

        if (event.touches.length >= 2) {
            const touch1 = event.touches[0];
            const touch2 = event.touches[1];

            this.touchState.lastDistance = this.getDistance(touch1, touch2);
            this.touchState.lastAngle = this.getAngle(touch1, touch2);
        }
    }

    handleTouchMove(event) {
        event.preventDefault();

        if (!this.touchState.isTouch) return;

        if (event.touches.length === 1) {
            this.handleSingleTouchMove(event.touches[0]);
        } else if (event.touches.length === 2) {
            this.handleMultiTouchMove(event.touches[0], event.touches[1]);
        }
    }

    handleSingleTouchMove(touch) {
        const prevTouch = this.touchState.touches.get(touch.identifier);
        if (!prevTouch) return;

        const deltaX = touch.clientX - prevTouch.x;
        const deltaY = touch.clientY - prevTouch.y;

        // Camera rotation based on swipe
        const rotationX = -deltaY * this.touchState.rotationSpeed;
        const rotationY = -deltaX * this.touchState.rotationSpeed;

        this.rotateCamera(rotationX, rotationY);

        // Store momentum
        this.momentum.rotation.x = rotationX * 0.3;
        this.momentum.rotation.y = rotationY * 0.3;

        // Update touch position
        prevTouch.x = touch.clientX;
        prevTouch.y = touch.clientY;
    }

    handleMultiTouchMove(touch1, touch2) {
        const distance = this.getDistance(touch1, touch2);
        const angle = this.getAngle(touch1, touch2);

        // Pinch to zoom
        if (this.touchState.lastDistance > 0) {
            const zoomDelta = (distance - this.touchState.lastDistance) * this.touchState.zoomSpeed;
            this.zoomCamera(zoomDelta);
            this.momentum.zoom = zoomDelta * 0.2;
        }

        // Two-finger rotation (optional - can be disabled for simpler UX)
        if (Math.abs(angle - this.touchState.lastAngle) < Math.PI / 2) {
            const angleDelta = angle - this.touchState.lastAngle;
            this.rotateCamera(0, 0, angleDelta * 0.5);
        }

        this.touchState.lastDistance = distance;
        this.touchState.lastAngle = angle;
    }

    handleTouchEnd(event) {
        event.preventDefault();

        // Remove ended touches
        const activeTouches = new Set();
        for (let i = 0; i < event.touches.length; i++) {
            activeTouches.add(event.touches[i].identifier);
        }

        for (const [id] of this.touchState.touches) {
            if (!activeTouches.has(id)) {
                this.touchState.touches.delete(id);
            }
        }

        if (event.touches.length === 0) {
            this.touchState.isTouch = false;
            this.touchState.lastDistance = 0;

            // Start momentum decay
            if (Math.abs(this.momentum.rotation.x) > 0.001 ||
                Math.abs(this.momentum.rotation.y) > 0.001 ||
                Math.abs(this.momentum.zoom) > 0.001) {
                this.momentum.active = true;
                this.applyMomentum();
            }
        }
    }

    rotateCamera(pitchDelta, yawDelta, rollDelta = 0) {
        // Get current camera position relative to target
        const spherical = new THREE.Spherical();
        spherical.setFromVector3(this.camera.position);

        // Apply rotations with bounds checking
        spherical.theta += yawDelta;
        spherical.phi = Math.max(0.1, Math.min(Math.PI - 0.1, spherical.phi + pitchDelta));

        // Update camera position
        this.camera.position.setFromSpherical(spherical);
        this.camera.lookAt(0, 0, 0);

        // Roll rotation if specified
        if (rollDelta !== 0) {
            this.camera.rotateZ(rollDelta);
        }
    }

    zoomCamera(delta) {
        const direction = new THREE.Vector3();
        this.camera.getWorldDirection(direction);
        direction.multiplyScalar(delta * 50);

        this.camera.position.add(direction);

        // Clamp zoom distance
        const distance = this.camera.position.length();
        if (distance < 100) {
            this.camera.position.normalize().multiplyScalar(100);
        } else if (distance > 2000) {
            this.camera.position.normalize().multiplyScalar(2000);
        }
    }

    applyMomentum() {
        if (!this.momentum.active) return;

        // Apply momentum to camera
        this.rotateCamera(
            this.momentum.rotation.x,
            this.momentum.rotation.y
        );

        if (Math.abs(this.momentum.zoom) > 0.001) {
            this.zoomCamera(this.momentum.zoom);
        }

        // Decay momentum
        this.momentum.rotation.x *= this.touchState.dampingFactor;
        this.momentum.rotation.y *= this.touchState.dampingFactor;
        this.momentum.zoom *= this.touchState.dampingFactor;

        // Check if momentum should stop
        if (Math.abs(this.momentum.rotation.x) < 0.001 &&
            Math.abs(this.momentum.rotation.y) < 0.001 &&
            Math.abs(this.momentum.zoom) < 0.001) {
            this.momentum.active = false;
            return;
        }

        requestAnimationFrame(() => this.applyMomentum());
    }

    getDistance(touch1, touch2) {
        const dx = touch2.clientX - touch1.clientX;
        const dy = touch2.clientY - touch1.clientY;
        return Math.sqrt(dx * dx + dy * dy);
    }

    getAngle(touch1, touch2) {
        return Math.atan2(touch2.clientY - touch1.clientY, touch2.clientX - touch1.clientX);
    }

    // Utility method to detect if running on mobile
    static isMobileDevice() {
        return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
               ('ontouchstart' in window) ||
               (navigator.maxTouchPoints > 0);
    }

    // Method to enable/disable based on device
    setEnabled(enabled) {
        this.touchState.isTouch = false;
        this.momentum.active = false;
        this.touchState.touches.clear();
    }
}

// Export for use in beacon atlas
window.BeaconMobileControls = BeaconMobileControls;
