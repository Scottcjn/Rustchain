# RustChain expliqué (fr-FR)

RustChain est un réseau Proof-of-Antiquity qui récompense les machines physiques réelles, en particulier le matériel ancien (vintage), pour prouver qu'elles continuent de fonctionner. L'idée centrale est simple : le matériel préservé a de la valeur, et le réseau doit être capable de distinguer une machine réelle d'une machine virtuelle (VM), d'un conteneur ou d'une fausse déclaration.

## Comment fonctionne la vérification

Le miner collecte des signaux locaux et envoie une `attestation` au nœud RustChain. Cette `attestation` comprend une empreinte matérielle (`fingerprint`). Le nœud utilise ces données pour évaluer l'âge/la rareté (`antiquity`) de la machine et calculer le multiplicateur de récompense.

Le processus doit être honnête :

- Ne simulez pas l'architecture ;
- Ne forcez pas une famille de processeurs que la machine ne possède pas ;
- Ne modifiez pas la charge utile (payload) pour paraître plus ancien ;
- Ne traduisez pas les options de commande ni les noms d'endpoints d'API.

## Vérifier avant de miner

Utilisez les commandes suivantes avant de laisser un miner s'exécuter :

```bash
python3 miners/linux/rustchain_linux_miner.py --dry-run --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --show-payload --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --test-only --wallet YOUR_WALLET_ID
```

Ces commandes vous permettent de vérifier la machine détectée, la charge utile de l'`attestation` et la connectivité avec le nœud. Elles doivent être conservées exactement telles quelles dans la documentation localisée.

## Ce que l'utilisateur consent

En confirmant le premier démarrage, l'utilisateur déclare comprendre que :

1. Le miner peut envoyer des données de `fingerprint` et d'`attestation` ;
2. Le matériel doit être déclaré honnêtement ;
3. Les récompenses en `RTC` dépendent de l'acceptation par le réseau et ne sont pas garanties ;
4. L'usurpation (spoofing), l'émulation non déclarée ou les charges utiles manipulées peuvent réduire les récompenses ou entraîner un rejet.

L'écran de consentement en français doit exiger une confirmation affirmative explicite, telle que **`OUI`**. Appuyer simplement sur Entrée ne doit pas démarrer le minage.

## Glossaire conservé

| Terme | Signification opérationnelle |
|---|---|
| `RTC` | Jeton utilisé par RustChain pour les récompenses et les bounties. |
| `attestation` | Déclaration vérifiable de la machine envoyée au nœud. |
| `antiquity` | Signal d'âge, de rareté et de préservation du matériel. |
| `fingerprint` | Ensemble de signaux matériels utilisés pour la vérification. |

## Guide du miner Linux

Le guide localisé du miner Linux se trouve à l'adresse suivante :

- [miners/linux/README.fr-FR.md](../../miners/linux/README.fr-FR.md)
