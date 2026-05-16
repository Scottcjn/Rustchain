/**
 * RustChain Explorer - Real-time Dashboard
 * Main application logic with WebSocket support
 */

class DashboardApp {
    constructor(options = {}) {
        this.apiBase = options.apiBase || window.location.origin;
        this.wsUrl = options.wsUrl || `ws://${window.location.host}`;
        this.pollInterval = options.pollInterval || 5000;
        
        this.socket = null;
        this.charts = {};
        this.state = {
            connected: false,
            blocks: [],
            transactions: [],
            miners: [],
            epoch: {},
            health: {},
            metrics: {
                blocksReceived: 0,
                transactionsReceived: 0,
                updatesReceived: 0
            },
            lastUpdate: null,
            startTime: Date.now()
        };
        
        this.minersHistory = [];
        this.blocksHistory = [];
        this.txsHistory = [];
        
        this.init();
    }

    init() {
        this.setupSocket();
        this.setupCharts();
        this.setupEventListeners();
        this.startPolling();
        
        console.log('[Dashboard] Initialized');
    }

    /**
     * Setup WebSocket connection
     */
    setupSocket() {
        // Use Socket.IO if available, otherwise fallback to native WebSocket
        if (window.io) {
            this.socket = io(this.wsUrl, {
                transports: ['websocket', 'polling'],
                reconnection: true,
                reconnectionDelay: 1000,
                reconnectionAttempts: 10
            });

            this.socket.on('connect', () => this.onConnect());
            this.socket.on('disconnect', () => this.onDisconnect());
            this.socket.on('block', (data) => this.onBlock(data));
            this.socket.on('transaction', (data) => this.onTransaction(data));
            this.socket.on('miner_update', (data) => this.onMinerUpdate(data));
            this.socket.on('epoch_update', (data) => this.onEpochUpdate(data));
            this.socket.on('health', (data) => this.onHealth(data));
            this.socket.on('metrics', (data) => this.onMetrics(data));
            this.socket.on('connected', (data) => this.onSocketConnected(data));
        } else {
            // Fallback to native WebSocket
            this.connectNativeWebSocket();
        }
    }

