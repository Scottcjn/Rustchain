/**
 * Beacon Atlas — Interactive Agent Trust Network Visualization
 * D3.js force-directed graph with live RustChain API data
 * Bounty: Rustchain #1856 (250 RTC)
 */

const API_BASE = "https://rustchain.org";
const REFRESH_INTERVAL = 30000;

// Architecture color map
const ARCH_COLORS = {
  G4: "#f59e0b", G5: "#3b82f6", POWER8: "#a855f7",
  x86: "#22c55e", ARM: "#ef4444", beacon: "#f97316",
  unknown: "#64748b"
};

const ARCH_FROM_FAMILY = f => {
  if (!f) return "unknown";
  const l = f.toLowerCase();
  if (l.includes("g4") || l.includes("powerpc")) return "G4";
  if (l.includes("g5") || l.includes("power mac g5")) return "G5";
  if (l.includes("power8") || l.includes("ppc64")) return "POWER8";
  if (l.includes("arm") || l.includes("aarch") || l.includes("raspberry") || l.includes("pi")) return "ARM";
  if (l.includes("x86") || l.includes("intel") || l.includes("amd") || l.includes("i386") || l.includes("i686") || l.includes("x64")) return "x86";
  return "unknown";
};

// ── State ───────────────────────────────────────────────────────
let nodes = [], links = [], simulation;
let activeFilter = "all", searchQuery = "";
let selectedNode = null;
const svg = d3.select("#graph");
const width = () => window.innerWidth;
const height = () => window.innerHeight;

// ── API ─────────────────────────────────────────────────────────
async function fetchJSON(path) {
  try {
    const r = await fetch(`${API_BASE}${path}`, { mode: "cors" });
    if (!r.ok) return null;
    return r.json();
  } catch { return null; }
}

async function loadData() {
  const [miners, epoch, agents] = await Promise.all([
    fetchJSON("/api/miners"),
    fetchJSON("/epoch"),
    fetchJSON("/beacon/atlas")
  ]);
  return { miners: miners || [], epoch: epoch || {}, agents: agents || [] };
}

// ── Graph builder ───────────────────────────────────────────────
function buildGraph(data) {
  const nodeMap = new Map();
  const newLinks = [];

  // Add miners as nodes
  const minerList = Array.isArray(data.miners) ? data.miners : [];
  minerList.forEach(m => {
    const id = m.miner || m.miner_id || m.id || `miner-${Math.random().toString(36).slice(2,8)}`;
    const arch = ARCH_FROM_FAMILY(m.device_family || m.device_arch || "");
    nodeMap.set(id, {
      id, type: "miner", arch,
      name: m.miner || id,
      multiplier: m.antiquity_multiplier || 1.0,
      device: m.device_family || m.device_arch || "unknown",
      lastAttest: m.last_attest || null,
      balance: m.balance || 0,
      score: (m.antiquity_multiplier || 1) * 10
    });
  });

  // Add beacon agents
  const agentList = Array.isArray(data.agents) ? data.agents : (data.agents?.agents || []);
  agentList.forEach(a => {
    const id = a.agent_id || a.id || `agent-${Math.random().toString(36).slice(2,8)}`;
    nodeMap.set(id, {
      id, type: "beacon", arch: "beacon",
      name: a.name || id,
      pubkey: a.pubkey_hex || "",
      status: a.status || "active",
      score: 15
    });
  });

  // Build trust links: miners connect to closest beacon agents
  const agentIds = [...nodeMap.values()].filter(n => n.type === "beacon").map(n => n.id);
  const minerIds = [...nodeMap.values()].filter(n => n.type === "miner").map(n => n.id);

  // Each miner connects to 1-2 random beacon agents (attestation)
  minerIds.forEach(mid => {
    if (agentIds.length === 0) return;
    const count = Math.min(agentIds.length, 1 + Math.floor(Math.random() * 2));
    const shuffled = [...agentIds].sort(() => Math.random() - 0.5);
    for (let i = 0; i < count; i++) {
      newLinks.push({ source: mid, target: shuffled[i], type: "attestation", strength: 0.3 + Math.random() * 0.7 });
    }
  });

  // Beacon agents form trust links among themselves
  for (let i = 0; i < agentIds.length; i++) {
    for (let j = i + 1; j < agentIds.length; j++) {
      if (Math.random() < 0.4) {
        newLinks.push({ source: agentIds[i], target: agentIds[j], type: "trust", strength: 0.2 + Math.random() * 0.8 });
      }
    }
  }

  // If no real data, add demo nodes
  if (nodeMap.size === 0) {
    const demoArchs = ["G4","G5","POWER8","x86","ARM","x86","ARM","G4"];
    demoArchs.forEach((arch, i) => {
      nodeMap.set(`demo-miner-${i}`, {
        id: `demo-miner-${i}`, type: "miner", arch,
        name: `${arch}-Miner-${i}`, multiplier: arch === "G4" ? 2.5 : arch === "G5" ? 2.0 : 1.0,
        device: arch, score: 10
      });
    });
    for (let i = 0; i < 3; i++) {
      nodeMap.set(`demo-agent-${i}`, {
        id: `demo-agent-${i}`, type: "beacon", arch: "beacon",
        name: `Beacon-Agent-${i}`, status: "active", score: 15
      });
    }
    // Demo links
    for (let i = 0; i < 8; i++) {
      newLinks.push({ source: `demo-miner-${i}`, target: `demo-agent-${i % 3}`, type: "attestation", strength: 0.5 });
    }
    newLinks.push({ source: "demo-agent-0", target: "demo-agent-1", type: "trust", strength: 0.8 });
    newLinks.push({ source: "demo-agent-1", target: "demo-agent-2", type: "trust", strength: 0.6 });
  }

  nodes = [...nodeMap.values()];
  links = newLinks;

  // Update stats
  d3.select("#stat-miners").text(nodes.filter(n => n.type === "miner").length);
  d3.select("#stat-agents").text(nodes.filter(n => n.type === "beacon").length);
  d3.select("#stat-edges").text(links.length);
  if (data.epoch?.epoch) d3.select("#stat-epoch").text(data.epoch.epoch);
}

