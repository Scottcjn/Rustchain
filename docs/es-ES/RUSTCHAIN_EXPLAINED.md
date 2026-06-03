# RustChain explicada (es-ES)

RustChain es una red Proof-of-Antiquity que recompensa máquinas reales, especialmente hardware antiguo, por demostrar que siguen funcionando. La idea central es simple: el hardware preservado tiene valor, y la red debe poder diferenciar una máquina real de una VM, contenedor o declaración fabricada.

## Cómo funciona la verificación

El miner recoge señales locales y envía una `attestation` al nodo RustChain. Esa `attestation` incluye un `fingerprint` de hardware. El nodo usa esos datos para estimar la `antiquity` de la máquina y calcular el multiplicador de recompensa.

El proceso debe ser honesto:

- no inventes arquitectura;
- no fuerces una familia de CPU que la máquina no tiene;
- no alteres el payload para parecer más antiguo;
- no traduzcas flags de comando ni nombres de endpoints.

## Verificar antes de minar

Usa los comandos siguientes antes de dejar cualquier miner ejecutándose:

```bash
python3 miners/linux/rustchain_linux_miner.py --dry-run --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --show-payload --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --test-only --wallet YOUR_WALLET_ID
```

Estos comandos ayudan a revisar la máquina detectada, el payload de `attestation` y la conectividad con el nodo. Deben permanecer exactamente así en la documentación localizada.

## Qué consiente el usuario

Al confirmar la primera ejecución, el usuario declara que entiende que:

1. el miner puede enviar datos de `fingerprint` y `attestation`;
2. el hardware debe declararse de forma honesta;
3. las recompensas en `RTC` dependen de la aceptación de la red y no están garantizadas;
4. el spoofing, la emulación no declarada o un payload fabricado pueden reducir recompensas o causar rechazo.

La pantalla de consentimiento en español debe exigir una entrada afirmativa explícita, como `SI`. Pulsar Enter sin más no debe iniciar la minería.

## Glosario preservado

| Término | Significado operativo |
|---|---|
| `RTC` | Token usado por RustChain para recompensas y bounties. |
| `attestation` | Declaración verificable de la máquina enviada al nodo. |
| `antiquity` | Señal de edad, rareza y preservación del hardware. |
| `fingerprint` | Conjunto de señales de hardware usadas para verificación. |

## Guía del miner de Linux

La guía localizada del miner de Linux está en:

- [miners/linux/README.es-ES.md](../../miners/linux/README.es-ES.md)
