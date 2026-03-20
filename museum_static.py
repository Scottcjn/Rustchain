// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

"""Static assets and styling for the RustChain Hardware Museum."""

import base64

# CSS Styles for Hardware Museum
MUSEUM_CSS = """
<style>
body {
    font-family: 'Monaco', 'Menlo', monospace;
    background: linear-gradient(135deg, #1a1a2e, #16213e);
    color: #e94560;
    margin: 0;
    padding: 20px;
    line-height: 1.6;
}

.museum-container {
    max-width: 1400px;
    margin: 0 auto;
    background: rgba(15, 15, 30, 0.9);
    border-radius: 12px;
    border: 2px solid #e94560;
    box-shadow: 0 0 30px rgba(233, 69, 96, 0.3);
    padding: 30px;
}

.museum-header {
    text-align: center;
    margin-bottom: 40px;
    border-bottom: 2px solid #e94560;
    padding-bottom: 20px;
}

.museum-title {
    font-size: 2.8em;
    margin-bottom: 10px;
    text-shadow: 0 0 10px rgba(233, 69, 96, 0.5);
    animation: glow-pulse 2s infinite alternate;
}

.museum-subtitle {
    color: #0f3460;
    font-size: 1.2em;
    margin-bottom: 20px;
}

.hardware-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
    gap: 25px;
    margin-top: 30px;
}

.hardware-card {
    background: linear-gradient(145deg, #0f1419, #1a1f2e);
    border: 1px solid #e94560;
    border-radius: 8px;
    padding: 20px;
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
}

.hardware-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 10px 25px rgba(233, 69, 96, 0.4);
    border-color: #ff6b8a;
}

.hardware-header {
    display: flex;
    align-items: center;
    margin-bottom: 15px;
}

.hardware-icon {
    width: 48px;
    height: 48px;
    margin-right: 15px;
    filter: drop-shadow(0 0 5px rgba(233, 69, 96, 0.3));
}

.hardware-name {
    font-size: 1.4em;
    font-weight: bold;
    color: #e94560;
    margin: 0;
}

.hardware-arch {
    color: #0f3460;
    font-size: 0.9em;
    margin-top: 2px;
}

.hardware-details {
    margin-top: 15px;
}

.detail-row {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
    font-size: 0.95em;
}

.detail-label {
    color: #b8c5d6;
    font-weight: 500;
}

.detail-value {
    color: #e94560;
    font-family: 'Courier New', monospace;
}

.multiplier-badge {
    position: absolute;
    top: 15px;
    right: 15px;
    background: linear-gradient(45deg, #e94560, #ff6b8a);
    color: white;
    padding: 5px 12px;
    border-radius: 20px;
    font-size: 0.8em;
    font-weight: bold;
    box-shadow: 0 2px 8px rgba(233, 69, 96, 0.3);
}

.stats-section {
    margin-top: 40px;
    text-align: center;
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    margin-top: 20px;
}

.stat-card {
    background: linear-gradient(145deg, #16213e, #1a1a2e);
    padding: 20px;
    border-radius: 8px;
    border: 1px solid #e94560;
}

.stat-value {
    font-size: 2.2em;
    color: #e94560;
    font-weight: bold;
    margin-bottom: 5px;
}

.stat-label {
    color: #b8c5d6;
    font-size: 0.9em;
}

.vintage-indicator {
    display: inline-block;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    margin-right: 8px;
    animation: pulse-glow 1.5s infinite;
}

.vintage-authentic { background: #00ff88; }
.vintage-classic { background: #ffaa00; }
.vintage-modern { background: #ff4444; }

@keyframes glow-pulse {
    0% { text-shadow: 0 0 10px rgba(233, 69, 96, 0.5); }
    100% { text-shadow: 0 0 20px rgba(233, 69, 96, 0.8); }
}

@keyframes pulse-glow {
    0%, 100% { opacity: 1; box-shadow: 0 0 5px currentColor; }
    50% { opacity: 0.6; box-shadow: 0 0 15px currentColor; }
}

.filter-bar {
    display: flex;
    justify-content: center;
    gap: 15px;
    margin-bottom: 30px;
    flex-wrap: wrap;
}

.filter-btn {
    background: linear-gradient(145deg, #16213e, #1a1a2e);
    color: #e94560;
    border: 1px solid #e94560;
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.3s ease;
    font-family: inherit;
}

.filter-btn:hover, .filter-btn.active {
    background: #e94560;
    color: white;
    transform: scale(1.05);
}
</style>
"""

