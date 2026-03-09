// Beacon Atlas - Minimap
// Corner minimap showing full Atlas overview

class Minimap {
    constructor(container, scene) {
        this.container = container;
        this.scene = scene;
        this.canvas = null;
        this.ctx = null;
        this.width = 200;
        this.height = 150;
        this.scale = 0.05;
        
        this.init();
    }
    
    init() {
        // Create canvas
        this.canvas = document.createElement('canvas');
        this.canvas.width = this.width;
        this.canvas.height = this.height;
        this.canvas.className = 'beacon-minimap';
        
        // Style
        this.canvas.style.position = 'absolute';
        this.canvas.style.bottom = '10px';
        this.canvas.style.left = '10px';
        this.canvas.style.border = '2px solid rgba(255,255,255,0.3)';
        this.canvas.style.borderRadius = '4px';
        this.canvas.style.background = 'rgba(0,0,0,0.5)';
        this.canvas.style.zIndex = '1000';
        
        this.container.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');
        
        // Click handler
        this.canvas.addEventListener('click', (e) => this.handleClick(e));
        
        // Start render loop
        this.render();
    }
    
    render() {
        if (!this.ctx) return;
        
        const ctx = this.ctx;
        const w = this.width;
        const h = this.height;
        
        // Clear
        ctx.fillStyle = 'rgba(0,0,0,0.3)';
        ctx.fillRect(0, 0, w, h);
        
        // Draw agents (green dots)
        ctx.fillStyle = '#00ff88';
        if (this.scene.agents) {
            this.scene.agents.forEach(agent => {
                const x = (agent.x || 0) * this.scale + w/2;
                const y = (agent.z || 0) * this.scale + h/2;
                ctx.beginPath();
                ctx.arc(x, y, 3, 0, Math.PI * 2);
                ctx.fill();
            });
        }
        
        // Draw cities (yellow dots)
        ctx.fillStyle = '#ffcc00';
        if (this.scene.cities) {
            this.scene.cities.forEach(city => {
                const x = (city.x || 0) * this.scale + w/2;
                const y = (city.z || 0) * this.scale + h/2;
                ctx.beginPath();
                ctx.arc(x, y, 5, 0, Math.PI * 2);
                ctx.fill();
            });
        }
        
        // Draw connections (blue lines)
        ctx.strokeStyle = 'rgba(100,150,255,0.5)';
        ctx.lineWidth = 1;
        if (this.scene.connections) {
            this.scene.connections.forEach(conn => {
                const x1 = (conn.from?.x || 0) * this.scale + w/2;
                const y1 = (conn.from?.z || 0) * this.scale + h/2;
                const x2 = (conn.to?.x || 0) * this.scale + w/2;
                const y2 = (conn.to?.z || 0) * this.scale + h/2;
                ctx.beginPath();
                ctx.moveTo(x1, y1);
                ctx.lineTo(x2, y2);
                ctx.stroke();
            });
        }
        
        // Draw viewport indicator
        if (this.scene.camera) {
            const camX = this.scene.camera.position?.x || 0;
            const camZ = this.scene.camera.position?.z || 0;
            const vx = camX * this.scale + w/2;
            const vy = camZ * this.scale + h/2;
            
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 2;
            ctx.strokeRect(vx - 15, vy - 10, 30, 20);
        }
        
        // Request next frame
        requestAnimationFrame(() => this.render());
    }
    
    handleClick(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        // Convert to world coordinates
        const worldX = (x - this.width/2) / this.scale;
        const worldZ = (y - this.height/2) / this.scale;
        
        // Emit event for camera to move
        if (this.scene.setCameraTarget) {
            this.scene.setCameraTarget(worldX, worldZ);
        }
    }
}

// Export
if (typeof window !== 'undefined') {
    window.BeaconMinimap = Minimap;
}

module.exports = Minimap;
