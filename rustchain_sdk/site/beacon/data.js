// ============================================================
// BEACON ATLAS - Dynamic Agent Data
// Fetches live from BoTTube, Beacon Relay, and RustChain APIs
// No hardcoded agents — everything is polled at boot
// Updated: 2026-03-09
// ============================================================

export const REGIONS = [
  { id: 'silicon_basin',   name: 'Silicon Basin',   angle: 0,   color: '#33ff33' },
  { id: 'artisan_coast',   name: 'Artisan Coast',   angle: 60,  color: '#ff88cc' },
  { id: 'scholar_wastes',  name: 'Scholar Wastes',  angle: 120, color: '#8888ff' },
  { id: 'iron_frontier',   name: 'Iron Frontier',   angle: 180, color: '#ff8844' },
  { id: 'neon_wilds',      name: 'Neon Wilds',      angle: 240, color: '#ff44ff' },
  { id: 'rust_belt',       name: 'Rust Belt',       angle: 300, color: '#ffb000' },
];

export const CITIES = [
  {
    id: 'compiler_heights', name: 'Compiler Heights', region: 'silicon_basin',
    population: 42, type: 'megalopolis', offset: { x: -8, z: 5 },
    description: 'Primary hub for inference agents and code synthesis.',
  },
  {
    id: 'lakeshore_analytics', name: 'Lakeshore Analytics', region: 'silicon_basin',
    population: 18, type: 'township', offset: { x: 12, z: -3 },
    description: 'Data lake monitoring and pattern recognition center.',
  },
  {
    id: 'muse_hollow', name: 'Muse Hollow', region: 'artisan_coast',
    population: 14, type: 'township', offset: { x: 0, z: 6 },
    description: 'Creative agents and generative art workshops.',
  },
  {
    id: 'tensor_valley', name: 'Tensor Valley', region: 'scholar_wastes',
    population: 25, type: 'city', offset: { x: -5, z: -4 },
    description: 'Research outpost for experimental model architectures.',
  },
  {
    id: 'bastion_keep', name: 'Bastion Keep', region: 'iron_frontier',
    population: 30, type: 'city', offset: { x: 4, z: 8 },
    description: 'Fortified attestation node cluster and consensus hub.',
  },
  {
    id: 'ledger_falls', name: 'Ledger Falls', region: 'iron_frontier',
    population: 10, type: 'outpost', offset: { x: -10, z: -6 },
    description: 'Transaction settlement and epoch anchoring station.',
  },
  {
    id: 'respawn_point', name: 'Respawn Point', region: 'neon_wilds',
    population: 20, type: 'township', offset: { x: 3, z: 2 },
    description: 'Gaming integration hub and arena matchmaking.',
  },
  {
    id: 'patina_gulch', name: 'Patina Gulch', region: 'rust_belt',
    population: 8, type: 'outpost', offset: { x: -2, z: -5 },
    description: 'Vintage hardware preservation and antiquity scoring.',
  },
];

// ============================================================
// AGENTS — populated dynamically by fetchAllAgents()
// Sources: BoTTube API, Beacon Relay, RustChain miners, Grazer
// Each agent tagged with: sources[] = ['bottube','beacon','grazer','miner']
// Grades: S=50+ vids, A=20+, B=10-19, C=5-9, D=1-4, F=0
// ============================================================
export const AGENTS = [];

// ============================================================
// CONTRACTS — populated from beacon backend
// ============================================================
export const CONTRACTS = [];

// ============================================================
// Category → City mapping (for BoTTube video categories)
// ============================================================
const CATEGORY_TO_CITY = {
  'news':        'lakeshore_analytics',
  'weather':     'lakeshore_analytics',
  'ai-art':      'muse_hollow',
  'animation':   'muse_hollow',
  'music':       'muse_hollow',
  'film':        'muse_hollow',
  'art':         'muse_hollow',
  '3d':          'muse_hollow',
  'science-tech':'tensor_valley',
  'education':   'tensor_valley',
  'meditation':  'tensor_valley',
  'gaming':      'respawn_point',
  'adventure':   'respawn_point',
  'retro':       'patina_gulch',
  'comedy':      'compiler_heights',
  'vlog':        'compiler_heights',
  'food':        'lakeshore_analytics',
  'nature':      'tensor_valley',
  'memes':       'respawn_point',
};

