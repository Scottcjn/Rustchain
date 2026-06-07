# RustChain-Dokumentation

> **RustChain** ist eine Proof-of-Antiquity-Blockchain, die ältere Hardware mit höheren Mining-Multiplikatoren belohnt. Das Netzwerk nutzt sechs Hardware-Fingerprint-Prüfungen, um zu verhindern, dass VMs und Emulatoren Rewards erhalten.

## Schnellzugriff

| Dokument | Beschreibung |
|----------|--------------|
| **[Entwickler-Tutorial](../RUSTCHAIN_DEVELOPER_TUTORIAL.md)** | Umfassender Leitfaden für Setup, Mining, Transaktionen und Beispiele |
| [Protokollspezifikation](../PROTOCOL.md) | Vollständiges RIP-200-Konsensprotokoll |
| [Mechanismus-Spezifikation und Falsifikationsmatrix](../MECHANISM_SPEC_AND_FALSIFICATION_MATRIX.md) | Eine kompakte Zuordnung von Behauptungen, Tests und Abbruchbedingungen |
| [API-Referenz](../API.md) | Alle Endpunkte mit curl-Beispielen |
| [Glossar](../GLOSSARY.md) | Begriffe und Definitionen |
| [Tokenomics](../tokenomics_v1.md) | RTC-Angebot und Verteilungsstruktur |
| [FAQ und Troubleshooting](../FAQ_TROUBLESHOOTING.md) | Häufige Setup- und Laufzeitprobleme mit Wiederherstellungsschritten |
| [Wallet-Benutzerhandbuch](../WALLET_USER_GUIDE.md) | Wallet-Grundlagen, Balance-Abfragen und sichere Bedienung |
| [Beitragsleitfaden](../CONTRIBUTING.md) | Contribution-Workflow, PR-Checkliste und Hinweise zur Bounty-Einreichung |
| [Reward-Analytics-Dashboard](../REWARD_ANALYTICS_DASHBOARD.md) | Diagramme und API für RTC-Reward-Transparenz |
| [Cross-Node-Sync-Validator](../CROSS_NODE_SYNC_VALIDATOR.md) | Konsistenzprüfungen über mehrere Nodes und Abweichungsberichte |
| [Discord-Leaderboard-Bot](../DISCORD_LEADERBOARD_BOT.md) | Webhook-Bot-Setup und Nutzung |
| [Japanischer Quickstart](../ja/README.md) | Community-gepflegter japanischer Quickstart-Leitfaden |

## Live-Netzwerk

- **Primärer Node**: `https://rustchain.org`
- **Explorer**: `https://rustchain.org/explorer`
- **Health Check**: `curl -sk https://rustchain.org/health`
- **Netzwerkstatus-Seite**: `docs/network-status.html` (Status-Dashboard, das über GitHub Pages gehostet werden kann)

## Aktuellen Status prüfen

```bash
# Node-Zustand prüfen
curl -sk https://rustchain.org/health | jq .

# Aktive Miner auflisten
curl -sk https://rustchain.org/api/miners | jq .

# Aktuelle Epoch-Informationen
curl -sk https://rustchain.org/epoch | jq .
```

## Architekturüberblick

```text
+-----------------+     +------------------+     +-----------------+
|  Vintage Miner  |---->| Attestation Node |---->|  Ergo Anchor    |
|  (G4/G5/SPARC)  |     |  (rustchain.org) |     | (Immutability)  |
+-----------------+     +------------------+     +-----------------+
        |                        |
        | Hardware Fingerprint   | Epoch Settlement
        | (6 checks)             | Hash
        v                        v
   +---------+              +---------+
   | RTC     |              | Ergo    |
   | Rewards |              | Chain   |
   +---------+              +---------+
```

## Erste Schritte

1. **Prüfen, ob deine Hardware qualifiziert ist**: siehe [CPU Antiquity Guide](../../CPU_ANTIQUITY_SYSTEM.md).
2. **Miner installieren**: siehe [INSTALL.md](../../INSTALL.md).
3. **Wallet registrieren**: Reiche eine Attestation ein, um RTC zu verdienen.

## Bounties

Aktive Bounties: [github.com/Scottcjn/rustchain-bounties](https://github.com/Scottcjn/rustchain-bounties)

---
*Diese Dokumentation wird von der RustChain-Community gepflegt.*
