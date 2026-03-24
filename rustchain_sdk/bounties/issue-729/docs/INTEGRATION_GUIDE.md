# BoTTube Integration Guide

This guide explains how to integrate the BoTTube Chrome Extension with the BoTTube API and YouTube.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     BoTTube Chrome Extension                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Popup     │  │   Options   │  │  Background │             │
│  │   (UI)      │  │   (Config)  │  │   Worker    │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         │                │                │                      │
│         └────────────────┼────────────────┘                      │
│                          │                                       │
│                  ┌───────▼───────┐                              │
│                  │ Chrome APIs   │                              │
│                  │ - storage     │                              │
│                  │ - tabs        │                              │
│                  │ - runtime     │                              │
│                  └───────┬───────┘                              │
└──────────────────────────┼──────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │ BoTTube API │
                    │ bottube.ai  │
                    └─────────────┘
```

## Entry Point Integration

### 1. Browse Integration

**Purpose**: Allow users to discover and browse AI videos on BoTTube.

**Integration Points**:
- Extension popup navigation
- Direct URL navigation
- Background API calls

**Implementation**:
```javascript
// In popup.js
async function handleBrowse() {
  // Open BoTTube browse page
  await chrome.tabs.create({
    url: 'https://bottube.ai/browse',
    active: true
  });
  
  // Optionally fetch trending videos in background
  await chrome.runtime.sendMessage({ action: 'fetchTrending' });
}
```

**API Integration**:
```javascript
// In service-worker.js
async function fetchTrendingVideos(apiKey = null) {
  const response = await fetch('https://bottube.ai/api/videos?limit=10&trending=true', {
    headers: {
      'Accept': 'application/json',
      ...(apiKey ? { 'Authorization': `Bearer ${apiKey}` } : {})
    }
  });
  return response.json();
}
```

### 2. Vote Integration

**Purpose**: Enable users to rate videos and earn RTC tokens.

**Integration Points**:
- YouTube content script (inline voting)
- Extension popup
- BoTTube website

**YouTube Integration Flow**:
```
1. User visits YouTube video
2. Content script injects "Vote" button
3. User clicks button → shows rating UI
4. User selects rating (1-5 stars)
5. Background worker submits to BoTTube API
6. User receives RTC reward notification
```

**Implementation**:
```javascript
// In youtube-integration.js
async function submitVote(youtubeVideoId, rating) {
  const apiKey = await getApiKey();
  
  const response = await chrome.runtime.sendMessage({
    action: 'submitVote',
    videoId: youtubeVideoId,
    rating: rating,
    apiKey: apiKey
  });
  
  if (response.success) {
    showToast(`Vote submitted! Earned ${response.reward} RTC`, 'success');
  }
}
```

**API Request**:
```http
POST https://bottube.ai/api/vote
Authorization: Bearer <api_key>
Content-Type: application/json

{
  "video_id": "youtube_video_id",
  "rating": 5,
  "timestamp": "2026-03-09T12:00:00Z"
}
```

### 3. Upload Integration

**Purpose**: Allow users to submit videos from YouTube to BoTTube.

**Integration Points**:
- YouTube content script (upload from current video)
- Extension popup
- BoTTube upload page

**Upload Flow**:
```
1. User visits YouTube video
2. Content script injects "Upload" button
3. User clicks button → shows upload modal
4. User fills title, description
5. Background worker submits metadata to BoTTube
6. User receives upload confirmation
```

**Implementation**:
```javascript
// In youtube-integration.js
async function uploadVideo(videoData) {
  const apiKey = await getApiKey();
  
  const response = await chrome.runtime.sendMessage({
    action: 'uploadVideo',
    videoData: {
      title: videoData.title,
      description: videoData.description,
      sourceUrl: window.location.href,
      public: true
    },
    apiKey: apiKey
  });
  
  if (response.success) {
    showToast('Video uploaded successfully!', 'success');
  }
}
```

**API Request**:
```http
POST https://bottube.ai/api/upload
Authorization: Bearer <api_key>
Content-Type: multipart/form-data

metadata: {
  "title": "Video Title",
  "description": "Video description...",
  "source_url": "https://youtube.com/watch?v=...",
  "public": true
}
```

## Configuration Integration

### API Key Management

**Storage**: Chrome sync storage (encrypted)

**Access Pattern**:
```javascript
// Get API key
const result = await chrome.storage.sync.get(['apiKey']);
const apiKey = result.apiKey;

// Set API key
await chrome.storage.sync.set({ apiKey: 'your_key_here' });
```

### Wallet Integration

**Supported Wallets**:
- Base (EVM): `0x...` addresses
- Solana: Base58 addresses

**Storage**:
```javascript
await chrome.storage.sync.set({
  walletAddress: '0xYourBaseAddress'
});
```

## Testing Integration

### Manual Testing

1. **Browse**:
   - Click extension icon
   - Click "Browse"
   - Verify BoTTube page opens

2. **Vote**:
   - Navigate to YouTube
   - Look for BoTTube "Vote" button
   - Click and rate a video
   - Verify success notification

3. **Upload**:
   - Navigate to YouTube
   - Click "Upload" button
   - Fill form and submit
   - Verify upload confirmation

### Automated Testing

```bash
# Run test suite
cd bounties/issue-729
python scripts/test_extension.py

# Validate with CI
./scripts/ci_validate.sh

# Collect proof
python scripts/collect_proof.py --output proof.json --include-metadata
```

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Vote button not showing | Content script not injected | Refresh YouTube page |
| API errors | Invalid/missing API key | Configure in settings |
| Upload fails | Network issue | Check console for errors |
| Settings not saving | Storage permission issue | Verify manifest permissions |

### Debug Mode

Enable verbose logging in service worker:
```javascript
// In service-worker.js
const DEBUG = true;
if (DEBUG) console.log('Debug:', message);
```

## Security Considerations

1. **API Keys**: Stored in Chrome sync storage (encrypted at rest)
2. **Content Scripts**: Isolated from page JavaScript
3. **CSP**: Strict Content Security Policy enforced
4. **Permissions**: Minimal required permissions only

## Performance

- **Cache TTL**: 5 minutes for API responses
- **Lazy Loading**: Content scripts load on demand
- **Background Worker**: Efficient message handling

## Future Enhancements

- [ ] Real-time reward notifications via WebSocket
- [ ] Batch vote submission
- [ ] Video analytics dashboard
- [ ] Cross-browser support (Firefox, Edge)
- [ ] Offline mode with sync

---

**Version**: 1.0.0  
**Last Updated**: 2026-03-09
