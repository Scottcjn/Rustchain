// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import os
from contextlib import contextmanager

DB_PATH = "otc_orders.db"

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_database():
    """Initialize the OTC orders database with proper schema and indexes"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Create orders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_address TEXT NOT NULL,
                rtc_amount REAL NOT NULL,
                price_per_rtc REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT 'ETH',
                total_value REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                escrow_address TEXT,
                buyer_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                notes TEXT
            )
        ''')

        # Create indexes for better query performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_seller ON orders(seller_address)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_currency ON orders(currency)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_price ON orders(price_per_rtc)')

        # Create escrow transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS escrow_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                transaction_hash TEXT UNIQUE,
                transaction_type TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL,
                from_address TEXT,
                to_address TEXT,
                block_number INTEGER,
                confirmations INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confirmed_at TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders (id)
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_escrow_order ON escrow_transactions(order_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_escrow_hash ON escrow_transactions(transaction_hash)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_escrow_status ON escrow_transactions(status)')

        conn.commit()

def create_order(seller_address, rtc_amount, price_per_rtc, currency='ETH', notes=None):
    """Create a new OTC order"""
    total_value = rtc_amount * price_per_rtc

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO orders (seller_address, rtc_amount, price_per_rtc, currency, total_value, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (seller_address, rtc_amount, price_per_rtc, currency, total_value, notes))

        order_id = cursor.lastrowid
        conn.commit()
        return order_id

def get_open_orders(currency=None, limit=50):
    """Get all open orders, optionally filtered by currency"""
    with get_db() as conn:
        cursor = conn.cursor()

        if currency:
            cursor.execute('''
                SELECT * FROM orders
                WHERE status = 'open' AND currency = ?
                ORDER BY price_per_rtc ASC, created_at DESC
                LIMIT ?
            ''', (currency, limit))
        else:
            cursor.execute('''
                SELECT * FROM orders
                WHERE status = 'open'
                ORDER BY price_per_rtc ASC, created_at DESC
                LIMIT ?
            ''', (limit,))

        return cursor.fetchall()

def get_order_by_id(order_id):
    """Get specific order by ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
        return cursor.fetchone()

def update_order_status(order_id, status, buyer_address=None, escrow_address=None):
    """Update order status and related fields"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE orders
            SET status = ?, buyer_address = ?, escrow_address = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (status, buyer_address, escrow_address, order_id))
        conn.commit()
        return cursor.rowcount > 0

def add_escrow_transaction(order_id, tx_hash, tx_type, amount, currency, from_addr=None, to_addr=None):
    """Add escrow transaction record"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO escrow_transactions
            (order_id, transaction_hash, transaction_type, amount, currency, from_address, to_address)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (order_id, tx_hash, tx_type, amount, currency, from_addr, to_addr))
        conn.commit()
        return cursor.lastrowid

def get_order_transactions(order_id):
    """Get all transactions for a specific order"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM escrow_transactions
            WHERE order_id = ?
            ORDER BY created_at DESC
        ''', (order_id,))
        return cursor.fetchall()

def cleanup_expired_orders():
    """Mark expired orders as cancelled"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE orders
            SET status = 'expired', updated_at = CURRENT_TIMESTAMP
            WHERE status = 'open' AND expires_at < CURRENT_TIMESTAMP
        ''')
        expired_count = cursor.rowcount
        conn.commit()
        return expired_count

def get_market_stats():
    """Get basic market statistics"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Total open orders
        cursor.execute('SELECT COUNT(*) as count FROM orders WHERE status = "open"')
        open_orders = cursor.fetchone()['count']

        # Total RTC available
        cursor.execute('SELECT SUM(rtc_amount) as total FROM orders WHERE status = "open"')
        total_rtc = cursor.fetchone()['total'] or 0

        # Average price by currency
        cursor.execute('''
            SELECT currency, AVG(price_per_rtc) as avg_price, COUNT(*) as count
            FROM orders WHERE status = "open"
            GROUP BY currency
        ''')
        avg_prices = cursor.fetchall()

        return {
            'open_orders': open_orders,
            'total_rtc_available': total_rtc,
            'average_prices': [dict(row) for row in avg_prices]
        }

def database_exists():
    """Check if database file exists"""
    return os.path.exists(DB_PATH)

if __name__ == "__main__":
    init_database()
    print(f"OTC database initialized at {DB_PATH}")
