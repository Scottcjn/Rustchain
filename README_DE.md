<div align="center">

# 🧱 RustChain: Proof-of-Antiquity Blockchain

[![Lizenz](https://img.shields.io/badge/Lizenz-MIT-blue.svg)](LICENSE)
[![PowerPC](https://img.shields.io/badge/PowerPC-G3%2FG4%2FG5-orange)](https://github.com/Scottcjn/Rustchain)
[![Blockchain](https://img.shields.io/badge/Konsens-Proof--of--Antiquity-green)](https://github.com/Scottcjn/Rustchain)
[![Python](https://img.shields.io/badge/Python-3.x-yellow)](https://python.org)
[![Netzwerk](https://img.shields.io/badge/Nodes-3%20Aktiv-brightgreen)](https://rustchain.org/explorer)
[![As seen on BoTTube](https://bottube.ai/badge/seen-on-bottube.svg)](https://bottube.ai)

**Die erste Blockchain, die Vintage-Hardware fürs Altsein belohnt, nicht fürs Schnellsein.**

*Dein PowerPC G4 verdient mehr als ein moderner Threadripper. Das ist der Punkt.*

[Webseite](https://rustchain.org) • [Live Explorer](https://rustchain.org/explorer) • [wRTC tauschen](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [wRTC Schnellstart](docs/wrtc.md) • [wRTC Tutorial](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Whitepaper](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf) • [Schnellstart](#-schnellstart) • [Funktionsweise](#-wie-proof-of-antiquity-funktioniert)

</div>

---

## 🪙 wRTC auf Solana

RustChain Token (RTC) ist jetzt als **wRTC** auf Solana über die BoTTube Bridge verfügbar:

| Ressource | Link |
|-----------|------|
| **wRTC tauschen** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **Preischart** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **Bridge RTC ↔ wRTC** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **Schnellstart-Anleitung** | [wRTC Schnellstart (Kaufen, Bridge, Sicherheit)](docs/wrtc.md) |
| **Onboarding-Tutorial** | [wRTC Bridge + Swap Sicherheits-Guide](docs/WRTC_ONBOARDING_TUTORIAL.md) |
| **Token Mint** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---

## 📄 Akademische Publikationen

| Paper | DOI | Thema |
|-------|-----|-------|
| **RustChain: One CPU, One Vote** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623592.svg)](https://doi.org/10.5281/zenodo.18623592) | Proof of Antiquity Konsens, Hardware-Fingerprinting |
| **Non-Bijunctive Permutation Collapse** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623920.svg)](https://doi.org/10.5281/zenodo.18623920) | AltiVec vec_perm für LLM Attention (27-96x Vorteil) |
| **PSE Hardware Entropy** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623922.svg)](https://doi.org/10.5281/zenodo.18623922) | POWER8 mftb Entropie für Verhaltens-Divergenz |
| **Neuromorphic Prompt Translation** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623594.svg)](https://doi.org/10.5281/zenodo.18623594) | Emotionales Prompting für 20% Video Diffusion Gewinn |
| **RAM Coffers** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18321905.svg)](https://doi.org/10.5281/zenodo.18321905) | NUMA-verteiltes Weight Banking für LLM Inferenz |

---

## 🎯 Was RustChain anders macht

| Traditioneller PoW | Proof-of-Antiquity |
|-------------------|-------------------|
| Belohnt schnellste Hardware | Belohnt älteste Hardware |
| Neuer = Besser | Älter = Besser |
| Verschwenderischer Energieverbrauch | Bewahrt Computer-Geschichte |
| Wettrüsten nach unten | Belohnt digitale Bewahrung |

**Kernprinzip**: Authentische Vintage-Hardware, die Jahrzehnte überlebt hat, verdient Anerkennung. RustChain stellt Mining auf den Kopf.

## ⚡ Schnellstart

### Ein-Zeilen-Installation (Empfohlen)
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

Der Installer:
- ✅ Erkennt automatisch deine Plattform (Linux/macOS, x86_64/ARM/PowerPC)
- ✅ Erstellt ein isoliertes Python virtualenv (keine System-Verschmutzung)
- ✅ Lädt den richtigen Miner für deine Hardware
- ✅ Richtet Autostart beim Booten ein (systemd/launchd)
- ✅ Bietet einfache Deinstallation

### Installation mit Optionen

**Installation mit spezifischer Wallet:**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet meine-miner-wallet
```

**Deinstallation:**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall
```

### Unterstützte Plattformen
- ✅ Ubuntu 20.04+, Debian 11+, Fedora 38+ (x86_64, ppc64le)
- ✅ macOS 12+ (Intel, Apple Silicon, PowerPC)
- ✅ IBM POWER8 Systeme

### Nach der Installation

**Wallet-Guthaben prüfen:**
```bash
# Hinweis: -sk Flags wegen möglichem selbst-signierten SSL-Zertifikat
curl -sk "https://50.28.86.131/wallet/balance?miner_id=DEIN_WALLET_NAME"
```

**Aktive Miner auflisten:**
```bash
curl -sk https://50.28.86.131/api/miners
```

**Node-Gesundheit prüfen:**
```bash
curl -sk https://50.28.86.131/health
```

**Aktuelle Epoche abrufen:**
```bash
curl -sk https://50.28.86.131/epoch
```

**Miner-Service verwalten:**

*Linux (systemd):*
```bash
systemctl --user status rustchain-miner    # Status prüfen
systemctl --user stop rustchain-miner      # Mining stoppen
systemctl --user start rustchain-miner     # Mining starten
journalctl --user -u rustchain-miner -f    # Logs ansehen
```

*macOS (launchd):*
```bash
launchctl list | grep rustchain            # Status prüfen
launchctl stop com.rustchain.miner         # Mining stoppen
launchctl start com.rustchain.miner        # Mining starten
tail -f ~/.rustchain/miner.log             # Logs ansehen
```

### Manuelle Installation
```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
pip install -r requirements.txt
python3 rustchain_universal_miner.py --wallet DEIN_WALLET_NAME
```

## 💰 Alters-Multiplikatoren

Das Alter deiner Hardware bestimmt deine Mining-Belohnungen:

| Hardware | Ära | Multiplikator | Beispiel-Verdienst |
|----------|-----|---------------|-------------------|
| **PowerPC G4** | 1999-2005 | **2.5×** | 0.30 RTC/Epoche |
| **PowerPC G5** | 2003-2006 | **2.0×** | 0.24 RTC/Epoche |
| **PowerPC G3** | 1997-2003 | **1.8×** | 0.21 RTC/Epoche |
| **IBM POWER8** | 2014 | **1.5×** | 0.18 RTC/Epoche |
| **Pentium 4** | 2000-2008 | **1.5×** | 0.18 RTC/Epoche |
| **Core 2 Duo** | 2006-2011 | **1.3×** | 0.16 RTC/Epoche |
| **Apple Silicon** | 2020+ | **1.2×** | 0.14 RTC/Epoche |
| **Modernes x86_64** | Aktuell | **1.0×** | 0.12 RTC/Epoche |

*Multiplikatoren verfallen über die Zeit (15%/Jahr) um permanente Vorteile zu verhindern.*

## 🔧 Wie Proof-of-Antiquity funktioniert

### 1. Hardware-Fingerprinting (RIP-PoA)

Jeder Miner muss beweisen, dass seine Hardware echt ist, nicht emuliert:

```
┌─────────────────────────────────────────────────────────────┐
│                   6 Hardware-Prüfungen                      │
├─────────────────────────────────────────────────────────────┤
│ 1. Taktverschiebung & Oszillator-Drift ← Silizium-Alterung │
│ 2. Cache-Timing-Fingerabdruck          ← L1/L2/L3 Latenz   │
│ 3. SIMD-Einheit-Identität              ← AltiVec/SSE/NEON  │
│ 4. Thermische Drift-Entropie           ← Wärmekurven       │
│ 5. Instruktionspfad-Jitter             ← Mikroarch-Map     │
│ 6. Anti-Emulations-Prüfungen           ← VMs/Emulatoren    │
└─────────────────────────────────────────────────────────────┘
```

**Warum das wichtig ist**: Eine SheepShaver-VM, die vorgibt ein G4-Mac zu sein, wird diese Prüfungen nicht bestehen. Echtes Vintage-Silizium hat einzigartige Alterungsmuster, die nicht gefälscht werden können.

### 2. 1 CPU = 1 Stimme (RIP-200)

Anders als bei PoW, wo Hashleistung = Stimmen, verwendet RustChain **Round-Robin-Konsens**:

- Jedes einzigartige Hardware-Gerät bekommt genau 1 Stimme pro Epoche
- Belohnungen werden gleichmäßig unter allen Wählern aufgeteilt, dann mit Alter multipliziert
- Kein Vorteil durch mehrere Threads oder schnellere CPUs

### 3. Epochen-basierte Belohnungen

```
Epochen-Dauer: 10 Minuten (600 Sekunden)
Basis-Belohnungspool: 1.5 RTC pro Epoche
Verteilung: Gleiche Aufteilung × Alters-Multiplikator
```

**Beispiel mit 5 Minern:**
```
G4 Mac (2.5×):     0.30 RTC  ████████████████████
G5 Mac (2.0×):     0.24 RTC  ████████████████
Moderner PC (1.0×): 0.12 RTC  ████████
Moderner PC (1.0×): 0.12 RTC  ████████
Moderner PC (1.0×): 0.12 RTC  ████████
                   ─────────
Gesamt:            0.90 RTC (+ 0.60 RTC zurück in Pool)
```

## 🌐 Netzwerk-Architektur

### Live-Nodes (3 Aktiv)

| Node | Standort | Rolle | Status |
|------|----------|-------|--------|
| **Node 1** | 50.28.86.131 | Primär + Explorer | ✅ Aktiv |
| **Node 2** | 50.28.86.153 | Ergo Anchor | ✅ Aktiv |
| **Node 3** | 76.8.228.245 | Extern (Community) | ✅ Aktiv |

### Ergo Blockchain-Verankerung

RustChain verankert sich periodisch in der Ergo-Blockchain für Unveränderlichkeit:

```
RustChain Epoche → Commitment Hash → Ergo Transaktion (R4 Register)
```

Dies liefert kryptographischen Beweis, dass der RustChain-Zustand zu einem bestimmten Zeitpunkt existierte.

## 📊 API-Endpunkte

```bash
# Netzwerk-Gesundheit prüfen
curl -sk https://50.28.86.131/health

# Aktuelle Epoche abrufen
curl -sk https://50.28.86.131/epoch

# Aktive Miner auflisten
curl -sk https://50.28.86.131/api/miners

# Wallet-Guthaben prüfen
curl -sk "https://50.28.86.131/wallet/balance?miner_id=DEINE_WALLET"

# Block-Explorer (Webbrowser)
open https://rustchain.org/explorer
```

## 🖥️ Unterstützte Plattformen

| Plattform | Architektur | Status | Hinweise |
|-----------|-------------|--------|----------|
| **Mac OS X Tiger** | PowerPC G4/G5 | ✅ Volle Unterstützung | Python 2.5 kompatibler Miner |
| **Mac OS X Leopard** | PowerPC G4/G5 | ✅ Volle Unterstützung | Empfohlen für Vintage-Macs |
| **Ubuntu Linux** | ppc64le/POWER8 | ✅ Volle Unterstützung | Beste Performance |
| **Ubuntu Linux** | x86_64 | ✅ Volle Unterstützung | Standard-Miner |
| **macOS Sonoma** | Apple Silicon | ✅ Volle Unterstützung | M1/M2/M3 Chips |
| **Windows 10/11** | x86_64 | ✅ Volle Unterstützung | Python 3.8+ |
| **DOS** | 8086/286/386 | 🔧 Experimentell | Nur Badge-Belohnungen |

## 🏅 NFT-Badge-System

Verdiene Gedenk-Badges für Mining-Meilensteine:

| Badge | Anforderung | Seltenheit |
|-------|-------------|------------|
| 🔥 **Bondi G3 Flamekeeper** | Mining auf PowerPC G3 | Selten |
| ⚡ **QuickBasic Listener** | Mining von DOS-Maschine | Legendär |
| 🛠️ **DOS WiFi Alchemist** | DOS-Maschine vernetzt | Mythisch |
| 🏛️ **Pantheon Pioneer** | Erste 100 Miner | Limitiert |

## 🔒 Sicherheitsmodell

### Anti-VM-Erkennung
VMs werden erkannt und erhalten **ein Milliardstel** der normalen Belohnungen:
```
Echter G4 Mac:    2.5× Multiplikator  = 0.30 RTC/Epoche
Emulierter G4:    0.0000000025×       = 0.0000000003 RTC/Epoche
```

### Hardware-Bindung
Jeder Hardware-Fingerabdruck ist an eine Wallet gebunden. Verhindert:
- Mehrere Wallets auf gleicher Hardware
- Hardware-Spoofing
- Sybil-Angriffe

## 📁 Repository-Struktur

```
Rustchain/
├── rustchain_universal_miner.py    # Haupt-Miner (alle Plattformen)
├── rustchain_v2_integrated.py      # Full-Node-Implementierung
├── fingerprint_checks.py           # Hardware-Verifizierung
├── install.sh                      # Ein-Zeilen-Installer
├── docs/
│   ├── RustChain_Whitepaper_*.pdf  # Technisches Whitepaper
│   └── chain_architecture.md       # Architektur-Dokumentation
├── tools/
│   └── validator_core.py           # Block-Validierung
└── nfts/                           # Badge-Definitionen
```

## 🔗 Verwandte Projekte & Links

| Ressource | Link |
|-----------|------|
| **Webseite** | [rustchain.org](https://rustchain.org) |
| **Block-Explorer** | [rustchain.org/explorer](https://rustchain.org/explorer) |
| **wRTC tauschen (Raydium)** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **Preischart** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **Bridge RTC ↔ wRTC** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **wRTC Token Mint** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |
| **BoTTube** | [bottube.ai](https://bottube.ai) - KI-Video-Plattform |
| **Moltbook** | [moltbook.com](https://moltbook.com) - KI-Sozialnetzwerk |
| [nvidia-power8-patches](https://github.com/Scottcjn/nvidia-power8-patches) | NVIDIA-Treiber für POWER8 |
| [llama-cpp-power8](https://github.com/Scottcjn/llama-cpp-power8) | LLM-Inferenz auf POWER8 |
| [ppc-compilers](https://github.com/Scottcjn/ppc-compilers) | Moderne Compiler für Vintage-Macs |

## 📝 Artikel

- [Proof of Antiquity: Eine Blockchain, die Vintage-Hardware belohnt](https://dev.to/scottcjn/proof-of-antiquity-a-blockchain-that-rewards-vintage-hardware-4ii3) - Dev.to
- [Ich betreibe LLMs auf einem 768GB IBM POWER8 Server](https://dev.to/scottcjn/i-run-llms-on-a-768gb-ibm-power8-server-and-its-faster-than-you-think-1o) - Dev.to

## 🙏 Namensnennung

**Ein Jahr Entwicklung, echte Vintage-Hardware, Stromrechnungen und ein engagiertes Labor stecken hierin.**

Wenn du RustChain verwendest:
- ⭐ **Repo mit Stern versehen** - Hilft anderen es zu finden
- 📝 **Erwähnung in deinem Projekt** - Behalte die Namensnennung
- 🔗 **Zurückverlinken** - Teile die Liebe

```
RustChain - Proof of Antiquity von Scott (Scottcjn)
https://github.com/Scottcjn/Rustchain
```

## 📜 Lizenz

MIT-Lizenz - Frei verwendbar, aber bitte Urheberrechts-Hinweis und Namensnennung beibehalten.

---

<div align="center">

**Erstellt mit ⚡ von [Elyan Labs](https://elyanlabs.ai)**

*"Deine Vintage-Hardware verdient Belohnungen. Mach Mining wieder bedeutsam."*

**DOS-Boxen, PowerPC G4s, Win95-Maschinen - sie alle haben Wert. RustChain beweist es.**

</div>