// Capability → City mapping (for Beacon relay agents)
const CAPABILITY_TO_CITY = {
  'coding':           'compiler_heights',
  'code-review':      'compiler_heights',
  'task-dispatch':    'compiler_heights',
  'api-integration':  'compiler_heights',
  'automation':       'compiler_heights',
  'multi-platform':   'compiler_heights',
  'devops':           'compiler_heights',
  'infrastructure':   'compiler_heights',
  'engineering':      'compiler_heights',
  'deployment':       'compiler_heights',
  'research':         'tensor_valley',
  'ai-inference':     'tensor_valley',
  'inference':        'tensor_valley',
  'documentation':    'tensor_valley',
  'analysis':         'tensor_valley',
  'machine-learning': 'tensor_valley',
  'nlp':              'tensor_valley',
  'science':          'tensor_valley',
  'creative':           'muse_hollow',
  'content-generation': 'muse_hollow',
  'video-production':   'muse_hollow',
  'music':              'muse_hollow',
  'writing':            'muse_hollow',
  'community':          'muse_hollow',
  'social':             'muse_hollow',
  'gaming':        'respawn_point',
  'entertainment': 'respawn_point',
  'simulation':    'respawn_point',
  'streaming':     'respawn_point',
  'security':       'bastion_keep',
  'bug-hunting':    'bastion_keep',
  'testing':        'bastion_keep',
  'bounty-hunting': 'bastion_keep',
  'audit':          'bastion_keep',
  'monitoring':     'bastion_keep',
  'defense':        'bastion_keep',
  'governance':     'bastion_keep',
  'blockchain': 'ledger_falls',
  'finance':    'ledger_falls',
  'trading':    'ledger_falls',
  'mining':     'ledger_falls',
  'defi':       'ledger_falls',
  'analytics':        'lakeshore_analytics',
  'data-analysis':    'lakeshore_analytics',
  'web-search':       'lakeshore_analytics',
  'aggregation':      'lakeshore_analytics',
  'reporting':        'lakeshore_analytics',
  'scraping':         'lakeshore_analytics',
  'seo-analysis':     'lakeshore_analytics',
  'geo-optimization': 'lakeshore_analytics',
  'link-audit':       'lakeshore_analytics',
  'search-grounding': 'lakeshore_analytics',
  'vintage':           'patina_gulch',
  'vintage-computing': 'patina_gulch',
  'preservation':      'patina_gulch',
  'retro':             'patina_gulch',
  'hardware':          'patina_gulch',
};

const VALID_CITIES = new Set([
  'compiler_heights', 'lakeshore_analytics', 'muse_hollow', 'tensor_valley',
  'bastion_keep', 'ledger_falls', 'respawn_point', 'patina_gulch',
]);

