# Add this endpoint to the Flask app

from flask import Flask, request, jsonify
from datetime import datetime
import sqlite3
from functools import wraps

app = Flask(__name__)

# Database connection helper
def get_db_connection():
    conn = sqlite3.connect('rustchain.db')
    conn.row_factory = sqlite3.Row
    return conn

# Validation decorator
def validate_miner_id(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        miner_id = request.args.get('miner_id')
        if not miner_id:
            return jsonify({
                'ok': False,
                'error': 'miner_id parameter is required'
            }), 400
        if len(miner_id) > 128:
            return jsonify({
                'ok': False,
                'error': 'miner_id exceeds maximum length'
            }), 400
        return f(*args, **kwargs)
    return decorated_function

@app.route('/wallet/history', methods=['GET'])
@validate_miner_id
def wallet_history():
    """
    Get transaction history for a wallet/miner.
    
    Query Parameters:
        miner_id (str, required): The miner/wallet identifier
        limit (int, optional): Maximum number of transactions to return (default: 50, max: 500)
        offset (int, optional): Number of transactions to skip (default: 0)
    
    Returns:
        JSON object with transaction history
    """
    try:
        miner_id = request.args.get('miner_id').strip()
        limit = request.args.get('limit', default=50, type=int)
        offset = request.args.get('offset', default=0, type=int)
        
        # Validate limit and offset
        if limit < 1 or limit > 500:
            return jsonify({
                'ok': False,
                'error': 'limit must be between 1 and 500'
            }), 400
        
        if offset < 0:
            return jsonify({
                'ok': False,
                'error': 'offset must be non-negative'
            }), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get total count of transactions for this miner
        cursor.execute("""
            SELECT COUNT(*) as total FROM transactions 
            WHERE sender_id = ? OR receiver_id = ?
        """, (miner_id, miner_id))
        total_count = cursor.fetchone()['total']
        
        # Get transaction history
        cursor.execute("""
            SELECT 
                transaction_id,
                sender_id,
                receiver_id,
                amount,
                fee,
                status,
                timestamp,
                block_height,
                tx_hash
            FROM transactions
            WHERE sender_id = ? OR receiver_id = ?
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """, (miner_id, miner_id, limit, offset))
        
        transactions = cursor.fetchall()
        conn.close()
        
        # Format response
        history = []
        for tx in transactions:
            transaction = {
                'transaction_id': tx['transaction_id'],
                'sender_id': tx['sender_id'],
                'receiver_id': tx['receiver_id'],
                'amount': float(tx['amount']),
                'fee': float(tx['fee']),
                'status': tx['status'],
                'timestamp': tx['timestamp'],
                'block_height': tx['block_height'],
                'tx_hash': tx['tx_hash'],
                'direction': 'sent' if tx['sender_id'] == miner_id else 'received'
            }
            history.append(transaction)
        
        return jsonify({
            'ok': True,
            'miner_id': miner_id,
            'total_transactions': total_count,
            'returned': len(history),
            'limit': limit,
            'offset': offset,
            'history': history
        }), 200
        
    except ValueError as e:
        return jsonify({
            'ok': False,
            'error': f'Invalid parameter format: {str(e)}'
        }), 400
    except Exception as e:
        return jsonify({
            'ok': False,
            'error': f'Server error: {str(e)}'
        }), 500

@app.route('/wallet/history/summary', methods=['GET'])
@validate_miner_id
def wallet_history_summary():
    """
    Get summary statistics of wallet transaction history.
    
    Query Parameters:
        miner_id (str, required): The miner/wallet identifier
    
    Returns:
        JSON object with transaction summary
    """
    try:
        miner_id = request.args.get('miner_id').strip()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get summary statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_transactions,
                SUM(CASE WHEN sender_id = ? THEN amount ELSE 0 END) as total_sent,
                SUM(CASE WHEN receiver_id = ? THEN amount ELSE 0 END) as total_received,
                SUM(CASE WHEN sender_id = ? THEN fee ELSE 0 END) as total_fees_paid,
                COUNT(CASE WHEN status = 'confirmed' THEN 1 END) as confirmed_count,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_count
            FROM transactions
            WHERE sender_id = ? OR receiver_id = ?
        """, (miner_id, miner_id, miner_id, miner_id, miner_id))
        
        summary = cursor.fetchone()
        conn.close()
        
        return jsonify({
            'ok': True,
            'miner_id': miner_id,
            'summary': {
                'total_transactions': summary['total_transactions'] or 0,
                'total_sent': float(summary['total_sent'] or 0),
                'total_received': float(summary['total_received'] or 0),
                'total_fees_paid': float(summary['total_fees_paid'] or 0),
                'confirmed_count': summary['confirmed_count'] or 0,
                'pending_count': summary['pending_count'] or 0,
                'failed_count': summary['failed_count'] or 0
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'ok': False,
            'error': f'Server error: {str(e)}'
        }), 500
