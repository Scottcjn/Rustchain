# RustChain erklärt (de-DE)

RustChain ist ein Proof-of-Antiquity-Netzwerk, das reale Maschinen, insbesondere ältere Hardware, dafür belohnt, dass sie nachweisen, dass sie weiterhin in Betrieb sind. Die Kernidee ist einfach: Erhaltene Hardware hat einen Wert, und das Netzwerk muss in der Lage sein, eine reale Maschine von einer virtuellen Maschine (VM), einem Container oder einer gefälschten Deklaration zu unterscheiden.

## Wie die Verifizierung funktioniert

Der Miner sammelt lokale Signale und sendet eine `attestation` an den RustChain-Knoten. Diese `attestation` enthält einen Hardware-Fingerabdruck (`fingerprint`). Der Knoten verwendet diese Daten, um das Alter/die Seltenheit (`antiquity`) der Maschine zu bewerten und den Belohnungsmultiplikator zu berechnen.

Der Prozess muss ehrlich sein:

- Simulieren Sie die Architektur nicht;
- Erzwingen Sie keine Prozessor-Familie, die die Maschine nicht besitzt;
- Ändern Sie die Nutzlast (Payload) nicht, um älter zu erscheinen;
- Übersetzen Sie keine Befehlsoptionen oder API-Endpunktnamen.

## Vor dem Mining überprüfen

Verwenden Sie die folgenden Befehle, bevor Sie einen Miner laufen lassen:

```bash
python3 miners/linux/rustchain_linux_miner.py --dry-run --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --show-payload --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --test-only --wallet YOUR_WALLET_ID
```

Diese Befehle ermöglichen es Ihnen, die erkannte Maschine, die `attestation`-Nutzlast und die Konnektivität mit dem Knoten zu überprüfen. Sie müssen in der lokalisierten Dokumentation exakt so beibehalten werden.

## Worüber der Benutzer einwilligt

Durch die Bestätigung des ersten Starts erklärt der Benutzer sein Einverständnis damit, dass:

1. Der Miner `fingerprint`- und `attestation`-Daten senden darf;
2. Die Hardware ehrlich deklariert werden muss;
3. Belohnungen in `RTC` von der Annahme durch das Netzwerk abhängen und nicht garantiert sind;
4. Spoofing (Fälschung), unerkannte Emulation oder manipulierte Nutzlasten Belohnungen reduzieren oder zur Ablehnung führen können.

Der Zustimmungsbildschirm auf Deutsch muss eine explizite affirmative Bestätigung erfordern, wie z. B. `JA`. Das bloße Drücken der Eingabetaste darf das Mining nicht starten.

## Beibehaltenes Glossar

| Begriff | Operative Bedeutung |
|---|---|
| `RTC` | Token, das von RustChain für Belohnungen und Bounties verwendet wird. |
| `attestation` | Überprüfbare Deklaration der Maschine, die an den Knoten gesendet wird. |
| `antiquity` | Signal für Alter, Seltenheit und Erhaltung der Hardware. |
| `fingerprint` | Satz von Hardware-Signalen, die zur Verifizierung verwendet werden. |

## Leitfaden für Linux-Miner

Der lokalisierte Leitfaden für den Linux-Miner befindet sich unter:

- [miners/linux/README.de-DE.md](../../miners/linux/README.de-DE.md)
