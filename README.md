# RustChain Welcome Bonus Program

Automated bonus distribution for new miners and developers.

## How to Use

Run the script to claim bonuses:

```bash
python src/bonus_program.py claim_miner <wallet> [hardware_type]
python src/bonus_program.py claim_dev <wallet> [bonus_type]
python src/bonus_program.py refer <referrer> <new_user> <type>
python src/bonus_program.py balance <wallet>
```

### Bonus Types

- **hardware_type**: `standard` (default), `real`, `vintage`
- **bonus_type**: `first_pr` (default), `first_bounty`
- **type** (for referral): `miner`, `dev`

## Configuration

Bonuses are defined in `src/bonus_program.py` under `BONUS_CONFIG`. Edit to adjust amounts.

## Notes

- One-time bonuses per wallet.
- Bonuses stack for each wallet.
- Claims are persisted in `claims.json`.
