# RustChain Miner para Linux (es-ES)

Esta guía localiza el flujo del miner de Linux para hablantes de español. Conserva los términos de arte `RTC`, `attestation`, `antiquity` y `fingerprint`, porque aparecen igual en el protocolo, los logs y las APIs.

## Verificar antes de confiar

Antes de minar, ejecuta los comandos de verificación. Muestran qué se enviará al nodo y permiten revisar el payload sin iniciar una sesión de minería.

```bash
python3 miners/linux/rustchain_linux_miner.py --dry-run --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --show-payload --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --test-only --wallet YOUR_WALLET_ID
```

No traduzcas ni cambies las flags anteriores. `--dry-run`, `--show-payload` y `--test-only` son comandos literales.

## Qué hace el miner

El miner de Linux detecta la máquina local, recoge señales honestas de hardware y envía una `attestation` al nodo RustChain. Esas señales forman un `fingerprint` de hardware que se usa para estimar la `antiquity` de la máquina y aplicar el multiplicador correcto.

El miner no debe inventar arquitectura, edad del hardware, número de núcleos, número de serie, hostname ni ninguna otra señal. Si una señal no está disponible, el comportamiento correcto es declarar su ausencia o degradar la verificación.

## Instalar dependencias

```bash
python3 --version
python3 -m pip install requests
```

En distribuciones Debian/Ubuntu, si `python3` o `pip` no están instalados:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip
```

## Ejecutar el miner

```bash
python3 miners/linux/rustchain_linux_miner.py --wallet YOUR_WALLET_ID
```

Usa una cartera o identificador que puedas reconocer después. El payout de bounties puede usar `github:tu-usuario`, pero la minería normal usa el valor pasado en `--wallet`.

## Consentimiento de primera ejecución

En la primera ejecución interactiva, el usuario debe confirmar explícitamente que entiende:

- el miner envía datos de `fingerprint` y `attestation` al nodo RustChain;
- los comandos de verificación deben usarse antes de minar;
- las recompensas en `RTC` no están garantizadas;
- la máquina debe presentarse de forma honesta, sin spoofing de hardware.

Respuesta afirmativa en español: `SI`.

## Referencia cruzada

Para una explicación corta del protocolo y de los términos preservados, lee:

- [RUSTCHAIN_EXPLAINED.md](../../docs/es-ES/RUSTCHAIN_EXPLAINED.md)

## Glosario

| Término | Cómo mantenerlo | Nota |
|---|---|---|
| `RTC` | `RTC` | Token nativo de RustChain. |
| `attestation` | `attestation` | Prueba enviada al nodo sobre la máquina. |
| `antiquity` | `antiquity` | Edad/rareza relativa usada en el multiplicador. |
| `fingerprint` | `fingerprint` | Conjunto de señales de hardware. |
