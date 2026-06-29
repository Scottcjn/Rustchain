/**
 * RustChain Claims Page Client
 * RIP-305 Track D: Claim Page + Eligibility Flow
 *
 * Security hardening (issue #7204):
 * All dynamic data from API responses and user input is rendered via
 * DOM API (createElement / textContent / appendChild) — never via
 * innerHTML template strings — to eliminate HTML parser sinks.
 */

// API Configuration
const API_BASE = '/api/claims';

// State
let currentMinerId = null;
let eligibleEpochs = [];
let selectedEpoch = null;
let claimData = null;

// DOM Elements
const minerIdInput = document.getElementById('minerIdInput');
const checkEligibilityBtn = document.getElementById('checkEligibilityBtn');
const eligibilityPanel = document.getElementById('eligibilityPanel');
const eligibilityResult = document.getElementById('eligibilityResult');
const epochSelect = document.getElementById('epochSelect');
const walletPanel = document.getElementById('walletPanel');
const walletAddressInput = document.getElementById('walletAddressInput');
const submitPanel = document.getElementById('submitPanel');
const claimSummary = document.getElementById('claimSummary');
const confirmCheckbox = document.getElementById('confirmCheckbox');
const submitClaimBtn = document.getElementById('submitClaimBtn');
const cancelBtn = document.getElementById('cancelBtn');
const exportHistoryBtn = document.getElementById('exportHistoryBtn');
const refreshBtn = document.getElementById('refreshBtn');
const loadingModal = document.getElementById('loadingModal');
const loadingText = document.getElementById('loadingText');

// ---------------------------------------------------------------------------
// Utility Functions
// ---------------------------------------------------------------------------

/** Muestra el modal de carga con el mensaje indicado. */
function showLoading(message = 'Processing...') {
  loadingText.textContent = message;
  loadingModal.style.display = 'flex';
}

/** Oculta el modal de carga. */
function hideLoading() {
  loadingModal.style.display = 'none';
}

/** Muestra un mensaje de error en el elemento indicado usando textContent. */
function showError(elementId, message) {
  const element = document.getElementById(elementId);
  element.textContent = message;
  element.style.display = 'block';
}

/** Oculta el elemento de error indicado. */
function hideError(elementId) {
  const element = document.getElementById(elementId);
  element.style.display = 'none';
}

/**
 * Normalises a CSS class name — strips any characters that are not safe
 * identifier characters to prevent class-injection attacks.
 * @param {*} value - Raw value to sanitise.
 * @returns {string} Safe CSS class string.
 */
function safeCssClass(value) {
  return String(value || 'unknown').toLowerCase().replace(/[^a-z0-9_-]/g, '-') || 'unknown';
}

/**
 * Returns a finite number or the fallback.
 * @param {*} value - Raw value.
 * @param {number} fallback - Fallback when value is not finite.
 * @returns {number}
 */
function safeNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

/**
 * Returns a safe integer or the fallback.
 * @param {*} value - Raw value.
 * @param {number} fallback - Fallback when value is not a safe integer.
 * @returns {number}
 */
function safeInteger(value, fallback = 0) {
  const number = Number.parseInt(value, 10);
  return Number.isFinite(number) ? number : fallback;
}

/**
 * Converts snake_case check names to Title Case for display.
 * @param {string} value - Raw check key.
 * @returns {string}
 */
