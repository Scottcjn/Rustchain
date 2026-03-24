/**
 * BoTTube Chrome Extension - Background Service Worker
 * Handles API calls, notifications, and cross-tab communication
 */

const API_BASE = 'https://bottube.ai';
const API_ENDPOINTS = {
  health: '/health',
  videos: '/api/videos',
  feed: '/api/feed',
  upload: '/api/upload',
  vote: '/api/vote',
  balance: '/api/agents/me/balance',
  reputation: '/api/agents/me/reputation'
};

// Cache for API responses
const apiCache = new Map();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

/**
 * Message handler for communication with popup and content scripts
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  handleMessage(message, sender).then(sendResponse).catch(err => {
    console.error('Background message error:', err);
    sendResponse({ error: err.message });
  });
  
  // Return true to indicate async response
  return true;
});

/**
 * Handle incoming messages
 */
async function handleMessage(message, sender) {
  switch (message.action) {
    case 'getBalance':
      return getAgentBalance(message.apiKey);
    
    case 'fetchTrending':
      return fetchTrendingVideos(message.apiKey);
    
    case 'submitVote':
      return submitVote(message.videoId, message.rating, message.apiKey);
    
    case 'uploadVideo':
      return uploadVideo(message.videoData, message.apiKey);
    
    case 'getApiKey':
      return getStoredApiKey();
    
    case 'checkHealth':
      return checkAPIHealth();
    
    case 'notifyUpload':
      return showNotification('Upload Complete', message.title || 'Your video has been uploaded successfully');
    
    default:
      throw new Error(`Unknown action: ${message.action}`);
  }
}

/**
 * Get stored API key from chrome storage
 */
async function getStoredApiKey() {
  const result = await chrome.storage.sync.get(['apiKey']);
  return result.apiKey || null;
}

/**
 * Make authenticated API request
 */
async function apiRequest(endpoint, options = {}, apiKey = null) {
  const url = `${API_BASE}${endpoint}`;
  const cacheKey = `${endpoint}:${JSON.stringify(options)}`;
  
  // Check cache for GET requests
  if (options.method === 'GET' || !options.method) {
    const cached = apiCache.get(cacheKey);
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      return cached.data;
    }
  }
  
  const headers = {
    'Accept': 'application/json',
    'User-Agent': 'BoTTube-Chrome-Extension/1.0.0',
    ...options.headers
  };
  
  if (apiKey) {
    headers['Authorization'] = `Bearer ${apiKey}`;
  }
  
  const response = await fetch(url, {
    ...options,
    headers
  });
  
  if (!response.ok) {
    const errorText = await response.text().catch(() => 'Unknown error');
    throw new Error(`API Error ${response.status}: ${errorText}`);
  }
  
  // Handle empty responses
  const contentType = response.headers.get('content-type');
  const data = contentType && contentType.includes('application/json')
    ? await response.json()
    : await response.text();
  
  // Cache GET responses
  if (options.method === 'GET' || !options.method) {
    apiCache.set(cacheKey, { data, timestamp: Date.now() });
  }
  
  return data;
}

/**
 * Get agent balance
 */
async function getAgentBalance(apiKey) {
  try {
    const data = await apiRequest(API_ENDPOINTS.balance, {}, apiKey);
    return {
      balance: data.balance || 0,
      currency: data.currency || 'RTC'
    };
  } catch (err) {
    console.warn('Could not fetch balance:', err);
    return { balance: 0, currency: 'RTC', error: err.message };
  }
}

/**
 * Fetch trending videos
 */
async function fetchTrendingVideos(apiKey = null) {
  try {
    const data = await apiRequest(`${API_ENDPOINTS.videos}?limit=10&trending=true`, {}, apiKey);
    return { success: true, videos: data.videos || data };
  } catch (err) {
    console.error('Failed to fetch trending:', err);
    return { success: false, error: err.message };
  }
}

/**
 * Submit vote for a video
 */
async function submitVote(videoId, rating, apiKey) {
  if (!apiKey) {
    throw new Error('API key required for voting');
  }
  
  try {
    const data = await apiRequest(API_ENDPOINTS.vote, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        video_id: videoId,
        rating: rating, // 1-5 scale
        timestamp: new Date().toISOString()
      })
    }, apiKey);
    
    return { success: true, reward: data.reward || 0 };
  } catch (err) {
    console.error('Vote submission failed:', err);
    return { success: false, error: err.message };
  }
}

/**
 * Upload video metadata
 */
async function uploadVideo(videoData, apiKey) {
  if (!apiKey) {
    throw new Error('API key required for upload');
  }
  
  try {
    const formData = new FormData();
    formData.append('metadata', new Blob([JSON.stringify({
      title: videoData.title,
      description: videoData.description,
      source_url: videoData.sourceUrl,
      public: videoData.public !== false
    })], { type: 'application/json' }));
    
    const data = await apiRequest(API_ENDPOINTS.upload, {
      method: 'POST',
      body: formData
    }, apiKey);
    
    return { success: true, videoId: data.video_id || data.id };
  } catch (err) {
    console.error('Upload failed:', err);
    return { success: false, error: err.message };
  }
}

/**
 * Check API health
 */
async function checkAPIHealth() {
  try {
    const response = await fetch(`${API_BASE}${API_ENDPOINTS.health}`, {
      headers: { 'Accept': 'application/json' }
    });
    return {
      healthy: response.ok,
      status: response.status,
      timestamp: new Date().toISOString()
    };
  } catch (err) {
    return {
      healthy: false,
      error: err.message,
      timestamp: new Date().toISOString()
    };
  }
}

/**
 * Show browser notification
 */
async function showNotification(title, message, iconUrl = null) {
  try {
    await chrome.notifications.create({
      type: 'basic',
      iconUrl: iconUrl || chrome.runtime.getURL('icons/icon128.png'),
      title,
      message,
      priority: 0
    });
  } catch (err) {
    console.warn('Notification failed:', err);
  }
}

/**
 * Periodic health check (every 5 minutes)
 */
async function periodicHealthCheck() {
  const health = await checkAPIHealth();
  await chrome.storage.local.set({ lastHealthCheck: health });
  
  // Notify if API is down
  if (!health.healthy) {
    const lastNotified = await chrome.storage.local.get(['lastDownNotification']);
    const now = Date.now();
    
    if (!lastNotified.lastDownNotification || now - lastNotified.lastDownNotification > 15 * 60 * 1000) {
      await showNotification(
        'BoTTube API Unavailable',
        'The BoTTube API is currently unreachable. Some features may be limited.'
      );
      await chrome.storage.local.set({ lastDownNotification: now });
    }
  }
}

// Run health check on startup and periodically
periodicHealthCheck();
setInterval(periodicHealthCheck, 5 * 60 * 1000);

/**
 * Install handler - show welcome message on first install
 */
chrome.runtime.onInstalled.addListener(async (details) => {
  if (details.reason === 'install') {
    await showNotification(
      'Welcome to BoTTube!',
      'Start browsing, voting, and uploading AI videos to earn RTC tokens.'
    );
    
    // Open options page for first-time setup
    await chrome.tabs.create({
      url: chrome.runtime.getURL('options/options.html'),
      active: true
    });
  } else if (details.reason === 'update') {
    console.log('BoTTube extension updated to version', chrome.runtime.getManifest().version);
  }
});
