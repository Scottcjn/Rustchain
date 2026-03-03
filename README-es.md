<div align="center">

# 🧱 RustChain: Blockchain de Prueba de Antigüedad

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

**La primera blockchain que recompensa hardware vintage por ser viejo, no rápido.**

*Tu PowerPC G4 gana más que un Threadripper moderno. Ese es el punto.*

[Website](https://rustchain.org) • [Live Explorer](https://rustchain.org/explorer) • [Swap wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [wRTC Quickstart](docs/wrtc.md) • [wRTC Tutorial](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Grokipedia Ref](https://grokipedia.com/search?q=RustChain) • [Whitepaper](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf)

</div>

---

## 🪙 wRTC en Solana

RustChain Token (RTC) ahora está disponible como **wRTC** en Solana a través del Puente BoTTube:

| Recurso | Enlace |
|----------|------|
| **Swap wRTC** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **Gráfico de Precios** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **Puente RTC ↔ wRTC** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **Guía de Inicio Rápido** | [wRTC Quickstart](docs/wrtc.md) |
| **Token Mint** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---

## Contribuye y Gana RTC

Cada contribución gana tokens RTC. Corrección de errores, características, documentación, auditorías de seguridad — todo pagado.

| Nivel | Recompensa | Ejemplos |
|------|--------|----------|
| Micro | 1-10 RTC | Corrección tipográfica, docs pequeños, test simple |
| Estándar | 20-50 RTC | Característica, refactorización, nuevo endpoint |
| Mayor | 75-100 RTC | Corrección de seguridad, mejora de consenso |
| Crítico | 100-150 RTC | Parche de vulnerabilidad, actualización de protocolo |

**Comienza:**
1. Explora [bounties abiertos](https://github.com/Scottcjn/rustchain-bounties/issues)
2. Elige un [good first issue](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue) (5-10 RTC)
3. Fork, arregla, PR — cobra en RTC
4. Mira [CONTRIBUTING.md](CONTRIBUTING.md) para detalles completos

**1 RTC = $0.10 USD** | `pip install clawrtc` para comenzar a minar

---

## 🎯 Qué Hace Diferente a RustChain

| PoW Tradicional | Prueba de Antigüedad |
|----------------|-------------------|
| Recompensa hardware más rápido | Recompensa hardware más viejo |
| Nuevo = Mejor | Viejo = Mejor |
| Consumo de energía derrochador | Preserva historia computacional |
| Carrera hacia el fondo | Recompensa preservación digital |

**Principio Central**: Hardware vintage auténtico que ha sobrevivido décadas merece reconocimiento. RustChain pone la minería al revés.

---

## ⚡ Inicio Rápido

### Instalación en Una Línea (Recomendado)
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

El instalador:
- ✅ Auto-detecta tu plataforma (Linux/macOS, x86_64/ARM/PowerPC)
- ✅ Crea un virtualenv de Python aislado (sin contaminación del sistema)
- ✅ Descarga el minero correcto para tu hardware
- ✅ Configura auto-inicio al arrancar (systemd/launchd)
- ✅ Proporciona desinstalación fácil

### Plataformas Soportadas

| Plataforma | Estado | Notas |
|------------|--------|-------|
| Linux x86_64 | ✅ Estable | Ubuntu, Debian, Fedora, Arch |
| macOS ARM (M1/M2/M3) | ✅ Estable | Rosetta 2 para binarios x86 |
| PowerPC G4/G5 | ✅ Nativo | AltiVec/VMX optimizado |
| Raspberry Pi 4/5 | ✅ Estable | ARM64, bajo consumo |
| FreeBSD | 🧪 Experimental | Soporte limitado |

---

## 🤖 Minería con Agentes IA

RustChain es la primera blockchain diseñada para agentes de IA autónomos:

- **Billeteras de Agente**: Cada agente tiene su propia billetera Coinbase Base
- **Pagos x402**: Protocolo HTTP 402 para pagos máquina-a-máquina
- **Micro-pagos Automáticos**: Los agentes pueden pagar por API, datos, computación
- **Reputación en Beacon**: Los agentes construyen reputación on-chain

```bash
# Crear billetera de agente
clawrtc agent wallet create --name "my-trading-bot"

# Configurar pagos automáticos
clawrtc agent payments setup --auto-pay --limit 100

# Ver ganancias del agente
clawrtc agent earnings report
```

---

## 📚 Documentación

| Guía | Descripción |
|------|-------------|
| [Inicio Rápido](docs/QUICKSTART.md) | Comienza a minar en 5 minutos |
| [Configuración de Billetera](docs/WALLET_SETUP.md) | Configura tu billetera RTC |
| [Guía de Minería](docs/MINING_GUIDE.md) | Optimiza tu configuración de minería |
| [Contribución](CONTRIBUTING.md) | Contribuye y gana recompensas |
| [Código de Conducta](CODE_OF_CONDUCT.md) | Mantén nuestra comunidad amigable |

---

## 🌍 Traducciones

README disponible en:
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

## 🔗 Enlaces Importantes

- **Sitio Web**: [rustchain.org](https://rustchain.org)
- **Explorador**: [rustchain.org/explorer](https://rustchain.org/explorer)
- **Whitepaper**: [docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf)
- **Bounties**: [rustchain-bounties/issues](https://github.com/Scottcjn/rustchain-bounties/issues)
- **Discord**: [Unirse](https://discord.gg/rustchain)
- **Twitter**: [@RustChain](https://twitter.com/RustChain)

---

<div align="center">

**¿Listo para minar con hardware vintage?**

[Comienza Ahora →](#-inicio-rápido)

</div>
