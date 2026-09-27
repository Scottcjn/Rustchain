// SPDX-License-Identifier: MIT

const SECOND_TO_MILLISECOND_CUTOFF = 1_000_000_000_000;

function text(value, fallback = '') {
  const normalized = String(value ?? '').trim();
  return normalized || fallback;
}

function compareText(left, right) {
  if (left < right) return -1;
  if (left > right) return 1;
  return 0;
}

export function contractTimeMillis(value) {
  if (value === null || value === undefined || value === '') return null;

  const numeric = Number(value);
  let milliseconds;
  if (Number.isFinite(numeric)) {
    if (numeric < 0) return null;
    milliseconds = numeric < SECOND_TO_MILLISECOND_CUTOFF
      ? numeric * 1000
      : numeric;
  } else {
    milliseconds = Date.parse(String(value));
  }

  if (!Number.isFinite(milliseconds)) return null;
  const date = new Date(milliseconds);
  return Number.isNaN(date.getTime()) ? null : date.getTime();
}

export function contractTimestampIso(value) {
  const milliseconds = contractTimeMillis(value);
  return milliseconds === null ? '' : new Date(milliseconds).toISOString();
}

export function formatContractTimestamp(value) {
  const iso = contractTimestampIso(value);
  return iso ? `${iso.slice(0, 19).replace('T', ' ')} UTC` : 'TIME UNKNOWN';
}

export function buildContractHistory(contracts, agentId) {
  const selectedId = text(agentId);
  if (!selectedId || !Array.isArray(contracts)) return [];

  return contracts
    .filter(contract => contract && typeof contract === 'object')
    .map(contract => {
      const from = text(contract.from);
      const to = text(contract.to);
      const direction = from === selectedId ? 'outgoing' : 'incoming';
      const counterpartyId = direction === 'outgoing' ? to : from;
      const createdAtMillis = contractTimeMillis(contract.created_at);
      const type = text(contract.type, 'contract').toLowerCase();
      const state = text(contract.state, 'unknown').toLowerCase();
      const id = text(contract.id, 'untracked');
      const deterministicKey = [
        id, from, to, type, state,
        text(contract.amount), text(contract.currency), text(contract.term),
      ].join('\u0000');

      return {
        ...contract,
        id,
        from,
        to,
        type,
        state,
        direction,
        counterpartyId,
        createdAtMillis,
        createdAtIso: createdAtMillis === null
          ? ''
          : new Date(createdAtMillis).toISOString(),
        deterministicKey,
      };
    })
    .filter(contract => contract.from === selectedId || contract.to === selectedId)
    .sort((left, right) => {
      if (left.createdAtMillis === null && right.createdAtMillis !== null) return 1;
      if (left.createdAtMillis !== null && right.createdAtMillis === null) return -1;
      if (left.createdAtMillis !== right.createdAtMillis) {
        return right.createdAtMillis - left.createdAtMillis;
      }
      return compareText(left.deterministicKey, right.deterministicKey);
    })
    .map(({ deterministicKey: _deterministicKey, ...contract }) => contract);
}
