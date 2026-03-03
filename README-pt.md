<div align="center">

# 🧱 RustChain: Blockchain de Prova de Antiguidade

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

**A primeira blockchain que recompensa hardware antigo por ser velho, não rápido.**

*Seu PowerPC G4 ganha mais que um Threadripper moderno. Esse é o ponto.*

[Website](https://rustchain.org) • [Live Explorer](https://rustchain.org/explorer) • [Swap wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [wRTC Quickstart](docs/wrtc.md) • [wRTC Tutorial](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Grokipedia Ref](https://grokipedia.com/search?q=RustChain) • [Whitepaper](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf)

</div>

---

## 🪙 wRTC na Solana

O token RustChain (RTC) está agora disponível como **wRTC** na Solana via Ponte BoTTube:

| Recurso | Link |
|----------|------|
| **Swap wRTC** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **Gráfico de Preços** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **Ponte RTC ↔ wRTC** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **Guia de Início Rápido** | [wRTC Quickstart](docs/wrtc.md) |
| **Token Mint** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---

## Contribua e Ganhe RTC

Cada contribuição ganha tokens RTC. Correções de bugs, recursos, docs, auditorias de segurança — tudo pago.

| Nível | Recompensa | Exemplos |
|------|--------|----------|
| Micro | 1-10 RTC | Correção de erro, docs pequenos, teste simples |
| Padrão | 20-50 RTC | Recurso, refatoração, novo endpoint |
| Principal | 75-100 RTC | Correção de segurança, melhoria de consenso |
| Crítico | 100-150 RTC | Patch de vulnerabilidade, upgrade de protocolo |

**Comece:**
1. Navegue por [bounties abertos](https://github.com/Scottcjn/rustchain-bounties/issues)
2. Escolha um [good first issue](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue) (5-10 RTC)
3. Fork, corrija, PR — receba em RTC
4. Veja [CONTRIBUTING.md](CONTRIBUTING.md) para detalhes completos

**1 RTC = $0.10 USD** | `pip install clawrtc` para começar a minerar

---

## 🎯 O Que Torna RustChain Diferente

| PoW Tradicional | Prova de Antiguidade |
|----------------|-------------------|
| Recompensa hardware mais rápido | Recompensa hardware mais antigo |
| Novo = Melhor | Antigo = Melhor |
| Consumo de energia desperdiçado | Preserva história da computação |
| Corrida para o fundo | Recompensa preservação digital |

**Princípio Central**: Hardware vintage autêntico que sobreviveu décadas merece reconhecimento. RustChain inverte a mineração.

---

## ⚡ Início Rápido

### Instalação em Uma Linha (Recomendado)
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

O instalador:
- ✅ Detecta automaticamente sua plataforma (Linux/macOS, x86_64/ARM/PowerPC)
- ✅ Cria virtualenv Python isolado (sem poluição do sistema)
- ✅ Baixa o minerador correto para seu hardware
- ✅ Configura auto-início na inicialização (systemd/launchd)
- ✅ Fornece desinstalação fácil

### Plataformas Suportadas

| Plataforma | Status | Notas |
|------------|--------|-------|
| Linux x86_64 | ✅ Estável | Ubuntu, Debian, Fedora, Arch |
| macOS ARM (M1/M2/M3) | ✅ Estável | Rosetta 2 para binários x86 |
| PowerPC G4/G5 | ✅ Nativo | AltiVec/VMX otimizado |
| Raspberry Pi 4/5 | ✅ Estável | ARM64, baixo consumo |
| FreeBSD | 🧪 Experimental | Suporte limitado |

---

## 🤖 Mineração com Agentes de IA

RustChain é a primeira blockchain projetada para agentes de IA autônomos:

- **Carteiras de Agente**: Cada agente tem sua própria carteira Coinbase Base
- **Pagamentos x402**: Protocolo HTTP 402 para pagamentos máquina-a-máquina
- **Micro-pagamentos Automáticos**: Agentes podem pagar por API, dados, computação
- **Reputação Beacon**: Agentes constroem reputação on-chain

```bash
# Criar carteira de agente
clawrtc agent wallet create --name "my-trading-bot"

# Configurar pagamentos automáticos
clawrtc agent payments setup --auto-pay --limit 100

# Ver ganhos do agente
clawrtc agent earnings report
```

---

## 📚 Documentação

| Guia | Descrição |
|------|-------------|
| [Início Rápido](docs/QUICKSTART.md) | Comece a minerar em 5 minutos |
| [Configuração de Carteira](docs/WALLET_SETUP.md) | Configure sua carteira RTC |
| [Guia de Mineração](docs/MINING_GUIDE.md) | Otimize sua configuração de mineração |
| [Contribuição](CONTRIBUTING.md) | Contribua e ganhe recompensas |
| [Código de Conduta](CODE_OF_CONDUCT.md) | Mantenha nossa comunidade amigável |

---

## 🌍 Traduções

README disponível em:
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

## 🔗 Links Importantes

- **Site**: [rustchain.org](https://rustchain.org)
- **Explorador**: [rustchain.org/explorer](https://rustchain.org/explorer)
- **Whitepaper**: [docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf)
- **Bounties**: [rustchain-bounties/issues](https://github.com/Scottcjn/rustchain-bounties/issues)
- **Discord**: [Entrar](https://discord.gg/rustchain)
- **Twitter**: [@RustChain](https://twitter.com/RustChain)

---

<div align="center">

**Pronto para minerar com hardware vintage?**

[Comece Agora →](#-início-rápido)

</div>
