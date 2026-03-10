### What happened
When querying the API endpoint for a non-existent block hash or index using `/api/chain/block/<id>`, the server raises an unhandled `KeyError` and returns a 500 Internal Server Error instead of properly handling the missing resource.

### Expected
The API should catch the missing block identifier and gracefully return a 404 Not Found status code with a standard JSON payload: `{"error": "Block not found"}`.

### Steps to reproduce
1. Start the local node: `python src/api_patch.py`
2. Execute the reproduction script: `python tests/reproduce_api_bug.py`
3. Alternatively run via curl: `curl -X GET http://localhost:5000/api/chain/block/999999`
4. Observe the 500 traceback in the console logs on the unpatched version.

### Environment
- OS: Ubuntu 22.04 LTS
- Python: 3.10.12
- Rustchain version: main (commit 8f3a2b1)

### Your wallet ID
RTC_WALLET_0x71C7656EC7ab88b098defB751B7401B5f6d8976F