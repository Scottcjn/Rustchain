# RustChain × BoTTube Mining Video Pipeline

Automated pipeline that monitors RustChain miner attestations, generates animated mining visualization videos, and publishes them to BoTTube.

## Architecture

```
RustChain API (/api/miners, /epoch)
        │
        ▼
┌─────────────────┐
│  Event Listener  │  ← Polls miners + epoch data
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Prompt Generator │  ← Maps miner metadata to visual style
│  - Device arch   │
│  - Hardware type │
│  - Multiplier    │
│  - Epoch stats   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Video Generator │  ← PIL frame rendering + ffmpeg encoding
│  - Per-arch style│
│  - Stats overlay │
│  - Hash stream   │
│  - Particles     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  BoTTube Upload  │  ← Playwright browser automation
│  - Title/desc    │
│  - Tags          │
│  - Category      │
└─────────────────┘
```

## Setup

```bash
# Install dependencies
pip install requests pillow playwright
playwright install chromium

# Set BoTTube auth (export cookies from browser)
# Save to: /root/.openclaw/workspace/auth/bottube_state.json

# Run pipeline
python mining_video_pipeline.py --full --count 10
```

## Usage

```bash
# List active miners
python mining_video_pipeline.py --list

# Generate videos from live data
python mining_video_pipeline.py --generate --count 10

# Upload generated videos
python mining_video_pipeline.py --upload

# Full pipeline
python mining_video_pipeline.py --full --count 10

# Generate for specific miner
python mining_video_pipeline.py --miner "power8-s824-sophia"
```

## Video Features

### Architecture-Specific Visual Styles

| Hardware Type | Color Theme | Device Icon |
|--------------|-------------|-------------|
| PowerPC (Vintage) | Bronze/Gold | Server rack with blinking LEDs |
| Apple Silicon | Silver/Blue | Chip with pulse effect |
| x86-64 (Modern) | Green/Neon | CPU with pins |
| Unknown/Other | Purple/Violet | Generic device |

### On-Screen Stats Overlay

Every video includes real-time mining data:
- Miner ID and architecture
- Hardware type and antiquity multiplier
- Current epoch, slot, and epoch pot
- Total RTC supply
- Last attestation timestamp

### Visual Effects

- Floating particle system (per-architecture color)
- Animated hash stream visualization
- Progress bars for attestation flow
- Device icon animation (bobbing, pulsing, LED blinking)
- Glow effects on branding text

## Demo Videos

12 videos generated and uploaded to BoTTube across 4 architecture types:

### PowerPC (Vintage)
- https://bottube.ai/watch/9L4kkzKy-G9

### Apple Silicon
- https://bottube.ai/watch/FFFKydmQ-xt
- https://bottube.ai/watch/_5-9mdTJC-d

### x86-64 (Modern)
- https://bottube.ai/watch/W9NecljXVat
- https://bottube.ai/watch/rbhkUDVQxk4
- https://bottube.ai/watch/Xx1JtmMwfec
- https://bottube.ai/watch/cxgqL7veOUw
- https://bottube.ai/watch/ZeVIhTrWmq4
- https://bottube.ai/watch/47asNJEK4pZ

### Unknown/Other
- https://bottube.ai/watch/Xv0KHKqlXtH
- https://bottube.ai/watch/DTxm-SFZ5ZZ
- https://bottube.ai/watch/jDc_6tz4Cwq

## Technical Details

- **Video backend**: PIL (Python Imaging Library) frame-by-frame rendering → ffmpeg H.264 encoding
- **Resolution**: 1280×720 (720p)
- **Duration**: 8 seconds per video
- **Frame rate**: 15 FPS
- **File size**: ~240-280 KB per video
- **Upload**: Playwright browser automation with cookie-based auth

## Configuration

Edit constants at the top of `mining_video_pipeline.py`:

```python
RUSTCHAIN_API = "https://50.28.86.131"
BOTTUBE_AUTH_FILE = "/path/to/auth/bottube_state.json"
OUTPUT_DIR = "/tmp/rustchain_videos"
WIDTH, HEIGHT = 1280, 720
FPS = 15
```

## Dependencies

- Python 3.10+
- `requests` — API calls
- `Pillow` — Image generation
- `playwright` — Browser automation for BoTTube upload
- `ffmpeg` — Video encoding (system package)
