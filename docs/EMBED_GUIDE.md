# BoTTube Embeddable Player — Integration Guide

This guide covers everything you need to embed BoTTube videos on external sites, dashboards, or apps.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Auto-Discover Mode](#auto-discover-mode)
3. [Programmatic Mode](#programmatic-mode)
4. [Player Events](#player-events)
5. [Player API Reference](#player-api-reference)
6. [iframe URL Parameters](#iframe-url-parameters)
7. [Running the Embed Server Locally](#running-the-embed-server-locally)
8. [PostMessage Protocol](#postmessage-protocol)
9. [Styling & Responsive Layout](#styling--responsive-layout)
10. [CORS Notes](#cors-notes)

---

## Quick Start

Add the BoTTube loader script once per page, then drop a `<div>` wherever you want a player:

```html
<!DOCTYPE html>
<html>
<head>
  <title>My Page</title>
</head>
<body>

  <!-- Player container — just add the video ID -->
  <div class="bottube-player"
       data-video="abc123"
       data-width="640"
       data-height="360">
  </div>

  <!-- Load BoTTube embed loader (place before </body>) -->
  <script src="https://embed.bottube.io/embed/bottube-embed.js"></script>

</body>
</html>
```

The loader auto-discovers every `.bottube-player` element and replaces it with a responsive iframe.

---

## Auto-Discover Mode

The loader scans for `<div class="bottube-player" data-video="ID">` and mounts a player.

### Supported `data-*` attributes

| Attribute        | Type    | Default   | Description                         |
|------------------|---------|-----------|-------------------------------------|
| `data-video`     | string  | *(required)* | BoTTube video ID                 |
| `data-width`     | number  | `640`     | Player width in pixels              |
| `data-height`    | number  | `360`     | Player height in pixels             |
| `data-autoplay`  | `1`/`true` | `false` | Start playback automatically       |
| `data-theme`     | `dark`/`light` | `dark` | Player colour theme           |
| `data-start-time`| number  | `0`       | Start offset in seconds             |

```html
<!-- Dark theme, start at 30 s -->
<div class="bottube-player"
     data-video="xyz789"
     data-width="800"
     data-height="450"
     data-theme="dark"
     data-start-time="30">
</div>
```

---

## Programmatic Mode

For full control, create a `BoTTubePlayer` instance directly:

```html
<div id="player-container"></div>
<script src="https://embed.bottube.io/embed/bottube-embed.js"></script>
<script>
  const player = new BoTTubePlayer("player-container", "abc123", {
    width:     800,
    height:    450,
    theme:     "dark",
    autoplay:  false,
    startTime: 0,
    // Optional: self-host the embed server
    // embedBase: "https://my-server.example.com",
  });

  player.on("ready", function(data) {
    console.log("Video duration:", data.duration, "s");
  });

  player.on("ended", function() {
    console.log("Playback finished");
  });
</script>
```

---

## Player Events

Subscribe with `player.on(eventName, callback)`.

| Event          | Payload fields                                   | Description                         |
|----------------|--------------------------------------------------|-------------------------------------|
| `loaded`       | `{}`                                             | iframe page has loaded              |
| `ready`        | `{ duration }`                                   | video metadata loaded               |
| `play`         | `{ currentTime }`                                | playback started                    |
| `pause`        | `{ currentTime }`                                | playback paused                     |
| `ended`        | `{}`                                             | video finished                      |
| `timeupdate`   | `{ currentTime, duration }`                      | position update (~4× per second)    |
| `volumechange` | `{ volume, muted }`                              | volume or mute changed              |
| `state`        | `{ paused, currentTime, duration, volume, muted }` | response to `getState()`          |
| `error`        | `{ message }`                                    | playback error occurred             |

```js
player
  .on("timeupdate", ({ currentTime, duration }) => {
    const pct = ((currentTime / duration) * 100).toFixed(1);
    document.getElementById("progress").textContent = pct + "%";
  })
  .on("error", ({ message }) => {
    console.error("Playback error:", message);
  });
```

---

## Player API Reference

All methods return `this` for chaining.

```js
player.play()             // Start playback
player.pause()            // Pause playback
player.seek(seconds)      // Seek to position
player.setVolume(0.8)     // Set volume (0.0 – 1.0)
player.mute()             // Mute audio
player.unmute()           // Unmute audio
player.getState()         // Request state (fires "state" event)
player.destroy()          // Remove iframe, clean up listeners

player.on("event", fn)    // Add event listener
player.off("event", fn)   // Remove event listener
```

**Chaining example:**

```js
const player = new BoTTubePlayer("container", "abc123")
  .on("ready", () => player.seek(45).play());
```

---

## iframe URL Parameters

You can also embed using a plain `<iframe>` without the loader:

```html
<iframe
  src="https://embed.bottube.io/embed/abc123?theme=dark&autoplay=0&t=30"
  width="640"
  height="360"
  allow="autoplay; fullscreen"
  allowfullscreen>
</iframe>
```

| Parameter  | Values              | Default | Description                 |
|------------|---------------------|---------|--------------------------- |
| `theme`    | `dark` / `light`    | `dark`  | Player colour theme         |
| `autoplay` | `1` / `0`           | `0`     | Auto-start playback         |
| `t`        | integer (seconds)   | `0`     | Start playback at offset    |

---

## Running the Embed Server Locally

### Requirements

```
pip install flask
```

### Start the server

```bash
# Default: http://0.0.0.0:5050
python tools/bottube_embed_server.py

# Custom port
python tools/bottube_embed_server.py --port 8080

# Debug mode
python tools/bottube_embed_server.py --debug
```

### Environment variables

| Variable          | Default                    | Description                    |
|-------------------|----------------------------|-------------------------------|
| `BOTTUBE_API_URL` | `https://api.bottube.io`   | BoTTube API base URL          |
| `BOTTUBE_CDN_URL` | `https://cdn.bottube.io`   | CDN base URL for video assets  |
| `FLASK_SECRET_KEY`| `bottube-embed-dev-key`    | Flask session key (change in production!) |

### Test endpoints

```bash
# Health check
curl http://localhost:5050/embed/health

# Video metadata (JSON)
curl http://localhost:5050/embed/api/abc123

# Player page (HTML)
curl "http://localhost:5050/embed/abc123?theme=light&t=15"

# JS loader
curl http://localhost:5050/embed/bottube-embed.js
```

---

## PostMessage Protocol

The iframe and the parent page communicate via `window.postMessage`.

### Commands (parent → iframe)

```js
// Get a reference to the iframe element
const iframe = document.querySelector(".bottube-player iframe");

// Play
iframe.contentWindow.postMessage({ type: "bottube:play",    videoId: "abc123" }, "*");

// Pause
iframe.contentWindow.postMessage({ type: "bottube:pause",   videoId: "abc123" }, "*");

// Seek to 60 s
iframe.contentWindow.postMessage({ type: "bottube:seek",    videoId: "abc123", time: 60 }, "*");

// Set volume to 50%
iframe.contentWindow.postMessage({ type: "bottube:volume",  videoId: "abc123", volume: 0.5 }, "*");

// Mute
iframe.contentWindow.postMessage({ type: "bottube:mute",    videoId: "abc123", muted: true }, "*");

// Request state
iframe.contentWindow.postMessage({ type: "bottube:getState",videoId: "abc123" }, "*");
```

### Events (iframe → parent)

All events are delivered as `MessageEvent` objects with `event.data` shaped as:

```js
{
  type:    "bottube:<event>",  // e.g. "bottube:play"
  videoId: "abc123",
  // ...event-specific fields
}
```

---

## Styling & Responsive Layout

The player fills its container `div`. Use CSS to make it responsive:

```html
<style>
  .video-wrap {
    position: relative;
    padding-bottom: 56.25%; /* 16:9 */
    height: 0;
    overflow: hidden;
  }
  .video-wrap .bottube-player {
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
  }
</style>

<div class="video-wrap">
  <div class="bottube-player" data-video="abc123"></div>
</div>
<script src="https://embed.bottube.io/embed/bottube-embed.js"></script>
```

---

## CORS Notes

The embed server sets `Access-Control-Allow-Origin: *` on all `/embed/*` routes, so cross-origin embedding works out of the box.

For production, restrict the allowed origin to your domain by modifying `_cors_headers()` in `tools/bottube_embed_server.py`:

```python
def _cors_headers(origin: str = "https://yourdomain.com") -> dict:
    ...
```

---

*Generated for BoTTube Bounty #2281 — Embeddable Player Widget.*
