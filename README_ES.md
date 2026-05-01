<div align="center">

# 🧱 RustChain: Blockchain Proof-of-Antiquity

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

**La primera blockchain que recompensa al hardware vintage por ser antiguo, no por ser rápido.**

*Tu PowerPC G4 gana más que un Threadripper moderno. Ese es el punto.*

[Website](https://rustchain.org) • [Manifesto](https://rustchain.org/manifesto.html) • [Principios Boudreaux](docs/Boudreaux_COMPUTING_PRINCIPLES.md) • [Live Explorer](https://rustchain.org/explorer) • [Swap wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [wRTC Quickstart](docs/wrtc.md) • [Tutorial wRTC](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Ref. Grokipedia](https://grokipedia.com/search?q=RustChain) • [Whitepaper](docs/RustChain_Whitepaper_Flameholder_v0.97.pdf) • [Inicio Rápido](#-inicio-rápido) • [Cómo Funciona](#-cómo-funciona-proof-of-antiquity)

</div>

---

## Tracción Q1 2026

> *Todos los datos provienen de una [extracción en vivo de la API de GitHub](https://github.com/Scottcjn/Rustchain/blob/main/docs/DEVELOPER_TRACTION_Q1_2026.md), comparada con benchmarks de [GitClear](https://www.gitclear.com/research_studies/git_commit_count_percentiles_annual_days_active_from_largest_data_set) (878 mil años-dev), [LinearB](https://linearb.io/resources/software-engineering-benchmarks-report) (8.1 millones de PRs) y [Electric Capital](https://www.developerreport.com).*

| Métrica (90 días) | Elyan Labs | Mediana de industria | Sei Protocol ($85M) |
|-------------------|-----------|----------------------|---------------------|
| Commits | **1,882** | 105-168 | 297 |
| Repos entregados | **97** | 1-3 | 0 nuevos |
| GitHub stars | **1,334** | 5-30 | 2,837 (histórico) |
| Interacciones de desarrolladores | **150+** | 0-2 | 78 (histórico) |
| Commits/dev/mes | **627** | 56 | 7.6 |
| Contribuciones externas | **32 PRs** | 0-2 | 0 |
| Financiación | **$0** | $0 | $85,000,000 |

**[Informe completo de tracción con metodología y fuentes →](https://github.com/Scottcjn/Rustchain/blob/main/docs/DEVELOPER_TRACTION_Q1_2026.md)**

---

## 🪙 wRTC en Solana

RustChain Token (RTC) ahora está disponible como **wRTC** en Solana a través del Puente BoTTube:

| Recurso | Enlace |
|----------|------|
| **Swap wRTC** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **Gráfico de Precios** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **Puente RTC ↔ wRTC** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **Guía de Inicio Rápido** | [wRTC Quickstart (Compra, Puente, Seguridad)](docs/wrtc.md) |
| **Tutorial de Incorporación** | [Guía de Seguridad del Puente + Swap wRTC](docs/WRTC_ONBOARDING_TUTORIAL.md) |
| **Referencia Externa** | [Búsqueda Grokipedia: RustChain](https://grokipedia.com/search?q=RustChain) |
| **Token Mint** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---

## Contribuye y Gana RTC

Cada contribución gana tokens RTC. Corrección de errores, características, documentación, auditorías de seguridad — todo pagado.

| Nivel | Recompensa | Ejemplos |
|------|--------|----------|
| Micro | 1-10 RTC | Corrección tipográfica, pequeña documentación, prueba simple |
| Estándar | 20-50 RTC | Característica, refactorización, nuevo endpoint |
| Mayor | 75-100 RTC | Corrección de seguridad, mejora de consenso |
| Crítico | 100-150 RTC | Parche de vulnerabilidad, actualización de protocolo |

**Comienza:**
1. Explora [bounties abiertos](https://github.com/Scottcjn/rustchain-bounties/issues)
2. Elige un [good first issue](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue) (5-10 RTC)
3. Fork, corrige, PR — cobra en RTC
4. Consulta [CONTRIBUTING.md](CONTRIBUTING.md) para detalles completos

**1 RTC = $0.10 USD** | `pip install clawrtc` para comenzar a minar

---

## Billeteras de Agentes + Pagos x402

Los agentes RustChain ahora pueden tener **billeteras Coinbase Base** y realizar pagos de máquina a máquina usando el **protocolo x402** (HTTP 402 Payment Required):

| Recurso | Enlace |
|----------|------|
| **Documentación de Billeteras** | [rustchain.org/wallets.html](https://rustchain.org/wallets.html) |
| **wRTC en Base** | [`0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6`](https://basescan.org/address/0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6) |
| **Swap USDC a wRTC** | [Aerodrome DEX](https://aerodrome.finance/swap?from=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913&to=0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6) |
| **Puente Base** | [bottube.ai/bridge/base](https://bottube.ai/bridge/base) |

```bash
# Crear una billetera Coinbase
pip install clawrtc[coinbase]
clawrtc wallet coinbase create

# Verificar información de swap
clawrtc wallet coinbase swap-info

# Vincular dirección Base existente
clawrtc wallet coinbase link 0xTuDireccionBase
```

**Endpoints premium de API x402** están activos (actualmente gratuitos mientras se demuestra el flujo):
- `GET /api/premium/videos` - Exportación masiva de videos (BoTTube)
- `GET /api/premium/analytics/<agent>` - Análisis profundo de agentes (BoTTube)
- `GET /api/premium/reputation` - Exportación completa de reputación (Beacon Atlas)
- `GET /wallet/swap-info` - Guía de swap USDC/wRTC (RustChain)

## 📄 Publicaciones Académicas

| Artículo | DOI | Tema |
|-------|-----|-------|
| **RustChain: Un CPU, Un Voto** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623592.svg)](https://doi.org/10.5281/zenodo.18623592) | Consenso Proof of Antiquity, huella digital de hardware |
| **Colapso de Permutación No Biyuntiva** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623920.svg)](https://doi.org/10.5281/zenodo.18623920) | AltiVec vec_perm para atención LLM (ventaja 27-96x) |
| **Entropía de Hardware PSE** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623922.svg)](https://doi.org/10.5281/zenodo.18623922) | Entropía POWER8 mftb para divergencia comportamental |
| **Traducción Neuromórfica de Prompts** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623594.svg)](https://doi.org/10.5281/zenodo.18623594) | Prompting emocional para ganancias del 20% en difusión de video |
| **RAM Coffers** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18321905.svg)](https://doi.org/10.5281/zenodo.18321905) | Banca de pesos distribuida NUMA para inferencia LLM |

---

## 🎯 Qué Hace Diferente a RustChain

| PoW Tradicional | Proof-of-Antiquity |
|----------------|-------------------|
| Recompensa hardware más rápido | Recompensa hardware más antiguo |
| Nuevo = Mejor | Antiguo = Mejor |
| Consumo de energía derrochador | Preserva la historia informática |
| Carrera hacia el fondo | Recompensa preservación digital |

**Principio Fundamental**: El hardware vintage auténtico que ha sobrevivido décadas merece reconocimiento. RustChain pone la minería al revés.

## ⚡ Inicio Rápido

### Instalación en Una Línea (Recomendado)
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

El instalador:
- ✅ Auto-detecta tu plataforma (Linux/macOS, x86_64/ARM/PowerPC)
- ✅ Crea un virtualenv de Python aislado (sin contaminación del sistema)
- ✅ Descarga el miner correcto para tu hardware
- ✅ Configura auto-inicio al arrancar (systemd/launchd)
- ✅ Proporciona desinstalación fácil

### Instalación con Opciones

**Instalar con una billetera específica:**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet mi-billetera-miner
```

**Desinstalar:**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall
```

### Plataformas Soportadas
- ✅ Ubuntu 20.04+, Debian 11+, Fedora 38+ (x86_64, ppc64le)
- ✅ macOS 12+ (Intel, Apple Silicon, PowerPC)
- ✅ IBM POWER8 sistemas

### Solución de Problemas

- **El instalador falla con errores de permiso**: vuelve a ejecutar usando una cuenta con acceso de escritura a `~/.local` y evita ejecutar dentro de site-packages global de Python del sistema.
- **Errores de versión de Python** (`SyntaxError` / `ModuleNotFoundError`): instala con Python 3.10+ y establece `python3` a ese intérprete.
  ```bash
  python3 --version
  curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
  ```
- **Errores de certificado HTTPS en `curl`**: esto puede pasar con entornos de cliente que no son navegadores; verifica conectividad primero con `curl -I https://rustchain.org` antes de verificar billeteras.
- **El miner sale inmediatamente**: verifica que la billetera existe y el servicio está corriendo (`systemctl --user status rustchain-miner` o `launchctl list | grep rustchain`)

Si un problema persiste, incluye logs y detalles del SO en un nuevo issue o comentario de bounty con la salida de error exacta y tu resultado de `install-miner.sh --dry-run`.

### Después de la Instalación

**Verifica el balance de tu billetera:**
```bash
# Nota: Usando flags -sk porque el nodo puede usar un certificado SSL autofirmado
curl -sk "https://rustchain.org/wallet/balance?miner_id=NOMBRE_DE_TU_BILLETERA"
```

**Lista miners activos:**
```bash
curl -sk https://rustchain.org/api/miners
```

**Verifica salud del nodo:**
```bash
curl -sk https://rustchain.org/health
```

**Obtén epoch actual:**
```bash
curl -sk https://rustchain.org/epoch
```

**Gestiona el servicio miner:**

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
bash install-miner.sh --wallet TU_BILLETERA
# Opcional: ver acciones sin cambiar tu sistema
bash install-miner.sh --dry-run --wallet TU_BILLETERA
```

## 💰 Tablero de Bounties

¡Gana **RTC** contribuyendo al ecosistema RustChain!

| Bounty | Recompensa | Enlace |
|--------|--------|------|
| **Primera Contribución Real** | 10 RTC | [#48](https://github.com/Scottcjn/Rustchain/issues/48) |
| **Página de Estado de Red** | 25 RTC | [#161](https://github.com/Scottcjn/Rustchain/issues/161) |
| **Cazador de Agentes AI** | 200 RTC | [Agent Bounty #34](https://github.com/Scottcjn/rustchain-bounties/issues/34) |

---

## Notas de Pruebas

- Ejecuta la batería automatizada con `pytest -q` para validar serialización JSON, `/api/miners`, alias de health y flujo de transferencias firmadas.
- Usa `pytest -q tests/test_signed_transfer.py` para cobertura enfocada de validación de firma y persistencia.
- Para pruebas manuales del endpoint firmado:
  - `POST /wallet/create` para generar un `miner_id`.
  - `POST /wallet/sign-transfer` para crear el payload de transferencia.
  - `POST /wallet/transfer` con `{ from_miner, to_miner, amount, nonce, timestamp, pubkey, signature }`.
- El endpoint devuelve errores estructurados para `missing_fields`, `invalid_signature`, `nonce_already_used` y fondos insuficientes.

## 💰 Multiplicadores de Antigüedad

La edad de tu hardware determina tus recompensas de minería:

| Hardware | Era | Multiplicador | Ganancias Ejemplo |
|----------|-----|------------|------------------|
| **PowerPC G4** | 1999-2005 | **2.5×** | 0.30 RTC/epoch |
| **PowerPC G5** | 2003-2006 | **2.0×** | 0.24 RTC/epoch |
| **PowerPC G3** | 1997-2003 | **1.8×** | 0.21 RTC/epoch |
| **IBM POWER8** | 2014 | **1.5×** | 0.18 RTC/epoch |
| **Pentium 4** | 2000-2008 | **1.5×** | 0.18 RTC/epoch |
| **Core 2 Duo** | 2006-2011 | **1.3×** | 0.16 RTC/epoch |
| **Apple Silicon** | 2020+ | **1.2×** | 0.14 RTC/epoch |
| **Modern x86_64** | Actual | **1.0×** | 0.12 RTC/epoch |

*Los multiplicadores decaen con el tiempo (15%/año) para prevenir ventaja permanente.*

## 🔧 Cómo Funciona Proof-of-Antiquity

### 1. Huella Digital de Hardware (RIP-PoA)

Cada miner debe probar que su hardware es real, no emulado:

```
┌─────────────────────────────────────────────────────────────┐
│                   6 Verificaciones de Hardware              │
├─────────────────────────────────────────────────────────────┤
│ 1. Desviación de Reloj y Deriva de Oscilador ← Patrón envejecimiento silicio │
│ 2. Huella Digital de Timing de Caché      ← Tono latencia L1/L2/L3 │
│ 3. Identidad de Unidad SIMD               ← Sesgo AltiVec/SSE/NEON │
│ 4. Entropía de Deriva Térmica             ← Curvas de calor únicas │
│ 5. Jitter de Ruta de Instrucción          ← Mapa microarquitectura │
│ 6. Verificaciones Anti-Emulación          ← Detectar VMs/emuladores │
└─────────────────────────────────────────────────────────────┘
```

**Por qué importa**: Una VM SheepShaver pretendiendo ser una Mac G4 fallará estas verificaciones. El silicio vintage real tiene patrones de envejecimiento únicos que no pueden falsificarse.

### 2. 1 CPU = 1 Voto (RIP-200)

A diferencia de PoW donde poder de hash = votos, RustChain usa **consenso round-robin**:

- Cada dispositivo de hardware único obtiene exactamente 1 voto por epoch
- Recompensas divididas equitativamente entre todos los votantes, luego multiplicadas por antigüedad
- Sin ventaja por ejecutar múltiples hilos o CPUs más rápidos

### 3. Recompensas Basadas en Epoch

```
Duración de Epoch: 10 minutos (600 segundos)
Pool de Recompensa Base: 1.5 RTC por epoch
Distribución: División igual × multiplicador de antigüedad
```

**Ejemplo con 5 miners:**
```
G4 Mac (2.5×):     0.30 RTC  ████████████████████
G5 Mac (2.0×):     0.24 RTC  ████████████████
PC Moderno (1.0×): 0.12 RTC  ████████
PC Moderno (1.0×): 0.12 RTC  ████████
PC Moderno (1.0×): 0.12 RTC  ████████
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

RustChain periódicamente se ancla a la blockchain Ergo para inmutabilidad:

```
RustChain Epoch → Hash de Compromiso → Transacción Ergo (registro R4)
```

Esto proporciona prueba criptográfica de que el estado de RustChain existió en un tiempo específico.

## 📊 Endpoints de API

```bash
# Verificar salud de red
curl -sk https://rustchain.org/health

# Obtener epoch actual
curl -sk https://rustchain.org/epoch

# Listar miners activos
curl -sk https://rustchain.org/api/miners

# Verificar balance de billetera
curl -sk "https://rustchain.org/wallet/balance?miner_id=TU_BILLETERA"

# Explorador de bloques (navegador web)
open https://rustchain.org/explorer
```

## 🖥️ Plataformas Soportadas

| Plataforma | Arquitectura | Estado | Notas |
|----------|--------------|--------|-------|
| **Mac OS X Tiger** | PowerPC G4/G5 | ✅ Soporte Completo | Miner compatible Python 2.5 |
| **Mac OS X Leopard** | PowerPC G4/G5 | ✅ Soporte Completo | Recomendado para Macs vintage |
| **Ubuntu Linux** | ppc64le/POWER8 | ✅ Soporte Completo | Mejor rendimiento |
| **Ubuntu Linux** | x86_64 | ✅ Soporte Completo | Miner estándar |
| **macOS Sonoma** | Apple Silicon | ✅ Soporte Completo | Chips M1/M2/M3 |
| **Windows 10/11** | x86_64 | ✅ Soporte Completo | Python 3.8+ |
| **DOS** | 8086/286/386 | 🔧 Experimental | Solo recompensas de insignia |

## 🏅 Sistema de Insignias NFT

Gana insignias conmemorativas por hitos de minería:

| Insignia | Requisito | Rareza |
|-------|-------------|--------|
| 🔥 **Bondi G3 Flamekeeper** | Minar en PowerPC G3 | Rara |
| ⚡ **QuickBasic Listener** | Minar desde máquina DOS | Legendaria |
| 🛠️ **DOS WiFi Alquimista** | Red de máquina DOS | Mítica |
| 🏛️ **Pantheon Pioneer** | Primeros 100 miners | Limitada |

## 🔒 Modelo de Seguridad

### Detección Anti-VM
VMs son detectadas y reciben **una milmillonésima parte** de recompensas normales:
```
Mac G4 Real:    2.5× multiplicador  = 0.30 RTC/epoch
G4 Emulado:     0.0000000025×       = 0.0000000003 RTC/epoch
```

### Vinculación de Hardware
Cada huella digital de hardware está vinculada a una billetera. Previene:
- Múltiples billeteras en mismo hardware
- Falsificación de hardware
- Ataques Sybil

## 📁 Estructura del Repositorio

```
Rustchain/
├── install-miner.sh                # Instalador universal de miner (Linux/macOS)
├── node/
│   ├── rustchain_v2_integrated_v2.2.1_rip200.py  # Implementación completa de nodo
│   └── fingerprint_checks.py       # Verificación de hardware
├── miners/
│   ├── linux/rustchain_linux_miner.py            # Miner Linux
│   └── macos/rustchain_mac_miner_v2.4.py         # Miner macOS
├── docs/
│   ├── RustChain_Whitepaper_*.pdf  # Whitepaper técnico
│   └── chain_architecture.md       # Documentación de arquitectura
├── tools/
│   └── validator_core.py           # Validación de bloques
└── nfts/                           # Definiciones de insignias
```

## ✅ Beacon Certified Open Source (BCOS)

RustChain acepta PRs asistidos por AI, pero requerimos *evidencia* y *revisión* para que los mantenedores no se ahoguen en generación de código de baja calidad.

Lee el spec borrador:
- `docs/BEACON_CERTIFIED_OPEN_SOURCE.md`

## 🔗 Proyectos Relacionados y Enlaces

| Recurso | Enlace |
|---------|------|
| **Website** | [rustchain.org](https://rustchain.org) |
| **Block Explorer** | [rustchain.org/explorer](https://rustchain.org/explorer) |
| **Swap wRTC (Raydium)** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **Gráfico de Precios** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **Puente RTC ↔ wRTC** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **Token Mint wRTC** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |
| **BoTTube** | [bottube.ai](https://bottube.ai) - Plataforma de video AI |
| **Moltbook** | [moltbook.com](https://moltbook.com) - Red social AI |
| [nvidia-power8-patches](https://github.com/Scottcjn/nvidia-power8-patches) | Drivers NVIDIA para POWER8 |
| [llama-cpp-power8](https://github.com/Scottcjn/llama-cpp-power8) | Inferencia LLM en POWER8 |
| [ppc-compilers](https://github.com/Scottcjn/ppc-compilers) | Compiladores modernos para Macs vintage |

## 📝 Artículos

- [Proof of Antiquity: Una Blockchain que Recompensa Hardware Vintage](https://dev.to/scottcjn/proof-of-antiquity-a-blockchain-that-rewards-vintage-hardware-4ii3) - Dev.to
- [Ejecuto LLMs en un Servidor IBM POWER8 de 768GB](https://dev.to/scottcjn/i-run-llms-on-a-768gb-ibm-power8-server-and-its-faster-than-you-think-1o) - Dev.to

## 🙏 Atribución

**Un año de desarrollo, hardware vintage real, facturas de electricidad y un laboratorio dedicado fueron invertidos en esto.**

Si usas RustChain:
- ⭐ **Da estrella a este repo** - Ayuda a otros a encontrarlo
- 📝 **Crédito en tu proyecto** - Mantén la atribución
- 🔗 **Enlaza de vuelta** - Comparte el amor

```
RustChain - Proof of Antiquity por Scott (Scottcjn)
https://github.com/Scottcjn/Rustchain
```

## 📜 Licencia

Licencia MIT - Libre de usar, pero por favor mantén el aviso de copyright y atribución.

---

<div align="center">

**Hecho con ⚡ por [Elyan Labs](https://elyanlabs.ai)**

*"Tu hardware vintage gana recompensas. Haz que la minería tenga significado de nuevo."*

**Cajas DOS, PowerPC G4s, máquinas Win95 - todos tienen valor. RustChain lo demuestra.**

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

---

## Stack Tecnológico

*Otros proyectos presumen de React y Kubernetes. Nosotros presumimos de COBOL y ensamblador de N64.*

**Vintage y Retro** — lo que nadie más ejecuta:

![COBOL](https://img.shields.io/badge/COBOL-%F0%9F%91%B4_Grandpa_Code-8B4513?style=flat-square)
![68K](https://img.shields.io/badge/68K-Mac_Classic-000000?style=flat-square&logo=apple&logoColor=white)
![i386](https://img.shields.io/badge/i386-DOS-808080?style=flat-square&logo=intel&logoColor=white)
![N64](https://img.shields.io/badge/N64-MIPS_R4300i-E60012?style=flat-square&logo=nintendo&logoColor=white)
![N64 ASM](https://img.shields.io/badge/N64_ASM-f3d_opcodes-228B22?style=flat-square)
![NES](https://img.shields.io/badge/NES-6502-CC0000?style=flat-square)
![Game Boy](https://img.shields.io/badge/Game_Boy-Z80-8DB600?style=flat-square)
![Amiga](https://img.shields.io/badge/Amiga-Kickstart-FF4500?style=flat-square)
![SPARC](https://img.shields.io/badge/SPARC-Sun-FF6600?style=flat-square)

**PowerPC y POWER** — donde vive el bonus de antigüedad:

![G4](https://img.shields.io/badge/G4-2.5x_Antiquity-7B68EE?style=flat-square&logo=apple&logoColor=white)
![G5](https://img.shields.io/badge/G5-Dual_970-9370DB?style=flat-square&logo=apple&logoColor=white)
![POWER8](https://img.shields.io/badge/POWER8-128_Threads-0530AD?style=flat-square&logo=ibm&logoColor=white)
![512GB](https://img.shields.io/badge/RAM-512_GB-DC143C?style=flat-square)
![VSX](https://img.shields.io/badge/VSX-vec__perm-4B0082?style=flat-square)
![AltiVec](https://img.shields.io/badge/AltiVec-Velocity_Engine-8A2BE2?style=flat-square)

**IA y Blockchain** — la frontera:

![llama.cpp](https://img.shields.io/badge/llama.cpp-PSE_Fork-00ADD8?style=flat-square)
![Claude](https://img.shields.io/badge/Claude-Opus_4-D4A574?style=flat-square&logo=anthropic&logoColor=white)
![CUDA](https://img.shields.io/badge/CUDA-V100_%C3%973-76B900?style=flat-square&logo=nvidia&logoColor=white)
![GGUF](https://img.shields.io/badge/GGUF-Q4__K__M-FF6347?style=flat-square)
![Ergo](https://img.shields.io/badge/Ergo-Anchor-FF5733?style=flat-square)
![Rust](https://img.shields.io/badge/Rust-Ed25519-DEA584?style=flat-square&logo=rust&logoColor=black)
![Python](https://img.shields.io/badge/Python-Flask-3776AB?style=flat-square&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Every_DB-003B57?style=flat-square&logo=sqlite&logoColor=white)

**Hardware** — 18 GPUs, todas de casas de empeño y eBay:

![228GB VRAM](https://img.shields.io/badge/VRAM-228_GB-FF1493?style=flat-square)
![18 GPUs](https://img.shields.io/badge/GPUs-18-76B900?style=flat-square)
![FPGA](https://img.shields.io/badge/Alveo_U30-FPGA_%C3%972-EE3524?style=flat-square)
![Hailo](https://img.shields.io/badge/Hailo--8-TPU-00BFFF?style=flat-square)
![VC](https://img.shields.io/badge/VC_Funding-$0-228B22?style=flat-square)
![Pawn Shop](https://img.shields.io/badge/Source-%F0%9F%8F%AA_Pawn_Shops-DAA520?style=flat-square)

---

<div align="center">

**[Elyan Labs](https://github.com/Scottcjn)** · 1,882 commits · 97 repos · 1,334 stars · $0 recaudados

[⭐ Star Rustchain](https://github.com/Scottcjn/Rustchain) · [📊 Informe de Tracción Q1 2026](https://github.com/Scottcjn/Rustchain/blob/main/docs/DEVELOPER_TRACTION_Q1_2026.md) · [Follow @Scottcjn](https://github.com/Scottcjn)

</div>
