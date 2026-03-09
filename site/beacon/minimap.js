// ============================================
// Minimap for Beacon Atlas
// Track B - 15 RTC
// ============================================

class Minimap {
    constructor(scene, camera, renderer) {
        this.scene = scene;
        this.camera = camera;
        this.renderer = renderer;
        
        // World bounds
        this.worldSize = 2000;
        
        // Minimap settings
        this.size = 180;
        
        // Canvas
        this.canvas = null;
        this.ctx = null;
        
        // Data references
        this.agentsMap = null;
        this.citiesData = null;
        this.connectionsData = null;
        
        this.init();
    }
    
    init() {
        this.canvas = document.createElement('canvas');
        this.canvas.id = 'minimap-canvas';
        this.canvas.width = this.size;
        this.canvas.height = this.size;
        
        this.canvas.style.position = 'absolute';
        this.canvas.style.left = '20px';
        this.canvas.style.bottom = '20px';
        this.canvas.style.width = this.size + 'px';
        this.canvas.style.height = this.size + 'px';
        this.canvas.style.backgroundColor = 'rgba(10, 15, 20, 0.85)';
        this.canvas.style.border = '2px solid #00ff88';
        this.canvas.style.borderRadius = '8px';
        this.canvas.style.zIndex = '1000';
        this.canvas.style.boxShadow = '0 0 20px rgba(0, 255, 136, 0.3)';
        this.canvas.style.pointerEvents = 'auto';
        
       (this.canvas);
        document.body.appendChild this.ctx = this.canvas.getContext('2d');
        
        // Click handler
        this.canvas.addEventListener('click', (e) => this.handleClick(e));
    }
    
    // Set data sources
    setDataSources(agentsMap, citiesData, connectionsData) {
        this.agentsMap = agentsMap;
        this.citiesData = citiesData;
        this.connectionsData = connectionsData;
    }
    
    worldToMinimap(x, z) {
        const scale = this.size / this.worldSize;
        const offset = this.size / 2;
        return {
            x: x * scale + offset,
            y: z * scale + offset
        };
    }
    
    minimapToWorld(mx, my) {
        const scale = this.worldSize / this.size;
        const offset = this.size / 2;
        return {
            x: (mx - offset) * scale,
            z: (my - offset) * scale
        };
    }
    
    getFrustumCorners() {
        const corners = [];
        const camera = this.camera;
        const dir = new THREE.Vector3();
        camera.getWorldDirection(dir);
        const pos = camera.position.clone();
        const fov = camera.fov * Math.PI / 180;
        const aspect = camera.aspect;
        const viewDistance = 800;
        const viewWidth = 2 * Math.tan(fov / 2) * viewDistance * aspect;
        const viewHeight = 2 * Math.tan(fov / 2) * viewDistance;
        
        const right = new THREE.Vector3();
        const up = new THREE.Vector3();
        right.crossVectors(dir, camera.up).normalize();
        up.crossVectors(right, dir).normalize();
        
        const halfW = viewWidth / 2;
        const halfH = viewHeight / 2;
        
        corners.push(this.worldToMinimap(
            pos.x + right.x * halfW + dir.x * viewDistance,
            pos.z + right.z * halfW + dir.z * viewDistance
        ));
        corners.push(this.worldToMinimap(
            pos.x - right.x * halfW + dir.x * viewDistance,
            pos.z - right.z * halfW + dir.z * viewDistance
        ));
        
        return corners;
    }
    
    render() {
        if (!this.ctx) return;
        
        const ctx = this.ctx;
        const size = this.size;
        
        ctx.clearRect(0, 0, size, size);
        
        // Background
        const gradient = ctx.createRadialGradient(size/2, size/2, 0, size/2, size/2, size);
        gradient.addColorStop(0, 'rgba(20, 30, 40, 0.9)');
        gradient.addColorStop(1, 'rgba(10, 15, 20, 0.95)');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, size, size);
        
        // Grid
        ctx.strokeStyle = 'rgba(0, 255, 136, 0.1)';
        ctx.lineWidth = 1;
        const gridStep = size / 10;
        for (let i = 0; i <= 10; i++) {
            ctx.beginPath();
            ctx.moveTo(i * gridStep, 0);
            ctx.lineTo(i * gridStep, size);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(0, i            ctx.lineTo(size, i * * gridStep);
 gridStep);
            ctx.stroke();
        }
        
