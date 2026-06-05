# RustChain Miner für Linux (de-DE)

Dieses Handbuch lokalisiert den Ablauf des Linux-Miners für deutschsprachige Benutzer. Es behält die technischen Begriffe `RTC`, `attestation`, `antiquity` und `fingerprint` bei, da sie im Protokoll, in den Konsolenprotokollen (Logs) und in den APIs vorkommen.

## Vor dem Start überprüfen

Führen Sie vor dem Starten des Minings die Überprüfungsbefehle aus. Diese zeigen an, was an den Knoten gesendet wird, und ermöglichen es Ihnen, die Nutzlast (Payload) zu überprüfen, ohne eine Mining-Sitzung zu starten.

```bash
python3 miners/linux/rustchain_linux_miner.py --dry-run --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --show-payload --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --test-only --wallet YOUR_WALLET_ID
```

Übersetzen oder ändern Sie die oben genannten Optionen (Flags) nicht. `--dry-run`, `--show-payload` und `--test-only` sind wörtliche Befehle.

## Was der Miner tut

Der Linux-Miner erkennt die lokale Maschine, sammelt ehrliche Hardware-Signale und sendet eine `attestation` an den RustChain-Knoten. Diese Signale bilden einen Hardware-Fingerabdruck (`fingerprint`), der verwendet wird, um das Alter/die Seltenheit (`antiquity`) der Maschine zu bewerten und den richtigen Multiplikator anzuwenden.

Der Miner darf die Architektur, das Alter der Hardware, die Anzahl der Kerne, die Seriennummer, den Hostnamen oder andere Signale nicht simulieren oder fälschen. Wenn ein Signal nicht verfügbar ist, besteht das korrekte Verhalten darin, sein Fehlen zu deklarieren oder die Verifizierung herabzustufen.

## Abhängigkeiten installieren

```bash
python3 --version
python3 -m pip install requests
```

Auf Debian/Ubuntu-Distributionen, falls `python3` oder `pip` nicht installiert sind:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip
```

## Miner ausführen

```bash
python3 miners/linux/rustchain_linux_miner.py --wallet YOUR_WALLET_ID
```

Verwenden Sie eine Wallet-Adresse oder eine Kennung, die Sie später wiedererkennen können. Die Auszahlung von Bounties kann `github:ihr-benutzername` verwenden, das normale Mining verwendet jedoch den an `--wallet` übergebenen Wert.

## Erstmalige Zustimmung

Beim ersten interaktiven Start muss der Benutzer explizit bestätigen, dass er Folgendes versteht:

- Der Miner überträgt `fingerprint`- und `attestation`-Daten an den RustChain-Knoten;
- Die Überprüfungsbefehle müssen vor dem Mining verwendet werden;
- Belohnungen in `RTC` sind nicht garantiert;
- Die Maschine muss sich ehrlich darstellen, ohne Hardware-Spoofing (Fälschung).

Affirmative (zustimmende) Antwort auf Deutsch: `JA`.

## Querverweis

Für eine kurze Erklärung des Protokolls und der beibehaltenen Begriffe lesen Sie bitte:

- [RUSTCHAIN_EXPLAINED.md](../../docs/de-DE/RUSTCHAIN_EXPLAINED.md)

## Glossar

| Begriff | Umgang mit dem Begriff | Hinweis |
|---|---|---|
| `RTC` | `RTC` | Nativer Token von RustChain. |
| `attestation` | `attestation` | An den Knoten gesendeter Nachweis über die Maschine. |
| `antiquity` | `antiquity` | Relatives Alter/Seltenheit, das im Multiplikator verwendet wird. |
| `fingerprint` | `fingerprint` | Satz von Hardware-Signalen. |
