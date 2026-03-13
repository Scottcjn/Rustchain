// Popup script for RTC Balance Viewer extension

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const balanceEl = document.getElementById('balance');
  const walletIdEl = document.getElementById('wallet-id');
  const endpointEl = document.getElementById('endpoint');
  const lastUpdatedEl = document.getElementById('last-updated');
  const statusEl = document.getElementById('status');
  const refreshBtn = document.getElementById('refresh-btn');
  const settingsBtn = document.getElementById('settings-btn');
  
  // Modal elements
  const settingsModal = document.getElementById('settings-modal');
  const closeModalBtn = document.getElementById('close-modal');
  const walletIdInput = document.getElementById('wallet-id-input');
  const endpointInput = document.getElementById('endpoint-input');
  const refreshIntervalInput = document.getElementById('refresh-interval');
  const saveSettingsBtn = document.getElementById('save-settings');
  const cancelSettingsBtn = document.getElementById('cancel-settings');
  
  // Load saved settings and display balance
  loadSettings();
  fetchBalance();
  
  // Event listeners
  refreshBtn.addEventListener('click', () => fetchBalance());
  settingsBtn.addEventListener('click', openSettings);
  closeModalBtn.addEventListener('click', closeSettings);
  saveSettingsBtn.addEventListener('click', saveSettings);
  cancelSettingsBtn.addEventListener('click', closeSettings);
  
  // Close modal on outside click
  settingsModal.addEventListener('click', (e) => {
    if (e.target === settingsModal) {
      closeSettings();
    }
  });
  
  // Load settings from storage
  async function loadSettings() {
    try {
      const result = await chrome.storage.local.get(['walletId', 'endpoint', 'refreshInterval']);
      
      if (result.walletId) {
        walletIdEl.textContent = truncateId(result.walletId);
        walletIdInput.value = result.walletId;
      }
      
      if (result.endpoint) {
        endpointEl.textContent = truncateUrl(result.endpoint);
        endpointInput.value = result.endpoint;
      }
      
      if (result.refreshInterval) {
        refreshIntervalInput.value = result.refreshInterval;
      }
      
      if (!result.walletId || !result.endpoint) {
        showStatus('Please configure wallet ID and endpoint in settings', 'loading');
      }
    } catch (error) {
      console.error('Error loading settings:', error);
      showStatus('Error loading settings', 'error');
    }
  }
  
  // Fetch balance from API
  async function fetchBalance() {
    try {
      const result = await chrome.storage.local.get(['walletId', 'endpoint']);
      
      if (!result.walletId || !result.endpoint) {
        showStatus('Please configure wallet ID and endpoint', 'loading');
        balanceEl.textContent = '--';
        return;
      }
      
      // Show loading state
      balanceEl.classList.add('loading');
      balanceEl.textContent = 'Loading...';
      refreshBtn.disabled = true;
      showStatus('Fetching balance...', 'loading');
      
      // Send message to background script
      const response = await chrome.runtime.sendMessage({
        action: 'fetchBalance',
        endpoint: result.endpoint,
        walletId: result.walletId
      });
      
      balanceEl.classList.remove('loading');
      
      if (response.success) {
        balanceEl.textContent = formatBalance(response.balance);
        balanceEl.classList.remove('error');
        lastUpdatedEl.textContent = formatTimestamp(new Date());
        showStatus('Balance updated successfully', 'success');
        
        // Update last fetch time
        await chrome.storage.local.set({ lastFetch: Date.now() });
      } else {
        balanceEl.textContent = 'Error';
        balanceEl.classList.add('error');
        showStatus(response.error || 'Failed to fetch balance', 'error');
      }
    } catch (error) {
      console.error('Error fetching balance:', error);
      balanceEl.classList.remove('loading');
      balanceEl.textContent = 'Error';
      balanceEl.classList.add('error');
      showStatus('Network error. Check endpoint configuration.', 'error');
    } finally {
      refreshBtn.disabled = false;
    }
  }
  
  // Open settings modal
  function openSettings() {
    settingsModal.classList.add('active');
  }
  
  // Close settings modal
  function closeSettings() {
    settingsModal.classList.remove('active');
  }
  
  // Save settings
  async function saveSettings() {
    const walletId = walletIdInput.value.trim();
    const endpoint = endpointInput.value.trim();
    const refreshInterval = parseInt(refreshIntervalInput.value, 10) || 5;
    
    if (!walletId) {
      alert('Please enter a wallet/miner ID');
      return;
    }
    
    if (!endpoint) {
      alert('Please enter an API endpoint');
      return;
    }
    
    try {
      await chrome.storage.local.set({
        walletId,
        endpoint,
        refreshInterval: Math.min(Math.max(refreshInterval, 1), 60)
      });
      
      // Update display
      walletIdEl.textContent = truncateId(walletId);
      endpointEl.textContent = truncateUrl(endpoint);
      
      closeSettings();
      showStatus('Settings saved', 'success');
      
      // Fetch balance with new settings
      fetchBalance();
      
      // Notify background script to update alarm
      chrome.runtime.sendMessage({ action: 'updateAlarm', interval: Math.min(Math.max(refreshInterval, 1), 60) });
    } catch (error) {
      console.error('Error saving settings:', error);
      showStatus('Error saving settings', 'error');
    }
  }
  
  // Show status message
  function showStatus(message, type) {
    statusEl.textContent = message;
    statusEl.className = 'status-message ' + type;
    
    // Auto-hide success messages after 3 seconds
    if (type === 'success') {
      setTimeout(() => {
        statusEl.className = 'status-message';
      }, 3000);
    }
  }
  
  // Utility functions
  function truncateId(id, length = 12) {
    if (!id || id.length <= length) return id;
    return id.substring(0, length) + '...';
  }
  
  function truncateUrl(url, length = 25) {
    if (!url || url.length <= length) return url;
    try {
      const urlObj = new URL(url);
      return urlObj.hostname + (urlObj.pathname.length > 1 ? urlObj.pathname.substring(0, 15) : '');
    } catch {
      return url.substring(0, length) + '...';
    }
  }
  
  function formatBalance(balance) {
    if (typeof balance === 'number') {
      return balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 });
    }
    return balance;
  }
  
  function formatTimestamp(date) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
});
