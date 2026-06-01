# RustChain Miner pour Linux (fr-FR)

Ce guide localise le flux du mineur Linux pour les francophones. Il préserve les termes de l'art `RTC`, `attestation`, `antiquity` et `fingerprint`, car ces termes apparaissent dans le protocole, les journaux et les API.

## Vérifier avant de faire confiance

Avant de miner, exécutez les commandes de vérification. Elles montrent ce qui sera envoyé au nœud et vous permettent de revoir le payload sans démarrer une session de minage.

```bash
python3 miners/linux/rustchain_linux_miner.py --dry-run --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --show-payload --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --test-only --wallet YOUR_WALLET_ID
```

Ne traduisez ni ne modifiez les drapeaux ci-dessus. `--dry-run`, `--show-payload` et `--test-only` sont des commandes littérales.

## Ce que fait le mineur

Le mineur Linux détecte la machine locale, collecte des signaux matériels honnêtes et envoie une `attestation` au nœud RustChain. Ces signaux forment une `fingerprint` matérielle utilisée pour évaluer l'`antiquity` de la machine et appliquer le bon multiplicateur.

Le mineur ne doit pas fabriquer d'architecture, d'âge de matériel, de nombre de cœurs, de série, de nom d'hôte ou de tout autre signal. Si un signal n'est pas disponible, le bon comportement est de déclarer l'absence ou de dégrader la vérification.

## Installer les dépendances

```bash
python3 --version
python3 -m pip install requests
```

Sur les distributions Debian/Ubuntu, si `python3` ou `pip` ne sont pas installés :

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip
```

## Exécuter le mineur

```bash
python3 miners/linux/rustchain_linux_miner.py --wallet YOUR_WALLET_ID
```

Utilisez un portefeuille ou un identifiant que vous pouvez reconnaître plus tard. Le paiement des bounties peut utiliser `github:votre-utilisateur`, mais le minage normal utilise la valeur passée dans `--wallet`.

## Premier consentement

Lors de la première exécution interactive, l'utilisateur doit explicitement confirmer qu'il comprend :

- le mineur envoie des données de `fingerprint` et d'`attestation` au nœud RustChain ;
- les commandes de vérification doivent être utilisées avant le minage ;
- les récompenses en `RTC` ne sont pas garanties ;
- la machine doit se présenter honnêtement, sans usurpation (spoofing) de matériel.

Réponse affirmative en français : `OUI`.

## Référence croisée

Pour une brève explication du protocole et des termes conservés, lisez :

- [RUSTCHAIN_EXPLAINED.md](../../docs/fr-FR/RUSTCHAIN_EXPLAINED.md)

## Glossaire

| Terme | Comment conserver | Remarque |
|---|---|---|
| `RTC` | `RTC` | Jeton natif de RustChain. |
| `attestation` | `attestation` | Preuve envoyée au nœud à propos de la machine. |
| `antiquity` | `antiquity` | Âge/rareté relative utilisé dans le multiplicateur. |
| `fingerprint` | `fingerprint` | Ensemble de signaux matériels. |
