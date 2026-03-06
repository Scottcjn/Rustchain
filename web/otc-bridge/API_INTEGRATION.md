# OTC Bridge API Integration Guide

**For Backend Developers**

This guide provides detailed instructions for integrating the OTC Bridge frontend with your backend services.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [API Specification](#api-specification)
- [Data Models](#data-models)
- [Implementation Examples](#implementation-examples)
- [Error Handling](#error-handling)
- [Security Considerations](#security-considerations)
- [Testing](#testing)

---

## Architecture Overview

```
┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│   Frontend UI    │ ──────▶ │  API Adapter     │ ──────▶ │  Backend Services│
│  (index.html)    │  HTTP   │  (otc-bridge.js) │  JSON   │  (Your Server)   │
└──────────────────┘         └──────────────────┘         └──────────────────┘
```

### Request Flow

1. User interacts with UI (enters amount, address)
2. Frontend validates input client-side
3. API adapter makes HTTP request to backend
4. Backend processes request, interacts with blockchain
5. Response returned to frontend
6. UI updates with results

---

## API Specification

### Base URL

```
Production: https://rustchain.org/api/otc
Development: http://localhost:3000/api/otc
```

### Authentication

Currently, all endpoints are public. For production:

- Implement rate limiting
- Consider API keys for high-volume users
- Use HTTPS only

### Common Response Format

All responses follow this structure:

```typescript
interface ApiResponse<T> {
    ok: boolean;           // Success indicator
    data?: T;             // Success data
    error?: {             // Error details (if ok === false)
        code: string;
        message: string;
        details?: any;
    };
    timestamp?: number;   // Unix timestamp
}
```

---

## Endpoint Details

### 1. GET /quote

Get a quote for swapping tokens.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `from` | string | Yes | Source token symbol (RTC or wRTC) |
| `to` | string | Yes | Destination token symbol |
| `amount` | number | Yes | Amount to swap |
| `slippage` | number | No | Slippage tolerance % (default: 0.5) |

**Example Request:**

```bash
curl -X GET "https://rustchain.org/api/otc/quote?from=RTC&to=wRTC&amount=100&slippage=0.5"
```

**Example Response:**

```json
{
    "ok": true,
    "quote": {
        "id": "quote_1709856000_abc123",
        "from": "RTC",
        "to": "wRTC",
        "fromAmount": "100.000000",
        "toAmount": "99.900000",
        "rate": "0.999000",
        "fee": "0.100000",
        "feePercent": "0.1",
        "slippage": "0.5",
        "minimumReceived": "99.400500",
        "priceImpact": "0.01",
        "validUntil": 1709856300,
        "createdAt": 1709856000
    },
    "timestamp": 1709856000
}
```

**Implementation Notes:**

- Quotes should be valid for 5-10 minutes
- Rate should include current market price + bridge fee
- Price impact should increase with larger amounts
- Store quote ID for later execution

---

### 2. POST /swap

Execute a token swap.

**Request Body:**

```typescript
interface SwapRequest {
    from: string;              // Source token
    to: string;                // Destination token
    fromAmount: string;        // Amount as string (precision)
    toAddress: string;         // Destination wallet address
    slippage: number;          // Slippage tolerance %
    quoteId: string;           // Quote ID from /quote
    memo?: string;             // Optional memo/note
}
```

**Example Request:**

```bash
curl -X POST "https://rustchain.org/api/otc/swap" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "RTC",
    "to": "wRTC",
    "fromAmount": "100.000000",
    "toAddress": "7nx8QmzxD1wKX7QJ1FVqT5hX9YvJxKqZb8yPoR3dL8mN",
    "slippage": 0.5,
    "quoteId": "quote_1709856000_abc123"
  }'
```

**Example Response:**

```json
{
    "ok": true,
    "swap": {
        "id": "swap_1709856000_xyz789",
        "status": "pending",
        "from": "RTC",
        "to": "wRTC",
        "fromAmount": "100.000000",
        "toAmount": "99.900000",
        "txHash": "5KtP7xQmzxD1wKX7QJ1FVqT5hX9YvJxKqZb8yPoR3dL8mN...",
        "sourceTxHash": "3AbC...xyz",
        "destinationTxHash": null,
        "estimatedTime": "5-30 minutes",
        "createdAt": 1709856000,
        "expiresAt": 1709859600
    },
    "timestamp": 1709856000
}
```

**Implementation Notes:**

- Validate quote ID and ensure it hasn't expired
- Lock tokens immediately upon swap creation
- Generate unique swap ID for tracking
- Return transaction hash(es) as they become available
- Implement idempotency (prevent duplicate swaps)

---

### 3. GET /status/:swapId

Check the status of a swap.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `swapId` | string | Yes | Swap ID from /swap response |

**Example Request:**

```bash
curl -X GET "https://rustchain.org/api/otc/status/swap_1709856000_xyz789"
```

**Example Response:**

```json
{
    "ok": true,
    "status": {
        "id": "swap_1709856000_xyz789",
        "state": "processing",
        "progress": 45,
        "steps": [
            {
                "name": "initiated",
                "completed": true,
                "timestamp": 1709856000,
                "txHash": null
            },
            {
                "name": "locked",
                "completed": true,
                "timestamp": 1709856120,
                "txHash": "3AbC...xyz"
            },
            {
                "name": "bridging",
                "completed": false,
                "timestamp": null,
                "txHash": null
            },
            {
                "name": "completed",
                "completed": false,
                "timestamp": null,
                "txHash": null
            }
        ],
        "from": "RTC",
        "to": "wRTC",
        "fromAmount": "100.000000",
        "toAmount": "99.900000",
        "sourceTxHash": "3AbC...xyz",
        "destinationTxHash": null,
        "estimatedCompletion": 1709857800
    },
    "timestamp": 1709856600
}
```

**State Machine:**

```
pending → initiated → locked → bridging → completed
                              ↓
                           failed
```

**State Descriptions:**

- `pending`: Swap created, waiting for token lock
- `initiated`: Transaction submitted to source chain
- `locked`: Tokens locked on source chain
- `bridging`: Cross-chain transfer in progress
- `completed`: Tokens released on destination chain
- `failed`: Swap failed (see error details)

---

### 4. GET /market

Get current market data.

**Example Request:**

```bash
curl -X GET "https://rustchain.org/api/otc/market"
```

**Example Response:**

```json
{
    "ok": true,
    "data": {
        "volume24h": "75432.50",
        "liquidity": "892156.00",
        "lastPrice": "1.000000",
        "priceChange24h": "-0.52",
        "high24h": "1.02",
        "low24h": "0.98",
        "trades24h": 1247
    },
    "timestamp": 1709856000
}
```

---

### 5. GET /recent

Get recent transactions.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | number | No | Number of transactions (default: 10, max: 50) |

**Example Request:**

```bash
curl -X GET "https://rustchain.org/api/otc/recent?limit=10"
```

**Example Response:**

```json
{
    "ok": true,
    "transactions": [
        {
            "id": "tx_1709856000_001",
            "swapId": "swap_1709855000_abc",
            "from": "RTC",
            "to": "wRTC",
            "amount": "150.000000",
            "toAmount": "149.850000",
            "txHash": "5KtP...xyz",
            "timestamp": 1709856000,
            "status": "completed"
        }
    ],
    "timestamp": 1709856000
}
```

---

### 6. POST /validate-address

Validate a wallet address.

**Request Body:**

```typescript
interface ValidateAddressRequest {
    address: string;         // Address to validate
    network: string;         // 'solana' or 'rustchain'
}
```

**Example Request:**

```bash
curl -X POST "https://rustchain.org/api/otc/validate-address" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "7nx8QmzxD1wKX7QJ1FVqT5hX9YvJxKqZb8yPoR3dL8mN",
    "network": "solana"
  }'
```

**Example Response:**

```json
{
    "ok": true,
    "valid": true,
    "network": "solana",
    "address": "7nx8QmzxD1wKX7QJ1FVqT5hX9YvJxKqZb8yPoR3dL8mN",
    "addressType": "wallet",
    "exists": true
}
```

---

## Data Models

### TypeScript Definitions

```typescript
// Token types
type TokenSymbol = 'RTC' | 'wRTC';

// Swap direction
type SwapDirection = 'rtc-to-wrtc' | 'wrtc-to-rtc';

// Quote object
interface Quote {
    id: string;
    from: TokenSymbol;
    to: TokenSymbol;
    fromAmount: string;        // Decimal string
    toAmount: string;          // Decimal string
    rate: string;              // Exchange rate
    fee: string;               // Fee amount
    feePercent: string;        // Fee percentage
    slippage: number;          // Slippage tolerance %
    minimumReceived: string;   // After slippage
    priceImpact: string;       // Price impact %
    validUntil: number;        // Unix timestamp
    createdAt: number;         // Unix timestamp
}

// Swap object
interface Swap {
    id: string;
    status: SwapStatus;
    from: TokenSymbol;
    to: TokenSymbol;
    fromAmount: string;
    toAmount: string;
    txHash: string;
    sourceTxHash?: string;
    destinationTxHash?: string;
    estimatedTime: string;
    createdAt: number;
    expiresAt?: number;
}

// Swap status
type SwapStatus = 
    | 'pending'
    | 'initiated'
    | 'locked'
    | 'bridging'
    | 'completed'
    | 'failed';

// Status step
interface StatusStep {
    name: string;
    completed: boolean;
    timestamp: number | null;
    txHash: string | null;
}

// Market data
interface MarketData {
    volume24h: string;
    liquidity: string;
    lastPrice: string;
    priceChange24h: string;
    high24h: string;
    low24h: string;
    trades24h: number;
}

// Transaction
interface Transaction {
    id: string;
    swapId: string;
    from: TokenSymbol;
    to: TokenSymbol;
    amount: string;
    toAmount: string;
    txHash: string;
    timestamp: number;
    status: SwapStatus;
}
```

---

## Implementation Examples

### Node.js/Express Example

```javascript
const express = require('express');
const app = express();

app.use(express.json());

// Quote endpoint
app.get('/api/otc/quote', async (req, res) => {
    const { from, to, amount, slippage = 0.5 } = req.query;
    
    try {
        // Validate parameters
        if (!from || !to || !amount) {
            return res.status(400).json({
                ok: false,
                error: {
                    code: 'INVALID_PARAMS',
                    message: 'Missing required parameters'
                }
            });
        }
        
        // Calculate quote (integrate with your pricing logic)
        const rate = await getExchangeRate(from, to);
        const fee = amount * 0.001; // 0.1%
        const toAmount = (amount - fee) * rate;
        const minimumReceived = toAmount * (1 - slippage / 100);
        
        // Generate quote ID
        const quoteId = `quote_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        // Store quote for later validation
        await storeQuote(quoteId, { from, to, amount, toAmount, rate, fee, slippage });
        
        res.json({
            ok: true,
            quote: {
                id: quoteId,
                from,
                to,
                fromAmount: amount.toString(),
                toAmount: toAmount.toFixed(6),
                rate: rate.toString(),
                fee: fee.toString(),
                feePercent: '0.1',
                slippage: slippage.toString(),
                minimumReceived: minimumReceived.toFixed(6),
                priceImpact: '0.01',
                validUntil: Math.floor(Date.now() / 1000) + 300,
                createdAt: Math.floor(Date.now() / 1000)
            }
        });
    } catch (error) {
        console.error('Quote error:', error);
        res.status(500).json({
            ok: false,
            error: {
                code: 'QUOTE_ERROR',
                message: error.message
            }
        });
    }
});

// Swap endpoint
app.post('/api/otc/swap', async (req, res) => {
    const { from, to, fromAmount, toAddress, slippage, quoteId } = req.body;
    
    try {
        // Validate quote
        const quote = await getQuote(quoteId);
        if (!quote) {
            return res.status(400).json({
                ok: false,
                error: {
                    code: 'INVALID_QUOTE',
                    message: 'Quote not found or expired'
                }
            });
        }
        
        // Validate address
        const isValid = await validateAddress(toAddress, to === 'wRTC' ? 'solana' : 'rustchain');
        if (!isValid) {
            return res.status(400).json({
                ok: false,
                error: {
                    code: 'INVALID_ADDRESS',
                    message: 'Invalid destination address'
                }
            });
        }
        
        // Create swap record
        const swapId = `swap_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        await createSwap({
            swapId,
            quoteId,
            from,
            to,
            fromAmount,
            toAddress,
            slippage
        });
        
        // Lock tokens (integrate with blockchain)
        const txHash = await lockTokens(from, fromAmount, /* ... */);
        
        res.json({
            ok: true,
            swap: {
                id: swapId,
                status: 'pending',
                from,
                to,
                fromAmount,
                toAmount: quote.toAmount,
                txHash,
                estimatedTime: '5-30 minutes',
                createdAt: Math.floor(Date.now() / 1000)
            }
        });
    } catch (error) {
        console.error('Swap error:', error);
        res.status(500).json({
            ok: false,
            error: {
                code: 'SWAP_ERROR',
                message: error.message
            }
        });
    }
});

app.listen(3000, () => {
    console.log('OTC Bridge API listening on port 3000');
});
```

### Python/FastAPI Example

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import time

app = FastAPI()

class QuoteRequest(BaseModel):
    from_token: str
    to_token: str
    amount: float
    slippage: Optional[float] = 0.5

class SwapRequest(BaseModel):
    from_token: str
    to_token: str
    fromAmount: str
    toAddress: str
    slippage: float
    quoteId: str

@app.get("/api/otc/quote")
async def get_quote(
    from_token: str,
    to_token: str,
    amount: float,
    slippage: float = 0.5
):
    try:
        # Calculate quote
        rate = await get_exchange_rate(from_token, to_token)
        fee = amount * 0.001
        to_amount = (amount - fee) * rate
        minimum_received = to_amount * (1 - slippage / 100)
        
        quote_id = f"quote_{int(time.time())}_{time.time_ns() % 1000000}"
        
        return {
            "ok": True,
            "quote": {
                "id": quote_id,
                "from": from_token,
                "to": to_token,
                "fromAmount": str(amount),
                "toAmount": f"{to_amount:.6f}",
                "rate": str(rate),
                "fee": str(fee),
                "feePercent": "0.1",
                "slippage": str(slippage),
                "minimumReceived": f"{minimum_received:.6f}",
                "priceImpact": "0.01",
                "validUntil": int(time.time()) + 300,
                "createdAt": int(time.time())
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/otc/swap")
async def create_swap(request: SwapRequest):
    try:
        # Validate and process swap
        swap_id = f"swap_{int(time.time())}_{time.time_ns() % 1000000}"
        
        # TODO: Implement token locking logic
        
        return {
            "ok": True,
            "swap": {
                "id": swap_id,
                "status": "pending",
                "from": request.from_token,
                "to": request.to_token,
                "fromAmount": request.fromAmount,
                "toAmount": "0.000000",  # From quote
                "txHash": "0x...",
                "estimatedTime": "5-30 minutes",
                "createdAt": int(time.time())
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## Error Handling

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_PARAMS` | 400 | Missing or invalid parameters |
| `INVALID_QUOTE` | 400 | Quote not found or expired |
| `INVALID_ADDRESS` | 400 | Invalid destination address |
| `INSUFFICIENT_LIQUIDITY` | 400 | Not enough liquidity for swap |
| `AMOUNT_TOO_LOW` | 400 | Amount below minimum |
| `AMOUNT_TOO_HIGH` | 400 | Amount above maximum |
| `SWAP_NOT_FOUND` | 404 | Swap ID not found |
| `UNAUTHORIZED` | 401 | Authentication required |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Internal server error |
| `BLOCKCHAIN_ERROR` | 500 | Blockchain interaction failed |

### Error Response Format

```json
{
    "ok": false,
    "error": {
        "code": "INVALID_QUOTE",
        "message": "Quote not found or has expired",
        "details": {
            "quoteId": "quote_123",
            "expiredAt": 1709856300
        }
    },
    "timestamp": 1709856600
}
```

### Frontend Error Handling

```javascript
async function fetchQuote() {
    try {
        const response = await OTCBridgeAPI.getQuote({ /* ... */ });
        
        if (!response.ok) {
            throw new Error(response.error.message);
        }
        
        // Process successful response
        state.quote = response.quote;
    } catch (error) {
        // Handle error
        if (error.code === 'INVALID_QUOTE') {
            showToast('error', 'Quote expired. Please enter amount again.');
        } else {
            showToast('error', error.message);
        }
    }
}
```

---

## Security Considerations

### 1. Input Validation

**Always validate on the backend:**
- Amount ranges (min/max)
- Address formats
- Token symbols
- Slippage tolerance

**Never trust client-side validation alone.**

### 2. Rate Limiting

Implement rate limiting to prevent abuse:

```javascript
const rateLimit = require('express-rate-limit');

const limiter = rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 100 // limit each IP to 100 requests per windowMs
});

app.use('/api/otc/', limiter);
```

### 3. Quote Expiration

- Quotes should expire after 5-10 minutes
- Prevents stale pricing
- Protects against market volatility

### 4. Idempotency

Prevent duplicate swaps:

```javascript
// Check if swap with same quoteId already exists
const existingSwap = await getSwapByQuoteId(quoteId);
if (existingSwap) {
    return res.json({ ok: true, swap: existingSwap });
}
```

### 5. Transaction Monitoring

- Monitor all transactions for completion
- Implement retry logic for failed transactions
- Alert on unusual patterns

### 6. HTTPS Only

**Never** serve the frontend or API over HTTP in production.

---

## Testing

### Unit Tests

```javascript
// quote.test.js
const { getQuote } = require('./quote');

describe('getQuote', () => {
    test('returns valid quote for valid inputs', async () => {
        const result = await getQuote('RTC', 'wRTC', 100, 0.5);
        
        expect(result.ok).toBe(true);
        expect(result.quote).toBeDefined();
        expect(result.quote.fromAmount).toBe('100');
        expect(parseFloat(result.quote.toAmount)).toBeLessThan(100);
    });
    
    test('rejects invalid token symbols', async () => {
        const result = await getQuote('INVALID', 'wRTC', 100, 0.5);
        
        expect(result.ok).toBe(false);
        expect(result.error.code).toBe('INVALID_PARAMS');
    });
    
    test('rejects amounts below minimum', async () => {
        const result = await getQuote('RTC', 'wRTC', 0.5, 0.5);
        
        expect(result.ok).toBe(false);
        expect(result.error.code).toBe('AMOUNT_TOO_LOW');
    });
});
```

### Integration Tests

```javascript
// integration.test.js
const request = require('supertest');
const app = require('./app');

describe('OTC Bridge API', () => {
    describe('GET /api/otc/quote', () => {
        it('returns 200 for valid request', async () => {
            const response = await request(app)
                .get('/api/otc/quote')
                .query({ from: 'RTC', to: 'wRTC', amount: 100 });
            
            expect(response.status).toBe(200);
            expect(response.body.ok).toBe(true);
        });
    });
    
    describe('POST /api/otc/swap', () => {
        it('creates swap for valid request', async () => {
            // First get a quote
            const quoteResponse = await request(app)
                .get('/api/otc/quote')
                .query({ from: 'RTC', to: 'wRTC', amount: 100 });
            
            const quote = quoteResponse.body.quote;
            
            // Then create swap
            const swapResponse = await request(app)
                .post('/api/otc/swap')
                .send({
                    from: 'RTC',
                    to: 'wRTC',
                    fromAmount: '100',
                    toAddress: '7nx8QmzxD1wKX7QJ1FVqT5hX9YvJxKqZb8yPoR3dL8mN',
                    slippage: 0.5,
                    quoteId: quote.id
                });
            
            expect(swapResponse.status).toBe(200);
            expect(swapResponse.body.ok).toBe(true);
            expect(swapResponse.body.swap.id).toBeDefined();
        });
    });
});
```

---

## Support

For questions or issues:

- **GitHub Issues:** [Scottcjn/Rustchain](https://github.com/Scottcjn/Rustchain)
- **Email:** dev@rustchain.org
- **Discord:** [rustchain.org/discord](https://rustchain.org/discord)

---

<div align="center">

**Bounty #695 - OTC Bridge API Integration Guide**

*Version 1.0.0 - March 2026*

</div>
