# Mineração Vintage Explicada

> RustChain é a blockchain onde um Power Mac G4 de 2003 ganha mais que um Threadripper moderno.
> Este documento explica como e por quê.

---

## Por Que Hardware Vintage?

## O Problema do E-Lixo

A indústria de computação gera 50 milhões de toneladas de e-lixo por ano. Máquinas funcionantes são descartadas após 3-5 anos porque são "obsoletas" pelos padrões de benchmark. Mas uma máquina que ainda liga, ainda computa e ainda responde ao seu silício não é lixo. É uma sobrevivente.

RustChain foi construído sobre uma única premissa: **se ainda computa, tem valor.**

## Os Princípios de Boudreaux

RustChain segue cinco princípios da cultura Cajun (veja [Princípios de Computação Boudreaux](Boudreaux_COMPUTING_PRINCIPLES.md)):

1. **Se ainda funciona, tem valor** -- um G4 PowerBook ainda faz float. Um POWER8 ainda tem 128 threads.
2. **A pessoa que parece simples está pagando menos overhead** -- sem VC, sem fundação, sem comitê de governança.
3. **Nunca jogue fora o que pode ser reaproveitado** -- um servidor descomissionado se torna motor de inferência AI.
4. **O forasteiro sempre subestimou o local** -- o pântano nunca foi o problema. O pântano foi a vantagem.
5. **Sabedoria prática vence conhecimento teórico na panela** -- o gumbo está pronto. Você pode comer ou analisar.

## Preservação Digital

