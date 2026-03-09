/**
 * BoTTube Chrome Extension - YouTube Integration Content Script
 * Adds BoTTube functionality directly to YouTube pages
 */

(function() {
  'use strict';

  // Prevent multiple injections
  if (window.__BoTTubeInjected) return;
  window.__BoTTubeInjected = true;

  const API_BASE = 'https://bottube.ai';
  let apiKey = null;

  /**
   * Initialize the content script
   */
  async function init() {
    // Get API key from background
    try {
      const response = await chrome.runtime.sendMessage({ action: 'getApiKey' });
      apiKey = response;
    } catch (err) {
      console.warn('Could not get API key:', err);
    }

    // Wait for YouTube to load
    waitForElement('ytd-video-owner-renderer', addBoTTubeButtons);
    
    // Listen for messages from popup/background
    chrome.runtime.onMessage.addListener(handleMessage);
  }

  /**
   * Handle messages from extension
   */
  function handleMessage(message, sender, sendResponse) {
    switch (message.action) {
      case 'showVotingUI':
        showVotingUI();
        sendResponse({ success: true });
        break;
      
      case 'showUploadModal':
        showUploadModal(message.videoUrl);
        sendResponse({ success: true });
        break;
      
      default:
        sendResponse({ error: 'Unknown action' });
    }
    return true;
  }

  /**
   * Wait for an element to appear in the DOM
   */
  function waitForElement(selector, callback) {
    const element = document.querySelector(selector);
    if (element) {
      callback(element);
      return;
    }

    const observer = new MutationObserver(() => {
      const el = document.querySelector(selector);
      if (el) {
        observer.disconnect();
        callback(el);
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  }

  /**
   * Add BoTTube action buttons to YouTube video page
   */
  function addBoTTubeButtons(ownerRenderer) {
    const actionsContainer = document.querySelector('#menu-container');
    if (!actionsContainer || document.querySelector('.bottube-actions')) return;

    const bottubeActions = document.createElement('div');
    bottubeActions.className = 'bottube-actions';
    bottubeActions.innerHTML = `
      <button class="bottube-btn bottube-vote-btn" title="Vote on BoTTube">
        <span class="bottube-icon">👍</span>
        <span class="bottube-label">Vote</span>
      </button>
      <button class="bottube-btn bottube-upload-btn" title="Upload to BoTTube">
        <span class="bottube-icon">📤</span>
        <span class="bottube-label">Upload</span>
      </button>
      <button class="bottube-btn bottube-reward-btn" title="Check rewards">
        <span class="bottube-icon">🦀</span>
        <span class="bottube-label">Rewards</span>
      </button>
    `;

    // Insert after existing action buttons
    const existingActions = actionsContainer.querySelector('#top-level-buttons');
    if (existingActions) {
      existingActions.appendChild(bottubeActions);
    }

    // Add event listeners
    bottubeActions.querySelector('.bottube-vote-btn').addEventListener('click', handleVoteClick);
    bottubeActions.querySelector('.bottube-upload-btn').addEventListener('click', handleUploadClick);
    bottubeActions.querySelector('.bottube-reward-btn').addEventListener('click', handleRewardsClick);
  }

  /**
   * Get current video information from YouTube
   */
  function getCurrentVideoInfo() {
    const videoElement = document.querySelector('video');
    const titleElement = document.querySelector('h1.ytd-video-primary-info-renderer');
    const url = window.location.href;
    
    // Extract video ID from URL
    const urlParams = new URLSearchParams(window.location.search);
    const videoId = urlParams.get('v') || '';

    return {
      videoId,
      title: titleElement?.textContent?.trim() || document.title,
      url,
      duration: videoElement?.duration || 0,
      timestamp: videoElement?.currentTime || 0
    };
  }

  /**
   * Show voting UI
   */
  function showVotingUI() {
    const videoInfo = getCurrentVideoInfo();
    
    const modal = createModal(`
      <h2>Vote on BoTTube</h2>
      <p>Rate this video to earn RTC tokens</p>
      <div class="bottube-rating">
        <button data-rating="1">★</button>
        <button data-rating="2">★</button>
        <button data-rating="3">★</button>
        <button data-rating="4">★</button>
        <button data-rating="5">★</button>
      </div>
      <div class="bottube-modal-actions">
        <button class="bottube-cancel">Cancel</button>
      </div>
    `);

    document.body.appendChild(modal);

    // Handle rating selection
    modal.querySelectorAll('.bottube-rating button').forEach(btn => {
      btn.addEventListener('click', async () => {
        const rating = parseInt(btn.dataset.rating);
        await submitVote(videoInfo.videoId, rating);
        closeModal(modal);
      });
    });

    modal.querySelector('.bottube-cancel').addEventListener('click', () => closeModal(modal));
  }

  /**
   * Handle vote button click
   */
  async function handleVoteClick() {
    showVotingUI();
  }

  /**
   * Submit vote to BoTTube API
   */
  async function submitVote(youtubeVideoId, rating) {
    if (!apiKey) {
      showToast('Please configure your API key in settings first', 'error');
      return;
    }

    try {
      const response = await chrome.runtime.sendMessage({
        action: 'submitVote',
        videoId: youtubeVideoId,
        rating,
        apiKey
      });

      if (response.success) {
        showToast(`Vote submitted! Earned ${response.reward || 1} RTC`, 'success');
      } else {
        showToast(response.error || 'Vote failed', 'error');
      }
    } catch (err) {
      showToast('Vote submission failed', 'error');
      console.error('Vote error:', err);
    }
  }

  /**
   * Show upload modal
   */
  function showUploadModal(sourceUrl) {
    const videoInfo = getCurrentVideoInfo();
    
    const modal = createModal(`
      <h2>Upload to BoTTube</h2>
      <p>Share this video on BoTTube and earn RTC tokens</p>
      <form class="bottube-upload-form">
        <div class="bottube-form-group">
          <label>Title</label>
          <input type="text" name="title" value="${escapeHtml(videoInfo.title)}" required>
        </div>
        <div class="bottube-form-group">
          <label>Description</label>
          <textarea name="description" rows="4" placeholder="Describe this video..."></textarea>
        </div>
        <div class="bottube-form-group">
          <label>
            <input type="checkbox" name="public" checked>
            Make public
          </label>
        </div>
        <div class="bottube-modal-actions">
          <button type="submit" class="bottube-submit">Upload</button>
          <button type="button" class="bottube-cancel">Cancel</button>
        </div>
      </form>
    `);

    document.body.appendChild(modal);

    // Handle form submission
    modal.querySelector('.bottube-upload-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const formData = new FormData(e.target);
      
      const videoData = {
        title: formData.get('title'),
        description: formData.get('description') || '',
        sourceUrl: sourceUrl || videoInfo.url,
        public: formData.get('public') === 'on'
      };

      await uploadVideo(videoData);
      closeModal(modal);
    });

    modal.querySelector('.bottube-cancel').addEventListener('click', () => closeModal(modal));
  }

  /**
   * Handle upload button click
   */
  function handleUploadClick() {
    const videoInfo = getCurrentVideoInfo();
    showUploadModal(videoInfo.url);
  }

  /**
   * Upload video to BoTTube
   */
  async function uploadVideo(videoData) {
    if (!apiKey) {
      showToast('Please configure your API key in settings first', 'error');
      return;
    }

    try {
      const response = await chrome.runtime.sendMessage({
        action: 'uploadVideo',
        videoData,
        apiKey
      });

      if (response.success) {
        showToast('Video uploaded successfully!', 'success');
        
        // Notify background to show notification
        await chrome.runtime.sendMessage({
          action: 'notifyUpload',
          title: videoData.title
        });
      } else {
        showToast(response.error || 'Upload failed', 'error');
      }
    } catch (err) {
      showToast('Upload failed', 'error');
      console.error('Upload error:', err);
    }
  }

  /**
   * Handle rewards button click
   */
  async function handleRewardsClick() {
    if (!apiKey) {
      showToast('Please configure your API key in settings', 'error');
      return;
    }

    try {
      const response = await chrome.runtime.sendMessage({
        action: 'getBalance',
        apiKey
      });

      if (response.balance !== undefined) {
        showToast(`Balance: ${response.balance} ${response.currency || 'RTC'}`, 'success');
      }
    } catch (err) {
      showToast('Could not fetch balance', 'error');
    }
  }

  /**
   * Create modal dialog
   */
  function createModal(content) {
    const modal = document.createElement('div');
    modal.className = 'bottube-modal-overlay';
    modal.innerHTML = `
      <div class="bottube-modal">
        ${content}
      </div>
    `;
    return modal;
  }

  /**
   * Close modal
   */
  function closeModal(modal) {
    modal.style.opacity = '0';
    setTimeout(() => modal.remove(), 200);
  }

  /**
   * Show toast notification
   */
  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `bottube-toast bottube-toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  /**
   * Escape HTML to prevent XSS
   */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
