"""
Example Flask Application with RTC Payment-Gated Endpoints

This demonstrates the x402 Payment Required protocol with RustChain.

Run:
    RTC_PAYMENT_ADDRESS=gurgguda python example_app.py

Test:
    # First request returns 402
    curl http://localhost:5000/api/data
    
    # With payment proof (after paying)
    curl http://localhost:5000/api/data \
      -H "X-Payment-TX: <tx_hash>" \
      -H "X-Payment-Signature: <signature>" \
      -H "X-Payment-Sender: <wallet_address>" \
      -H "X-Payment-Nonce: <nonce>"
"""

import os
from flask import Flask, jsonify, g
from rtc_payment_middleware import require_rtc_payment

app = Flask(__name__)

# Configuration
PAYMENT_ADDRESS = os.environ.get('RTC_PAYMENT_ADDRESS', 'gurgguda')


@app.route('/')
def index():
    """Public endpoint - no payment required."""
    return jsonify({
        'message': 'Welcome to the RTC-gated API',
        'endpoints': {
            '/': 'This help message (free)',
            '/api/data': 'Premium data endpoint (0.001 RTC)',
            '/api/analysis': 'Analysis endpoint (0.005 RTC)',
            '/api/bulk': 'Bulk data endpoint (0.01 RTC)'
        }
    })


@app.route('/api/data')
@require_rtc_payment(amount=0.001, recipient=PAYMENT_ADDRESS)
def get_data():
    """Premium data endpoint - requires 0.001 RTC payment."""
    return jsonify({
        'status': 'success',
        'data': {
            'message': 'This is premium data',
            'timestamp': __import__('time').time(),
            'paid_by': getattr(g, 'rtc_sender', 'unknown'),
            'amount_paid': getattr(g, 'rtc_payment_amount', 0)
        }
    })


@app.route('/api/analysis')
@require_rtc_payment(amount=0.005, recipient=PAYMENT_ADDRESS)
def get_analysis():
    """Analysis endpoint - requires 0.005 RTC payment."""
    return jsonify({
        'status': 'success',
        'analysis': {
            'trend': 'positive',
            'confidence': 0.87,
            'recommendation': 'hold',
            'generated_for': getattr(g, 'rtc_sender', 'unknown')
        }
    })


@app.route('/api/bulk')
@require_rtc_payment(amount=0.01, recipient=PAYMENT_ADDRESS)
def get_bulk_data():
    """Bulk data endpoint - requires 0.01 RTC payment."""
    return jsonify({
        'status': 'success',
        'bulk_data': [
            {'id': i, 'value': f'item_{i}'} for i in range(100)
        ],
        'count': 100,
        'paid_by': getattr(g, 'rtc_sender', 'unknown')
    })


if __name__ == '__main__':
    print(f"Starting RTC payment-gated API server...")
    print(f"Payment address: {PAYMENT_ADDRESS}")
    print(f"Endpoints:")
    print(f"  GET /          - Free (info)")
    print(f"  GET /api/data  - 0.001 RTC")
    print(f"  GET /api/analysis - 0.005 RTC")
    print(f"  GET /api/bulk  - 0.01 RTC")
    app.run(debug=True, port=5000)
