/**
 * RustChain Claims Page Client
 * RIP-305 Track D: Claim Page + Eligibility Flow
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

// Utility Functions
function showLoading(message = 'Processing...') {
  loadingText.textContent = message;
  loadingModal.style.display = 'flex';
}

function hideLoading() {
  loadingModal.style.display = 'none';
}

function showError(elementId, message) {
  const element = document.getElementById(elementId);
  element.textContent = message;
  element.style.display = 'block';
}

function hideError(elementId) {
  const element = document.getElementById(elementId);
  element.style.display = 'none';
}

function safeCssClass(value) {
  return String(value || 'unknown').toLowerCase().replace(/[^a-z0-9_-]/g, '-') || 'unknown';
}

function safeNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function safeInteger(value, fallback = 0) {
  const number = Number.parseInt(value, 10);
  return Number.isFinite(number) ? number : fallback;
}

function formatCheckName(value) {
  return String(value || '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, l => l.toUpperCase());
}

function formatRtc(urtc) {
  return (safeNumber(urtc) / 100_000_000).toFixed(6);
}

function createElement(tagName, options = {}, children = []) {
  const element = document.createElement(tagName);

  if (options.className) {
    element.className = options.className;
  }
  if (options.text !== undefined) {
    element.textContent = String(options.text);
  }
  if (options.colSpan !== undefined) {
    element.colSpan = options.colSpan;
  }
  if (options.styles) {
    Object.assign(element.style, options.styles);
  }
  if (options.dataset) {
    Object.entries(options.dataset).forEach(([key, value]) => {
      element.dataset[key] = String(value);
    });
  }

  children.forEach(child => element.append(child));
  return element;
}

function createOption(label, value = '', dataset = {}) {
  const option = new Option(label, String(value));
  Object.entries(dataset).forEach(([key, datasetValue]) => {
    option.dataset[key] = String(datasetValue);
  });
  return option;
}

function createSummaryRow(label, value, options = {}) {
  return createElement('div', { className: 'summary-row' }, [
    createElement('span', { className: 'summary-label', text: label }),
    createElement('span', {
      className: 'summary-value',
      text: value,
      styles: options.valueStyles || {}
    })
  ]);
}

function createCheckItem(label, passed) {
  return createElement('div', { className: 'check-item' }, [
    createElement('span', {
      className: `check-icon ${passed ? 'pass' : 'fail'}`,
      text: passed ? String.fromCharCode(10003) : String.fromCharCode(10007)
    }),
    createElement('span', { text: label })
  ]);
}

function createTableCell(value, options = {}) {
  return createElement('td', {
    className: options.className,
    text: value,
    styles: options.styles || {},
    colSpan: options.colSpan
  });
}

function renderSubmitSuccess(result) {
  const submitSuccess = document.getElementById('submitSuccess');
  const claimId = createElement('code', {
    text: result.claim_id,
    styles: { fontFamily: 'var(--font-mono)' }
  });

  submitSuccess.replaceChildren(
    createElement('strong', { text: 'Claim submitted successfully!' }),
    document.createElement('br'),
    'Claim ID: ',
    claimId,
    document.createElement('br'),
    `Reward: ${formatRtc(result.reward_urtc)} RTC`,
    document.createElement('br'),
    `Estimated settlement: ${new Date(safeNumber(result.estimated_settlement) * 1000).toLocaleString()}`
  );
  submitSuccess.style.display = 'block';
}

function formatTimestamp(ts) {
  if (!ts) return 'N/A';
  return new Date(safeNumber(ts) * 1000).toLocaleString();
}

function generateClaimId(minerId, epoch) {
  return `claim_${epoch}_${minerId}`;
}

// API Functions
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

async function submitClaim(claimPayload) {
  try {
    const response = await fetch(`${API_BASE}/submit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
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

// UI Update Functions
function renderEligibilityResult(eligibility) {
  const isEligible = eligibility.eligible;

  const status = createElement('div', { className: 'eligibility-status' }, [
    createElement('div', {
      className: `status-indicator ${isEligible ? 'eligible' : 'not-eligible'}`
    }),
    createElement('span', {
      text: isEligible ? 'Eligible to Claim' : 'Not Eligible',
      styles: {
        fontWeight: '600',
        fontSize: '1.125rem'
      }
    })
  ]);

  const detailNodes = [];
  if (isEligible) {
    detailNodes.push(
      createSummaryRow('Miner ID', eligibility.miner_id, {
        valueStyles: { fontFamily: 'var(--font-mono)' }
      }),
      createSummaryRow('Device Architecture', eligibility.attestation?.device_arch || 'N/A'),
      createSummaryRow(
        'Antiquity Multiplier',
        `${safeNumber(eligibility.attestation?.antiquity_multiplier, 1).toFixed(2)}x`
      ),
      createSummaryRow('Wallet Address', eligibility.wallet_address || 'Not registered', {
        valueStyles: { fontFamily: 'var(--font-mono)' }
      })
    );
  } else {
    detailNodes.push(createElement('div', {
      text: 'Reason: ' + (eligibility.reason || 'Unknown'),
      styles: {
        color: 'var(--error)',
        marginTop: '1rem'
      }
    }));
  }

  const checks = createElement('div', { className: 'checks-grid' });
  if (isEligible) {
    checks.replaceChildren(
      createCheckItem('Attestation Valid', true),
      createCheckItem('Epoch Participation', true),
      createCheckItem('Fingerprint Passed', true),
      createCheckItem('Wallet Registered', Boolean(eligibility.wallet_address))
    );
  } else {
    checks.replaceChildren(
      ...Object.entries(eligibility.checks || {}).map(([check, passed]) =>
        createCheckItem(formatCheckName(check), Boolean(passed))
      )
    );
  }

  eligibilityResult.replaceChildren(status, ...detailNodes, checks);
}

function renderEpochSelect(epochData) {
  const unclaimedEpochs = epochData.epochs.filter(e => !e.claimed && e.settled);

  if (unclaimedEpochs.length === 0) {
    epochSelect.replaceChildren(createOption('No unclaimed epochs available'));
    return;
  }

  epochSelect.replaceChildren(
    createOption('-- Select an epoch --'),
    ...unclaimedEpochs.map(epoch => {
      const epochNumber = safeInteger(epoch.epoch);
      const rewardUrtc = safeInteger(epoch.reward_urtc);
      return createOption(
        `Epoch ${epochNumber} - ${formatRtc(epoch.reward_urtc)} RTC`,
        epochNumber,
        { reward: rewardUrtc }
      );
    })
  );

  eligibleEpochs = unclaimedEpochs;
}

function renderClaimSummary(minerId, epoch, rewardUrtc, walletAddress) {
  claimSummary.replaceChildren(
    createSummaryRow('Miner ID', minerId, {
      valueStyles: { fontFamily: 'var(--font-mono)' }
    }),
    createSummaryRow('Epoch', safeInteger(epoch)),
    createSummaryRow('Wallet Address', walletAddress, {
      valueStyles: { fontFamily: 'var(--font-mono)' }
    }),
    createSummaryRow('Reward Amount', `${formatRtc(rewardUrtc)} RTC`, {
      valueStyles: { color: 'var(--accent-primary)' }
    }),
    createSummaryRow('Estimated Settlement', '~30 minutes')
  );
}

function renderClaimHistory(history) {
  const tbody = document.getElementById('claimsHistoryBody');

  if (!history.claims || history.claims.length === 0) {
    tbody.replaceChildren(createElement('tr', {}, [
      createTableCell('No claims yet. Check your eligibility to get started.', {
        className: 'empty-state',
        colSpan: 6
      })
    ]));
    return;
  }

  tbody.replaceChildren(...history.claims.map(claim => {
    const statusBadge = createElement('span', {
      className: `status-badge ${safeCssClass(claim.status)}`,
      text: claim.status
    });

    return createElement('tr', {}, [
      createTableCell(claim.claim_id, {
        styles: {
          fontFamily: 'var(--font-mono)',
          fontSize: '0.875rem'
        }
      }),
      createTableCell(safeInteger(claim.epoch)),
      createElement('td', {}, [statusBadge]),
      createTableCell(formatRtc(claim.reward_urtc), {
        styles: { fontFamily: 'var(--font-mono)' }
      }),
      createTableCell(formatTimestamp(claim.submitted_at)),
      createTableCell(formatTimestamp(claim.settled_at))
    ]);
  }));
}

function updateStats() {
  // Update dashboard stats (would come from API in production)
  document.getElementById('totalClaimed').textContent = 'Loading...';
  document.getElementById('pendingClaims').textContent = 'Loading...';
  document.getElementById('settlementTime').textContent = 'Loading...';
  
  // In production, fetch from API
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

// Event Handlers
async function handleCheckEligibility() {
  const minerId = minerIdInput.value.trim();
  
  if (!minerId) {
    showError('minerIdError', 'Please enter your miner ID');
    return;
  }
  
  hideError('minerIdError');
  showLoading('Checking eligibility...');
  
  try {
    // Check eligibility
    const eligibility = await checkEligibility(minerId);
    currentMinerId = minerId;
    
    renderEligibilityResult(eligibility);
    eligibilityPanel.style.display = 'block';
    
    if (eligibility.eligible) {
      // Get eligible epochs
      const epochData = await getEligibleEpochs(minerId);
      renderEpochSelect(epochData);
      
      // Pre-fill wallet address if available
      if (eligibility.wallet_address) {
        walletAddressInput.value = eligibility.wallet_address;
      }
      
      // Scroll to eligibility panel
      eligibilityPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
      // Hide subsequent panels if not eligible
      walletPanel.style.display = 'none';
      submitPanel.style.display = 'none';
    }
    
    // Load claim history
    loadClaimHistory(minerId);
  } catch (error) {
    showError('minerIdError', error.message || 'Failed to check eligibility');
    eligibilityPanel.style.display = 'none';
  } finally {
    hideLoading();
  }
}

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
  
  // Update claim summary
  renderClaimSummary(
    currentMinerId,
    selectedEpoch,
    rewardUrtc,
    walletAddressInput.value || 'Not provided'
  );
  
  walletPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function handleWalletInput() {
  const walletAddress = walletAddressInput.value.trim();
  
  if (!walletAddress || !selectedEpoch) {
    submitPanel.style.display = 'none';
    return;
  }
  
  // Validate wallet address format
  if (!walletAddress.startsWith('RTC') || walletAddress.length < 23) {
    showError('walletError', 'Invalid wallet address format. Must start with RTC and be at least 23 characters.');
    submitPanel.style.display = 'none';
    return;
  }
  
  hideError('walletError');
  
  // Update claim summary
  const selectedOption = epochSelect.options[epochSelect.selectedIndex];
  const rewardUrtc = parseInt(selectedOption.dataset.reward);
  
  renderClaimSummary(
    currentMinerId,
    selectedEpoch,
    rewardUrtc,
    walletAddress
  );
  
  submitPanel.style.display = 'block';
  submitPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function handleConfirmChange() {
  submitClaimBtn.disabled = !confirmCheckbox.checked;
}

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
    // In production, this would generate a real Ed25519 signature
    // For now, we'll use a mock signature
    const timestamp = Math.floor(Date.now() / 1000);
    const payload = {
      miner_id: currentMinerId,
      epoch: selectedEpoch,
      wallet_address: walletAddress,
      timestamp: timestamp
    };
    
    // Mock signature (in production, use actual cryptographic signing)
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
      renderSubmitSuccess(result);
      
      // Reset form
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

function handleCancel() {
  resetForm();
}

function resetForm() {
  minerIdInput.value = '';
  walletAddressInput.value = '';
  epochSelect.replaceChildren(createOption('-- Select an epoch --'));
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

async function loadClaimHistory(minerId) {
  try {
    const history = await getClaimHistory(minerId);
    renderClaimHistory(history);
  } catch (error) {
    console.error('Failed to load claim history:', error);
  }
}

function handleExportHistory() {
  if (!currentMinerId) {
    alert('Please enter your miner ID first');
    return;
  }
  
  // Get history data and export as CSV
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
      
      const csv = [headers, ...rows].map(row => row.join(',')).join('\n');
      
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

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  // Event listeners
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
  
  // Initial stats load
  updateStats();
  
  // Check if miner ID is in URL query params
  const urlParams = new URLSearchParams(window.location.search);
  const minerIdParam = urlParams.get('miner_id');
  if (minerIdParam) {
    minerIdInput.value = minerIdParam;
    handleCheckEligibility();
  }
});
