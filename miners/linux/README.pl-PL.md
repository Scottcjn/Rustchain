# RustChain Miner dla Linuxa (pl-PL)

Ten przewodnik lokalizuje przepływ Linux miner dla osób czytających po polsku. Terminy `RTC`, `attestation`, `antiquity` i `fingerprint` pozostają bez tłumaczenia, ponieważ występują w protokole, logach i API.

## Sprawdź zanim zaufasz

Przed rozpoczęciem kopania uruchom komendy weryfikacyjne. Pokazują one, co zostanie wysłane do węzła, i pozwalają obejrzeć payload bez startu sesji mining.

```bash
python3 miners/linux/rustchain_linux_miner.py --dry-run --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --show-payload --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --test-only --wallet YOUR_WALLET_ID
```

Nie tłumacz ani nie zmieniaj powyższych flag. `--dry-run`, `--show-payload` i `--test-only` są literalnymi komendami.

## Co robi miner

Linux miner wykrywa lokalną maszynę, zbiera uczciwe sygnały sprzętowe i wysyła `attestation` do węzła RustChain. Te sygnały tworzą sprzętowy `fingerprint`, który pomaga ocenić `antiquity` maszyny i zastosować odpowiedni mnożnik.

Miner nie może fabrykować architektury, wieku sprzętu, liczby rdzeni, numeru seryjnego, nazwy hosta ani żadnego innego sygnału. Jeśli sygnał nie jest dostępny, prawidłowe zachowanie to zgłosić brak danych albo obniżyć poziom weryfikacji.

## Instalacja zależności

```bash
python3 --version
python3 -m pip install requests
```

W dystrybucjach Debian/Ubuntu, jeśli `python3` lub `pip` nie są zainstalowane:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip
```

## Uruchomienie minera

```bash
python3 miners/linux/rustchain_linux_miner.py --wallet YOUR_WALLET_ID
```

Użyj portfela lub identyfikatora, który później rozpoznasz. Wypłaty bounty mogą używać `github:twoj-login`, ale zwykłe kopanie używa wartości przekazanej przez `--wallet`.

## Zgoda przy pierwszym uruchomieniu

Przy pierwszym interaktywnym uruchomieniu użytkownik musi wyraźnie potwierdzić, że rozumie:

- miner wysyła `fingerprint` i dane `attestation` do węzła RustChain;
- komendy weryfikacyjne powinny być użyte przed kopaniem;
- nagrody w `RTC` nie są gwarantowane;
- maszyna musi przedstawić się uczciwie, bez spoofingu sprzętu.

Polska odpowiedź twierdząca: `TAK`.

## Odnośnik

Krótkie wyjaśnienie protokołu i zachowanych terminów znajduje się tutaj:

- [RUSTCHAIN_EXPLAINED.md](../../docs/pl-PL/RUSTCHAIN_EXPLAINED.md)

## Słownik

| Termin | Jak zachowac | Uwaga |
|---|---|---|
| `RTC` | `RTC` | Natywny token RustChain. |
| `attestation` | `attestation` | Dowód wysyłany do węzła o maszynie. |
| `antiquity` | `antiquity` | Wiek/rzadkość używana w mnożniku. |
| `fingerprint` | `fingerprint` | Zestaw sygnałów sprzętowych. |
