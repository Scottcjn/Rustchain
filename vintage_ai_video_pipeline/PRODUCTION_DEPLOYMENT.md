# Production Deployment Guide

> **Issue:** #1855 — Vintage AI Miner Videos  
> **Version:** 1.0.0  
> **Last Updated:** March 26, 2026

This guide covers deploying the Vintage AI Video Pipeline in production with real video generation backends.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Video Backend Setup](#video-backend-setup)
4. [Pipeline Configuration](#pipeline-configuration)
5. [Deployment Options](#deployment-options)
6. [Monitoring & Maintenance](#monitoring--maintenance)
7. [Troubleshooting](#troubleshooting)

---

## Overview

The pipeline consists of four main components:

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐
│ RustChain   │ -> │ Prompt       │ -> │ Video        │ -> │ BoTTube  │
│ API Client  │    │ Generator    │    │ Generator    │    │ Uploader │
└─────────────┘    └──────────────┘    └──────────────┘    └──────────┘
```

**Production Requirements:**
- RustChain API access (public: https://rustchain.org)
- Video generation backend (LTX-Video, CogVideo, or Mochi)
- BoTTube API key (for uploads)
- Python 3.8+ runtime

---

## Prerequisites

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16+ GB |
| Storage | 10 GB | 50+ GB SSD |
| GPU | Optional | NVIDIA with 8GB+ VRAM |
| Network | 10 Mbps | 100+ Mbps |

### Software Dependencies

```bash
# Python 3.8+
python3 --version

# Git (optional, for version control)
git --version

# systemd (optional, for service management)
systemctl --version
```

### Environment Variables

Create a `.env` file in the pipeline directory:

```bash
# RustChain API
export RUSTCHAIN_URL="https://rustchain.org"

# BoTTube API (required for uploads)
export BOTTUBE_API_KEY="your_api_key_here"
export BOTTUBE_URL="https://bottube.ai"

# Video Backend
export VIDEO_BACKEND="ltx-video"  # or cogvideo, mochi
export VIDEO_BACKEND_URL="http://localhost:8080"

# Pipeline Configuration
export PIPELINE_MODE="continuous"  # or once, demo
export POLL_INTERVAL="300"  # seconds
export MAX_VIDEOS_PER_RUN="10"
```

---

## Video Backend Setup

### Option 1: LTX-Video (Recommended)

LTX-Video is a high-quality open video generation model with good prompt adherence.

#### Installation

```bash
# Clone LTX-Video repository
git clone https://github.com/Lightricks/LTX-Video.git
cd LTX-Video

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# Download model weights
python scripts/download_model.py
```

#### Configuration

```bash
# Start LTX-Video API server
python api_server.py \
  --host 0.0.0.0 \
  --port 8080 \
  --model_path checkpoints/ltx-video.safetensors \
  --device cuda
```

#### Test Connection

```bash
curl -X POST http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A vintage computer mining cryptocurrency",
    "negative_prompt": "low quality, blurry",
    "duration": 5,
    "fps": 24,
    "resolution": "1280x720"
  }'
```

**Expected Response:**
```json
{
  "status": "processing",
  "job_id": "abc123",
  "estimated_time": 120
}
```

---

### Option 2: CogVideo

CogVideo offers fast generation with good quality for short clips.

#### Installation

```bash
# Clone CogVideo repository
git clone https://github.com/THUDM/CogVideo.git
cd CogVideo

# Install dependencies
pip install -r requirements.txt
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

#### Configuration

```bash
# Start CogVideo server
python server.py \
  --host 0.0.0.0 \
  --port 8000 \
  --model THUDM/CogVideoX-2b \
  --device cuda
```

#### Test Connection

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Vintage hardware mining blockchain",
    "num_frames": 120,
    "fps": 24,
    "width": 1280,
    "height": 720
  }'
```

---

### Option 3: Mochi

Mochi is a lightweight option suitable for CPU-only deployments.

#### Installation

```bash
# Install via pip
pip install mochi-video

# Or clone repository
git clone https://github.com/genmoai/mochi.git
cd mochi
pip install -e .
```

#### Configuration

```bash
# Start Mochi API
python -m mochi.api.server \
  --host 0.0.0.0 \
  --port 7860 \
  --model mochi-1
```

---

### Option 4: Cloud Hosting (Alternative)

If local GPU is not available, consider:

| Provider | Model | Cost | Notes |
|----------|-------|------|-------|
| RunPod | LTX-Video | ~$0.40/hr | GPU cloud |
| Vast.ai | CogVideo | ~$0.30/hr | Marketplace |
| Hugging Face Spaces | Mochi | Free tier | Limited compute |
| Replicate | Various | Pay-per-gen | API-based |

---

## Pipeline Configuration

### Step 1: Install Pipeline Dependencies

```bash
cd vintage_ai_video_pipeline

# The pipeline uses Python standard library only
# No additional dependencies required
python3 -c "import pipeline; print('OK')"
```

### Step 2: Configure Backend

Edit `video_generator.py` if you need to customize backend settings:

```python
BACKENDS = {
    "ltx-video": {
        "type": "http_api",
        "default_url": "http://localhost:8080",
        "endpoint": "/generate",
        "timeout": 300,
    },
    # ... other backends
}
```

### Step 3: Test Video Generation

```bash
# Test with demo mode first
python3 pipeline.py --mode demo --demo-count 3 --dry-run

# Test with real backend
python3 pipeline.py --mode once --max-videos 1 --backend ltx-video
```

### Step 4: Verify Output

Check generated videos and metadata:

```bash
ls -lh generated_videos/
cat generated_videos/*.meta.json | python3 -m json.tool
```

---

## Deployment Options

### Option A: Manual Execution

Run the pipeline manually or via cron:

```bash
# Single run (process current miners)
python3 pipeline.py --mode once --max-videos 10

# Continuous monitoring
python3 pipeline.py --mode continuous --poll-interval 300
```

### Option B: systemd Service (Recommended for Production)

Create `/etc/systemd/system/rustchain-video-pipeline.service`:

```ini
[Unit]
Description=RustChain Vintage AI Video Pipeline
After=network.target

[Service]
Type=simple
User=rustchain
WorkingDirectory=/opt/rustchain/vintage_ai_video_pipeline
Environment="RUSTCHAIN_URL=https://rustchain.org"
Environment="BOTTUBE_API_KEY=your_key"
Environment="VIDEO_BACKEND=ltx-video"
Environment="VIDEO_BACKEND_URL=http://localhost:8080"
ExecStart=/usr/bin/python3 /opt/rustchain/vintage_ai_video_pipeline/pipeline.py --mode continuous --poll-interval 300
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable rustchain-video-pipeline
sudo systemctl start rustchain-video-pipeline
sudo systemctl status rustchain-video-pipeline
```

### Option C: Docker Container

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . /app

ENV RUSTCHAIN_URL=https://rustchain.org
ENV VIDEO_BACKEND=ltx-video
ENV VIDEO_BACKEND_URL=http://host.docker.internal:8080

CMD ["python3", "pipeline.py", "--mode", "continuous", "--poll-interval", "300"]
```

**Build and run:**

```bash
docker build -t rustchain-video-pipeline .
docker run -d \
  --name video-pipeline \
  -e BOTTUBE_API_KEY=your_key \
  --add-host=host.docker.internal:host-gateway \
  rustchain-video-pipeline
```

---

## Monitoring & Maintenance

### Health Checks

```bash
# Check pipeline status
curl https://rustchain.org/health

# Check video backend
curl http://localhost:8080/health  # LTX-Video

# Check generated videos
ls -1 generated_videos/*.mp4 | wc -l
```

### Log Monitoring

The pipeline logs to stdout. Capture logs:

```bash
# systemd logs
journalctl -u rustchain-video-pipeline -f

# Or redirect to file
python3 pipeline.py --mode continuous 2>&1 | tee pipeline.log
```

### Metrics to Track

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Videos generated/day | 10-50 | <5 or >100 |
| Generation success rate | >95% | <90% |
| Upload success rate | >98% | <95% |
| API response time | <2s | >5s |
| Disk usage | <80% | >90% |

### Maintenance Tasks

**Daily:**
- Check logs for errors
- Verify disk space
- Monitor generation queue

**Weekly:**
- Review generated video quality
- Update backend if needed
- Check RustChain API changes

**Monthly:**
- Rotate logs
- Backup generated videos
- Review performance metrics

---

## Troubleshooting

### Issue: Video Generation Fails

**Symptoms:**
```
❌ Generation failed: Connection refused
```

**Solutions:**
1. Verify backend is running: `curl http://localhost:8080/health`
2. Check backend logs for errors
3. Ensure GPU memory is available
4. Verify firewall rules allow localhost access

### Issue: Low Quality Output

**Symptoms:**
- Blurry or distorted videos
- Poor prompt adherence

**Solutions:**
1. Increase `inference_steps` (default: 50) to 75-100
2. Adjust `guidance_scale` (default: 7.5) to 6.0-8.0
3. Improve prompt specificity in `prompt_generator.py`
4. Ensure backend model is properly loaded

### Issue: Upload Fails

**Symptoms:**
```
❌ Upload failed: 401 Unauthorized
```

**Solutions:**
1. Verify `BOTTUBE_API_KEY` is set correctly
2. Check API key has upload permissions
3. Ensure video file size is within limits
4. Validate metadata format matches spec

### Issue: Pipeline Crashes

**Symptoms:**
- Unexpected termination
- Python exceptions

**Solutions:**
1. Check system logs: `journalctl -xe`
2. Verify Python version: `python3 --version`
3. Ensure all dependencies are installed
4. Run with `--verbose` flag for detailed logs

### Issue: SSL/Certificate Errors

**Symptoms:**
```
SSL: CERTIFICATE_VERIFY_FAILED
```

**Solutions:**
1. Update CA certificates: `sudo update-ca-certificates`
2. Set `verify_ssl=False` in pipeline config (development only)
3. Check system time is synchronized

---

## Performance Tuning

### GPU Optimization

```bash
# Set CUDA environment variables
export CUDA_VISIBLE_DEVICES=0
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

# Enable TF32 for Ampere+ GPUs
export NVIDIA_TF32_OVERRIDE=1
```

### Batch Processing

For high-volume deployments, modify `pipeline.py` to batch miners:

```python
# Process miners in batches of 10
for i in range(0, len(miners), 10):
    batch = miners[i:i+10]
    results = pipeline.generate_batch(batch)
```

### Caching

Cache miner metadata to avoid redundant API calls:

```python
# Add to rustchain_client.py
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_miner_info(miner_id: str) -> Dict:
    return self._get(f"/api/miners/{miner_id}")
```

---

## Security Considerations

### API Key Management

- Store API keys in environment variables, not code
- Use secrets management (HashiCorp Vault, AWS Secrets Manager)
- Rotate keys periodically
- Limit API key permissions to minimum required

### Network Security

- Use HTTPS for all external API calls
- Firewall video backend to localhost only
- Implement rate limiting on API endpoints
- Monitor for unusual traffic patterns

### Data Privacy

- Do not log sensitive miner wallet addresses
- Anonymize metrics before sharing
- Comply with data retention policies
- Secure backup storage

---

## Support & Resources

### Documentation

- [README.md](README.md) - Pipeline overview
- [ISSUE_1855_PROGRESS.md](../ISSUE_1855_PROGRESS.md) - Implementation details
- Backend docs: LTX-Video, CogVideo, Mochi repositories

### Community

- RustChain Discord: [invite link]
- GitHub Issues: [Scottcjn/Rustchain/issues](https://github.com/Scottcjn/Rustchain/issues)
- BoTTube API docs: [bottube.ai/api/docs](https://bottube.ai/api/docs)

### Reporting Issues

When reporting issues, include:

1. Pipeline version
2. Backend and version
3. Error messages (full traceback)
4. Steps to reproduce
5. Expected vs actual behavior

---

## Appendix: Configuration Reference

### Full Environment Variable List

```bash
# RustChain
RUSTCHAIN_URL=https://rustchain.org

# BoTTube
BOTTUBE_API_KEY=your_key
BOTTUBE_URL=https://bottube.ai

# Video Backend
VIDEO_BACKEND=ltx-video  # ltx-video, cogvideo, mochi, demo
VIDEO_BACKEND_URL=http://localhost:8080
VIDEO_OUTPUT_DIR=./generated_videos

# Pipeline
PIPELINE_MODE=continuous  # continuous, once, demo
POLL_INTERVAL=300  # seconds
MAX_VIDEOS_PER_RUN=10
DRY_RUN=false
VERBOSE=true

# Advanced
VERIFY_SSL=true
TIMEOUT=30
RETRY_COUNT=3
RETRY_DELAY=1.0
```

### Backend Comparison

| Backend | Quality | Speed | VRAM | Ease |
|---------|---------|-------|------|------|
| LTX-Video | High | Medium | 12GB | Medium |
| CogVideo | Medium-High | Fast | 8GB | Easy |
| Mochi | Medium | Slow | 6GB | Easy |
| Demo | N/A | Instant | 0GB | Trivial |

---

*Production Deployment Guide v1.0.0 — March 26, 2026*
