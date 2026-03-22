# Silicon Obituary Generator — Issue #2308 Implementation

> "We don't just mine with machines — we honor them. Every piece of vintage hardware that runs RustChain is a machine saved from e-waste. When it finally dies, it deserves a send-off."

## Overview

The Silicon Obituary Generator automatically detects retired miners (7+ days inactive), generates poetic eulogies with real statistics, creates memorial videos, and posts them to BoTTube with Discord notifications.

## Features

| Feature | Description |
|---------|-------------|
| **Inactive Detection** | Scans database for miners inactive 7+ days |
| **Eulogy Generation** | Creates poetic text with real miner stats |
| **Video Creation** | Generates memorial videos with TTS, music, animations |
| **BoTTube Integration** | Auto-posts with #SiliconObituary tag |
| **Discord Notifications** | Sends rich embed notifications |
| **Multiple Styles** | Poetic, Technical, Humorous, Epic |

## Installation

### Prerequisites

```bash
# Python 3.8+
python3 --version

# Install dependencies
pip install requests pillow numpy
```

### Optional Dependencies (for full video generation)

```bash
pip install moviepy
```

## Usage

### Quick Start

```bash
# Navigate to the implementation directory
cd bounties/issue-2308

# Scan for inactive miners
python3 src/silicon_obituary.py --scan

# Generate obituary for specific miner
python3 src/silicon_obituary.py --generate 0x1234...abcd

# Generate obituaries for all inactive miners
python3 src/silicon_obituary.py --generate-all

# Run in daemon mode (checks hourly)
python3 src/silicon_obituary.py --daemon --discord-webhook https://discord.com/...
```

### CLI Options

```
--scan              Scan for inactive miners (7+ days)
--generate MINER    Generate obituary for specific miner ID
--generate-all      Generate for all inactive miners
--daemon            Run continuously, checking every hour
--db-path PATH      Database path (default: ~/.rustchain/rustchain.db)
--inactive-days N   Days of inactivity threshold (default: 7)
--output-dir PATH   Output directory for videos
--discord-webhook   Discord webhook URL for notifications
--dry-run           Simulate without creating/posting
--verbose, -v       Verbose output
```

### Examples

```bash
# Dry run to test without posting
python3 src/silicon_obituary.py --generate-all --dry-run

# Custom database and output
python3 src/silicon_obituary.py \
    --db-path /path/to/rustchain.db \
    --output-dir /path/to/videos \
    --generate-all

# With Discord notifications
python3 src/silicon_obituary.py \
    --discord-webhook https://discord.com/api/webhooks/... \
    --generate 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Silicon Obituary Generator                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Miner      │    │   Eulogy     │    │   Video      │      │
│  │   Scanner    │───►│   Generator  │───►│   Creator    │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         │                   │                   │               │
│         ▼                   │                   ▼               │
│  ┌──────────────┐           │          ┌──────────────┐        │
│  │  SQLite DB   │           │          │   BoTTube    │        │
│  │  (miners)    │           │          │   Platform   │        │
│  └──────────────┘           │          └──────────────┘        │
│                             │                   │               │
│                             ▼                   ▼               │
│                      ┌──────────────┐    ┌──────────────┐      │
│                      │   Discord    │    │   Report     │      │
│                      │   Notifier   │    │   Generator  │      │
│                      └──────────────┘    └──────────────┘      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Miner Scanner (`miner_scanner.py`)

Detects inactive miners by querying the RustChain database.

```python
from miner_scanner import MinerScanner

scanner = MinerScanner(db_path="~/.rustchain/rustchain.db", inactive_days=7)
inactive_miners = scanner.find_inactive_miners()

for miner in inactive_miners:
    print(f"{miner.miner_id}: {miner.days_inactive} days inactive")
    print(f"  Device: {miner.device_model}")
    print(f"  Epochs: {miner.total_epochs}")
    print(f"  RTC Earned: {miner.total_rtc_earned}")
```

### 2. Eulogy Generator (`eulogy_generator.py`)

Generates poetic eulogies with real miner statistics.

```python
from eulogy_generator import EulogyGenerator, EulogyData

data = EulogyData(
    miner_id="0x123...",
    device_model="Power Mac G4 MDD",
    device_arch="PowerPC G4",
    total_epochs=847,
    total_rtc_earned=412.5,
    days_inactive=14,
    years_of_service=2.3,
    first_attestation="2024-01-15T08:30:00",
    last_attestation="2026-03-08T14:22:00",
    multiplier_history=[1.5, 1.5, 1.5]
)

generator = EulogyGenerator(style="poetic")
eulogy = generator.generate(data)
print(eulogy)
```

**Available Styles:**
- `poetic` - Lyrical and emotional
- `technical` - Focus on specs and achievements
- `humorous` - Light-hearted send-off
- `epic` - Grand heroic narrative
- `random` - Random style selection

### 3. Video Creator (`video_creator.py`)

Creates memorial videos with visuals, TTS, and music.

```python
from video_creator import BoTTubeVideoCreator, VideoConfig

