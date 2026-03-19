// SPDX-License-Identifier: MIT

import * as THREE from 'https://unpkg.com/three@0.155.0/build/three.module.js';
import { OrbitControls } from 'https://unpkg.com/three@0.155.0/examples/jsm/controls/OrbitControls.js';

class VintageHardwareMuseum {
    constructor(container) {
        this.container = container;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.exhibits = [];
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();
        this.keys = {};
        this.clock = new THREE.Clock();
        this.selectedExhibit = null;
        
        this.init();
        this.createExhibits();
        this.setupEventListeners();
        this.animate();
    }

    init() {
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x1a1a2e);
        
        this.camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
        this.camera.position.set(0, 5, 10);
        
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        this.container.appendChild(this.renderer.domElement);
        
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.1;
        this.controls.maxPolarAngle = Math.PI / 2;
        
        this.setupLighting();
        this.createFloor();
    }

    setupLighting() {
        const ambientLight = new THREE.AmbientLight(0x404040, 0.4);
        this.scene.add(ambientLight);
        
        const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
        directionalLight.position.set(-1, 1, 1);
        directionalLight.castShadow = true;
        directionalLight.shadow.mapSize.width = 2048;
        directionalLight.shadow.mapSize.height = 2048;
        this.scene.add(directionalLight);
        
        const spotLight = new THREE.SpotLight(0x16213e, 0.8);
        spotLight.position.set(0, 10, 0);
        spotLight.castShadow = true;
        this.scene.add(spotLight);
    }

    createFloor() {
        const floorGeometry = new THREE.PlaneGeometry(50, 50);
        const floorMaterial = new THREE.MeshLambertMaterial({ 
            color: 0x0f3460,
            transparent: true,
            opacity: 0.8
        });
        const floor = new THREE.Mesh(floorGeometry, floorMaterial);
        floor.rotation.x = -Math.PI / 2;
        floor.receiveShadow = true;
        this.scene.add(floor);
    }

    createExhibits() {
        const exhibits = [
            { name: 'PowerBook G4', position: [-8, 1, -5], minerId: 'pb_g4_001' },
            { name: 'IBM POWER8', position: [0, 1, -8], minerId: 'ibm_p8_001' },
            { name: 'ThinkPad T60', position: [8, 1, -5], minerId: 'tp_t60_001' },
            { name: 'PowerMac G5', position: [-8, 1, 5], minerId: 'pm_g5_001' },
            { name: 'Sun SPARC', position: [0, 1, 8], minerId: 'sun_sparc_001' },
            { name: 'SGI Octane', position: [8, 1, 5], minerId: 'sgi_oct_001' }
        ];

        exhibits.forEach(exhibitData => {
            const exhibit = this.createHardwareModel(exhibitData);
            this.scene.add(exhibit);
            this.exhibits.push(exhibit);
        });
    }

    createHardwareModel(data) {
        const group = new THREE.Group();
        
        const baseGeometry = new THREE.BoxGeometry(2, 0.3, 1.5);
        const baseMaterial = new THREE.MeshPhongMaterial({ 
            color: 0x2c3e50,
            shininess: 30
        });
        const base = new THREE.Mesh(baseGeometry, baseMaterial);
        base.castShadow = true;
        base.receiveShadow = true;
        
        const screenGeometry = new THREE.BoxGeometry(1.8, 1.2, 0.1);
        const screenMaterial = new THREE.MeshPhongMaterial({ color: 0x1a1a1a });
        const screen = new THREE.Mesh(screenGeometry, screenMaterial);
        screen.position.set(0, 0.9, 0.7);
        screen.castShadow = true;
        
        const glowGeometry = new THREE.PlaneGeometry(1.6, 1);
        const glowMaterial = new THREE.MeshBasicMaterial({ 
            color: 0x00ff88,
            transparent: true,
            opacity: 0.3
        });
        const glow = new THREE.Mesh(glowGeometry, glowMaterial);
        glow.position.set(0, 0.9, 0.71);
        
        group.add(base);
        group.add(screen);
        group.add(glow);
        
        group.position.set(...data.position);
        group.userData = {
            name: data.name,
            minerId: data.minerId,
            isExhibit: true
        };
        
        const labelGeometry = new THREE.PlaneGeometry(3, 0.5);
        const labelTexture = this.createTextTexture(data.name);
        const labelMaterial = new THREE.MeshBasicMaterial({ 
            map: labelTexture,
            transparent: true
        });
        const label = new THREE.Mesh(labelGeometry, labelMaterial);
        label.position.set(0, 2.5, 0);
        label.lookAt(this.camera.position);
        group.add(label);
        
        return group;
    }

    createTextTexture(text) {
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 128;
        const context = canvas.getContext('2d');
        
        context.fillStyle = 'rgba(0, 0, 0, 0.8)';
        context.fillRect(0, 0, canvas.width, canvas.height);
        
        context.fillStyle = '#ffffff';
        context.font = '32px Arial';
        context.textAlign = 'center';
        context.fillText(text, canvas.width / 2, canvas.height / 2);
        
        const texture = new THREE.CanvasTexture(canvas);
        return texture;
    }

    setupEventListeners() {
        window.addEventListener('resize', () => this.onWindowResize());
        window.addEventListener('keydown', (e) => this.onKeyDown(e));
        window.addEventListener('keyup', (e) => this.onKeyUp(e));
        this.renderer.domElement.addEventListener('click', (e) => this.onMouseClick(e));
        this.renderer.domElement.addEventListener('touchstart', (e) => this.onTouchStart(e));
    }

    onWindowResize() {
        this.camera.aspect = window.innerWidth / window.innerHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(window.innerWidth, window.innerHeight);
    }

    onKeyDown(event) {
        this.keys[event.code] = true;
    }

    onKeyUp(event) {
        this.keys[event.code] = false;
    }

    onMouseClick(event) {
        this.mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
        this.mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;
        
        this.raycaster.setFromCamera(this.mouse, this.camera);
        const intersects = this.raycaster.intersectObjects(this.scene.children, true);
        
        if (intersects.length > 0) {
            const object = intersects[0].object;
            let exhibit = object;
            while (exhibit.parent && !exhibit.userData.isExhibit) {
                exhibit = exhibit.parent;
            }
            
            if (exhibit.userData && exhibit.userData.isExhibit) {
                this.selectExhibit(exhibit);
            }
        }
    }

    onTouchStart(event) {
        if (event.touches.length === 1) {
            const touch = event.touches[0];
            this.mouse.x = (touch.clientX / window.innerWidth) * 2 - 1;
            this.mouse.y = -(touch.clientY / window.innerHeight) * 2 + 1;
            
            this.raycaster.setFromCamera(this.mouse, this.camera);
            const intersects = this.raycaster.intersectObjects(this.scene.children, true);
            
            if (intersects.length > 0) {
                const object = intersects[0].object;
                let exhibit = object;
                while (exhibit.parent && !exhibit.userData.isExhibit) {
                    exhibit = exhibit.parent;
                }
                
                if (exhibit.userData && exhibit.userData.isExhibit) {
                    this.selectExhibit(exhibit);
                }
            }
        }
    }

    async selectExhibit(exhibit) {
        if (this.selectedExhibit) {
            this.selectedExhibit.scale.set(1, 1, 1);
        }
        
        this.selectedExhibit = exhibit;
        exhibit.scale.set(1.1, 1.1, 1.1);
        
        await this.loadMinerData(exhibit.userData.minerId);
        this.showExhibitInfo(exhibit);
    }

    async loadMinerData(minerId) {
        try {
            const response = await fetch(`/api/miner/${minerId}`);
            if (response.ok) {
                const data = await response.json();
                this.updateExhibitDisplay(data);
            }
        } catch (error) {
            console.log('Failed to load miner data:', error);
        }
    }

    updateExhibitDisplay(minerData) {
        const infoPanel = document.getElementById('exhibit-info');
        if (infoPanel) {
            infoPanel.innerHTML = `
                <h3>${minerData.name || 'Unknown Miner'}</h3>
                <div class="stats">
                    <div>Hashrate: ${minerData.hashrate || '0'} MH/s</div>
                    <div>Temperature: ${minerData.temperature || 'N/A'}°C</div>
                    <div>Power: ${minerData.power || 'N/A'}W</div>
                    <div>Status: ${minerData.status || 'Offline'}</div>
                    <div>Uptime: ${minerData.uptime || '0h'}</div>
                </div>
            `;
            infoPanel.style.display = 'block';
        }
    }

    showExhibitInfo(exhibit) {
        let infoPanel = document.getElementById('exhibit-info');
        if (!infoPanel) {
            infoPanel = document.createElement('div');
            infoPanel.id = 'exhibit-info';
            infoPanel.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                width: 300px;
                background: rgba(0, 0, 0, 0.8);
                color: white;
                padding: 20px;
                border-radius: 10px;
                font-family: 'Courier New', monospace;
                z-index: 1000;
                border: 2px solid #00ff88;
            `;
            document.body.appendChild(infoPanel);
            
            const closeBtn = document.createElement('button');
            closeBtn.innerHTML = '×';
            closeBtn.style.cssText = `
                position: absolute;
                top: 5px;
                right: 10px;
                background: none;
                border: none;
                color: white;
                font-size: 20px;
                cursor: pointer;
            `;
            closeBtn.onclick = () => {
                infoPanel.style.display = 'none';
                if (this.selectedExhibit) {
                    this.selectedExhibit.scale.set(1, 1, 1);
                    this.selectedExhibit = null;
                }
            };
            infoPanel.appendChild(closeBtn);
        }
    }

    handleMovement() {
        const speed = 0.1;
        const direction = new THREE.Vector3();
        
        if (this.keys['KeyW']) direction.z -= speed;
        if (this.keys['KeyS']) direction.z += speed;
        if (this.keys['KeyA']) direction.x -= speed;
        if (this.keys['KeyD']) direction.x += speed;
        
        if (direction.length() > 0) {
            direction.normalize();
            direction.multiplyScalar(speed);
            direction.applyQuaternion(this.camera.quaternion);
            this.camera.position.add(direction);
        }
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        
        this.handleMovement();
        this.controls.update();
        
        this.exhibits.forEach(exhibit => {
            exhibit.rotation.y += 0.005;
        });
        
        this.renderer.render(this.scene, this.camera);
    }
}

window.VintageHardwareMuseum = VintageHardwareMuseum;

document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('museum-container') || document.body;
    new VintageHardwareMuseum(container);
});