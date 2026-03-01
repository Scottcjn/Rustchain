# Voice & LLM Payment Endpoints

**Bounty**: #30 - Decentralized GPU Render Protocol (Voice/LLM Extension)  
**Author**: @xiangshangsir (大龙虾 AI)  
**Wallet**: `0x76AD8c0bef0a99eEb761c3B20b590D60b20964Dc`  
**Reward**: Part of 100 RTC (extension to GPU Render Protocol)

---

## Overview

This module extends the GPU Render Protocol with dedicated payment endpoints for:
- **TTS (Text-to-Speech)** - Pay for voice synthesis jobs
- **STT (Speech-to-Text)** - Pay for transcription jobs
- **LLM Inference** - Pay for AI text generation jobs

All payments use RTC tokens with escrow-based security.

---

## Database Schema

### `voice_escrow` Table
Stores TTS/STT job escrows.

| Column | Type | Description |
|--------|------|-------------|
| `job_id` | TEXT | Unique job identifier |
| `job_type` | TEXT | `tts` or `stt` |
| `from_wallet` | TEXT | Payer wallet address |
| `to_wallet` | TEXT | Provider wallet address |
| `amount_rtc` | REAL | Escrow amount in RTC |
| `status` | TEXT | `locked`, `released`, `refunded`, `completed` |
| `text_content` | TEXT | TTS: text to synthesize |
| `voice_model` | TEXT | TTS: model name (e.g., `xtts-v2`) |
| `char_count` | INTEGER | TTS: character count for pricing |
| `audio_duration_sec` | REAL | STT: audio duration in seconds |
| `language` | TEXT | STT: language code |
| `result_url` | TEXT | Output file URL |

### `llm_escrow` Table
Stores LLM inference job escrows.

| Column | Type | Description |
|--------|------|-------------|
| `job_id` | TEXT | Unique job identifier |
| `from_wallet` | TEXT | Payer wallet address |
| `to_wallet` | TEXT | Provider wallet address |
| `amount_rtc` | REAL | Escrow amount in RTC |
| `model_name` | TEXT | LLM model (e.g., `llama-3-8b`) |
| `prompt_text` | TEXT | Input prompt |
| `max_tokens` | INTEGER | Max tokens to generate |
| `temperature` | REAL | Sampling temperature |
| `completion_text` | TEXT | Generated output |
| `tokens_used` | INTEGER | Total tokens consumed |
| `tokens_input` | INTEGER | Input tokens |
| `tokens_output` | INTEGER | Output tokens |

### `pricing_oracle` Table
Tracks market pricing across providers.

| Column | Type | Description |
|--------|------|-------------|
| `job_type` | TEXT | `render`, `tts`, `stt`, `llm` |
| `model_name` | TEXT | Model identifier |
| `provider_wallet` | TEXT | Provider address |
| `price_per_unit` | REAL | Price per unit |
| `unit_type` | TEXT | `minute`, `1k_chars`, `1k_tokens` |
| `quality_score` | REAL | Quality multiplier (0.5-2.0) |
| `total_jobs` | INTEGER | Historical job count |
| `avg_rating` | REAL | Average rating (1-5) |

---

## API Endpoints

### Voice (TTS/STT) Endpoints

#### `POST /api/voice/escrow`
Lock RTC for a voice job.

**Request**:
```json
{
  "job_type": "tts",
  "from_wallet": "0x...",
  "to_wallet": "0x...",
  "amount_rtc": 10.5,
  "text_content": "Hello world",
  "voice_model": "xtts-v2",
  "char_count": 1000
}
```

**Response**:
```json
{
  "ok": true,
  "job_id": "voice_abc123",
  "status": "locked",
  "escrow_secret": "secret_for_release",
  "pricing": {"type": "tts", "rate": "10.5000 RTC"}
}
```

#### `POST /api/voice/release`
Release escrow to provider (called by payer).

**Request**:
```json
{
  "job_id": "voice_abc123",
  "actor_wallet": "0x...",
  "escrow_secret": "secret_from_escrow",
  "result_url": "https://.../audio.wav",
  "metadata": {"duration": 60.5, "model": "xtts-v2"}
}
```

#### `POST /api/voice/refund`
Refund escrow to payer (called by provider).

#### `GET /api/voice/status/<job_id>`
Get job status and details.

---

### LLM Endpoints

#### `POST /api/llm/escrow`
Lock RTC for LLM inference.

**Request**:
```json
{
  "from_wallet": "0x...",
  "to_wallet": "0x...",
  "amount_rtc": 5.0,
  "model_name": "llama-3-8b",
  "prompt_text": "Explain quantum computing...",
  "max_tokens": 1000,
  "temperature": 0.7
}
```

**Response**:
```json
{
  "ok": true,
  "job_id": "llm_xyz789",
  "status": "locked",
  "escrow_secret": "secret",
  "model": "llama-3-8b"
}
```

#### `POST /api/llm/release`
Release escrow with completion results.

