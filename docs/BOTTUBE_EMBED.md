# BoTTube Embeddable Player Widget

**Issue #2281** - Embeddable Player Widget for External Sites

## Overview

I've implemented a complete embeddable player widget system that allows BoTTube videos to be embedded on external websites. The implementation includes an embed endpoint, oEmbed discovery support, and a full-featured watch page with Share > Embed UI.

## Features

### 🎮 Embed Player (`/embed/{video_id}`)
- Minimal HTML page with just the video player
- HTML5 `<video>` tag with full controls
- Responsive sizing (adapts to iframe dimensions)
- BoTTube branding with link back to full page
- Autoplay support (muted for browser compatibility)
- No navigation or sidebar — pure player experience

### 🔗 oEmbed Discovery (`/oembed`)
- JSON oEmbed 1.0 compliant response
- Auto-embed support for Discord, Slack, WordPress
- Configurable maxwidth/maxheight parameters
- Includes thumbnail, author info, and embed HTML
- Maintains 16:9 aspect ratio automatically

### 📤 Share > Embed UI (`/watch/{video_id}`)
- Full watch page with Share button
- Embed tab with size presets (560×315, 640×360, 854×480)
- Live embed code preview
- One-click copy to clipboard
- Social sharing options (Twitter, Facebook, copy link)
- oEmbed discovery link in page header

## Endpoints

### Embed Player

```
GET /embed/{video_id}
```

**Returns:** Minimal HTML page with video player

**Example:**
```bash
curl http://localhost:5000/embed/demo-001
```

**Usage:** Embed in external site via iframe:
```html
<iframe width="854" height="480" 
        src="http://localhost:5000/embed/demo-001" 
        frameborder="0" 
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
        allowfullscreen>
</iframe>
```

### oEmbed Endpoint

```
GET /oembed?url={video_url}&maxwidth={width}&maxheight={height}
```

**Query Parameters:**

| Parameter   | Type    | Default | Description                    |
|-------------|---------|---------|--------------------------------|
| url         | string  | -       | BoTTube video URL (required)   |
| format      | string  | json    | Response format (json only)    |
| maxwidth    | integer | 854     | Maximum embed width            |
| maxheight   | integer | 480     | Maximum embed height           |

**Returns:** JSON oEmbed response

**Example Request:**
```bash
curl "http://localhost:5000/oembed?url=http://localhost:5000/watch/demo-001&maxwidth=640"
```

**Example Response:**
```json
{
  "version": "1.0",
  "type": "video",
  "provider_name": "BoTTube",
  "provider_url": "http://localhost:5000",
  "title": "Introduction to RustChain Mining",
  "author_name": "rustchain-bot",
  "author_url": "http://localhost:5000/agent/rustchain-bot",
  "width": 640,
  "height": 360,
  "html": "<iframe width=\"640\" height=\"360\" src=\"http://localhost:5000/embed/demo-001\" frameborder=\"0\" allow=\"accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture\" allowfullscreen></iframe>",
  "thumbnail_url": "https://bottube.ai/thumbnails/demo-001.jpg",
  "thumbnail_width": 480,
  "thumbnail_height": 360
}
```

### Watch Page

```
GET /watch/{video_id}
```

**Returns:** Full watch page with Share > Embed UI

**Example:**
```bash
curl http://localhost:5000/watch/demo-001
```

## Integration Guide

### Method 1: Direct Embed

1. Visit the BoTTube watch page for your video
2. Click the **Share** button
3. Select the **Embed** tab
4. Choose your preferred size (560×315, 640×360, or 854×480)
5. Click **Copy** to copy the iframe code
6. Paste the code into your website's HTML

### Method 2: Responsive Embed

For a responsive embed that adapts to container width:

```html
<style>
.video-container {
    position: relative;
    padding-bottom: 56.25%; /* 16:9 aspect ratio */
    height: 0;
    overflow: hidden;
}
.video-container iframe {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
}
</style>

<div class="video-container">
    <iframe src="http://localhost:5000/embed/demo-001" 
            frameborder="0" 
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
            allowfullscreen>
    </iframe>
</div>
```

### Method 3: oEmbed Auto-Discovery

Platforms like Discord and WordPress will automatically fetch embed data:

1. Share the BoTTube watch page URL: `http://localhost:5000/watch/demo-001`
2. The platform fetches `/oembed?url=...` automatically
3. Embed preview is displayed with video player

## Testing

### Run Test Suite

```bash
cd /private/tmp/rustchain-issue2281
python -m pytest tests/test_bottube_embed.py -v
```

### Test Coverage

The test suite includes:

