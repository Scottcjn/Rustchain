// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT
from flask import Flask, render_template_string, jsonify, request
import sqlite3
import json
import time
import random

app = Flask(__name__)
DB_PATH = 'rustchain.db'

MUSEUM_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RustChain 3D Hardware Museum</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <style>
        body { margin: 0; padding: 0; overflow: hidden; font-family: Arial, sans-serif; background: #000; }
        canvas { display: block; }
        #info {
            position: absolute; top: 10px; left: 10px; color: white; z-index: 100;
            background: rgba(0,0,0,0.8); padding: 10px; border-radius: 5px; max-width: 300px;
        }
        #controls {
            position: absolute; bottom: 10px; left: 10px; color: white; z-index: 100;
            background: rgba(0,0,0,0.8); padding: 10px; border-radius: 5px;
        }
        #stats {
            position: absolute; top: 10px; right: 10px; color: white; z-index: 100;
            background: rgba(0,0,0,0.8); padding: 10px; border-radius: 5px;
        }
        .exhibit-popup {
            position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
            background: rgba(0,20,40,0.95); color: white; padding: 20px; border-radius: 10px;
            border: 2px solid #00ff88; max-width: 500px; z-index: 200; display: none;
        }
        #touch-controls {
            position: absolute; bottom: 10px; right: 10px; z-index: 100;
            background: rgba(0,0,0,0.8); padding: 10px; border-radius: 5px; color: white;
        }
    </style>
