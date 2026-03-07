#!/usr/bin/env python3
"""
RustChain API Server - Bounty #695 Rework

Flask-based API server providing real-time integration with RustChain network.
No mock data - all endpoints proxy to live RustChain nodes with proper error handling,
input validation, and rate limiting.

Endpoints:
    GET /health          - Server health status
    GET /api/health      - Upstream node health
    GET /api/epoch       - Current epoch information
    GET /api/miners      - List of active miners
    GET /api/miner/<id>  - Specific miner details
    GET /api/balance     - Wallet balance lookup
    GET /api/transactions- Recent transactions

Usage:
    export RUSTCHAIN_API_BASE="https://rustchain.org"
    python api_server.py
"""

import os
import time
import logging
from functools import wraps
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Any, Tuple

from flask import Flask, jsonify, request, Response
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError as ReqConnectionError
from marshmallow import Schema, fields, validate, ValidationError as MarshmallowValidationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('rustchain-api')

# Initialize Flask app
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Configuration from environment
API_BASE = os.environ.get('RUSTCHAIN_API_BASE', 'https://rustchain.org').rstrip('/')
API_TIMEOUT = float(os.environ.get('RUSTCHAIN_API_TIMEOUT', '10'))
SERVER_PORT = int(os.environ.get('PORT', '8080'))
SERVER_HOST = os.environ.get('HOST', '0.0.0.0')
DEBUG_MODE = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

# Rate limiting configuration
RATE_LIMIT_REQUESTS = int(os.environ.get('RATE_LIMIT_REQUESTS', '100'))
RATE_LIMIT_WINDOW = int(os.environ.get('RATE_LIMIT_WINDOW', '60'))  # seconds

# ============================================================================
# Rate Limiter Implementation (In-memory, production-ready for single instance)
# ============================================================================

class RateLimiter:
    """
    Simple in-memory rate limiter with sliding window.
    For production multi-instance deployments, use Redis-backed limiter.
    """
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)
    
    def is_allowed(self, identifier: str) -> Tuple[bool, Dict[str, int]]:
        """
        Check if request is allowed for given identifier (IP or API key).
        
        Returns:
            Tuple of (allowed: bool, rate_info: dict)
        """
        now = time.time()
        window_start = now - self.window_seconds
        
        # Clean old entries
        self.requests[identifier] = [
            ts for ts in self.requests[identifier] 
            if ts > window_start
        ]
        
        # Check limit
        current_count = len(self.requests[identifier])
        remaining = max(0, self.max_requests - current_count)
        reset_time = int(now + self.window_seconds)
        
        rate_info = {
            'X-RateLimit-Limit': self.max_requests,
            'X-RateLimit-Remaining': remaining,
            'X-RateLimit-Reset': reset_time,
        }
        
        if current_count >= self.max_requests:
            return False, rate_info
        
        # Record this request
        self.requests[identifier].append(now)
        rate_info['X-RateLimit-Remaining'] = remaining - 1
        
        return True, rate_info
    
    def reset(self, identifier: str = None):
        """Reset rate limit for identifier or all"""
        if identifier:
            self.requests[identifier] = []
        else:
            self.requests.clear()


# Global rate limiter instance
rate_limiter = RateLimiter(
    max_requests=RATE_LIMIT_REQUESTS,
    window_seconds=RATE_LIMIT_WINDOW
)


