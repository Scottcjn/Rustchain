# RustChain Mining Status Badge Action

A reusable GitHub Action that writes a RustChain mining status badge into a README file.

## Usage

```yaml
- uses: ./.github/actions/mining-status-badge
  with:
    wallet: my-wallet-name
    readme-path: README.md
    badge-style: flat-square
```

## Inputs

- `wallet` (required): RustChain wallet used in `/api/badge/{wallet}`.
- `readme-path` (default: `README.md`): Target file.
- `badge-style` (default: `flat-square`): Shields.io badge style.

## Behavior

If the marker block exists, it is replaced:

```md
<!-- rustchain-mining-badge-start -->
![RustChain Mining Status](https://img.shields.io/endpoint?...)
<!-- rustchain-mining-badge-end -->
```

If missing, a new section `## Mining Status` is appended to the file.
