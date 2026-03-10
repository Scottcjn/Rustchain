/**
 * RustChain Explorer - Real-time WebSocket Client
 * Provides live data streaming for dashboard updates
 */

class RealtimeClient {
    constructor(options = {}) {
        this.wsUrl = options.wsUrl || 'ws://localhost:8080/ws';
        this.httpBase = options.httpBase || 'http://localhost:8080';
        this.reconnectInterval = options.reconnectInterval || 3000;
        this.maxReconnectAttempts = options.maxReconnectAttempts || 5;
        this.heartbeatInterval = options.heartbeatInterval || 30000;
        
        this.ws = null;
        this.reconnectAttempts = 0;
        this.listeners = new Map();
        this.state = {
            connected: false,
            lastMessage: null,
            metrics: {
                blocksReceived: 0,
                transactionsReceived: 0,
                minersUpdated: 0,
                reconnects: 0
            }
        };
        this.heartbeatTimer = null;
        this.reconnectTimer = null;
    }

    /**
     * Connect to WebSocket server
     */
    connect() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            console.log('[Realtime] Already connected');
            return Promise.resolve();
        }

        return new Promise((resolve, reject) => {
            try {
                this.ws = new WebSocket(this.wsUrl);

                this.ws.onopen = () => {
                    console.log('[Realtime] Connected to WebSocket');
                    this.state.connected = true;
                    this.reconnectAttempts = 0;
                    this.startHeartbeat();
                    this.emit('connected', { timestamp: Date.now() });
                    resolve();
                };

                this.ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        this.state.lastMessage = data;
                        this.handleMessage(data);
                    } catch (error) {
                        console.error('[Realtime] Failed to parse message:', error);
                    }
                };

                this.ws.onclose = (event) => {
                    console.log('[Realtime] Connection closed:', event.code, event.reason);
                    this.state.connected = false;
                    this.stopHeartbeat();
                    this.emit('disconnected', { code: event.code, reason: event.reason });
                    this.scheduleReconnect();
                };

                this.ws.onerror = (error) => {
                    console.error('[Realtime] WebSocket error:', error);
                    this.emit('error', { error: 'WebSocket error' });
                    reject(error);
                };
            } catch (error) {
                console.error('[Realtime] Failed to create WebSocket:', error);
                reject(error);
            }
        });
    }

    /**
     * Disconnect from WebSocket server
     */
    disconnect() {
        this.stopHeartbeat();
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        if (this.ws) {
            this.ws.close(1000, 'Client disconnect');
            this.ws = null;
        }
        this.state.connected = false;
        this.emit('disconnected', { code: 1000, reason: 'Client disconnect' });
    }

    /**
     * Handle incoming WebSocket messages
     */
    handleMessage(data) {
        const { type, payload } = data;

        switch (type) {
            case 'block':
                this.state.metrics.blocksReceived++;
                this.emit('block', payload);
                break;
            case 'transaction':
                this.state.metrics.transactionsReceived++;
                this.emit('transaction', payload);
                break;
            case 'miner_update':
                this.state.metrics.minersUpdated++;
                this.emit('miner_update', payload);
                break;
            case 'epoch_update':
                this.emit('epoch_update', payload);
                break;
            case 'health':
                this.emit('health', payload);
                break;
            case 'metrics':
                this.emit('metrics', payload);
                break;
            case 'pong':
                // Heartbeat response
                break;
            default:
                console.log('[Realtime] Unknown message type:', type);
        }
    }

    /**
     * Start heartbeat timer
     */
    startHeartbeat() {
        this.stopHeartbeat();
        this.heartbeatTimer = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, this.heartbeatInterval);
    }

    /**
     * Stop heartbeat timer
     */
    stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }

    /**
     * Schedule reconnection attempt
     */
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('[Realtime] Max reconnection attempts reached');
            this.emit('max_reconnects_reached', { attempts: this.reconnectAttempts });
            return;
        }

        this.reconnectAttempts++;
        this.state.metrics.reconnects++;
        const delay = this.reconnectInterval * Math.pow(2, this.reconnectAttempts - 1);

        console.log(`[Realtime] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

        this.reconnectTimer = setTimeout(() => {
            this.connect().catch(() => {});
        }, delay);
    }

    /**
     * Subscribe to event type
     */
    on(eventType, callback) {
        if (!this.listeners.has(eventType)) {
            this.listeners.set(eventType, new Set());
        }
        this.listeners.get(eventType).add(callback);
        return () => this.off(eventType, callback);
    }

    /**
     * Unsubscribe from event type
     */
    off(eventType, callback) {
        const listeners = this.listeners.get(eventType);
        if (listeners) {
            listeners.delete(callback);
        }
    }

    /**
     * Emit event to all listeners
     */
    emit(eventType, data) {
        const listeners = this.listeners.get(eventType);
        if (listeners) {
            listeners.forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`[Realtime] Error in ${eventType} listener:`, error);
                }
            });
        }
    }

    /**
     * Send message to server
     */
    send(type, payload = {}) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.warn('[Realtime] Cannot send message: not connected');
            return false;
        }
        this.ws.send(JSON.stringify({ type, payload }));
        return true;
    }

    /**
     * Get current connection state
     */
    getState() {
        return { ...this.state };
    }

    /**
     * Get connection metrics
     */
    getMetrics() {
        return { ...this.state.metrics };
    }
}

// Fallback polling client for environments without WebSocket support
class PollingClient {
    constructor(options = {}) {
        this.httpBase = options.httpBase || 'http://localhost:8080';
        this.pollInterval = options.pollInterval || 5000;
        this.listeners = new Map();
        this.state = {
            connected: false,
            lastPoll: null,
            metrics: {
                pollsExecuted: 0,
                errors: 0
            }
        };
        this.pollTimer = null;
        this.lastKnownState = {
            blocks: [],
            transactions: [],
            miners: [],
            epoch: null
        };
    }

    /**
     * Start polling
     */
    connect() {
        this.state.connected = true;
        this.emit('connected', { timestamp: Date.now(), mode: 'polling' });
        this.startPolling();
        return Promise.resolve();
    }

    /**
     * Stop polling
     */
    disconnect() {
        this.stopPolling();
        this.state.connected = false;
        this.emit('disconnected', { code: 1000, reason: 'Client disconnect' });
    }

    /**
     * Start polling timer
     */
    startPolling() {
        this.stopPolling();
        this.pollTimer = setInterval(() => this.poll(), this.pollInterval);
        this.poll(); // Initial poll
    }

    /**
     * Stop polling timer
     */
    stopPolling() {
        if (this.pollTimer) {
            clearInterval(this.pollTimer);
            this.pollTimer = null;
        }
    }

    /**
     * Execute poll cycle
     */
    async poll() {
        this.state.metrics.pollsExecuted++;
        this.state.lastPoll = Date.now();

        try {
            const [blocks, transactions, miners, epoch] = await Promise.all([
                this.fetchJSON('/blocks'),
                this.fetchJSON('/api/transactions'),
                this.fetchJSON('/api/miners'),
                this.fetchJSON('/epoch')
            ]);

            // Detect changes and emit events
            this.detectChanges(blocks, transactions, miners, epoch);

            this.emit('metrics', {
                blocks: blocks.length,
                transactions: transactions.length,
                miners: miners.length,
                epoch: epoch
            });
        } catch (error) {
            this.state.metrics.errors++;
            this.emit('error', { error: error.message, type: 'poll' });
        }
    }

    /**
     * Detect changes between poll cycles
     */
    detectChanges(blocks, transactions, miners, epoch) {
        // New blocks
        if (blocks.length > this.lastKnownState.blocks.length) {
            const newBlocks = blocks.slice(0, this.lastKnownState.blocks.length);
            newBlocks.forEach(block => this.emit('block', block));
        }

        // New transactions
        if (transactions.length > this.lastKnownState.transactions.length) {
            const newTxs = transactions.slice(0, this.lastKnownState.transactions.length);
            newTxs.forEach(tx => this.emit('transaction', tx));
        }

        // Miner updates (simplified - check if any miner changed)
        if (JSON.stringify(miners) !== JSON.stringify(this.lastKnownState.miners)) {
            this.emit('miner_update', { miners });
        }

        // Epoch updates
        if (JSON.stringify(epoch) !== JSON.stringify(this.lastKnownState.epoch)) {
            this.emit('epoch_update', epoch);
        }

        // Update last known state
        this.lastKnownState = { blocks, transactions, miners, epoch };
    }

    /**
     * Fetch JSON from HTTP endpoint
     */
    async fetchJSON(endpoint) {
        const response = await fetch(`${this.httpBase}${endpoint}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return response.json();
    }

    /**
     * Subscribe to event type
     */
    on(eventType, callback) {
        if (!this.listeners.has(eventType)) {
            this.listeners.set(eventType, new Set());
        }
        this.listeners.get(eventType).add(callback);
        return () => this.off(eventType, callback);
    }

    /**
     * Unsubscribe from event type
     */
    off(eventType, callback) {
        const listeners = this.listeners.get(eventType);
        if (listeners) {
            listeners.delete(callback);
        }
    }

    /**
     * Emit event to all listeners
     */
    emit(eventType, data) {
        const listeners = this.listeners.get(eventType);
        if (listeners) {
            listeners.forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`[Polling] Error in ${eventType} listener:`, error);
                }
            });
        }
    }

    /**
     * Get current state
     */
    getState() {
        return { ...this.state };
    }

    /**
     * Get metrics
     */
    getMetrics() {
        return { ...this.state.metrics };
    }
}

// Auto-detect and create appropriate client
function createRealtimeClient(options = {}) {
    const hasWebSocket = typeof WebSocket !== 'undefined';
    
    if (hasWebSocket && options.forceWebSocket !== false) {
        return new RealtimeClient(options);
    } else {
        return new PollingClient(options);
    }
}

// Export for use in other modules
window.RealtimeClient = RealtimeClient;
window.PollingClient = PollingClient;
window.createRealtimeClient = createRealtimeClient;