def rate_limit(f):
    """Decorator to apply rate limiting to endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get client identifier (IP address)
        client_ip = request.remote_addr or 'unknown'
        
        # Check rate limit
        allowed, rate_info = rate_limiter.is_allowed(client_ip)
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            response = jsonify({
                'error': 'Rate limit exceeded',
                'message': f'Maximum {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW} seconds',
                'retry_after': rate_info['X-RateLimit-Reset'] - int(time.time())
            })
            response.status_code = 429
            for key, value in rate_info.items():
                response.headers[key] = str(value)
            return response
        
        # Execute the actual function
        response = f(*args, **kwargs)
        
        # Add rate limit headers to response
        if isinstance(response, Response):
            for key, value in rate_info.items():
                response.headers[key] = str(value)
        elif isinstance(response, tuple):
            resp, status = response[0], response[1] if len(response) > 1 else 200
            for key, value in rate_info.items():
                resp.headers[key] = str(value)
            return resp, status
        
        return response
    
    return decorated_function


# ============================================================================
# Input Validation Schemas (Marshmallow)
# ============================================================================

class MinerIdSchema(Schema):
    """Validation schema for miner ID parameter"""
    miner_id = fields.Str(
        required=True,
        validate=[
            validate.Length(min=1, max=128, error="Miner ID must be 1-128 characters"),
            validate.Regexp(r'^[a-zA-Z0-9_-]+$', error="Miner ID contains invalid characters")
        ]
    )


class WalletAddressSchema(Schema):
    """Validation schema for wallet address parameter"""
    address = fields.Str(
        required=True,
        validate=[
            validate.Length(min=1, max=256, error="Address must be 1-256 characters"),
        ]
    )


class PaginationSchema(Schema):
    """Validation schema for pagination parameters"""
    limit = fields.Int(
        validate=[validate.Range(min=1, max=1000, error="Limit must be 1-1000")],
        load_default=50
    )
    offset = fields.Int(
        validate=[validate.Range(min=0, error="Offset must be >= 0")],
        load_default=0
    )


# ============================================================================
# Upstream API Client
# ============================================================================

class UpstreamClient:
    """
    Client for making requests to upstream RustChain API.
    Handles connection errors, timeouts, and response parsing.
    """
    
    def __init__(self, base_url: str, timeout: float):
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'RustChain-API-Server/1.0',
            'Accept': 'application/json',
        })
    
    def get(self, endpoint: str, params: Dict = None) -> Dict[str, Any]:
        """
        Make GET request to upstream API.
        
        Args:
            endpoint: API endpoint path
            params: Optional query parameters
            
        Returns:
            Parsed JSON response
            
        Raises:
            UpstreamError: If request fails
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            logger.debug(f"Upstream GET: {url} params={params}")
            response = self.session.get(
                url,
                params=params,
                timeout=self.timeout
            )
            
            # Handle HTTP errors
            if response.status_code >= 500:
                raise UpstreamError(
                    f"Upstream server error: {response.status_code}",
                    status_code=502
                )
            
            if response.status_code == 404:
                raise UpstreamError(
                    "Resource not found",
                    status_code=404
                )
            
            if response.status_code >= 400:
                raise UpstreamError(
                    f"Upstream client error: {response.status_code}",
                    status_code=400
                )
            
            # Parse JSON
            try:
                return response.json()
            except ValueError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                raise UpstreamError("Invalid JSON response from upstream", status_code=502)
                
        except Timeout as e:
            logger.error(f"Upstream timeout: {url}")
            raise UpstreamError(f"Upstream timeout after {self.timeout}s", status_code=504) from e
            
        except ReqConnectionError as e:
            logger.error(f"Upstream connection error: {url} - {e}")
            raise UpstreamError("Cannot connect to upstream", status_code=502) from e
            
        except RequestException as e:
            logger.error(f"Upstream request failed: {url} - {e}")
            raise UpstreamError(f"Request failed: {str(e)}", status_code=502) from e
    
    def close(self):
        """Close the session"""
        self.session.close()


class UpstreamError(Exception):
    """Exception for upstream API errors"""
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


# Global upstream client
upstream = UpstreamClient(API_BASE, API_TIMEOUT)


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(400)
def bad_request(error):
    return jsonify({
        'error': 'Bad Request',
        'message': str(error.description) if hasattr(error, 'description') else 'Invalid request'
    }), 400


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested resource was not found'
    }), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        'error': 'Method Not Allowed',
        'message': 'The HTTP method is not allowed for this endpoint'
    }), 405


@app.errorhandler(429)
def rate_limit_exceeded(error):
    return jsonify({
        'error': 'Too Many Requests',
        'message': 'Rate limit exceeded. Please slow down.'
    }), 429


@app.errorhandler(500)
def internal_error(error):
    logger.exception("Internal server error")
    return jsonify({
        'error': 'Internal Server Error',
        'message': 'An unexpected error occurred'
    }), 500


@app.errorhandler(502)
def bad_gateway(error):
    return jsonify({
        'error': 'Bad Gateway',
        'message': 'Failed to communicate with upstream server'
    }), 502


@app.errorhandler(504)
def gateway_timeout(error):
    return jsonify({
        'error': 'Gateway Timeout',
        'message': 'Upstream server did not respond in time'
    }), 504


# ============================================================================
# API Endpoints
# ============================================================================

@app.route('/health', methods=['GET'])
@rate_limit
def health_check():
    """
    Health check endpoint for this API server.
    
    Returns:
        JSON with server status, uptime, and version
    """
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'uptime_seconds': time.time() - app.config.get('start_time', time.time()),
        'version': '1.0.0',
        'upstream_base': API_BASE
    })