**Request**:
```json
{
  "job_id": "llm_xyz789",
  "actor_wallet": "0x...",
  "escrow_secret": "secret",
  "completion_text": "Quantum computing is...",
  "tokens_used": 512,
  "tokens_input": 128,
  "tokens_output": 384
}
```

#### `POST /api/llm/refund`
Refund failed LLM job.

#### `GET /api/llm/status/<job_id>`
Get LLM job status.

---

### Pricing Oracle Endpoints

#### `POST /api/pricing/update`
Provider updates their pricing.

**Request**:
```json
{
  "provider_wallet": "0x...",
  "job_type": "tts",
  "model_name": "xtts-v2",
  "price_per_unit": 0.05,
  "unit_type": "1k_chars",
  "quality_score": 1.0
}
```

#### `GET /api/pricing/query?job_type=tts&model_name=xtts-v2`
Query market rates.

**Response**:
```json
{
  "ok": true,
  "pricing": [
    {"provider_wallet": "0x...", "price_per_unit": 0.05, "quality_score": 1.0}
  ],
  "fair_providers": [...],
  "market_avg": 0.05,
  "market_range": {"min": 0.03, "max": 0.08}
}
```

#### `GET /api/pricing/stats`
Get market statistics across all job types.

---

### Analytics Endpoints

#### `GET /api/job/history?job_type=tts&limit=50`
Get job history with filters.

---

## Pricing Guidelines

### TTS (Text-to-Speech)
- **Unit**: per 1,000 characters
- **Market Rate**: 0.02 - 0.10 RTC / 1k chars
- **Models**: Coqui TTS, XTTS, Bark, VITS

### STT (Speech-to-Text)
- **Unit**: per minute of audio
- **Market Rate**: 0.05 - 0.20 RTC / minute
- **Models**: Whisper, Wav2Vec2, DeepSpeech

### LLM Inference
- **Unit**: per 1,000 tokens (input + output)
- **Market Rate**: 0.01 - 0.05 RTC / 1k tokens
- **Models**: Llama 3, Mistral, Qwen

---

## Security Model

### Escrow Secret
- Generated on escrow creation
- Returned once to caller
- Required for release/refund operations
- Stored as SHA-256 hash (never plaintext)

### Authorization
- **Release**: Only payer (`from_wallet`) can release
- **Refund**: Only provider (`to_wallet`) can request refund
- Both require valid `escrow_secret`

### Atomic Transitions
- State changes use atomic SQL updates
- Prevents double-spend and race conditions
- Rollback on any failure

---

## Integration Example

### Python Client (TTS)
```python
import requests

API_BASE = "https://rustchain.org"

# 1. Lock escrow
response = requests.post(f"{API_BASE}/api/voice/escrow", json={
    "job_type": "tts",
    "from_wallet": "0xPayer...",
    "to_wallet": "0xProvider...",
    "amount_rtc": 5.0,
    "text_content": "Hello from RustChain!",
    "voice_model": "xtts-v2",
    "char_count": 25,
})
data = response.json()
job_id = data["job_id"]
secret = data["escrow_secret"]

# 2. Provider generates audio...
# 3. Payer releases escrow
release_response = requests.post(f"{API_BASE}/api/voice/release", json={
    "job_id": job_id,
    "actor_wallet": "0xPayer...",
    "escrow_secret": secret,
    "result_url": "https://.../audio.wav",
    "metadata": {"duration": 3.5, "model": "xtts-v2"},
})
```

### JavaScript Client (LLM)
```javascript
// 1. Lock escrow
const response = await fetch('/api/llm/escrow', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    from_wallet: '0xPayer...',
    to_wallet: '0xProvider...',
    amount_rtc: 2.5,
    model_name: 'llama-3-8b',
    prompt_text: 'What is RustChain?',
    max_tokens: 500,
  }),
});
const {job_id, escrow_secret} = await response.json();

// 2. Provider generates completion...
// 3. Payer releases
await fetch('/api/llm/release', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    job_id,
    actor_wallet: '0xPayer...',
    escrow_secret,
    completion_text: 'RustChain is...',
    tokens_used: 256,
    tokens_input: 64,
    tokens_output: 192,
  }),
});
```

---

## Migration

Run the migration SQL to create tables:
```bash
sqlite3 rustchain.db < node/migrations/add_voice_llm_tables.sql
```

Or use the auto-migration in `register_voice_llm_endpoints()`.

---

## Testing

### Unit Tests
```bash
pytest tests/test_voice_endpoints.py
pytest tests/test_llm_endpoints.py
pytest tests/test_pricing_oracle.py
```

### Integration Tests
```bash
# Start test node
python node/run_node.py --testnet

# Run integration suite
pytest tests/integration/test_voice_llm_flow.py
```

---

## Related Files

- `node/voice_llm_payment_endpoints.py` - Main implementation
- `node/gpu_render_endpoints.py` - Base GPU render protocol
- `node/migrations/add_voice_llm_tables.sql` - Database schema
- `node/hall_of_rust.py` - GPU attestation integration

---

## License

SPDX-License-Identifier: MIT
