/**
 * RustChain Block Explorer - Real-Time WebSocket Client
 * Connects to the RustChain node WebSocket feed (Socket.IO /ws/feed)
 * and displays live blocks, attestations, and epoch settlements.
 */

(function () {
    'use strict';

    // ─── Config ────────────────────────────────────────────────────────────────
    const WS_URL = getQueryParam('ws') || 'ws://localhost:5001';
    const NAMESPACE = '/ws/feed';
    const MAX_BLOCKS = 50;
    const MAX_ATTESTATIONS = 100;
    const MAX_LOG_ENTRIES = 200;
    const RECONNECT_BASE_MS = 1000;
    const RECONNECT_MAX_MS = 30000;

    // ─── State ─────────────────────────────────────────────────────────────────
    let socket = null;
    let reconnectAttempts = 0;
    let reconnectTimer = null;
    let blocksFound = 0;
    let attestationsCount = 0;
    let lastSlot = null;
    let lastEpoch = null;
    let eventTimestamps = [];
    let showAllEvents = true;

    // ─── DOM Refs ──────────────────────────────────────────────────────────────
    const $ = (id) => document.getElementById(id);
    const statusDot = $('statusDot');
    const statusText = $('statusText');
    const statEpoch = $('statEpoch');
    const statSlot = $('statSlot');
    const statMiners = $('statMiners');
    const statBlocks = $('statBlocks');
    const statAttestations = $('statAttestations');
    const statLastUpdate = $('statLastUpdate');
    const blocksFeed = $('blocksFeed');
    const attestationsFeed = $('attestationsFeed');
    const eventLog = $('eventLog');
    const nodeUrl = $('nodeUrl');
    const epochNotification = $('epochNotification');
    const newEpochNum = $('newEpochNum');
    const activityRate = $('activityRate');
    const showAllEventsChk = $('showAllEvents');

    // ─── Utilities ────────────────────────────────────────────────────────────
    function getQueryParam(key) {
        const params = new URLSearchParams(window.location.search);
        return params.get(key);
    }

    function formatTime(ts) {
        if (!ts) return '--';
        const d = new Date(ts * 1000);
        return d.toLocaleTimeString();
    }

    function timeAgo(ts) {
        if (!ts) return '';
        const secs = Math.floor((Date.now() / 1000) - ts);
        if (secs < 60) return `${secs}s ago`;
        const mins = Math.floor(secs / 60);
        if (mins < 60) return `${mins}m ago`;
        return `${Math.floor(mins / 60)}h ago`;
    }

    function truncate(str, len = 12) {
        if (!str) return '--';
        return str.length > len ? str.slice(0, len) + '...' : str;
    }

    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function getRelativeTime() {
        const now = Date.now();
        return now;
    }

    function formatNumber(n) {
        if (n === null || n === undefined || n === '--') return '--';
        return Number(n).toLocaleString();
    }

    // ─── Connection Management ─────────────────────────────────────────────────
    function setStatus(state, msg) {
        statusDot.className = 'status-dot status-' + state;
        statusText.textContent = msg;
        nodeUrl.textContent = WS_URL;
    }

    function connect() {
        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }

        setStatus('connecting', 'Connecting...');

        const fullUrl = WS_URL + (WS_URL.endsWith('/') ? '' : '') + NAMESPACE;

        try {
            socket = io(fullUrl, {
                transports: ['websocket', 'polling'],
                reconnection: false, // we handle reconnect manually
                timeout: 10000,
            });
        } catch (e) {
            scheduleReconnect();
            return;
        }

        socket.on('connect', onConnect);
        socket.on('disconnect', onDisconnect);
        socket.on('connect_error', onConnectError);
        socket.on('connected', onConnected);
        socket.on('event', onEvent);
        socket.on('subscribed', onSubscribed);
        socket.on('pong', onPong);
    }

    function scheduleReconnect() {
        if (reconnectTimer) return;
        const delay = Math.min(RECONNECT_BASE_MS * Math.pow(2, reconnectAttempts), RECONNECT_MAX_MS);
        reconnectAttempts++;
        setStatus('reconnecting', `Reconnecting in ${Math.round(delay / 1000)}s... (attempt ${reconnectAttempts})`);
        reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            connect();
        }, delay);
    }

    // ─── Event Handlers ───────────────────────────────────────────────────────
    function onConnect() {
        reconnectAttempts = 0;
        setStatus('connected', 'Connected');
    }

    function onConnected(data) {
        setStatus('connected', 'Connected to ' + (data.node || WS_URL));
        addLogEntry('system', 'Connected to node: ' + escapeHtml(data.node || WS_URL));
        // Start ping interval
        setInterval(() => {
            if (socket && socket.connected) socket.emit('ping');
        }, 30000);
    }

    function onDisconnect() {
        setStatus('disconnected', 'Disconnected');
        scheduleReconnect();
    }

    function onConnectError(err) {
        setStatus('error', 'Connection error');
        scheduleReconnect();
    }

    function onSubscribed(data) {
        addLogEntry('system', 'Subscribed to: ' + (data.types === 'all' ? 'all events' : data.types.join(', ')));
    }

    function onPong(data) {
        // heartbeat acknowledged
    }

    function onEvent(event) {
        trackActivity();
        const type = event.type;
        const data = event.data;
        const ts = event.ts;

        updateLastUpdate(ts);

        if (type === 'new_block') {
            handleNewBlock(data, ts);
        } else if (type === 'attestation') {
            handleAttestation(data, ts);
        } else if (type === 'epoch_settlement') {
            handleEpochSettlement(data, ts);
        } else if (showAllEvents) {
            addLogEntry('event', `[${type}] ${JSON.stringify(data)}`);
        }
    }

    // ─── Event Processors ─────────────────────────────────────────────────────
    function handleNewBlock(data, ts) {
        blocksFound++;
        lastSlot = data.slot;
        lastEpoch = data.epoch;
        statBlocks.textContent = blocksFound;
        statSlot.textContent = formatNumber(data.slot);
        if (data.epoch) statEpoch.textContent = formatNumber(data.epoch);

        const el = document.createElement('div');
        el.className = 'block-item new';
        el.innerHTML = `
            <div class="block-icon">&#128992;</div>
            <div class="block-info">
                <div class="block-title">Block #${escapeHtml(data.slot || data.epoch_slot || '?')}</div>
                <div class="block-meta">
                    Epoch: ${escapeHtml(data.epoch)} &middot;
                    Slot: ${escapeHtml(data.slot)} &middot;
                    Time: ${formatTime(ts)}
                </div>
            </div>
        `;

        // Remove empty state if present
        const empty = blocksFeed.querySelector('.empty-state');
        if (empty) empty.remove();

        blocksFeed.insertBefore(el, blocksFeed.firstChild);

        // Trim
        while (blocksFeed.children.length > MAX_BLOCKS) {
            blocksFeed.removeChild(blocksFeed.lastChild);
        }

        // Flash animation
        setTimeout(() => el.classList.remove('new'), 1000);

        addLogEntry('block', `Block #${data.slot || '?'} found at epoch ${data.epoch}`);
    }

    function handleAttestation(data, ts) {
        attestationsCount++;
        statAttestations.textContent = attestationsCount;
        if (data.miners !== undefined) {
            statMiners.textContent = formatNumber(data.miners);
        }

        const el = document.createElement('div');
        el.className = 'attestation-item new';
        el.innerHTML = `
            <div class="attestation-icon">&#128993;</div>
            <div class="attestation-info">
                <div class="attestation-title">${escapeHtml(truncate(data.miner || data.wallet, 16))}</div>
                <div class="attestation-meta">
                    Arch: ${escapeHtml(data.arch || 'unknown')} &middot;
                    Multiplier: ${data.multiplier || 1.0}x &middot;
                    ${timeAgo(ts)}
                </div>
            </div>
        `;

        const empty = attestationsFeed.querySelector('.empty-state');
        if (empty) empty.remove();

        attestationsFeed.insertBefore(el, attestationsFeed.firstChild);

        while (attestationsFeed.children.length > MAX_ATTESTATIONS) {
            attestationsFeed.removeChild(attestationsFeed.lastChild);
        }

        setTimeout(() => el.classList.remove('new'), 1000);

        addLogEntry('attest', `Attestation from ${truncate(data.miner, 12)} (${data.arch || '?'}, ${data.multiplier || 1.0}x)`);
    }

    function handleEpochSettlement(data, ts) {
        const newEpoch = data.new_epoch;
        if (newEpoch) {
            lastEpoch = newEpoch;
            statEpoch.textContent = formatNumber(newEpoch);
        }

        // Show notification
        newEpochNum.textContent = newEpoch;
        epochNotification.style.display = 'flex';
        setTimeout(() => {
            epochNotification.style.display = 'none';
        }, 8000);

        if (data.total_rtc) {
            addLogEntry('epoch', `Epoch ${newEpoch} settled! Total RTC: ${formatNumber(data.total_rtc)}, Miners: ${formatNumber(data.miners)}`);
        } else {
            addLogEntry('epoch', `Epoch ${newEpoch} settled!`);
        }
    }

    // ─── Log ──────────────────────────────────────────────────────────────────
    function addLogEntry(type, msg) {
        if (!showAllEvents && type === 'event') return;

        const ts = new Date().toLocaleTimeString();
        const el = document.createElement('div');
        el.className = `log-entry log-${type}`;
        el.innerHTML = `<span class="log-ts">${ts}</span><span class="log-msg">${escapeHtml(msg)}</span>`;

        const empty = eventLog.querySelector('.empty-state');
        if (empty) empty.remove();

        eventLog.insertBefore(el, eventLog.firstChild);

        while (eventLog.children.length > MAX_LOG_ENTRIES) {
            eventLog.removeChild(eventLog.lastChild);
        }
    }

    // ─── Stats ────────────────────────────────────────────────────────────────
    function updateLastUpdate(ts) {
        statLastUpdate.textContent = formatTime(ts);
    }

    function trackActivity() {
        const now = Date.now();
        eventTimestamps.push(now);
        // Keep only last 30s
        const cutoff = now - 30000;
        eventTimestamps = eventTimestamps.filter(t => t > cutoff);
        const rate = (eventTimestamps.length / 30).toFixed(1);
        activityRate.textContent = rate + ' events/s';
    }

    // ─── Sparkline ────────────────────────────────────────────────────────────
    const sparklineCanvas = $('sparklineCanvas');
    const ctx = sparklineCanvas.getContext('2d');
    const sparklineData = new Array(60).fill(0);
    let sparklineIndex = 0;

    function drawSparkline() {
        const w = sparklineCanvas.width;
        const h = sparklineCanvas.height;
        ctx.clearRect(0, 0, w, h);

        // Background grid
        ctx.strokeStyle = '#1a2035';
        ctx.lineWidth = 1;
        for (let i = 0; i < 5; i++) {
            const y = (h / 5) * i;
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(w, y);
            ctx.stroke();
        }

        if (sparklineData.length < 2) return;

        const max = Math.max(...sparklineData, 1);
        const step = w / (sparklineData.length - 1);

        // Fill
        ctx.beginPath();
        ctx.moveTo(0, h);
        sparklineData.forEach((v, i) => {
            const x = i * step;
            const y = h - (v / max) * h;
            ctx.lineTo(x, y);
        });
        ctx.lineTo(w, h);
        ctx.closePath();
        ctx.fillStyle = 'rgba(0, 200, 100, 0.1)';
        ctx.fill();

        // Line
        ctx.beginPath();
        sparklineData.forEach((v, i) => {
            const x = i * step;
            const y = h - (v / max) * h;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.strokeStyle = '#00c864';
        ctx.lineWidth = 2;
        ctx.stroke();
    }

    setInterval(() => {
        sparklineData[sparklineIndex % sparklineData.length] = 0;
        sparklineIndex++;
        drawSparkline();
    }, 500);

    // Increment sparkline on each event
    const origTrackActivity = trackActivity;
    window.trackActivity = function () {
        origTrackActivity();
        const idx = Math.floor((Date.now() % 30000) / 500);
        sparklineData[Math.floor((Date.now() / 500) % sparklineData.length)]++;
    };

    // ─── Clear Functions ─────────────────────────────────────────────────────
    window.clearBlocks = function () {
        blocksFeed.innerHTML = '<div class="empty-state">Waiting for blocks...</div>';
        blocksFound = 0;
        statBlocks.textContent = '0';
    };

    window.clearAttestations = function () {
        attestationsFeed.innerHTML = '<div class="empty-state">Waiting for attestations...</div>';
        attestationsCount = 0;
        statAttestations.textContent = '0';
    };

    window.clearLog = function () {
        eventLog.innerHTML = '<div class="empty-state">Event stream cleared.</div>';
    };

    // ─── Show All Events Toggle ───────────────────────────────────────────────
    if (showAllEventsChk) {
        showAllEventsChk.addEventListener('change', (e) => {
            showAllEvents = e.target.checked;
        });
    }

    // ─── Boot ─────────────────────────────────────────────────────────────────
    setStatus('connecting', 'Connecting to ' + WS_URL + '...');
    connect();

    // Periodic reconnect reset (after 10 minutes)
    setInterval(() => {
        reconnectAttempts = 0;
    }, 600000);

})();
