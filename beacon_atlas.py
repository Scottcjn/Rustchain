// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, render_template_string, jsonify, request
import sqlite3
import json
from datetime import datetime
import os

app = Flask(__name__)

DB_PATH = "rustchain.db"

BEACON_ATLAS_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Beacon Atlas - RustChain Agent World</title>
    <style>
        body { margin: 0; padding: 0; background: #000; font-family: monospace; overflow: hidden; }
        #canvas-container { position: relative; width: 100vw; height: 100vh; }
        #info-panel { 
            position: absolute; top: 20px; right: 20px; width: 300px; 
            background: rgba(0,20,30,0.9); border: 1px solid #00ff88; 
            color: #00ff88; padding: 15px; display: none; border-radius: 5px;
        }
        #info-panel h3 { margin: 0 0 10px 0; color: #fff; }
        .status-badge { 
            padding: 2px 8px; border-radius: 3px; font-size: 12px; font-weight: bold;
        }
        .status-online { background: #00ff88; color: #000; }
        .status-idle { background: #ffaa00; color: #000; }
        .status-offline { background: #ff4444; color: #fff; }
        #stats { 
            position: absolute; top: 20px; left: 20px; color: #00ff88; 
            background: rgba(0,20,30,0.8); padding: 10px; border-radius: 5px;
        }
    </style>
</head>
<body>
    <div id="canvas-container">
        <div id="stats">
            <div>Active Agents: <span id="agent-count">0</span></div>
            <div>Total Beacons: <span id="beacon-count">0</span></div>
        </div>
        <div id="info-panel">
            <h3 id="agent-name">Agent Details</h3>
            <div><strong>ID:</strong> <span id="agent-id"></span></div>
            <div><strong>Status:</strong> <span id="agent-status"></span></div>
            <div><strong>Reputation:</strong> <span id="agent-reputation"></span></div>
            <div><strong>Jobs:</strong> <span id="agent-jobs"></span></div>
            <div><strong>Trust Level:</strong> <span id="agent-trust"></span></div>
            <div><strong>Registered:</strong> <span id="agent-registered"></span></div>
            <div><strong>Last Seen:</strong> <span id="agent-lastseen"></span></div>
            <div><strong>PubKey:</strong> <span id="agent-pubkey"></span></div>
            <button onclick="closePanel()" style="margin-top: 10px; background: #00ff88; border: none; padding: 5px 10px; cursor: pointer;">Close</button>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
        let scene, camera, renderer, raycaster, mouse;
        let beacons = [];
        let agents = [];

        function init() {
            scene = new THREE.Scene();
            scene.fog = new THREE.Fog(0x001122, 50, 300);
            
            camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
            camera.position.set(0, 50, 100);
            camera.lookAt(0, 0, 0);

            renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(window.innerWidth, window.innerHeight);
            renderer.setClearColor(0x001122);
            document.getElementById('canvas-container').appendChild(renderer.domElement);

            raycaster = new THREE.Raycaster();
            mouse = new THREE.Vector2();

            createWorld();
            loadAgents();
            
            renderer.domElement.addEventListener('click', onMouseClick);
            window.addEventListener('resize', onWindowResize);
            
            animate();
        }

        function createWorld() {
            // Grid floor
            const gridHelper = new THREE.GridHelper(200, 50, 0x004488, 0x002244);
            scene.add(gridHelper);

            // Corner pillars
            const pillarGeometry = new THREE.CylinderGeometry(1, 1, 20);
            const pillarMaterial = new THREE.MeshBasicMaterial({ color: 0x006699, wireframe: true });
            
            const positions = [[-100, 10, -100], [100, 10, -100], [-100, 10, 100], [100, 10, 100]];
            positions.forEach(pos => {
                const pillar = new THREE.Mesh(pillarGeometry, pillarMaterial);
                pillar.position.set(pos[0], pos[1], pos[2]);
                scene.add(pillar);
            });

            // Star field
            const starsGeometry = new THREE.BufferGeometry();
            const starsVertices = [];
            for (let i = 0; i < 1000; i++) {
                starsVertices.push(
                    (Math.random() - 0.5) * 1000,
                    Math.random() * 200 + 100,
                    (Math.random() - 0.5) * 1000
                );
            }
            starsGeometry.setAttribute('position', new THREE.Float32BufferAttribute(starsVertices, 3));
            const starsMaterial = new THREE.PointsMaterial({ color: 0xffffff, size: 0.5 });
            const stars = new THREE.Points(starsGeometry, starsMaterial);
            scene.add(stars);

            // Ambient light
            const ambientLight = new THREE.AmbientLight(0x404040, 0.3);
            scene.add(ambientLight);
        }

        function loadAgents() {
            fetch('/api/agents')
                .then(response => response.json())
                .then(data => {
                    agents = data.agents;
                    createBeacons();
                    updateStats();
                })
                .catch(error => console.error('Error loading agents:', error));
        }

        function createBeacons() {
            agents.forEach((agent, index) => {
                const beacon = createBeacon(agent, index);
                scene.add(beacon);
                beacons.push(beacon);
            });
        }

        function createBeacon(agent, index) {
            const gridSize = Math.ceil(Math.sqrt(agents.length));
            const x = (index % gridSize - gridSize/2) * 8;
            const z = (Math.floor(index / gridSize) - gridSize/2) * 8;

            let geometry, color;
            if (agent.status === 'online') {
                geometry = new THREE.OctahedronGeometry(1.5);
                color = 0x00ff88;
            } else {
                geometry = new THREE.BoxGeometry(2, 2, 2);
                color = agent.status === 'idle' ? 0xffaa00 : 0xff4444;
            }

            const material = new THREE.MeshBasicMaterial({ 
                color: color,
                wireframe: false,
                transparent: true,
                opacity: 0.8
            });

            const beacon = new THREE.Mesh(geometry, material);
            beacon.position.set(x, 3, z);
            beacon.userData = agent;

            // Glow effect
            const glowGeometry = geometry.clone();
            const glowMaterial = new THREE.MeshBasicMaterial({
                color: color,
                transparent: true,
                opacity: 0.3,
                side: THREE.BackSide
            });
            const glow = new THREE.Mesh(glowGeometry, glowMaterial);
            glow.scale.multiplyScalar(1.2);
            beacon.add(glow);

            return beacon;
        }

        function onMouseClick(event) {
            mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
            mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

            raycaster.setFromCamera(mouse, camera);
            const intersects = raycaster.intersectObjects(beacons);

            if (intersects.length > 0) {
                const agent = intersects[0].object.userData;
                showAgentDetails(agent);
            }
        }

        function showAgentDetails(agent) {
            fetch(`/api/reputation/${agent.id}`)
                .then(response => response.json())
                .then(rep => {
                    document.getElementById('agent-name').textContent = agent.name || 'Unknown Agent';
                    document.getElementById('agent-id').textContent = agent.id;
                    
                    const statusBadge = `<span class="status-badge status-${agent.status}">${agent.status.toUpperCase()}</span>`;
                    document.getElementById('agent-status').innerHTML = statusBadge;
                    
                    document.getElementById('agent-reputation').textContent = rep.reputation_score || 0;
                    document.getElementById('agent-jobs').textContent = rep.completed_jobs || 0;
                    document.getElementById('agent-trust').textContent = rep.trust_level || 'Unknown';
                    document.getElementById('agent-registered').textContent = agent.created_at || 'Unknown';
                    document.getElementById('agent-lastseen').textContent = agent.last_seen || 'Never';
                    document.getElementById('agent-pubkey').textContent = agent.public_key ? 
                        agent.public_key.substring(0, 20) + '...' : 'Not Set';
                    
                    document.getElementById('info-panel').style.display = 'block';
                })
                .catch(error => {
                    console.error('Error loading reputation:', error);
                    document.getElementById('info-panel').style.display = 'block';
                });
        }

        function closePanel() {
            document.getElementById('info-panel').style.display = 'none';
        }

        function updateStats() {
            const onlineCount = agents.filter(a => a.status === 'online').length;
            document.getElementById('agent-count').textContent = onlineCount;
            document.getElementById('beacon-count').textContent = agents.length;
        }

        function animate() {
            requestAnimationFrame(animate);
            
            // Rotate beacons
            beacons.forEach(beacon => {
                beacon.rotation.y += 0.01;
            });
            
            renderer.render(scene, camera);
        }

        function onWindowResize() {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        }

        init();
    </script>
</body>
</html>
"""

@app.route('/beacon-atlas')
def beacon_atlas():
    return render_template_string(BEACON_ATLAS_HTML)

@app.route('/api/agents')
def api_agents():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, name, public_key, status, created_at, last_seen
                FROM agents 
                ORDER BY created_at DESC
            """)
            
            agents = []
            for row in cursor.fetchall():
                agents.append({
                    'id': row['id'],
                    'name': row['name'],
                    'public_key': row['public_key'],
                    'status': row['status'] or 'offline',
                    'created_at': row['created_at'],
                    'last_seen': row['last_seen']
                })
            
            return jsonify({'agents': agents})
            
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reputation/<agent_id>')
def api_reputation(agent_id):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get reputation data
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END), 0) as completed_jobs,
                    COALESCE(AVG(rating), 0) as avg_rating,
                    COUNT(*) as total_jobs
                FROM jobs 
                WHERE assigned_to = ?
            """, (agent_id,))
            
            job_stats = cursor.fetchone()
            
            # Calculate reputation score
            reputation_score = int(job_stats['completed_jobs'] * 10 + job_stats['avg_rating'] * 5)
            
            # Determine trust level
            if reputation_score >= 100:
                trust_level = 'Legendary'
            elif reputation_score >= 50:
                trust_level = 'Trusted'
            elif reputation_score >= 20:
                trust_level = 'Reliable'
            elif reputation_score >= 5:
                trust_level = 'Emerging'
            else:
                trust_level = 'New'
            
            return jsonify({
                'reputation_score': reputation_score,
                'completed_jobs': job_stats['completed_jobs'],
                'total_jobs': job_stats['total_jobs'],
                'avg_rating': round(job_stats['avg_rating'], 1),
                'trust_level': trust_level
            })
            
    except sqlite3.Error as e:
        return jsonify({
            'reputation_score': 0,
            'completed_jobs': 0,
            'total_jobs': 0,
            'avg_rating': 0,
            'trust_level': 'Unknown'
        })

if __name__ == '__main__':
    app.run(debug=True, port=5003)