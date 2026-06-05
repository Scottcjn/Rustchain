# RustChain Miner pour Linux (fr-FR)

Ce guide localise le fonctionnement du miner Linux pour les utilisateurs francophones. Il conserve les termes techniques `RTC`, `attestation`, `antiquity` et `fingerprint` car ils apparaissent dans le protocole, les journaux de console (logs) et les API.

## À vérifier avant de démarrer

Avant de lancer le minage, exécutez les commandes de vérification. Celles-ci indiquent ce qui sera envoyé au nœud et vous permettent de valider la charge utile (payload) sans démarrer de session de minage active.

```bash
python3 miners/linux/rustchain_linux_miner.py --dry-run --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --show-payload --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --test-only --wallet YOUR_WALLET_ID
```

Ne traduisez ni ne modifiez pas les options (flags) ci-dessus. `--dry-run`, `--show-payload` et `--test-only` sont des commandes littérales.

## Ce que fait le miner

Le miner Linux détecte la machine locale, collecte d'honnêtes signaux matériels et envoie une `attestation` au nœud RustChain. Ces signaux forment une empreinte matérielle (`fingerprint`) utilisée pour évaluer l'âge/la rareté (`antiquity`) de la machine et appliquer le bon multiplicateur.

Le miner ne doit pas simuler ou falsifier l'architecture, l'âge du matériel, le nombre de cœurs, le numéro de série, le nom d'hôte ou tout autre signal. Si un signal n'est pas disponible, le comportement correct consiste à déclarer son absence ou à dégrader la vérification.

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

## Exécuter le miner

```bash
python3 miners/linux/rustchain_linux_miner.py --wallet YOUR_WALLET_ID
```

Utilisez une adresse de portefeuille ou un identifiant que vous pourrez reconnaître plus tard. Le paiement des bounties peut utiliser `github:votre-nom-d-utilisateur`, mais le minage normal utilise la valeur passée à `--wallet`.

## Consentement initial

Lors du premier démarrage interactif, l'utilisateur doit confirmer explicitement qu'il comprend que :

- Le miner transmettra les données de `fingerprint` et d'`attestation` au nœud RustChain ;
- Les commandes de vérification doivent être utilisées avant de miner ;
- Les récompenses en `RTC` ne sont pas garanties ;
- La machine doit se présenter honnêtement, sans usurpation (spoofing) de matériel.

Réponse affirmative en français : **`OUI`**.

## Référence croisée

Pour une explication rapide du protocole et des termes conservés, veuillez lire :

- [RUSTCHAIN_EXPLAINED.md](../../docs/fr-FR/RUSTCHAIN_EXPLAINED.md)

## Glossaire

| Terme | Traitement du terme | Note |
|---|---|---|
| `RTC` | `RTC` | Jeton natif de RustChain. |
| `attestation` | `attestation` | Preuve de la machine envoyée au nœud. |
| `antiquity` | `antiquity` | Âge/rareté relative utilisé dans le multiplicateur. |
| `fingerprint` | `fingerprint` | Ensemble de signaux matériels. |