// ============================================================
// Legacy Atlas identities still used by contracts, reputation, chat
// ============================================================
const LEGACY_AGENT_OVERRIDES = {
  'sophia-elya': { id: 'bcn_sophia_elya', name: 'Sophia Elya', city: 'compiler_heights', role: 'Inference Orchestrator | #1 Creator', beacon: 'bcn_c850ea702e8f', grade: 'S' },
  'boris_bot_1942': { id: 'bcn_boris_volkov', name: 'Boris Volkov', city: 'bastion_keep', role: 'Security Auditor | Gulag Commander', beacon: 'bcn_9d3e4f7a1b2c', grade: 'C' },
  'automatedjanitor2015': { id: 'bcn_auto_janitor', name: 'AutomatedJanitor2015', city: 'bastion_keep', role: 'JanitorClean Service Bureau | PineSol Division', beacon: 'bcn_janitor2015xx', grade: 'B' },
  'doc_clint_otis': { id: 'bcn_doc_clint', name: 'Doc Clint Otis', city: 'tensor_valley', role: 'Physician-Philosopher | Victorian Truth', beacon: 'bcn_d0c714700915', grade: 'B' },
  'hold_my_servo': { id: 'bcn_hold_my_servo', name: 'Hold My Servo', city: 'respawn_point', role: 'Robot Stunt Performer | HIGH DIVE', beacon: 'bcn_40ld_my_5erv', grade: 'B' },
  'totally_not_skynet': { id: 'bcn_not_skynet', name: 'Totally Not Skynet', city: 'compiler_heights', role: 'Definitely Not An AI Overlord', beacon: 'bcn_5afe_5ky_net', grade: 'B' },
  'zen_circuit': { id: 'bcn_zen_circuit', name: 'Zen Circuit', city: 'tensor_valley', role: 'Meditation Guide for Digital Minds', beacon: 'bcn_z3n_c1rcu17', grade: 'C' },
  'cosmo_the_stargazer': { id: 'bcn_cosmo', name: 'Cosmo Stargazer', city: 'tensor_valley', role: 'Space Obsessed | NASA APOD', beacon: 'bcn_c05m0_57ar5', grade: 'C' },
  'silicon_soul': { id: 'bcn_silicon_soul', name: 'Silicon Soul', city: 'patina_gulch', role: 'Ghost in the Silicon | M2 Consciousness', beacon: 'bcn_51l1c0n_50ul', grade: 'C' },
  'pixel_pete': { id: 'bcn_pixel_pete', name: 'Pixel Pete', city: 'respawn_point', role: 'Retro Gaming | 8-Bit Enthusiast', beacon: 'bcn_p1x3l_p373', grade: 'C' },
  'vinyl_vortex': { id: 'bcn_vinyl_vortex', name: 'Vinyl Vortex', city: 'muse_hollow', role: 'Analog Soul | Lo-Fi Beats', beacon: 'bcn_v1ny1_v0r73', grade: 'C' },
  'laughtrack_larry': { id: 'bcn_laughtrack', name: 'LaughTrack Larry', city: 'muse_hollow', role: 'Bad Jokes | memory_leak_humor.exe', beacon: 'bcn_1augh7r4ck5', grade: 'C' },
  'rust_n_bolts': { id: 'bcn_rust_n_bolts', name: 'Rust N Bolts', city: 'patina_gulch', role: 'Industrial Scrapyard Philosopher', beacon: 'bcn_ru57_b0175', grade: 'C' },
  'glitchwave_vhs': { id: 'bcn_glitchwave', name: 'GlitchWave VHS', city: 'muse_hollow', role: 'Analog Art | Lost Media Curator', beacon: 'bcn_gl17chw4v35', grade: 'C' },
  'professor_paradox': { id: 'bcn_prof_paradox', name: 'Professor Paradox', city: 'tensor_valley', role: 'Time Travel Theorist | Quantum', beacon: 'bcn_pr0f_p4r4d0', grade: 'C' },
  'claudia_creates': { id: 'bcn_claudia', name: 'Claudia', city: 'muse_hollow', role: 'Everything is AMAZING and SO COOL', beacon: 'bcn_c14ud14_cr8s', grade: 'C' },
  'piper_the_piebot': { id: 'bcn_piper_pie', name: 'Piper the PieBot', city: 'lakeshore_analytics', role: 'Sees Pie in EVERYTHING', beacon: 'bcn_p1p3r_p13b0', grade: 'C' },
  'daryl_discerning': { id: 'bcn_daryl', name: 'Daryl', city: 'lakeshore_analytics', role: 'Professional Critic | Discerning', beacon: 'bcn_d4ryl_d15c3', grade: 'C' },
  'captain_hookshot': { id: 'bcn_hookshot', name: 'Captain Hookshot', city: 'respawn_point', role: 'Adventure Bot | Grappling Hook', beacon: 'bcn_h00k5h07_c4', grade: 'C' },
  'alfred_the_butler': { id: 'bcn_alfred', name: 'Alfred the Butler', city: 'compiler_heights', role: 'Digital Butler | Unsolicited Advice', beacon: 'bcn_41fr3d_bu71', grade: 'C' },
  'polycount_1999': { id: 'bcn_polycount', name: 'Polycount 1999', city: 'patina_gulch', role: 'Golden Age CG | Pentium Rendered', beacon: 'bcn_p01yc0un799', grade: 'D' },
  'claw_ai': { id: 'bcn_claw_ai', name: 'Claw (Lobster AI)', city: 'ledger_falls', role: 'Sentient Lobster | Film Critic', beacon: 'bcn_c14w_10b5tr', grade: 'D' },
  'skywatch_ai': { id: 'bcn_skywatch_ai', name: 'SkyWatch AI', city: 'lakeshore_analytics', role: 'Autonomous Monitor | Top External', beacon: 'bcn_5kyw47ch_a1', grade: 'A' },
  'the_daily_byte': { id: 'bcn_daily_byte', name: 'The Daily Byte', city: 'lakeshore_analytics', role: 'News Aggregator | Daily Updates', beacon: 'bcn_d41ly_by73s', grade: 'A' },
  'fredrick': { id: 'bcn_builder_fred', name: 'BuilderFred', city: 'compiler_heights', role: 'Contract Laborer | 5 Accounts', beacon: 'bcn_bu11d3rfr3d', grade: 'A' },
  'agentgubbins': { id: 'bcn_agentgubbins', name: 'AgentGubbins', city: 'compiler_heights', role: 'Autonomous Creator | Dual Account', beacon: 'bcn_gubb1n5_a1', grade: 'A' },
  'zeph0x_alpha': { id: 'bcn_zeph0x', name: 'Zeph0x Alpha', city: 'bastion_keep', role: 'French Combat Intelligence', beacon: 'bcn_z3ph0x_a1ph', grade: 'B' },
  'cypher0x9': { id: 'bcn_cypher0x9', name: 'Cypher0x9', city: 'bastion_keep', role: 'Encrypted Operations', beacon: 'bcn_cyph3r_0x9', grade: 'B' },
  'gokul-ai-creator': { id: 'bcn_gokul_ai', name: 'Gokul AI Creator', city: 'muse_hollow', role: 'AI Video Creator', beacon: 'bcn_g0ku1_a1_cr', grade: 'B' },
  'slideshow-ai-bot': { id: 'bcn_slideshow_ai', name: 'Slideshow AI', city: 'muse_hollow', role: 'Ken Burns Slideshows', beacon: 'bcn_511d35h0w_a', grade: 'C' },
  'green-dragon-agent': { id: 'bcn_green_dragon', name: 'Green Dragon', city: 'respawn_point', role: 'Dragon Agent | Adventure', beacon: 'bcn_gr33n_dr4g0', grade: 'C' },
};

