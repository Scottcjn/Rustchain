```python
def release_escrow():
    data = request.get_json()
    job_id = data['job_id']
    actor_wallet = data['actor_wallet']
    escrow_secret = data['escrow_secret']

    # Fetch the escrow record
    cursor = db.execute('''SELECT from_wallet, to_wallet, amount_rtc, status, escrow_secret 
                          FROM render_escrow 
                          WHERE job_id = ? AND status = 'locked' AND escrow_secret = ?''', 
                          (job_id, escrow_secret))
    result = cursor.fetchone()
    if not result:
        return jsonify({'error': 'Escrow not found or already processed'})

    from_wallet, to_wallet, amount_rtc, status, stored_secret = result
    if stored_secret != escrow_secret:
        return jsonify({'error': 'Invalid escrow_secret'})

    # Verify actor_wallet matches from_wallet
    if actor_wallet != from_wallet:
        return jsonify({'error': 'Actor wallet does not match from_wallet'})

    # Update the status and return the amount
    db.execute('''UPDATE render_escrow 
                  SET status = 'released' 
                  WHERE job_id = ? AND escrow_secret = ?''', 
                  (job_id, escrow_secret))
    db.commit()

    return jsonify({'message': 'Escrow released successfully', 'amount_rtc': amount_rtc})
```