# JavaScript for interactive features
MUSEUM_JS = """
<script>
class HardwareMuseum {
    constructor() {
        this.hardwareData = new Map();
        this.currentFilter = 'all';
        this.init();
    }

    init() {
        this.bindFilterEvents();
        this.startStatsUpdater();
        this.initializeHardwareCards();
    }

    bindFilterEvents() {
        const filterBtns = document.querySelectorAll('.filter-btn');
        filterBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.setFilter(e.target.dataset.filter);
            });
        });
    }

    setFilter(filter) {
        this.currentFilter = filter;
        const cards = document.querySelectorAll('.hardware-card');
        const filterBtns = document.querySelectorAll('.filter-btn');

        filterBtns.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.filter === filter);
        });

        cards.forEach(card => {
            const arch = card.dataset.arch;
            const visible = filter === 'all' || arch === filter;
            card.style.display = visible ? 'block' : 'none';

            if (visible) {
                card.style.animation = 'fadeInUp 0.5s ease-out';
            }
        });
    }

    updateMinerStatus(minerId, status) {
        const card = document.querySelector(`[data-miner-id="${minerId}"]`);
        if (card) {
            const indicator = card.querySelector('.vintage-indicator');
            const statusMap = {
                'online': 'vintage-authentic',
                'mining': 'vintage-classic',
                'offline': 'vintage-modern'
            };

            indicator.className = `vintage-indicator ${statusMap[status] || 'vintage-modern'}`;
        }
    }

    startStatsUpdater() {
        this.updateStats();
        setInterval(() => this.updateStats(), 30000);
    }

    async updateStats() {
        try {
            const response = await fetch('/api/miners');
            const miners = await response.json();

            const totalMiners = miners.length;
            const activeMiners = miners.filter(m => m.status === 'online').length;
            const vintageCount = miners.filter(m => m.is_vintage).length;

            this.updateStatCard('total-miners', totalMiners);
            this.updateStatCard('active-miners', activeMiners);
            this.updateStatCard('vintage-ratio', `${Math.round(vintageCount/totalMiners*100)}%`);

        } catch (error) {
            console.warn('Stats update failed:', error);
        }
    }

    updateStatCard(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
            element.style.animation = 'none';
            setTimeout(() => element.style.animation = 'glow-pulse 0.5s ease-out', 10);
        }
    }

    initializeHardwareCards() {
        const cards = document.querySelectorAll('.hardware-card');
        cards.forEach((card, index) => {
            card.style.animationDelay = `${index * 0.1}s`;
            card.addEventListener('click', () => this.showHardwareDetails(card));
        });
    }

    showHardwareDetails(card) {
        const name = card.querySelector('.hardware-name').textContent;
        const arch = card.querySelector('.hardware-arch').textContent;

        // Simple modal-style details (could be expanded)
        const details = `
            Hardware: ${name}
            Architecture: ${arch}
            Click outside to close
        `;

        if (confirm(details)) {
            // Could expand to show more detailed info
        }
    }
}

// Initialize museum when DOM loads
document.addEventListener('DOMContentLoaded', () => {
    window.museum = new HardwareMuseum();
});
</script>
"""

