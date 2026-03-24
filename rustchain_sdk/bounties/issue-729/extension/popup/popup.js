/**
 * BoTTube Chrome Extension - Popup Script
 * Handles user interactions for browse, vote, and upload actions
 */

const API_BASE = 'https://bottube.ai';
const EXTENSION_VERSION = '1.0.0';

document.addEventListener('DOMContentLoaded', async () => {
  // Set version
  document.getElementById('extension-version').textContent = EXTENSION_VERSION;

  // Initialize wallet status
  await updateWalletStatus();

  // Navigation handlers
  document.getElementById('btn-browse').addEventListener('click', handleBrowse);
  document.getElementById('btn-vote').addEventListener('click', handleVote);
  document.getElementById('btn-upload').addEventListener('click', handleUpload);
  document.getElementById('btn-open-bottube').addEventListener('click', openBoTTube);
  document.getElementById('btn-settings').addEventListener('click', openSettings);
});

/**
 * Update wallet connection status and RTC balance
 */
async function updateWalletStatus() {
  const walletStatus = document.getElementById('wallet-status');
  const rtcBalance = document.getElementById('rtc-balance');

  try {
    // Get stored API key
    const result = await chrome.storage.sync.get(['apiKey', 'walletAddress']);
    
    if (result.apiKey) {
      walletStatus.textContent = 'Connected';
      walletStatus.className = 'connected';
      
      // Fetch balance if API key available
      try {
        const response = await chrome.runtime.sendMessage({
          action: 'getBalance',
          apiKey: result.apiKey
        });
        
        if (response && response.balance !== undefined) {
          rtcBalance.textContent = `${response.balance} RTC`;
        } else {
          rtcBalance.textContent = '0 RTC';
        }
      } catch (err) {
        rtcBalance.textContent = '--';
        console.warn('Could not fetch balance:', err);
      }
    } else {
      walletStatus.textContent = 'Not connected';
      walletStatus.className = 'disconnected';
      rtcBalance.textContent = '--';
    }
  } catch (err) {
    console.error('Error updating wallet status:', err);
    walletStatus.textContent = 'Error';
    walletStatus.className = 'disconnected';
    rtcBalance.textContent = '--';
  }
}

/**
 * Handle Browse action - Open BoTTube video browser
 */
async function handleBrowse(e) {
  e.preventDefault();
  showToast('Opening video browser...');
  
  try {
    // Create new tab with BoTTube browse page
    await chrome.tabs.create({
      url: `${API_BASE}/browse`,
      active: true
    });
    
    // Also notify background to fetch trending videos
    await chrome.runtime.sendMessage({ action: 'fetchTrending' });
  } catch (err) {
    showToast('Failed to open browser', 'error');
    console.error('Browse error:', err);
  }
}

/**
 * Handle Vote action - Show voting interface
 */
async function handleVote(e) {
  e.preventDefault();
  
  try {
    // Get current active tab
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    if (tab.url.includes('youtube.com') || tab.url.includes('bottube.ai')) {
      // Send message to content script to show voting UI
      await chrome.tabs.sendMessage(tab.id, { action: 'showVotingUI' });
      showToast('Voting interface activated');
    } else {
      // Open BoTTube voting page
      await chrome.tabs.create({
        url: `${API_BASE}/vote`,
        active: true
      });
      showToast('Opening voting page...');
    }
  } catch (err) {
    // Fallback: open voting page
    await chrome.tabs.create({
      url: `${API_BASE}/vote`,
      active: true
    });
    showToast('Opening voting page...');
  }
}

/**
 * Handle Upload action - Show upload interface
 */
async function handleUpload(e) {
  e.preventDefault();
  
  try {
    // Get current active tab to check if on YouTube
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    if (tab.url.includes('youtube.com')) {
      // Show upload modal for current YouTube video
      await chrome.tabs.sendMessage(tab.id, { 
        action: 'showUploadModal',
        videoUrl: tab.url 
      });
      showToast('Upload interface activated');
    } else {
      // Open BoTTube upload page
      await chrome.tabs.create({
        url: `${API_BASE}/upload`,
        active: true
      });
      showToast('Opening upload page...');
    }
  } catch (err) {
    // Fallback: open upload page
    await chrome.tabs.create({
      url: `${API_BASE}/upload`,
      active: true
    });
    showToast('Opening upload page...');
  }
}

/**
 * Open BoTTube.ai main site
 */
async function openBoTTube() {
  await chrome.tabs.create({
    url: API_BASE,
    active: true
  });
}

/**
 * Open extension settings/options page
 */
async function openSettings() {
  await chrome.tabs.create({
    url: chrome.runtime.getURL('options/options.html'),
    active: true
  });
}

/**
 * Show toast notification
 */
function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  
  setTimeout(() => {
    toast.remove();
  }, 3000);
}