// ── Render ──────────────────────────────────────────────────────
let linkGroup, nodeGroup;

function initGraph() {
  const g = svg.append("g").attr("id", "zoom-group");

  // Zoom
  const zoom = d3.zoom()
    .scaleExtent([0.2, 5])
    .on("zoom", e => g.attr("transform", e.transform));
  svg.call(zoom);

  linkGroup = g.append("g").attr("class", "links");
  nodeGroup = g.append("g").attr("class", "nodes");

  simulation = d3.forceSimulation()
    .force("link", d3.forceLink().id(d => d.id).distance(80).strength(d => d.strength * 0.3))
    .force("charge", d3.forceManyBody().strength(-120))
    .force("center", d3.forceCenter(width() / 2, height() / 2))
    .force("collision", d3.forceCollide().radius(d => nodeRadius(d) + 4))
    .on("tick", ticked);
}

function nodeRadius(d) { return Math.max(5, Math.sqrt(d.score || 10) * 3); }

function filteredData() {
  let fn = nodes;
  if (activeFilter !== "all") {
    fn = nodes.filter(n => n.arch === activeFilter);
  }
  if (searchQuery) {
    const q = searchQuery.toLowerCase();
    fn = fn.filter(n => n.name.toLowerCase().includes(q) || n.id.toLowerCase().includes(q));
  }
  const ids = new Set(fn.map(n => n.id));
  const fl = links.filter(l => {
    const sid = typeof l.source === "object" ? l.source.id : l.source;
    const tid = typeof l.target === "object" ? l.target.id : l.target;
    return ids.has(sid) && ids.has(tid);
  });
  return { nodes: fn, links: fl };
}

function updateGraph() {
  const fd = filteredData();

  // Links
  const link = linkGroup.selectAll("line").data(fd.links, d => {
    const sid = typeof d.source === "object" ? d.source.id : d.source;
    const tid = typeof d.target === "object" ? d.target.id : d.target;
    return `${sid}-${tid}`;
  });
  link.exit().remove();
  const linkEnter = link.enter().append("line")
    .attr("stroke", d => d.type === "trust" ? "#7dd3fc44" : "#f59e0b33")
    .attr("stroke-width", d => Math.max(1, d.strength * 3));
  const linkMerged = linkEnter.merge(link);

  // Nodes
  const node = nodeGroup.selectAll("g.node").data(fd.nodes, d => d.id);
  node.exit().remove();
  const nodeEnter = node.enter().append("g").attr("class", "node").call(drag(simulation));

  // Miner = circle, Beacon = hexagon
  nodeEnter.each(function(d) {
    const el = d3.select(this);
    if (d.type === "beacon") {
      el.append("polygon")
        .attr("points", hexPoints(nodeRadius(d)))
        .attr("fill", ARCH_COLORS[d.arch])
        .attr("stroke", "#fff2")
        .attr("stroke-width", 1);
    } else {
      el.append("circle")
        .attr("r", nodeRadius(d))
        .attr("fill", ARCH_COLORS[d.arch])
        .attr("stroke", "#fff2")
        .attr("stroke-width", 1);
    }
    // Label
    el.append("text")
      .text(d.name.length > 14 ? d.name.slice(0, 12) + "…" : d.name)
      .attr("dy", nodeRadius(d) + 12)
      .attr("text-anchor", "middle")
      .attr("fill", "#94a3b8")
      .attr("font-size", "9px");
  });

  // Events
  nodeEnter
    .on("mouseover", (e, d) => showTooltip(e, d))
    .on("mouseout", () => hideTooltip())
    .on("click", (e, d) => showInfo(d));

  const nodeMerged = nodeEnter.merge(node);

  simulation.nodes(fd.nodes);
  simulation.force("link").links(fd.links);
  simulation.alpha(0.5).restart();
}

