# RustChain wyjaśniony (pl-PL)

RustChain to sieć Proof-of-Antiquity, która nagradza realne maszyny, szczególnie starszy sprzęt, za udowodnienie, że nadal działają. Główna idea jest prosta: zachowany sprzęt ma wartość, a sieć musi umieć odróżnić prawdziwą maszynę od VM, kontenera lub sfabrykowanej deklaracji.

## Jak działa weryfikacja

Miner zbiera lokalne sygnały i wysyła `attestation` do węzła RustChain. Ta `attestation` zawiera sprzętowy `fingerprint`. Węzeł używa tych danych do oszacowania `antiquity` maszyny i obliczenia mnożnika nagrody.

Proces musi być uczciwy:

- nie wymyślaj architektury;
- nie wymuszaj rodziny CPU, której maszyna nie posiada;
- nie zmieniaj payload, aby sprzęt wyglądał na starszy;
- nie tłumacz flag komend ani nazw endpointów.

## Sprawdź przed kopaniem

Przed zostawieniem minera w pracy użyj poniższych komend:

```bash
python3 miners/linux/rustchain_linux_miner.py --dry-run --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --show-payload --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --test-only --wallet YOUR_WALLET_ID
```

Te komendy pomagają sprawdzić wykrytą maszynę, payload `attestation` i łączność z węzłem. W dokumentacji lokalizowanej muszą pozostać dokładnie w tej formie.

## Na co zgadza się użytkownik

Potwierdzając pierwsze uruchomienie, użytkownik deklaruje, że rozumie:

1. miner może wysyłać dane `fingerprint` i `attestation`;
2. sprzęt musi być raportowany uczciwie;
3. nagrody w `RTC` zależą od akceptacji sieci i nie są gwarantowane;
4. spoofing, nieujawniona emulacja albo sfabrykowany payload mogą obniżyć nagrody albo spowodować odrzucenie.

Polski ekran zgody musi wymagać wyraźnego wpisu twierdzącego, np. `TAK`. Samo naciśnięcie Enter nie może rozpocząć kopania.

## Zachowany słownik

| Termin | Znaczenie operacyjne |
|---|---|
| `RTC` | Token używany przez RustChain do nagród i bounty. |
| `attestation` | Weryfikowalna deklaracja maszyny wysyłana do węzła. |
| `antiquity` | Sygnał wieku, rzadkości i zachowania sprzętu. |
| `fingerprint` | Zestaw sygnałów sprzętowych używanych do weryfikacji. |

## Przewodnik Linux miner

Zlokalizowany przewodnik Linux miner znajduje się tutaj:

- [miners/linux/README.pl-PL.md](../../miners/linux/README.pl-PL.md)
