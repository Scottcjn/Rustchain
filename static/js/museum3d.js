// SPDX-License-Identifier: MIT

class Museum3D {
    constructor() {
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.exhibits = [];
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();
        this.keys = {};
        this.moveSpeed = 0.1;
        this.isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
        this.touchStart = { x: 0, y: 0 };
        this.touchEnd = { x: 0, y: 0 };
        this.lastApiUpdate = 0;
        this.apiUpdateInterval = 30000; // 30 seconds
        
        this.init();
        this.animate();
        this.setupEventListeners();
        this.loadExhibits();
    }

    init() {
        // Scene setup
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x0a0a0a);
        this.scene.fog = new THREE.Fog(0x0a0a0a, 10, 100);

        // Camera setup
        this.camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
        this.camera.position.set(0, 2, 5);

        // Renderer setup
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.2;
        document.getElementById('museum-container').appendChild(this.renderer.domElement);

        // Lighting
        this.setupLighting();
        
        // Floor
        this.createFloor();
        
        // Create exhibit pedestals
        this.createPedestals();
    }

    setupLighting() {
        // Ambient light
        const ambientLight = new THREE.AmbientLight(0x404040, 0.3);
        this.scene.add(ambientLight);

        // Main directional light
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(10, 10, 5);
        directionalLight.castShadow = true;
        directionalLight.shadow.mapSize.width = 2048;
        directionalLight.shadow.mapSize.height = 2048;
        directionalLight.shadow.camera.near = 0.5;
        directionalLight.shadow.camera.far = 50;
        this.scene.add(directionalLight);

        // Exhibit spot lights
        const spotLight1 = new THREE.SpotLight(0xffffff, 1, 10, Math.PI * 0.3, 0.3, 1);
        spotLight1.position.set(-3, 5, 0);
        spotLight1.target.position.set(-3, 0, 0);
        this.scene.add(spotLight1);
        this.scene.add(spotLight1.target);

        const spotLight2 = new THREE.SpotLight(0xffffff, 1, 10, Math.PI * 0.3, 0.3, 1);
        spotLight2.position.set(3, 5, 0);
        spotLight2.target.position.set(3, 0, 0);
        this.scene.add(spotLight2);
        this.scene.add(spotLight2.target);
    }

    createFloor() {
        const floorGeometry = new THREE.PlaneGeometry(50, 50);
        const floorMaterial = new THREE.MeshLambertMaterial({ 
            color: 0x222222,
            transparent: true,
            opacity: 0.8
        });
        const floor = new THREE.Mesh(floorGeometry, floorMaterial);
        floor.rotation.x = -Math.PI / 2;
        floor.receiveShadow = true;
        this.scene.add(floor);
    }

    createPedestals() {
        const pedestalGeometry = new THREE.CylinderGeometry(1.2, 1.2, 0.3, 8);
        const pedestalMaterial = new THREE.MeshPhongMaterial({ color: 0x333333 });
        
        // PowerBook G4 pedestal
        const pedestal1 = new THREE.Mesh(pedestalGeometry, pedestalMaterial);
        pedestal1.position.set(-3, 0.15, 0);
        pedestal1.castShadow = true;
        pedestal1.receiveShadow = true;
        this.scene.add(pedestal1);

        // IBM POWER8 pedestal
        const pedestal2 = new THREE.Mesh(pedestalGeometry, pedestalMaterial);
        pedestal2.position.set(3, 0.15, 0);
        pedestal2.castShadow = true;
        pedestal2.receiveShadow = true;
        this.scene.add(pedestal2);
    }

    loadExhibits() {
        this.createPowerBookG4();
        this.createIBMPOWER8();
        this.updateExhibitData();
    }

    createPowerBookG4() {
        const group = new THREE.Group();
        
        // Laptop base
        const baseGeometry = new THREE.BoxGeometry(1.6, 0.1, 1.2);
        const baseMaterial = new THREE.MeshPhongMaterial({ color: 0xc0c0c0 });
        const base = new THREE.Mesh(baseGeometry, baseMaterial);
        base.castShadow = true;
        group.add(base);

        // Screen
        const screenGeometry = new THREE.BoxGeometry(1.5, 1.0, 0.05);
        const screenMaterial = new THREE.MeshPhongMaterial({ color: 0x1a1a1a });
        const screen = new THREE.Mesh(screenGeometry, screenMaterial);
        screen.position.set(0, 0.55, -0.5);
        screen.rotation.x = -Math.PI * 0.1;
        screen.castShadow = true;
        group.add(screen);

        // Logo
        const logoGeometry = new THREE.CircleGeometry(0.08, 16);
        const logoMaterial = new THREE.MeshPhongMaterial({ color: 0xffffff });
        const logo = new THREE.Mesh(logoGeometry, logoMaterial);
        logo.position.set(0, 0.8, -0.47);
        logo.rotation.x = -Math.PI * 0.1;
        group.add(logo);

        group.position.set(-3, 0.35, 0);
        group.userData = { 
            type: 'powerbook_g4',
            name: 'PowerBook G4',
            specs: 'PowerPC G4 • 1.67GHz • 2GB RAM',
            minerId: 'pbg4_001'
        };
        
        this.scene.add(group);
        this.exhibits.push(group);
    }

    createIBMPOWER8() {
        const group = new THREE.Group();
        
        // Server chassis
        const chassisGeometry = new THREE.BoxGeometry(1.8, 0.8, 2.0);
        const chassisMaterial = new THREE.MeshPhongMaterial({ color: 0x2a2a2a });
        const chassis = new THREE.Mesh(chassisGeometry, chassisMaterial);
        chassis.castShadow = true;
        group.add(chassis);

        // Front panel
        const frontGeometry = new THREE.BoxGeometry(1.7, 0.7, 0.1);
        const frontMaterial = new THREE.MeshPhongMaterial({ color: 0x1a1a1a });
        const front = new THREE.Mesh(frontGeometry, frontMaterial);
        front.position.set(0, 0, 1.05);
        group.add(front);

        // LED indicators
        const ledGeometry = new THREE.SphereGeometry(0.02, 8, 8);
        const ledMaterial = new THREE.MeshPhongMaterial({ 
            color: 0x00ff00,
            emissive: 0x004400
        });
        
        for (let i = 0; i < 4; i++) {
            const led = new THREE.Mesh(ledGeometry, ledMaterial);
            led.position.set(-0.6 + i * 0.4, 0.2, 1.1);
            group.add(led);
        }

        // IBM logo
        const logoGeometry = new THREE.PlaneGeometry(0.3, 0.1);
        const logoMaterial = new THREE.MeshPhongMaterial({ color: 0x0066cc });
        const logo = new THREE.Mesh(logoGeometry, logoMaterial);
        logo.position.set(0, -0.2, 1.1);
        group.add(logo);

        group.position.set(3, 0.7, 0);
        group.userData = { 
            type: 'ibm_power8',
            name: 'IBM POWER8',
            specs: 'POWER8 • 8-Core • 64GB RAM',
            minerId: 'power8_001'
        };
        
        this.scene.add(group);
        this.exhibits.push(group);
    }

    setupEventListeners() {
        // Keyboard controls
        document.addEventListener('keydown', (event) => {
            this.keys[event.code] = true;
        });
        
        document.addEventListener('keyup', (event) => {
            this.keys[event.code] = false;
        });

        // Mouse/touch controls
        if (this.isMobile) {
            this.setupTouchControls();
        } else {
            this.setupMouseControls();
        }

        // Window resize
        window.addEventListener('resize', () => {
            this.camera.aspect = window.innerWidth / window.innerHeight;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(window.innerWidth, window.innerHeight);
        });

        // Click/tap interaction
        this.renderer.domElement.addEventListener('click', (event) => {
            this.handleClick(event);
        });
    }

    setupMouseControls() {
        let isMouseDown = false;
        let previousMousePosition = { x: 0, y: 0 };

        this.renderer.domElement.addEventListener('mousedown', (event) => {
            isMouseDown = true;
            previousMousePosition = { x: event.clientX, y: event.clientY };
        });

        this.renderer.domElement.addEventListener('mouseup', () => {
            isMouseDown = false;
        });

        this.renderer.domElement.addEventListener('mousemove', (event) => {
            if (isMouseDown) {
                const deltaMove = {
                    x: event.clientX - previousMousePosition.x,
                    y: event.clientY - previousMousePosition.y
                };

                this.camera.rotation.y -= deltaMove.x * 0.005;
                this.camera.rotation.x -= deltaMove.y * 0.005;
                this.camera.rotation.x = Math.max(-Math.PI/2, Math.min(Math.PI/2, this.camera.rotation.x));

                previousMousePosition = { x: event.clientX, y: event.clientY };
            }
        });
    }

    setupTouchControls() {
        this.renderer.domElement.addEventListener('touchstart', (event) => {
            if (event.touches.length === 1) {
                this.touchStart = {
                    x: event.touches[0].clientX,
                    y: event.touches[0].clientY
                };
            }
        });

        this.renderer.domElement.addEventListener('touchmove', (event) => {
            event.preventDefault();
            if (event.touches.length === 1) {
                const deltaMove = {
                    x: event.touches[0].clientX - this.touchStart.x,
                    y: event.touches[0].clientY - this.touchStart.y
                };

                this.camera.rotation.y -= deltaMove.x * 0.005;
                this.camera.rotation.x -= deltaMove.y * 0.005;
                this.camera.rotation.x = Math.max(-Math.PI/2, Math.min(Math.PI/2, this.camera.rotation.x));

                this.touchStart = {
                    x: event.touches[0].clientX,
                    y: event.touches[0].clientY
                };
            }
        });

        // Virtual D-pad for mobile
        this.createVirtualControls();
    }

    createVirtualControls() {
        const controlsDiv = document.createElement('div');
        controlsDiv.id = 'virtual-controls';
        controlsDiv.style.cssText = `
            position: fixed;
            bottom: 20px;
            left: 20px;
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            grid-template-rows: 1fr 1fr 1fr;
            gap: 10px;
            width: 120px;
            height: 120px;
            z-index: 1000;
        `;

        const buttons = [
            { text: '↖', keys: ['KeyW', 'KeyA'] },
            { text: '↑', keys: ['KeyW'] },
            { text: '↗', keys: ['KeyW', 'KeyD'] },
            { text: '←', keys: ['KeyA'] },
            { text: '⊙', keys: [] },
            { text: '→', keys: ['KeyD'] },
            { text: '↙', keys: ['KeyS', 'KeyA'] },
            { text: '↓', keys: ['KeyS'] },
            { text: '↘', keys: ['KeyS', 'KeyD'] }
        ];

        buttons.forEach((btn, index) => {
            if (btn.keys.length === 0) return; // Skip center button
            
            const button = document.createElement('button');
            button.textContent = btn.text;
            button.style.cssText = `
                background: rgba(255,255,255,0.2);
                border: 1px solid rgba(255,255,255,0.3);
                color: white;
                font-size: 16px;
                border-radius: 5px;
                touch-action: manipulation;
            `;

            button.addEventListener('touchstart', (e) => {
                e.preventDefault();
                btn.keys.forEach(key => this.keys[key] = true);
            });

            button.addEventListener('touchend', (e) => {
                e.preventDefault();
                btn.keys.forEach(key => this.keys[key] = false);
            });

            controlsDiv.appendChild(button);
        });

        document.body.appendChild(controlsDiv);
    }

    handleClick(event) {
        this.mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
        this.mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

        this.raycaster.setFromCamera(this.mouse, this.camera);
        const intersects = this.raycaster.intersectObjects(this.exhibits, true);

        if (intersects.length > 0) {
            const exhibit = intersects[0].object.parent || intersects[0].object;
            if (exhibit.userData.type) {
                this.showExhibitInfo(exhibit.userData);
            }
        }
    }

    showExhibitInfo(exhibitData) {
        // Remove existing info panel
        const existing = document.getElementById('exhibit-info');
        if (existing) existing.remove();

        const infoPanel = document.createElement('div');
        infoPanel.id = 'exhibit-info';
        infoPanel.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(0, 0, 0, 0.9);
            color: white;
            padding: 30px;
            border-radius: 10px;
            border: 1px solid #333;
            max-width: 400px;
            z-index: 1000;
            font-family: 'Courier New', monospace;
        `;

        // Get live data for this exhibit
        this.fetchExhibitData(exhibitData.minerId).then(data => {
            infoPanel.innerHTML = `
                <h2 style="margin-top: 0; color: #00ff00;">${exhibitData.name}</h2>
                <p style="color: #ccc;">${exhibitData.specs}</p>
                <hr style="border-color: #333;">
                <h3>Mining Stats:</h3>
                <div style="font-family: monospace; font-size: 14px;">
                    <div>Hashrate: <span style="color: #00ff00;">${data.hashrate || 'N/A'}</span></div>
                    <div>Power Draw: <span style="color: #ffaa00;">${data.power || 'N/A'}</span></div>
                    <div>Temperature: <span style="color: #ff6600;">${data.temperature || 'N/A'}</span></div>
                    <div>Uptime: <span style="color: #0099ff;">${data.uptime || 'N/A'}</span></div>
                    <div>Blocks Found: <span style="color: #ff00ff;">${data.blocks || '0'}</span></div>
                </div>
                <button onclick="document.getElementById('exhibit-info').remove()" 
                        style="margin-top: 20px; padding: 10px 20px; background: #333; color: white; border: none; border-radius: 5px; cursor: pointer;">
                    Close
                </button>
            `;
        });

        document.body.appendChild(infoPanel);
    }

    async fetchExhibitData(minerId) {
        try {
            const response = await fetch(`/api/miner/${minerId}/stats`);
            if (response.ok) {
                return await response.json();
            }
        } catch (error) {
            console.warn('Failed to fetch exhibit data:', error);
        }
        
        // Return mock data if API fails
        return {
            hashrate: Math.floor(Math.random() * 1000) + 'H/s',
            power: Math.floor(Math.random() * 200) + 'W',
            temperature: Math.floor(Math.random() * 40 + 40) + '°C',
            uptime: Math.floor(Math.random() * 24) + 'h ' + Math.floor(Math.random() * 60) + 'm',
            blocks: Math.floor(Math.random() * 10)
        };
    }

    updateExhibitData() {
        const now = Date.now();
        if (now - this.lastApiUpdate > this.apiUpdateInterval) {
            this.exhibits.forEach(exhibit => {
                if (exhibit.userData.minerId) {
                    this.fetchExhibitData(exhibit.userData.minerId).then(data => {
                        exhibit.userData.liveData = data;
                    });
                }
            });
            this.lastApiUpdate = now;
        }
    }

    handleMovement() {
        const moveVector = new THREE.Vector3();
        
        if (this.keys['KeyW']) moveVector.z -= this.moveSpeed;
        if (this.keys['KeyS']) moveVector.z += this.moveSpeed;
        if (this.keys['KeyA']) moveVector.x -= this.moveSpeed;
        if (this.keys['KeyD']) moveVector.x += this.moveSpeed;

        // Apply camera rotation to movement
        moveVector.applyQuaternion(this.camera.quaternion);
        this.camera.position.add(moveVector);

        // Keep camera above ground
        this.camera.position.y = Math.max(1, this.camera.position.y);
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        
        this.handleMovement();
        this.updateExhibitData();
        
        // Animate LEDs on IBM POWER8
        const time = Date.now() * 0.001;
        this.exhibits.forEach(exhibit => {
            if (exhibit.userData.type === 'ibm_power8') {
                exhibit.children.forEach(child => {
                    if (child.material && child.material.emissive) {
                        const intensity = Math.sin(time * 3 + child.position.x * 10) * 0.5 + 0.5;
                        child.material.emissive.setHex(intensity > 0.5 ? 0x004400 : 0x001100);
                    }
                });
            }
        });
        
        this.renderer.render(this.scene, this.camera);
    }
}

// Initialize museum when page loads
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('museum-container')) {
        new Museum3D();
    }
});