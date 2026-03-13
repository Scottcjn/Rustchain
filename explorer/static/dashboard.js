// RustChain Beacon Dashboard JavaScript

class BeaconDashboard {
    constructor() {
        this.apiUrl = '/api';
        this.refreshInterval = 5000; // 5 seconds
        this.init();
    }

    init() {
        this.updateStatus();
        this.loadNodes();
        setInterval(() => this.updateStatus(), this.refreshInterval);
        setInterval(() => this.loadNodes(), this.refreshInterval);
    }

    async updateStatus() {
        try {
            const response = await fetch(`${this.apiUrl}/status`);
            const data = await response.json();
            
            document.getElementById('total-nodes').textContent = data.total_nodes;
            document.getElementById('active-nodes').textContent = data.active_nodes;
            document.getElementById('last-update').textContent = new Date(data.timestamp).toLocaleTimeString();
            
            const statusDot = document.querySelector('.status-dot');
            const statusText = document.getElementById('status-text');
            
            if (data.active_nodes > 0) {
                statusDot.classList.add('active');
                statusText.textContent = 'Connected';
            } else {
                statusDot.classList.remove('active');
                statusText.textContent = 'No Active Nodes';
            }
        } catch (error) {
            console.error('Failed to fetch status:', error);
            document.getElementById('status-text').textContent = 'Connection Error';
        }
    }

    async loadNodes() {
        try {
            const response = await fetch(`${this.apiUrl}/nodes`);
            const data = await response.json();
            
            const nodesList = document.getElementById('nodes-list');
            
            if (data.nodes.length === 0) {
                nodesList.innerHTML = '<div class="loading">No beacon nodes configured</div>';
                return;
            }
            
            nodesList.innerHTML = data.nodes.map(node => `
                <div class="node-card ${node.active ? 'active' : ''}">
                    <div class="node-header">
                        <span class="node-name">${node.name || 'Unknown Node'}</span>
                        <span class="node-status ${node.active ? 'active' : 'inactive'}">
                            ${node.active ? 'Active' : 'Inactive'}
                        </span>
                    </div>
                    <div class="node-details">
                        <p><strong>Endpoint:</strong> ${node.endpoint || 'N/A'}</p>
                        <p><strong>Sync Status:</strong> ${node.sync_status || 'Unknown'}</p>
                        <p><strong>Peers:</strong> ${node.peers || 0}</p>
                        <p><strong>Slot:</strong> ${node.current_slot || 'N/A'}</p>
                        <p><strong>Last Update:</strong> ${node.last_update ? new Date(node.last_update).toLocaleString() : 'Never'}</p>
                    </div>
                </div>
            `).join('');
        } catch (error) {
            console.error('Failed to load nodes:', error);
        }
    }
}

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', () => {
    new BeaconDashboard();
});
