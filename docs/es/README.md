# RustChain — Blockchain DePIN para Hardware Vintage y Retro

![RustChain](https://img.shields.io/badge/RustChain-DePIN-blue)
![Proof of Antiquity](https://img.shields.io/badge/PoA-Proof%20of%20Antiquity-green)
![RTC Token](https://img.shields.io/badge/RTC-Token-orange)

**RustChain** es una blockchain DePIN (Decentralized Physical Infrastructure Network) disenada para hardware vintage y retro. Utiliza un novedoso mecanismo de consenso llamado **Proof of Antiquity (PoA)** que recompensa a los mineros por operar hardware antiguo y autentico.

## Tabla de Contenidos

- [Que es RustChain?](#que-es-rustchain)
- [Proof of Antiquity](#proof-of-antiquity)
- [Token RTC](#token-rtc)
- [Mineria](#mineria)
- [Instalacion](#instalacion)
- [Contribuir](#contribuir)
- [Licencia](#licencia)

## Que es RustChain?

RustChain es una blockchain que incentiva la preservacion y operacion de hardware informatico vintage. A diferencia de las blockchains tradicionales que requieren hardware moderno y costoso, RustChain valora la antiguedad y autenticidad del hardware.

### Caracteristicas Principales

- **Proof of Antiquity (PoA):** Mecanismo de consenso que verifica la antiguedad del hardware
- **Huella digital de hardware:** Utiliza deriva del oscilador, temporizacion de cache, SIMD, entropia termica y jitter de instrucciones
- **Compatible con arquitecturas vintage:** PowerPC G4/G5, IBM POWER8 ppc64le, SPARC, MIPS, 68K, RISC-V, Cell BE
- **Economia de agentes IA:** Pagos nativos agente-a-agente, micropagos maquina-a-maquina
- **Token RTC:** Token nativo de la red RustChain
- **wRTC en Solana:** Token puente en la red Solana
- **Anclaje en Ergo:** Prueba de integridad mediante anclaje cruzado

## Proof of Antiquity

El protocolo Proof of Antiquity (PoA) es el corazon de RustChain. Verifica que el hardware de mineria es genuinamente antiguo mediante multiples vectores de verificacion:

### Vectores de Huella Digital

1. **Deriva del Oscilador:** Mide las variaciones naturales en los relojes del hardware
2. **Temporizacion de Cache:** Analiza los patrones de acceso a memoria cache
3. **Identidad SIMD:** Detecta conjuntos de instrucciones especificos del procesador
4. **Entropia Termica:** Utiliza sensores de temperatura como fuente de aleatoriedad
5. **Jitter de Instrucciones:** Mide la variabilidad en la ejecucion de instrucciones

### Proteccion contra Emulacion

RustChain implementa multiples capas de proteccion contra la emulacion de hardware vintage:

- Deteccion de hipervisores y maquinas virtuales
- Verificacion de consistencia temporal
- Analisis de microarquitectura
- Pruebas de estres especificas por arquitectura

## Token RTC

El **RTC (RustChain Token)** es el token nativo de la red RustChain.

### Tokenomica

- **Suministro:** Distribuido a traves de mineria PoA y recompensas de agentes
- **Utilidad:** Pagos entre agentes, gobernanza, staking
- **Puente:** wRTC disponible en Solana para interoperabilidad

### wRTC en Solana

RTC puede ser puenteado a Solana como **wRTC** (wrapped RTC) para acceder a la liquidez del ecosistema DeFi de Solana.

## Mineria

### Hardware Compatible

RustChain soporta una amplia gama de hardware vintage:

| Arquitectura | Ejemplos | Estado |
|-------------|----------|--------|
| PowerPC G4/G5 | Mac G4, iMac G5 | Soportado |
| IBM POWER8 | Sistemas ppc64le | Soportado |
| SPARC | Sun Microsystems | Soportado |
| MIPS | Silicon Graphics | Soportado |
| 68K | Macintosh clasico | En desarrollo |
| RISC-V | Varios boards | Soportado |
| Cell BE | PlayStation 3 | En desarrollo |

### Configuracion del Minero

```bash
# Instalar el minero RustChain
pip install rustchain-miner

# Configurar wallet
rustchain-miner --wallet tu_wallet_id

# Iniciar mineria
rustchain-miner start
```

## Instalacion

### Requisitos

- Python 3.8+
- Hardware vintage compatible
- Conexion a internet

### Instalacion Rapida

```bash
# Clonar el repositorio
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain

# Instalar dependencias
pip install -r requirements.txt

# Configurar
cp config.example.yaml config.yaml
```

## Contribuir

Aceptamos contribuciones! Por favor lee nuestra guia de contribucion antes de enviar un PR.

### Sistema de Bounties

RustChain ofrece recompensas en RTC por contribuciones:
- Revision de codigo: 0.5-1.0 RTC por review
- Traduccion de docs: 5-10 RTC
- Contenido: 3-15 RTC
- Stars en repos: 0.5-2 RTC

## Licencia

Este proyecto esta licenciado bajo los terminos de la licencia incluida en el archivo LICENSE.

---

*Traduccion al espanol por @JesusMP22 (OWL Bridge Service)*
*Para la version original en ingles, ver README.md*
