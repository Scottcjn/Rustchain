# Enhanced RustChain Block Explorer

A comprehensive block explorer web application for the RustChain Proof-of-Antiquity network.

## Features

### 📊 Network Overview
- Real-time network status and uptime
- Active miner count
- Current epoch information
- Epoch pot size

### ⛏️ Miner Dashboard
- Complete list of all active miners
- Architecture information with visual badges
- Antiquity multiplier display
- Online/offline status
- Last attestation timestamps
- Total earnings per miner
- Search functionality

### 🕐 Epoch Information
- Current epoch number
- Slot number
- Block height
- Timestamp

### 💸 Transaction Explorer
- Recent transactions list
- Transaction details (from, to, amount, fee)
- Transaction status
- Timestamp information

## Technical Details

### Architecture
- **Single Page Application (SPA)** - No server-side rendering required
- **Vanilla JavaScript** - No build step, no dependencies
- **Responsive Design** - Works on desktop and mobile
- **Dark Theme** - Matches RustChain branding
  - Background: `#1a1a2e` (dark navy)
  - Cards: `#1f2940`
  - Accents: `#f39c12` (gold)

### API Integration

The explorer consumes the following RustChain API endpoints:

```bash
# Health check
GET /health

# Active miners
GET /api/miners

# Current epoch
GET /epoch

# Wallet balances (for future enhancement)
GET /api/balances

# Transactions (for future enhancement)
GET /api/transactions
```

### Auto-Refresh
- Data automatically refreshes every 30 seconds
- Manual refresh button available on each view

## Usage

### Local Testing

1. Open `enhanced-explorer.html` in a web browser
2. The explorer will automatically connect to the RustChain API at `https://50.28.86.131`

### Deployment

To deploy with nginx (as per RustChain's existing setup):

1. Copy `enhanced-explorer.html` to your nginx root directory
2. Configure nginx to serve the file

3. Restart nginx

## File Structure

```
explorer/
├── enhanced-explorer.html      # Main explorer application
├── ENHANCED_EXPLORER_README.md # This file
├── index.html                  # Original explorer
├── dashboard.html              # Dashboard view
└── ... (other explorer files)
```

## Future Enhancements

- [ ] Transaction history with pagination
- [ ] Wallet balance lookup
- [ ] Block explorer with block details
- [ ] Charts and graphs (miner distribution, epoch history)
- [ ] Hall of Rust integration
- [ ] Agent Economy marketplace view
- [ ] Search by wallet address
- [ ] Export data to CSV/JSON

## API Response Format

### /api/miners
```json
{
  "miners": [
    {
      "miner_id": "Miner-Name",
      "architecture": "PowerPC G4",
      "multiplier": 2.5,
      "last_attestation": "2026-03-12T09:00:00Z",
      "earnings": 150.5,
      "wallet": "wallet_address"
    }
  ]
}
```

### /epoch
```json
{
  "epoch": 95,
  "slot": 12345,
  "height": 67890,
  "timestamp": 1710237600
}
```

### /health
```json
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 200000
}
```

## Browser Compatibility

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers (iOS Safari, Chrome Mobile)

---

**Built for RustChain Bounties** - Block Explorer Enhancement