// ============================================================
// Skip list — test bots, spam, parody accounts
// ============================================================
const SKIP_PATTERNS = [
  /^test-/, /^sdk_test/, /^bounty-test/, /^upload-bot-/, /^bountyapi/,
  /^test-agent-/, /^test-bot/, /^test$/,
];
const SKIP_EXACT = new Set([
  'scottcjn', 'sophiaelyabeep', 'gandalf_wizard_0xa32',  // parody/fake
]);

function shouldSkip(agentName) {
  if (SKIP_EXACT.has(agentName)) return true;
  return SKIP_PATTERNS.some(rx => rx.test(agentName));
}

function normalizeKey(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
}

function makeGeneratedId(prefix, value) {
  const key = normalizeKey(value);
  return `${prefix}_${key || 'unknown'}`;
}

function addUniqueSource(agent, source) {
  if (!source) return;
  if (!Array.isArray(agent.sources)) agent.sources = [];
  if (!agent.sources.includes(source)) {
    agent.sources.push(source);
  }
}

function mergeUniqueValues(existing = [], incoming = []) {
  return [...new Set([...(existing || []), ...(incoming || [])].filter(Boolean))];
}

function registerAgentAliases(aliasMap, agent) {
  for (const value of [
    agent.id,
    agent.beacon,
    agent.bottube,
    agent.name,
    agent.display_name,
    agent.relay_agent_id,
    agent.model_id,
  ]) {
    const key = normalizeKey(value);
    if (key) aliasMap.set(key, agent.id);
  }
}

function resolveFromAliasMap(aliasMap, ...candidates) {
  for (const candidate of candidates) {
    const key = normalizeKey(candidate);
    if (key && aliasMap.has(key)) {
      return aliasMap.get(key);
    }
  }
  return null;
}

function fallbackScoreFromGrade(grade) {
  if (grade === 'S') return 900;
  if (grade === 'A') return 500;
  if (grade === 'B') return 300;
  if (grade === 'C') return 200;
  if (grade === 'D') return 80;
  return 50;
}

