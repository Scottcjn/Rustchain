// Background service worker for RTC Balance Viewer extension

// Initialize alarm on extension install
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    // Set default refresh interval
    chrome.storage.local.set({ refreshInterval: 5 });
  }
  
  // Setup alarm for auto-refresh
  setupAlarm();
});

// Setup alarm for periodic balance refresh
async function setupAlarm() {
  try {
    const result = await chrome.storage.local.get(['refreshInterval']);
    const interval = result.refreshInterval || 5;
    
    // Clear existing alarm
    await chrome.alarms.clear('balanceRefresh');
    
    // Create new alarm (minimum interval is 1 minute for non-Chrome extensions in development)
    chrome.alarms.create('balanceRefresh', {
      periodInMinutes: Math.max(interval, 1)
    });
  } catch (error) {
    console.error('Error setting up alarm:', error);
  }
}

// Handle alarm events
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'balanceRefresh') {
    // Could trigger a notification here if balance changed significantly
    console.log('Auto-refresh triggered');
  }
});

// Handle messages from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'fetchBalance') {
    fetchBalance(message.endpoint, message.walletId)
      .then((result) => sendResponse(result))
      .catch((error) => sendResponse({ success: false, error: error.message }));
    
    // Return true to indicate async response
    return true;
  }
  
  if (message.action === 'updateAlarm') {
    setupAlarm();
    sendResponse({ success: true });
    return true;
  }
});

// Fetch balance from API endpoint
async function fetchBalance(endpoint, walletId) {
  try {
    // Validate endpoint URL
    if (!endpoint || !walletId) {
      return { success: false, error: 'Missing endpoint or wallet ID' };
    }
    
    // Construct the API URL with wallet ID
    // Common patterns: /balance/{walletId}, /balance?address={walletId}, etc.
    let url = endpoint;
    
    if (!endpoint.includes(walletId)) {
      // Try to append wallet ID to URL
      if (endpoint.endsWith('/')) {
        url = endpoint + walletId;
      } else if (endpoint.includes('?')) {
        url = endpoint + '&address=' + walletId;
      } else {
        url = endpoint + '?address=' + walletId;
      }
    }
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json'
      }
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    
    // Try to extract balance from various response formats
    let balance = extractBalance(data);
    
    if (balance === null) {
      return { success: false, error: 'Could not parse balance from response' };
    }
    
    return { success: true, balance: balance };
  } catch (error) {
    console.error('Error fetching balance:', error);
    return { success: false, error: error.message };
  }
}

// Extract balance from various API response formats
function extractBalance(data) {
  if (typeof data === 'number') {
    return data;
  }
  
  if (typeof data === 'string') {
    const parsed = parseFloat(data);
    return isNaN(parsed) ? null : parsed;
  }
  
  if (typeof data === 'object' && data !== null) {
    // Common balance field names
    const balanceFields = ['balance', 'available', 'amount', 'value', 'data', 'result'];
    
    for (const field of balanceFields) {
      if (data[field] !== undefined) {
        if (typeof data[field] === 'number') {
          return data[field];
        }
        if (typeof data[field] === 'string') {
          const parsed = parseFloat(data[field]);
          if (!isNaN(parsed)) {
            return parsed;
          }
        }
        // Handle nested objects
        if (typeof data[field] === 'object' && data[field] !== null) {
          const nestedBalance = extractBalance(data[field]);
          if (nestedBalance !== null) {
            return nestedBalance;
          }
        }
      }
    }
    
    // Try to find any numeric value in the object
    for (const key in data) {
      if (typeof data[key] === 'number') {
        return data[key];
      }
    }
  }
  
  return null;
}

// Setup alarm when extension starts
setupAlarm();
