from flask import Flask, jsonify

app = Flask(__name__)

# Mocking the blockchain state for bug demonstration
chain_data = {
    "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f": {
        "height": 0, 
        "transactions": []
    }
}

@app.route('/api/chain/block/<block_id>', methods=['GET'])
def get_block(block_id):
    try:
        # FIX INCLUDED: Verify block_id exists before accessing dict to prevent KeyError / 500 Error
        if block_id not in chain_data:
            return jsonify({"error": "Block not found", "status": 404}), 404
            
        block = chain_data[block_id]
        return jsonify({"block": block, "status": 200}), 200
        
    except Exception as e:
        # Unhandled exceptions will fallback to 500
        return jsonify({"error": "Internal Server Error", "details": str(e), "status": 500}), 500

if __name__ == "__main__":
    app.run(port=5000, debug=True)
