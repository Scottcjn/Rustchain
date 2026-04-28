/聘
 * RTC Pull Request Reward — GitHub Action
 * Bounty #2864 — universe7creator
 *
 * Fires on pull_request.closed (merged==true).
 * Awards configurable RTC to contributor's registered wallet.
 * Supports dry-run, cooldown tracking, and PR-body wallet extraction.
 *

const core = require('@actions/core');
const github = require('@actions/github');

const NODE_URL    = process.env.NODE_URL    || core.getInput('node-url')    || 'https://50.28.86.131';
const ADMIN_KEY   = core.getInput('admin-key')  || '';
const DRY_RUN     = (core.getInput('dry-run') || 'false').toLowerCase() === 'true';
const DEF_AMOUNT  = parseFloat(core.getInput('amount') || '5');
const WALLET_FROM  = core.getInput('wallet-from') || '';
const REGISTRY_URL = core.getInput('registry-url') || `${NODE_URL}/wallet/registry`;
const COOLDOWN_MIN = parseInt(core.getInput('cooldowns-minutes') || '60', 10);

// ── Helpers ────────────────────────────────────────────────────────────────────

async function rpcFetch(path, body) {
  const url = `${NODE_URL}${path}`;
  core.info(`→ RPC ${body ? 'POST' : 'GET'} ${url}`);
  try {
    const opts = {
      method: body ? 'POST' : 'GET',
      headers: { 'Content-Type': 'application/json' },
      signal: AbortSignal.timeout(15000),
    };
    if (body) opts.body = JSON.stringify(body);
    const r = await fetch(url, opts);
    const text = await r.text();
    let json;
    try { json = JSON.parse(text); } catch { json = { raw: text }; }
    core.info(`  ← ${r.status} ${JSON.stringify(json).slice(0, 200)}`);
    return { ok: r.ok, status: r.status, data: json };
  } catch (e) {
    core.warning(`RPC error: ${e.message}`);
    return { ok: false, status: 0, data: { error: e.message } };
  }
}

async function checkBalance(minerId) {
  const { data } = await rpcFetch(`/wallet/balance?miner_id=${encodeURIComponent(minerId)}`, null);
  return data?.amount_rtc ?? data?.balance ?? data?.amount_i64 ?? null;
}

async function doTransfer(fromWallet, toWallet, amount, adminKey) {
  if (DRY_RUN) {
    core.info(`[DRY-RUN] Would transfer ${amount} RTC ${fromWallet} → ${toWallet}`);
    return { success: true, txId: 'dry-run-tx', ticket_id: 'dry-run-ticket' };
  }
  const body = { from: fromWallet, to: toWallet, amount };
  if (adminKey) body.admin_key = adminKey;
  const { ok, data } = await rpcFetch('/wallet/transfer', body);
  if (!ok) return { success: false, error: data?.error || data?.message || 'transfer failed' };
  return { success: true, txId: data.txId || data.ticket_id || 'unknown', ticket_id: data.ticket_id };
}

// Look up a wallet by miner_id in the on-chain registry.
async function resolveWallet(minerId) {
  const { data } = await rpcFetch(`/wallet/registry?miner_id=${encodeURIComponent(minerId)}`, null);
  if (data?.wallet_id) return data.wallet_id;
  // Fallback: treat miner_id as wallet name directly
  return minerId;
}

// Extract wallet name from PR body or description.
// Supports several formats:
//   Wallet: RTC<hex>
//   Wallet: <miner_id>
//   /wallet <miner_id>
//   /register <miner_id>
function extractWalletFromBody(body) {
  if (!body) return null;
  const lines = (body || '').split('\n');
  for (const line of lines) {
    const l = line.trim();
    if (l.startsWith('Wallet:') || l.startsWith('wallet:') || l.startsWith('WALLET:')) {
      return l.split(':').slice(1).join(':').trim();
    }
  }
  // Allow inline mention:  wallet RTC<hex> or /wallet <id>
  const m = body.match(/wallet[:\s]+(RTC[a-fA-F0-9]{40,})/i)
         || body.match(/wallet[:\s]+([a-zA-Z0-9_-]{3,32})/)
         || body.match(/\/wallet\s+([a-zA-Z0-9_-]{3,32})/)
         || body.match(/\/register\s+([a-zA-Z0-9_-]{3,32})/);
  return m ? m[1] : null;
}

