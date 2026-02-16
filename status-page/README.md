# RustChain Network Status Page

Real-time health monitoring dashboard for all RustChain nodes.

## Features

- **Live Status Indicators**: Green/Yellow/Red status for each node
- **Response Time Monitoring**: Real-time latency measurements
- **24-Hour Uptime History**: Visual bar chart showing health over time
- **Auto-Refresh**: Updates every 60 seconds automatically
- **Mobile-Friendly**: Responsive design works on all devices
- **Local Storage History**: Persists uptime data in browser

## Monitored Nodes

1. **Primary Node** (https://50.28.86.131/health)
   - Main consensus node
   
2. **Ergo Anchor** (https://50.28.86.153/health)
   - Blockchain anchor

3. **External Node** (http://76.8.228.245:8099/health)
   - Community-hosted

## Deployment

### Option 1: GitHub Pages (Recommended)

1. Push this `status-page/` directory to your repository
2. Go to **Settings → Pages**
3. Select **Deploy from a branch**
4. Choose `main` branch, `/status-page` folder
5. Save
6. Your status page will be live at: `https://[username].github.io/Rustchain/`

### Option 2: Static Hosting (Netlify, Vercel, Cloudflare Pages)

Simply deploy the `status-page/` folder. No build step required!

### Option 3: Local Testing

```bash
cd status-page
python3 -m http.server 8000
# Open http://localhost:8000 in browser
```

## How It Works

1. **Polling**: Fetches `/health` endpoint from each node every 60 seconds
2. **Status Logic**:
   - 🟢 **Healthy**: Response < 2s
   - 🟡 **Degraded**: Response 2-5s
   - 🔴 **Down**: Timeout or error
3. **History**: Stores last 24 hours of data in `localStorage`
4. **Charts**: Renders uptime bars based on historical data

## Health API Response Format

```json
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 86400,
  "db_rw": true,
  "tip_age_slots": 0
}
```

## Screenshots

![Status Page](https://via.placeholder.com/800x600.png?text=RustChain+Network+Status)

## Customization

### Changing Poll Interval

Edit `index.html`, line 241:

```javascript
const POLL_INTERVAL = 60000; // Change to desired interval in milliseconds
```

### Adding More Nodes

Edit `NODES` array in `index.html`, line 220:

```javascript
const NODES = [
    {
        name: 'Node Name',
        url: 'https://node-url/health',
        description: 'Node description'
    },
    // Add more nodes here
];
```

### Styling

All CSS is inline in `<style>` tag. Modify colors, fonts, layout as needed.

## CORS Considerations

If nodes don't have CORS enabled, you may need:

1. **Server-side proxy**: Create a backend that proxies requests
2. **CORS browser extension**: For local testing only
3. **Enable CORS on nodes**: Add appropriate headers

Current implementation attempts direct fetch with `mode: 'cors'`.

## Browser Compatibility

- ✅ Chrome/Edge 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Mobile browsers (iOS Safari, Chrome Mobile)

Uses modern JavaScript (async/await, fetch API, localStorage).

## License

Apache License 2.0 (same as RustChain)

## Contributing

Found a bug or want to add a feature? Submit a PR!

---

**Built for RustChain Bounty #161** (25 RTC)
