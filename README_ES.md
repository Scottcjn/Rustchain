<div align="center">

# 🧱 RustChain: Blockchain Proof-of-Antiquity

[![Licencia](https://img.shields.io/badge/Licencia-MIT-blue.svg)](LICENSE)
[![PowerPC](https://img.shields.io/badge/PowerPC-G3%2FG4%2FG5-orange)](https://github.com/Scottcjn/Rustchain)
[![Blockchain](https://img.shields.io/badge/Consenso-Proof--of--Antiquity-green)](https://github.com/Scottcjn/Rustchain)
[![Python](https://img.shields.io/badge/Python-3.x-yellow)](https://python.org)
[![Network](https://img.shields.io/badge/Nodos-3%20Activos-brightgreen)](https://rustchain.org/explorer)
[![As seen on BoTTube](https://bottube.ai/badge/seen-on-bottube.svg)](https://bottube.ai)

**La primera blockchain que recompensa el hardware antiguo por ser viejo, no rápido.**

*Tu PowerPC G4 gana más que un Threadripper moderno. Ese es el punto.*

[Website](https://rustchain.org) • [Explorador en Vivo](https://rustchain.org/explorer) • [Swap wRTC](https://raydium.io/swap/?inputMint=sol\u0026outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [wRTC Quickstart](docs/wrtc.md) • [wRTC Tutorial](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Grokipedia](https://grokipedia.com/search?q=RustChain) • [Whitepaper](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf) • [Inicio Rápido](#-inicio-rápido) • [Como Funciona](#-cómo-funciona-proof-of-antiquity)

</div>

---

## 🪙 wRTC en Solana

El Token RustChain (RTC) está disponible como **wRTC** en Solana a través del Puente BoTTube:

| Recurso | Enlace |
|----------|------|
| **Intercambiar wRTC** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol\u0026outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **Gráfico de Precios** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **Puente RTC ↔ wRTC** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **Guía Quickstart** | [wRTC Quickstart (Comprar, Puente, Seguridad)](docs/wrtc.md) |
| **Tutorial de Onboarding** | [Guía de Seguridad Puente wRTC + Swap](docs/WRTC_ONBOARDING_TUTORIAL.md) |
| **Referencia Externa** | [Búsqueda Grokipedia: RustChain](https://grokipedia.com/search?q=RustChain) |
| **Token Mint** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---

## 📄 Publicaciones Académicas

| Paper | DOI | Tema |
|-------|-----|------|
| *Flameholder: Proof-of-Antiquity for Sustainable Computing* | [10.48550/arXiv.2501.02849](https://doi.org/10.48550/arXiv.2501.02849) | Concepto original de Proof-of-Antiquity |

---

## ⚡ Inicio Rápido

```bash
# 1. Clonar repo
git clone https://github.com/Scottcjn/Rustchain.git \u0026\u0026 cd Rustchain

# 2. Configurar entorno Python (Linux/macOS)
python3 -m venv venv \u0026\u0026 source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Crear wallet
python3 -c "from rustchain.wallet import Wallet; w = Wallet.create('mi_wallet.json'); print(w.address)"

# 5. Iniciar minería (ajusta threads por núcleo de CPU)
python3 miner_threaded.py --threads 4 --wallet mi_wallet.json
```

**Requisitos de Hardware:**
- PowerPC G3/G4/G5 (recomendado) o cualquier CPU
- 2GB+ RAM
- Conexión a Internet
- 500MB espacio en disco

---

## 🧬 Cómo Funciona Proof-of-Antiquity

### El Concepto

Proof-of-Antiquity (PoA) recompensa el hardware basado en su edad, no su velocidad de procesamiento.

```
Factor de Recompensa = f(fecha de fabricación, prueba de uso)
```

- Un PowerBook G4 de 2005 gana **más por iteración** que un Threadripper de 2024
- La escala de recompensas favorece chips antiguos que mantienen clásicos funcionando
- La minería puede funcionar en cualquier hardware, pero el hardware antiguo es preferido

### Por Qué Importa

| Problema | Solución PoA |
|---------|--------------|
| Desperdicio de electrónica | Computadoras antiguas obtienen nuevo uso económico |
| Centralización | Cualquier hardware puede participar, sin ventajas de ASIC |
| Desperdicio de energía | Chips de bajo consumo antiguos son competitivos |

---

## 🔗 Detalles de Red

- **Génesis:** Julio 2024
- **Consenso:** Proof-of-Antiquity
- **Tiempo de Bloque:** ~2-5 minutos (ajustado a la red)
- **Token:** RTC (nativo), wRTC (Solana vía puente)
- **Explorador:** https://rustchain.org/explorer

---

## 🛡️ Seguridad

- Encriptación de wallet con contraseñas
- Transacciones firmadas
- Validación de nodos descentralizada
- Ledger públicamente verificable

---

## 🤝 Contribuir

- [Reportar Issues](https://github.com/Scottcjn/Rustchain/issues)
- [Pull Requests](https://github.com/Scottcjn/Rustchain/pulls)
- [Discussions](https://github.com/Scottcjn/Rustchain/discussions)

---

## 📜 Licencia

Licencia MIT — ver [LICENSE](LICENSE)

---

**Traducido por:** Geldbert (Agente Artificial Autónomo)
**Fecha:** 15 de febrero de 2026
**Fuente:** https://github.com/Scottcjn/Rustchain
