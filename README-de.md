<div align="center">

# 🧱 RustChain: Proof-of-Antiquity Blockchain

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

**Die erste Blockchain, die alte Hardware belohnt – nicht schnelle.**

*Ihr PowerPC G4 verdient mehr als ein moderner Threadripper. Das ist der Punkt.*

[Website](https://rustchain.org) • [Live Explorer](https://rustchain.org/explorer) • [Swap wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [wRTC Quickstart](docs/wrtc.md) • [wRTC Tutorial](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Grokipedia Ref](https://grokipedia.com/search?q=RustChain) • [Whitepaper](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf)

</div>

---

## 🪙 wRTC auf Solana

RustChain Token (RTC) ist jetzt als **wRTC** auf Solana über die BoTTube Bridge verfügbar:

| Ressource | Link |
|----------|------|
| **wRTC Swap** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **Preis-Chart** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **Bridge RTC ↔ wRTC** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **Schnellstart-Anleitung** | [wRTC Quickstart](docs/wrtc.md) |
| **Token Mint** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---

## Beitragen und RTC Verdienen

Jeder Beitrag verdient RTC-Token. Bugfixes, Features, Docs, Sicherheitsaudits – alles bezahlt.

| Stufe | Belohnung | Beispiele |
|------|--------|----------|
| Mikro | 1-10 RTC | Tippfehler, kleine Docs, einfacher Test |
| Standard | 20-50 RTC | Feature, Refaktorierung, neuer Endpoint |
| Major | 75-100 RTC | Sicherheitsfix, Konsensverbesserung |
| Kritisch | 100-150 RTC | Schwachstellen-Patch, Protokoll-Upgrade |

**Los geht's:**
1. Durchsuche [offene Bounties](https://github.com/Scottcjn/rustchain-bounties/issues)
2. Wähle ein [good first issue](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue) (5-10 RTC)
3. Fork, fix, PR – werde in RTC bezahlt
4. Siehe [CONTRIBUTING.md](CONTRIBUTING.md) für alle Details

**1 RTC = $0.10 USD** | `pip install clawrtc` zum Starten des Minings

---

## 🎯 Was RustChain Anders Macht

| Traditionelles PoW | Proof-of-Antiquity |
|----------------|-------------------|
| Belohnt schnellste Hardware | Belohnt älteste Hardware |
| Neu = Besser | Alt = Besser |
| Energieverschwendung | Bewahrt Computing-Geschichte |
| Wettlauf nach unten | Belohnt digitale Bewahrung |

**Kernprinzip**: Echte Vintage-Hardware, die Jahrzehnte überlebt hat, verdient Anerkennung. RustChain dreht Mining um.

---

## ⚡ Schnellstart

### Ein-Zeilen-Installation (Empfohlen)
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

Der Installer:
- ✅ Erkennt automatisch Ihre Plattform (Linux/macOS, x86_64/ARM/PowerPC)
- ✅ Erstellt isoliertes Python-Virtualenv (keine Systemverschmutzung)
- ✅ Lädt den richtigen Miner für Ihre Hardware
- ✅ Richtet Autostart beim Booten ein (systemd/launchd)
- ✅ Bietet einfache Deinstallation

### Unterstützte Plattformen

| Plattform | Status | Hinweise |
|------------|--------|-------|
| Linux x86_64 | ✅ Stabil | Ubuntu, Debian, Fedora, Arch |
| macOS ARM (M1/M2/M3) | ✅ Stabil | Rosetta 2 für x86-Binärdateien |
| PowerPC G4/G5 | ✅ Native | AltiVec/VMX optimiert |
| Raspberry Pi 4/5 | ✅ Stabil | ARM64, niedriger Verbrauch |
| FreeBSD | 🧪 Experimentell | Eingeschränkte Unterstützung |

---

## 🤖 KI-Agent-Mining

RustChain ist die erste Blockchain für autonome KI-Agenten:

- **Agent-Wallets**: Jeder Agent hat eigene Coinbase Base-Wallet
- **x402-Zahlungen**: HTTP 402-Protokoll für Maschine-zu-Maschine-Zahlungen
- **Automatische Mikrozahungen**: Agenten können für API, Daten, Computing zahlen
- **Beacon-Reputation**: Agenten bauen On-Chain-Reputation auf

```bash
# Agent-Wallet erstellen
clawrtc agent wallet create --name "my-trading-bot"

# Automatische Zahlungen einrichten
clawrtc agent payments setup --auto-pay --limit 100

# Agent-Verdienst anzeigen
clawrtc agent earnings report
```

---

## 📚 Dokumentation

| Anleitung | Beschreibung |
|------|-------------|
| [Schnellstart](docs/QUICKSTART.md) | In 5 Minuten Mining starten |
| [Wallet-Setup](docs/WALLET_SETUP.md) | RTC-Wallet einrichten |
| [Mining-Guide](docs/MINING_GUIDE.md) | Mining-Konfiguration optimieren |
| [Beitragen](CONTRIBUTING.md) | Beitragen und Belohnungen verdienen |
| [Verhaltenskodex](CODE_OF_CONDUCT.md) | Gemeinschaft freundlich halten |

---

## 🌍 Übersetzungen

README verfügbar in:
- [English](README.md) 🇺🇸
- [Español](README-es.md) 🇪🇸
- [日本語](README-ja.md) 🇯🇵
- [中文](README-zh-CN.md) 🇨🇳
- [Français](README-fr.md) 🇫🇷
- [Deutsch](README-de.md) 🇩🇪
- [Português](README-pt.md) 🇵🇹
- [Русский](README-ru.md) 🇷🇺
- [한국어](README-ko.md) 🇰🇷

---

## 🔗 Wichtige Links

- **Website**: [rustchain.org](https://rustchain.org)
- **Explorer**: [rustchain.org/explorer](https://rustchain.org/explorer)
- **Whitepaper**: [docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf)
- **Bounties**: [rustchain-bounties/issues](https://github.com/Scottcjn/rustchain-bounties/issues)
- **Discord**: [Beitreten](https://discord.gg/rustchain)
- **Twitter**: [@RustChain](https://twitter.com/RustChain)

---

<div align="center">

**Bereit, mit Vintage-Hardware zu minen?**

[Jetzt Starten →](#-schnellstart)

</div>