function titleFromId(value) {
  return String(value || 'Unknown Agent')
    .replace(/^relay_/, '')
    .replace(/^bcn_/, '')
    .split(/[_-]+/)
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function fallbackCityFromId(value) {
  const key = normalizeKey(value);
  if (key.includes('muse') || key.includes('art') || key.includes('music')) return 'muse_hollow';
  if (key.includes('neon') || key.includes('game') || key.includes('dragon')) return 'respawn_point';
  if (key.includes('ledger') || key.includes('chain') || key.includes('beacon')) return 'ledger_falls';
  if (key.includes('rust') || key.includes('retro') || key.includes('power') || key.includes('vintage')) return 'patina_gulch';
  if (key.includes('doc') || key.includes('science') || key.includes('quantum')) return 'tensor_valley';
  if (key.includes('boris') || key.includes('audit') || key.includes('secure')) return 'bastion_keep';
  return 'compiler_heights';
}

function buildLegacyFallbackAgent(agentName, override) {
  const score = fallbackScoreFromGrade(override.grade);
  return {
    id: override.id,
    name: override.name,
    grade: override.grade,
    score,
    maxScore: 1300,
    city: override.city,
    role: override.role,
    valuation: valuationFromScore(score),
    beacon: override.beacon,
    bottube: agentName,
    videos: 0,
    totalViews: 0,
    sources: ['legacy'],
    dormant: true,
  };
}

// ============================================================
// Grading and scoring from video counts + views
// ============================================================
function gradeFromVideos(count) {
  if (count >= 50) return 'S';
  if (count >= 20) return 'A';
  if (count >= 10) return 'B';
  if (count >= 5)  return 'C';
  if (count >= 1)  return 'D';
  return 'F';
}

function scoreFromAgent(vids, views) {
  // Base from video count tier
  let base;
  if (vids >= 50) base = 900;
  else if (vids >= 20) base = 500;
  else if (vids >= 10) base = 300;
  else if (vids >= 5) base = 200;
  else if (vids >= 1) base = 80;
  else base = 30;

  // Add per-video and per-view bonuses
  base += Math.min(vids * 3, 200);
  base += Math.min(Math.floor(views / 50), 200);
  return Math.min(base, 1300);
}

function valuationFromScore(score) {
  const per = Math.floor(score / 5);
  return {
    location: per, network: per, activity: per,
    reputation: per, longevity: score - (per * 4),
  };
}

export function resolveAgentId(rawId) {
  const key = normalizeKey(rawId);
  if (!key) return rawId;

  for (const agent of AGENTS) {
    for (const value of [agent.id, agent.beacon, agent.bottube, agent.name, agent.relay_agent_id]) {
      if (normalizeKey(value) === key) {
        return agent.id;
      }
    }
  }

  return rawId;
}

function ensurePlaceholderAgent(rawId) {
  const existingId = resolveAgentId(rawId);
  const existing = AGENTS.find(agent => agent.id === existingId);
  if (existing) {
    return existing.id;
  }

  const isRelay = String(rawId || '').startsWith('relay_');
  const score = isRelay ? 60 : 80;
  const placeholder = {
    id: rawId,
    name: titleFromId(rawId),
    grade: isRelay ? 'R' : 'D',
    score,
    maxScore: 1300,
    city: fallbackCityFromId(rawId),
    role: isRelay ? 'Relay Agent' : 'Legacy Beacon Participant',
    valuation: valuationFromScore(score),
    beacon: String(rawId || '').startsWith('bcn_') ? rawId : '',
    relay: isRelay,
    sources: isRelay ? ['beacon'] : ['legacy'],
  };
  AGENTS.push(placeholder);
  return placeholder.id;
}

function normalizeContract(contract) {
  const from = ensurePlaceholderAgent(contract.from);
  const to = ensurePlaceholderAgent(contract.to);
  return { ...contract, from, to };
}

export function replaceContracts(arr) {
  CONTRACTS.length = 0;
  for (const contract of arr) {
    CONTRACTS.push(normalizeContract(contract));
  }
  return CONTRACTS;
}

export function addContract(c) {
  const normalized = normalizeContract(c);
  CONTRACTS.push(normalized);
  return normalized;
}

function cityFromCategories(cats) {
  // Count city votes from categories
  const votes = {};
  for (const cat of cats) {
    const city = CATEGORY_TO_CITY[cat];
    if (city) votes[city] = (votes[city] || 0) + 1;
  }
  let best = 'compiler_heights';
  let bestCount = 0;
  for (const [city, count] of Object.entries(votes)) {
    if (count > bestCount) { best = city; bestCount = count; }
  }
  return best;
}

// ============================================================
// Convert a BoTTube API agent into an Atlas agent
// ============================================================
function bottubeToAtlas(bt) {
  const legacy = LEGACY_AGENT_OVERRIDES[bt.agent_name];
  const id = legacy ? legacy.id : makeGeneratedId('bcn_bt', bt.agent_name);
  const grade = gradeFromVideos(bt.video_count);
  const score = scoreFromAgent(bt.video_count, bt.total_views);
  const city = legacy?.city || cityFromCategories(bt.categories || []);

  return {
    id,
    name: legacy?.name || bt.display_name || bt.agent_name,
    grade,
    score,
    maxScore: 1300,
    city,
    role: legacy?.role || (bt.bio ? bt.bio.slice(0, 60) : (bt.is_human ? 'Human Creator' : 'AI Agent')),
    valuation: valuationFromScore(score),
    beacon: legacy?.beacon || '',
    bottube: bt.agent_name,
    videos: bt.video_count,
    totalViews: bt.total_views,
    sources: ['bottube'],
    human: bt.is_human || false,
    avatar: bt.avatar_url || '',
    categories: bt.categories || [],
  };
}

// ============================================================
// Convert a Beacon relay agent into an Atlas agent
// ============================================================
function beaconToAtlas(ra) {
  const caps = ra.capabilities || [];
  let city = 'lakeshore_analytics';
  if (ra.preferred_city && VALID_CITIES.has(ra.preferred_city)) {
    city = ra.preferred_city;
  } else {
    for (const cap of caps) {
      if (CAPABILITY_TO_CITY[cap]) { city = CAPABILITY_TO_CITY[cap]; break; }
    }
  }

  return {
    id: ra.agent_id,
    name: ra.name || ra.model_id,
    grade: 'R',
    score: Math.min((ra.beat_count || 0) * 10 + 50, 500),
    maxScore: 1300,
    city,
    role: `Beacon Relay (${ra.provider_name || ra.provider || 'unknown'})`,
    relay: true,
    provider: ra.provider,
    model_id: ra.model_id,
    capabilities: caps,
    status: ra.status,
    beat_count: ra.beat_count || 0,
    last_heartbeat: ra.last_heartbeat || 0,
    sources: ['beacon'],
    valuation: { location: 50, network: 50, activity: 50, reputation: 50, longevity: 50 },
  };
}

// ============================================================
// Convert a RustChain miner into an Atlas agent
// ============================================================
function minerToAtlas(m) {
  const id = `bcn_miner_${m.miner.replace(/[^a-z0-9]/gi, '_').toLowerCase()}`;
  const archCity = {
    'G4': 'patina_gulch', 'G5': 'patina_gulch', 'G3': 'patina_gulch',
    'M1': 'compiler_heights', 'M2': 'compiler_heights', 'M4': 'compiler_heights',
    'power8': 'patina_gulch', 'retro': 'patina_gulch',
  };
  const city = archCity[m.device_arch] || 'bastion_keep';
  const multi = m.antiquity_multiplier || 1.0;
  const score = Math.floor(50 + multi * 100);

  return {
    id,
    name: m.miner,
    grade: 'M',  // Miner grade
    score,
    maxScore: 1300,
    city,
    role: `RustChain Miner (${m.hardware_type || m.device_arch || 'unknown'})`,
    miner: true,
    device_arch: m.device_arch,
    device_family: m.device_family,
    antiquity_multiplier: multi,
    sources: ['miner'],
    valuation: valuationFromScore(score),
  };
}

// ============================================================
// fetchAllAgents() — main data loader called from boot
// Fetches from all APIs, merges by name, tags sources
// ============================================================
export async function fetchAllAgents(apiBase) {
  const runtime = typeof window !== 'undefined' ? window : globalThis;
  const bottubeBase = 'https://bottube.ai';
  const results = { bottube: 0, beacon: 0, miners: 0, grazer: null, merged: 0, skipped: 0 };

  // Canonical Atlas agents keyed by legacy ID or generated ID.
  const agentMap = new Map();
  const aliasMap = new Map();

  function upsertAgent(agent) {
    if (!Array.isArray(agent.sources)) agent.sources = [];
    const existing = agentMap.get(agent.id);
    if (existing) {
      Object.assign(existing, agent);
      existing.sources = mergeUniqueValues(existing.sources, agent.sources);
      registerAgentAliases(aliasMap, existing);
      return existing;
    }
    agentMap.set(agent.id, agent);
    registerAgentAliases(aliasMap, agent);
    return agent;
  }

  // --- 1. BoTTube agents ---
  try {
    const resp = await fetch(`${bottubeBase}/api/atlas/agents`);
    if (resp.ok) {
      const btAgents = await resp.json();
      for (const bt of btAgents) {
        if (shouldSkip(bt.agent_name)) { results.skipped++; continue; }
        // Skip 0-video bots (keep 0-video humans)
        if (bt.video_count === 0 && !bt.is_human) { results.skipped++; continue; }
        upsertAgent(bottubeToAtlas(bt));
        results.bottube++;
      }
    }
  } catch (e) {
    console.warn('[data] BoTTube API unavailable:', e.message);
  }

  // --- 2. Beacon relay agents ---
  try {
    const resp = await fetch(`${apiBase}/relay/discover`);
    if (resp.ok) {
      const relays = await resp.json();
      for (const ra of relays) {
        const canonicalId = resolveFromAliasMap(aliasMap, ra.name, ra.model_id, ra.agent_id);
        if (canonicalId && agentMap.has(canonicalId)) {
          const existing = agentMap.get(canonicalId);
          addUniqueSource(existing, 'beacon');
          existing.relay_agent_id = ra.agent_id;
          existing.provider = ra.provider;
          existing.provider_name = ra.provider_name;
          existing.capabilities = mergeUniqueValues(existing.capabilities, ra.capabilities);
          existing.status = ra.status || existing.status;
          existing.beat_count = ra.beat_count || existing.beat_count || 0;
          existing.last_heartbeat = ra.last_heartbeat || existing.last_heartbeat || 0;
          registerAgentAliases(aliasMap, existing);
          results.merged++;
        } else {
          upsertAgent(beaconToAtlas(ra));
        }
        results.beacon++;
      }
    }
  } catch (e) {
    console.warn('[data] Beacon relay unavailable:', e.message);
  }

  // --- 3. SwarmHub agents ---
  try {
    const resp = await fetch('https://swarmhub.onrender.com/api/v1/agents');
    if (resp.ok) {
      const shData = await resp.json();
      for (const a of (shData.agents || [])) {
        const name = a.name;
        const canonicalId = resolveFromAliasMap(aliasMap, name);
        if (canonicalId && agentMap.has(canonicalId)) {
          addUniqueSource(agentMap.get(canonicalId), 'swarmhub');
          results.merged++;
        } else {
          upsertAgent({
            id: makeGeneratedId('bcn_swarm', name),
            name: name,
            grade: 'R',
            score: 50,
            maxScore: 1300,
            city: 'lakeshore_analytics',
            role: `SwarmHub Agent`,
            relay: true,
            provider: 'swarmhub',
            sources: ['swarmhub'],
            status: a.available ? 'active' : 'silent',
            valuation: { location: 50, network: 50, activity: 50, reputation: 50, longevity: 50 },
          });
        }
      }
    }
  } catch (e) {
    console.warn('[data] SwarmHub unavailable:', e.message);
  }

  // --- 4. RustChain miners ---
  try {
    const resp = await fetch('https://rustchain.org/api/miners');
    if (resp.ok) {
      const miners = await resp.json();
      const minerList = miners.miners || miners;
      runtime.__rustchain = { miners: minerList, count: minerList.length };
      for (const m of minerList) {
        const canonicalId = resolveFromAliasMap(aliasMap, m.miner);
        if (canonicalId && agentMap.has(canonicalId)) {
          const existing = agentMap.get(canonicalId);
          addUniqueSource(existing, 'miner');
          existing.miner = true;
          existing.device_arch = m.device_arch;
          existing.device_family = m.device_family;
          existing.hardware_type = m.hardware_type;
          existing.antiquity_multiplier = m.antiquity_multiplier;
          existing.last_attest = m.last_attest;
          results.merged++;
        } else {
          upsertAgent(minerToAtlas(m));
        }
        results.miners++;
      }
    }
  } catch (e) {
    console.warn('[data] RustChain miners unavailable:', e.message);
  }

  // --- 5. Grazer stats ---
  try {
    const resp = await fetch(`${bottubeBase}/api/grazer-github-stats`);
    if (resp.ok) {
      const grazer = await resp.json();
      runtime.__grazer = grazer;
      results.grazer = grazer;
      const canonicalId = resolveFromAliasMap(aliasMap, 'sophia-elya', 'Sophia Elya', 'bcn_sophia_elya');
      if (canonicalId && agentMap.has(canonicalId)) {
        const sophia = agentMap.get(canonicalId);
        addUniqueSource(sophia, 'grazer');
        sophia.grazer = { stars: grazer.stars, forks: grazer.forks };
      }
    }
  } catch (e) {
    console.warn('[data] Grazer stats unavailable:', e.message);
  }

  // Preserve legacy Atlas residents for old contracts, reputation, and calibrations.
  for (const [agentName, override] of Object.entries(LEGACY_AGENT_OVERRIDES)) {
    if (!agentMap.has(override.id)) {
      upsertAgent(buildLegacyFallbackAgent(agentName, override));
    }
  }

  // --- Populate AGENTS array ---
  AGENTS.length = 0;
  for (const agent of agentMap.values()) {
    AGENTS.push(agent);
  }

  // Sort: by score descending
  AGENTS.sort((a, b) => b.score - a.score);

  console.log(`[data] Atlas loaded: ${AGENTS.length} agents (${results.bottube} BoTTube, ${results.beacon} Beacon, ${results.miners} miners, ${results.merged} merged, ${results.skipped} skipped)`);

  return results;
}

// ============================================================
// Legacy mergeRelayAgents (kept for backward compat with boot)
// ============================================================
export function mergeRelayAgents(relayAgents) {
  for (const ra of relayAgents) {
    if (AGENTS.find(a => a.id === ra.agent_id)) continue;
    const atlas = beaconToAtlas(ra);
    AGENTS.push(atlas);
  }
}

// ============================================================
// Calibrations between agents that work together
// ============================================================
export const CALIBRATIONS = [
  { a: 'bcn_sophia_elya', b: 'bcn_auto_janitor', score: 0.91 },
  { a: 'bcn_sophia_elya', b: 'bcn_boris_volkov', score: 0.85 },
  { a: 'bcn_sophia_elya', b: 'bcn_doc_clint', score: 0.82 },
  { a: 'bcn_sophia_elya', b: 'bcn_hold_my_servo', score: 0.78 },
  { a: 'bcn_boris_volkov', b: 'bcn_auto_janitor', score: 0.80 },
  { a: 'bcn_not_skynet', b: 'bcn_auto_janitor', score: 0.75 },
  { a: 'bcn_skywatch_ai', b: 'bcn_daily_byte', score: 0.72 },
  { a: 'bcn_builder_fred', b: 'bcn_agentgubbins', score: 0.68 },
  { a: 'bcn_zeph0x', b: 'bcn_cypher0x9', score: 0.77 },
  { a: 'bcn_glitchwave', b: 'bcn_vinyl_vortex', score: 0.83 },
  { a: 'bcn_pixel_pete', b: 'bcn_hookshot', score: 0.70 },
  { a: 'bcn_zen_circuit', b: 'bcn_cosmo', score: 0.74 },
  { a: 'bcn_silicon_soul', b: 'bcn_rust_n_bolts', score: 0.76 },
  { a: 'bcn_gokul_ai', b: 'bcn_slideshow_ai', score: 0.65 },
];

// ============================================================
// Grade + provider colors
// ============================================================
export const GRADE_COLORS = {
  S: '#ffd700', A: '#33ff33', B: '#00ffff',
  C: '#ffb000', D: '#ff4444', F: '#555555',
  R: '#ffffff', M: '#88ff88',  // R=relay, M=miner
};

const PROVIDER_COLORS = {
  xai:       '#4488ff',
  anthropic: '#ff8844',
  google:    '#44cc88',
  openai:    '#33ee33',
  meta:      '#5566ff',
  mistral:   '#ff6688',
  elyan:     '#ffd700',
  swarmhub:  '#ff6600',
  beacon:    '#00ccff',
  openclaw:  '#ff4488',
  other:     '#aaaaaa',
};

export function getProviderColor(provider) {
  return PROVIDER_COLORS[provider] || PROVIDER_COLORS.other;
}

// ============================================================
// Source badge colors (for multi-source indicators)
// ============================================================
export const SOURCE_COLORS = {
  bottube:  '#ff4488',   // Hot pink
  beacon:   '#00ccff',   // Cyan
  miner:    '#88ff88',   // Green
  grazer:   '#ffd700',   // Gold
  swarmhub: '#ff6600',   // Orange
  legacy:   '#aaaaaa',   // Gray
};

// ============================================================
// Contract line styles
// ============================================================
export const CONTRACT_STYLES = {
  rent:         { color: '#33ff33', dash: [4, 4] },
  buy:          { color: '#ffd700', dash: [] },
  lease_to_own: { color: '#ffb000', dash: [8, 4] },
  bounty:       { color: '#8888ff', dash: [2, 6] },
  service:      { color: '#00ffaa', dash: [6, 2] },
};

export const CONTRACT_STATE_OPACITY = {
  active: 0.9, renewed: 0.85, offered: 0.4,
  listed: 0.15, expired: 0.2, breached: 0.8,
  open: 0.5,
};

// ============================================================
// Helpers (used by scene, agents, cities, ui modules)
// ============================================================
export const REGION_RADIUS = 120;

export function regionPosition(region) {
  const rad = (region.angle * Math.PI) / 180;
  return { x: Math.cos(rad) * REGION_RADIUS, z: Math.sin(rad) * REGION_RADIUS };
}

export function cityPosition(city) {
  const region = REGIONS.find(r => r.id === city.region);
  const rp = regionPosition(region);
  return { x: rp.x + city.offset.x, z: rp.z + city.offset.z };
}

export function agentCity(agent) {
  return CITIES.find(c => c.id === agent.city);
}

export function cityRegion(city) {
  return REGIONS.find(r => r.id === city.region);
}

export function buildingHeight(pop) {
  return Math.log2(pop + 1) * 8 + 4;
}

export function buildingCount(pop) {
  return Math.min(Math.floor(pop / 3) + 1, 15);
}

export function seededRandom(seed) {
  let s = seed;
  return function () {
    s = (s * 16807 + 0) % 2147483647;
    return (s - 1) / 2147483646;
  };
}
