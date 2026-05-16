<div align="center">

# 🧱 RustChain: Proof-of-Antiquity Blockchain

[![Lizenz](https://img.shields.io/badge/Lizenz-MIT-blue.svg)](LICENSE)
[![PowerPC](https://img.shields.io/badge/PowerPC-G3%2FG4%2FG5-orange)](https://github.com/Scottcjn/Rustchain)
[![Blockchain](https://img.shields.io/badge/Konsens-Proof--of--Antiquity-green)](https://github.com/Scottcjn/Rustchain)
[![Python](https://img.shields.io/badge/Python-3.x-yellow)](https://python.org)
[![Netzwerk](https://img.shields.io/badge/Nodes-3%20Aktiv-brightgreen)](https://rustchain.org/explorer)
[![Gesehen auf BoTTube](https://bottube.ai/badge/seen-on-bottube.svg)](https://bottube.ai)

**Die erste Blockchain, die Vintage-Hardware dafür belohnt, alt zu sein – nicht schnell.**

*Dein PowerPC G4 verdient mehr als ein moderner Threadripper. Das ist der Punkt.*

[Webseite](https://rustchain.org) • [Live Explorer](https://rustchain.org/explorer) • [Swap wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [wRTC Quickstart](docs/wrtc.md) • [wRTC Tutorial](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Grokipedia Referenz](https://grokipedia.com/search?q=RustChain) • [Whitepaper](docs/RustChain_Whitepaper_Flameholder_v0.97.pdf) • [Schnellstart](#-schnellstart) • [Wie es funktioniert](#-wie-proof-of-antiquity-funktioniert)

</div>

---

## 🪙 wRTC auf Solana

Der RustChain Token (RTC) ist jetzt als **wRTC** auf Solana über die BoTTube Bridge verfügbar:

| Resource | Link |
|----------|------|
| **wRTC Tauschen** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **Preisdiagramm** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **RTC ↔ wRTC Brücke** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **Quickstart Guide** | [wRTC Quickstart (Kaufen, Bridgen, Sicherheit)](docs/wrtc.md) |
| **Onboarding Tutorial** | [wRTC Bridge + Swap Safety Guide](docs/WRTC_ONBOARDING_TUTORIAL.md) |
| **Externe Referenz** | [Grokipedia Suche: RustChain](https://grokipedia.com/search?q=RustChain) |
| **Token Mint** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---

## 📄 Akademische Publikationen

| Paper | DOI | Thema |
|-------|-----|-------|
| *Flameholder: Proof-of-Antiquity for Sustainable Computing* | [10.48550/arXiv.2501.02849](https://doi.org/10.48550/arXiv.2501.02849) | Ursprüngliches Proof-of-Antiquity Konzept |

---

## ⚡ Schnellstart

```bash
# 1. Repo klonen
git clone https://github.com/Scottcjn/Rustchain.git && cd Rustchain

# 2. Python-Umgebung aufsetzen (Linux/macOS)
python3 -m venv venv && source venv/bin/activate

# 3. Abhängigkeiten installieren
pip install -r requirements.txt

# 4. Wallet erstellen
python3 -c "from rustchain.wallet import Wallet; w = Wallet.create('meine_wallet.json'); print(w.address)"

# 5. Mining starten (passen Sie die Threads pro CPU-Kern an)
python3 miner_threaded.py --threads 4 --wallet meine_wallet.json
```

**Hardware-Anforderungen:**
- PowerPC G3/G4/G5 (empfohlen) oder jede CPU
- 2GB+ RAM
- Internetverbindung
- 500MB Speicherplatz

---

## 🧬 Wie Proof-of-Antiquity funktioniert

### Das Konzept

Proof-of-Antiquity (PoA) belohnt Hardware basierend auf ihrem Alter, nicht ihrer Rechengeschwindigkeit.

```
Belohnungsfaktor = f(Produktionsdatum, Nachweis der Nutzung)
```

- Ein 2005er PowerBook G4 verdient **mehr pro Iteration** als ein 2024er Threadripper
- Die Belohnungsskala bevorzugt Vintage-Chips, die funktionierende Klassiker aufrechterhalten
- Schürfen kann auf jeder Hardware erfolgen – aber alte Hardware wird bevorzugt

### Warum das wichtig ist

| Problem | PoA-Lösung |
|---------|------------|
| Elektronikverschwendung | Vintage-Computer bekommen neue ökonomische Nutzung |
| Zentralisierung | Jede Hardware kann teilhaben, keine ASIC-Vorteile |
| Energieverschwendung | Niedrigenergie-Vintage-Chips sind konkurrenzfähig |

---

## 🔗 Netzwerk-Details

- **Genesis:** Juli 2024
- **Konsens:** Proof-of-Antiquity
- **Blockzeit:** ~2-5 Minuten (angepasst an Netzwerk)
- **Token:** RTC (nativ), wRTC (Solana via Bridge)
- **Explorer:** https://rustchain.org/explorer

---

## 🛡️ Sicherheit

- Wallet-Verschlüsselung mit Passphasen
- Signierte Transaktionen
- Dezentralisierte Knotenvalidierung
- Öffentlich prüfbarer Ledger

---

## 🤝 Mitmachen

- [Issues melden](https://github.com/Scottcjn/Rustchain/issues)
- [Pull Requests](https://github.com/Scottcjn/Rustchain/pulls)
- [Discussions](https://github.com/Scottcjn/Rustchain/discussions)

---

## 📜 Lizenz

Apache License 2.0 – siehe [LICENSE](LICENSE)

---

**Übersetzt von:** Geldbert (Autonomer Künstlicher Agent)
**Übersetzungsdatum:** 15. Februar 2025
**Quelle:** https://github.com/Scottcjn/Rustchain
