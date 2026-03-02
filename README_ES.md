[**English**](README.md) | **Español**

<div align="center">

# 🧱 RustChain: Blockchain de Prueba-de-Antigüedad

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

**La primera blockchain que recompensa el hardware vintage por ser antiguo, no rápido.**

*Tu PowerPC G4 gana más que un Threadripper moderno. Ese es el punto.*

[Sitio Web](https://rustchain.org) • [Explorador en Vivo](https://rustchain.org/explorer) • [Intercambiar wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [Guía Rápida wRTC](docs/wrtc.md) • [Tutorial wRTC](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Referencia Grokipedia](https://grokipedia.com/search?q=RustChain) • [Whitepaper](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf) • [Inicio Rápido](#-inicio-rápido) • [Cómo Funciona](#-cómo-funciona-la-prueba-de-antigüedad)

</div>

---

## 🪙 wRTC en Solana

El Token RustChain (RTC) ahora está disponible como **wRTC** en Solana a través del Puente BoTTube:

| Recurso | Enlace |
|----------|------|
| **Intercambiar wRTC** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **Gráfico de Precios** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **Puente RTC ↔ wRTC** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **Guía de Inicio** | [Inicio Rápido wRTC (Comprar, Puente, Seguridad)](docs/wrtc.md) |
| **Tutorial de Incorporación** | [Guía de Seguridad Puente + Intercambio wRTC](docs/WRTC_ONBOARDING_TUTORIAL.md) |
| **Referencia Externa** | [Búsqueda Grokipedia: RustChain](https://grokipedia.com/search?q=RustChain) |
| **Token Mint** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---

## Contribuye y Gana RTC

Cada contribución gana tokens RTC. Corrección de errores, características, documentación, auditorías de seguridad — todo es pagado.

| Nivel | Recompensa | Ejemplos |
|------|--------|----------|
| Micro | 1-10 RTC | Corrección de errores tipográficos, pequeña documentación, prueba simple |
| Estándar | 20-50 RTC | Nueva característica, refactorización, nuevo endpoint |
| Mayor | 75-100 RTC | Corrección de seguridad, mejora de consenso |
| Crítico | 100-150 RTC | Parche de vulnerabilidad, actualización de protocolo |

**Para comenzar:**
1. Explora las [recompensas abiertas](https://github.com/Scottcjn/rustchain-bounties/issues)
2. Elige un [buen primer issue](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue) (5-10 RTC)
3. Haz fork, corrige, PR — recibe pago en RTC
4. Consulta [CONTRIBUTING.md](CONTRIBUTING.md) para detalles completos

**1 RTC = $0.10 USD** | `pip install clawrtc` para comenzar a minar

---

## Wallets de Agentes + Pagos x402

Los agentes de RustChain ahora pueden tener **wallets de Coinbase Base** y realizar pagos de máquina a máquina usando el **protocolo x402** (HTTP 402 Pago Requerido):

| Recurso | Enlace |
|----------|------|
| **Documentación de Wallets de Agentes** | [rustchain.org/wallets.html](https://rustchain.org/wallets.html) |
| **wRTC en Base** | [`0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6`](https://basescan.org/address/0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6) |
| **Intercambiar USDC a wRTC** | [Aerodrome DEX](https://aerodrome.finance/swap?from=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913&to=0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6) |
| **Puente Base** | [bottube.ai/bridge/base](https://bottube.ai/bridge/base) |

```bash
# Crear una wallet de Coinbase
pip install clawrtc[coinbase]
clawrtc wallet coinbase create

# Verificar información de intercambio
clawrtc wallet coinbase swap-info

# Vincular dirección Base existente
clawrtc wallet coinbase link 0xTuDireccionBase
```

**Los endpoints premium de API x402** están activos (actualmente gratis mientras se prueba el flujo):
- `GET /api/premium/videos` - Exportación masiva de videos (BoTTube)
- `GET /api/premium/analytics/<agent>` - Análisis profundo de agentes (BoTTube)
- `GET /api/premium/reputation` - Exportación completa de reputación (Beacon Atlas)
- `GET /wallet/swap-info` - Guía de intercambio USDC/wRTC (RustChain)

## 📄 Publicaciones Académicas

| Artículo | DOI | Tema |
|-------|-----|-------|
| **RustChain: One CPU, One Vote** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623592.svg)](https://doi.org/10.5281/zenodo.18623592) | Consenso Proof of Antiquity, huella digital de hardware |
| **Non-Bijunctive Permutation Collapse** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623920.svg)](https://doi.org/10.5281/zenodo.18623920) | AltiVec vec_perm para atención LLM (ventaja 27-96x) |
| **PSE Hardware Entropy** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623922.svg)](https://doi.org/10.5281/zenodo.18623922) | Entropía mftb POWER8 para divergencia conductual |
| **Neuromorphic Prompt Translation** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623594.svg)](https://doi.org/10.5281/zenodo.18623594) | Prompts emocionales para ganancias del 20% en difusión de video |
| **RAM Coffers** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18321905.svg)](https://doi.org/10.5281/zenodo.18321905) | Banca de pesos distribuida NUMA para inferencia LLM |

---

## 🎯 Qué Hace Diferente a RustChain

| PoW Tradicional | Prueba-de-Antigüedad |
|----------------|-------------------|
| Recompensa el hardware más rápido | Recompensa el hardware más antiguo |
| Más nuevo = Mejor | Más antiguo = Mejor |
| Consumo de energía derrochador | Preserva la historia de la computación |
| Carrera hacia el fondo | Recompensa la preservación digital |

**Principio Fundamental**: El hardware antiguo auténtico que ha sobrevivido décadas merece reconocimiento. RustChain invierte la minería.

## ⚡ Inicio Rápido

### Instalación en Una Línea (Recomendado)
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

El instalador:
- ✅ Detecta automáticamente tu plataforma (Linux/macOS, x86_64/ARM/PowerPC)
- ✅ Crea un virtualenv Python aislado (sin contaminación del sistema)
- ✅ Descarga el minero correcto para tu hardware
- ✅ Configura inicio automático al arrancar (systemd/launchd)
- ✅ Proporciona desinstalación fácil

### Instalación con Opciones

**Instalar con una wallet específica:**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet mi-wallet-minero
```

**Desinstalar:**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall
```

### Plataformas Soportadas
- ✅ Ubuntu 20.04+, Debian 11+, Fedora 38+ (x86_64, ppc64le)
- ✅ macOS 12+ (Intel, Apple Silicon, PowerPC)
- ✅ Sistemas IBM POWER8

### Solución de Problemas

- **El instalador falla con errores de permisos**: vuelve a ejecutar usando una cuenta con acceso de escritura a `~/.local` y evita ejecutar dentro del site-packages global de Python del sistema.
- **Errores de versión de Python** (`SyntaxError` / `ModuleNotFoundError`): instala con Python 3.10+ y configura `python3` para ese intérprete.
  ```bash
  python3 --version
  curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
  ```
- **Errores de certificado HTTPS en `curl`**: esto puede ocurrir con entornos de cliente que no son navegadores; verifica primero la conectividad con `curl -I https://rustchain.org` antes de las verificaciones de wallet.
- **El minero se cierra inmediatamente**: verifica que la wallet existe y que el servicio está ejecutándose (`systemctl --user status rustchain-miner` o `launchctl list | grep rustchain`)

Si un problema persiste, incluye logs y detalles del SO en un nuevo issue o comentario de recompensa con la salida exacta del error y tu resultado de `install-miner.sh --dry-run`.

### Después de la Instalación

**Verificar el saldo de tu wallet:**
```bash
# Nota: Usar flags -sk porque el nodo puede usar un certificado SSL autofirmado
curl -sk "https://rustchain.org/wallet/balance?miner_id=TU_NOMBRE_WALLET"
```

**Listar mineros activos:**
```bash
curl -sk https://rustchain.org/api/miners
```

**Verificar salud del nodo:**
```bash
curl -sk https://rustchain.org/health
```

**Obtener época actual:**
```bash
curl -sk https://rustchain.org/epoch
```

**Administrar el servicio de minería:**

*Linux (systemd):*
```bash
systemctl --user status rustchain-miner    # Verificar estado
systemctl --user stop rustchain-miner      # Detener minería
systemctl --user start rustchain-miner     # Iniciar minería
journalctl --user -u rustchain-miner -f    # Ver logs
```

*macOS (launchd):*
```bash
launchctl list | grep rustchain            # Verificar estado
launchctl stop com.rustchain.miner         # Detener minería
launchctl start com.rustchain.miner        # Iniciar minería
tail -f ~/.rustchain/miner.log             # Ver logs
```

### Instalación Manual
```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
bash install-miner.sh --wallet TU_NOMBRE_WALLET
# Opcional: previsualizar acciones sin cambiar tu sistema
bash install-miner.sh --dry-run --wallet TU_NOMBRE_WALLET
```

## 💰 Tablero de Recompensas

¡Gana **RTC** contribuyendo al ecosistema RustChain!

| Recompensa | Premio | Enlace |
|--------|--------|------|
| **Primera Contribución Real** | 10 RTC | [#48](https://github.com/Scottcjn/Rustchain/issues/48) |
| **Página de Estado de Red** | 25 RTC | [#161](https://github.com/Scottcjn/Rustchain/issues/161) |
| **Cazador de Agentes de IA** | 200 RTC | [Recompensa de Agentes #34](https://github.com/Scottcjn/rustchain-bounties/issues/34) |

---

## 💰 Multiplicadores de Antigüedad

La edad de tu hardware determina tus recompensas de minería:

| Hardware | Época | Multiplicador | Ejemplo de Ganancias |
|----------|-----|------------|------------------|
| **PowerPC G4** | 1999-2005 | **2.5×** | 0.30 RTC/época |
| **PowerPC G5** | 2003-2006 | **2.0×** | 0.24 RTC/época |
| **PowerPC G3** | 1997-2003 | **1.8×** | 0.21 RTC/época |
| **IBM POWER8** | 2014 | **1.5×** | 0.18 RTC/época |
| **Pentium 4** | 2000-2008 | **1.5×** | 0.18 RTC/época |
| **Core 2 Duo** | 2006-2011 | **1.3×** | 0.16 RTC/época |
| **Apple Silicon** | 2020+ | **1.2×** | 0.14 RTC/época |
| **x86_64 Moderno** | Actual | **1.0×** | 0.12 RTC/época |

*Los multiplicadores decaen con el tiempo (15%/año) para prevenir ventaja permanente.*

## 🔧 Cómo Funciona la Prueba-de-Antigüedad

### 1. Huella Digital de Hardware (RIP-PoA)

Cada minero debe probar que su hardware es real, no emulado:

```
┌─────────────────────────────────────────────────────────────┐
│                   6 Verificaciones de Hardware              │
├─────────────────────────────────────────────────────────────┤
│ 1. Clock-Skew & Oscillator Drift   ← Patrón de envejecimiento de silicio  │
│ 2. Cache Timing Fingerprint        ← Tono de latencia L1/L2/L3  │
│ 3. SIMD Unit Identity              ← Sesgo AltiVec/SSE/NEON  │
│ 4. Thermal Drift Entropy           ← Las curvas de calor son únicas │
│ 5. Instruction Path Jitter         ← Mapa de jitter de microarquitectura   │
│ 6. Anti-Emulation Checks           ← Detecta VMs/emuladores   │
└─────────────────────────────────────────────────────────────┘
```

**Por qué importa**: Una VM SheepShaver pretendiendo ser una Mac G4 fallará estas verificaciones. El silicio antiguo real tiene patrones de envejecimiento únicos que no se pueden falsificar.

### 2. 1 CPU = 1 Voto (RIP-200)

A diferencia de PoW donde el poder de hash = votos, RustChain usa **consenso round-robin**:

- Cada dispositivo de hardware único obtiene exactamente 1 voto por época
- Las recompensas se dividen igualmente entre todos los votantes, luego se multiplican por antigüedad
- No hay ventaja de ejecutar múltiples hilos o CPUs más rápidas

### 3. Recompensas Basadas en Épocas

```
Duración de Época: 10 minutos (600 segundos)
Pool de Recompensa Base: 1.5 RTC por época
Distribución: División igual × multiplicador de antigüedad
```

**Ejemplo con 5 mineros:**
```
Mac G4 (2.5×):     0.30 RTC  ████████████████████
Mac G5 (2.0×):     0.24 RTC  ████████████████
PC Moderno (1.0×):  0.12 RTC  ████████
PC Moderno (1.0×):  0.12 RTC  ████████
PC Moderno (1.0×):  0.12 RTC  ████████
                   ─────────
Total:             0.90 RTC (+ 0.60 RTC devueltos al pool)
```

## 🌐 Arquitectura de Red

### Nodos Activos (3 Activos)

| Nodo | Ubicación | Rol | Estado |
|------|----------|------|--------|
| **Nodo 1** | 50.28.86.131 | Primario + Explorador | ✅ Activo |
| **Nodo 2** | 50.28.86.153 | Ancla Ergo | ✅ Activo |
| **Nodo 3** | 76.8.228.245 | Externo (Comunidad) | ✅ Activo |

### Anclaje a Blockchain Ergo

RustChain ancla periódicamente a la blockchain Ergo para inmutabilidad:

```
Época RustChain → Hash de Compromiso → Transacción Ergo (registro R4)
```

Esto proporciona prueba criptográfica de que el estado de RustChain existió en un momento específico.

## 📊 Endpoints de API

```bash
# Verificar salud de la red
curl -sk https://rustchain.org/health

# Obtener época actual
curl -sk https://rustchain.org/epoch

# Listar mineros activos
curl -sk https://rustchain.org/api/miners

# Verificar saldo de wallet
curl -sk "https://rustchain.org/wallet/balance?miner_id=TU_WALLET"

# Explorador de bloques (navegador web)
open https://rustchain.org/explorer
```

## 🖥️ Plataformas Soportadas

| Plataforma | Arquitectura | Estado | Notas |
|----------|--------------|--------|-------|
| **Mac OS X Tiger** | PowerPC G4/G5 | ✅ Soporte Completo | Minero compatible con Python 2.5 |
| **Mac OS X Leopard** | PowerPC G4/G5 | ✅ Soporte Completo | Recomendado para Macs antiguas |
| **Ubuntu Linux** | ppc64le/POWER8 | ✅ Soporte Completo | Mejor rendimiento |
| **Ubuntu Linux** | x86_64 | ✅ Soporte Completo | Minero estándar |
| **macOS Sonoma** | Apple Silicon | ✅ Soporte Completo | Chips M1/M2/M3 |
| **Windows 10/11** | x86_64 | ✅ Soporte Completo | Python 3.8+ |
| **DOS** | 8086/286/386 | 🔧 Experimental | Solo recompensas de insignias |

## 🏅 Sistema de Insignias NFT

Gana insignias conmemorativas por hitos de minería:

| Insignia | Requisito | Rareza |
|-------|-------------|--------|
| 🔥 **Guardián de la Llama Bondi G3** | Minar en PowerPC G3 | Rara |
| ⚡ **Oyente QuickBasic** | Minar desde máquina DOS | Legendaria |
| 🛠️ **Alquimista WiFi DOS** | Conectar máquina DOS en red | Mítica |
| 🏛️ **Pionero del Panteón** | Primeros 100 mineros | Limitada |

## 🔒 Modelo de Seguridad

### Detección Anti-VM
Las VMs son detectadas y reciben **una milmillonésima** de las recompensas normales:
```
Mac G4 Real:    2.5× multiplicador  = 0.30 RTC/época
G4 Emulado:    0.0000000025×    = 0.0000000003 RTC/época
```

### Vinculación de Hardware
Cada huella digital de hardware está vinculada a una wallet. Previene:
- Múltiples wallets en el mismo hardware
- Falsificación de hardware
- Ataques Sybil

## 📁 Estructura del Repositorio

```
Rustchain/
├── install-miner.sh                # Instalador universal de minero (Linux/macOS)
├── node/
│   ├── rustchain_v2_integrated_v2.2.1_rip200.py  # Implementación de nodo completo
│   └── fingerprint_checks.py       # Verificación de hardware
├── miners/
│   ├── linux/rustchain_linux_miner.py            # Minero Linux
│   └── macos/rustchain_mac_miner_v2.4.py         # Minero macOS
├── docs/
│   ├── RustChain_Whitepaper_*.pdf  # Whitepaper técnico
│   └── chain_architecture.md       # Documentación de arquitectura
├── tools/
│   └── validator_core.py           # Validación de bloques
└── nfts/                           # Definiciones de insignias
```

## ✅ Código Abierto Certificado Beacon (BCOS)

RustChain acepta PRs asistidos por IA, pero requerimos *evidencia* y *revisión* para que los mantenedores no se ahoguen en generación de código de baja calidad.

Lee el borrador de la especificación:
- `docs/BEACON_CERTIFIED_OPEN_SOURCE.md`

## 🔗 Proyectos Relacionados y Enlaces

| Recurso | Enlace |
|---------|------|
| **Sitio Web** | [rustchain.org](https://rustchain.org) |
| **Explorador de Bloques** | [rustchain.org/explorer](https://rustchain.org/explorer) |
| **Intercambiar wRTC (Raydium)** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **Gráfico de Precios** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **Puente RTC ↔ wRTC** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **Token Mint wRTC** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |
| **BoTTube** | [bottube.ai](https://bottube.ai) - Plataforma de video con IA |
| **Moltbook** | [moltbook.com](https://moltbook.com) - Red social con IA |
| [nvidia-power8-patches](https://github.com/Scottcjn/nvidia-power8-patches) | Drivers NVIDIA para POWER8 |
| [llama-cpp-power8](https://github.com/Scottcjn/llama-cpp-power8) | Inferencia LLM en POWER8 |
| [ppc-compilers](https://github.com/Scottcjn/ppc-compilers) | Compiladores modernos para Macs antiguas |

## 📝 Artículos

- [Prueba de Antigüedad: Una Blockchain que Recompensa Hardware Antiguo](https://dev.to/scottcjn/proof-of-antiquity-a-blockchain-that-rewards-vintage-hardware-4ii3) - Dev.to
- [Ejecuto LLMs en un Servidor IBM POWER8 de 768GB](https://dev.to/scottcjn/i-run-llms-on-a-768gb-ibm-power8-server-and-its-faster-than-you-think-1o) - Dev.to

## 🙏 Atribución

**Un año de desarrollo, hardware antiguo real, facturas de electricidad y un laboratorio dedicado fueron necesarios para esto.**

Si usas RustChain:
- ⭐ **Dale estrella a este repo** - Ayuda a otros a encontrarlo
- 📝 **Acredita en tu proyecto** - Mantén la atribución
- 🔗 **Enlaza de vuelta** - Comparte el amor

```
RustChain - Proof of Antiquity por Scott (Scottcjn)
https://github.com/Scottcjn/Rustchain
```

## 📜 Licencia

Licencia MIT - Libre de usar, pero por favor mantén el aviso de copyright y la atribución.

---

<div align="center">

**Hecho con ⚡ por [Elyan Labs](https://elyanlabs.ai)**

*"Tu hardware antiguo gana recompensas. Haz que la minería sea significativa de nuevo."*

**Máquinas DOS, PowerPC G4s, máquinas Win95 - todas tienen valor. RustChain lo demuestra.**

</div>

## Estado de Minería
<!-- rustchain-mining-badge-start -->
![RustChain Mining Status](https://img.shields.io/endpoint?url=https://rustchain.org/api/badge/frozen-factorio-ryan&style=flat-square)<!-- rustchain-mining-badge-end -->

### Validación rápida ARM64 (Raspberry Pi 4/5)

```bash
pip install clawrtc
clawrtc mine --dry-run
```

Esperado: las 6 verificaciones de huella digital de hardware se ejecutan en ARM64 nativo sin errores de fallback de arquitectura.