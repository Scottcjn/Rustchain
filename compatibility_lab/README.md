# RustChain Compatibility Lab

The Compatibility Lab defines and tests the stable, public read-only surface used by
node monitors, miners, wallets, and explorers:

- `GET /health`
- `GET /epoch`
- `GET /api/miners`
- `GET /wallet/balance?miner_id=...`

The canonical source is
[`read_only_api.openapi.json`](read_only_api.openapi.json), an OpenAPI 3.1 JSON
document whose response definitions use JSON Schema 2020-12. The contract was
derived from the handlers in
[`node/rustchain_v2_integrated_v2.2.1_rip200.py`](../node/rustchain_v2_integrated_v2.2.1_rip200.py).
The checked-in [generated reference](../docs/READ_ONLY_API_CONTRACT.md) is for
human review; do not edit it directly.

## Offline Validation

From the repository root:

```bash
python3 -m compatibility_lab validate
```

This command validates the contract's read-only invariants and the exact fixture
set declared by each operation. It uses only the Python standard library and makes
no network requests. Fixtures include healthy and unhealthy health responses,
miner pagination and error responses, and successful and invalid wallet lookups.

Run the complete CI-equivalent gate with:

```bash
python3 -m compatibility_lab ci
```

That additionally checks that the generated reference is current, that configured
local Markdown links resolve, and that API routes claimed by core docs are actually
registered as `GET` routes in the authoritative integrated node. This catches
broken documentation claims without probing a deployed service.

## Generated Docs

Regenerate the reference after changing the canonical JSON:

```bash
python3 -m compatibility_lab generate-docs
python3 -m compatibility_lab generate-docs --check
python3 -m compatibility_lab check-links
```

The generator is deterministic. CI runs check mode and fails if the checked-in file
does not exactly match the contract.

`validate` and `probe` work from an installed wheel. Docs generation, default
link checks, and `ci` inspect repository-owned files, so run them from a
RustChain checkout or pass `--repo-root /path/to/Rustchain`.

## Optional Live Probe

Live probing is opt-in and is never run by CI:

```bash
python3 -m compatibility_lab probe https://node.example \
  --miner-id compatibility-probe \
  --timeout 5
```

The probe constructs only the four contract URLs, sends only `GET`, and refuses
redirects. It has no
options for request bodies, credentials, write methods, or disabled TLS
verification. The timeout is capped at 30 seconds and each response is capped at
1 MiB. A valid non-200 response such as an unhealthy `503` or miner-list `429` is
accepted only when its body matches the schema declared for that status.

The wallet probe uses a syntactically valid identifier; unknown valid identifiers
are expected to return a zero balance. Choose an existing public miner ID only when
you intentionally want to validate its returned balance shape.

## Contract Changes

When an implementation response changes:

1. Inspect the production handler and every status branch.
2. Update the OpenAPI JSON and its declared fixtures together.
3. Regenerate the Markdown reference.
4. Run `python3 -m compatibility_lab ci` and the focused pytest module.

Do not add a route to the contract because another file proposes or documents it.
The integrated node must actually register the public `GET` route first. This keeps
the lab useful for resolving broken-doc reports such as
[`RustChain #7910`](https://github.com/Scottcjn/Rustchain/issues/7910).
