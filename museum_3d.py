// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
from flask import Flask, render_template_string, jsonify, request
from datetime import datetime

app = Flask(__name__)
DB_PATH = 'rustchain.db'

@app.route('/museum')
def museum_3d():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>3D Vintage Hardware Museum</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <style>
        body { margin: 0; overflow: hidden; background: #000; }
        canvas { display: block; }
        #info { position: absolute; top: 10px; left: 10px; color: white; font-family: Arial; z-index: 100; }
        #controls { position: absolute; bottom: 10px; left: 10px; color: white; font-family: Arial; font-size: 12px; }
        #stats-panel { position: absolute; top: 10px; right: 10px; width: 300px; background: rgba(0,0,0,0.8); color: white; padding: 15px; border-radius: 5px; display: none; }
        .loading { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: white; font-family: Arial; }
    </style>
</head>
<body>
    <div id="info">
        <h3>RustChain 3D Hardware Museum</h3>
        <p>Click on exhibits to view mining stats</p>
    </div>
    <div id="controls">
        WASD: Move | Mouse: Look | Click: Interact | Mobile: Touch to move
    </div>
    <div id="stats-panel">
        <h4 id="exhibit-name">Hardware Info</h4>
        <div id="exhibit-stats"></div>
        <button onclick="closeStats()" style="margin-top: 10px; padding: 5px 10px;">Close</button>
    </div>
    <div class="loading" id="loading">Loading Museum...</div>

    <script>
        let scene, camera, renderer, controls;
        let exhibits = [];
        let moveForward = false, moveBackward = false, moveLeft = false, moveRight = false;
        let velocity = new THREE.Vector3();
        let direction = new THREE.Vector3();
        let mouse = new THREE.Vector2();
        let raycaster = new THREE.Raycaster();
        let touchStartX = 0, touchStartY = 0;

        const exhibitData = {
            'powerbook_g4': {
                name: 'PowerBook G4 (2005)',
                position: [-5, 0, 0],
                color: 0x808080,
                api_endpoint: 'powerbook_g4'
            },
            'ibm_power8': {
                name: 'IBM POWER8 Server',
                position: [5, 0, 0], 
                color: 0x000080,
                api_endpoint: 'ibm_power8'
            },
            'sun_sparc': {
                name: 'Sun SPARC Station',
                position: [0, 0, -5],
                color: 0xff6600,
                api_endpoint: 'sun_sparc'
            },
            'sgi_octane': {
                name: 'SGI Octane',
                position: [-3, 0, 5],
                color: 0x4b0082,
                api_endpoint: 'sgi_octane'
            },
            'dec_alpha': {
                name: 'DEC Alpha Workstation',
                position: [3, 0, 5],
                color: 0x800000,
                api_endpoint: 'dec_alpha'
            }
        };

        function init() {
            scene = new THREE.Scene();
            scene.fog = new THREE.Fog(0x000000, 0, 750);

            camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 1, 1000);
            camera.position.set(0, 5, 10);

            renderer = new THREE.WebGLRenderer();
            renderer.setSize(window.innerWidth, window.innerHeight);
            renderer.setClearColor(0x000000);
            document.body.appendChild(renderer.domElement);

            // Lighting
            const ambientLight = new THREE.AmbientLight(0x404040, 0.4);
            scene.add(ambientLight);

            const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
            directionalLight.position.set(10, 10, 5);
            scene.add(directionalLight);

            // Floor
            const floorGeometry = new THREE.PlaneGeometry(100, 100);
            const floorMaterial = new THREE.MeshLambertMaterial({ color: 0x333333 });
            const floor = new THREE.Mesh(floorGeometry, floorMaterial);
            floor.rotation.x = -Math.PI / 2;
            scene.add(floor);

            // Grid
            const gridHelper = new THREE.GridHelper(100, 100, 0x444444, 0x222222);
            scene.add(gridHelper);

            // Create exhibits
            Object.keys(exhibitData).forEach(key => {
                const data = exhibitData[key];
                const geometry = new THREE.BoxGeometry(2, 1.5, 1);
                const material = new THREE.MeshLambertMaterial({ color: data.color });
                const exhibit = new THREE.Mesh(geometry, material);
                exhibit.position.set(...data.position);
                exhibit.position.y = 0.75;
                exhibit.userData = { type: 'exhibit', id: key, name: data.name };
                
                // Add glow effect
                const glowGeometry = new THREE.BoxGeometry(2.2, 1.7, 1.2);
                const glowMaterial = new THREE.MeshBasicMaterial({
                    color: data.color,
                    transparent: true,
                    opacity: 0.3
                });
                const glow = new THREE.Mesh(glowGeometry, glowMaterial);
                glow.position.copy(exhibit.position);
                scene.add(glow);
                
                scene.add(exhibit);
                exhibits.push(exhibit);

                // Label
                const loader = new THREE.FontLoader();
                createTextLabel(data.name, exhibit.position.clone().add(new THREE.Vector3(0, 2, 0)));
            });

            // Event listeners
            document.addEventListener('keydown', onKeyDown);
            document.addEventListener('keyup', onKeyUp);
            document.addEventListener('click', onMouseClick);
            document.addEventListener('mousemove', onMouseMove);
            
            // Touch events for mobile
            document.addEventListener('touchstart', onTouchStart, { passive: false });
            document.addEventListener('touchmove', onTouchMove, { passive: false });
            document.addEventListener('touchend', onTouchEnd, { passive: false });

            document.getElementById('loading').style.display = 'none';
        }

        function createTextLabel(text, position) {
            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');
            context.font = '48px Arial';
            context.fillStyle = 'white';
            context.fillText(text, 0, 48);

            const texture = new THREE.CanvasTexture(canvas);
            const spriteMaterial = new THREE.SpriteMaterial({ map: texture });
            const sprite = new THREE.Sprite(spriteMaterial);
            sprite.position.copy(position);
            sprite.scale.set(4, 2, 1);
            scene.add(sprite);
        }

        function onKeyDown(event) {
            switch(event.code) {
                case 'KeyW': moveForward = true; break;
                case 'KeyS': moveBackward = true; break;
                case 'KeyA': moveLeft = true; break;
                case 'KeyD': moveRight = true; break;
            }
        }

        function onKeyUp(event) {
            switch(event.code) {
                case 'KeyW': moveForward = false; break;
                case 'KeyS': moveBackward = false; break;
                case 'KeyA': moveLeft = false; break;
                case 'KeyD': moveRight = false; break;
            }
        }

        function onMouseClick(event) {
            mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
            mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

            raycaster.setFromCamera(mouse, camera);
            const intersects = raycaster.intersectObjects(exhibits);

            if (intersects.length > 0) {
                const clicked = intersects[0].object;
                if (clicked.userData.type === 'exhibit') {
                    showExhibitStats(clicked.userData.id, clicked.userData.name);
                }
            }
        }

        function onMouseMove(event) {
            const movementX = event.movementX || 0;
            const movementY = event.movementY || 0;

            camera.rotation.y -= movementX * 0.002;
            camera.rotation.x -= movementY * 0.002;
            camera.rotation.x = Math.max(-Math.PI/2, Math.min(Math.PI/2, camera.rotation.x));
        }

        function onTouchStart(event) {
            event.preventDefault();
            touchStartX = event.touches[0].clientX;
            touchStartY = event.touches[0].clientY;
        }

        function onTouchMove(event) {
            event.preventDefault();
            if (event.touches.length === 1) {
                const deltaX = event.touches[0].clientX - touchStartX;
                const deltaY = event.touches[0].clientY - touchStartY;
                
                camera.rotation.y -= deltaX * 0.005;
                camera.rotation.x -= deltaY * 0.005;
                camera.rotation.x = Math.max(-Math.PI/2, Math.min(Math.PI/2, camera.rotation.x));
                
                touchStartX = event.touches[0].clientX;
                touchStartY = event.touches[0].clientY;
            }
        }

        function onTouchEnd(event) {
            event.preventDefault();
            if (event.changedTouches.length === 1) {
                mouse.x = (event.changedTouches[0].clientX / window.innerWidth) * 2 - 1;
                mouse.y = -(event.changedTouches[0].clientY / window.innerHeight) * 2 + 1;
                
                raycaster.setFromCamera(mouse, camera);
                const intersects = raycaster.intersectObjects(exhibits);
                
                if (intersects.length > 0) {
                    const clicked = intersects[0].object;
                    if (clicked.userData.type === 'exhibit') {
                        showExhibitStats(clicked.userData.id, clicked.userData.name);
                    }
                }
            }
        }

        function showExhibitStats(exhibitId, exhibitName) {
            document.getElementById('exhibit-name').textContent = exhibitName;
            document.getElementById('stats-panel').style.display = 'block';
            document.getElementById('exhibit-stats').innerHTML = '<p>Loading stats...</p>';

            fetch(`/api/miner_stats/${exhibitId}`)
                .then(response => response.json())
                .then(data => {
                    let html = `
                        <p><strong>Hash Rate:</strong> ${data.hash_rate || 'N/A'}</p>
                        <p><strong>Temperature:</strong> ${data.temperature || 'N/A'}°C</p>
                        <p><strong>Power Usage:</strong> ${data.power_usage || 'N/A'}W</p>
                        <p><strong>Uptime:</strong> ${data.uptime || 'N/A'}</p>
                        <p><strong>Blocks Mined:</strong> ${data.blocks_mined || 0}</p>
                        <p><strong>Status:</strong> <span style="color: ${data.status === 'active' ? 'green' : 'red'}">${data.status || 'Unknown'}</span></p>
                    `;
                    if (data.last_block_time) {
                        html += `<p><strong>Last Block:</strong> ${new Date(data.last_block_time).toLocaleString()}</p>`;
                    }
                    document.getElementById('exhibit-stats').innerHTML = html;
                })
                .catch(error => {
                    document.getElementById('exhibit-stats').innerHTML = '<p>Error loading stats</p>';
                });
        }

        function closeStats() {
            document.getElementById('stats-panel').style.display = 'none';
        }

        function animate() {
            requestAnimationFrame(animate);

            direction.x = Number(moveRight) - Number(moveLeft);
            direction.z = Number(moveBackward) - Number(moveForward);
            direction.normalize();

            if (moveForward || moveBackward) velocity.z -= direction.z * 400.0 * 0.016;
            if (moveLeft || moveRight) velocity.x -= direction.x * 400.0 * 0.016;

            velocity.x *= 0.9;
            velocity.z *= 0.9;

            camera.translateX(velocity.x * 0.016);
            camera.translateZ(velocity.z * 0.016);

            if (camera.position.y < 2) camera.position.y = 2;

            renderer.render(scene, camera);
        }

        function onWindowResize() {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        }

        window.addEventListener('resize', onWindowResize);
        window.addEventListener('click', () => {
            document.body.requestPointerLock();
        });

        init();
        animate();
    </script>
