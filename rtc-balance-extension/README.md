# RTC Balance Viewer - Browser Extension

A lightweight browser extension that displays RTC (RustChain Token) balance for a configured wallet or miner ID.

## Features

- **Minimal UI**: Clean, simple interface showing your RTC balance at a glance
- **Configurable Endpoint**: Set your own RPC/API endpoint for balance queries
- **Auto-refresh**: Automatic balance updates at configurable intervals
- **Wallet/Miner ID Support**: Works with any wallet or miner ID format
- **Privacy-focused**: All data stored locally in browser storage

## Installation

### Chrome / Chromium / Edge

1. Open your browser and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in the top right corner)
3. Click **Load unpacked**
4. Select the `rtc-balance-extension` folder
5. The extension icon will appear in your browser toolbar

### Firefox

1. Open Firefox and navigate to `about:debugging#/runtime/this-firefox`
2. Click **Load Temporary Add-on**
3. Select the `manifest.json` file in the `rtc-balance-extension` folder
4. The extension will be loaded until Firefox is restarted

> **Note**: For Firefox, you may need to adjust the manifest version or use WebExtensions API compatibility layer.

## Configuration

1. Click the extension icon in your browser toolbar
2. Click **Settings** button
3. Enter your **Wallet/Miner ID**
4. Enter your **API Endpoint** URL
5. Set **Auto-refresh interval** (1-60 minutes)
6. Click **Save**

### API Endpoint Format

The extension supports various endpoint formats:

- `https://api.rustchain.io/balance` - Wallet ID appended automatically
- `https://api.rustchain.io/balance/{walletId}` - Include wallet ID in URL
- `https://api.rustchain.io/balance?address={walletId}` - Query parameter format

The extension will automatically adapt to your endpoint format.

## Usage

- **Refresh**: Click the Refresh button to manually update your balance
- **Settings**: Configure wallet ID, endpoint, and refresh interval
- **Balance Display**: Shows current RTC balance with last update time

## File Structure

```
rtc-balance-extension/
├── manifest.json      # Extension manifest (MV3)
├── popup.html         # Popup UI structure
├── popup.js           # Popup logic and event handlers
├── background.js      # Background service worker for API calls
├── styles.css         # Popup styling
├── icons/             # Extension icons
│   ├── icon16.png
│   ├── icon48.png
│   └── icon128.png
└── README.md          # This file
```

## Permissions

The extension requests the following permissions:

- `storage`: Store wallet ID, endpoint, and settings locally
- `alarms`: Enable automatic balance refresh
- `host_permissions`: Allow API calls to configured endpoints

All data is stored locally and never transmitted except to your configured endpoint.

## Development

### Testing Changes

1. Make changes to extension files
2. Go to `chrome://extensions/`
3. Click the refresh icon on the extension card
4. Re-open the popup to see changes

### Building Icons

Placeholder icons should be replaced with actual RTC branding. You can generate icons using:

```bash
# Using ImageMagick to create placeholder icons
mkdir -p icons
convert -size 16x16 xc:#667eea icons/icon16.png
convert -size 48x48 xc:#667eea icons/icon48.png
convert -size 128x128 xc:#667eea icons/icon128.png
```

Or use any image editor to create PNG icons with the desired branding.

## Troubleshooting

### Balance not showing

1. Verify your wallet/miner ID is correct
2. Check that the API endpoint is accessible
3. Open browser DevTools and check the extension console for errors

### Auto-refresh not working

1. Ensure the interval is set to at least 1 minute
2. Check that the extension has necessary permissions
3. Try reloading the extension

### API endpoint errors

The extension expects JSON responses. If your API returns a different format, you may need to:

1. Modify `background.js` to parse your specific response format
2. Use a proxy endpoint that returns compatible JSON

## API Response Format

The extension can parse various JSON response formats:

```json
// Simple number
123.45

// Object with balance field
{ "balance": 123.45 }
{ "data": { "balance": 123.45 } }
{ "result": { "available": "123.45" } }
```

## Security Considerations

- Never share your wallet/miner ID with untrusted parties
- Only use HTTPS endpoints in production
- The extension stores configuration locally in browser storage
- Review the source code before installing

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Support

For issues or questions, please open an issue in the repository.