// Build a stable cache key for the cooldowns JSON artifact.
function cooldownKey(wallet) { return `cooldown_${wallet}`; }

async function loadCooldownArtifact(artifactClient, wallet) {
  const name = cooldownKey(wallet);
  try {
    const download = await artifactClient.actions.downloadArtifact({
      owner: github.context.repo.owner,
      repo: github.context.repo.repo,
      artifactName: name,
      archivePath: '/tmp/cooldown',
    });
    if (!download) return null;
    return JSON.parse(require('fs').readFileSync('/tmp/cooldown', 'utf8'));
  } catch { return null; }
}

async function saveCooldownArtifact(artifactClient, wallet, record) {
  const name = cooldownKey(wallet);
  const path = '/tmp/cooldown';
  require('fs').writeFileSync(path, JSON.stringify(record));
  try {
    await artifactClient.actions.uploadArtifact({
      owner: github.context.repo.owner,
      repo: github.context.repo.repo,
      artifactName: name,
      files: [{ name: 'cooldown', path }],
      retentionDays: 1,
      overwrite: true,
    });
  } catch (e) {
    core.warning(`Could not persist cooldown: ${e.message}`);
  }
}

// ── Main ────────────────────────────────────────────────────────────────────────

async function run() {
  const ctx = github.context;
  const pr  = ctx.payload.pull_request;

  if (!pr?.merged) {
    core.info('PR was closed without merging — nothing to do.');
    return;
  }

  const contributor = pr.user?.login;
  if (!contributor) { core.setFailed('Cannot determine PR author'); return; }

  // ── Wallet resolution ────────────────────────────────────────────────────────
  let wallet = extractWalletFromBody(pr.body + '\n' + (pr.description || ''));

  if (!wallet) {
    core.info(`No wallet in PR body for @${contributor}; checking registry…`);
    wallet = await resolveWallet(contributor);
    if (!wallet || wallet === contributor) {
      core.warning(`No registered wallet for @${contributor} — skipping reward.`);
      core.notice(`@${contributor} can add a wallet line to their PR body:\n  Wallet: <miner_id>`);
      return;
    }
  }

  core.info(`Reward target wallet: ${wallet}`);

  // ── Cooldown check ───────────────────────────────────────────────────────────
  if (COOLDOWN_MIN > 0) {
    const token = core.getInput('github-token');
    const octokit = github.getOctokit(token);
    const art = github.getArtifactClient();
    const prev = await loadCooldownArtifact(art, wallet);
    if (prev) {
      const elapsed = (Date.now() - new Date(prev.ts).getTime()) / 1000 / 60;
      if (elapsed < COOLDOWN_MIN) {
        core.info(`Cooldown active for ${wallet} (${elapsed.toFixed(1)}/${COOLDOWN_MIN} min) — skipping.`);
        return;
      }
    }
    await saveCooldownArtifact(art, wallet, { ts: new Date().toISOString(), pr: pr.number });
  }

  // ── Transfer ─────────────────────────────────────────────────────────────────
  const fromWallet = WALLET_FROM || contributor;
  const result = await doTransfer(fromWallet, wallet, DEF_AMOUNT, ADMIN_KEY);

  const amount  = DEF_AMOUNT;
  const txUrl   = `${NODE_URL}/tx/${result.txId || result.ticket_id || '?'}`;

  const lines = [
    `## 🎉 PR Merged — RTC Reward Issued`,
    ``,
    `| Field | Value |`,
    `|-------|-------|`,
    `| Contributor | @${contributor} |`,
    `| Wallet | \`${wallet}\` |`,
    `| Amount | **${amount} RTC** |`,
    `| TX / Ticket | \`${result.txId || result.ticket_id || 'dry-run'}\` |`,
    `| Explorer | ${txUrl} |`,
    ``,
    DRY_RUN
      ? '> ⚠️ **Dry-run mode** — no real transfer was made.'
      : '> ✅ Reward queued. Confirmations depend on node settlement interval.',
  ];

  const body = lines.join('\n');

  const token = core.getInput('github-token');
  const octokit = github.getOctokit(token);
  const { owner, repo } = ctx.repo;

  await octokit.rest.issues.createComment({ owner, repo, issue_number: pr.number, body });

  if (!result.success) {
    core.setFailed(`Transfer failed: ${result.error}`);
  } else {
    core.info(`Reward posted for #${pr.number}: ${amount} RTC → ${wallet}`);
  }
}

run().catch(e => core.setFailed(e.message));
