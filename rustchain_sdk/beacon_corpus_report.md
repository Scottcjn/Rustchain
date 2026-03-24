# Beacon Relay Smoke Test Report

- Timestamp: 2026-02-14T23:01:04.619506+00:00
- Node health: ok=True backup_age_hours=19.669464161396025 tip_age_slots=0
- Epoch: 74 (blocks/epoch 144, enrolled_miners 11)

## Top 5 miner attests by timestamp
- apple_silicon_c318209d4dadd5e8b2f91e08999d1af7efec85RTC (multiplier 1.2) last attest 2026-02-14T23:01:04+00:00
- eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC (multiplier 2.5) last attest 2026-02-14T23:01:02+00:00
- RTC-agent-frog (multiplier 1.0) last attest 2026-02-14T23:00:16+00:00
- cinder-b550-126 (multiplier 1.0) last attest 2026-02-14T22:58:52+00:00
- modern-sophia-Pow-9862e3be (multiplier 1.0) last attest 2026-02-14T22:57:11+00:00

## Beacon relay check
- `attest/challenge` + `attest/submit` endpoints respond within 1s (observed)
- No SSL errors when hitting Node 1 (k flag used), so we can automate future polls.