config = VideoConfig(
    output_dir="./output",
    tts_voice="default",
    background_music="./music/solemn.mp3"
)

creator = BoTTubeVideoCreator(config)
result = creator.create_memorial_video(
    miner_id="0x123...",
    eulogy_text="Here lies...",
    miner_data={...}
)

print(f"Video: {result.video_path}")
print(f"Duration: {result.duration_seconds}s")
```

### 4. Discord Notifier (`discord_notifier.py`)

Sends rich embed notifications to Discord.

```python
from discord_notifier import DiscordNotifier

notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/...")

result = notifier.send_obituary_notification(
    miner_id="0x123...",
    miner_data={...},
    eulogy_text="Here lies...",
    video_url="https://bottube.ai/video/..."
)

print(f"Sent: {result.success}")
```

## Example Output

### Eulogy Example (Poetic Style)

```
Here lies dual-g4-125, a Power Mac G4 MDD. It attested for 847 epochs 
and earned 412.50 RTC. Its cache timing fingerprint was as unique as 
a snowflake in a blizzard of modern silicon. It served faithfully for 
2.3 years, from 2024-01-15 to 2026-03-08. It is survived by its power 
supply, which still works.
```

### Eulogy Example (Technical Style)

```
MINER OBITUARY: Power Mac G4 MDD
Architecture: PowerPC G4
Service Period: 2.3 years (2024-01-15 to 2026-03-08)
Total Attestations: 847 epochs
RTC Mined: 412.50
Average Multiplier: 1.50x
Status: Retired (inactive 14 days)
Cause: Hardware retirement
```

### Discord Notification

```
🕯️ Silicon Obituary 🎗️

In Memoriam ⚰️
A faithful miner has completed its final attestation.

🖥️ Device
Power Mac G4 MDD
PowerPC G4

⏱️ Service    Epochs
2.3 years     847

💰 RTC Earned
412.50 RTC

📜 Eulogy
Here lies dual-g4-125, a Power Mac G4 MDD...

🎬 Memorial Video
[Watch on BoTTube](https://bottube.ai/video/abc123)
```

## Testing

```bash
# Run all tests
cd bounties/issue-2308
python3 -m pytest tests/test_silicon_obituary.py -v

# Run specific test class
python3 -m pytest tests/test_silicon_obituary.py::TestEulogyGenerator -v

# Run with coverage
python3 -m pytest tests/ --cov=src --cov-report=html
```

## Configuration

### Environment Variables

```bash
# Database path
export RUSTCHAIN_DB_PATH=~/.rustchain/rustchain.db

# Discord webhook
export DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Output directory
export OBITUARY_OUTPUT_DIR=./output

# Inactivity threshold (days)
export INACTIVE_DAYS=7
```

### Config File

Create `config.json`:

```json
{
    "db_path": "~/.rustchain/rustchain.db",
    "inactive_days": 7,
    "output_dir": "./output",
    "discord_webhook": "https://discord.com/api/webhooks/...",
    "tts_voice": "default",
    "background_music": "./music/solemn.mp3",
    "eulogy_style": "poetic"
}
```

## Video Elements

The memorial video includes:

1. **Title Card** - Device name, architecture, service years
2. **Scrolling Eulogy** - Text narration with scroll effect
3. **RTC Counter Animation** - Animated counter showing total earned
4. **Memorial Card** - Final stats summary
5. **Background Music** - Optional solemn music
6. **TTS Narration** - Text-to-speech eulogy reading

## BoTTube Integration

Videos are posted with:
- Title: "Silicon Obituary: [Device Name]"
- Description: Full eulogy text
- Tags: `#SiliconObituary`, `#RustChain`, `#HardwareMemorial`
- Thumbnail: Architecture-specific icon

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| Detect miners inactive 7+ days | ✅ |
| Query historical data from database | ✅ |
| Generate eulogy with real statistics | ✅ |
| Create BoTTube video with all elements | ✅ |
| Auto-post with #SiliconObituary tag | ✅ |
| Send Discord notification | ✅ |

## Troubleshooting

### Database Not Found

```
Error: Database not found: ~/.rustchain/rustchain.db
```

**Solution:** Specify correct path with `--db-path`

### PIL/Pillow Not Available

```
Warning: PIL not available, creating placeholder video file
```

**Solution:** Install Pillow: `pip install pillow`

### Discord Webhook Failed

```
Error: Discord webhook error: 403
```

**Solution:** Check webhook URL permissions

## License

Same as RustChain project license.

## Credits

- Issue #2308 by Scottcjn
- Implementation for RustChain bounty program
- Inspired by vintage hardware preservation
