# GPU Render Payment Protocol

Decentralized GPU rendering payment layer for RustChain.

## Features

### GPU Node Attestation
- Register GPU nodes with hardware specs
- Track VRAM, CUDA/ROCm versions, benchmark scores
- Support multiple job types: render, tts, stt, llm

### Payment Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/gpu/attest` | POST | Register GPU node |
| `/api/gpu/nodes` | GET | List available GPUs |
| `/render/escrow` | POST | Lock RTC for render job |
| `/render/release` | POST | Release to GPU on completion |
| `/render/refund` | POST | Refund if job fails |
| `/voice/escrow` | POST | Lock RTC for TTS/STT |
| `/voice/release` | POST | Release on audio delivery |
| `/llm/escrow` | POST | Lock RTC for LLM inference |
| `/llm/release` | POST | Release on completion |
| `/api/pricing/current` | GET | Fair market rates |

## Usage

```bash
# Run the server
python3 payment_protocol.py

# Register a GPU node
curl -X POST http://localhost:8099/api/gpu/attest \
  -H "Content-Type: application/json" \
  -d '{
    "miner_pubkey": "RTC...",
    "gpu_model": "RTX 4090",
    "vram_gb": 24,
    "cuda_version": "12.2",
    "benchmark_score": 15000,
    "job_types": ["render", "tts"]
  }'

# Lock escrow for render job
curl -X POST http://localhost:8099/render/escrow \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "render-123",
    "from_wallet": "bot-wallet",
    "to_wallet": "gpu-node-wallet",
    "amount": 10.0
  }'
```

## Database

Creates tables:
- `gpu_nodes` - Registered GPU nodes
- `escrow` - Payment escrow state
- `pricing_history` - Historical pricing data