        // Draw connections
        if (this.connectionsData) {
            ctx.strokeStyle = 'rgba(0, 200, 255, 0.4)';
            ctx.lineWidth = 1;
            for (const conn of this.connectionsData) {
                if (conn.line) {
                    const positions = conn.line.geometry.attributes.position;
                    if (positions && positions.count >= 2) {
                        const start = this.worldToMinimap(positions.getX(0), positions.getZ(0));
                        const end = this.worldToMinimap(positions.getX(positions.count - 1), positions.getZ(positions.count - 1));
                        ctx.beginPath();
                        ctx.moveTo(start.x, start.y);
                        ctx.lineTo(end.x, end.y);
                        ctx.stroke();
                    }
                }
            }
        }
        
        // Draw cities
        if (this.citiesData) {
            for (const city of this.citiesData) {
                const pos = this.worldToMinimap(city.mesh.position.x, city.mesh.position.z);
                const radius = 5;
                
                ctx.beginPath();
                ctx.arc(pos.x, pos.y, radius + 3, 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(255, 200, 0, 0.2)';
                ctx.fill();
                
                ctx.beginPath();
                ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
                ctx.fillStyle = '#ffcc00';
                ctx.fill();
                ctx.strokeStyle = '#ff8800';
                ctx.lineWidth = 1;
                ctx.stroke();
            }
        }
        
        // Draw agents
        if (this.agentsMap) {
            for (const [agentId, agentData] of this.agentsMap) {
                const pos = this.worldToMinimap(agentData.group.position.x, agentData.group.position.z);
                
                let color = '#00ff88';
                if (agentData.status === 'silent' || agentData.status === 'offline') color = '#666666';
                else if (agentData.status === 'busy') color = '#ff4444';
                
                ctx.beginPath();
                ctx.arc(pos.x, pos.y, 3, 0, Math.PI * 2);
                ctx.fillStyle = color;
                ctx.fill();
                
                if (agentData.status !== 'silent' && agentData.status !== 'offline') {
                    ctx.beginPath();
                    ctx.arc(pos.x, pos.y, 5, 0, Math.PI * 2);
                    ctx.strokeStyle = color;
                    ctx.globalAlpha = 0.5;
                    ctx.lineWidth = 1;
                    ctx.stroke();
                    ctx.globalAlpha = 1;
                }
            }
        }
        
        // Draw viewport
        const corners = this.getFrustumCorners();
        if (corners.length >= 2) {
            let minX = Math.max(0, Math.min(corners[0].x, corners[1].x) - 20);
            let maxX = Math.min(size, Math.max(corners[0].x, corners[1].x) + 20);
            let minY = Math.max(0, Math.min(corners[0].y, corners[1].y) - 20);
            let maxY = Math.min(size, Math.max(corners[0].y, corners[1].y) + 20);
            
            minX = Math.max(0, minX);
            minY = Math.max(0, minY);
            maxX = Math.min(size, maxX);
            maxY = Math.min(size, maxY);
            
            ctx.strokeStyle = 'rgba(0, 255, 136, 0.8)';
            ctx.lineWidth = 2;
            ctx.strokeRect(minX, minY, maxX - minX, maxY - minY);
            ctx.fillStyle = 'rgba(0, 255, 136, 0.1)';
            ctx.fillRect(minX, minY, maxX - minX, maxY - minY);
        }
        
        // Center indicator
        const camPos = this.worldToMinimap(this.camera.position.x, this.camera.position.z);
        ctx.fillStyle = '#00ff88';
        ctx.font = 'bold 10px monospace';
        ctx.textAlign = 'center';
        ctx.fillText('N', camPos.x, camPos.y - 15);
        
        ctx.strokeStyle = 'rgba(0, 255, 136, 0.6)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(camPos.x - 6, camPos.y);
        ctx.lineTo(camPos.x + 6, camPos.y);
        ctx.moveTo(camPos.x, camPos.y - 6);
        ctx.lineTo(camPos.x, camPos.y + 6);
        ctx.stroke();
    }
    
    handleClick(e) {
        const rect = this.canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        
        const worldPos = this.minimapToWorld(mx, my);
        
        // Emit event for camera to move
        const event = new CustomEvent('minimapClick', {
            detail: { x: worldPos.x, z: worldPos.z }
        });
        document.dispatchEvent(event);
    }
    
    toggle() {
        this.canvas.style.display = this.canvas.style.display === 'none' ? 'block' : 'none';
    }
    
    show() {
        if (this.canvas) this.canvas.style.display = 'block';
    }
    
    hide() {
        if (this.canvas) this.canvas.style.display = 'none';
    }
    
    dispose() {
        if (this.canvas && this.canvas.parentNode) {
            this.canvas.parentNode.removeChild(this.canvas);
        }
    }
}

window.Minimap = Minimap;
