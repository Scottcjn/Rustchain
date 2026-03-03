<div align="center">

# 🧱 RustChain : Blockchain de Preuve d'Antiquité

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

**La première blockchain qui récompense le matériel vintage pour être ancien, pas rapide.**

*Votre PowerPC G4 gagne plus qu'un Threadripper moderne. C'est le but.*

[Website](https://rustchain.org) • [Live Explorer](https://rustchain.org/explorer) • [Swap wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [wRTC Quickstart](docs/wrtc.md) • [wRTC Tutorial](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Grokipedia Ref](https://grokipedia.com/search?q=RustChain) • [Whitepaper](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf)

</div>

---

## 🪙 wRTC sur Solana

Le token RustChain (RTC) est maintenant disponible en tant que **wRTC** sur Solana via le pont BoTTube :

| Ressource | Lien |
|----------|------|
| **Swap wRTC** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **Graphique de Prix** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **Pont RTC ↔ wRTC** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **Guide de Démarrage** | [wRTC Quickstart](docs/wrtc.md) |
| **Token Mint** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---

## Contribuez et Gagnez des RTC

Chaque contribution rapporte des tokens RTC. Corrections de bugs, fonctionnalités, docs, audits de sécurité — tout est payé.

| Niveau | Récompense | Exemples |
|------|--------|----------|
| Micro | 1-10 RTC | Correction typo, petits docs, test simple |
| Standard | 20-50 RTC | Fonctionnalité, refactorisation, nouvel endpoint |
| Majeur | 75-100 RTC | Correction sécurité, amélioration consensus |
| Critique | 100-150 RTC | Patch vulnérabilité, mise à jour protocole |

**Commencez :**
1. Parcourez les [bounties ouverts](https://github.com/Scottcjn/rustchain-bounties/issues)
2. Choisissez un [good first issue](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue) (5-10 RTC)
3. Fork, corrigez, PR — soyez payé en RTC
4. Voyez [CONTRIBUTING.md](CONTRIBUTING.md) pour tous les détails

**1 RTC = $0.10 USD** | `pip install clawrtc` pour commencer à miner

---

## 🎯 Ce Qui Rend RustChain Différent

| PoW Traditionnel | Preuve d'Antiquité |
|----------------|-------------------|
| Récompense le matériel le plus rapide | Récompense le matériel le plus ancien |
| Nouveau = Mieux | Ancien = Mieux |
| Consommation énergétique gaspillée | Préserve l'histoire informatique |
| Course vers le bas | Récompense la préservation numérique |

**Principe Central** : Le matériel vintage authentique ayant survécu des décennies mérite reconnaissance. RustChain inverse le minage.

---

## ⚡ Démarrage Rapide

### Installation en Une Ligne (Recommandé)
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

L'installateur :
- ✅ Détecte automatiquement votre plateforme (Linux/macOS, x86_64/ARM/PowerPC)
- ✅ Crée un virtualenv Python isolé (pas de pollution système)
- ✅ Télécharge le mineur correct pour votre matériel
- ✅ Configure le démarrage automatique (systemd/launchd)
- ✅ Fournit une désinstallation facile

### Plateformes Supportées

| Plateforme | Statut | Notes |
|------------|--------|-------|
| Linux x86_64 | ✅ Stable | Ubuntu, Debian, Fedora, Arch |
| macOS ARM (M1/M2/M3) | ✅ Stable | Rosetta 2 pour binaires x86 |
| PowerPC G4/G5 | ✅ Natif | AltiVec/VMX optimisé |
| Raspberry Pi 4/5 | ✅ Stable | ARM64, faible consommation |
| FreeBSD | 🧪 Expérimental | Support limité |

---

## 🤖 Minage avec Agents IA

RustChain est la première blockchain conçue pour les agents IA autonomes :

- **Portefeuilles d'Agent** : Chaque agent a son propre portefeuille Coinbase Base
- **Paiements x402** : Protocole HTTP 402 pour paiements machine-à-machine
- **Micro-paiements Automatiques** : Les agents peuvent payer pour API, données, calcul
- **Réputation Beacon** : Les agents construisent une réputation on-chain

```bash
# Créer un portefeuille d'agent
clawrtc agent wallet create --name "my-trading-bot"

# Configurer paiements automatiques
clawrtc agent payments setup --auto-pay --limit 100

# Voir gains de l'agent
clawrtc agent earnings report
```

---

## 📚 Documentation

| Guide | Description |
|------|-------------|
| [Démarrage Rapide](docs/QUICKSTART.md) | Commencez à miner en 5 minutes |
| [Configuration Portefeuille](docs/WALLET_SETUP.md) | Configurez votre portefeuille RTC |
| [Guide de Minage](docs/MINING_GUIDE.md) | Optimisez votre configuration |
| [Contribution](CONTRIBUTING.md) | Contribuez et gagnez des récompenses |
| [Code de Conduite](CODE_OF_CONDUCT.md) | Gardez notre communauté amicale |

---

## 🌍 Traductions

README disponible en :
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

## 🔗 Liens Importants

- **Site Web** : [rustchain.org](https://rustchain.org)
- **Explorateur** : [rustchain.org/explorer](https://rustchain.org/explorer)
- **Whitepaper** : [docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf)
- **Bounties** : [rustchain-bounties/issues](https://github.com/Scottcjn/rustchain-bounties/issues)
- **Discord** : [Rejoindre](https://discord.gg/rustchain)
- **Twitter** : [@RustChain](https://twitter.com/RustChain)

---

<div align="center">

**Prêt à miner avec du matériel vintage ?**

[Commencez Maintenant →](#-démarrage-rapide)

</div>