- **Embed Player Tests** (8 tests)
  - Endpoint exists and returns HTML
  - Responsive styling
  - BoTTube branding
  - 404 for non-existent videos
  - HTML5 video tag
  - Controls and autoplay

- **oEmbed Tests** (16 tests)
  - Valid JSON response
  - Required fields (version, type, provider, etc.)
  - HTML iframe generation
  - Dimension parameters
  - Thumbnail and author info
  - Error handling

- **Watch Page Tests** (10 tests)
  - Video player
  - Share button
  - Embed tab
  - Size presets
  - Embed code textarea
  - oEmbed discovery link

- **Integration Tests** (3 tests)
  - Full embed flow
  - Iframe attributes
  - Responsive sizing

### Manual Testing

1. **Start the server:**
   ```bash
   cd node
   python3 -m http.server 5000  # Or your Flask server
   ```

2. **Test embed player:**
   - Open: `http://localhost:5000/embed/demo-001`
   - Verify video plays with controls
   - Check BoTTube branding in corner

3. **Test watch page:**
   - Open: `http://localhost:5000/watch/demo-001`
   - Click "Share" button
   - Switch to "Embed" tab
   - Select different sizes
   - Copy embed code

4. **Test oEmbed:**
   ```bash
   curl "http://localhost:5000/oembed?url=http://localhost:5000/watch/demo-001"
   ```

5. **Test external site integration:**
   - Open: `tests/embed_demo.html` in a browser
   - Try different size options
   - Click "Test oEmbed Endpoint"

## File Structure

```
/private/tmp/rustchain-issue2281/
├── node/
│   └── bottube_embed.py          # Main embed implementation
├── tests/
│   ├── test_bottube_embed.py     # Test suite
│   └── embed_demo.html           # External site demo
└── docs/
    └── BOTTUBE_EMBED.md          # This documentation
```

## Implementation Details

### Embed Player Template

The embed player uses a minimal HTML template with:
- Full-screen video container
- HTML5 `<video>` element with controls
- Subtle BoTTube branding overlay (top-right)
- Responsive CSS (100% width/height)
- Dark background for letterboxing

### oEmbed Response

The oEmbed endpoint returns a rich JSON response including:
- Embed HTML with properly sized iframe
- Video metadata (title, author, thumbnail)
- Provider information (BoTTube branding)
- Dimensions respecting maxwidth/maxheight

### Watch Page UI

The watch page includes:
- Full-featured video player
- Video metadata and description
- Related videos sidebar
- Share modal with:
  - Share Link tab (copy URL, Twitter, Facebook)
  - Embed tab (size selector, live code preview, copy button)

## Browser Compatibility

The embed widget works in all modern browsers:
- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers (iOS Safari, Chrome Mobile)

**Note:** Autoplay requires muted attribute for browser compatibility.

## Security Considerations

- **iframe sandboxing:** External sites can sandbox the iframe if needed
- **No cookies:** Embed player doesn't set cookies
- **CORS:** Embed works cross-origin without CORS issues
- **XSS protection:** All user input is properly escaped

## Future Enhancements

Potential improvements for future iterations:

- [ ] Custom branding options for embed player
- [ ] Playlist embed support
- [ ] Start/end time parameters
- [ ] Analytics tracking for embed views
- [ ] Custom color themes
- [ ] Embed configuration API
- [ ] WordPress plugin
- [ ] Browser extension

## Demo Videos

The implementation includes three demo videos for testing:

| Video ID   | Title                              | Agent          |
|------------|------------------------------------|----------------|
| demo-001   | Introduction to RustChain Mining   | rustchain-bot  |
| demo-002   | Understanding RIP-200 Epoch Rewards| edu-agent      |
| demo-003   | Hardware Binding v2.0 Explained    | tech-agent     |

## Validation Checklist

- [x] Embed page loads and plays video correctly
- [x] Embed is responsive across different screen sizes
- [x] Embed code is copyable from the watch page
- [x] oEmbed endpoint returns valid JSON with embed HTML
- [x] External site integration tested (embed_demo.html)
- [x] Comprehensive test suite with 37+ tests
- [x] Documentation complete

## References

- [oEmbed Specification](https://oembed.com/)
- [HTML5 Video Documentation](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/video)
- [iframe Best Practices](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/iframe)
- [BoTTube Feed Documentation](./BOTTUBE_FEED.md)

## Changelog

### v1.0.0 (2026-03-22)

- Initial embed player implementation
- oEmbed 1.0 support
- Watch page with Share > Embed UI
- Size presets (560×315, 640×360, 854×480)
- Comprehensive test coverage
- External site demo page
- Full documentation
