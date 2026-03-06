# RTC Reward Analytics Dashboard

This dashboard adds reward transparency views on top of the existing explorer service.

## Endpoints

- Page: `/reward-analytics`
- API: `/api/reward-analytics`

## What It Shows

1. Reward distribution per epoch (bar chart)
2. Top miner earnings over time (line chart)
3. Architecture reward breakdown (doughnut chart)
4. Multiplier impact model for current epoch (equal share vs weighted share)

## Data Sources

- Node API: `GET /epoch`
- Local DB:
  - `epoch_rewards` (reward history)
  - `epoch_enroll` (current epoch weights)
  - `miner_attest_recent` (architecture mapping)

The API route is resilient to partial/missing tables and returns empty arrays if one source is unavailable.

## Run

From the RustChain host (same as existing explorer):

```bash
python3 explorer/rustchain_dashboard.py
```

Open:

- `http://localhost:8099/reward-analytics`

## Notes

- Charts refresh every 30 seconds.
- If historical reward tables are missing, the page still renders with available data.
