// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template_string
import random
import time

app = Flask(__name__)

DB_PATH = 'rustchain.db'

MUSEUM_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>RustChain 3D Hardware Museum</title>
    <style>
        body { margin: 0; padding: 0; font-family: monospace; background: #000; color: #0f0; overflow: hidden; }
        #info { position: absolute; top: 10px; left: 10px; z-index: 100; background: rgba(0,0,0,0.8); padding: 10px; border: 1px solid #0f0; }
        #controls { position: absolute; bottom: 10px; left: 10px; z-index: 100; background: rgba(0,0,0,0.8); padding: 10px; border: 1px solid #0f0; }
        #exhibit-panel { position: absolute; top: 10px; right: 10px; z-index: 100; background: rgba(0,0,0,0.8); padding: 10px; border: 1px solid #0f0; max-width: 300px; }
        canvas { display: block; }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
</head>
<body>
    <div id="info">
        <h3>RustChain Hardware Museum</h3>
        <div>Active Miners: <span id="active-miners">0</span></div>
        <div>Total Hashrate: <span id="total-hashrate">0 H/s</span></div>
        <div>Network Difficulty: <span id="difficulty">0</span></div>
    </div>
    
    <div id="controls">
        <div>WASD: Move | Mouse: Look | Click: Examine Hardware</div>
        <div>Mobile: Touch & Drag</div>
    </div>
    
    <div id="exhibit-panel" style="display: none;">
        <h4 id="exhibit-title">Hardware Info</h4>
        <div id="exhibit-details"></div>
        <button onclick="closeExhibit()">Close</button>
    </div>

    <script>
        let scene, camera, renderer, controls;
        let exhibits = [];
        let selectedExhibit = null;
        
        const exhibits_data = [
            {
                name: "PowerBook G4",
                type: "vintage_laptop",
                year: "2003",
                position: [-5, 0, -5],
                color: 0x888888,
                specs: "PowerPC G4 1.67GHz, 1GB RAM, ATI Mobility Radeon 9700"
            },
            {
                name: "IBM POWER8",
                type: "server_rack", 
                year: "2014",
                position: [0, 0, -8],
                color: 0x0066cc,
                specs: "12-core POWER8, 512GB RAM, 22nm SOI process"
            },
            {
                name: "SGI Octane",
                type: "workstation",
                year: "1997", 
                position: [5, 0, -5],
                color: 0x9900cc,
                specs: "MIPS R10000 250MHz, 1GB RAM, VPro graphics"
            },
            {
                name: "Sun SPARCstation",
                type: "unix_workstation",
                year: "1989",
                position: [-3, 0, 0],
                color: 0xffaa00,
                specs: "SPARC CPU 25MHz, 16MB RAM, CG3 framebuffer"
            }
        ];

        function init() {
            scene = new THREE.Scene();
            scene.background = new THREE.Color(0x001122);
            
            camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
            camera.position.set(0, 2, 5);
            
            renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(window.innerWidth, window.innerHeight);
            renderer.shadowMap.enabled = true;
            renderer.shadowMap.type = THREE.PCFSoftShadowMap;
            document.body.appendChild(renderer.domElement);
            
            // Lighting
            const ambientLight = new THREE.AmbientLight(0x404040, 0.3);
            scene.add(ambientLight);
            
            const spotlight = new THREE.SpotLight(0xffffff, 1, 100, Math.PI/6, 0.5);
            spotlight.position.set(0, 10, 0);
            spotlight.castShadow = true;
            scene.add(spotlight);
            
            // Floor
            const floorGeometry = new THREE.PlaneGeometry(50, 50);
            const floorMaterial = new THREE.MeshLambertMaterial({ color: 0x333333 });
            const floor = new THREE.Mesh(floorGeometry, floorMaterial);
            floor.rotation.x = -Math.PI / 2;
            floor.receiveShadow = true;
            scene.add(floor);
            
            // Create exhibits
            exhibits_data.forEach((data, index) => {
                createExhibit(data, index);
            });
            
            // Mouse controls
            renderer.domElement.addEventListener('click', onMouseClick);
            document.addEventListener('keydown', onKeyDown);
            
            animate();
            fetchMuseumStats();
            setInterval(fetchMuseumStats, 10000);
        }
        
        function createExhibit(data, id) {
            let geometry;
            switch(data.type) {
                case 'vintage_laptop':
                    geometry = new THREE.BoxGeometry(1, 0.1, 0.7);
                    break;
                case 'server_rack':
                    geometry = new THREE.BoxGeometry(0.6, 2, 1);
                    break;
                case 'workstation':
                    geometry = new THREE.BoxGeometry(0.8, 0.8, 1.2);
                    break;
                default:
                    geometry = new THREE.BoxGeometry(1, 1, 1);
            }
            
            const material = new THREE.MeshPhongMaterial({ 
                color: data.color,
                transparent: true,
                opacity: 0.8
            });
            
            const exhibit = new THREE.Mesh(geometry, material);
            exhibit.position.set(...data.position);
            exhibit.castShadow = true;
            exhibit.userData = { ...data, id: id };
            
            // Add glow effect
            const glowGeometry = geometry.clone();
            const glowMaterial = new THREE.MeshBasicMaterial({
                color: data.color,
                transparent: true,
                opacity: 0.2,
                side: THREE.BackSide
            });
            glowGeometry.scale(1.1, 1.1, 1.1);
            const glow = new THREE.Mesh(glowGeometry, glowMaterial);
            exhibit.add(glow);
            
            scene.add(exhibit);
            exhibits.push(exhibit);
        }
        
        const raycaster = new THREE.Raycaster();
        const mouse = new THREE.Vector2();
        
        function onMouseClick(event) {
            mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
            mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;
            
            raycaster.setFromCamera(mouse, camera);
            const intersects = raycaster.intersectObjects(exhibits);
            
            if (intersects.length > 0) {
                const exhibit = intersects[0].object;
                showExhibitInfo(exhibit.userData);
            }
        }
        
        function showExhibitInfo(data) {
            const panel = document.getElementById('exhibit-panel');
            const title = document.getElementById('exhibit-title');
            const details = document.getElementById('exhibit-details');
            
            title.textContent = data.name;
            
            fetch(`/api/exhibit/${data.id}`)
                .then(response => response.json())
                .then(exhibitData => {
                    details.innerHTML = `
                        <div><strong>Year:</strong> ${data.year}</div>
                        <div><strong>Specs:</strong> ${data.specs}</div>
                        <div><strong>Status:</strong> ${exhibitData.mining_status}</div>
                        <div><strong>Hashrate:</strong> ${exhibitData.hashrate} H/s</div>
                        <div><strong>Temperature:</strong> ${exhibitData.temperature}°C</div>
                        <div><strong>Power Draw:</strong> ${exhibitData.power_draw}W</div>
                        <div><strong>Uptime:</strong> ${exhibitData.uptime} minutes</div>
                    `;
                })
                .catch(() => {
                    details.innerHTML = `
                        <div><strong>Year:</strong> ${data.year}</div>
                        <div><strong>Specs:</strong> ${data.specs}</div>
                        <div><strong>Status:</strong> Exhibit Mode</div>
                    `;
                });
            
            panel.style.display = 'block';
        }
        
        function closeExhibit() {
            document.getElementById('exhibit-panel').style.display = 'none';
        }
        
        const keys = {};
        
        function onKeyDown(event) {
            keys[event.code] = true;
        }
        
        document.addEventListener('keyup', (event) => {
            keys[event.code] = false;
        });
        
        function updateMovement() {
            const speed = 0.1;
            
            if (keys['KeyW']) camera.translateZ(-speed);
            if (keys['KeyS']) camera.translateZ(speed);
            if (keys['KeyA']) camera.translateX(-speed);
            if (keys['KeyD']) camera.translateX(speed);
        }
        
        function fetchMuseumStats() {
            fetch('/api/museum/stats')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('active-miners').textContent = data.active_miners;
                    document.getElementById('total-hashrate').textContent = data.total_hashrate;
                    document.getElementById('difficulty').textContent = data.difficulty;
                })
                .catch(console.error);
        }
        
        function animate() {
            requestAnimationFrame(animate);
            updateMovement();
            
            // Rotate exhibits slightly
            exhibits.forEach((exhibit, index) => {
                exhibit.rotation.y += 0.005 * (index % 2 === 0 ? 1 : -1);
            });
            
            renderer.render(scene, camera);
        }
        
        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });
        
        init();
    </script>
