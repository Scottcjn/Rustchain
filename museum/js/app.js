/**
 * Vintage Hardware Museum - Main Application
 * Initializes and wires everything together
 */

(function () {
  'use strict';

  let museumScene;
  let controls;
  let panel;
  let minersApi;
  let minimap;
  let tooltip;
  let hoverExhibitId = null;

  function init() {
    // Loading screen
    const loadingEl = document.getElementById('loading');
    const barEl = document.querySelector('.loading-bar-inner');

    // Init API
    minersApi = new MinersAPI();

    // Init scene
    museumScene = new MuseumScene(document.getElementById('canvas-container'));
    museumScene.init();

    // Init controls
    controls = new MuseumControls(
      museumScene.camera,
      document.getElementById('canvas-container')
    );

    // Init panel
    panel = new InfoPanel(minersApi);

    // Init minimap
    const minimapCanvas = document.getElementById('minimap-canvas');
    if (minimapCanvas) {
      minimap = new Minimap(minimapCanvas);
    }

    // Tooltip
    tooltip = document.getElementById('tooltip');

    // Start API polling
    minersApi.startPolling();
    minersApi.onUpdate(data => {
      _updateGlows();
      _updateStatsBadge();
      panel.refresh();
    });

    // Set up click handler
    document.getElementById('canvas-container').addEventListener('click', e => {
      // If pointer is locked, check center of screen
      let nx, ny;
      if (controls.isPointerLocked) {
        nx = 0; ny = 0;
      } else {
        nx = (e.clientX / window.innerWidth) * 2 - 1;
        ny = -(e.clientY / window.innerHeight) * 2 + 1;
      }
      const hit = museumScene.getIntersectedExhibit(nx, ny);
      if (hit) {
        panel.open(hit);
      }
    });

    // Mousemove for hover tooltip (non-pointer-lock)
    document.addEventListener('mousemove', e => {
      if (controls.isPointerLocked) {
        const hit = museumScene.getIntersectedExhibit(0, 0);
        if (hit !== hoverExhibitId) {
          hoverExhibitId = hit;
          if (hit) {
            const ex = EXHIBITS.find(x => x.id === hit);
            _showTooltip(ex ? ex.name : hit, window.innerWidth / 2, window.innerHeight / 2 - 30);
          } else {
            _hideTooltip();
          }
        }
        return;
      }

      const nx = (e.clientX / window.innerWidth) * 2 - 1;
      const ny = -(e.clientY / window.innerHeight) * 2 + 1;
      const hit = museumScene.getIntersectedExhibit(nx, ny);

      if (hit !== hoverExhibitId) {
        hoverExhibitId = hit;
        if (hit) {
          const ex = EXHIBITS.find(x => x.id === hit);
          document.body.style.cursor = 'pointer';
          _showTooltip(ex ? `${ex.name} — Click to inspect` : hit, e.clientX, e.clientY - 40);
        } else {
          document.body.style.cursor = '';
          _hideTooltip();
        }
      } else if (hit) {
        tooltip.style.left = (e.clientX - tooltip.offsetWidth / 2) + 'px';
        tooltip.style.top = (e.clientY - 50) + 'px';
      }
    });

    // Start render loop
    museumScene.animate((delta, elapsed) => {
      controls.update(delta);
      if (minimap) {
        minimap.render(museumScene.camera.position, controls.yaw);
      }
    });

    // Dismiss loading screen after bar completes
    setTimeout(() => {
      loadingEl.classList.add('fade-out');
      setTimeout(() => { loadingEl.style.display = 'none'; }, 800);
    }, 2200);
  }

  function _updateGlows() {
    EXHIBITS.forEach(exhibit => {
      const active = minersApi.isActive(exhibit.minerKey);
      museumScene.setExhibitActive(exhibit.id, active);
    });
  }

  function _updateStatsBadge() {
    const stats = minersApi.getGlobalStats();
    if (!stats) return;
    const badge = document.getElementById('stats-badge');
    if (!badge) return;
    badge.innerHTML = `
      <div><span class="stat-label">ACTIVE</span>${stats.activeCount}/${stats.totalMiners}</div>
      <div><span class="stat-label">POOL</span>${minersApi.formatHashrate(stats.totalHashrate)}</div>
      <div style="font-size:0.6rem;color:#335;margin-top:2px;">Updated ${new Date().toLocaleTimeString()}</div>
    `;
  }

  function _showTooltip(text, x, y) {
    if (!tooltip) return;
    tooltip.textContent = text;
    tooltip.style.display = 'block';
    tooltip.style.left = (x - tooltip.offsetWidth / 2) + 'px';
    tooltip.style.top = (y - 20) + 'px';
  }

  function _hideTooltip() {
    if (tooltip) tooltip.style.display = 'none';
  }

  // Start when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
