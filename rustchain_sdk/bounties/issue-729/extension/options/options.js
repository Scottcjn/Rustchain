/**
 * BoTTube Chrome Extension - Options Page Script
 * Handles settings configuration and management
 */

const API_BASE = 'https://bottube.ai';
const EXTENSION_VERSION = '1.0.0';

document.addEventListener('DOMContentLoaded', async () => {
  // Set version
  document.getElementById('extension-version').textContent = EXTENSION_VERSION;

  // Load saved settings
  await loadSettings();

  // Form handlers
  document.getElementById('api-form').addEventListener('submit', handleApiSave);
  document.getElementById('btn-test-connection').addEventListener('click', testConnection);
  document.getElementById('btn-save-wallet').addEventListener('click', handleSaveWallet);
  document.getElementById('btn-clear-cache').addEventListener('click', clearCache);
  document.getElementById('btn-reset-settings').addEventListener('click', resetSettings);

  // Notification toggle handlers
  ['notify-upload', 'notify-vote', 'notify-reward', 'notify-status'].forEach(id => {
    document.getElementById(id).addEventListener('change', saveNotificationSettings);
  });

  // Cache TTL handler
  document.getElementById('cache-ttl').addEventListener('change', saveAdvancedSettings);
});

/**
 * Load saved settings from chrome storage
 */
async function loadSettings() {
  try {
    const result = await chrome.storage.sync.get([
      'apiKey',
      'apiBaseUrl',
      'walletAddress',
      'notifyUpload',
      'notifyVote',
      'notifyReward',
      'notifyStatus',
      'cacheTtl'
    ]);

    // API settings
    if (result.apiKey) {
      document.getElementById('api-key').value = result.apiKey;
    }
    if (result.apiBaseUrl) {
      document.getElementById('api-base-url').value = result.apiBaseUrl;
    }

    // Wallet
    if (result.walletAddress) {
      document.getElementById('wallet-address').textContent = truncateAddress(result.walletAddress);
      document.getElementById('wallet-address-input').value = result.walletAddress;
    }

    // Notification settings
    document.getElementById('notify-upload').checked = result.notifyUpload !== false;
    document.getElementById('notify-vote').checked = result.notifyVote !== false;
    document.getElementById('notify-reward').checked = result.notifyReward !== false;
    document.getElementById('notify-status').checked = result.notifyStatus === true;

    // Advanced settings
    if (result.cacheTtl) {
      document.getElementById('cache-ttl').value = result.cacheTtl;
    }
  } catch (err) {
    console.error('Error loading settings:', err);
    showStatus('Failed to load settings', 'error');
  }
}

/**
 * Handle API settings save
 */
async function handleApiSave(e) {
  e.preventDefault();

  const apiKey = document.getElementById('api-key').value.trim();
  const apiBaseUrl = document.getElementById('api-base-url').value.trim() || API_BASE;

  try {
    await chrome.storage.sync.set({
      apiKey,
      apiBaseUrl: apiBaseUrl.replace(/\/$/, '') // Remove trailing slash
    });

    showStatus('Settings saved successfully!', 'success');

    // Test connection if API key provided
    if (apiKey) {
      await testConnection();
    }
  } catch (err) {
    console.error('Error saving settings:', err);
    showStatus('Failed to save settings', 'error');
  }
}

/**
 * Test API connection
 */
async function testConnection() {
  const btn = document.getElementById('btn-test-connection');
  const apiKey = document.getElementById('api-key').value.trim();
  const apiBaseUrl = document.getElementById('api-base-url').value.trim() || API_BASE;

  btn.classList.add('loading');
  btn.textContent = 'Testing...';

  try {
    const response = await fetch(`${apiBaseUrl}/health`, {
      headers: {
        'Accept': 'application/json',
        ...(apiKey ? { 'Authorization': `Bearer ${apiKey}` } : {})
      }
    });

    if (response.ok) {
      showStatus('Connection successful! API is healthy.', 'success');
    } else {
      showStatus(`Connection failed: HTTP ${response.status}`, 'error');
    }
  } catch (err) {
    showStatus(`Connection failed: ${err.message}`, 'error');
  } finally {
    btn.classList.remove('loading');
    btn.textContent = 'Test Connection';
  }
}

/**
 * Handle wallet save
 */
async function handleSaveWallet() {
  const walletAddress = document.getElementById('wallet-address-input').value.trim();

  if (!walletAddress) {
    showStatus('Please enter a wallet address', 'error');
    return;
  }

  // Basic validation
  const isValidAddress = /^(0x)?[a-zA-Z0-9]{40,44}$/.test(walletAddress);
  if (!isValidAddress) {
    showStatus('Invalid wallet address format', 'error');
    return;
  }

  try {
    await chrome.storage.sync.set({ walletAddress });

    document.getElementById('wallet-address').textContent = truncateAddress(walletAddress);
    showStatus('Wallet connected successfully!', 'success');
  } catch (err) {
    console.error('Error saving wallet:', err);
    showStatus('Failed to save wallet', 'error');
  }
}

/**
 * Save notification settings
 */
async function saveNotificationSettings() {
  try {
    await chrome.storage.sync.set({
      notifyUpload: document.getElementById('notify-upload').checked,
      notifyVote: document.getElementById('notify-vote').checked,
      notifyReward: document.getElementById('notify-reward').checked,
      notifyStatus: document.getElementById('notify-status').checked
    });
  } catch (err) {
    console.error('Error saving notification settings:', err);
  }
}

/**
 * Save advanced settings
 */
async function saveAdvancedSettings() {
  const cacheTtl = parseInt(document.getElementById('cache-ttl').value, 10);

  if (cacheTtl < 1 || cacheTtl > 60) {
    showStatus('Cache TTL must be between 1 and 60 minutes', 'error');
    document.getElementById('cache-ttl').value = 5;
    return;
  }

  try {
    await chrome.storage.sync.set({ cacheTtl });
  } catch (err) {
    console.error('Error saving advanced settings:', err);
  }
}

/**
 * Clear API cache
 */
async function clearCache() {
  try {
    await chrome.storage.local.clear();
    showStatus('Cache cleared successfully!', 'success');
  } catch (err) {
    console.error('Error clearing cache:', err);
    showStatus('Failed to clear cache', 'error');
  }
}

/**
 * Reset all settings to defaults
 */
async function resetSettings() {
  if (!confirm('Are you sure you want to reset all settings? This cannot be undone.')) {
    return;
  }

  try {
    await chrome.storage.sync.clear();
    await loadSettings();
    showStatus('All settings reset to defaults', 'success');
  } catch (err) {
    console.error('Error resetting settings:', err);
    showStatus('Failed to reset settings', 'error');
  }
}

/**
 * Show status message
 */
function showStatus(message, type = 'info') {
  const statusEl = document.getElementById('connection-status');
  statusEl.textContent = message;
  statusEl.className = `status-message ${type}`;
  statusEl.classList.remove('hidden');

  setTimeout(() => {
    statusEl.classList.add('hidden');
  }, 5000);
}

/**
 * Truncate address for display
 */
function truncateAddress(address) {
  if (!address || address.length < 10) return address;
  return `${address.slice(0, 6)}...${address.slice(-4)}`;
}