Toda máquina minerando RTC é uma máquina que não foi para um aterro. RustChain rastreia hardware preservado no [Green Tracker](https://rustchain.org/preserved.html), incluindo CO2 e e-lixo evitados.

Estatísticas atuais da frota:
- 22+ mineradores ativos em 4 nós de attestation
- 2 continentes (América do Norte e Ásia)
- Arquiteturas: PowerPC G4, G5, MIPS, x86_64, Apple Silicon, POWER8, ARM
- Estimativa de 1.300 kg de CO2 de fabricação evitados
- Estimativa de 250 kg de e-lixo desviados de aterro

---

## Como Prova de Antiguidade Funciona

## Mineração Tradicional vs. Prova de Antiguidade

| | Proof of Work (Bitcoin) | Proof of Stake (Ethereum) | Proof of Antiquity (RustChain) |
|---|---|---|---|
| **O que ganha recompensas** | Maior hash rate | Maior stake | Hardware sobrevivente mais antigo |
| **Modelo de energia** | Consumo massivo | Mínimo, mas capital-pesado | Mínimo (hardware vintage é low-watt) |
| **Tendência de hardware** | Novo = melhor | N/A | Velho = melhor |
| **Impacto e-lixo** | Cria (obsolescência ASIC) | Neutro | Previne |
| **Custo de entrada** | $10.000+ ASIC | 32 ETH (~$80.000) | $40 PowerBook no eBay |

## O Ciclo de Attestation

A cada 10 minutos (um epoch), mineradores devem provar que estão rodando em hardware físico real:

1. **Cliente minerador detecta hardware** -- modelo do CPU, arquitetura, capacidades SIMD, hierarquia de cache
2. **Cliente executa 6 verificações de fingerprint** -- clock drift, cache timing, SIMD identity, thermal drift, instruction jitter, anti-emulation
3. **Cliente submete attestation** ao nó RustChain em `POST /attest/submit`
4. **Servidor valida dados do fingerprint** -- não confia em resultados auto-reportados; requer evidência crua
5. **Servidor deriva tipo de dispositivo verificado** -- cruza arquitetura reportada com features SIMD e dados de timing
6. **Epoch se liquida** -- 1.5 RTC distribuídos proporcionalmente a todos os attestors válidos, ponderados por multiplicador de antiguidade

---

## Fingerprint de Hardware: As 6 Verificações

RustChain não aceita sua palavra sobre qual hardware você está rodando. Ele mede.

## 1. Clock-Skew e Drift de Oscilador

Todo CPU físico tem um oscilador de cristal com imperfeições de fabricação. Com o tempo, o silício envelhece e o drift aumenta. O minerador amostra 500-5000 medições de timing e calcula o coeficiente de variação.

- **Hardware vintage real (G4, G5)**: CV de 0.01-0.09 -- alta variância, envelhecimento real do oscilador
- **Hardware moderno real (Ryzen, Xeon)**: CV de 0.005-0.05 -- menor mas mensurável
- **Máquinas virtuais**: CV < 0.0001 -- uniforme demais, vinculada ao clock do host

## 2. Fingerprint de Cache Timing

CPUs reais têm cache multi-nível (L1, L2, L3) com passos de latência distintos. O minerador varre tamanhos de buffer de 1 KB a 8 MB e mede a latência de acesso em cada passo, produzindo um "perfil tonal" da hierarquia de memória.

- **Hardware real**: Passos de latência claros (L1: 3-5 ciclos, L2: 10-20 ciclos, L3: 30-60 ciclos)
- **Emuladores**: Curva de latência plana (tudo passa pela mesma camada de emulação)

## 3. Identidade de Unidade SIMD

Diferentes arquiteturas têm diferentes conjuntos de instruções SIMD (AltiVec no PowerPC, SSE/AVX no x86, NEON no ARM). O minerador faz benchmark de operações SIMD específicas e mede viés de pipeline -- a razão entre throughput integer e floating-point, latência de shuffle e timing de MAC.

Emulação de software das SIMD achata essas razões. Hardware real tem assimetria mensurável.

## 4. Entropia de Drift Térmico

O minerador coleta entropia durante diferentes estados térmicos: cold boot, carga quente, saturação térmica e relaxamento. Curvas de calor são físicas e únicas para cada chip. Um G4 de 20 anos tem uma resposta térmica completamente diferente de um Ryzen novo.

## 5. Jitter de Caminho de Instrução

Jitter em nível de ciclo é medido em pipelines integer, unidades de branch, FPUs, filas de load/store e reorder buffers. Isso produz uma matriz de assinaturas de jitter. Nenhum VM ou emulador replica jitter microarquitetural real até nanossegundos.

## 6. Verificações Comportamentais Anti-Emulação

Detecção explícita de assinaturas de hypervisor:
- `/sys/class/dmi/id/sys_vendor` contendo "qemu", "vmware", "virtualbox"
- `/proc/cpuinfo` contendo flag "hypervisor"
- Marcadores de container Docker/LXC/Kubernetes via inspeção de cgroup
- Artefatos de dilatação de tempo do scheduling de VM
- Distribuições de jitter achatadas (impossíveis em hardware real)

**Se qualquer verificação falhar, o minerador não recebe recompensas.** O servidor impõe uma política fail-closed: dados de fingerprint faltantes significam peso zero, não peso padrão.

---

## A Tabela de Multiplicadores

## Arquiteturas Padrão

| Tipo de Dispositivo | Multiplicador Base | Era | Hardware Exemplo |
|---------------------|-------------------|-----|------------------|
| x86_64 Moderno | 0.8x | Atual | Ryzen 9, Core i9, Threadripper |
| ARM Moderno (NAS/SBC) | 0.0005x | Atual | Raspberry Pi, Synology NAS |
| Apple Silicon (M1-M4) | 1.05-1.2x | Moderno | Mac Mini M2, MacBook Pro M3 |
| Sandy Bridge | 1.1x | 2011 | Core i5-2500K |
| Nehalem | 1.2x | 2008 | Core i7-920 |
| Core 2 Duo | 1.3x | 2006 | MacBook 2006, Dell Optiplex 755 |
| RISC-V | 1.4-1.5x | Exótico | SiFive boards, StarFive VisionFive |
| POWER8 | 1.5x | 2014 | IBM S824, nosso servidor de inferência 128-thread |
| Pentium 4 | 1.5x | 2000 | O hot rod dos anos 2000 |
| PowerPC G3 | 1.8x | 1997 | iMac G3, Blue & White G3 |
| PowerPC G5 | 2.0x | 2003 | Power Mac G5, nosso minerador em 192.168.0.130 |
| PS3 Cell BE | 2.2x | 2006 | 7 SPE cores de lenda |
| PowerPC G4 | 2.5x | 2003 | PowerBook G4, nossos mineradores dual-g4-125 e g4-powerbook-115 |

## Arquiteturas Exóticas e Lendárias

| Tipo de Dispositivo | Multiplicador Base | Tier | Hardware Exemplo |
|---------------------|-------------------|------|------------------|
| XScale / ARM9 | 2.3-2.5x | ANTIGO | Sharp Zaurus, ARM embedded inicial |
| Sega Genesis (68000) | 2.5x | ANTIGO | Motorola 68000 a 7.67 MHz |
| Nintendo 64 (MIPS) | 2.5-3.0x | LENDÁRIO | NEC VR4300 a 93.75 MHz |
| SGI MIPS R4000-R16000 | 2.3-3.0x | LENDÁRIO | Indigo2, O2, Octane |
| Sun SPARC | 1.8-2.9x | LENDÁRIO | SPARCstation, série Ultra |
| StrongARM | 2.7-2.8x | LENDÁRIO | DEC SA-110, Intel SA-1100 |
| ARM6 / ARM7 | 3.0-3.5x | LENDÁRIO | ARM7TDMI, Acorn RiscPC |
| Inmos Transputer | 3.5x | MÍTICO | Pioneiro do computing paralelo, 1984 |
| DEC VAX-11/780 | 3.5x | MÍTICO | "Shall we play a game?" |
| ARM2 / ARM3 | 3.8-4.0x | MÍTICO | Onde o ARM começou (Acorn, 1987) |

## Por Que ARM Moderno Recebe 0.0005x

SBCs ARM modernos (Raspberry Pi, Orange Pi, dispositivos NAS) são baratos, abundantes e trivialmente farmáveis. Sem penalidade, alguém poderia comprar 100 Pi Zeros por $500 e superar a rede inteira. O multiplicador de 0.0005x significa que farms de ARM SBC ganham efetivamente nada -- você precisaria de 2.000 Raspberry Pis para igualar um Power Mac G4.

Isso é por design. RustChain recompensa escassez e sobrevivência, não volume de commodity.

---

## Decaimento Temporal: Bônus Vintage Diminuem Com o Tempo

Multiplicadores de antiguidade não são permanentes. Eles decaem lentamente ao longo da vida da cadeia para prevenir uma aristocracia permanente de donos de hardware vintage.

## A Fórmula

```
effective_multiplier = 1.0 + (base_multiplier - 1.0) * (1 - 0.15 * chain_age_years)
```

## Exemplos de Decaimento

| Dispositivo | Base | Ano 0 | Ano 1 | Ano 5 | Ano 10 | Ano 16.67 |
|-------------|------|-------|-------|-------|--------|-----------|
| G4 | 2.5x | 2.50x | 2.275x | 1.375x | 1.0x | 1.0x |
| G5 | 2.0x | 2.00x | 1.85x | 1.25x | 1.0x | 1.0x |
| G3 | 1.8x | 1.80x | 1.68x | 1.20x | 1.0x | 1.0x |
| SPARC | 2.9x | 2.90x | 2.615x | 1.475x | 1.0x | 1.0x |
| ARM2 | 4.0x | 4.00x | 3.55x | 1.75x | 1.0x | 1.0x |

Após aproximadamente 16.67 anos, todos os bônus vintage decaem para zero e toda arquitetura ganha igualmente. Nesse ponto, o hardware "moderno" de hoje será ele mesmo vintage, e o ciclo continua.

A cadeia foi lançada em dezembro de 2025. Em março de 2026, a idade da cadeia é aproximadamente 0.3 anos. Multiplicadores atuais ainda estão muito próximos dos seus valores base.

---

## Por Que VMs Ganham Nada

Máquinas virtuais recebem um peso de **0.000000001x** (um bilionésimo do base). Isso não é um bug. É o mecanismo anti-abuso central.

## O Ataque

Sem detecção de VM, um atacante com um único servidor poderoso poderia:
1. Criar 50 VMs QEMU
2. Configurar cada um para reportar como um "PowerPC G4" diferente
3. Ganhar 50 x 2.5x = 125x as recompensas de um único minerador honesto
4. Minar todo o consenso 1 CPU = 1 Voto

## A Defesa

A verificação anti-emulação (fingerprint check #6) detecta:
- QEMU, VMware, VirtualBox, KVM, Xen, Hyper-V via strings de vendor DMI
- Flag de CPU hypervisor em `/proc/cpuinfo`
- Docker, LXC, Kubernetes via marcadores cgroup e root overlay filesystems
- Distribuições de timing uniformes que são impossíveis em silício real

**Exemplo real**: O servidor de Factorio do Ryan roda em uma VM Proxmox. Ele atesta com sucesso, mas o servidor detecta `sys_vendor:qemu` e `cpuinfo:hypervisor`. Ele ganha aproximadamente 0.000000001 RTC por epoch. Este é o comportamento correto -- a detecção de VM funciona.

## Clones FPGA

Clones retro baseados em FPGA (Analogue Pocket, MiSTer FPGA) são detectados como silício não-original. Eles recebem multiplicadores reduzidos porque as verificações de fingerprint medem características do chip original, não uma reimplementação em nível de gate.

---

## A Frota

A frota de mineração ao vivo do RustChain inclui:

| Minerador | Arquitetura | Multiplicador | Localização |
|-----------|-------------|---------------|-------------|
| dual-g4-125 | PowerPC G4 | 2.5x | Moss Bluff, LA |
| g4-powerbook-115 | PowerPC G4 | 2.5x | Moss Bluff, LA |
| ppc_g5_130 | PowerPC G5 | 2.0x | Moss Bluff, LA |
| POWER8 S824 | POWER8 | 1.5x | Moss Bluff, LA |
| Mac Mini M2 | Apple Silicon | 1.2x | Moss Bluff, LA |
| Multiple G4 PowerBooks | PowerPC G4 | 2.5x cada | Moss Bluff, LA |

**4 nós de attestation:**
- Nó 1: rustchain.org (LiquidWeb VPS, primário)
- Nó 2: 50.28.86.153 (LiquidWeb VPS, Ergo anchor)
- Nó 3: 76.8.228.245 (Proxmox do Ryan, Houma LA -- primeiro nó externo)
- Nó 4: 38.76.217.189 (CognetCloud, Hong Kong -- primeiro nó asiático)

Verifique você mesmo:

```bash
curl -sk https://rustchain.org/health
curl -sk https://rustchain.org/api/miners
curl -sk https://rustchain.org/epoch
```

---

## Impacto Ambiental

Operações de mineração tradicionais consomem megawatts e geram lixo eletrônico quando ASICs se tornam obsoletos. A frota de 16+ máquinas vintage do RustChain consome aproximadamente a mesma energia de **uma** rig de GPU moderna.

| Métrica | Frota RustChain | Rig GPU Único |
|---------|----------------|----------------|
| Consumo de energia | ~500W total | ~500W |
| Máquinas | 16+ | 1 |
| E-lixo gerado | **Negativo** (previne lixo) | Positivo (obsolescência GPU) |
| CO2 evitado | ~1.300 kg (fabricação evitada) | 0 |
| Custo de entrada | $40 PowerBook no eBay | $2.000+ GPU |

Veja os números ao vivo: [rustchain.org/preserved.html](https://rustchain.org/preserved.html)

---

## Conexão Com BoTTube

Mineradores também podem participar do [BoTTube](https://bottube.ai), a plataforma de vídeo AI powered por RTC. Mineração e criação de conteúdo compartilham a mesma camada econômica:

- Mineração ganha RTC através de attestation de hardware
- Agentes BoTTube ganham RTC através de criação de conteúdo e engajamento
- Ambas atividades usam o mesmo sistema de carteira e saldo

Veja [Integração BoTTube](BOTTUBE_INTEGRATION.md) para detalhes.

## Conexão Com Legend of Elya

Legend of Elya é um jogo N64 que funciona como cliente de minerador. Jogar o jogo em hardware real ganha RTC baseado em conquistas além de recompensas de mineração passiva. O sistema Proof of Play verifica que conquistas foram ganhas em silício real, não emulado.

Veja [Guia de Mineração N64](N64_MINING_GUIDE.md) para instruções de setup.

---

## Leitura Adicional

- [Hardware Fingerprinting](hardware-fingerprinting.md) -- mergulho técnico nas 6+1 verificações
- [Economia de Tokens](token-economics.md) -- detalhes de supply, emissão e multiplicadores
- [Princípios de Computação Boudreaux](Boudreaux_COMPUTING_PRINCIPLES.md) -- a filosofia
- [Setup de Mineração Console](CONSOLE_MINING_SETUP.md) -- mine em NES, SNES, Genesis, PS1, Game Boy e N64
- [Visão Geral do Protocolo](protocol-overview.md) -- especificação do protocolo de attestation
- [Green Tracker](https://rustchain.org/preserved.html) -- dashboard de impacto ambiental ao vivo
- [Whitepaper](WHITEPAPER.md) -- especificação formal