// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Blueprint, jsonify, request, render_template
from app.models.payout_ledger import PayoutLedger, db
from datetime import datetime

payout_bp = Blueprint('payout_ledger', __name__)

@payout_bp.route('/ledger')
def view_ledger():
    """Display the bounty payout ledger"""
    payouts = PayoutLedger.query.order_by(PayoutLedger.date_utc.desc()).all()
    return render_template('payout_ledger.html', payouts=payouts)

@payout_bp.route('/api/ledger')
def api_ledger():
    """API endpoint for payout ledger data"""
    payouts = PayoutLedger.query.order_by(PayoutLedger.date_utc.desc()).all()
    return jsonify([payout.to_dict() for payout in payouts])

@payout_bp.route('/api/ledger/add', methods=['POST'])
def add_payout_entry():
    """Add new payout entry to ledger"""
    data = request.get_json()
    
    payout = PayoutLedger(
        bounty_ref=data['bounty_ref'],
        github_user=data['github_user'],
        wallet=data['wallet'],
        amount_rtc=data['amount_rtc'],
        status=data['status'],
        pending_id=data.get('pending_id'),
        tx_hash=data.get('tx_hash'),
        notes=data.get('notes'),
        confirms_at=datetime.fromisoformat(data['confirms_at']) if data.get('confirms_at') else None
    )
    
    db.session.add(payout)
    db.session.commit()
    
    return jsonify(payout.to_dict()), 201

@payout_bp.route('/api/ledger/update/<int:payout_id>', methods=['PUT'])
def update_payout_status(payout_id):
    """Update payout status and related fields"""
    payout = PayoutLedger.query.get_or_404(payout_id)
    data = request.get_json()
    
    if 'status' in data:
        payout.status = data['status']
    if 'tx_hash' in data:
        payout.tx_hash = data['tx_hash']
    if 'notes' in data:
        payout.notes = data['notes']
    if 'confirms_at' in data:
        payout.confirms_at = datetime.fromisoformat(data['confirms_at']) if data['confirms_at'] else None
    
    db.session.commit()
    return jsonify(payout.to_dict())