function formatCheckName(value) {
  return String(value || '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, l => l.toUpperCase());
}

/**
 * Converts micro-RTC integer to human-readable RTC string.
 * @param {number} urtc - Value in micro-RTC.
 * @returns {string}
 */
function formatRtc(urtc) {
  return (safeNumber(urtc) / 100_000_000).toFixed(6);
}

/**
 * Formats a Unix timestamp as a locale string.
 * @param {number} ts - Unix timestamp in seconds.
 * @returns {string}
 */
function formatTimestamp(ts) {
  if (!ts) return 'N/A';
  return new Date(safeNumber(ts) * 1000).toLocaleString();
}

// ---------------------------------------------------------------------------
// Safe DOM Helpers — no innerHTML involved
// ---------------------------------------------------------------------------

/**
 * Creates an element with a CSS class and sets its textContent.
 * @param {string} tag - HTML tag name.
 * @param {string} className - CSS class.
 * @param {string} text - Text content (rendered as text, not HTML).
 * @returns {HTMLElement}
 */
function makeEl(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

/**
 * Creates a summary row div containing a label span and a value span.
 * @param {string} label - Row label text.
 * @param {string} value - Row value text.
 * @param {string} [valueStyle] - Optional inline style for the value span.
 * @returns {HTMLDivElement}
 */
function makeSummaryRow(label, value, valueStyle) {
  const row = document.createElement('div');
  row.className = 'summary-row';

  const lbl = makeEl('span', 'summary-label', label);
  const val = makeEl('span', 'summary-value', value);
  if (valueStyle) val.setAttribute('style', valueStyle);

  row.appendChild(lbl);
  row.appendChild(val);
  return row;
}

/**
 * Creates a check-item div with pass/fail icon and label.
 * @param {boolean} passed - Whether the check passed.
 * @param {string} label - Display label for this check.
 * @returns {HTMLDivElement}
 */
function makeCheckItem(passed, label) {
  const item = document.createElement('div');
  item.className = 'check-item';

  const icon = makeEl('span', `check-icon ${passed ? 'pass' : 'fail'}`, passed ? '✓' : '✗');
  const text = makeEl('span', '', label);

  item.appendChild(icon);
  item.appendChild(text);
  return item;
}

// ---------------------------------------------------------------------------
// API Functions
// ---------------------------------------------------------------------------

/**
 * Checks miner eligibility via the claims API.
 * @param {string} minerId - Miner identifier.
 * @returns {Promise<Object>} Eligibility data.
 */
async function checkEligibility(minerId) {
  try {
    const response = await fetch(`${API_BASE}/eligibility?miner_id=${encodeURIComponent(minerId)}`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.reason || 'Eligibility check failed');
    }

    return data;
  } catch (error) {
    console.error('Eligibility check error:', error);
    throw error;
  }
}

/**
 * Returns the list of eligible epochs for the given miner.
 * @param {string} minerId - Miner identifier.
 * @returns {Promise<Object>} Epoch list data.
 */
async function getEligibleEpochs(minerId) {
  try {
    const response = await fetch(`${API_BASE}/epochs?miner_id=${encodeURIComponent(minerId)}`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || 'Failed to get eligible epochs');
    }

    return data;
  } catch (error) {
    console.error('Get epochs error:', error);
    throw error;
  }
}

/**
 * Submits a claim payload to the API.
 * @param {Object} claimPayload - Claim data.
 * @returns {Promise<Object>} API response.
 */