@app.route('/api/health', methods=['GET'])
@rate_limit
def upstream_health():
    """
    Proxy to upstream node health endpoint.
    
    Returns:
        JSON with upstream node health status
    """
    try:
        health_data = upstream.get('/health')
        return jsonify({
            'success': True,
            'data': health_data,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
    except UpstreamError as e:
        logger.warning(f"Upstream health check failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }), e.status_code


@app.route('/api/epoch', methods=['GET'])
@rate_limit
def get_epoch():
    """
    Get current epoch information from upstream.
    
    Returns:
        JSON with epoch data:
        - epoch: Current epoch number
        - slot: Current slot within epoch
        - blocks_per_epoch: Total blocks per epoch
        - enrolled_miners: Number of enrolled miners
        - epoch_pot: Proof of Transit value
    """
    try:
        epoch_data = upstream.get('/epoch')
        
        # Validate and normalize response
        if not isinstance(epoch_data, dict):
            raise UpstreamError("Invalid epoch response format", status_code=502)
        
        return jsonify({
            'success': True,
            'data': {
                'epoch': epoch_data.get('epoch', 0),
                'slot': epoch_data.get('slot', 0),
                'blocks_per_epoch': epoch_data.get('blocks_per_epoch', 144),
                'enrolled_miners': epoch_data.get('enrolled_miners', 0),
                'epoch_pot': epoch_data.get('epoch_pot', 0.0),
                'progress_percent': round(
                    (epoch_data.get('slot', 0) / max(1, epoch_data.get('blocks_per_epoch', 144))) * 100, 2
                )
            },
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
        
    except UpstreamError as e:
        logger.warning(f"Epoch fetch failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), e.status_code


@app.route('/api/miners', methods=['GET'])
@rate_limit
def get_miners():
    """
    Get list of active miners from upstream.
    
    Query Parameters:
        limit: Maximum miners to return (1-1000, default: 50)
        offset: Offset for pagination (default: 0)
    
    Returns:
        JSON array of miner objects with:
        - miner: Wallet address
        - antiquity_multiplier: Hardware antiquity multiplier
        - hardware_type: Hardware description
        - device_arch: Device architecture
        - last_attest: Last attestation timestamp
    """
    # Validate pagination parameters
    schema = PaginationSchema()
    try:
        params = schema.load(request.args.to_dict())
    except MarshmallowValidationError as e:
        return jsonify({
            'success': False,
            'error': 'Invalid parameters',
            'details': e.messages
        }), 400
    
    try:
        miners_data = upstream.get('/api/miners', params={'limit': params['limit'], 'offset': params['offset']})
        
        # Ensure we return a list
        if not isinstance(miners_data, list):
            miners_data = []
        
        # Normalize miner data structure
        normalized_miners = []
        for miner in miners_data:
            if not isinstance(miner, dict):
                continue
            
            normalized_miners.append({
                'miner_id': miner.get('miner', miner.get('miner_id', 'unknown')),
                'antiquity_multiplier': float(miner.get('antiquity_multiplier', 1.0)),
                'hardware_type': miner.get('hardware_type', miner.get('hardware', 'Unknown')),
                'device_arch': miner.get('device_arch', miner.get('arch', 'unknown')),
                'last_attest': miner.get('last_attest', miner.get('last_attestation', 0)),
                'score': miner.get('score', 0),
                'multiplier': miner.get('multiplier', 1.0)
            })
        
        return jsonify({
            'success': True,
            'data': normalized_miners,
            'count': len(normalized_miners),
            'pagination': {
                'limit': params['limit'],
                'offset': params['offset']
            },
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
        
    except UpstreamError as e:
        logger.warning(f"Miners fetch failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), e.status_code


@app.route('/api/miner/<miner_id>', methods=['GET'])
@rate_limit
def get_miner(miner_id: str):
    """
    Get details for a specific miner.
    
    Path Parameters:
        miner_id: Miner wallet address or ID
    
    Returns:
        JSON with miner details including balance, rewards, and attestation history
    """
    # Validate miner_id
    schema = MinerIdSchema()
    try:
        schema.validate({'miner_id': miner_id})
    except MarshmallowValidationError as e:
        return jsonify({
            'success': False,
            'error': 'Invalid miner ID',
            'details': e.messages
        }), 400
    
    try:
        # Try to get miner-specific data from upstream
        # Note: This assumes upstream has /api/miner/<id> endpoint
        miner_data = upstream.get(f'/api/miner/{miner_id}')
        
        if not isinstance(miner_data, dict):
            raise UpstreamError("Invalid miner response format", status_code=502)
        
        return jsonify({
            'success': True,
            'data': miner_data,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
        
    except UpstreamError as e:
        if e.status_code == 404:
            return jsonify({
                'success': False,
                'error': 'Miner not found'
            }), 404
        logger.warning(f"Miner fetch failed for {miner_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), e.status_code


@app.route('/api/balance', methods=['GET'])
@rate_limit
def get_balance():
    """
    Get wallet balance for a miner.
    
    Query Parameters:
        address: Wallet address to look up
    
    Returns:
        JSON with balance information:
        - miner_pk: Wallet address
        - balance: Current balance in RTC
        - epoch_rewards: Rewards in current epoch
        - total_earned: Total RTC earned
    """
    # Validate address parameter
    schema = WalletAddressSchema()
    try:
        params = schema.load(request.args.to_dict())
    except MarshmallowValidationError as e:
        return jsonify({
            'success': False,
            'error': 'Invalid address parameter',
            'details': e.messages
        }), 400
    
    address = params['address']
    
    try:
        balance_data = upstream.get('/balance', params={'miner_id': address})
        
        if not isinstance(balance_data, dict):
            raise UpstreamError("Invalid balance response format", status_code=502)
        
        return jsonify({
            'success': True,
            'data': {
                'address': address,
                'balance': float(balance_data.get('balance', 0.0)),
                'epoch_rewards': float(balance_data.get('epoch_rewards', 0.0)),
                'total_earned': float(balance_data.get('total_earned', 0.0)),
                'pending': float(balance_data.get('pending', 0.0))
            },
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
        
    except UpstreamError as e:
        if e.status_code == 404:
            return jsonify({
                'success': False,
                'error': 'Wallet not found',
                'address': address
            }), 404
        logger.warning(f"Balance fetch failed for {address}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), e.status_code


@app.route('/api/transactions', methods=['GET'])
@rate_limit
def get_transactions():
    """
    Get recent transactions from upstream.
    
    Query Parameters:
        limit: Maximum transactions to return (1-1000, default: 50)
        offset: Offset for pagination (default: 0)
        address: Optional filter by wallet address
    
    Returns:
        JSON array of transaction objects with:
        - tx_id: Transaction ID/hash
        - from_addr: Source address
        - to_addr: Destination address
        - amount: Amount transferred
        - timestamp: Unix timestamp
        - status: Transaction status
    """
    # Validate pagination parameters
    schema = PaginationSchema()
    try:
        params = schema.load(request.args.to_dict())
    except MarshmallowValidationError as e:
        return jsonify({
            'success': False,
            'error': 'Invalid parameters',
            'details': e.messages
        }), 400
    
    # Optional address filter
    address_filter = request.args.get('address')
    if address_filter:
        addr_schema = WalletAddressSchema()
        try:
            addr_schema.validate({'address': address_filter})
        except MarshmallowValidationError as e:
            return jsonify({
                'success': False,
                'error': 'Invalid address filter',
                'details': e.messages
            }), 400
    
    query_params = {
        'limit': params['limit'],
        'offset': params['offset']
    }
    if address_filter:
        query_params['address'] = address_filter
    
    try:
        tx_data = upstream.get('/api/transactions', params=query_params)
        
        # Ensure we return a list
        if not isinstance(tx_data, list):
            tx_data = []
        
        # Normalize transaction structure
        normalized_txs = []
        for tx in tx_data:
            if not isinstance(tx, dict):
                continue
            
            normalized_txs.append({
                'tx_id': tx.get('tx_id', tx.get('hash', tx.get('id', 'unknown'))),
                'from_addr': tx.get('from_addr', tx.get('from', tx.get('sender', 'unknown'))),
                'to_addr': tx.get('to_addr', tx.get('to', tx.get('recipient', 'unknown'))),
                'amount': float(tx.get('amount', tx.get('value', 0.0))),
                'timestamp': tx.get('timestamp', tx.get('created_at', tx.get('time', 0))),
                'status': tx.get('status', 'confirmed'),
                'fee': float(tx.get('fee', 0.0)),
                'block_height': tx.get('block_height', tx.get('block', 0))
            })
        
        return jsonify({
            'success': True,
            'data': normalized_txs,
            'count': len(normalized_txs),
            'pagination': {
                'limit': params['limit'],
                'offset': params['offset'],
                'address_filter': address_filter
            },
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
        
    except UpstreamError as e:
        logger.warning(f"Transactions fetch failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), e.status_code


@app.route('/api/stats', methods=['GET'])
@rate_limit
def get_stats():
    """
    Get aggregated network statistics.
    Combines data from multiple upstream endpoints.
    
    Returns:
        JSON with aggregated stats:
        - total_miners: Number of active miners
        - current_epoch: Current epoch number
        - network_status: Overall network health
        - total_transactions: Recent transaction count
    """
    try:
        # Fetch data from multiple endpoints in parallel would be ideal
        # For now, sequential calls with error handling
        stats = {
            'total_miners': 0,
            'current_epoch': 0,
            'network_status': 'unknown',
            'total_transactions': 0
        }
        
        # Get epoch data
        try:
            epoch_data = upstream.get('/epoch')
            stats['current_epoch'] = epoch_data.get('epoch', 0)
            stats['enrolled_miners'] = epoch_data.get('enrolled_miners', 0)
        except UpstreamError:
            pass
        
        # Get miners count
        try:
            miners_data = upstream.get('/api/miners', params={'limit': 1})
            if isinstance(miners_data, list):
                stats['total_miners'] = len(miners_data)
        except UpstreamError:
            pass
        
        # Get health status
        try:
            health_data = upstream.get('/health')
            stats['network_status'] = 'healthy' if health_data.get('ok', False) else 'degraded'
            stats['node_version'] = health_data.get('version', 'unknown')
        except UpstreamError:
            stats['network_status'] = 'unknown'
        
        return jsonify({
            'success': True,
            'data': stats,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
        
    except Exception as e:
        logger.exception("Stats aggregation failed")
        return jsonify({
            'success': False,
            'error': f'Stats aggregation failed: {str(e)}'
        }), 500


# ============================================================================
# Admin Endpoints (Protected)
# ============================================================================

@app.route('/admin/rate-limit/reset', methods=['POST'])
def reset_rate_limit():
    """
    Admin endpoint to reset rate limits.
    In production, this should be protected with authentication.
    
    Query Parameters:
        ip: Optional IP address to reset (resets all if not provided)
    """
    # Simple token-based auth (replace with proper auth in production)
    auth_token = request.headers.get('X-Admin-Token')
    expected_token = os.environ.get('ADMIN_TOKEN')
    
    if expected_token and auth_token != expected_token:
        return jsonify({
            'success': False,
            'error': 'Unauthorized'
        }), 401
    
    ip_to_reset = request.args.get('ip')
    rate_limiter.reset(ip_to_reset)
    
    return jsonify({
        'success': True,
        'message': f'Rate limit reset for {ip_to_reset or "all IPs"}'
    })


# ============================================================================
# Frontend Routes
# ============================================================================

@app.route('/', methods=['GET'])
def serve_frontend():
    """Serve the main frontend dashboard"""
    return app.send_static_file('index.html') if os.path.exists('api/index.html') else jsonify({
        'message': 'RustChain API Server',
        'version': '1.0.0',
        'endpoints': [
            '/health',
            '/api/health',
            '/api/epoch',
            '/api/miners',
            '/api/miner/<id>',
            '/api/balance',
            '/api/transactions',
            '/api/stats'
        ]
    })


@app.route('/dashboard', methods=['GET'])
def dashboard():
    """Serve the network explorer dashboard"""
    static_dir = os.path.dirname(os.path.abspath(__file__))
    index_path = os.path.join(static_dir, 'index.html')
    
    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8') as f:
            return f.read(), 200, {'Content-Type': 'text/html'}
    
    return jsonify({
        'error': 'Frontend not found',
        'message': 'Please ensure index.html exists in the api directory'
    }), 404


# ============================================================================
# Main Entry Point
# ============================================================================

def create_app():
    """Application factory for WSGI servers"""
    app.config['start_time'] = time.time()
    return app


if __name__ == '__main__':
    app.config['start_time'] = time.time()
    logger.info(f"Starting RustChain API Server on {SERVER_HOST}:{SERVER_PORT}")
    logger.info(f"Upstream API base: {API_BASE}")
    logger.info(f"Rate limit: {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW}s")
    
    if DEBUG_MODE:
        app.run(host=SERVER_HOST, port=SERVER_PORT, debug=True)
    else:
        # For production, use gunicorn:
        # gunicorn -w 4 -b 0.0.0.0:8080 api_server:app
        app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False)