    connectNativeWebSocket() {
        try {
            this.socket = new WebSocket(this.wsUrl);
            
            this.socket.onopen = () => this.onConnect();
            this.socket.onclose = () => this.onDisconnect();
            this.socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketMessage(data);
                } catch (e) {
                    console.error('[Dashboard] Failed to parse WS message:', e);
                }
            };
            this.socket.onerror = (error) => {
                console.error('[Dashboard] WebSocket error:', error);
                this.updateConnectionStatus('error');
            };
        } catch (e) {
            console.error('[Dashboard] Failed to create WebSocket:', e);
        }
    }

    handleWebSocketMessage(data) {
        const { type, payload } = data;
        
        switch (type) {
            case 'block':
                this.onBlock(payload);
                break;
            case 'transaction':
                this.onTransaction(payload);
                break;
            case 'miner_update':
                this.onMinerUpdate(payload);
                break;
            case 'epoch_update':
                this.onEpochUpdate(payload);
                break;
            case 'health':
                this.onHealth(payload);
                break;
            case 'metrics':
                this.onMetrics(payload);
                break;
            case 'connected':
                this.onSocketConnected(payload);
                break;
        }
    }

    onConnect() {
        this.state.connected = true;
        this.updateConnectionStatus('connected');
        console.log('[Dashboard] Connected to server');
        
        // Request initial state
        if (this.socket && this.socket.emit) {
            this.socket.emit('request_state');
        } else if (this.socket && this.socket.send) {
            this.socket.send(JSON.stringify({ type: 'request_state' }));
        }
    }

    onDisconnect() {
        this.state.connected = false;
        this.updateConnectionStatus('disconnected');
        console.log('[Dashboard] Disconnected from server');
    }

    onSocketConnected(data) {
        console.log('[Dashboard] Socket connected:', data);
        if (data.state) {
            this.updateState(data.state);
        }
    }

    onBlock(block) {
        this.state.metrics.blocksReceived++;
        this.state.metrics.updatesReceived++;
        
        // Add to blocks array (keep last 50)
        this.state.blocks.unshift(block);
        if (this.state.blocks.length > 50) {
            this.state.blocks.pop();
        }
        
        this.updateBlocksDisplay();
        this.updateBlocksChart();
        this.highlightNewBlock(block);
        this.updateLastUpdateTime();
    }

    onTransaction(tx) {
        this.state.metrics.transactionsReceived++;
        this.state.metrics.updatesReceived++;
        
        // Add to transactions array (keep last 100)
        this.state.transactions.unshift(tx);
        if (this.state.transactions.length > 100) {
            this.state.transactions.pop();
        }
        
        this.updateTransactionsDisplay();
        this.updateTransactionsChart();
        this.updateLastUpdateTime();
    }

    onMinerUpdate(data) {
        this.state.metrics.updatesReceived++;
        
        const miners = data.miners || data;
        if (Array.isArray(miners)) {
            this.state.miners = miners;
            this.updateMinersDisplay();
            this.updateHardwareDistribution();
            this.updateMinersChart();
        }
        
        this.updateLastUpdateTime();
    }

    onEpochUpdate(epoch) {
        this.state.epoch = epoch;
        this.updateEpochDisplay();
        this.updateLastUpdateTime();
    }

    onHealth(health) {
        this.state.health = health;
        this.updateHealthDisplay();
        this.updateLastUpdateTime();
    }

    onMetrics(metrics) {
        this.state.serverMetrics = metrics;
        this.updateMetricsDisplay();
    }

    updateState(state) {
        if (state.blocks) this.state.blocks = state.blocks;
        if (state.transactions) this.state.transactions = state.transactions;
        if (state.miners) this.state.miners = state.miners;
        if (state.epoch) this.state.epoch = state.epoch;
        if (state.health) this.state.health = state.health;
        
        this.updateAllDisplays();
    }

    /**
     * Setup charts
     */
    setupCharts() {
        // Blocks per hour chart
        if (document.getElementById('blocks-chart')) {
            this.charts.blocks = new ChartRenderer('blocks-chart', {
                type: 'area',
                colors: ['#8b5cf6', '#6366f1']
            });
        }

        // Transactions chart
        if (document.getElementById('transactions-chart')) {
            this.charts.transactions = new ChartRenderer('transactions-chart', {
                type: 'line',
                colors: ['#10b981', '#059669']
            });
        }

        // Miners sparkline
        if (document.getElementById('miners-chart')) {
            this.charts.miners = new ChartRenderer('miners-chart', {
                type: 'line',
                colors: ['#f59e0b'],
                showLegend: false,
                showGrid: false
            });
        }

        // Hardware distribution
        if (document.getElementById('hardware-chart')) {
            this.charts.hardware = new ChartRenderer('hardware-chart', {
                type: 'doughnut',
                colors: ['#f59e0b', '#3b82f6', '#6b7280', '#8b5cf6', '#10b981']
            });
        }

        // Initialize with empty data
        this.initializeCharts();
    }

    initializeCharts() {
        // Initialize with placeholder data
        const placeholderData = [0, 0, 0, 0, 0, 0];
        
        if (this.charts.blocks) {
            this.charts.blocks.update(placeholderData);
        }
        if (this.charts.transactions) {
            this.charts.transactions.update(placeholderData);
        }
        if (this.charts.miners) {
            this.charts.miners.update(placeholderData);
        }
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Theme toggle
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => this.toggleTheme());
        }

        // Handle page visibility change
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.pauseUpdates();
            } else {
                this.resumeUpdates();
            }
        });

        // Handle online/offline
        window.addEventListener('online', () => this.onOnline());
        window.addEventListener('offline', () => this.onOffline());
    }

    /**
     * Start polling for data
     */
    startPolling() {
        this.pollTimer = setInterval(() => this.pollData(), this.pollInterval);
        this.pollData(); // Initial poll
    }

    async pollData() {
        if (!navigator.onLine) return;

        try {
            const response = await fetch(`${this.apiBase}/api/dashboard`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.updateState(data);
        } catch (error) {
            console.error('[Dashboard] Poll error:', error);
        }
    }

    /**
     * Update displays
     */
    updateAllDisplays() {
        this.updateHealthDisplay();
        this.updateMinersDisplay();
        this.updateEpochDisplay();
        this.updateBlocksDisplay();
        this.updateTransactionsDisplay();
        this.updateHardwareDistribution();
        this.updateMetricsDisplay();
        this.updateCharts();
    }

    updateHealthDisplay() {
        const statusEl = document.getElementById('network-status');
        const indicatorEl = document.getElementById('network-indicator');
        
        if (this.state.health.status === 'ok' || this.state.health.status === 'demo') {
            statusEl.textContent = 'Online';
            statusEl.className = 'stat-value text-success';
            if (indicatorEl) indicatorEl.className = 'stat-indicator online';
        } else if (this.state.health.status) {
            statusEl.textContent = this.state.health.status;
            statusEl.className = 'stat-value text-warning';
            if (indicatorEl) indicatorEl.className = 'stat-indicator warning';
        } else {
            statusEl.textContent = 'Unknown';
            statusEl.className = 'stat-value text-muted';
            if (indicatorEl) indicatorEl.className = 'stat-indicator';
        }
    }

    updateMinersDisplay() {
        const minersEl = document.getElementById('active-miners');
        if (minersEl) {
            minersEl.textContent = this.state.miners.length;
        }

        // Update top miners table
        this.updateMinersTable();
    }

    updateMinersTable() {
        const tbody = document.getElementById('top-miners');
        if (!tbody) return;

        const sortedMiners = [...this.state.miners]
            .sort((a, b) => (b.score || 0) - (a.score || 0))
            .slice(0, 10);

        if (sortedMiners.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="loading-cell">
                        <span>No miners found</span>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = sortedMiners.map((miner, index) => `
            <tr class="${miner.isNew ? 'new' : ''}">
                <td>${index + 1}</td>
                <td class="mono">${this.escapeHtml(this.shortenAddress(miner.miner_id || miner.miner || 'unknown'))}</td>
                <td><span class="badge badge-${this.getArchitectureTier(miner.device_arch)}">${this.escapeHtml(miner.device_arch || 'Unknown')}</span></td>
                <td class="text-accent">${this.escapeHtml(miner.score || 0)}</td>
                <td>${this.escapeHtml(this.formatNumber(miner.multiplier || 1, 2))}x</td>
                <td><span class="badge badge-active">● ACTIVE</span></td>
            </tr>
        `).join('');

        // Clear new flags
        this.state.miners.forEach(m => m.isNew = false);
    }

    updateEpochDisplay() {
        const epochEl = document.getElementById('current-epoch');
        const potEl = document.getElementById('epoch-pot');
        const progressEl = document.getElementById('epoch-progress');

        if (epochEl) {
            epochEl.textContent = `#${this.state.epoch.epoch || 0}`;
        }

        if (potEl) {
            potEl.textContent = this.formatNumber(this.state.epoch.pot || 0);
        }

        if (progressEl) {
            const slot = this.state.epoch.slot || 0;
            const total = this.state.epoch.blocks_per_epoch || 144;
            const percent = (slot / total) * 100;
            progressEl.style.setProperty('--progress', `${percent}%`);
        }
    }

    updateBlocksDisplay() {
        const container = document.getElementById('recent-blocks');
        if (!container) return;

        const blocks = this.state.blocks.slice(0, 10);
        
        if (blocks.length === 0) {
            container.innerHTML = `
                <div class="loading-state">
                    <span>No blocks yet</span>
                </div>
            `;
            return;
        }

        container.innerHTML = blocks.map(block => `
            <div class="activity-item ${block.isNew ? 'new' : ''}">
                <div class="activity-icon">📦</div>
                <div class="activity-content">
                    <div class="activity-title">Block #${this.escapeHtml(block.height || 0)}</div>
                    <div class="activity-subtitle mono">${this.escapeHtml(this.shortenHash(block.hash || '0x'))}</div>
                </div>
                <div class="activity-meta">
                    <div class="activity-time">${this.formatRelativeTime(block.timestamp)}</div>
                    <div class="activity-value">${this.escapeHtml(block.miners_count || 0)} miners</div>
                </div>
            </div>
        `).join('');

        // Clear new flags
        this.state.blocks.forEach(b => b.isNew = false);
    }

    updateTransactionsDisplay() {
        const container = document.getElementById('recent-transactions');
        if (!container) return;

        const txs = this.state.transactions.slice(0, 10);
        
        if (txs.length === 0) {
            container.innerHTML = `
                <div class="loading-state">
                    <span>No transactions yet</span>
                </div>
            `;
            return;
        }

        container.innerHTML = txs.map(tx => `
            <div class="activity-item ${tx.isNew ? 'new' : ''}">
                <div class="activity-icon">💸</div>
                <div class="activity-content">
                    <div class="activity-title">${this.escapeHtml(String(tx.type || 'transfer').toUpperCase())}</div>
                    <div class="activity-subtitle mono">${this.escapeHtml(this.shortenAddress(tx.from || '0x'))} → ${this.escapeHtml(this.shortenAddress(tx.to || '0x'))}</div>
                </div>
                <div class="activity-meta">
                    <div class="activity-time">${this.formatRelativeTime(tx.timestamp)}</div>
                    <div class="activity-value">${this.escapeHtml(this.formatNumber(tx.amount || 0))} RTC</div>
                </div>
            </div>
        `).join('');

        // Clear new flags
        this.state.transactions.forEach(t => t.isNew = false);
    }

    updateHardwareDistribution() {
        const legendEl = document.getElementById('hardware-legend');
        if (!legendEl) return;

        const breakdown = {};
        this.state.miners.forEach(miner => {
            const arch = miner.device_arch || 'Unknown';
            if (!breakdown[arch]) breakdown[arch] = 0;
            breakdown[arch]++;
        });

        const total = this.state.miners.length;
        const colors = ['#f59e0b', '#3b82f6', '#6b7280', '#8b5cf6', '#10b981', '#ef4444'];
        
        const data = Object.entries(breakdown).map(([arch, count], index) => ({
            label: arch,
            value: count,
            color: colors[index % colors.length],
            percent: ((count / total) * 100).toFixed(1)
        }));

        // Update doughnut chart
        if (this.charts.hardware) {
            this.charts.hardware.update(data);
        }

        // Update legend
        legendEl.innerHTML = data.map(item => `
            <div class="hardware-legend-item">
                <div class="hardware-legend-color" style="background: ${item.color}"></div>
                <div class="hardware-legend-info">
                    <div class="hardware-legend-label">${this.escapeHtml(item.label)}</div>
                    <div class="hardware-legend-value">${this.escapeHtml(item.percent)}%</div>
                </div>
                <div class="hardware-legend-count">${this.escapeHtml(item.value)}</div>
            </div>
        `).join('');
    }

    updateMetricsDisplay() {
        const connectionEl = document.getElementById('metric-connection');
        const updatesEl = document.getElementById('metric-updates');
        const lastUpdateEl = document.getElementById('metric-last-update');
        const uptimeEl = document.getElementById('metric-uptime');

        if (connectionEl) {
            connectionEl.textContent = this.state.connected ? 'WebSocket' : 'Polling';
        }

        if (updatesEl) {
            updatesEl.textContent = this.state.metrics.updatesReceived;
        }

        if (lastUpdateEl && this.state.lastUpdate) {
            lastUpdateEl.textContent = this.formatRelativeTime(this.state.lastUpdate);
        }

        if (uptimeEl) {
            const uptime = Math.floor((Date.now() - this.state.startTime) / 1000);
            uptimeEl.textContent = this.formatUptime(uptime);
        }
    }

    updateConnectionStatus(status) {
        const statusEl = document.getElementById('connection-status');
        const wsStatusEl = document.getElementById('ws-status');
        
        if (!statusEl) return;

        const dot = statusEl.querySelector('.status-dot');
        const text = statusEl.querySelector('.status-text');

        dot.className = 'status-dot ' + status;
        
        switch (status) {
            case 'connected':
                text.textContent = 'Connected';
                if (wsStatusEl) wsStatusEl.textContent = 'Connected';
                break;
            case 'connecting':
                text.textContent = 'Connecting...';
                if (wsStatusEl) wsStatusEl.textContent = 'Connecting...';
                break;
            case 'disconnected':
                text.textContent = 'Disconnected';
                if (wsStatusEl) wsStatusEl.textContent = 'Disconnected';
                break;
            case 'error':
                text.textContent = 'Error';
                if (wsStatusEl) wsStatusEl.textContent = 'Error';
                break;
        }
    }

    updateLastUpdateTime() {
        this.state.lastUpdate = Date.now();
        this.updateMetricsDisplay();
    }

    updateCharts() {
        this.updateBlocksChart();
        this.updateTransactionsChart();
        this.updateMinersChart();
    }

    updateBlocksChart() {
        if (!this.charts.blocks) return;

        // Group blocks by hour (simplified)
        const now = Date.now();
        const hours = 6;
        const data = [];

        for (let i = hours - 1; i >= 0; i--) {
            const hourStart = now - (i + 1) * 3600 * 1000;
            const hourEnd = now - i * 3600 * 1000;
            const count = this.state.blocks.filter(b => {
                const ts = typeof b.timestamp === 'number' ? b.timestamp * 1000 : new Date(b.timestamp).getTime();
                return ts >= hourStart && ts < hourEnd;
            }).length;
            data.push(count);
        }

        this.charts.blocks.update(data);
    }

    updateTransactionsChart() {
        if (!this.charts.transactions) return;

        // Group transactions by hour (simplified)
        const now = Date.now();
        const hours = 6;
        const data = [];

        for (let i = hours - 1; i >= 0; i--) {
            const hourStart = now - (i + 1) * 3600 * 1000;
            const hourEnd = now - i * 3600 * 1000;
            const count = this.state.transactions.filter(tx => {
                const ts = typeof tx.timestamp === 'number' ? tx.timestamp * 1000 : new Date(tx.timestamp).getTime();
                return ts >= hourStart && ts < hourEnd;
            }).length;
            data.push(count);
        }

        this.charts.transactions.update(data);
    }

    updateMinersChart() {
        if (!this.charts.miners) return;

        // Track miners count over time
        this.minersHistory.push(this.state.miners.length);
        if (this.minersHistory.length > 20) {
            this.minersHistory.shift();
        }

        this.charts.miners.update(this.minersHistory);
    }

    highlightNewBlock(block) {
        block.isNew = true;
        setTimeout(() => { block.isNew = false; }, 2000);
    }

    /**
     * Theme toggle
     */
    toggleTheme() {
        document.body.classList.toggle('light-theme');
        const isLight = document.body.classList.contains('light-theme');
        localStorage.setItem('theme', isLight ? 'light' : 'dark');
        
        const btn = document.getElementById('theme-toggle');
        if (btn) {
            btn.textContent = isLight ? '☀️' : '🌙';
        }
    }

    /**
     * Pause/resume updates
     */
    pauseUpdates() {
        if (this.pollTimer) {
            clearInterval(this.pollTimer);
            this.pollTimer = null;
        }
    }

    resumeUpdates() {
        if (!this.pollTimer) {
            this.startPolling();
        }
    }

    onOnline() {
        console.log('[Dashboard] Back online');
        this.resumeUpdates();
        this.pollData();
    }

    onOffline() {
        console.log('[Dashboard] Went offline');
        this.pauseUpdates();
        this.updateConnectionStatus('disconnected');
    }

    /**
     * Utility functions
     */
    shortenHash(hash, chars = 8) {
        if (!hash) return '';
        if (hash.length <= chars * 2) return hash;
        return `${hash.slice(0, chars)}...${hash.slice(-chars)}`;
    }

    shortenAddress(addr, chars = 6) {
        if (!addr) return '';
        if (addr.length <= chars * 2) return addr;
        return `${addr.slice(0, chars)}...${addr.slice(-chars)}`;
    }

    formatNumber(num, decimals = 2) {
        if (num === null || num === undefined) return '0';
        return Number(num).toLocaleString(undefined, {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });
    }

    formatRelativeTime(ts) {
        if (!ts) return '';
        const timestamp = typeof ts === 'number' ? ts * 1000 : new Date(ts).getTime();
        if (isNaN(timestamp)) return '';
        const diff = Date.now() - timestamp;
        const seconds = Math.floor(diff / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (days > 0) return `${days}d ago`;
        if (hours > 0) return `${hours}h ago`;
        if (minutes > 0) return `${minutes}m ago`;
        return 'Just now';
    }

    formatUptime(seconds) {
        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        return `${days}d ${hours}h ${mins}m`;
    }

    escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, char => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        })[char]);
    }

    getArchitectureTier(arch) {
        if (!arch) return 'modern';
        const archLower = String(arch).toLowerCase();
        if (archLower.includes('g3') || archLower.includes('g4') || archLower.includes('g5') ||
            archLower.includes('powerpc') || archLower.includes('sparc')) return 'vintage';
        if (archLower.includes('pentium') || archLower.includes('core 2') ||
            archLower.includes('486') || archLower.includes('retro')) return 'retro';
        if (archLower.includes('m1') || archLower.includes('m2') || archLower.includes('apple silicon')) return 'classic';
        if (archLower.includes('ancient') || archLower.includes('legacy')) return 'ancient';
        return 'modern';
    }
}

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new DashboardApp();
});