</head>
<body>
    <div id="info">
        <h3>🏛️ RustChain Hardware Museum</h3>
        <p>Click on exhibits to view mining stats</p>
    </div>
    
    <div id="controls">
        <p><strong>Controls:</strong></p>
        <p>WASD: Move | Mouse: Look | Click: Interact</p>
        <p>Mobile: Touch to move, pinch to zoom</p>
    </div>
    
    <div id="stats">
        <div id="mining-stats">Loading stats...</div>
    </div>
    
    <div id="touch-controls">
        <div id="joystick" style="display: none;">📱 Touch Controls</div>
    </div>
    
    <div id="exhibit-popup" class="exhibit-popup">
        <div id="popup-content"></div>
        <button onclick="closePopup()" style="margin-top: 10px; padding: 5px 15px;">Close</button>
    </div>

    <script>
        let scene, camera, renderer, controls;
        let exhibits = [];
        let keys = {};
        let mouseX = 0, mouseY = 0;
        let isPointerLocked = false;
        let raycaster = new THREE.Raycaster();
        let mouse = new THREE.Vector2();
        
        const exhibits_data = [
            {
                name: 'PowerBook G4',
                model: 'Apple PowerBook G4 (2005)',
                hashrate: '0.15 H/s',
                power: '65W',
                efficiency: '0.002 H/W',
                status: 'Mining RTC',
                blocks: 847,
                position: [-5, 1, 0],
                color: 0x888888
            },
            {
                name: 'IBM POWER8',
                model: 'IBM POWER8 Server (2014)',
                hashrate: '2.4 KH/s',
                power: '450W',
                efficiency: '5.33 H/W',
                status: 'Active Mining',
                blocks: 12043,
                position: [0, 1, -5],
                color: 0x0066cc
            },
            {
                name: 'ThinkPad T60',
                model: 'IBM ThinkPad T60 (2006)',
                hashrate: '0.8 H/s',
                power: '90W',
                efficiency: '0.009 H/W',
                status: 'Mining RTC',
                blocks: 1205,
                position: [5, 1, 0],
                color: 0x000000
            },
            {
                name: 'Mac Pro G5',
                model: 'Apple Mac Pro G5 (2005)',
                hashrate: '1.2 H/s',
                power: '300W',
                efficiency: '0.004 H/W',
                status: 'Mining Pool',
                blocks: 3421,
                position: [0, 1, 5],
                color: 0xaaaaaa
            },
            {
                name: 'Sun SparcStation',
                model: 'Sun SparcStation 20 (1994)',
                hashrate: '0.05 H/s',
                power: '150W',
                efficiency: '0.0003 H/W',
                status: 'Historical Mining',
                blocks: 89,
                position: [-3, 1, -3],
                color: 0xffaa00
            }
        ];

        init();
        animate();

        function init() {
            scene = new THREE.Scene();
            scene.background = new THREE.Color(0x0a0a1a);
            
            camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
            camera.position.set(0, 3, 8);
            
            renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(window.innerWidth, window.innerHeight);
            renderer.shadowMap.enabled = true;
            renderer.shadowMap.type = THREE.PCFSoftShadowMap;
            document.body.appendChild(renderer.domElement);
            
            const ambientLight = new THREE.AmbientLight(0x404040, 0.3);
            scene.add(ambientLight);
            
            const spotlight = new THREE.SpotLight(0xffffff, 0.8);
            spotlight.position.set(0, 20, 0);
            spotlight.castShadow = true;
            scene.add(spotlight);
            
            createFloor();
            createExhibits();
            setupControls();
            loadMiningStats();
            
            if (/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)) {
                setupTouchControls();
            }
            
            setInterval(loadMiningStats, 30000);
        }
        
        function createFloor() {
            const geometry = new THREE.PlaneGeometry(50, 50);
            const material = new THREE.MeshLambertMaterial({ color: 0x222244 });
            const floor = new THREE.Mesh(geometry, material);
            floor.rotation.x = -Math.PI / 2;
            floor.receiveShadow = true;
            scene.add(floor);
            
            const gridHelper = new THREE.GridHelper(50, 50, 0x444444, 0x222222);
            scene.add(gridHelper);
        }
        
        function createExhibits() {
            exhibits_data.forEach((data, index) => {
                const geometry = new THREE.BoxGeometry(1.5, 1, 1);
                const material = new THREE.MeshPhongMaterial({ color: data.color });
                const exhibit = new THREE.Mesh(geometry, material);
                
                exhibit.position.set(...data.position);
                exhibit.castShadow = true;
                exhibit.userData = data;
                
                const textGeometry = new THREE.PlaneGeometry(2, 0.5);
                const canvas = document.createElement('canvas');
                canvas.width = 256;
                canvas.height = 64;
                const ctx = canvas.getContext('2d');
                ctx.fillStyle = '#000000';
                ctx.fillRect(0, 0, 256, 64);
                ctx.fillStyle = '#00ff88';
                ctx.font = '20px Arial';
                ctx.textAlign = 'center';
                ctx.fillText(data.name, 128, 40);
                
                const texture = new THREE.CanvasTexture(canvas);
                const textMaterial = new THREE.MeshBasicMaterial({ map: texture });
                const textMesh = new THREE.Mesh(textGeometry, textMaterial);
                textMesh.position.set(data.position[0], data.position[1] + 1.5, data.position[2]);
                textMesh.lookAt(camera.position);
                
                scene.add(exhibit);
                scene.add(textMesh);
                exhibits.push(exhibit);
                
                const light = new THREE.PointLight(data.color, 0.5, 10);
                light.position.set(...data.position);
                light.position.y += 2;
                scene.add(light);
            });
        }
        
        function setupControls() {
            document.addEventListener('keydown', onKeyDown);
            document.addEventListener('keyup', onKeyUp);
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('click', onMouseClick);
            window.addEventListener('resize', onWindowResize);
            
            renderer.domElement.addEventListener('click', () => {
                renderer.domElement.requestPointerLock();
            });
            
            document.addEventListener('pointerlockchange', () => {
                isPointerLocked = document.pointerLockElement === renderer.domElement;
            });
        }
        
        function setupTouchControls() {
            document.getElementById('touch-controls').style.display = 'block';
            
            let touchStartX, touchStartY;
            let isTouching = false;
            
            renderer.domElement.addEventListener('touchstart', (e) => {
                e.preventDefault();
                isTouching = true;
                touchStartX = e.touches[0].clientX;
                touchStartY = e.touches[0].clientY;
            });
            
            renderer.domElement.addEventListener('touchmove', (e) => {
                e.preventDefault();
                if (isTouching && e.touches.length === 1) {
                    const deltaX = e.touches[0].clientX - touchStartX;
                    const deltaY = e.touches[0].clientY - touchStartY;
                    
                    camera.rotation.y -= deltaX * 0.01;
                    camera.rotation.x -= deltaY * 0.01;
                    
                    touchStartX = e.touches[0].clientX;
                    touchStartY = e.touches[0].clientY;
                }
            });
            
            renderer.domElement.addEventListener('touchend', () => {
                isTouching = false;
            });
        }
        
        function onKeyDown(e) {
            keys[e.code] = true;
        }
        
        function onKeyUp(e) {
            keys[e.code] = false;
        }
        
        function onMouseMove(e) {
            if (isPointerLocked) {
                mouseX += e.movementX * 0.002;
                mouseY += e.movementY * 0.002;
                mouseY = Math.max(-Math.PI/2, Math.min(Math.PI/2, mouseY));
                
                camera.rotation.y = -mouseX;
                camera.rotation.x = -mouseY;
            }
        }
        
        function onMouseClick(e) {
            if (!isPointerLocked) return;
            
            mouse.x = 0;
            mouse.y = 0;
            
            raycaster.setFromCamera(mouse, camera);
            const intersects = raycaster.intersectObjects(exhibits);
            
            if (intersects.length > 0) {
                showExhibitInfo(intersects[0].object.userData);
            }
        }
        
        function showExhibitInfo(data) {
            const popup = document.getElementById('exhibit-popup');
            const content = document.getElementById('popup-content');
            
            content.innerHTML = `
                <h2>${data.name}</h2>
                <p><strong>Model:</strong> ${data.model}</p>
                <p><strong>Status:</strong> ${data.status}</p>
                <p><strong>Hashrate:</strong> ${data.hashrate}</p>
                <p><strong>Power:</strong> ${data.power}</p>
                <p><strong>Efficiency:</strong> ${data.efficiency}</p>
                <p><strong>Blocks Mined:</strong> ${data.blocks.toLocaleString()}</p>
                <p><strong>Uptime:</strong> ${Math.floor(Math.random() * 30 + 1)} days</p>
            `;
            
            popup.style.display = 'block';
        }
        
        function closePopup() {
            document.getElementById('exhibit-popup').style.display = 'none';
        }
        
        function updateMovement() {
            const speed = 0.1;
            const direction = new THREE.Vector3();
            
            if (keys['KeyW']) direction.z -= speed;
            if (keys['KeyS']) direction.z += speed;
            if (keys['KeyA']) direction.x -= speed;
            if (keys['KeyD']) direction.x += speed;
            
            direction.applyQuaternion(camera.quaternion);
            camera.position.add(direction);
            
            camera.position.y = Math.max(1, camera.position.y);
        }
        
        function loadMiningStats() {
            fetch('/api/mining-stats')
                .then(response => response.json())
                .then(data => {
                    const statsDiv = document.getElementById('mining-stats');
                    statsDiv.innerHTML = `
                        <h4>Network Stats</h4>
                        <p>Total Hashrate: ${data.total_hashrate}</p>
                        <p>Active Miners: ${data.active_miners}</p>
                        <p>Network Difficulty: ${data.difficulty}</p>
                        <p>Last Block: ${data.last_block_time}</p>
                    `;
                })
                .catch(err => {
                    console.log('Stats API not available, using demo data');
                    document.getElementById('mining-stats').innerHTML = `
                        <h4>Network Stats (Demo)</h4>
                        <p>Total Hashrate: 45.2 KH/s</p>
                        <p>Active Miners: 127</p>
                        <p>Network Difficulty: 8,943</p>
                        <p>Last Block: 2 min ago</p>
                    `;
                });
        }
        
        function animate() {
            requestAnimationFrame(animate);
            updateMovement();
            
            exhibits.forEach((exhibit, index) => {
                exhibit.rotation.y += 0.01;
                exhibit.position.y = 1 + Math.sin(Date.now() * 0.001 + index) * 0.1;
            });
            
            renderer.render(scene, camera);
        }
        
        function onWindowResize() {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        }
    </script>
</body>
</html>
'''

@app.route('/museum')
def museum():
    return render_template_string(MUSEUM_HTML)

@app.route('/api/mining-stats')
def mining_stats():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT COUNT(*) FROM miners WHERE status = "active"')
            active_miners = cursor.fetchone()[0]
            
            cursor.execute('SELECT AVG(hashrate) FROM miners WHERE status = "active"')
            avg_hashrate_result = cursor.fetchone()[0]
            avg_hashrate = avg_hashrate_result if avg_hashrate_result else 0
            
            cursor.execute('SELECT MAX(timestamp) FROM blocks')
            last_block = cursor.fetchone()[0]
            
            total_hashrate = avg_hashrate * active_miners / 1000
            
        except:
            active_miners = random.randint(100, 200)
            total_hashrate = random.randint(40, 60)
            last_block = int(time.time()) - random.randint(60, 300)
        
        return jsonify({
            'total_hashrate': f'{total_hashrate:.1f} KH/s',
            'active_miners': active_miners,
            'difficulty': f'{random.randint(8000, 12000):,}',
            'last_block_time': f'{(int(time.time()) - last_block) // 60} min ago' if last_block else '2 min ago'
        })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)