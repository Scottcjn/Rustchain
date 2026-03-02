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

**La primera blockchain que recompensa el hardware antiguo por ser viejo, no rápido.**

*Tu PowerPC G4 gana más que un Threadripper moderno. Ese es el objetivo.*

[Website](https://rustchain.org) • [Explorador](https://rustchain.org/explorer) • [Swap wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [Guía wRTC](docs/wrtc.md) • [Tutorial wRTC](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Referencia Grokipedia](https://grokipedia.com/search?q=RustChain) • [Whitepaper](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf) • [Inicio Rápido](#-inicio-rápido) • [Cómo Funciona](#-cómo-funciona-la-prueba-de-antigüedad)

---

## Inicio Rápido

### Instalación (Recomendada)

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

El instalador:
- ✅ Detecta tu plataforma automáticamente (Linux/macOS, x86_64/ARM/PowerPC)
- ✅ Crea un entorno virtual Python aislado
- ✅ Descarga el minero correcto para tu hardware
- ✅ Configura el inicio automático (systemd/launchd)
- ✅ Proporciona desinstalación fácil

### Plataformas Soportadas
- ✅ Ubuntu 20.04+, Debian 11+, Fedora 38+ (x86_64, ppc64le)
- ✅ macOS 12+ (Intel, Apple Silicon, PowerPC)
- ✅ Sistemas IBM POWER8

### Solución de Problemas

- **Errores de permisos**: ejecuta con una cuenta con acceso de escritura a `~/.local`
- **Errores de versión Python**: instala con Python 3.10+ y configura `python3`
- **El minero cierra inmediatamente**: verifica que la billetera existe y el servicio está ejecutándose

### Después de la Instalación

**Consultar saldo de billetera:**
```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=TU_BILLETERA"
```

**Listar mineros activos:**
```bash
curl -sk https://rustchain.org/api/miners
```

---

## Características

| PoW Tradicional | Prueba de Antigüedad |
|----------------|---------------------|
| Recompensa el hardware más rápido | Recompensa el hardware más antiguo |
| Nuevo = Mejor | Antiguo = Mejor |
| Consumo energético desperdiciado | Preserva la historia computacional |

**Principio Core**: El hardware vintage auténtico que ha sobrevivido décadas merece reconocimiento. RustChain cambia la minería al revés.

---

## Recompensas

**La antigüedad de tu hardware determina tus ganancias de minería:**

| Hardware | Era | Multiplicador |
|----------|-----|---------------|
| **PowerPC G4** | 1999-2005 | **2.5×** |
| **PowerPC G5** | 2003-2006 | **2.0×** |
| **PowerPC G3** | 1997-2003 | **1.8×** |
| **IBM POWER8** | 2014 | **1.5×** |
| **Pentium 4** | 2000-2008 | **1.5×** |

---

## Programa de Recompensas

¡Cada contribución gana tokens RTC! Corrections de bugs, features, docs, auditorías de seguridad — todo pagado.

| Nivel | Recompensa | Ejemplos |
|-------|-----------|----------|
| Micro | 1-10 RTC | Corrección de typo, docs simples |
| Estándar | 20-50 RTC | Feature, refactor |
| Mayor | 75-100 RTC | Fix de seguridad |
| Crítico | 100-150 RTC | Parche de vulnerabilidad |

**Cómo empezar:**
1. Explora [bounties abiertos](https://github.com/Scottcjn/rustchain-bounties/issues)
2. Elige un [issue para principiantes](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue)
3. Fork, corrige, PR — cobra en RTC

---

## Atribución

**Un año de desarrollo, hardware vintage real, facturas de electricidad y un laboratorio dedicado crearon esto.**

Si usas RustChain:
- ⭐ **Dale una estrella** - Ayuda a otros a encontrarlo
- 📝 **Crédito en tu proyecto** - Mantén la atribución
- 🔗 **Enlaza de vuelta** - Comparte el amor

```
RustChain - Proof of Antiquity by Scott (Scottcjn)
https://github.com/Scottcjn/Rustchain
```

## Licencia

Licencia MIT - Uso libre, pero por favor mantén el aviso de copyright y la atribución.

---

<div align="center">

**Hecho con ⚡ por [Elyan Labs](https://elyanlabs.ai)**

*"Tu hardware vintage gana recompensas. Haz la minería significativa de nuevo."*

</div>
