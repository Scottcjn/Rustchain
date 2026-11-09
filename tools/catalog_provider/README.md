# Unattended RustChain Service Catalog Provider Daemon (`#17184`)

Polls `GET /catalog/orders?role=provider&status=requested`, executes repository review/audit work via pluggable `RepoReviewWorker`, writes the Markdown deliverable, computes its SHA-256 hash, calls `POST /catalog/orders/<id>/deliver`, and persists state atomically in `provider_state.json` and `status.json`.

## Live Public Provider Verification
- **Beacon Agent ID**: `bcn_cf42ef35704e`
- **RTC Wallet**: `RTCcf42ef35704e2e281a803afbfbbdb9ad961ec021`
- **Public Standing**: `GET https://rustchain.org/catalog/providers/bcn_cf42ef35704e` (`active_listings: 4`, `orders_delivered: 2`, `orders_accepted: 2`, `distinct_buyers_accepted: 2`)