</body>
</html>
"""

def init_museum_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS museum_exhibits (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                hardware_type TEXT,
                year INTEGER,
                mining_status TEXT DEFAULT 'active',
                hashrate INTEGER DEFAULT 0,
                temperature REAL DEFAULT 0.0,
                power_draw INTEGER DEFAULT 0,
                uptime INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        exhibits = [
            ("PowerBook G4", "vintage_laptop", 2003, "mining", 1200, 65.5, 85, 1440),
            ("IBM POWER8", "server_rack", 2014, "mining", 15000, 72.1, 450, 2160),
            ("SGI Octane", "workstation", 1997, "mining", 800, 68.9, 120, 960),
            ("Sun SPARCstation", "unix_workstation", 1989, "exhibit", 0, 45.2, 25, 0)
        ]
        
        cursor.executemany('''
            INSERT OR IGNORE INTO museum_exhibits 
            (name, hardware_type, year, mining_status, hashrate, temperature, power_draw, uptime)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', exhibits)
        
        conn.commit()

@app.route('/')
def museum():
    return render_template_string(MUSEUM_TEMPLATE)

@app.route('/api/museum/stats')
def museum_stats():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM museum_exhibits WHERE mining_status = 'mining'")
        active_miners = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(hashrate) FROM museum_exhibits WHERE mining_status = 'mining'")
        total_hashrate = cursor.fetchone()[0] or 0
        
        # Simulate network difficulty
        difficulty = int(time.time() / 100) * 1000 + random.randint(0, 999)
        
        return jsonify({
            'active_miners': active_miners,
            'total_hashrate': f"{total_hashrate:,}",
            'difficulty': f"{difficulty:,}",
            'timestamp': datetime.now().isoformat()
        })

@app.route('/api/exhibit/<int:exhibit_id>')
def exhibit_details(exhibit_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT name, hardware_type, year, mining_status, hashrate, 
                   temperature, power_draw, uptime, last_updated
            FROM museum_exhibits WHERE id = ?
        ''', (exhibit_id + 1,))
        
        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'Exhibit not found'}), 404
            
        # Add some realistic variations
        temp_variation = random.uniform(-2.0, 2.0)
        hashrate_variation = random.randint(-100, 100)
        
        return jsonify({
            'name': result[0],
            'hardware_type': result[1],
            'year': result[2],
            'mining_status': result[3],
            'hashrate': max(0, result[4] + hashrate_variation),
            'temperature': round(result[5] + temp_variation, 1),
            'power_draw': result[6],
            'uptime': result[7] + random.randint(0, 60),
            'last_updated': result[8]
        })

@app.route('/api/mining/live')
def live_mining_data():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT name, hashrate, temperature, power_draw
            FROM museum_exhibits 
            WHERE mining_status = 'mining'
            ORDER BY hashrate DESC
        ''')
        
        miners = []
        for row in cursor.fetchall():
            miners.append({
                'name': row[0],
                'hashrate': row[1] + random.randint(-50, 50),
                'temperature': round(row[2] + random.uniform(-1.5, 1.5), 1),
                'power_draw': row[3],
                'efficiency': round(row[1] / row[3], 2) if row[3] > 0 else 0
            })
        
        return jsonify({
            'miners': miners,
            'network_hashrate': sum(m['hashrate'] for m in miners),
            'avg_temperature': round(sum(m['temperature'] for m in miners) / len(miners), 1) if miners else 0,
            'total_power': sum(m['power_draw'] for m in miners),
            'timestamp': datetime.now().isoformat()
        })

@app.route('/api/exhibits/list')
def list_exhibits():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, hardware_type, year, mining_status, hashrate
            FROM museum_exhibits
            ORDER BY year ASC
        ''')
        
        exhibits = []
        for row in cursor.fetchall():
            exhibits.append({
                'id': row[0],
                'name': row[1],
                'type': row[2],
                'year': row[3],
                'status': row[4],
                'hashrate': row[5]
            })
        
        return jsonify({'exhibits': exhibits})

if __name__ == '__main__':
    init_museum_db()
    app.run(debug=True, host='0.0.0.0', port=8080)