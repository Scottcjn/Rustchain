# RustChain expliqué (fr-FR)

RustChain est un réseau Proof-of-Antiquity qui récompense les vraies machines, en particulier le vieux matériel, pour prouver qu'elles fonctionnent toujours. L'idée centrale est simple : le matériel préservé a de la valeur, et le réseau doit pouvoir différencier une vraie machine d'une VM, d'un conteneur ou d'une déclaration fabriquée.

## Comment fonctionne la vérification

Le mineur collecte des signaux locaux et envoie une `attestation` au nœud RustChain. Cette `attestation` inclut une `fingerprint` matérielle. Le nœud utilise ces données pour estimer l'`antiquity` de la machine et calculer le multiplicador de récompense.

Le processus doit être honnête :

- n'inventez pas d'architecture ;
- ne forcez pas une famille de processeurs que la machine ne possède pas ;
- ne modifiez pas le payload pour qu'il paraisse plus ancien ;
- ne traduisez pas les drapeaux de commande ou les noms des terminaux.

## Vérifier avant de miner

Utilisez les commandes ci-dessous avant de laisser tout mineur fonctionner :

```bash
python3 miners/linux/rustchain_linux_miner.py --dry-run --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --show-payload --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --test-only --wallet YOUR_WALLET_ID
```

Ces commandes vous aident à revoir la machine détectée, le payload d'`attestation` et la connectivité au nœud. Elles doivent rester exactement comme cela dans la documentation localisée.

## Ce à quoi l'utilisateur consent

Lors de la confirmation de la première exécution, l'utilisateur déclare qu'il comprend que :

1. le mineur peut envoyer des données de `fingerprint` et d'`attestation` ;
2. le matériel doit être déclaré honnêtement ;
3. les récompenses en `RTC` dépendent de l'acceptation du réseau et ne sont pas garanties ;
4. le spoofing, l'émulation non déclarée ou un payload fabriqué peuvent réduire les récompenses ou entraîner un rejet.

L'écran de consentement en français doit exiger une saisie affirmative explicite, telle que `OUI`. Appuyer simplement sur Entrée ne doit pas démarrer le minage.

## Glossaire préservé

| Termo | Signification opérationnelle |
|---|---|
| `RTC` | Jeton utilisé par RustChain pour les récompenses et les bounties. |
| `attestation` | Déclaration vérifiable de la machine envoyée au nœud. |
| `antiquity` | Signal de l'âge, rareté et préservation du matériel. |
| `fingerprint` | Ensemble de signaux matériels utilisés pour la vérification. |

## Guide du mineur Linux

Le guide localisé du mineur Linux se trouve sur :

- [miners/linux/README.fr-FR.md](../../miners/linux/README.fr-FR.md)
