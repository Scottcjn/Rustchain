# RustChain expliquée (fr-FR)

RustChain est un réseau Proof-of-Antiquity qui récompense les machines réelles, en particulier le matériel ancien, pour prouver qu'elles continuent de fonctionner. L'idée centrale est simple : le matériel préservé a de la valeur, et le réseau doit pouvoir différencier une machine réelle d'une machine virtuelle (VM), d'un conteneur ou d'une déclaration falsifiée.

## Comment fonctionne la vérification

Le mineur collecte des signaux locaux et envoie une `attestation` au nœud RustChain. Cette `attestation` contient une empreinte matérielle (`fingerprint`). Le nœud utilise ces données pour évaluer l'ancienneté (`antiquity`) de la machine et calculer le multiplicateur de récompense.

Le processus doit être honnête :

- ne simulez pas l'architecture ;
- ne forcez pas une famille de processeur que la machine ne possède pas ;
- ne modifiez pas la charge utile (payload) pour paraître plus ancien ;
- ne traduisez pas les options de commande ou les noms de points d'accès (endpoints).

## Vérifier avant de miner

Utilisez les commandes ci-dessous avant de laisser tourner un mineur :

```bash
python3 miners/linux/rustchain_linux_miner.py --dry-run --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --show-payload --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --test-only --wallet YOUR_WALLET_ID
```

Ces commandes vous permettent de passer en revue la machine détectée, la charge utile d' `attestation` et la connectivité avec le nœud. Elles doivent rester exactement telles quelles dans la documentation localisée.

## Ce à quoi consent l'utilisateur

En confirmant le premier lancement, l'utilisateur déclare comprendre que :

1. le mineur peut envoyer des données de `fingerprint` et d'`attestation` ;
2. le matériel doit être déclaré honnêtement ;
3. les récompenses en `RTC` dépendent de l'acceptation par le réseau et ne sont pas garanties ;
4. l'usurpation (spoofing), l'émulation non déclarée ou les charges utiles falsifiées peuvent réduire les récompenses ou entraîner un rejet.

L'écran de consentement en français doit exiger une confirmation affirmative explicite, telle que `OUI`. Appuyer simplement sur Entrée ne doit pas démarrer le minage.

## Glossaire préservé

| Terme | Signification opérationnelle |
|---|---|
| `RTC` | Jeton utilisé par RustChain pour les récompenses et bounties. |
| `attestation` | Déclaration vérifiable de la machine envoyée au nœud. |
| `antiquity` | Signal d'âge, de rareté et de préservation du matériel. |
| `fingerprint` | Ensemble de signaux matériels utilisés pour la vérification. |

## Guide du mineur Linux

Le guide localisé du mineur Linux se trouve à l'adresse suivante :

- [miners/linux/README.fr-FR.md](../../miners/linux/README.fr-FR.md)
