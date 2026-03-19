// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class PayoutLedger(db.Model):
    __tablename__ = 'payout_ledger'
    
    id = db.Column(db.Integer, primary_key=True)
    date_utc = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    bounty_ref = db.Column(db.String(100), nullable=False)
    github_user = db.Column(db.String(100), nullable=False)
    wallet = db.Column(db.String(100), nullable=False)
    amount_rtc = db.Column(db.Integer, nullable=False)
    status = db.Column(db.Enum('Queued', 'Pending', 'Confirmed', 'Voided', name='payout_status'), nullable=False)
    pending_id = db.Column(db.Integer)
    tx_hash = db.Column(db.String(64))
    notes = db.Column(db.Text)
    confirms_at = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<PayoutLedger {self.bounty_ref} - {self.github_user}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'date_utc': self.date_utc.isoformat() if self.date_utc else None,
            'bounty_ref': self.bounty_ref,
            'github_user': self.github_user,
            'wallet': self.wallet,
            'amount_rtc': self.amount_rtc,
            'status': self.status,
            'pending_id': self.pending_id,
            'tx_hash': self.tx_hash,
            'notes': self.notes,
            'confirms_at': self.confirms_at.isoformat() if self.confirms_at else None
        }