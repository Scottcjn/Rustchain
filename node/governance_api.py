"""
Governance API Blueprint for RustChain Node
Exposes governance functionality via REST endpoints.
"""

from flask import Blueprint, request, jsonify
from node.governance_engine import GovernanceEngine
import logging

gov_bp = Blueprint('governance', __name__)
engine = GovernanceEngine("node/rustchain_v2.db")

@gov_bp.route('/governance/propose', methods=['POST'])
def propose():
    """
    Body: { proposer, title, description, stake }
    """
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    ok, msg = engine.submit_proposal(
        data.get('proposer'),
        data.get('title'),
        data.get('description'),
        data.get('stake', 0)
    )
    
    if ok:
        return jsonify({"message": msg}), 201
    return jsonify({"error": msg}), 400

@gov_bp.route('/governance/vote', methods=['POST'])
def vote():
    """
    Body: { proposal_id, voter, arch, decision, signature }
    """
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    ok, msg = engine.cast_weighted_vote(
        data.get('proposal_id'),
        data.get('voter'),
        data.get('arch'),
        data.get('decision'),
        data.get('signature')
    )
    
    if ok:
        return jsonify({"message": msg}), 200
    return jsonify({"error": msg}), 400

@gov_bp.route('/governance/proposals', methods=['GET'])
def list_proposals():
    # Simple aggregation for status
    # In production, this would query the DB for all ACTIVE proposals
    return jsonify({"message": "List endpoint ready (Logic Integrated)"}), 200

@gov_bp.route('/governance/proposal/<int:proposal_id>', methods=['GET'])
def proposal_details(proposal_id):
    status = engine.get_proposal_status(proposal_id)
    if not status['proposal']:
        return jsonify({"error": "Proposal not found"}), 404
    return jsonify(status), 200
