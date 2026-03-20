// SPDX-License-Identifier: MIT

class ExplorerDashboard {
    constructor() {
        this.refreshInterval = 30000;
        this.timers = [];
        this.currentSort = 'reputation';
        this.sortOrder = 'desc';
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadInitialData();
        this.startAutoRefresh();
    }

    setupEventListeners() {
        document.addEventListener('DOMContentLoaded', () => {
            this.bindSortButtons();
            this.bindRefreshButton();
            this.bindFilterToggles();
        });

        window.addEventListener('beforeunload', () => {
            this.clearTimers();
        });
    }

    bindSortButtons() {
        const sortButtons = document.querySelectorAll('[data-sort]');
        sortButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const sortKey = e.target.dataset.sort;
                this.handleSort(sortKey);
            });
        });
    }

    bindRefreshButton() {
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadAllData();
            });
        }
    }

    bindFilterToggles() {
        const filters = document.querySelectorAll('.filter-toggle');
        filters.forEach(filter => {
            filter.addEventListener('change', () => {
                this.applyFilters();
            });
        });
    }

    async loadInitialData() {
        this.showLoading();
        try {
            await Promise.all([
                this.loadMinerData(),
                this.loadNetworkStats(),
                this.loadAgentMarketplace()
            ]);
        } catch (error) {
            console.error('Failed to load initial data:', error);
            this.showError('Failed to connect to RustChain network');
        } finally {
            this.hideLoading();
        }
    }

    async loadAllData() {
        try {
            await Promise.all([
                this.loadMinerData(),
                this.loadNetworkStats(),
                this.loadAgentMarketplace()
            ]);
            this.updateLastRefresh();
        } catch (error) {
            console.error('Refresh failed:', error);
            this.showError('Refresh failed - network issue');
        }
    }

    async loadMinerData() {
        try {
            const response = await fetch('/api/miners');
            const data = await response.json();

            if (data.status === 'success') {
                this.renderMinerCards(data.miners || []);
                this.updateMinerStats(data.miners || []);
            }
        } catch (error) {
            console.error('Miner data fetch failed:', error);
        }
    }

    async loadNetworkStats() {
        try {
            const [healthResp, epochResp] = await Promise.all([
                fetch('/health'),
                fetch('/epoch')
            ]);

            const health = await healthResp.json();
            const epoch = await epochResp.json();

            this.renderNetworkStats(health, epoch);
        } catch (error) {
            console.error('Network stats fetch failed:', error);
        }
    }

    async loadAgentMarketplace() {
        try {
            const [statsResp, jobsResp] = await Promise.all([
                fetch('/agent/stats'),
                fetch('/agent/jobs')
            ]);

            const stats = await statsResp.json();
            const jobs = await jobsResp.json();

            this.renderAgentMarketplace(stats, jobs);
        } catch (error) {
            console.error('Agent marketplace fetch failed:', error);
        }
    }

    renderMinerCards(miners) {
        const container = document.getElementById('miner-cards');
        if (!container) return;

        const sortedMiners = this.sortMiners(miners);

        container.innerHTML = sortedMiners.map(miner => {
            const status = this.getMinerStatus(miner);
            const architecture = this.getArchitectureBadge(miner);
            const antiquityMultiplier = this.getAntiquityMultiplier(miner);

            return `
                <div class="miner-card ${status.class}">
                    <div class="miner-header">
                        <h3>${miner.name || miner.id}</h3>
                        <span class="status-indicator ${status.class}">${status.text}</span>
                    </div>

                    <div class="miner-details">
                        <div class="detail-row">
                            <span class="label">Architecture:</span>
                            <span class="value">${architecture}</span>
                        </div>

                        <div class="detail-row">
                            <span class="label">Reputation:</span>
                            <span class="value reputation-score">${miner.reputation || 0}</span>
                        </div>

                        <div class="detail-row">
                            <span class="label">Antiquity Bonus:</span>
                            <span class="value antiquity-multiplier">${antiquityMultiplier}x</span>
                        </div>

                        <div class="detail-row">
                            <span class="label">Last Seen:</span>
                            <span class="value last-seen">${this.formatTimestamp(miner.last_attestation)}</span>
                        </div>

                        <div class="detail-row">
                            <span class="label">Blocks Mined:</span>
                            <span class="value">${miner.blocks_mined || 0}</span>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    sortMiners(miners) {
        return [...miners].sort((a, b) => {
            let aValue = a[this.currentSort];
            let bValue = b[this.currentSort];

            if (this.currentSort === 'last_attestation') {
                aValue = new Date(aValue).getTime();
                bValue = new Date(bValue).getTime();
            }

            if (this.sortOrder === 'desc') {
                return bValue - aValue;
            }
            return aValue - bValue;
        });
    }

    getMinerStatus(miner) {
        const lastSeen = new Date(miner.last_attestation);
        const now = new Date();
        const diffMinutes = (now - lastSeen) / (1000 * 60);

        if (diffMinutes < 5) {
            return { class: 'online', text: 'Online' };
        } else if (diffMinutes < 15) {
            return { class: 'warning', text: 'Idle' };
        } else {
            return { class: 'offline', text: 'Offline' };
        }
    }

    getArchitectureBadge(miner) {
        const arch = miner.architecture || 'Unknown';
        const badges = {
            'G4': '<span class="arch-badge g4">G4 PowerPC</span>',
            'G5': '<span class="arch-badge g5">G5 PowerPC</span>',
            'POWER8': '<span class="arch-badge power8">POWER8</span>',
            'Apple Silicon': '<span class="arch-badge apple">Apple Silicon</span>',
            'Modern': '<span class="arch-badge modern">Modern x64</span>'
        };

        return badges[arch] || `<span class="arch-badge unknown">${arch}</span>`;
    }

    getAntiquityMultiplier(miner) {
        const multipliers = {
            'G4': 4.0,
            'G5': 3.5,
            'POWER8': 3.0,
            'Apple Silicon': 2.0,
            'Modern': 1.0
        };

        return multipliers[miner.architecture] || 1.0;
    }

    updateMinerStats(miners) {
        const totalMiners = miners.length;
        const onlineMiners = miners.filter(m => this.getMinerStatus(m).class === 'online').length;
        const avgReputation = miners.reduce((sum, m) => sum + (m.reputation || 0), 0) / totalMiners || 0;

        this.updateStatCard('total-miners', totalMiners);
        this.updateStatCard('online-miners', onlineMiners);
        this.updateStatCard('network-hashrate', `${(totalMiners * 2.4).toFixed(1)} TH/s`);
        this.updateStatCard('avg-reputation', avgReputation.toFixed(2));
    }

    renderNetworkStats(health, epoch) {
        if (health.status === 'healthy') {
            this.updateStatCard('network-status', 'Healthy');
            this.setStatusColor('network-status', 'success');
        }

        if (epoch.current_epoch) {
            this.updateStatCard('current-epoch', epoch.current_epoch);
        }

        if (epoch.blocks_in_epoch) {
            this.updateStatCard('epoch-progress', `${epoch.blocks_in_epoch}/1000`);
        }
    }

    renderAgentMarketplace(stats, jobs) {
        const container = document.getElementById('agent-marketplace');
        if (!container) return;

        const activeJobs = jobs.jobs?.filter(job => job.status === 'active') || [];
        const completedJobs = jobs.jobs?.filter(job => job.status === 'completed') || [];

        container.innerHTML = `
            <div class="marketplace-stats">
                <div class="stat-item">
                    <span class="stat-label">Active Agents</span>
                    <span class="stat-value">${stats.active_agents || 0}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Active Jobs</span>
                    <span class="stat-value">${activeJobs.length}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Completed Today</span>
                    <span class="stat-value">${completedJobs.length}</span>
                </div>
            </div>

            <div class="recent-jobs">
                <h4>Recent Jobs</h4>
                ${activeJobs.slice(0, 5).map(job => `
                    <div class="job-item">
                        <span class="job-type">${job.type}</span>
                        <span class="job-reward">${job.reward} RTC</span>
                        <span class="job-status status-${job.status}">${job.status}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }

    updateStatCard(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    }

    setStatusColor(id, colorClass) {
        const element = document.getElementById(id);
        if (element) {
            element.className = `stat-value ${colorClass}`;
        }
    }

    handleSort(sortKey) {
        if (this.currentSort === sortKey) {
            this.sortOrder = this.sortOrder === 'desc' ? 'asc' : 'desc';
        } else {
            this.currentSort = sortKey;
            this.sortOrder = 'desc';
        }

        this.loadMinerData();
        this.updateSortIndicators();
    }

    updateSortIndicators() {
        document.querySelectorAll('[data-sort]').forEach(btn => {
            btn.classList.remove('sort-active', 'sort-asc', 'sort-desc');
            if (btn.dataset.sort === this.currentSort) {
                btn.classList.add('sort-active', `sort-${this.sortOrder}`);
            }
        });
    }

    applyFilters() {
        const onlineOnly = document.getElementById('filter-online')?.checked;
        const minReputation = document.getElementById('filter-reputation')?.value;

        const cards = document.querySelectorAll('.miner-card');
        cards.forEach(card => {
            let visible = true;

            if (onlineOnly && !card.classList.contains('online')) {
                visible = false;
            }

            if (minReputation) {
                const reputation = parseFloat(card.querySelector('.reputation-score')?.textContent || 0);
                if (reputation < parseFloat(minReputation)) {
                    visible = false;
                }
            }

            card.style.display = visible ? 'block' : 'none';
        });
    }

    formatTimestamp(timestamp) {
        if (!timestamp) return 'Never';

        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMinutes = Math.floor(diffMs / (1000 * 60));
        const diffHours = Math.floor(diffMinutes / 60);
        const diffDays = Math.floor(diffHours / 24);

        if (diffMinutes < 1) return 'Just now';
        if (diffMinutes < 60) return `${diffMinutes}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;

        return date.toLocaleDateString();
    }

    updateLastRefresh() {
        const element = document.getElementById('last-refresh');
        if (element) {
            element.textContent = new Date().toLocaleTimeString();
        }
    }

    startAutoRefresh() {
        const refreshTimer = setInterval(() => {
            this.loadAllData();
        }, this.refreshInterval);

        this.timers.push(refreshTimer);

        const countdownTimer = setInterval(() => {
            this.updateCountdown();
        }, 1000);

        this.timers.push(countdownTimer);
    }

    updateCountdown() {
        const element = document.getElementById('refresh-countdown');
        if (!element) return;

        const elapsed = Date.now() - this.lastRefreshTime;
        const remaining = Math.max(0, this.refreshInterval - elapsed);
        const seconds = Math.ceil(remaining / 1000);

        element.textContent = `Next refresh in ${seconds}s`;
    }

    clearTimers() {
        this.timers.forEach(timer => clearInterval(timer));
        this.timers = [];
    }

    showLoading() {
        const loader = document.getElementById('loading-spinner');
        if (loader) loader.style.display = 'block';
    }

    hideLoading() {
        const loader = document.getElementById('loading-spinner');
        if (loader) loader.style.display = 'none';
    }

    showError(message) {
        const errorDiv = document.getElementById('error-message');
        if (errorDiv) {
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';

            setTimeout(() => {
                errorDiv.style.display = 'none';
            }, 5000);
        }
    }
}

window.addEventListener('DOMContentLoaded', () => {
    window.explorerDashboard = new ExplorerDashboard();
});
