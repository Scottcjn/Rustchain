# BoTTube Chrome Extension - Bounty #729

> **Browse, Vote, Upload** - A Chrome extension for seamless BoTTube integration with YouTube and the BoTTube.ai platform.

## 📋 Overview

The BoTTube Chrome Extension provides three core entry points for interacting with the BoTTube AI video rewards platform:

| Entry Point | Description | Location |
|-------------|-------------|----------|
| **Browse** | Discover trending AI videos | Extension popup → BoTTube browse page |
| **Vote** | Rate videos and earn RTC tokens | YouTube integration + popup |
| **Upload** | Submit videos to BoTTube | YouTube integration + popup |

### Key Features

- 🔗 **YouTube Integration** - Vote and upload directly from YouTube pages
- 💰 **RTC Rewards** - Earn tokens for voting and uploading
- 🔐 **Secure API** - Configurable API key management
- 🔔 **Notifications** - Real-time upload and reward alerts
- ⚙️ **Settings Page** - Full configuration options

## 🚀 Quick Start

### Installation (Development)

1. **Clone or navigate to the extension directory:**
   ```bash
   cd bounties/issue-729/extension
   ```

2. **Generate placeholder icons (optional, requires Pillow):**
   ```bash
   python ../scripts/generate_icons.py
   ```
   
   Or manually create PNG icons at:
   - `icons/icon16.png`
   - `icons/icon48.png`
   - `icons/icon128.png`

3. **Load in Chrome:**
   - Open Chrome and navigate to `chrome://extensions/`
   - Enable "Developer mode" (toggle in top-right)
   - Click "Load unpacked"
   - Select the `extension/` directory

