# RustChain live balance verifier

Tier: T2 verify integration for bounty #13040.

## Run

```bash
python3 integrations/thenaturelover343-jpg/rustchain_live_balance_verifier.py \
  --wallet RTC789488a6053e782d99d7242591603407ff515ce1
```

Optional node override:

```bash
python3 integrations/thenaturelover343-jpg/rustchain_live_balance_verifier.py \
  --node-url https://rustchain.org \
  --wallet RTC789488a6053e782d99d7242591603407ff515ce1
```

## Checks

`/health`: requires `ok: true`.

`/epoch`: requires a non-negative epoch and positive total supply.

`/api/miners`: requires a non-empty miners list.

`/wallet/balance`: requires the returned `miner_id` or `wallet_id` to match the requested wallet.

`amount_i64`: when present, must equal `amount_rtc * 1_000_000`.

## Live output

```text
$ python3 integrations/thenaturelover343-jpg/rustchain_live_balance_verifier.py --wallet RTC789488a6053e782d99d7242591603407ff515ce1
RustChain live balance verifier
node: https://rustchain.org
health: ok=true version=2.2.1-rip200
epoch: 183 slot=26406 supply=8388608
miners: count=18 first=bb
balance: wallet=RTC789488a6053e782d99d7242591603407ff515ce1 amount_rtc=0.0 amount_i64=0
verification: PASS
```
