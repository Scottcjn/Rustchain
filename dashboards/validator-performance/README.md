# RustChain Validator Performance Dashboard

A static browser dashboard for monitoring validator activity from the public RustChain miner API.

## Metrics

| Metric | Source |
| --- | --- |
| Active validators | `/api/miners` rows with active/online/up status or recent attestation fields |
| Average attestations | `/api/miners` attestation count fields |
| Average latency | `/api/miners` latency fields |
| Top validator | Highest available performance, score, antiquity, or attestation value |
| Recent history | In-browser samples from each refresh |

## Usage

Open `index.html` directly or serve the directory locally:

```bash
python3 -m http.server 8080
```

Then open `http://localhost:8080/dashboards/validator-performance/`.