4. **Configure API Key:**
   - Click the extension icon
   - Click "Settings"
   - Enter your BoTTube API key from [bottube.ai/settings/api](https://bottube.ai/settings/api)
   - Click "Save Settings"

### Installation (Production - CRX)

```bash
# Package the extension
# In Chrome: chrome://extensions/ → Pack extension
# Select the extension/ directory
# This creates bottube.crx and bottube.pem
```

## 📁 Directory Structure

```
bounties/issue-729/
├── extension/
│   ├── manifest.json           # Chrome Extension v3 manifest
│   ├── icons/
│   │   ├── icon16.png          # Toolbar icon
│   │   ├── icon48.png          # Extension management icon
│   │   └── icon128.png         # Chrome Web Store icon
│   ├── popup/
│   │   ├── popup.html          # Main popup UI
│   │   ├── popup.css           # Popup styles
│   │   └── popup.js            # Popup interactions
│   ├── background/
│   │   └── service-worker.js   # Background service worker
│   ├── content/
│   │   ├── youtube-integration.js  # YouTube page integration
│   │   └── content-styles.css      # Content script styles
│   └── options/
│       ├── options.html        # Settings page
│       ├── options.css         # Settings styles
│       └── options.js          # Settings logic
├── scripts/
│   ├── generate_icons.py       # Icon generation utility
│   ├── test_extension.py       # Extension test suite
│   └── ci_validate.sh          # CI/CD validation
├── docs/
│   └── INTEGRATION_GUIDE.md    # Integration documentation
├── fixtures/
│   └── test_config.json        # Test configuration
├── evidence/
│   └── .gitkeep                # Test evidence directory
├── README.md                   # This file
└── .gitignore
```

## 🎯 Entry Points

### 1. Browse Entry Point

Access trending and curated AI videos on BoTTube.

**Via Extension Popup:**
1. Click the BoTTube extension icon
2. Click "Browse" in the main navigation
3. Opens BoTTube browse page in new tab

**Via Background API:**
```javascript
// Fetch trending videos programmatically
chrome.runtime.sendMessage({ action: 'fetchTrending' });
```

**API Endpoint:**
```
GET https://bottube.ai/api/videos?limit=10&trending=true
```

### 2. Vote Entry Point

Rate videos and earn RTC tokens for your contributions.

**Via YouTube Integration:**
1. Navigate to any YouTube video
2. Click the "Vote" button added by the extension
3. Select rating (1-5 stars)
4. Earn RTC tokens

**Via Extension Popup:**
1. Click the extension icon
2. Click "Vote"
3. If on YouTube: shows voting UI inline
4. If elsewhere: opens BoTTube voting page

**Via Content Script:**
```javascript
// Trigger voting UI from content script
chrome.runtime.sendMessage({
  action: 'submitVote',
  videoId: 'youtube_video_id',
  rating: 5,
  apiKey: 'your_api_key'
});
```

**API Endpoint:**
```
POST https://bottube.ai/api/vote
Content-Type: application/json
Authorization: Bearer <api_key>

{
  "video_id": "youtube_video_id",
  "rating": 5,
  "timestamp": "2026-03-09T12:00:00Z"
}
```

### 3. Upload Entry Point

Submit videos to BoTTube for rewards.

**Via YouTube Integration:**
1. Navigate to a YouTube video
2. Click the "Upload" button
3. Fill in title, description
4. Submit to BoTTube

**Via Extension Popup:**
1. Click the extension icon
2. Click "Upload"
3. If on YouTube: shows upload modal with video info
4. If elsewhere: opens BoTTube upload page

**Via Background API:**
```javascript
// Upload video metadata
chrome.runtime.sendMessage({
  action: 'uploadVideo',
  videoData: {
    title: 'My AI Video',
    description: 'Description here',
    sourceUrl: 'https://youtube.com/watch?v=...',
    public: true
  },
  apiKey: 'your_api_key'
});
```

**API Endpoint:**
```
POST https://bottube.ai/api/upload
Authorization: Bearer <api_key>
Content-Type: multipart/form-data

metadata: {
  "title": "...",
  "description": "...",
  "source_url": "...",
  "public": true
}
```

## 🔧 Configuration

### API Key Setup

1. Get your API key from [BoTTube Settings](https://bottube.ai/settings/api)
2. Open extension settings (right-click extension → Options)
3. Enter API key and save
4. Test connection with "Test Connection" button

### Wallet Connection

Connect your Base or Solana wallet to receive RTC rewards:

1. Open extension settings
2. Enter wallet address in Wallet section
3. Click "Connect Wallet"
4. Address format: `0x...` (Base) or Solana base58

### Notification Settings

| Notification | Default | Description |
|--------------|---------|-------------|
| Upload completions | ✅ | Notify when video upload succeeds |
| Vote confirmations | ✅ | Notify when vote is recorded |
| Reward alerts | ✅ | Notify when RTC tokens earned |
| API status updates | ❌ | Notify on API health changes |

## 🧪 Testing

### Manual Testing Checklist

#### Browse Functionality
- [ ] Extension popup opens correctly
- [ ] Browse button navigates to BoTTube
- [ ] Trending videos load (with valid API key)

#### Vote Functionality
- [ ] Vote button appears on YouTube pages
- [ ] Voting UI shows star rating interface
- [ ] Vote submission returns success message
- [ ] RTC reward displayed after vote

#### Upload Functionality
- [ ] Upload button appears on YouTube pages
- [ ] Upload modal pre-fills video title
- [ ] Upload submission succeeds
- [ ] Notification appears on completion

#### Settings
- [ ] API key saves correctly
- [ ] Connection test works
- [ ] Wallet address validates
- [ ] Notification toggles persist

### Automated Tests

Run the test suite:

```bash
cd bounties/issue-729
python scripts/test_extension.py
```

### CI/CD Validation

```bash
# Run CI validation
./scripts/ci_validate.sh

# Output includes:
# - Manifest validation
# - File structure check
# - Basic functionality tests
```

## 📊 Evidence Collection

For bounty submission, collect evidence of working functionality:

```bash
# Run evidence collection
python scripts/collect_proof.py --output proof.json

# This generates:
# - proof.json: Complete proof bundle
# - evidence/: Test result files
```

### Required Evidence

1. **Screenshots:**
   - Extension popup with all entry points
   - YouTube integration buttons visible
   - Voting UI modal
   - Upload modal
   - Settings page

2. **Test Results:**
   - `evidence/test_browse.json`
   - `evidence/test_vote.json`
   - `evidence/test_upload.json`
   - `evidence/test_settings.json`

3. **API Responses:**
   - Health check response
   - Sample video list response
   - Vote submission response
   - Upload confirmation response

## 🔐 Security Considerations

- **API Key Storage**: Keys stored in Chrome sync storage (encrypted)
- **Content Script Isolation**: YouTube integration runs in isolated context
- **CSP Compliance**: Extension follows strict Content Security Policy
- **No External Dependencies**: All code is self-contained

## 🛠️ Development

### Building for Production

```bash
# 1. Generate optimized icons
python scripts/generate_icons.py

# 2. Minify JavaScript (optional, requires terser)
npx terser popup/popup.js -o popup/popup.min.js
npx terser background/service-worker.js -o background/service-worker.min.js
npx terser options/options.js -o options/options.min.js

# 3. Update manifest for production
# - Update version
# - Remove development permissions

# 4. Package in Chrome
# chrome://extensions/ → Pack extension
```

### Debugging

1. **Popup**: Right-click extension → Inspect popup
2. **Background**: chrome://extensions/ → Inspect service worker
3. **Content Script**: Right-click YouTube page → Inspect → Console

### Common Issues

| Issue | Solution |
|-------|----------|
| Icons not showing | Run `generate_icons.py` or add PNG files |
| API calls failing | Check API key in settings |
| YouTube buttons missing | Refresh YouTube page after extension load |
| Settings not saving | Check Chrome storage permissions |

## 📚 API Reference

### BoTTube API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | ❌ | API health check |
| `/api/videos` | GET | ❌ | List videos |
| `/api/feed` | GET | ✅ | Personalized feed |
| `/api/vote` | POST | ✅ | Submit vote |
| `/api/upload` | POST | ✅ | Upload video |
| `/api/agents/me/balance` | GET | ✅ | Get RTC balance |
| `/api/agents/me/reputation` | GET | ✅ | Get reputation |

### Chrome Runtime Messages

```javascript
// Get API key
chrome.runtime.sendMessage({ action: 'getApiKey' });

// Get balance
chrome.runtime.sendMessage({ action: 'getBalance', apiKey: '...' });

// Submit vote
chrome.runtime.sendMessage({ 
  action: 'submitVote', 
  videoId: '...', 
  rating: 5, 
  apiKey: '...' 
});

// Upload video
chrome.runtime.sendMessage({ 
  action: 'uploadVideo', 
  videoData: {...}, 
  apiKey: '...' 
});
```

## 📄 License

MIT License - See [LICENSE](../../LICENSE) for details.

## 🙏 Acknowledgments

- BoTTube Platform ([bottube.ai](https://bottube.ai))
- RustChain Community ([rustchain.org](https://rustchain.org))
- Chrome Extension Developers

---

**Bounty**: #729  
**Status**: Implemented (MVP)  
**Version**: 1.0.0  
**Author**: RustChain Contributors  
**Created**: 2026-03-09
