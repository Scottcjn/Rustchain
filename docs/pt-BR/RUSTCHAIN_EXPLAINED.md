# RustChain explicada (pt-BR)

RustChain e uma rede Proof-of-Antiquity que recompensa maquinas reais, especialmente hardware antigo, por provar que continuam operando. A ideia central e simples: hardware preservado tem valor, e a rede deve conseguir diferenciar uma maquina real de uma VM, container ou declaracao fabricada.

## Como a verificacao funciona

O minerador coleta sinais locais e envia uma `attestation` ao no RustChain. Essa `attestation` inclui um `fingerprint` de hardware. O no usa esses dados para estimar a `antiquity` da maquina e calcular o multiplicador de recompensa.

O processo deve ser honesto:

- nao invente arquitetura;
- nao force uma familia de CPU que a maquina nao possui;
- nao altere o payload para parecer mais antigo;
- nao traduza flags de comando ou nomes de endpoints.

## Verificar antes de minerar

Use os comandos abaixo antes de deixar qualquer minerador rodando:

```bash
python3 miners/linux/rustchain_linux_miner.py --dry-run --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --show-payload --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --test-only --wallet YOUR_WALLET_ID
```

Esses comandos ajudam a revisar a maquina detectada, o payload de `attestation` e a conectividade com o no. Eles devem permanecer exatamente assim em documentacao localizada.

## O que o usuario consente

Ao confirmar a primeira execucao, o usuario declara que entende que:

1. o minerador pode enviar dados de `fingerprint` e `attestation`;
2. o hardware deve ser reportado honestamente;
3. recompensas em `RTC` dependem da aceitacao da rede e nao sao garantidas;
4. spoofing, emulacao nao declarada ou payload fabricado podem reduzir recompensas ou causar rejeicao.

A tela de consentimento em portugues deve exigir uma entrada afirmativa explicita, como `SIM`. Apenas pressionar Enter nao deve iniciar a mineracao.

## Glossario preservado

| Termo | Significado operacional |
|---|---|
| `RTC` | Token usado pela RustChain para recompensas e bounties. |
| `attestation` | Declaracao verificavel da maquina enviada ao no. |
| `antiquity` | Sinal de idade, raridade e preservacao do hardware. |
| `fingerprint` | Conjunto de sinais de hardware usados para verificacao. |

## Guia do minerador Linux

O guia localizado do minerador Linux fica em:

- [miners/linux/README.pt-BR.md](../../miners/linux/README.pt-BR.md)
