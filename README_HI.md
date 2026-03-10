<div align="center">

# 🧱 RustChain: Proof-of-Antiquity ब्लॉकचेन

> **हिंदी अनुवाद संस्करण** | [English Version](README.md)

[![CI](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml/badge.svg)](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/Scottcjn/Rustchain?style=flat&color=gold)](https://github.com/Scottcjn/Rustchain/stargazers)
[![Contributors](https://img.shields.io/github/contributors/Scottcjn/Rustchain?color=brightgreen)](https://github.com/Scottcjn/Rustchain/graphs/contributors)
[![Last Commit](https://img.shields.io/github/last-commit/Scottcjn/Rustchain?color=blue)](https://github.com/Scottcjn/Rustchain/commits/main)
[![Open Issues](https://img.shields.io/github/issues/Scottcjn/Rustchain?color=orange)](https://github.com/Scottcjn/Rustchain/issues)
[![PowerPC](https://img.shields.io/badge/PowerPC-G3%2FG4%2FG5-orange)](https://github.com/Scottcjn/Rustchain)
[![Blockchain](https://img.shields.io/badge/Consensus-Proof--of--Antiquity-green)](https://github.com/Scottcjn/Rustchain)
[![Python](https://img.shields.io/badge/Python-3.x-yellow)](https://www.python.org)
[![Network](https://img.shields.io/badge/Nodes-3%20Active-brightgreen)](https://rustchain.org/explorer)
[![Bounties](https://img.shields.io/badge/Bounties-Open%20%F0%9F%92%B0-green)](https://github.com/Scottcjn/rustchain-bounties/issues)
[![As seen on BoTTube](https://bottube.ai/badge/seen-on-bottube.svg)](https://bottube.ai)
[![Discussions](https://img.shields.io/github/discussions/Scottcjn/Rustchain?color=purple)](https://github.com/Scottcjn/Rustchain/discussions)

**दुनिया का पहला ब्लॉकचेन जो पुराने हार्डवेयर को उसकी गति नहीं बल्कि उसकी उम्र के आधार पर पुरस्कृत करता है।**

*आपका PowerPC G4 एक आधुनिक Threadripper से भी अधिक कमा सकता है। यही इसका उद्देश्य है।*

[वेबसाइट](https://rustchain.org) • [लाइव एक्सप्लोरर](https://rustchain.org/explorer) • [wRTC स्वैप](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [wRTC क्विकस्टार्ट](docs/wrtc.md) • [wRTC ट्यूटोरियल](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Grokipedia संदर्भ](https://grokipedia.com/search?q=RustChain) • [व्हाइटपेपर](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf) • [क्विक स्टार्ट](#-quick-start) • [यह कैसे काम करता है](#-how-proof-of-antiquity-works)

<div align="left">
  # ⚡ क्विक स्टार्ट

### वन-लाइन इंस्टॉल (अनुशंसित)

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

इंस्टॉलर निम्न कार्य करता है:

* ✅ प्लेटफ़ॉर्म को स्वतः पहचानता है (Linux/macOS, x86_64/ARM/PowerPC)
* ✅ अलग Python virtual environment बनाता है (सिस्टम को प्रभावित नहीं करता)
* ✅ आपके हार्डवेयर के लिए सही miner डाउनलोड करता है
* ✅ सिस्टम बूट पर ऑटो-स्टार्ट सेट करता है (systemd/launchd)
* ✅ आसान uninstall विकल्प प्रदान करता है

### विकल्पों के साथ इंस्टॉलेशन

**विशिष्ट वॉलेट के साथ इंस्टॉल करें:**

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-miner-wallet
```

**अनइंस्टॉल करें:**

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall
```

### समर्थित प्लेटफ़ॉर्म

* ✅ Ubuntu 20.04+, Debian 11+, Fedora 38+ (x86_64, ppc64le)
* ✅ macOS 12+ (Intel, Apple Silicon, PowerPC)
* ✅ IBM POWER8 सिस्टम

### ट्रबलशूटिंग

* **यदि इंस्टॉलर permission error के साथ फेल हो जाए:**
  `~/.local` पर लिखने की अनुमति वाले अकाउंट से दोबारा चलाएँ और system Python के global site-packages के अंदर चलाने से बचें।

* **Python version error (`SyntaxError` / `ModuleNotFoundError`):**
  Python 3.10+ इंस्टॉल करें और `python3` उसी interpreter को इंगित करे।

```bash
python3 --version
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

* **`curl` में HTTPS certificate error:**
  यह non-browser environments में हो सकता है। पहले कनेक्टिविटी जांचें:

```bash
curl -I https://rustchain.org
```

* **Miner तुरंत बंद हो जाता है:**
  सुनिश्चित करें कि वॉलेट मौजूद है और service चल रही है:

```bash
systemctl --user status rustchain-miner
```

या

```bash
launchctl list | grep rustchain
```

यदि समस्या बनी रहती है, तो error output और OS विवरण के साथ नया issue या bounty comment पोस्ट करें।

### इंस्टॉलेशन के बाद

**वॉलेट बैलेंस जांचें:**

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

**सक्रिय miners की सूची देखें:**

```bash
curl -sk https://rustchain.org/api/miners
```

**नोड की स्थिति जांचें:**

```bash
curl -sk https://rustchain.org/health
```

**वर्तमान epoch प्राप्त करें:**

```bash
curl -sk https://rustchain.org/epoch
```

### Miner सेवा प्रबंधन

*Linux (systemd):*

```bash
systemctl --user status rustchain-miner
systemctl --user stop rustchain-miner
systemctl --user start rustchain-miner
journalctl --user -u rustchain-miner -f
```

*macOS (launchd):*

```bash
launchctl list | grep rustchain
launchctl stop com.rustchain.miner
launchctl start com.rustchain.miner
tail -f ~/.rustchain/miner.log
```

### मैनुअल इंस्टॉलेशन

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
bash install-miner.sh --wallet YOUR_WALLET_NAME
# सिस्टम बदले बिना preview देखने के लिए
bash install-miner.sh --dry-run --wallet YOUR_WALLET_NAME
```

</div>

</div>

---
