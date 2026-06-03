# RustChain Miner pour Linux (fr-FR)

Ce guide localise le flux du mineur Linux pour les utilisateurs francophones. Il conserve les termes techniques `RTC`, `attestation`, `antiquity` et `fingerprint`, car ils apparaissent dans le protocole, les journaux de console (logs) et les API.

## Vérifier avant de s'engager

Avant de lancer le minage, exécutez les commandes de vérification. Elles affichent ce qui sera envoyé au nœud et vous permettent d'examiner la charge utile (payload) sans démarrer de session de minage.

```bash
python3 miners/linux/rustchain_linux_miner.py --dry-run --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --show-payload --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --test-only --wallet YOUR_WALLET_ID
```

Ne traduisez pas et ne modifiez pas les options (flags) ci-dessus. `--dry-run`, `--show-payload` et `--test-only` sont des commandes littérales.

## Ce que fait le mineur

Le mineur Linux détecte la machine locale, collecte des signaux matériels honnêtes et envoie une `attestation` au nœud RustChain. Ces signaux forment une empreinte matérielle (`fingerprint`) utilisée pour évaluer l'ancienneté (`antiquity`) de la machine et appliquer le bon multiplicateur.

Le mineur ne doit pas simuler ou falsifier l'architecture, l'âge du matériel, le nombre de cœurs, le numéro de série, le nom d'hôte (hostname) ou tout autre signal. Si un signal n'est pas disponible, le comportement correct est de déclarer son absence ou de dégrader la vérification.

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

Utilisez une adresse de portefeuille ou un identifiant que vous pourrez reconnaître plus tard. Le paiement des bounties peut utiliser `github:votre-utilisateur`, mais le minage normal utilise la valeur passée à `--wallet`.

## Premier consentement

Lors du premier lancement interactif, l'utilisateur doit confirmer explicitement qu'il comprend :

- le mineur transmet des données de `fingerprint` et d'`attestation` au nœud RustChain ;
- les commandes de vérification doivent être utilisées avant de miner ;
- les récompenses en `RTC` ne sont pas garanties ;
- la machine doit se présenter honnêtement, sans usurpation (spoofing) de matériel.

Réponse affirmative en français : `OUI`.

## Référence croisée

Pour une explication courte du protocole et des termes préservés, veuillez lire :

- [RUSTCHAIN_EXPLAINED.md](../../docs/fr-FR/RUSTCHAIN_EXPLAINED.md)

## Glossaire

| Terme | Comment le maintenir | Remarque |
|---|---|---|
| `RTC` | `RTC` | Jeton natif de RustChain. |
| `attestation` | `attestation` | Preuve envoyée au nœud concernant la machine. |
| `antiquity` | `antiquity` | Âge/rareté relative utilisé dans le multiplicateur. |
| `fingerprint` | `fingerprint` | Ensemble de signaux matériels. |
