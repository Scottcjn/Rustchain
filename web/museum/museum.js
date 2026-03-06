(() => {
  const $ = (id) => document.getElementById(id);
  const TRACKER_URL = 'https://github.com/Scottcjn/rustchain-bounties/blob/main/bounties/XP_TRACKER.md';
  const HUNTER_PROXY_API = '/api/hunters/badges';
  const HUNTER_BADGES_RAW = {
    totalXp: 'https://raw.githubusercontent.com/Scottcjn/rustchain-bounties/main/badges/hunter-stats.json',
    topHunter: 'https://raw.githubusercontent.com/Scottcjn/rustchain-bounties/main/badges/top-hunter.json',
    activeHunters: 'https://raw.githubusercontent.com/Scottcjn/rustchain-bounties/main/badges/active-hunters.json',
    legendaryHunters: 'https://raw.githubusercontent.com/Scottcjn/rustchain-bounties/main/badges/legendary-hunters.json',
    updatedAt: 'https://raw.githubusercontent.com/Scottcjn/rustchain-bounties/main/badges/updated-at.json',
  };

  const state = {
    miners: [],
    stats: null,
    epoch: null,
    hunters: null,
    lastLoaded: 0,
  };

  function fmtAgo(ts) {
    if (!ts) return 'unknown';
    const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
    if (s < 60) return `${s}s ago`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 48) return `${h}h ago`;
    const d = Math.floor(h / 24);
    return `${d}d ago`;
  }

  function wingOf(m) {
    const t = String(m.hardware_type || '').toLowerCase();
    if (t.includes('vintage') || t.includes('retro') || t.includes('powerpc')) return 'vintage';
    if (t.includes('modern') || t.includes('apple silicon') || t.includes('x86-64')) return 'modern';
    return 'other';
  }

  function el(tag, attrs = {}, kids = []) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === 'class') e.className = v;
      else if (k === 'html') e.innerHTML = v;
      else e.setAttribute(k, String(v));
    }
    for (const c of kids) e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    return e;
  }

  async function api(path) {
    const r = await fetch(path, { cache: 'no-store' });
    if (!r.ok) throw new Error(`${path} -> ${r.status}`);
    return await r.json();
  }

  async function fetchJson(url) {
    const r = await fetch(url, { cache: 'no-store' });
    if (!r.ok) return null;
    return await r.json();
  }

  function badgeEndpoint(rawUrl) {
    return `https://img.shields.io/endpoint?url=${encodeURIComponent(rawUrl)}`;
  }

  async function loadHunterData() {
    try {
      const proxied = await api(HUNTER_PROXY_API);
      if (proxied && (proxied.topHunter || proxied.totalXp || proxied.activeHunters)) {
        return proxied;
      }
    } catch (_) {
      // Fall through to direct raw fetch if proxy endpoint is unavailable.
    }

    const [topHunter, totalXp, activeHunters, legendaryHunters, updatedAt] = await Promise.all([
      fetchJson(HUNTER_BADGES_RAW.topHunter).catch(() => null),
      fetchJson(HUNTER_BADGES_RAW.totalXp).catch(() => null),
      fetchJson(HUNTER_BADGES_RAW.activeHunters).catch(() => null),
      fetchJson(HUNTER_BADGES_RAW.legendaryHunters).catch(() => null),
      fetchJson(HUNTER_BADGES_RAW.updatedAt).catch(() => null),
    ]);

    return {
      topHunter,
      totalXp,
      activeHunters,
      legendaryHunters,
      updatedAt,
      rawUrls: HUNTER_BADGES_RAW,
      endpointUrls: {
        topHunter: badgeEndpoint(HUNTER_BADGES_RAW.topHunter),
        totalXp: badgeEndpoint(HUNTER_BADGES_RAW.totalXp),
        activeHunters: badgeEndpoint(HUNTER_BADGES_RAW.activeHunters),
        legendaryHunters: badgeEndpoint(HUNTER_BADGES_RAW.legendaryHunters),
        updatedAt: badgeEndpoint(HUNTER_BADGES_RAW.updatedAt),
      },
    };
  }

  function renderStats() {
    const box = $('stats');
    box.innerHTML = '';

    const add = (k, v) => box.appendChild(el('div', { class: 'stat' }, [
      el('div', { class: 'stat-k' }, [k]),
      el('div', { class: 'stat-v' }, [String(v)])
    ]));

    add('Epoch', state.epoch?.epoch ?? 'n/a');
    add('Attested Miners (1h)', state.miners.length);
    add('Version', state.stats?.version ?? 'n/a');
    add('Last Refresh', new Date(state.lastLoaded).toLocaleTimeString());
  }

  function renderHunterPanel() {
    const meta = $('huntersMeta');
    const box = $('hunterBadges');
    if (!meta || !box) return;

    box.innerHTML = '';
    if (!state.hunters) {
      meta.textContent = 'Hall of Hunters data unavailable right now.';
      return;
    }

    const top = state.hunters.topHunter?.message || 'n/a';
    const total = state.hunters.totalXp?.message || 'n/a';
    const active = state.hunters.activeHunters?.message || 'n/a';
    const legendary = state.hunters.legendaryHunters?.message || 'n/a';
    const updated = state.hunters.updatedAt?.message || 'n/a';

    meta.textContent = `Top Hunter: ${top} | Total XP: ${total} | Active Hunters: ${active} | Legendary: ${legendary} | Updated: ${updated}`;

    const endpointUrls = state.hunters.endpointUrls || {
      topHunter: badgeEndpoint((state.hunters.rawUrls || HUNTER_BADGES_RAW).topHunter),
      totalXp: badgeEndpoint((state.hunters.rawUrls || HUNTER_BADGES_RAW).totalXp),
      activeHunters: badgeEndpoint((state.hunters.rawUrls || HUNTER_BADGES_RAW).activeHunters),
      legendaryHunters: badgeEndpoint((state.hunters.rawUrls || HUNTER_BADGES_RAW).legendaryHunters),
      updatedAt: badgeEndpoint((state.hunters.rawUrls || HUNTER_BADGES_RAW).updatedAt),
    };

    const badgeEntries = [
      ['Top Hunter', endpointUrls.topHunter],
      ['Total XP', endpointUrls.totalXp],
      ['Active Hunters', endpointUrls.activeHunters],
      ['Legendary Hunters', endpointUrls.legendaryHunters],
      ['Updated', endpointUrls.updatedAt],
    ];

    for (const [label, src] of badgeEntries) {
      const a = el('a', { href: TRACKER_URL, target: '_blank', rel: 'noopener', title: label });
      const img = el('img', { src, alt: label, loading: 'lazy' });
      a.appendChild(img);
      box.appendChild(a);
    }
  }

  function renderArchChart(miners) {
    const box = $('archChart');
    const counts = new Map();
    for (const m of miners) {
      const key = `${m.device_family || 'unknown'} / ${m.device_arch || 'unknown'}`;
      counts.set(key, (counts.get(key) || 0) + 1);
    }

    const entries = [...counts.entries()].sort((a, b) => b[1] - a[1]);
    const total = miners.length || 1;

    const colors = ['#d6b25e', '#3a7a62', '#4b7bd8', '#c5563a', '#222', '#888'];

    // Simple SVG donut.
    const size = 140;
    const r = 54;
    const cx = 70;
    const cy = 70;
    const stroke = 18;

    let a0 = -Math.PI / 2;
    const segs = entries.map(([name, n], i) => {
      const frac = n / total;
      const a1 = a0 + frac * Math.PI * 2;
      const x0 = cx + r * Math.cos(a0);
      const y0 = cy + r * Math.sin(a0);
      const x1 = cx + r * Math.cos(a1);
      const y1 = cy + r * Math.sin(a1);
      const large = frac > 0.5 ? 1 : 0;
      const d = `M ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1}`;
      a0 = a1;
      return { d, name, n, color: colors[i % colors.length] };
    });

    const legend = el('div', { class: 'small-note' });
    legend.style.marginTop = '10px';
    legend.innerHTML = entries.slice(0, 6).map(([n, c]) => `${c}x ${n}`).join('<br>') + (entries.length > 6 ? '<br>...' : '');

    const svg = `
      <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
        <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="rgba(0,0,0,.08)" stroke-width="${stroke}" />
        ${segs.map(s => `<path d="${s.d}" fill="none" stroke="${s.color}" stroke-width="${stroke}" stroke-linecap="round"/>`).join('')}
        <text x="${cx}" y="${cy}" text-anchor="middle" dominant-baseline="middle" font-family="IBM Plex Mono" font-size="11" fill="rgba(0,0,0,.75)">${total} miners</text>
      </svg>
    `;

    box.innerHTML = svg;
    box.appendChild(legend);
  }

  function renderTimeline(miners) {
    const box = $('timeline');
    box.innerHTML = '';

    const withFirst = miners
      .filter(m => m.first_attest)
      .slice()
      .sort((a, b) => a.first_attest - b.first_attest);

    if (!withFirst.length) {
      box.appendChild(el('div', { class: 'small-note' }, ['first_attest not available on this node yet.']));
      return;
    }

    for (const m of withFirst.slice(0, 18)) {
      const pill = el('div', { class: 'pill' }, [
        el('b', {}, [String(m.device_arch || 'unknown')]),
        el('span', {}, [String(m.miner || '').slice(0, 10)]),
        el('span', {}, [new Date(m.first_attest * 1000).toLocaleDateString()])
      ]);
      box.appendChild(pill);
    }
  }

  function applyFilters(list) {
    const q = $('q').value.trim().toLowerCase();
    const wing = $('wing').value;

    let out = list;
    if (q) {
      out = out.filter(m => {
        const blob = `${m.miner} ${m.device_arch} ${m.device_family} ${m.hardware_type}`.toLowerCase();
        return blob.includes(q);
      });
    }

    if (wing) out = out.filter(m => wingOf(m) === wing);

    const sort = $('sort').value;
    const cmp = {
      last_desc: (a, b) => (b.last_attest || 0) - (a.last_attest || 0),
      mult_desc: (a, b) => (b.antiquity_multiplier || 0) - (a.antiquity_multiplier || 0),
      entropy_desc: (a, b) => (b.entropy_score || 0) - (a.entropy_score || 0),
      miner_asc: (a, b) => String(a.miner || '').localeCompare(String(b.miner || '')),
    }[sort] || ((a, b) => 0);

    out = out.slice().sort(cmp);
    return out;
  }

  function renderCards() {
    const list = applyFilters(state.miners);
    const box = $('cards');
    box.innerHTML = '';

    $('subtitle').textContent = `Showing ${list.length}/${state.miners.length} miners`;

    for (const m of list) {
      const wing = wingOf(m);
      const b = el('div', { class: `badge ${wing}` }, [wing]);

      const card = el('div', { class: 'card' });
      card.appendChild(el('div', { class: 'row' }, [
        el('div', { class: 'miner' }, [String(m.miner || '')]),
        b
      ]));

      card.appendChild(el('h3', {}, [String(m.hardware_type || 'Unknown')]));

      const meta = el('div', { class: 'meta' }, [
        kv('Arch', `${m.device_arch || 'unknown'}`),
        kv('Multiplier', `${Number(m.antiquity_multiplier || 1).toFixed(2)}x`),
        kv('Entropy', `${Number(m.entropy_score || 0).toFixed(3)}`),
        kv('Last Attest', fmtAgo(m.last_attest))
      ]);
      card.appendChild(meta);

      card.addEventListener('click', () => openModal(m));
      box.appendChild(card);
    }

    renderArchChart(list);
    renderTimeline(list);
  }

  function kv(k, v) {
    return el('div', { class: 'kv' }, [
      el('div', { class: 'k' }, [k]),
      el('div', { class: 'v' }, [String(v)])
    ]);
  }

  async function openModal(m) {
    const modal = $('modal');
    $('mTitle').textContent = m.hardware_type || 'Miner';
    $('mSub').textContent = `${m.device_family || 'unknown'} / ${m.device_arch || 'unknown'} | ${String(m.miner || '')}`;

    const body = $('mBody');
    body.innerHTML = '';

    const left = el('div');
    left.appendChild(kv('Miner', m.miner || ''));
    left.appendChild(kv('First Attest', m.first_attest ? new Date(m.first_attest * 1000).toLocaleString() : 'n/a'));
    left.appendChild(kv('Last Attest', m.last_attest ? new Date(m.last_attest * 1000).toLocaleString() : 'n/a'));
    left.appendChild(kv('Entropy Score', Number(m.entropy_score || 0).toFixed(6)));
    left.appendChild(kv('Antiquity Mult', `${Number(m.antiquity_multiplier || 1).toFixed(3)}x`));

    const right = el('div');
    const pre = el('pre', { class: 'code' }, ['Loading attestation history...']);
    right.appendChild(pre);
    right.appendChild(el('div', { class: 'small-note' }, ['Tip: attach this JSON when reporting fingerprint issues.']));

    body.appendChild(left);
    body.appendChild(right);

    modal.showModal();

    // Best-effort extra data.
    try {
      const hist = await api(`/api/miner/${encodeURIComponent(m.miner)}/attestations?limit=120`);
      pre.textContent = JSON.stringify(hist, null, 2);
    } catch (e) {
      pre.textContent = `No attestation history endpoint on this node yet, or table missing.\n\nError: ${String(e)}`;
    }
  }

  function downloadJson(obj, name) {
    const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 500);
  }

  async function loadAll() {
    $('subtitle').textContent = 'Loading miners...';

    const [stats, epoch, miners, hunters] = await Promise.all([
      api('/api/stats').catch(() => null),
      api('/epoch').catch(() => null),
      api('/api/miners').catch(() => []),
      loadHunterData().catch(() => null),
    ]);

    state.stats = stats;
    state.epoch = epoch;
    state.miners = Array.isArray(miners) ? miners : (miners?.miners || []);
    state.hunters = hunters;
    state.lastLoaded = Date.now();

    renderStats();
    renderCards();
    renderHunterPanel();
  }

  function wire() {
    $('refreshBtn').addEventListener('click', () => loadAll());
    $('exportBtn').addEventListener('click', () => downloadJson({
      stats: state.stats,
      epoch: state.epoch,
      miners: state.miners,
      hunters: state.hunters,
      exported_at: new Date().toISOString(),
    }, `rustchain_museum_${Date.now()}.json`));

    for (const id of ['q', 'wing', 'sort']) {
      $(id).addEventListener('input', () => renderCards());
      $(id).addEventListener('change', () => renderCards());
    }
  }

  wire();
  loadAll().catch((e) => {
    $('subtitle').textContent = `Failed to load: ${String(e)}`;
    renderHunterPanel();
  });
})();