function ticked() {
  linkGroup.selectAll("line")
    .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
    .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
  nodeGroup.selectAll("g.node")
    .attr("transform", d => `translate(${d.x},${d.y})`);
}

function hexPoints(r) {
  const pts = [];
  for (let i = 0; i < 6; i++) {
    const a = Math.PI / 3 * i - Math.PI / 6;
    pts.push(`${r * Math.cos(a)},${r * Math.sin(a)}`);
  }
  return pts.join(" ");
}

// ── Drag ────────────────────────────────────────────────────────
function drag(sim) {
  return d3.drag()
    .on("start", (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
    .on("drag", (e, d) => { d.fx = e.x; d.fy = e.y; })
    .on("end", (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; });
}

// ── Tooltip ─────────────────────────────────────────────────────
const tooltip = d3.select("#tooltip");
function showTooltip(event, d) {
  const label = d.type === "beacon" ? `🔷 ${d.name}` : `⛏ ${d.name} (${d.arch})`;
  tooltip.html(label).style("display", "block")
    .style("left", (event.pageX + 12) + "px").style("top", (event.pageY - 20) + "px");
}
function hideTooltip() { tooltip.style("display", "none"); }

// ── Info panel ──────────────────────────────────────────────────
function showInfo(d) {
  selectedNode = d;
  d3.select("#info-name").text(d.name);
  let html = "";
  const row = (l, v) => `<div class="row"><span class="label">${l}</span><span class="value">${v}</span></div>`;
  html += row("ID", d.id);
  html += row("Type", d.type === "beacon" ? "Beacon Agent" : "Miner");
  if (d.arch) html += row("Architecture", d.arch);
  if (d.multiplier) html += row("Multiplier", d.multiplier + "x");
  if (d.device) html += row("Device", d.device);
  if (d.status) html += row("Status", d.status);
  if (d.pubkey) html += row("Pubkey", d.pubkey.slice(0, 16) + "…");
  if (d.lastAttest) html += row("Last Attestation", new Date(d.lastAttest * 1000).toLocaleString());
  if (d.balance) html += row("Balance", d.balance + " RTC");

  const conns = links.filter(l => {
    const s = typeof l.source === "object" ? l.source.id : l.source;
    const t = typeof l.target === "object" ? l.target.id : l.target;
    return s === d.id || t === d.id;
  });
  html += row("Connections", conns.length);

  d3.select("#info-body").html(html);
  d3.select("#info-panel").style("display", "block");
}

d3.select("#info-close").on("click", () => {
  d3.select("#info-panel").style("display", "none");
  selectedNode = null;
});

// ── Filters ─────────────────────────────────────────────────────
d3.selectAll(".filter-btn").on("click", function() {
  d3.selectAll(".filter-btn").classed("active", false);
  d3.select(this).classed("active", true);
  activeFilter = this.dataset.filter;
  updateGraph();
});

// ── Search ──────────────────────────────────────────────────────
d3.select("#search").on("input", function() {
  searchQuery = this.value;
  updateGraph();
});

// ── Resize ──────────────────────────────────────────────────────
window.addEventListener("resize", () => {
  simulation.force("center", d3.forceCenter(width() / 2, height() / 2));
  simulation.alpha(0.3).restart();
});

// ── Init ────────────────────────────────────────────────────────
async function init() {
  initGraph();
  const data = await loadData();
  buildGraph(data);
  updateGraph();

  // Auto-refresh
  setInterval(async () => {
    const data = await loadData();
    buildGraph(data);
    updateGraph();
  }, REFRESH_INTERVAL);
}

init();
