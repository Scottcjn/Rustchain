# RustChain Health Check Integration

Tiny T1 integration for bounty #13040.

What it does:
- Queries the live RustChain `/health` endpoint
- Parses the JSON response
- Prints a short human-readable status line

## Run

```bash
python integrations/kitwongpixel/rustchain_health_check.py --base-url https://rustchain.org
```

Optional:

```bash
python integrations/kitwongpixel/rustchain_health_check.py --base-url https://rustchain.org --path /health --pretty
```

## Live transcript

See `TRANSCRIPT.txt` for a real run against the live node.