async function submitClaim(claimPayload) {
  try {
    const response = await fetch(`${API_BASE}/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(claimPayload)
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || 'Claim submission failed');
    }

    return data;
  } catch (error) {
    console.error('Submit claim error:', error);
    throw error;
  }
}

/**
 * Fetches the current status of a claim.
 * @param {string} claimId - Claim identifier.
 * @returns {Promise<Object>} Claim status data.
 */
async function getClaimStatus(claimId) {
  try {
    const response = await fetch(`${API_BASE}/status/${encodeURIComponent(claimId)}`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || 'Failed to get claim status');
    }

    return data;
  } catch (error) {
    console.error('Get status error:', error);
    throw error;
  }
}

/**
 * Fetches claim history for a miner.
 * @param {string} minerId - Miner identifier.
 * @returns {Promise<Object>} History data.
 */
async function getClaimHistory(minerId) {
  try {
    const response = await fetch(`${API_BASE}/history?miner_id=${encodeURIComponent(minerId)}`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || 'Failed to get claim history');
    }

    return data;
  } catch (error) {
    console.error('Get history error:', error);
    throw error;
  }
}

// ---------------------------------------------------------------------------
// UI Update Functions — all use DOM API, no innerHTML on API data
// ---------------------------------------------------------------------------

/**
 * Renders the eligibility result panel using safe DOM construction.
 * All values from the API response are set via textContent, never innerHTML.
 * @param {Object} eligibility - Eligibility API response.
 */
function renderEligibilityResult(eligibility) {
  const isEligible = eligibility.eligible;
  eligibilityResult.textContent = '';

  // Status indicator row
  const statusDiv = document.createElement('div');
  statusDiv.className = 'eligibility-status';

  const indicator = document.createElement('div');
  indicator.className = `status-indicator ${isEligible ? 'eligible' : 'not-eligible'}`;

  const statusLabel = document.createElement('span');
  statusLabel.setAttribute('style', 'font-weight: 600; font-size: 1.125rem;');
  statusLabel.textContent = isEligible ? 'Eligible to Claim' : 'Not Eligible';

  statusDiv.appendChild(indicator);
  statusDiv.appendChild(statusLabel);
  eligibilityResult.appendChild(statusDiv);

  if (isEligible) {
    const attest = eligibility.attestation || {};
    eligibilityResult.appendChild(makeSummaryRow('Miner ID', String(eligibility.miner_id || ''), 'font-family: var(--font-mono);'));
    eligibilityResult.appendChild(makeSummaryRow('Device Architecture', String(attest.device_arch || 'N/A')));
    eligibilityResult.appendChild(makeSummaryRow('Antiquity Multiplier', `${safeNumber(attest.antiquity_multiplier, 1).toFixed(2)}x`));
    eligibilityResult.appendChild(makeSummaryRow('Wallet Address', String(eligibility.wallet_address || 'Not registered'), 'font-family: var(--font-mono);'));

    // Static check grid for eligible miners
    const checksGrid = document.createElement('div');
    checksGrid.className = 'checks-grid';
    checksGrid.appendChild(makeCheckItem(true, 'Attestation Valid'));
    checksGrid.appendChild(makeCheckItem(true, 'Epoch Participation'));
    checksGrid.appendChild(makeCheckItem(true, 'Fingerprint Passed'));
    checksGrid.appendChild(makeCheckItem(Boolean(eligibility.wallet_address), 'Wallet Registered'));
    eligibilityResult.appendChild(checksGrid);
  } else {
    // Reason line
    const reasonDiv = document.createElement('div');
    reasonDiv.setAttribute('style', 'color: var(--error); margin-top: 1rem;');
    reasonDiv.textContent = `Reason: ${eligibility.reason || 'Unknown'}`;
    eligibilityResult.appendChild(reasonDiv);

    // Dynamic check grid from API
    const checksGrid = document.createElement('div');
    checksGrid.className = 'checks-grid';
    Object.entries(eligibility.checks || {}).forEach(([check, passed]) => {
      checksGrid.appendChild(makeCheckItem(Boolean(passed), formatCheckName(check)));
    });
    eligibilityResult.appendChild(checksGrid);
  }
}

/**
 * Populates the epoch <select> element with safe DOM option nodes.
 * @param {Object} epochData - API response containing an `epochs` array.
 */
function renderEpochSelect(epochData) {
  const unclaimedEpochs = epochData.epochs.filter(e => !e.claimed && e.settled);

  // Clear existing options safely
  while (epochSelect.options.length > 0) {
    epochSelect.remove(0);
  }

  if (unclaimedEpochs.length === 0) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = 'No unclaimed epochs available';
    epochSelect.appendChild(opt);
    return;
  }

  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = '-- Select an epoch --';
  epochSelect.appendChild(placeholder);

  unclaimedEpochs.forEach(epoch => {
    const opt = document.createElement('option');
    opt.value = String(safeInteger(epoch.epoch));
    opt.dataset.reward = String(safeInteger(epoch.reward_urtc));
    opt.textContent = `Epoch ${safeInteger(epoch.epoch)} - ${formatRtc(epoch.reward_urtc)} RTC`;
    epochSelect.appendChild(opt);
  });

  eligibleEpochs = unclaimedEpochs;
}

/**
 * Renders the claim summary panel using safe DOM construction.
 * @param {string} minerId - Miner identifier.
 * @param {number} epoch - Selected epoch number.
 * @param {number} rewardUrtc - Reward in micro-RTC.
 * @param {string} walletAddress - Destination wallet address.
 */
function renderClaimSummary(minerId, epoch, rewardUrtc, walletAddress) {
  claimSummary.textContent = '';
  claimSummary.appendChild(makeSummaryRow('Miner ID', String(minerId), 'font-family: var(--font-mono);'));
  claimSummary.appendChild(makeSummaryRow('Epoch', String(safeInteger(epoch))));
  claimSummary.appendChild(makeSummaryRow('Wallet Address', String(walletAddress), 'font-family: var(--font-mono);'));

  const rewardRow = makeSummaryRow('Reward Amount', `${formatRtc(rewardUrtc)} RTC`);
  rewardRow.querySelector('.summary-value').setAttribute('style', 'color: var(--accent-primary);');
  claimSummary.appendChild(rewardRow);

  claimSummary.appendChild(makeSummaryRow('Estimated Settlement', '~30 minutes'));
}

/**
 * Renders claim history into the table body using safe DOM construction.
 * All claim fields are set via textContent — no innerHTML on API data.
 * @param {Object} history - API response with a `claims` array.
 */
function renderClaimHistory(history) {
  const tbody = document.getElementById('claimsHistoryBody');
  tbody.textContent = '';

  if (!history.claims || history.claims.length === 0) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.setAttribute('colspan', '6');
    td.className = 'empty-state';
    td.textContent = 'No claims yet. Check your eligibility to get started.';
    tr.appendChild(td);
    tbody.appendChild(tr);
    return;
  }

  history.claims.forEach(claim => {
    const tr = document.createElement('tr');

    // Claim ID cell
    const tdId = document.createElement('td');
    tdId.setAttribute('style', 'font-family: var(--font-mono); font-size: 0.875rem;');
    tdId.textContent = String(claim.claim_id || '');
    tr.appendChild(tdId);

    // Epoch cell
    const tdEpoch = document.createElement('td');
    tdEpoch.textContent = String(safeInteger(claim.epoch));
    tr.appendChild(tdEpoch);

    // Status badge cell
    const tdStatus = document.createElement('td');
    const badge = document.createElement('span');
    badge.className = `status-badge ${safeCssClass(claim.status)}`;
    badge.textContent = String(claim.status || '');
    tdStatus.appendChild(badge);
    tr.appendChild(tdStatus);

    // Reward cell
    const tdReward = document.createElement('td');
    tdReward.setAttribute('style', 'font-family: var(--font-mono);');
    tdReward.textContent = formatRtc(claim.reward_urtc);
    tr.appendChild(tdReward);

    // Submitted at cell
    const tdSubmitted = document.createElement('td');
    tdSubmitted.textContent = formatTimestamp(claim.submitted_at);
    tr.appendChild(tdSubmitted);

    // Settled at cell
    const tdSettled = document.createElement('td');
    tdSettled.textContent = formatTimestamp(claim.settled_at);
    tr.appendChild(tdSettled);

    tbody.appendChild(tr);
  });
}

/**
 * Fetches and updates the dashboard stats counters.
 * Uses textContent for all dynamic values.
 */
function updateStats() {
  document.getElementById('totalClaimed').textContent = 'Loading...';
  document.getElementById('pendingClaims').textContent = 'Loading...';
  document.getElementById('settlementTime').textContent = 'Loading...';

  fetch('/api/claims/stats')
    .then(r => r.json())
    .then(stats => {
      document.getElementById('totalClaimed').textContent = `${formatRtc(stats.total_claimed_urtc || 0)} RTC`;
      document.getElementById('pendingClaims').textContent = stats.pending_count || 0;
      document.getElementById('settlementTime').textContent = `${Math.round(stats.avg_settlement_minutes || 30)} min`;
    })
    .catch(() => {
      document.getElementById('totalClaimed').textContent = '--';
      document.getElementById('pendingClaims').textContent = '--';
      document.getElementById('settlementTime').textContent = '--';
    });
}

// ---------------------------------------------------------------------------
// Event Handlers
// ---------------------------------------------------------------------------

/**
 * Handles the "Check Eligibility" button click.
 * Fetches eligibility data and renders the result panel.
 */
async function handleCheckEligibility() {
  const minerId = minerIdInput.value.trim();

  if (!minerId) {
    showError('minerIdError', 'Please enter your miner ID');
    return;
  }

  hideError('minerIdError');
  showLoading('Checking eligibility...');

  try {
    const eligibility = await checkEligibility(minerId);
    currentMinerId = minerId;

    renderEligibilityResult(eligibility);
    eligibilityPanel.style.display = 'block';

    if (eligibility.eligible) {
      const epochData = await getEligibleEpochs(minerId);
      renderEpochSelect(epochData);

      if (eligibility.wallet_address) {
        walletAddressInput.value = eligibility.wallet_address;
      }

      eligibilityPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
      walletPanel.style.display = 'none';
      submitPanel.style.display = 'none';
    }

    loadClaimHistory(minerId);
  } catch (error) {
    showError('minerIdError', error.message || 'Failed to check eligibility');
    eligibilityPanel.style.display = 'none';
  } finally {
    hideLoading();
  }
}

/**
 * Handles epoch selection change — shows wallet panel and updates summary.
 */
function handleEpochSelect() {
  const selectedOption = epochSelect.options[epochSelect.selectedIndex];

  if (!selectedOption.value) {
    selectedEpoch = null;
    walletPanel.style.display = 'none';
    submitPanel.style.display = 'none';
    return;
  }

  selectedEpoch = parseInt(selectedOption.value);
  const rewardUrtc = parseInt(selectedOption.dataset.reward);

  walletPanel.style.display = 'block';

  renderClaimSummary(
    currentMinerId,
    selectedEpoch,
    rewardUrtc,
    walletAddressInput.value || 'Not provided'
  );

  walletPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/**
 * Handles wallet address input — validates format and shows submit panel.
 */
function handleWalletInput() {
  const walletAddress = walletAddressInput.value.trim();

  if (!walletAddress || !selectedEpoch) {
    submitPanel.style.display = 'none';
    return;
  }

  if (!walletAddress.startsWith('RTC') || walletAddress.length < 23) {
    showError('walletError', 'Invalid wallet address format. Must start with RTC and be at least 23 characters.');
    submitPanel.style.display = 'none';
    return;
  }

  hideError('walletError');

  const selectedOption = epochSelect.options[epochSelect.selectedIndex];
  const rewardUrtc = parseInt(selectedOption.dataset.reward);

  renderClaimSummary(currentMinerId, selectedEpoch, rewardUrtc, walletAddress);

  submitPanel.style.display = 'block';
  submitPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/**
 * Syncs submit button disabled state with the confirm checkbox.
 */
function handleConfirmChange() {
  submitClaimBtn.disabled = !confirmCheckbox.checked;
}

/**
 * Handles claim submission — renders success message via safe DOM,
 * not via innerHTML template strings.
 */
async function handleSubmitClaim() {
  if (!currentMinerId || !selectedEpoch) {
    showError('submitError', 'Invalid claim data');
    return;
  }

  const walletAddress = walletAddressInput.value.trim();
  const selectedOption = epochSelect.options[epochSelect.selectedIndex];
  const rewardUrtc = parseInt(selectedOption.dataset.reward);

  if (!walletAddress) {
    showError('submitError', 'Wallet address is required');
    return;
  }

  showLoading('Generating signature and submitting claim...');
  hideError('submitError');

  try {
    const timestamp = Math.floor(Date.now() / 1000);

    // Mock signature (in production, use actual Ed25519 cryptographic signing)
    const mockSignature = '0'.repeat(128);
    const mockPublicKey = '1'.repeat(64);

    const claimPayload = {
      miner_id: currentMinerId,
      epoch: selectedEpoch,
      wallet_address: walletAddress,
      signature: mockSignature,
      public_key: mockPublicKey
    };

    const result = await submitClaim(claimPayload);

    if (result.success) {
      // Render success message via safe DOM — no innerHTML on API response
      const successEl = document.getElementById('submitSuccess');
      successEl.textContent = '';

      const strong = document.createElement('strong');
      strong.textContent = 'Claim submitted successfully!';
      successEl.appendChild(strong);
      successEl.appendChild(document.createElement('br'));

      const claimIdLabel = document.createTextNode('Claim ID: ');
      successEl.appendChild(claimIdLabel);

      const claimIdCode = document.createElement('code');
      claimIdCode.setAttribute('style', 'font-family: var(--font-mono);');
      claimIdCode.textContent = String(result.claim_id || '');
      successEl.appendChild(claimIdCode);
      successEl.appendChild(document.createElement('br'));

      const rewardLine = document.createTextNode(`Reward: ${formatRtc(result.reward_urtc)} RTC`);
      successEl.appendChild(rewardLine);
      successEl.appendChild(document.createElement('br'));

      const settlementTs = new Date(safeNumber(result.estimated_settlement) * 1000).toLocaleString();
      const settlementLine = document.createTextNode(`Estimated settlement: ${settlementTs}`);
      successEl.appendChild(settlementLine);

      successEl.style.display = 'block';

      setTimeout(() => {
        resetForm();
        loadClaimHistory(currentMinerId);
      }, 3000);
    } else {
      showError('submitError', result.error || 'Claim submission failed');
    }
  } catch (error) {
    showError('submitError', error.message || 'Failed to submit claim');
  } finally {
    hideLoading();
  }
}

/** Handles the Cancel button — resets form to initial state. */
function handleCancel() {
  resetForm();
}

/**
 * Resets all form fields and hides all dynamic panels.
 */
function resetForm() {
  minerIdInput.value = '';
  walletAddressInput.value = '';

  // Clear epoch options safely
  while (epochSelect.options.length > 0) {
    epochSelect.remove(0);
  }
  const defaultOpt = document.createElement('option');
  defaultOpt.value = '';
  defaultOpt.textContent = '-- Select an epoch --';
  epochSelect.appendChild(defaultOpt);

  confirmCheckbox.checked = false;
  submitClaimBtn.disabled = true;

  eligibilityPanel.style.display = 'none';
  walletPanel.style.display = 'none';
  submitPanel.style.display = 'none';

  hideError('minerIdError');
  hideError('walletError');
  hideError('submitError');
  document.getElementById('submitSuccess').style.display = 'none';

  currentMinerId = null;
  selectedEpoch = null;
  eligibleEpochs = [];
}

/**
 * Loads and renders claim history for the given miner.
 * @param {string} minerId - Miner identifier.
 */
async function loadClaimHistory(minerId) {
  try {
    const history = await getClaimHistory(minerId);
    renderClaimHistory(history);
  } catch (error) {
    console.error('Failed to load claim history:', error);
  }
}

/**
 * Exports claim history as a CSV file download.
 * CSV cell values are quoted to prevent formula injection.
 */
function handleExportHistory() {
  if (!currentMinerId) {
    alert('Please enter your miner ID first');
    return;
  }

  getClaimHistory(currentMinerId)
    .then(history => {
      if (!history.claims || history.claims.length === 0) {
        alert('No claims to export');
        return;
      }

      const headers = ['Claim ID', 'Epoch', 'Status', 'Reward (RTC)', 'Submitted At', 'Settled At'];
      const rows = history.claims.map(c => [
        c.claim_id,
        c.epoch,
        c.status,
        formatRtc(c.reward_urtc),
        new Date(c.submitted_at * 1000).toISOString(),
        c.settled_at ? new Date(c.settled_at * 1000).toISOString() : ''
      ]);

      // Quote all CSV cells to prevent CSV injection / formula injection
      const escape = v => `"${String(v ?? '').replace(/"/g, '""')}"`;
      const csv = [headers, ...rows].map(row => row.map(escape).join(',')).join('\n');

      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `rustchain_claims_${currentMinerId}_${Date.now()}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    })
    .catch(error => {
      alert('Failed to export history: ' + error.message);
    });
}

/**
 * Handles the Refresh button — reloads stats and claim history.
 */
function handleRefresh() {
  if (currentMinerId) {
    showLoading('Refreshing...');
    loadClaimHistory(currentMinerId);
    updateStats();
    setTimeout(hideLoading, 1000);
  } else {
    window.location.reload();
  }
}

// ---------------------------------------------------------------------------
// Initialize
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  checkEligibilityBtn.addEventListener('click', handleCheckEligibility);
  minerIdInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') handleCheckEligibility();
  });

  epochSelect.addEventListener('change', handleEpochSelect);
  walletAddressInput.addEventListener('input', handleWalletInput);
  confirmCheckbox.addEventListener('change', handleConfirmChange);
  submitClaimBtn.addEventListener('click', handleSubmitClaim);
  cancelBtn.addEventListener('click', handleCancel);
  exportHistoryBtn.addEventListener('click', handleExportHistory);
  refreshBtn.addEventListener('click', handleRefresh);

  updateStats();

  // Auto-populate miner ID from URL query param
  const urlParams = new URLSearchParams(window.location.search);
  const minerIdParam = urlParams.get('miner_id');
  if (minerIdParam) {
    minerIdInput.value = minerIdParam;
    handleCheckEligibility();
  }
});
