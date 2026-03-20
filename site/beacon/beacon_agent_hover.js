// SPDX-License-Identifier: MIT
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';

class BeaconAgentHover {
    constructor(scene, camera, renderer) {
        this.scene = scene;
        this.camera = camera;
        this.renderer = renderer;
        this.css2dRenderer = null;
        this.hoverCard = null;
        this.currentHoveredAgent = null;
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();
        this.agents = [];

        this.initializeCSS2DRenderer();
        this.createHoverCard();
        this.setupEventListeners();
    }

    initializeCSS2DRenderer() {
        this.css2dRenderer = new CSS2DRenderer();
        this.css2dRenderer.setSize(window.innerWidth, window.innerHeight);
        this.css2dRenderer.domElement.style.position = 'absolute';
        this.css2dRenderer.domElement.style.top = '0px';
        this.css2dRenderer.domElement.style.pointerEvents = 'none';
        document.body.appendChild(this.css2dRenderer.domElement);
    }

    createHoverCard() {
        const cardElement = document.createElement('div');
        cardElement.className = 'agent-hover-card';
        cardElement.style.cssText = `
            background: rgba(15, 15, 35, 0.95);
            border: 1px solid #4a90e2;
            border-radius: 8px;
            padding: 12px;
            color: white;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            min-width: 180px;
            box-shadow: 0 4px 12px rgba(74, 144, 226, 0.3);
            backdrop-filter: blur(10px);
            opacity: 0;
            transition: opacity 0.2s ease;
            pointer-events: none;
        `;

        this.hoverCard = new CSS2DObject(cardElement);
        this.hoverCard.visible = false;
        this.scene.add(this.hoverCard);
    }

    setupEventListeners() {
        window.addEventListener('mousemove', (event) => {
            this.mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
            this.mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;
            this.checkHover();
        });

        window.addEventListener('resize', () => {
            this.css2dRenderer.setSize(window.innerWidth, window.innerHeight);
        });
    }

    registerAgent(agentMesh, agentData) {
        this.agents.push({
            mesh: agentMesh,
            data: agentData
        });
    }

    checkHover() {
        this.raycaster.setFromCamera(this.mouse, this.camera);
        const agentMeshes = this.agents.map(agent => agent.mesh);
        const intersects = this.raycaster.intersectObjects(agentMeshes);

        if (intersects.length > 0) {
            const intersectedMesh = intersects[0].object;
            const agent = this.agents.find(a => a.mesh === intersectedMesh);

            if (agent && agent !== this.currentHoveredAgent) {
                this.showHoverCard(agent, intersects[0].point);
                this.currentHoveredAgent = agent;
            }
        } else {
            this.hideHoverCard();
            this.currentHoveredAgent = null;
        }
    }

    showHoverCard(agent, position) {
        const cardData = this.formatAgentData(agent.data);
        this.hoverCard.element.innerHTML = cardData;

        this.hoverCard.position.copy(position);
        this.hoverCard.position.y += 15;

        this.hoverCard.visible = true;
        this.hoverCard.element.style.opacity = '1';
    }

    hideHoverCard() {
        if (this.hoverCard) {
            this.hoverCard.visible = false;
            this.hoverCard.element.style.opacity = '0';
        }
    }

    formatAgentData(data) {
        const name = data.name || data.id || 'Unknown Agent';
        const status = this.getStatusBadge(data.status);
        const videoCount = data.video_count || data.videos || 0;
        const lastSeen = data.last_seen ? this.formatTimeAgo(data.last_seen) : 'Unknown';
        const nodeType = data.node_type || 'Agent';

        return `
            <div style="margin-bottom: 6px;">
                <strong style="color: #4a90e2;">${name}</strong>
            </div>
            <div style="margin-bottom: 4px;">
                Status: ${status}
            </div>
            <div style="margin-bottom: 4px;">
                Type: <span style="color: #7cb342;">${nodeType}</span>
            </div>
            <div style="margin-bottom: 4px;">
                Videos: <span style="color: #ff9800;">${videoCount}</span>
            </div>
            <div style="font-size: 10px; color: #888;">
                Last seen: ${lastSeen}
            </div>
        `;
    }

    getStatusBadge(status) {
        const statusColors = {
            'online': '#4caf50',
            'offline': '#f44336',
            'idle': '#ff9800',
            'active': '#2196f3'
        };

        const color = statusColors[status] || '#666';
        const displayStatus = status || 'unknown';

        return `<span style="color: ${color}; font-weight: bold;">●</span> ${displayStatus}`;
    }

    formatTimeAgo(timestamp) {
        const now = Date.now();
        const then = new Date(timestamp).getTime();
        const diff = now - then;

        if (diff < 60000) return 'Just now';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
        return `${Math.floor(diff / 86400000)}d ago`;
    }

    render() {
        if (this.css2dRenderer) {
            this.css2dRenderer.render(this.scene, this.camera);
        }
    }

    dispose() {
        if (this.css2dRenderer && this.css2dRenderer.domElement.parentNode) {
            this.css2dRenderer.domElement.parentNode.removeChild(this.css2dRenderer.domElement);
        }

        if (this.hoverCard) {
            this.scene.remove(this.hoverCard);
        }

        window.removeEventListener('mousemove', this.checkHover.bind(this));
        window.removeEventListener('resize', this.onWindowResize.bind(this));
    }
}

export { BeaconAgentHover };
