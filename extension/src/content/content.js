/**
 * RustChain Wallet - Content Script
 * 
 * Injects the RustChain provider into web pages for dApp integration.
 * Handles communication between dApps and the wallet extension.
 */

// Inject the provider script
function injectProvider() {
  const container = document.head || document.documentElement;
  const script = document.createElement('script');
  script.src = chrome.runtime.getURL('src/content/injected.js');
  script.onload = () => script.remove();
  container.appendChild(script);
}

// Handle messages from injected script
window.addEventListener('message', (event) => {
  if (event.source !== window) return;
  if (event.data.type !== 'RUSTCHAIN_REQUEST') return;
  
  // Forward request to background
  chrome.runtime.sendMessage(event.data.payload, (response) => {
    window.postMessage({
      type: 'RUSTCHAIN_RESPONSE',
      payload: response,
      id: event.data.id
    }, '*');
  });
});

// Check connection status
chrome.runtime.sendMessage({ type: 'IS_CONNECTED', payload: { origin: window.location.origin } }, (response) => {
  if (response?.success && response.connected) {
    notifyConnection();
  }
});

// Notify page of connection
function notifyConnection() {
  window.postMessage({
    type: 'RUSTCHAIN_CONNECTED',
    payload: { origin: window.location.origin }
  }, '*');
}

// Inject on load
injectProvider();

console.log('[RustChain] Content script loaded');
