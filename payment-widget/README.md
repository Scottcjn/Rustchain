# RustChain Payment Widget (rustchain-pay.js)

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-orange" alt="Version">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/crypto-Ed25519-blue" alt="Crypto">
</p>

A lightweight, embeddable JavaScript widget for accepting **RTC (RustChain Token)** payments on any website. Similar to Stripe's checkout button, but for RustChain's Proof-of-Antiquity cryptocurrency.

## ✨ Features

- **🔒 Client-Side Signing** - Private keys never leave the browser
- **📦 Zero Dependencies** - Self-contained with bundled TweetNaCl.js
- **🎨 Beautiful UI** - Modern, responsive modal design
- **⚡ Easy Integration** - Single script tag, auto-initializes
- **🔑 Multiple Auth Methods** - Supports seed phrases and encrypted keystores
- **📱 Responsive** - Works on desktop and mobile
- **🔗 Callback Support** - Webhook notifications for payment confirmation

## 🚀 Quick Start

### Method 1: Data Attributes (Easiest)

```html
<!-- Include the widget -->
<script src="rustchain-pay.js"></script>

<!-- Add a payment button -->
<div id="rtc-pay" 
     data-to="RTCyour_wallet_address_here" 
     data-amount="10" 
     data-memo="Payment for services">
</div>
```

That's it! The widget auto-initializes and creates a "Pay 10 RTC" button.

### Method 2: JavaScript API

```html
<script src="rustchain-pay.js"></script>
<button id="pay-btn">Buy Now</button>

<script>
const rtcPay = new RustChainPay({
  nodeUrl: 'https://50.28.86.131',  // Optional: custom node
  onSuccess: (result) => {
    console.log('Payment TX:', result.tx_hash);
    // Redirect to success page, update UI, etc.
  },
  onError: (error) => {
    console.error('Payment failed:', error);
  },
  onCancel: () => {
    console.log('User cancelled payment');
  }
});

document.getElementById('pay-btn').onclick = () => {
  rtcPay.openPaymentModal({
    to: 'RTCyour_wallet_address',
    amount: 25,
    memo: 'Order #12345',
    callback: 'https://your-api.com/payment-webhook'
  });
};
</script>
```

## 📖 API Reference

### `RustChainPay` Class

#### Constructor Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `nodeUrl` | string | `https://50.28.86.131` | RustChain node URL |
| `onSuccess` | function | `() => {}` | Called on successful payment |
| `onError` | function | `() => {}` | Called on payment error |
| `onCancel` | function | `() => {}` | Called when user cancels |

#### Methods

##### `createButton(container, options)`

Attaches a payment button to an existing DOM element.

```javascript
rtcPay.createButton('#container', {
  to: 'RTC...',
  amount: 10,
  memo: 'Product purchase',
  label: 'Buy Now - 10 RTC',
  callback: 'https://api.example.com/webhook'
});
```

##### `openPaymentModal(options)`

Opens the payment modal directly.

```javascript
rtcPay.openPaymentModal({
  to: 'RTC...',
  amount: 5,
  memo: 'Subscription fee',
  callback: 'https://api.example.com/webhook'
});
```

##### `checkBalance(address)`

Fetches wallet balance from the node.

```javascript
const balance = await rtcPay.checkBalance('RTCaddress...');
console.log(balance.amount_rtc); // e.g., 150.5
```

### Data Attributes

| Attribute | Required | Description |
|-----------|----------|-------------|
| `data-to` | Yes | Recipient wallet address (RTC...) |
| `data-amount` | Yes | Payment amount in RTC |
| `data-memo` | No | Payment memo/description |
| `data-label` | No | Custom button text |
| `data-callback` | No | Webhook URL for payment notification |

### Success Callback Payload

```javascript
{
  tx_hash: "abc123...",    // Transaction hash
  from: "RTCsender...",    // Sender address
  to: "RTCrecipient...",   // Recipient address
  amount: 10,              // Amount in RTC
  memo: "Order #123",      // Payment memo
  timestamp: 1706900000    // Unix timestamp
}
```

## 🔐 Security

### Client-Side Signing

All cryptographic operations happen in the browser:

1. **Seed Phrase Entry** - User enters their 24-word BIP39 seed
2. **Key Derivation** - PBKDF2-HMAC-SHA256 with RustChain salt (100,000 iterations)
3. **Ed25519 Signing** - Transaction signed with derived private key
4. **Submission** - Only signature and public key sent to network

**The private key never leaves the browser.**

### Keystore Support

Supports RustChain's encrypted keystore format:
- AES-256-GCM encryption
- PBKDF2 key derivation
- Password-protected seed storage

### Transaction Format

```json
{
  "from_address": "RTC...",
  "to_address": "RTC...",
  "amount_rtc": 10.0,
  "timestamp": 1706900000,
  "nonce": "cryptographically_secure_random",
  "memo": "Payment description",
  "signature": "ed25519_signature_hex",
  "public_key": "ed25519_pubkey_hex"
}
```

## 🎨 Customization

### CSS Variables

Override the default styles:

```css
/* Custom button color */
.rtc-pay-btn {
  background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%) !important;
}

/* Custom modal background */
.rtc-modal {
  background: #0a0a0a !important;
}
```

### Custom Button Styling

```html
<style>
  .my-custom-btn {
    /* Your styles */
  }
</style>

<button class="my-custom-btn" id="pay">Pay 10 RTC</button>

<script>
document.getElementById('pay').onclick = () => {
  new RustChainPay().openPaymentModal({
    to: 'RTC...',
    amount: 10
  });
};
</script>
```

## 🌐 Webhook Integration

Set `data-callback` or pass `callback` in options to receive POST notifications:

```javascript
// Your webhook endpoint receives:
{
  "tx_hash": "abc123...",
  "from": "RTCsender...",
  "to": "RTCrecipient...",
  "amount": 10,
  "memo": "Order #123",
  "timestamp": 1706900000
}
```

### Example Node.js Webhook Handler

```javascript
app.post('/payment-webhook', (req, res) => {
  const { tx_hash, from, to, amount, memo } = req.body;
  
  // Verify payment on-chain (recommended)
  // Update order status
  // Send confirmation email
  
  res.status(200).json({ received: true });
});
```

## 🔧 Development

### Building from Source

The widget is self-contained. To modify:

1. Clone the repository
2. Edit `rustchain-pay.js`
3. Test with `demo.html`

### Running Demo

```bash
# Simple HTTP server
python3 -m http.server 8000
# Open http://localhost:8000/demo.html
```

## 📋 Browser Support

- Chrome 60+
- Firefox 55+
- Safari 11+
- Edge 79+

Requires Web Crypto API support.

## 🔗 Resources

- **RustChain Repo**: [github.com/Scottcjn/Rustchain](https://github.com/Scottcjn/Rustchain)
- **Network Explorer**: [50.28.86.131/explorer](https://50.28.86.131/explorer/)
- **Bounties**: [github.com/Scottcjn/rustchain-bounties](https://github.com/Scottcjn/rustchain-bounties)
- **Node API**: `https://50.28.86.131`
  - `GET /health` - Node status
  - `GET /api/miners` - Active miners
  - `GET /wallet/balance?miner_id=ADDRESS` - Check balance
  - `POST /wallet/transfer/signed` - Submit signed transfer

## 📜 License

MIT License - Free for commercial and non-commercial use.

---

**Built for RustChain** - The Proof-of-Antiquity blockchain rewarding vintage hardware.