</body>
</html>
    ''')

@app.route('/api/miner_stats/<exhibit_id>')
def miner_stats_api(exhibit_id):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Get miner stats for exhibit
            cursor.execute('''
                SELECT hash_rate, temperature, power_usage, uptime, blocks_mined, status, last_block_time
                FROM vintage_miners 
                WHERE exhibit_id = ?
            ''', (exhibit_id,))
            
            result = cursor.fetchone()
            
            if result:
                return jsonify({
                    'hash_rate': f"{result[0]} MH/s" if result[0] else None,
                    'temperature': result[1],
                    'power_usage': result[2],
                    'uptime': f"{result[3]} hours" if result[3] else None,
                    'blocks_mined': result[4],
                    'status': result[5],
                    'last_block_time': result[6]
                })
            else:
                # Return mock data for demo
                mock_data = {
                    'powerbook_g4': {
                        'hash_rate': '12.5 KH/s',
                        'temperature': 68,
                        'power_usage': 85,
                        'uptime': '72',
                        'blocks_mined': 3,
                        'status': 'active',
                        'last_block_time': datetime.now().isoformat()
                    },
                    'ibm_power8': {
                        'hash_rate': '2.1 GH/s', 
                        'temperature': 45,
                        'power_usage': 350,
                        'uptime': '168',
                        'blocks_mined': 47,
                        'status': 'active',
                        'last_block_time': datetime.now().isoformat()
                    },
                    'sun_sparc': {
                        'hash_rate': '850 KH/s',
                        'temperature': 52,
                        'power_usage': 120,
                        'uptime': '96',
                        'blocks_mined': 12,
                        'status': 'maintenance',
                        'last_block_time': datetime.now().isoformat()
                    },
                    'sgi_octane': {
                        'hash_rate': '1.2 MH/s',
                        'temperature': 41,
                        'power_usage': 200,
                        'uptime': '240',
                        'blocks_mined': 28,
                        'status': 'active',
                        'last_block_time': datetime.now().isoformat()
                    },
                    'dec_alpha': {
                        'hash_rate': '950 KH/s',
                        'temperature': 39,
                        'power_usage': 175,
                        'uptime': '144',
                        'blocks_mined': 19,
                        'status': 'offline',
                        'last_block_time': None
                    }
                }
                
                return jsonify(mock_data.get(exhibit_id, {
                    'hash_rate': None,
                    'temperature': None,
                    'power_usage': None,
                    'uptime': None,
                    'blocks_mined': 0,
                    'status': 'unknown',
                    'last_block_time': None
                }))
                
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def init_museum_db():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vintage_miners (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exhibit_id TEXT UNIQUE,
                    name TEXT,
                    hash_rate REAL,
                    temperature INTEGER,
                    power_usage INTEGER,
                    uptime INTEGER,
                    blocks_mined INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'offline',
                    last_block_time TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
    except Exception as e:
        print(f"Database init error: {e}")

if __name__ == '__main__':
    init_museum_db()
    app.run(debug=True)