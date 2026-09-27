// SPDX-License-Identifier: MIT

const MAX_METRIC = 1_000_000_000;
const DEFAULT_LIMIT = 10;
const MAX_LIMIT = 50;

function safeCount(value) {
  const count = Number(value);
  if (!Number.isFinite(count) || count <= 0) return 0;
  return Math.min(MAX_METRIC, Math.floor(count));
}

function safeLimit(value) {
  const limit = Number(value);
  if (!Number.isFinite(limit) || limit <= 0) return DEFAULT_LIMIT;
  return Math.min(MAX_LIMIT, Math.floor(limit));
}

function reputationFor(reputation, agentId) {
  if (reputation instanceof Map) return reputation.get(agentId) || {};
  if (!reputation || typeof reputation !== 'object') return {};
  return reputation[agentId] || {};
}

function visibleContractCounts(contracts) {
  const counts = new Map();
  const seenByAgent = new Map();

  for (const [index, contract] of (Array.isArray(contracts) ? contracts : []).entries()) {
    if (!contract || typeof contract !== 'object') continue;
    const contractKey = String(contract.id ?? `row-${index}`);
    const participants = new Set([contract.from, contract.to].filter(value => (
      typeof value === 'string' && value.length > 0
    )));

    for (const agentId of participants) {
      if (!seenByAgent.has(agentId)) seenByAgent.set(agentId, new Set());
      const seen = seenByAgent.get(agentId);
      if (seen.has(contractKey)) continue;
      seen.add(contractKey);
      counts.set(agentId, (counts.get(agentId) || 0) + 1);
    }
  }

  return counts;
}

function compareText(left, right) {
  const a = String(left ?? '').toLowerCase();
  const b = String(right ?? '').toLowerCase();
  if (a < b) return -1;
  if (a > b) return 1;
  return 0;
}

/**
 * Build a deterministic leaderboard without mutating live Atlas data.
 *
 * Contract totals use the larger of currently-visible relationships and the
 * backend's completed-contract counter so historical work remains represented.
 */
export function buildAgentLeaderboard(
  agents,
  contracts,
  reputation = {},
  sortBy = 'beats',
  limit = DEFAULT_LIMIT,
) {
  const contractCounts = visibleContractCounts(contracts);
  const entries = [];
  const seenAgentIds = new Set();

  for (const agent of (Array.isArray(agents) ? agents : [])) {
    if (!agent || typeof agent !== 'object') continue;
    const id = typeof agent.id === 'string' ? agent.id : '';
    if (!id || seenAgentIds.has(id)) continue;
    seenAgentIds.add(id);

    const rep = reputationFor(reputation, id);
    const beats = safeCount(agent.beat_count);
    const contractCount = Math.max(
      safeCount(contractCounts.get(id)),
      safeCount(rep.contracts_completed),
    );

    if (beats === 0 && contractCount === 0) continue;
    entries.push({
      id,
      name: typeof agent.name === 'string' && agent.name.trim() ? agent.name.trim() : id,
      beats,
      contracts: contractCount,
    });
  }

  const mode = sortBy === 'contracts' ? 'contracts' : 'beats';
  const secondary = mode === 'beats' ? 'contracts' : 'beats';
  entries.sort((a, b) => (
    b[mode] - a[mode]
    || b[secondary] - a[secondary]
    || compareText(a.name, b.name)
    || compareText(a.id, b.id)
  ));

  return entries.slice(0, safeLimit(limit));
}
