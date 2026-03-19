<!-- SPDX-License-Identifier: MIT -->
# Rustchain API Reference

Here’s a quick guide to the main API endpoints we run in Rustchain. Hope this makes it easier for devs to plug in and test things out.

## Public Endpoints

### GET /health
Check if the node is alive.  
Example:  
```bash
curl https://node.rustchain.io/health
```
Returns `{"status":"ok"}` when healthy.

### GET /ready
See if the node is ready for requests.  
```bash
curl https://node.rustchain.io/ready
```

### GET /epoch
Get the current epoch number.  
```bash
curl https://node.rustchain.io/epoch
```

### GET /api/miners
List active miners.  
```bash
curl https://node.rustchain.io/api/miners
```

### GET /wallet/balance
Check a wallet’s balance (public view).  
```bash
curl https://node.rustchain.io/wallet/balance?address=abc123
```

### GET /explorer
Open the block explorer UI.  
Visit `https://node.rustchain.io/explorer`.

## Admin Endpoints (Auth Required)

### POST /wallet/transfer
Move funds between wallets. Needs admin JWT.  
```bash
curl -X POST -H "Authorization: Bearer $ADMIN_JWT" \
  -d '{"from":"abc","to":"xyz","amount":100}' \
  https://node.rustchain.io/wallet/transfer
```

### POST /rewards/settle
Trigger reward settlement.  
```bash
curl -X POST -H "Authorization: Bearer $ADMIN_JWT" \
  https://node.rustchain.io/rewards/settle
```

## Notes
- All responses are JSON.  
- Use HTTPS in production.  
- Admin endpoints require a valid JWT in the `Authorization` header.
