import sqlite3
from flask import Blueprint, request, jsonify

wallet_history_bp = Blueprint('wallet_history', __name__)

# Function to fetch wallet history from sqlite database
def fetch_wallet_history(page, per_page):
    conn = sqlite3.connect('wallet.db')  # Replace with actual DB path
    cursor = conn.cursor()
    # Pagination and sorting query
    query = '''SELECT * FROM ledger UNION ALL SELECT * FROM epoch_rewards ORDER BY timestamp DESC LIMIT ? OFFSET ?'''
    cursor.execute(query, (per_page, (page - 1) * per_page))
    results = cursor.fetchall()
    conn.close()
    return results

@wallet_history_bp.route('/wallet/history', methods=['GET'])
def wallet_history():
    try:
        # Get query parameters
        page = int(request.args.get('page', 1))  # Default page 1
        per_page = int(request.args.get('per_page', 10))  # Default items per page 10

        # Fetch wallet history
        history = fetch_wallet_history(page, per_page)
        if not history:
            return jsonify({'message': 'No history found'}), 404

        # Format response
        response = {
            'page': page,
            'per_page': per_page,
            'total': len(history),
            'history': history
        }
        return jsonify(response), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