# Base64 encoded hardware architecture icons
HARDWARE_ICONS = {
    'powerpc': 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDgiIGhlaWdodD0iNDgiIHZpZXdCb3g9IjAgMCA0OCA0OCIgZmlsbD0ibm9uZSI+PHJlY3Qgd2lkdGg9IjQ4IiBoZWlnaHQ9IjQ4IiByeD0iOCIgZmlsbD0iIzFhMWEyZSIgc3Ryb2tlPSIjZTk0NTYwIi8+PHRleHQgeD0iMjQiIHk9IjMwIiBmaWxsPSIjZTk0NTYwIiBmb250LXNpemU9IjE0IiBmb250LXdlaWdodD0iYm9sZCIgdGV4dC1hbmNob3I9Im1pZGRsZSI+UFBDPC90ZXh0Pjwvc3ZnPg==',

    'm68k': 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDgiIGhlaWdodD0iNDgiIHZpZXdCb3g9IjAgMCA0OCA0OCIgZmlsbD0ibm9uZSI+PHJlY3Qgd2lkdGg9IjQ4IiBoZWlnaHQ9IjQ4IiByeD0iOCIgZmlsbD0iIzFhMWEyZSIgc3Ryb2tlPSIjZTk0NTYwIi8+PHRleHQgeD0iMjQiIHk9IjMwIiBmaWxsPSIjZTk0NTYwIiBmb250LXNpemU9IjEyIiBmb250LXdlaWdodD0iYm9sZCIgdGV4dC1hbmNob3I9Im1pZGRsZSI+NjhLPC90ZXh0Pjwvc3ZnPg==',

    'sparc': 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDgiIGhlaWdodD0iNDgiIHZpZXdCb3g9IjAgMCA0OCA0OCIgZmlsbD0ibm9uZSI+PHJlY3Qgd2lkdGg9IjQ4IiBoZWlnaHQ9IjQ4IiByeD0iOCIgZmlsbD0iIzFhMWEyZSIgc3Ryb2tlPSIjZTk0NTYwIi8+PHRleHQgeD0iMjQiIHk9IjMwIiBmaWxsPSIjZTk0NTYwIiBmb250LXNpemU9IjEwIiBmb250LXdlaWdodD0iYm9sZCIgdGV4dC1hbmNob3I9Im1pZGRsZSI+U1BBUkM8L3RleHQ+PC9zdmc+',

    'x86': 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDgiIGhlaWdodD0iNDgiIHZpZXdCb3g9IjAgMCA0OCA0OCIgZmlsbD0ibm9uZSI+PHJlY3Qgd2lkdGg9IjQ4IiBoZWlnaHQ9IjQ4IiByeD0iOCIgZmlsbD0iIzFhMWEyZSIgc3Ryb2tlPSIjZTk0NTYwIi8+PHRleHQgeD0iMjQiIHk9IjMwIiBmaWxsPSIjZTk0NTYwIiBmb250LXNpemU9IjEyIiBmb250LXdlaWdodD0iYm9sZCIgdGV4dC1hbmNob3I9Im1pZGRsZSI+eDg2PC90ZXh0Pjwvc3ZnPg==',

    'risc': 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDgiIGhlaWdodD0iNDgiIHZpZXdCb3g9IjAgMCA0OCA0OCIgZmlsbD0ibm9uZSI+PHJlY3Qgd2lkdGg9IjQ4IiBoZWlnaHQ9IjQ4IiByeD0iOCIgZmlsbD0iIzFhMWEyZSIgc3Ryb2tlPSIjZTk0NTYwIi8+PHRleHQgeD0iMjQiIHk9IjMwIiBmaWxsPSIjZTk0NTYwIiBmb250LXNpemU9IjEwIiBmb250LXdlaWdodD0iYm9sZCIgdGV4dC1hbmNob3I9Im1pZGRsZSI+UklTQzwvdGV4dD48L3N2Zz4=',

    'arm': 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDgiIGhlaWdodD0iNDgiIHZpZXdCb3g9IjAgMCA0OCA0OCIgZmlsbD0ibm9uZSI+PHJlY3Qgd2lkdGg9IjQ4IiBoZWlnaHQ9IjQ4IiByeD0iOCIgZmlsbD0iIzFhMWEyZSIgc3Ryb2tlPSIjZTk0NTYwIi8+PHRleHQgeD0iMjQiIHk9IjMwIiBmaWxsPSIjZTk0NTYwIiBmb250LXNpemU9IjEyIiBmb250LXdlaWdodD0iYm9sZCIgdGV4dC1hbmNob3I9Im1pZGRsZSI+QVJNPC90ZXh0Pjwvc3ZnPg=='
}

# Filter buttons HTML
FILTER_BUTTONS = """
<div class="filter-bar">
    <button class="filter-btn active" data-filter="all">All Hardware</button>
    <button class="filter-btn" data-filter="powerpc">PowerPC</button>
    <button class="filter-btn" data-filter="m68k">68K</button>
    <button class="filter-btn" data-filter="sparc">SPARC</button>
    <button class="filter-btn" data-filter="x86">x86</button>
    <button class="filter-btn" data-filter="risc">RISC</button>
</div>
"""

def get_hardware_icon(arch_type):
    """Get base64 encoded icon for hardware architecture."""
    return HARDWARE_ICONS.get(arch_type.lower(), HARDWARE_ICONS['x86'])

def get_vintage_class(year):
    """Get CSS class based on hardware vintage."""
    if year < 1990:
        return 'vintage-authentic'
    elif year < 2005:
        return 'vintage-classic'
    else:
        return 'vintage-modern'

def generate_hardware_card(hardware_info):
    """Generate HTML for a single hardware card."""
    arch = hardware_info.get('architecture', 'unknown').lower()
    icon = get_hardware_icon(arch)
    vintage_class = get_vintage_class(hardware_info.get('year', 2020))

    return f"""
    <div class="hardware-card" data-arch="{arch}" data-miner-id="{hardware_info.get('miner_id', '')}">
        <div class="multiplier-badge">{hardware_info.get('multiplier', '1.0')}x</div>
        <div class="hardware-header">
            <img src="{icon}" class="hardware-icon" alt="{arch} icon">
            <div>
                <h3 class="hardware-name">{hardware_info.get('name', 'Unknown System')}</h3>
                <div class="hardware-arch">
                    <span class="vintage-indicator {vintage_class}"></span>
                    {hardware_info.get('architecture', 'Unknown')} • {hardware_info.get('year', 'Unknown')}
                </div>
            </div>
        </div>
        <div class="hardware-details">
            <div class="detail-row">
                <span class="detail-label">CPU:</span>
                <span class="detail-value">{hardware_info.get('cpu', 'Unknown')}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Memory:</span>
                <span class="detail-value">{hardware_info.get('memory', 'Unknown')}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">OS:</span>
                <span class="detail-value">{hardware_info.get('os', 'Unknown')}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Status:</span>
                <span class="detail-value">{hardware_info.get('status', 'Offline')}</span>
            </div>
        </div>
    </div>
    """
