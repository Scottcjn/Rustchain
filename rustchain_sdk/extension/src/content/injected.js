/**
 * RustChain Wallet - Injected Provider
 * 
 * Provides the window.rustchain API for dApps to interact with the wallet.
 * Follows EIP-1193 pattern for compatibility.
 */

(function() {
  // Provider class
  class RustChainProvider {
    constructor() {
      this.isRustChain = true;
      this.chainId = '0x1'; // Mainnet
      this.networkVersion = '1';
      this.selectedAddress = null;
      this._requestId = 0;
      this._pendingRequests = new Map();
      
      // Bind methods
      this.request = this.request.bind(this);
      this.enable = this.enable.bind(this);
      this.send = this.send.bind(this);
      this.sendAsync = this.sendAsync.bind(this);
      
      // Listen for responses
      window.addEventListener('message', this._handleResponse.bind(this));
    }
    
    /**
     * Send request to wallet
     * @param {Object} args 
     * @param {string} args.method 
     * @param {Array} args.params 
     * @returns {Promise<any>}
     */
    async request({ method, params = [] }) {
      const id = ++this._requestId;
      
      return new Promise((resolve, reject) => {
        this._pendingRequests.set(id, { resolve, reject });
        
        window.postMessage({
          type: 'RUSTCHAIN_REQUEST',
          payload: {
            type: 'RPC_REQUEST',
            method,
            params,
            origin: window.location.origin
          },
          id
        }, '*');
        
        // Timeout after 30 seconds
        setTimeout(() => {
          if (this._pendingRequests.has(id)) {
            this._pendingRequests.delete(id);
            reject(new Error('Request timeout'));
          }
        }, 30000);
      });
    }
    
    /**
     * Enable wallet access (legacy)
     * @returns {Promise<string[]>}
     */
    async enable() {
      const accounts = await this.request({ method: 'rustchain_requestAccounts' });
      return accounts;
    }
    
    /**
     * Send method (legacy)
     * @param {Object|string} payloadOrMethod 
     * @param {Function} callback 
     */
    send(payloadOrMethod, callback) {
      if (typeof payloadOrMethod === 'string') {
        // Legacy send(method, params)
        this.request({ method: payloadOrMethod, params: callback })
          .then(result => callback(null, { result }))
          .catch(error => callback(error, null));
      } else {
        // Send payload
        this.request(payloadOrMethod)
          .then(result => callback(null, { result }))
          .catch(error => callback(error, null));
      }
    }
    
    /**
     * Send async method (legacy)
     * @param {Object} payload 
     * @returns {Promise<Object>}
     */
    async sendAsync(payload) {
      const result = await this.request(payload);
      return { result };
    }
    
    /**
     * Handle response from content script
     * @param {MessageEvent} event 
     */
    _handleResponse(event) {
      if (event.source !== window) return;
      
      if (event.data.type === 'RUSTCHAIN_RESPONSE') {
        const { id, payload } = event.data;
        const request = this._pendingRequests.get(id);
        
        if (request) {
          this._pendingRequests.delete(id);
          
          if (payload.success) {
            request.resolve(payload.result);
          } else {
            request.reject(new Error(payload.error || 'Request failed'));
          }
        }
      }
      
      if (event.data.type === 'RUSTCHAIN_CONNECTED') {
        this.emit('connect', {});
      }
      
      if (event.data.type === 'RUSTCHAIN_ACCOUNT_CHANGED') {
        this.selectedAddress = event.data.payload.address;
        this.emit('accountsChanged', [event.data.payload.address]);
      }
    }
    
    /**
     * Event emitter (simplified)
     */
    _events = new Map();
    
    on(event, callback) {
      if (!this._events.has(event)) {
        this._events.set(event, []);
      }
      this._events.get(event).push(callback);
    }
    
    emit(event, data) {
      const callbacks = this._events.get(event) || [];
      callbacks.forEach(cb => cb(data));
    }
    
    removeListener(event, callback) {
      const callbacks = this._events.get(event) || [];
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }
  
  // Create provider instance
  const provider = new RustChainProvider();
  
  // Expose to window
  window.rustchain = provider;
  window.RustChainProvider = RustChainProvider;
  
  // Also expose as ethereum for compatibility
  window.ethereum = provider;
  
  console.log('[RustChain] Provider injected');
  
  // Dispatch event for dApps waiting for provider
  window.dispatchEvent(new Event('rustchain#initialized'));
  window.dispatchEvent(new Event('ethereum#initialized'));
})();
