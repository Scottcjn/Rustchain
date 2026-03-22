# Implementation Details — Issue #2308 Silicon Obituary

## Architecture Overview

The Silicon Obituary Generator is built with a modular architecture that separates concerns:

```
silicon_obituary.py    # Main orchestrator
├── miner_scanner.py   # Database scanning
├── eulogy_generator.py # Text generation
├── video_creator.py   # Video production
└── discord_notifier.py # Notifications
```

## Database Schema

The scanner queries these existing RustChain tables:

```sql
-- Recent attestation data
miner_attest_recent (
    miner TEXT PRIMARY KEY,
    ts_ok INTEGER NOT NULL,        -- Last successful attestation
    device_family TEXT,            -- Device model
    device_arch TEXT,              -- Architecture
    warthog_bonus REAL             -- Multiplier
)

-- Epoch enrollment history
epoch_enroll (
    epoch INTEGER,
    miner_pk TEXT,
    weight REAL,
    PRIMARY KEY (epoch, miner_pk)
)

-- Balance tracking
balances (
    miner_pk TEXT PRIMARY KEY,
    balance_rtc REAL DEFAULT 0
)
```

## Inactivity Detection Algorithm

```python
def find_inactive_miners():
    cutoff_ts = now() - (7 * 24 * 60 * 60)  # 7 days ago
    
    SELECT miner FROM miner_attest_recent
    WHERE ts_ok < cutoff_ts
    ORDER BY ts_ok ASC
    
    # For each inactive miner:
    # 1. Count epochs from epoch_enroll
    # 2. Get balance from balances table
    # 3. Calculate years of service
    # 4. Build MinerStatus object
```

## Eulogy Generation

### Template System

Eulogies use template-based generation with variable substitution:

```python
TEMPLATES = {
    "poetic": [
        "Here lies {device}, a {arch}. It attested for {epochs} epochs..."
    ],
    "technical": [
        "MINER OBITUARY: {device}\nArchitecture: {arch}..."
    ],
    # ...
}
```

### Variable Substitution

| Variable | Source |
|----------|--------|
| `{device}` | miner_attest_recent.device_family |
| `{arch}` | miner_attest_recent.device_arch |
| `{epochs}` | COUNT(epoch_enroll) |
| `{rtc}` | balances.balance_rtc |
| `{years}` | Calculated from first/last attestation |
| `{unique_feature}` | Architecture-specific feature |

## Video Generation

### Frame Composition

1. **Title Card** (90 frames @ 30fps = 3s)
   - "SILICON OBITUARY" title
   - Device name and architecture
   - Years of service

2. **Eulogy Scroll** (variable, ~6s minimum)
   - Word-wrapped text
   - Smooth scroll animation
   - Readable font size

3. **Memorial Card** (120 frames @ 30fps = 4s)
   - Stats display
   - Animated RTC counter

### Fallback Handling

When video libraries (PIL, moviepy) are unavailable:
- Creates JSON metadata file
- Creates minimal binary placeholder
- Logs warning but continues

## BoTTube Integration

### Post Structure

```python
{
    "title": "Silicon Obituary: Power Mac G4 MDD",
    "description": "<eulogy_text>",
    "tags": ["#SiliconObituary", "#RustChain", "#HardwareMemorial"],
    "video_file": "<path>",
    "thumbnail": "<arch_icon_url>"
}
```

### Video ID Generation

```python
video_id = sha256(miner_id + timestamp)[:12]
video_url = f"https://bottube.ai/video/{video_id}"
```

## Discord Notification

### Embed Structure

```json
{
    "title": "🪦 In Memoriam",
    "color": 0x663399,
    "fields": [
        {"name": "🖥️ Device", "value": "..."},
        {"name": "💰 RTC Earned", "value": "..."},
        {"name": "📜 Eulogy", "value": "..."},
        {"name": "🎬 Memorial Video", "value": "[Watch](url)"}
    ],
    "footer": {"text": "Miner ID: 0x..."},
    "timestamp": "ISO8601"
}
```

## Error Handling

### Graceful Degradation

| Component | Fallback |
|-----------|----------|
| Video creation | JSON placeholder |
| TTS | Silent audio |
| BoTTube post | Log URL, continue |
| Discord | Log message, continue |
| Database | Return empty list |

### Error Recovery

```python
try:
    result = generate_obituary(miner_id)
except Exception as e:
    logger.exception(f"Failed: {e}")
    return ObituaryResult(status="failed", error=str(e))
```

## Performance Considerations

### Rate Limiting

- 2 second delay between obituary generations
- Batch Discord notifications for multiple obituaries
- Database connections are properly closed

### Memory Management

- Frames generated on-demand
- No full video loaded into memory
- Streaming video write when possible

## Security

### Database Access

- Read-only queries for miner data
- Parameterized queries (no SQL injection)
- Connection context managers

### Webhook Handling

- Webhook URL from config/env only
- Never logged in full
- Timeout on requests (10s)

## Testing Strategy

### Unit Tests

- `TestMinerScanner` - Database queries
- `TestEulogyGenerator` - Text generation
- `TestVideoCreator` - Video creation
- `TestDiscordNotifier` - Notifications

### Integration Tests

- Full obituary flow
- Database → Eulogy → Video → Post

### Mocking

- Discord webhook (requests.post)
- BoTTube API
- File system operations

## Extensibility

### Adding New Eulogy Styles

```python
TEMPLATES["new_style"] = [
    "Template text with {variables}..."
]
```

### Adding New Video Elements

```python
def _create_new_element(self, data):
    frames = []
    # Create frames
    return frames
```

### Adding Notification Channels

```python
class SlackNotifier:
    def send_notification(self, ...):
        # Slack-specific implementation
```

## Monitoring

### Logging

```python
logger.info(f"Found {len(inactive)} inactive miner(s)")
logger.info(f"Eulogy generated ({len(eulogy_text)} chars)")
logger.info(f"Video created: {video_path}")
```

### Metrics (Future)

- Obituaries generated per day
- Average video duration
- Discord delivery rate
- BoTTube post success rate

## Future Enhancements

1. **LLM Integration** - Use actual LLM for more creative eulogies
2. **Real TTS** - Integrate Google TTS or AWS Polly
3. **Video Templates** - Multiple visual themes
4. **Hardware Images** - Auto-fetch device images
5. **Social Sharing** - Twitter/LinkedIn integration
6. **Memorial Page** - Web-based memorial gallery
