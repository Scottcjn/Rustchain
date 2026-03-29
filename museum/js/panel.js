/**
 * Vintage Hardware Museum - Info Panel UI
 * Shows machine specs + live miner data when an exhibit is clicked
 */

class InfoPanel {
  constructor(minersApi) {
    this.api = minersApi;
    this.el = document.getElementById('info-panel');
    this.currentExhibitId = null;

    document.getElementById('panel-close').addEventListener('click', () => this.close());
  }

  open(exhibitId) {
    const exhibit = EXHIBITS.find(e => e.id === exhibitId);
    if (!exhibit) return;
    this.currentExhibitId = exhibitId;

    document.getElementById('panel-machine-name').textContent = exhibit.name;
    document.getElementById('panel-machine-type').textContent =
      `${exhibit.type} · ${exhibit.year} · ${exhibit.tag}`;

    this._renderSpecs(exhibit);
    this._renderMinerStats(exhibit);
    this.el.classList.add('open');
  }

  close() {
    this.el.classList.remove('open');
    this.currentExhibitId = null;
  }

  refresh() {
    if (this.currentExhibitId) {
      const exhibit = EXHIBITS.find(e => e.id === this.currentExhibitId);
      if (exhibit) this._renderMinerStats(exhibit);
    }
  }

  _renderSpecs(exhibit) {
    const body = document.getElementById('panel-body');

    // Hardware specs
    let html = '<div class="spec-section"><h3>Hardware Specs</h3>';
    Object.entries(exhibit.specs).forEach(([k, v]) => {
      const isAntiquity = k === 'Antiquity';
      html += `<div class="spec-row">
        <span class="key">${k}</span>
        <span class="val${isAntiquity ? ' highlight' : ''}">${v}</span>
      </div>`;
    });
    html += '</div>';

    // Lore / history
    html += `<div class="spec-section">
      <h3>Field Notes</h3>
      <p style="font-size:0.74rem;color:#889;line-height:1.5;padding:4px 0;">${exhibit.lore}</p>
    </div>`;

    // Miner stats placeholder
    html += '<div id="miner-stats"><div id="miner-status-row"><div id="miner-status-dot"></div><span id="miner-status-text">Loading miner data...</span></div><div id="miner-details"></div></div>';

    body.innerHTML = html;
  }

  _renderMinerStats(exhibit) {
    const dot = document.getElementById('miner-status-dot');
    const statusText = document.getElementById('miner-status-text');
    const details = document.getElementById('miner-details');
    if (!dot || !statusText || !details) return;

    if (!this.api.data) {
      dot.className = '';
      statusText.textContent = 'Connecting to network...';
      statusText.style.color = '#556';
      details.innerHTML = '<div class="miner-loading">⟳ Fetching live data...</div>';
      return;
    }

    const isActive = this.api.isActive(exhibit.minerKey);
    const minerData = this.api.getMinerData(exhibit.minerKey);

    dot.className = isActive ? 'active' : 'inactive';
    statusText.textContent = isActive ? 'MINING ACTIVE' : 'OFFLINE';
    statusText.style.color = isActive ? '#00ff88' : '#cc4444';

    let dhtml = '';
    if (minerData) {
      const fields = [
        ['Hashrate', this.api.formatHashrate(minerData.hashrate || minerData.hash_rate)],
        ['Shares', minerData.shares || minerData.accepted_shares || 'N/A'],
        ['Blocks', minerData.blocks || minerData.blocks_found || 'N/A'],
        ['Uptime', this._formatUptime(minerData.uptime)],
        ['Last Seen', this._formatAge(minerData.last_seen || minerData.last_update)],
        ['RTC Earned', minerData.balance || minerData.rtc_earned || 'N/A'],
      ];
      fields.forEach(([k, v]) => {
        if (v !== 'N/A' && v !== null && v !== undefined) {
          dhtml += `<div class="miner-stat-row"><span class="mk">${k}</span><span class="mv">${v}</span></div>`;
        }
      });
    } else {
      // Show global pool stats as fallback
      const global = this.api.getGlobalStats();
      if (global) {
        dhtml += `<div class="miner-stat-row"><span class="mk">Pool Hashrate</span><span class="mv">${this.api.formatHashrate(global.totalHashrate)}</span></div>`;
        dhtml += `<div class="miner-stat-row"><span class="mk">Active Miners</span><span class="mv">${global.activeCount} / ${global.totalMiners}</span></div>`;
      }
      dhtml += `<div style="font-size:0.68rem;color:#445;margin-top:6px;padding:4px 0;">No per-machine data for this exhibit</div>`;
    }

    if (exhibit.antiquityMultiplier > 1.0) {
      dhtml += `<div class="miner-stat-row" style="margin-top:4px;border-top:1px solid #1a3a1a;">
        <span class="mk" style="color:#00ff88;">Antiquity Bonus</span>
        <span class="mv" style="color:#00ff88;font-weight:bold;">${exhibit.antiquityMultiplier}×</span>
      </div>`;
    }

    details.innerHTML = dhtml;
  }

  _formatUptime(seconds) {
    if (!seconds) return 'N/A';
    seconds = Number(seconds);
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (h > 48) return `${Math.floor(h/24)}d ${h%24}h`;
    return `${h}h ${m}m`;
  }

  _formatAge(ts) {
    if (!ts) return 'N/A';
    const now = Date.now();
    const t = typeof ts === 'number' ? ts * 1000 : new Date(ts).getTime();
    const diff = Math.floor((now - t) / 1000);
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
    return `${Math.floor(diff/86400)}d ago`;
  }
}
