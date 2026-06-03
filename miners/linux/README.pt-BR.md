# RustChain Miner para Linux (pt-BR)

Este guia localiza o fluxo do minerador Linux para falantes de portugues do Brasil. Ele preserva os termos de arte `RTC`, `attestation`, `antiquity` e `fingerprint`, porque esses termos aparecem no protocolo, nos logs e nas APIs.

## Verificar antes de confiar

Antes de minerar, rode os comandos de verificacao. Eles mostram o que sera enviado ao no e permitem revisar o payload sem iniciar uma sessao de mineracao.

```bash
python3 miners/linux/rustchain_linux_miner.py --dry-run --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --show-payload --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --test-only --wallet YOUR_WALLET_ID
```

Nao traduza nem altere as flags acima. `--dry-run`, `--show-payload` e `--test-only` sao comandos literais.

## O que o minerador faz

O minerador Linux detecta a maquina local, coleta sinais honestos de hardware e envia uma `attestation` ao no RustChain. Esses sinais formam um `fingerprint` de hardware usado para avaliar a `antiquity` da maquina e aplicar o multiplicador correto.

O minerador nao deve fabricar arquitetura, idade do hardware, numero de nucleos, serial, hostname ou qualquer outro sinal. Se um sinal nao estiver disponivel, o comportamento correto e declarar a ausencia ou degradar a verificacao.

## Instalar dependencias

```bash
python3 --version
python3 -m pip install requests
```

Em distribuicoes Debian/Ubuntu, se `python3` ou `pip` nao estiverem instalados:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip
```

## Executar o minerador

```bash
python3 miners/linux/rustchain_linux_miner.py --wallet YOUR_WALLET_ID
```

Use uma carteira ou identificador que voce consiga reconhecer depois. O payout de bounties pode usar `github:seu-usuario`, mas a mineracao normal usa o valor passado em `--wallet`.

## Primeiro consentimento

Na primeira execucao interativa, o usuario deve confirmar explicitamente que entende:

- o minerador envia `fingerprint` e dados de `attestation` ao no RustChain;
- os comandos de verificacao devem ser usados antes da mineracao;
- recompensas em `RTC` nao sao garantidas;
- a maquina deve se apresentar honestamente, sem spoofing de hardware.

Resposta afirmativa em portugues: `SIM`.

## Referencia cruzada

Para uma explicacao curta do protocolo e dos termos preservados, leia:

- [RUSTCHAIN_EXPLAINED.md](../../docs/pt-BR/RUSTCHAIN_EXPLAINED.md)

## Glossario

| Termo | Como manter | Observacao |
|---|---|---|
| `RTC` | `RTC` | Token nativo da RustChain. |
| `attestation` | `attestation` | Prova enviada ao no sobre a maquina. |
| `antiquity` | `antiquity` | Idade/raridade relativa usada no multiplicador. |
| `fingerprint` | `fingerprint` | Conjunto de sinais de hardware. |
