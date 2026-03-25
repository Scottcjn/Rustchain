/**
 * RustChain Explorer - WebSocket Client
 * Issue #2295 - Real-time WebSocket Feed (75 RTC)
 * 
 * Features:
 * - WebSocket connection to RustChain node
 * - Live block feed (new blocks without refresh)
 * - Live attestation feed (miner attestations stream)
 * - Connection status indicator
 * - Auto-reconnect on disconnect
 * - Works with nginx proxy config
 */

// WebSocket Client Module
const RustChainWebSocket = (function() {
    'use strict';

    // Configuration
    const WS_CONFIG = {
        // WebSocket endpoint - will be constructed from current page origin
        get WS_URL() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = window.location.host;
            // Try different WebSocket endpoints
            return `${protocol}//${host}/ws`;
        },
        WS_FALLBACK_URLS: [
            // Fallback URLs to try
            '/ws',
            '/socket.io/?EIO=4&transport=websocket',
            ':8765'  // Direct WebSocket port
        ],
        RECONNECT_INTERVAL: 3000,      // 3 seconds
        MAX_RECONNECT_ATTEMPTS: 10,
        PING_INTERVAL: 25000,          // 25 seconds
        PONG_TIMEOUT: 35000,           // 35 seconds
        MAX_MESSAGES_QUEUE: 100
    };

    // State
    const wsState = {
        socket: null,
        isConnected: false,
        reconnectAttempts: 0,
        lastPong: null,
        pingInterval: null,
        pongTimeout: null,
        messageQueue: [],
        listeners: new Map(),
        connectionHistory: []
    };

    // Connection status enum
    const ConnectionStatus = {
        CONNECTING: 'connecting',
        CONNECTED: 'connected',
        DISCONNECTED: 'disconnected',
        RECONNECTING: 'reconnecting',
        ERROR: 'error'
    };

    // Current status
    let currentStatus = ConnectionStatus.DISCONNECTED;

    /**
     * Initialize WebSocket connection
     */
    function connect() {
        if (wsState.socket && wsState.socket.readyState === WebSocket.OPEN) {
            console.log('[WS] Already connected');
            return;
        }

        updateStatus(ConnectionStatus.CONNECTING);
        logConnection('Attempting to connect...');

        // Try Socket.IO first (for Flask-SocketIO compatibility)
        if (typeof io !== 'undefined') {
            connectSocketIO();
        } else {
            // Fallback to native WebSocket
            connectNative();
        }
    }

    /**
     * Connect using Socket.IO client
     */
    function connectSocketIO() {
        try {
            const socketUrl = window.location.origin;
            console.log('[WS] Connecting via Socket.IO to:', socketUrl);
            
            wsState.socket = io(socketUrl, {
                transports: ['websocket', 'polling'],
                reconnection: true,
                reconnectionAttempts: WS_CONFIG.MAX_RECONNECT_ATTEMPTS,
                reconnectionDelay: WS_CONFIG.RECONNECT_INTERVAL,
                timeout: 10000
            });

            setupSocketIOEvents();
        } catch (error) {
            console.error('[WS] Socket.IO connection failed:', error);
            // Fallback to native WebSocket
            connectNative();
        }
    }

    /**
     * Set up Socket.IO event handlers
     */
    function setupSocketIOEvents() {
        const socket = wsState.socket;

        socket.on('connect', () => {
            console.log('[WS] Socket.IO connected');
            onConnected();
        });

        socket.on('disconnect', (reason) => {
            console.log('[WS] Socket.IO disconnected:', reason);
            onDisconnected(reason);
        });

        socket.on('connect_error', (error) => {
            console.error('[WS] Socket.IO connection error:', error);
            onError(error);
        });

        socket.on('connected', (data) => {
            console.log('[WS] Received welcome:', data);
            emit('connected', data);
        });

        socket.on('connection_status', (data) => {
            console.log('[WS] Connection status:', data);
            emit('connection_status', data);
        });

        socket.on('block', (data) => {
            console.log('[WS] New block:', data);
            emit('block', data);
            handleNewBlock(data);
        });

        socket.on('attestation', (data) => {
            console.log('[WS] New attestation:', data);
            emit('attestation', data);
            handleNewAttestation(data);
        });

        socket.on('epoch_settlement', (data) => {
            console.log('[WS] Epoch settlement:', data);
            emit('epoch_settlement', data);
            handleEpochSettlement(data);
        });

        socket.on('miner_update', (data) => {
            console.log('[WS] Miner update:', data);
            emit('miner_update', data);
            handleMinerUpdate(data);
        });

        socket.on('epoch_update', (data) => {
            console.log('[WS] Epoch update:', data);
            emit('epoch_update', data);
            handleEpochUpdate(data);
        });

        socket.on('health', (data) => {
            console.log('[WS] Health update:', data);
            emit('health', data);
            handleHealthUpdate(data);
        });

        socket.on('pong', (data) => {
            wsState.lastPong = Date.now();
            emit('pong', data);
        });
    }

    /**
     * Connect using native WebSocket
     */
    function connectNative() {
        const url = WS_CONFIG.WS_URL;
        console.log('[WS] Connecting to native WebSocket:', url);

        try {
            wsState.socket = new WebSocket(url);
            setupNativeEvents();
        } catch (error) {
            console.error('[WS] Native WebSocket connection failed:', error);
            onError(error);
            scheduleReconnect();
        }
    }

    /**
     * Set up native WebSocket event handlers
     */
    function setupNativeEvents() {
        const socket = wsState.socket;

        socket.onopen = () => {
            console.log('[WS] Native WebSocket connected');
            onConnected();
            startPingPong();
        };

        socket.onclose = (event) => {
            console.log('[WS] Native WebSocket closed:', event.code, event.reason);
            onDisconnected(`Closed: ${event.code}`);
            stopPingPong();
        };

        socket.onerror = (error) => {
            console.error('[WS] Native WebSocket error:', error);
            onError(error);
        };

        socket.onmessage = (event) => {
            handleMessage(event.data);
        };
    }

    /**
     * Handle incoming message
     */
    function handleMessage(data) {
        try {
            const message = JSON.parse(data);
            const { type, payload } = message;

            switch (type) {
                case 'block':
                    handleNewBlock(payload);
                    break;
                case 'attestation':
                    handleNewAttestation(payload);
                    break;
                case 'epoch_settlement':
                    handleEpochSettlement(payload);
                    break;
                case 'miner_update':
                    handleMinerUpdate(payload);
                    break;
                case 'epoch_update':
                    handleEpochUpdate(payload);
                    break;
                case 'health':
                    handleHealthUpdate(payload);
                    break;
                case 'pong':
                    wsState.lastPong = Date.now();
                    break;
                default:
                    console.log('[WS] Unknown message type:', type);
            }

            emit(type, payload);
        } catch (error) {
            console.error('[WS] Error parsing message:', error);
        }
    }

    /**
     * Handle new block event
     */
    function handleNewBlock(block) {
        if (window.RustChainExplorer && window.RustChainExplorer.state) {
            // Add to blocks array
            const blocks = window.RustChainExplorer.state.blocks || [];
            blocks.unshift(block);
            window.RustChainExplorer.state.blocks = blocks.slice(0, 50);
            
            // Trigger UI update
            if (typeof renderBlocksTable === 'function') {
                renderBlocksTable();
            }
            
            // Show notification
            showNotification('block', `New Block #${block.height}`, 
                `Miners: ${block.miners_count || 0} | Reward: ${block.reward || 0} RTC`);
        }
    }

    /**
     * Handle new attestation event
     */
    function handleNewAttestation(attestation) {
        if (window.RustChainExplorer && window.RustChainExplorer.state) {
            // Update miners if this miner is new or updated
            const miners = window.RustChainExplorer.state.miners || [];
            const existingIndex = miners.findIndex(m => m.miner_id === attestation.miner_id);
            
            if (existingIndex >= 0) {
                miners[existingIndex] = { ...miners[existingIndex], ...attestation };
            } else {
                miners.push(attestation);
            }
            
            window.RustChainExplorer.state.miners = miners;
            
            // Trigger UI update
            if (typeof renderMinersTable === 'function') {
                renderMinersTable();
            }
            
            // Show notification
            showNotification('attestation', 'New Attestation', 
                `Miner: ${attestation.miner_id?.slice(0, 16)}... | Arch: ${attestation.device_arch}`);
        }
    }

    /**
     * Handle epoch settlement event (bonus feature)
     */
    function handleEpochSettlement(settlement) {
        showNotification('settlement', `🎉 Epoch #${settlement.epoch} Settled!`, 
            `Total Reward: ${settlement.total_reward?.toFixed(2)} RTC | Miners: ${settlement.miners_count}`);
        
        // Play sound notification (bonus feature)
        if (window.playNotificationSound) {
            window.playNotificationSound('settlement');
        }
    }

    /**
     * Handle miner update event
     */
    function handleMinerUpdate(data) {
        if (window.RustChainExplorer && window.RustChainExplorer.state && data.miners) {
            window.RustChainExplorer.state.miners = data.miners;
            
            if (typeof renderMinersTable === 'function') {
                renderMinersTable();
            }
            if (typeof renderHardwareBreakdown === 'function') {
                renderHardwareBreakdown();
            }
        }
    }

    /**
     * Handle epoch update event
     */
    function handleEpochUpdate(epoch) {
        if (window.RustChainExplorer && window.RustChainExplorer.state) {
            window.RustChainExplorer.state.epoch = epoch;
            
            if (typeof renderEpochStats === 'function') {
                renderEpochStats();
            }
        }
    }

    /**
     * Handle health update event
     */
    function handleHealthUpdate(health) {
        if (window.RustChainExplorer && window.RustChainExplorer.state) {
            window.RustChainExplorer.state.health = health;
            
            if (typeof renderStatusBar === 'function') {
                renderStatusBar();
            }
        }
    }

    /**
     * On connected callback
     */
    function onConnected() {
        wsState.isConnected = true;
        wsState.reconnectAttempts = 0;
        updateStatus(ConnectionStatus.CONNECTED);
        logConnection('Connected successfully');
        
        // Show connection status
        updateConnectionIndicator(true);
        
        // Request initial state
        if (wsState.socket && typeof wsState.socket.emit === 'function') {
            wsState.socket.emit('request_state');
        }
    }

    /**
     * On disconnected callback
     */
    function onDisconnected(reason) {
        wsState.isConnected = false;
        updateStatus(ConnectionStatus.DISCONNECTED);
        logConnection(`Disconnected: ${reason}`);
        
        // Update connection indicator
        updateConnectionIndicator(false);
        
        // Schedule reconnect
        scheduleReconnect();
    }

    /**
     * On error callback
     */
    function onError(error) {
        updateStatus(ConnectionStatus.ERROR);
        logConnection(`Error: ${error}`);
    }

    /**
     * Schedule reconnection attempt
     */
    function scheduleReconnect() {
        if (wsState.reconnectAttempts >= WS_CONFIG.MAX_RECONNECT_ATTEMPTS) {
            console.log('[WS] Max reconnect attempts reached');
            updateStatus(ConnectionStatus.DISCONNECTED);
            return;
        }

        wsState.reconnectAttempts++;
        updateStatus(ConnectionStatus.RECONNECTING);
        logConnection(`Reconnecting in ${WS_CONFIG.RECONNECT_INTERVAL / 1000}s (attempt ${wsState.reconnectAttempts})`);

        setTimeout(() => {
            connect();
        }, WS_CONFIG.RECONNECT_INTERVAL);
    }

    /**
     * Start ping-pong heartbeat
     */
    function startPingPong() {
        stopPingPong();
        
        wsState.pingInterval = setInterval(() => {
            if (wsState.socket && wsState.isConnected) {
                if (typeof wsState.socket.emit === 'function') {
                    wsState.socket.emit('ping');
                } else if (wsState.socket.readyState === WebSocket.OPEN) {
                    wsState.socket.send(JSON.stringify({ type: 'ping' }));
                }
            }
        }, WS_CONFIG.PING_INTERVAL);

        // Check for pong timeout
        wsState.pongTimeout = setInterval(() => {
            if (wsState.lastPong && Date.now() - wsState.lastPong > WS_CONFIG.PONG_TIMEOUT) {
                console.log('[WS] Pong timeout, reconnecting...');
                disconnect();
                connect();
            }
        }, WS_CONFIG.PONG_TIMEOUT);
    }

    /**
     * Stop ping-pong heartbeat
     */
    function stopPingPong() {
        if (wsState.pingInterval) {
            clearInterval(wsState.pingInterval);
            wsState.pingInterval = null;
        }
        if (wsState.pongTimeout) {
            clearInterval(wsState.pongTimeout);
            wsState.pongTimeout = null;
        }
    }

    /**
     * Disconnect WebSocket
     */
    function disconnect() {
        stopPingPong();
        
        if (wsState.socket) {
            if (typeof wsState.socket.disconnect === 'function') {
                wsState.socket.disconnect();
            } else if (typeof wsState.socket.close === 'function') {
                wsState.socket.close();
            }
            wsState.socket = null;
        }
        
        wsState.isConnected = false;
        updateStatus(ConnectionStatus.DISCONNECTED);
        updateConnectionIndicator(false);
    }

    /**
     * Update connection status
     */
    function updateStatus(status) {
        currentStatus = status;
        emit('status', { status });
    }

    /**
     * Update connection indicator UI
     */
    function updateConnectionIndicator(connected) {
        const indicator = document.getElementById('ws-connection-indicator');
        const statusText = document.getElementById('ws-status-text');
        
        if (indicator) {
            indicator.className = 'ws-indicator ' + (connected ? 'connected' : 'disconnected');
            indicator.title = connected ? 'WebSocket Connected' : 'WebSocket Disconnected';
        }
        
        if (statusText) {
            statusText.textContent = connected ? 'Live' : 'Offline';
            statusText.className = 'ws-status-text ' + (connected ? 'connected' : 'disconnected');
        }
    }

    /**
     * Log connection event
     */
    function logConnection(message) {
        const timestamp = new Date().toLocaleTimeString();
        wsState.connectionHistory.push({ timestamp, message });
        
        // Keep only last 50 entries
        if (wsState.connectionHistory.length > 50) {
            wsState.connectionHistory.shift();
        }
        
        console.log(`[WS] ${timestamp} - ${message}`);
    }

    /**
     * Show notification
     */
    function showNotification(type, title, body) {
        // Create notification element
        const container = document.getElementById('ws-notifications');
        if (!container) return;

        const notification = document.createElement('div');
        notification.className = `ws-notification ws-notification-${type}`;
        notification.innerHTML = `
            <div class="ws-notification-header">
                <span class="ws-notification-icon">${getNotificationIcon(type)}</span>
                <span class="ws-notification-title">${escapeHtml(title)}</span>
                <button class="ws-notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
            <div class="ws-notification-body">${escapeHtml(body)}</div>
        `;

        container.appendChild(notification);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.classList.add('ws-notification-fade-out');
                setTimeout(() => notification.remove(), 300);
            }
        }, 5000);
    }

    /**
     * Get notification icon
     */
    function getNotificationIcon(type) {
        const icons = {
            block: '📦',
            attestation: '⛏️',
            settlement: '🎉',
            default: '🔔'
        };
        return icons[type] || icons.default;
    }

    /**
     * Escape HTML
     */
    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    /**
     * Event emitter - add listener
     */
    function on(event, callback) {
        if (!wsState.listeners.has(event)) {
            wsState.listeners.set(event, []);
        }
        wsState.listeners.get(event).push(callback);
    }

    /**
     * Event emitter - remove listener
     */
    function off(event, callback) {
        if (wsState.listeners.has(event)) {
            const callbacks = wsState.listeners.get(event);
            const index = callbacks.indexOf(callback);
            if (index > -1) {
                callbacks.splice(index, 1);
            }
        }
    }

    /**
     * Event emitter - emit event
     */
    function emit(event, data) {
        if (wsState.listeners.has(event)) {
            wsState.listeners.get(event).forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`[WS] Error in listener for ${event}:`, error);
                }
            });
        }
    }

    /**
     * Get current state
     */
    function getState() {
        return {
            isConnected: wsState.isConnected,
            status: currentStatus,
            reconnectAttempts: wsState.reconnectAttempts,
            connectionHistory: wsState.connectionHistory.slice(-10)
        };
    }

    /**
     * Request current state from server
     */
    function requestState() {
        if (wsState.socket && wsState.isConnected) {
            if (typeof wsState.socket.emit === 'function') {
                wsState.socket.emit('request_state');
            } else if (wsState.socket.readyState === WebSocket.OPEN) {
                wsState.socket.send(JSON.stringify({ type: 'request_state' }));
            }
        }
    }

    // Public API
    return {
        connect,
        disconnect,
        getState,
        requestState,
        on,
        off,
        ConnectionStatus
    };
})();

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('[WS] Initializing WebSocket client...');
    
    // Load Socket.IO client library dynamically if not present
    if (typeof io === 'undefined') {
        const script = document.createElement('script');
        script.src = 'https://cdn.socket.io/4.7.2/socket.io.min.js';
        script.onload = () => {
            console.log('[WS] Socket.IO loaded');
            RustChainWebSocket.connect();
        };
        script.onerror = () => {
            console.log('[WS] Socket.IO load failed, using native WebSocket');
            RustChainWebSocket.connect();
        };
        document.head.appendChild(script);
    } else {
        RustChainWebSocket.connect();
    }
});

// Export for global access
window.RustChainWebSocket = RustChainWebSocket;