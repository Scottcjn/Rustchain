# RustChain

> **🇳🇱 Nederlandse vertaling** | [English](../README.md)
> Technische termen blijven in het Engels: RTC, attiquity, fingerprint, consensus, epoch, Proof-of-Antiquity.
> Codeblokken en commando's zijn NIET vertaald.

---

# RustChain — Netwerk van Fysieke AI

## Wat is RustChain?

RustChain is een gedistribueerd netwerk van artificiële intelligentie dat wereldwijd rekennimt coherentie dichterbij brengt. Het netwerk stelt knopen (nodes) in staat om via consensus te stemmen over inhoud die door modellen van artificiële intelligentie wordt gegenereerd. Het netwerk is vernoemd naar de programmeertaal Rust en de onderliggende technologie van een gedistribueerd grootboek (blockchain), waardoor twee onafhankelijke informatiebronnen de waarheid kunnen bewijzen. Consensus = waarheid.

## Kernkenmerken

### Proof-of-Antiquity (PoA)
Het unieke consensusmechanisme van RustChain dat knoden verplicht om hun fysieke identiteit te bewijzen attiquiteit (ouderdom/historie) authentieke deelname. Dit voorkomt Sybil-aanvallen zonder centrale autoriteit.

### Gedistribueerd AI-netwerk
- **Consensus-gestuurde validatie**: Meerdere knoden stemmen over AI-gegenereerde inhoud
- **Fysieke verificatie**: Hardware-vingerafdrukken bevestigen unieke deelnemers
- **Beloning in RTC**: Netwerkdeelnemers verdienen RTC-tokens bij het bijdragen aan consensus

### Technische architectuur
- Gebouwd in **Rust** voor prestaties en geheugenveiligheid
- **Blockchain-grootboek** voor transactie- en consensusregistratie
- **P2P-netwerklaag** voor gedistribueerde communicatie
- **Hardware Attestation** voor fysieke aanwezigheidsverificatie

## Hoe het werkt

### 1. Knopstart (Node Boot)
Wanneer een nieuw knooppunt zich bij het netwerk aansluit, genereert het:
- Een unieke hardware-vingerafdruk
- Een kryptografisch sleutelpaar
- Een attiteitsbewijs (proof of antiquity)

### 2. Consensusronde
1. Een AI-model genereert inhoud (bijv. een antwoord op een vraag)
2. Het netwerk selecteert willekeurige validator-knopen
3. Validators verifiëren de inhoud tegen hun eigen modellen
4. Consensus wordt bereikt wanneer >51% het eens is

### 3. Beloning
- Validators die meestemmen met de consensus ontvangen RTC
- Het bedrag hangt af van attiteitsgewicht en netwerkomstandigheden
- Beloningen worden per époque (epoch) uitbetaald

## Installatie

### Linux-miner
```bash
# Kloon de repository
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain

# Bouw de miner
cargo build --release

# Start de miner
./target/release/rustchain-miner --wallet jesusmp
```

### Docker
```bash
docker run -d --name rustchain-miner \
  -e WALLET=jesusmp \
  rustchain/miner:latest
```

## Mining

Mining op RustChain vereist:
1. **Hardware**: Minstens 4GB RAM, moderne CPU (SSE4.2+)
2. **Netwerk**: Stabiele internetverbinding
3. **Wallet**: Een RTC-walletnaam (bijv. "mijn_wallet")

Het mining-proces:
1. Registreer uw wallet bij het netwerk
2. Start de miner-software
3. De miner neemt deel aan consensusrondes
4. Verdien RTC voor correcte validatie

## Veelgestelde Vragen (FAQ)

### Wat is RTC?
RTC (RustChain Token) is het native utility-token van het RustChain-netwerk. Het wordt gebruikt voor:
- Beloning van netwerkdeelnemers
- Transactiekosten
- Governance-stemmen

### Hoeveel RTC kan ik verdien?
Dit hangt af van:
- Het aantal actieve deelnemers in uw époque
- Uw attiteitsgewicht (hoe langer u actief bent, hoe meer u verdient)
- Netwerkbelasting

### Is RustChain Proof of Work?
Nee. RustChain gebruikt **Proof-of-Antiquity (PoA)**, een uniek mechanisme dat zowel fysieke aanwezigheid als rekenkracht vereist. Dit is energiezuiniger dan traditioneel Proof of Work.

## Bijdragen

We verwelkomen bijdragen! Zie [CONTRIBUTING.md](../../CONTRIBUTING.md) voor richtlijnen.

## Licentie

Dit project is gelicentieerd onder de MIT-licentie.

## Contact

- **GitHub**: https://github.com/Scottcjn/Rustchain
- **Discord**: https://discord.gg/rustchain
- **Website**: https://rustchain.org

---

*Deze vertaling is gemaakt als onderdeel van het RustChain documentatie-bountyprogramma.*
*Vertaling: Nederlands (nl-NL) | Wallet: jesusmp*
